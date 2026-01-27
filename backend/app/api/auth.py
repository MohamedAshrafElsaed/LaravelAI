# ============================================================================
# FILE: backend/app/api/auth.py (UPDATED)
# ============================================================================
"""
GitHub OAuth authentication routes with automatic team creation.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from pydantic import BaseModel
import logging

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    encrypt_token,
    get_current_user,
)
from app.models.models import User
from app.services.team_service import TeamService

logger = logging.getLogger(__name__)

router = APIRouter()


class TokenResponse(BaseModel):
    """Response model for token endpoints."""
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    """Response model for user data."""
    id: str
    username: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    has_personal_team: bool = False

    class Config:
        from_attributes = True


class TeamInfoResponse(BaseModel):
    """Team info in auth response."""
    id: str
    name: str
    slug: str
    is_personal: bool


class AuthResponse(BaseModel):
    """Response model for authentication."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    personal_team: Optional[TeamInfoResponse] = None


class CodeExchangeRequest(BaseModel):
    """Request model for code exchange."""
    code: str


@router.get("/github")
async def github_login():
    """
    Redirect to GitHub OAuth authorization page.

    This initiates the OAuth flow by redirecting the user to GitHub's
    authorization endpoint with the configured scopes.
    """
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.github_client_id}"
        f"&redirect_uri={settings.github_redirect_uri}"
        f"&scope=repo,read:user,user:email,read:org"
    )
    return RedirectResponse(url=github_auth_url)


@router.get("/github/callback")
async def github_callback(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle GitHub OAuth callback.

    This endpoint:
    1. Exchanges the authorization code for an access token
    2. Fetches user information from GitHub
    3. Creates or updates the user in our database
    4. Creates a personal team for new users
    5. Returns a JWT token for authentication
    """
    logger.info("[AUTH] GitHub callback received")

    # Exchange code for GitHub access token
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": settings.github_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )

        if token_response.status_code != 200:
            logger.error(f"[AUTH] GitHub token exchange failed: {token_response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange code for token",
            )

        token_data = token_response.json()
        github_token = token_data.get("access_token")

        if not github_token:
            logger.error(f"[AUTH] No access token in response: {token_data}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access token received from GitHub",
            )

        # Fetch user info from GitHub
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/json",
            },
        )

        if user_response.status_code != 200:
            logger.error(f"[AUTH] GitHub user fetch failed: {user_response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch user info from GitHub",
            )

        github_user = user_response.json()

        # Fetch user email if not public
        email = github_user.get("email")
        if not email:
            emails_response = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/json",
                },
            )
            if emails_response.status_code == 200:
                emails = emails_response.json()
                primary_email = next(
                    (e for e in emails if e.get("primary")), None
                )
                if primary_email:
                    email = primary_email.get("email")

    # Check if user exists
    stmt = select(User).where(User.github_id == github_user["id"])
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    is_new_user = user is None

    if user:
        # Update existing user
        logger.info(f"[AUTH] Updating existing user: {github_user['login']}")
        user.username = github_user["login"]
        user.email = email
        user.avatar_url = github_user.get("avatar_url")
        user.github_access_token = encrypt_token(github_token)
        user.github_token_expires_at = datetime.utcnow() + timedelta(hours=8)
        user.updated_at = datetime.utcnow()
    else:
        # Create new user
        logger.info(f"[AUTH] Creating new user: {github_user['login']}")
        user = User(
            github_id=github_user["id"],
            username=github_user["login"],
            email=email,
            avatar_url=github_user.get("avatar_url"),
            github_access_token=encrypt_token(github_token),
            github_token_expires_at=datetime.utcnow() + timedelta(hours=8),
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    # Create personal team for new users
    team_service = TeamService(db)
    personal_team = await team_service.get_user_personal_team(str(user.id))
    
    if not personal_team:
        logger.info(f"[AUTH] Creating personal team for user: {user.username}")
        personal_team = await team_service.create_personal_team(user)

    # Create JWT token
    access_token = create_access_token(user_id=str(user.id))


    logger.info(f"[AUTH] Authentication successful for user: {user.username}")

    # Redirect to frontend with token
    redirect_url = f"{settings.frontend_url}/auth/callback?token={access_token}"
    return RedirectResponse(url=redirect_url)


@router.post("/exchange", response_model=AuthResponse)
async def exchange_code(
    request: CodeExchangeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange authorization code for access token (for SPA flow).
    
    This is an alternative to the callback redirect for single-page apps
    that handle the OAuth flow themselves.
    """
    logger.info("[AUTH] Code exchange requested")

    async with httpx.AsyncClient() as client:
        # Exchange code for GitHub token
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": request.code,
            },
            headers={"Accept": "application/json"},
        )

        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange code for token",
            )

        token_data = token_response.json()
        github_token = token_data.get("access_token")

        if not github_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access token received",
            )

        # Fetch user info
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/json",
            },
        )

        if user_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch user info",
            )

        github_user = user_response.json()

        # Fetch email
        email = github_user.get("email")
        if not email:
            emails_response = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/json",
                },
            )
            if emails_response.status_code == 200:
                emails = emails_response.json()
                primary = next((e for e in emails if e.get("primary")), None)
                if primary:
                    email = primary.get("email")

    # Find or create user
    stmt = select(User).where(User.github_id == github_user["id"])
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        user.username = github_user["login"]
        user.email = email
        user.avatar_url = github_user.get("avatar_url")
        user.github_access_token = encrypt_token(github_token)
        user.github_token_expires_at = datetime.utcnow() + timedelta(hours=8)
        user.updated_at = datetime.utcnow()
    else:
        user = User(
            github_id=github_user["id"],
            username=github_user["login"],
            email=email,
            avatar_url=github_user.get("avatar_url"),
            github_access_token=encrypt_token(github_token),
            github_token_expires_at=datetime.utcnow() + timedelta(hours=8),
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    # Create/get personal team
    team_service = TeamService(db)
    personal_team = await team_service.get_user_personal_team(str(user.id))
    
    if not personal_team:
        personal_team = await team_service.create_personal_team(user)

    # Create JWT
    access_token = create_access_token(user_id=str(user.id))

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            avatar_url=user.avatar_url,
            has_personal_team=True,
        ),
        personal_team=TeamInfoResponse(
            id=personal_team.id,
            name=personal_team.name,
            slug=personal_team.slug,
            is_personal=personal_team.is_personal,
        ),
    )


@router.get("/me", response_model=AuthResponse)
async def get_current_user_info(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user info including team."""
    team_service = TeamService(db)
    personal_team = await team_service.get_user_personal_team(str(current_user.id))

    return AuthResponse(
        access_token="",  # Not returned for security
        token_type="bearer",
        user=UserResponse(
            id=str(current_user.id),
            username=current_user.username,
            email=current_user.email,
            avatar_url=current_user.avatar_url,
            has_personal_team=personal_team is not None,
        ),
        personal_team=TeamInfoResponse(
            id=personal_team.id,
            name=personal_team.name,
            slug=personal_team.slug,
            is_personal=personal_team.is_personal,
        ) if personal_team else None,
    )


@router.post("/logout")
async def logout():
    """
    Logout endpoint.
    
    Since we use JWT tokens, the actual logout happens client-side
    by removing the token. This endpoint is here for completeness.
    """
    return {"message": "Logged out successfully"}