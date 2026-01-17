"""Project/repository management routes."""
import shutil
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from github import Github, GithubException

from app.core.database import get_db
from app.core.security import get_current_user, decrypt_token
from app.models.models import Project, ProjectStatus, User, IndexedFile

router = APIRouter()


class ProjectCreate(BaseModel):
    """Request model for creating a project."""
    github_repo_id: int


class ProjectResponse(BaseModel):
    """Project response model."""
    id: str
    name: str
    repo_full_name: str
    repo_url: str
    default_branch: str
    clone_path: Optional[str]
    status: ProjectStatus
    indexed_files_count: int
    laravel_version: Optional[str]
    error_message: Optional[str]
    last_indexed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectDetailResponse(ProjectResponse):
    """Detailed project response with additional info."""
    php_version: Optional[str]


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ProjectResponse]:
    """List all projects for current user."""
    stmt = select(Project).where(Project.user_id == current_user.id).order_by(
        Project.updated_at.desc()
    )
    result = await db.execute(stmt)
    projects = result.scalars().all()
    return projects


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new project from a GitHub repository.

    This will:
    1. Validate the GitHub repo exists and user has access
    2. Check if project already exists for this user/repo
    3. Create the project record
    4. Trigger a background clone job
    """
    # Check if project already exists for this user
    stmt = select(Project).where(
        Project.user_id == current_user.id,
        Project.github_repo_id == project_data.github_repo_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project already exists for this repository.",
        )

    # Fetch repo details from GitHub
    try:
        github_token = decrypt_token(current_user.github_access_token)
        g = Github(github_token)
        repo = g.get_repo(project_data.github_repo_id)
    except GithubException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found or you don't have access.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error: {str(e)}",
        )

    # Create project
    project = Project(
        user_id=current_user.id,
        github_repo_id=repo.id,
        name=repo.name,
        repo_full_name=repo.full_name,
        repo_url=repo.html_url,
        default_branch=repo.default_branch or "main",
        status=ProjectStatus.PENDING,
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    # TODO: Trigger background clone job
    # background_tasks.add_task(clone_and_index_project, project.id, github_token)

    return project


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectDetailResponse:
    """Get a specific project by ID."""
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a project and cleanup associated resources.

    This will:
    1. Delete the project record (cascades to indexed_files, conversations)
    2. Remove the cloned repository from disk if it exists
    """
    # Fetch project
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    # Cleanup cloned repo directory if it exists
    if project.clone_path:
        try:
            shutil.rmtree(project.clone_path, ignore_errors=True)
        except Exception:
            # Log but don't fail deletion
            pass

    # Delete project (cascade will handle related records)
    await db.delete(project)
    await db.commit()


@router.post("/{project_id}/index", response_model=ProjectResponse)
async def start_indexing(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start or re-index a project's codebase.

    This will trigger a background job to:
    1. Pull latest changes from GitHub
    2. Parse and index all PHP/Laravel files
    3. Generate vector embeddings for semantic search
    """
    # Fetch project
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    if project.status == ProjectStatus.INDEXING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project is already being indexed.",
        )

    if project.status == ProjectStatus.CLONING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project is currently being cloned.",
        )

    # Update status to indexing
    project.status = ProjectStatus.INDEXING
    project.error_message = None
    await db.commit()
    await db.refresh(project)

    # TODO: Trigger background indexing job
    # background_tasks.add_task(index_project, project.id)

    return project


@router.post("/{project_id}/clone", response_model=ProjectResponse)
async def start_cloning(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Clone or re-clone a project's repository.
    """
    # Fetch project
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    if project.status in [ProjectStatus.CLONING, ProjectStatus.INDEXING]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project is currently being {project.status.value}.",
        )

    # Update status to cloning
    project.status = ProjectStatus.CLONING
    project.error_message = None
    await db.commit()
    await db.refresh(project)

    # TODO: Trigger background clone job
    # github_token = decrypt_token(current_user.github_access_token)
    # background_tasks.add_task(clone_project, project.id, github_token)

    return project
