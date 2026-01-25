"""GitHub App authentication service."""
import time
import logging
from typing import Optional

import jwt
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.github_app_models import GitHubAppInstallation

logger = logging.getLogger(__name__)


class GitHubAppError(Exception):
    pass


class GitHubAppService:
    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self._private_key = self._load_private_key()

    def _load_private_key(self) -> Optional[str]:
        if settings.github_app_private_key_path:
            try:
                with open(settings.github_app_private_key_path) as f:
                    return f.read()
            except FileNotFoundError:
                pass
        if settings.github_app_private_key:
            import base64
            try:
                return base64.b64decode(settings.github_app_private_key).decode()
            except Exception:
                return settings.github_app_private_key
        return None

    def _generate_jwt(self) -> str:
        if not self._private_key:
            raise GitHubAppError("No GitHub App private key configured")
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 600, "iss": settings.github_app_id}
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    async def get_installation_token(self, installation_id: int) -> str:
        app_jwt = self._generate_jwt()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={"Authorization": f"Bearer {app_jwt}", "Accept": "application/vnd.github+json"},
            )
            if resp.status_code != 201:
                raise GitHubAppError(f"Failed to get installation token: {resp.status_code}")
            return resp.json()["token"]

    async def get_user_installation(self, user_id: str) -> Optional[GitHubAppInstallation]:
        if not self.db:
            return None
        stmt = select(GitHubAppInstallation).where(
            GitHubAppInstallation.user_id == user_id,
            GitHubAppInstallation.is_active == True,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_token_for_user(self, user_id: str) -> Optional[str]:
        installation = await self.get_user_installation(user_id)
        if not installation:
            return None
        return await self.get_installation_token(installation.installation_id)

    async def save_installation(self, user_id: str, installation_id: int, account_login: str, account_type: str):
        if not self.db:
            raise GitHubAppError("DB required")
        stmt = select(GitHubAppInstallation).where(GitHubAppInstallation.installation_id == installation_id)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.user_id = user_id
            existing.is_active = True
        else:
            self.db.add(GitHubAppInstallation(
                user_id=user_id, installation_id=installation_id,
                account_login=account_login, account_type=account_type,
            ))
        await self.db.commit()