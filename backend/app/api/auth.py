"""GitHub OAuth authentication routes."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    encrypt_token,
    get_current_user,
)
from app.models.models import User

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

    class Config:
        from_attributes = True


class CodeExchangeRequest(BaseModel):
    """Request model for code exchange."""
    code: str


class AuthResponse(BaseModel):
    """Response model for authentication."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


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
        f"&scope=repo,read:user,user:email"
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
    4. Returns a JWT for subsequent API requests
    """
    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )

        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to authenticate with GitHub",
            )

        token_data = token_response.json()
        github_token = token_data.get("access_token")

        if not github_token:
            error = token_data.get("error_description", "No access token received")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"GitHub OAuth error: {error}",
            )

        # Get user info from GitHub
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/json",
            },
        )

        if user_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to fetch user info from GitHub",
            )

        github_user = user_response.json()

        # Get user email (may be private)
        email_response = await client.get(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/json",
            },
        )
        emails = email_response.json() if email_response.status_code == 200 else []
        primary_email = next(
            (e["email"] for e in emails if e.get("primary")), None
        )

    # Encrypt the GitHub token before storage
    encrypted_token = encrypt_token(github_token)

    # Find or create user
    stmt = select(User).where(User.github_id == github_user["id"])
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Update existing user
        user.github_access_token = encrypted_token
        user.avatar_url = github_user.get("avatar_url")
        user.username = github_user["login"]  # Username might change
        if primary_email:
            user.email = primary_email
    else:
        # Create new user
        user = User(
            github_id=github_user["id"],
            username=github_user["login"],
            email=primary_email,
            avatar_url=github_user.get("avatar_url"),
            github_access_token=encrypted_token,
        )
        db.add(user)

    await db.flush()

    # Create our JWT (7-day expiry configured in settings)
    access_token = create_access_token(user.id)

    # Redirect to frontend with token
    redirect_url = f"{settings.frontend_url}/auth/success?token={access_token}"
    return RedirectResponse(url=redirect_url)


@router.post("/github/callback", response_model=AuthResponse)
async def github_callback_post(
    request: CodeExchangeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle GitHub OAuth callback via POST (for frontend-initiated flow).

    This endpoint accepts the authorization code in the request body
    and returns the JWT token directly instead of redirecting.
    """
    code = request.code

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )

        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to authenticate with GitHub",
            )

        token_data = token_response.json()
        github_token = token_data.get("access_token")

        if not github_token:
            error = token_data.get("error_description", "No access token received")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"GitHub OAuth error: {error}",
            )

        # Get user info from GitHub
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/json",
            },
        )

        if user_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to fetch user info from GitHub",
            )

        github_user = user_response.json()

        # Get user email (may be private)
        email_response = await client.get(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/json",
            },
        )
        emails = email_response.json() if email_response.status_code == 200 else []
        primary_email = next(
            (e["email"] for e in emails if e.get("primary")), None
        )

    # Encrypt the GitHub token before storage
    encrypted_token = encrypt_token(github_token)

    # Find or create user
    stmt = select(User).where(User.github_id == github_user["id"])
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Update existing user
        user.github_access_token = encrypted_token
        user.avatar_url = github_user.get("avatar_url")
        user.username = github_user["login"]
        if primary_email:
            user.email = primary_email
    else:
        # Create new user
        user = User(
            github_id=github_user["id"],
            username=github_user["login"],
            email=primary_email,
            avatar_url=github_user.get("avatar_url"),
            github_access_token=encrypted_token,
        )
        db.add(user)

    await db.flush()

    # Create JWT
    access_token = create_access_token(user.id)

    return AuthResponse(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            avatar_url=user.avatar_url,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Get the current authenticated user.

    Requires a valid JWT in the Authorization header.

    Returns:
        UserResponse: The authenticated user's public profile data
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        avatar_url=current_user.avatar_url,
    )
