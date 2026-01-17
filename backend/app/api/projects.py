"""Project/repository management routes."""
import asyncio
import shutil
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from pydantic import BaseModel
from github import Github, GithubException

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_user, decrypt_token
from app.models.models import Project, ProjectStatus, User, IndexedFile
from app.services.git_service import GitService, GitServiceError
from app.services.indexer import (
    ProjectIndexer,
    get_indexing_progress,
    IndexingProgress,
    IndexingPhase,
)
from app.services.embeddings import EmbeddingProvider
from app.services.vector_store import VectorStore

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


class IndexingStatusResponse(BaseModel):
    """Response model for indexing status."""
    status: str
    progress: int
    phase: str
    current_file: Optional[str]
    total_files: int
    processed_files: int
    total_chunks: int
    error: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]


# Background task helper for creating a new database session
async def get_background_db():
    """Create a new database session for background tasks."""
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
    await engine.dispose()


async def clone_project_task(
    project_id: str,
    github_token: str,
) -> None:
    """
    Background task to clone a project repository.

    Args:
        project_id: The project's UUID
        github_token: GitHub access token
    """
    # Create a new database session for background task
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as db:
        try:
            # Fetch project
            stmt = select(Project).where(Project.id == project_id)
            result = await db.execute(stmt)
            project = result.scalar_one_or_none()

            if not project:
                return

            # Clone repository
            git_service = GitService(github_token)
            clone_path = git_service.clone_repo(
                project_id=str(project.id),
                repo_full_name=project.repo_full_name,
                branch=project.default_branch,
            )

            # Update project with clone path
            project.clone_path = clone_path
            project.status = ProjectStatus.PENDING  # Ready for indexing
            project.error_message = None
            await db.commit()

        except GitServiceError as e:
            # Update project with error
            stmt = select(Project).where(Project.id == project_id)
            result = await db.execute(stmt)
            project = result.scalar_one_or_none()
            if project:
                project.status = ProjectStatus.ERROR
                project.error_message = str(e)
                await db.commit()

        except Exception as e:
            # Update project with error
            stmt = select(Project).where(Project.id == project_id)
            result = await db.execute(stmt)
            project = result.scalar_one_or_none()
            if project:
                project.status = ProjectStatus.ERROR
                project.error_message = f"Unexpected error: {str(e)}"
                await db.commit()

    await engine.dispose()


async def index_project_task(
    project_id: str,
    embedding_provider: str = "openai",
) -> None:
    """
    Background task to index a project codebase.

    Args:
        project_id: The project's UUID
        embedding_provider: Embedding provider to use
    """
    # Create a new database session for background task
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as db:
        try:
            # Determine embedding provider
            provider = (
                EmbeddingProvider.VOYAGE
                if embedding_provider == "voyage"
                else EmbeddingProvider.OPENAI
            )

            # Create indexer and run
            indexer = ProjectIndexer(
                db=db,
                embedding_provider=provider,
            )

            await indexer.index_project(project_id)

        except Exception as e:
            # Update project with error
            stmt = select(Project).where(Project.id == project_id)
            result = await db.execute(stmt)
            project = result.scalar_one_or_none()
            if project:
                project.status = ProjectStatus.ERROR
                project.error_message = f"Indexing failed: {str(e)}"
                await db.commit()

    await engine.dispose()


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
        status=ProjectStatus.CLONING,  # Start cloning immediately
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    # Trigger background clone job
    background_tasks.add_task(
        clone_project_task,
        str(project.id),
        github_token,
    )

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
    3. Delete the vector collection from Qdrant
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

    # Cleanup vector collection
    try:
        vector_store = VectorStore()
        vector_store.delete_collection(str(project.id))
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
    1. Scan all PHP/Laravel files
    2. Parse and extract code structure
    3. Generate vector embeddings for semantic search
    4. Store embeddings in Qdrant
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
            detail="Project is currently being cloned. Wait for cloning to complete.",
        )

    if not project.clone_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has not been cloned yet. Clone the repository first.",
        )

    # Update status to indexing
    project.status = ProjectStatus.INDEXING
    project.error_message = None
    await db.commit()
    await db.refresh(project)

    # Trigger background indexing job
    background_tasks.add_task(
        index_project_task,
        str(project.id),
    )

    return project


@router.get("/{project_id}/index/status", response_model=IndexingStatusResponse)
async def get_indexing_status(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current indexing progress for a project.

    Returns status information including:
    - Current phase (scanning, parsing, embedding, storing)
    - Progress percentage (0-100)
    - Current file being processed
    - Error information if failed
    """
    # Verify project access
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

    # Get progress from in-memory tracker
    progress = get_indexing_progress(project_id)

    if progress:
        return IndexingStatusResponse(
            status=progress.phase.value,
            progress=progress.progress,
            phase=progress.phase.value,
            current_file=progress.current_file,
            total_files=progress.total_files,
            processed_files=progress.processed_files,
            total_chunks=progress.total_chunks,
            error=progress.error,
            started_at=progress.started_at.isoformat() if progress.started_at else None,
            completed_at=progress.completed_at.isoformat() if progress.completed_at else None,
        )

    # No active progress - return status based on project state
    if project.status == ProjectStatus.INDEXING:
        return IndexingStatusResponse(
            status="indexing",
            progress=0,
            phase="starting",
            current_file=None,
            total_files=0,
            processed_files=0,
            total_chunks=0,
            error=None,
            started_at=None,
            completed_at=None,
        )
    elif project.status == ProjectStatus.READY:
        return IndexingStatusResponse(
            status="completed",
            progress=100,
            phase="completed",
            current_file=None,
            total_files=project.indexed_files_count,
            processed_files=project.indexed_files_count,
            total_chunks=0,
            error=None,
            started_at=None,
            completed_at=project.last_indexed_at.isoformat() if project.last_indexed_at else None,
        )
    elif project.status == ProjectStatus.ERROR:
        return IndexingStatusResponse(
            status="error",
            progress=0,
            phase="error",
            current_file=None,
            total_files=0,
            processed_files=0,
            total_chunks=0,
            error=project.error_message,
            started_at=None,
            completed_at=None,
        )
    else:
        return IndexingStatusResponse(
            status="pending",
            progress=0,
            phase="pending",
            current_file=None,
            total_files=0,
            processed_files=0,
            total_chunks=0,
            error=None,
            started_at=None,
            completed_at=None,
        )


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

    # Get GitHub token and trigger clone
    github_token = decrypt_token(current_user.github_access_token)
    background_tasks.add_task(
        clone_project_task,
        str(project.id),
        github_token,
    )

    return project
