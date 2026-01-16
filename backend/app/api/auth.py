"""GitHub OAuth authentication routes."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from jose import jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.models.models import User

router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str]
    avatar_url: Optional[str]


def create_access_token(user_id: str) -> str:
    """Create JWT access token."""
    expire = datetime.utcnow() + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


@router.get("/github")
async def github_login():
    """Redirect to GitHub OAuth."""
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
    """Handle GitHub OAuth callback."""
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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No access token received from GitHub",
            )

        # Get user info from GitHub
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/json",
            },
        )
        github_user = user_response.json()

        # Get user email
        email_response = await client.get(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/json",
            },
        )
        emails = email_response.json()
        primary_email = next(
            (e["email"] for e in emails if e.get("primary")), None
        )

    # Find or create user
    stmt = select(User).where(User.github_id == github_user["id"])
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Update existing user
        user.github_access_token = github_token
        user.avatar_url = github_user.get("avatar_url")
        if primary_email:
            user.email = primary_email
    else:
        # Create new user
        user = User(
            github_id=github_user["id"],
            username=github_user["login"],
            email=primary_email,
            avatar_url=github_user.get("avatar_url"),
            github_access_token=github_token,
        )
        db.add(user)

    await db.flush()

    # Create our JWT
    access_token = create_access_token(user.id)

    # Redirect to frontend with token
    redirect_url = f"{settings.frontend_url}/auth/success?token={access_token}"
    return RedirectResponse(url=redirect_url)


@router.get("/me", response_model=UserResponse)
async def get_current_user(
        db: AsyncSession = Depends(get_db),
        # TODO: Add auth dependency
):
    """Get current authenticated user."""
    # This will be implemented with auth dependency
    raise HTTPException(status_code=501, detail="Not implemented yet")
