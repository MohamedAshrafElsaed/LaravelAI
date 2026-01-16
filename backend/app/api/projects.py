"""Project/repository management routes."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.models.models import Project, ProjectStatus

router = APIRouter()


class ProjectCreate(BaseModel):
    repo_full_name: str  # owner/repo format


class ProjectResponse(BaseModel):
    id: str
    repo_full_name: str
    repo_url: str
    status: ProjectStatus
    indexed_files_count: int
    laravel_version: str | None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
        db: AsyncSession = Depends(get_db),
        # TODO: Add user dependency
):
    """List all projects for current user."""
    # Placeholder - will add auth
    return []


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
        project: ProjectCreate,
        db: AsyncSession = Depends(get_db),
):
    """Connect a new GitHub repository."""
    # TODO: Implement with GitHub API validation
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/{project_id}/index")
async def start_indexing(
        project_id: str,
        db: AsyncSession = Depends(get_db),
):
    """Start indexing a project's codebase."""
    # TODO: Queue indexing job
    raise HTTPException(status_code=501, detail="Not implemented yet")