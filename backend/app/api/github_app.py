"""GitHub App installation endpoints."""
import logging
import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_user
from app.models.models import User
from app.services.github_app_service import GitHubAppService

logger = logging.getLogger(__name__)
router = APIRouter()


class InstallationStatus(BaseModel):
    installed: bool
    installation_id: Optional[int] = None
    account_login: Optional[str] = None
    install_url: str = f"https://github.com/apps/{settings.github_app_name}/installations/new"


@router.get("/install")
async def install_app(current_user: User = Depends(get_current_user)):
    """Redirect to GitHub App installation."""
    return RedirectResponse(f"https://github.com/apps/{settings.github_app_name}/installations/new")


@router.get("/callback")
async def callback(
        installation_id: int = Query(...),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Handle installation callback."""
    service = GitHubAppService(db)
    app_jwt = service._generate_jwt()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/app/installations/{installation_id}",
            headers={"Authorization": f"Bearer {app_jwt}", "Accept": "application/vnd.github+json"},
        )
        if resp.status_code == 200:
            data = resp.json()
            account = data.get("account", {})
            await service.save_installation(
                str(current_user.id), installation_id,
                account.get("login", "unknown"), account.get("type", "User"),
            )

    return RedirectResponse(f"{settings.frontend_url}/settings?github_app=installed")


@router.get("/status", response_model=InstallationStatus)
async def status(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Check installation status."""
    service = GitHubAppService(db)
    inst = await service.get_user_installation(str(current_user.id))
    if inst:
        return InstallationStatus(installed=True, installation_id=inst.installation_id,
                                  account_login=inst.account_login)
    return InstallationStatus(installed=False)