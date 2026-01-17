"""Project/repository management routes."""
import asyncio
import shutil
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

logger = logging.getLogger(__name__)
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
    status: str
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


async def clone_and_index_project_task(
    project_id: str,
    github_token: str,
    embedding_provider: str = "openai",
) -> None:
    """
    Background task to clone a project repository and then index it.
    This chains cloning → indexing automatically.

    Args:
        project_id: The project's UUID
        github_token: GitHub access token
        embedding_provider: Embedding provider to use for indexing
    """
    logger.info(f"[CLONE_INDEX_TASK] Starting clone and index task for project_id={project_id}")

    # Create a new database session for background task
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    logger.debug(f"[CLONE_INDEX_TASK] Database session created for project_id={project_id}")

    async with async_session() as db:
        try:
            # Fetch project
            logger.debug(f"[CLONE_INDEX_TASK] Fetching project from database: {project_id}")
            stmt = select(Project).where(Project.id == project_id)
            result = await db.execute(stmt)
            project = result.scalar_one_or_none()

            if not project:
                logger.error(f"[CLONE_INDEX_TASK] Project not found in database: {project_id}")
                await engine.dispose()
                return

            logger.info(f"[CLONE_INDEX_TASK] Found project: {project.repo_full_name}, branch: {project.default_branch}")

            # ========== PHASE 1: CLONE ==========
            logger.info(f"[CLONE_INDEX_TASK] Phase 1: Starting git clone for {project.repo_full_name}")
            git_service = GitService(github_token)
            clone_path = git_service.clone_repo(
                project_id=str(project.id),
                repo_full_name=project.repo_full_name,
                branch=project.default_branch,
            )
            logger.info(f"[CLONE_INDEX_TASK] Clone successful, path: {clone_path}")

            # Update project with clone path and move to INDEXING status
            project.clone_path = clone_path
            project.status = ProjectStatus.INDEXING.value  # Go directly to indexing
            project.error_message = None
            await db.commit()
            logger.info(f"[CLONE_INDEX_TASK] Project status updated to INDEXING, clone_path saved")

            # ========== PHASE 2: INDEX ==========
            logger.info(f"[CLONE_INDEX_TASK] Phase 2: Starting indexing for project_id={project_id}")

            # Determine embedding provider
            provider = (
                EmbeddingProvider.VOYAGE
                if embedding_provider == "voyage"
                else EmbeddingProvider.OPENAI
            )
            logger.info(f"[CLONE_INDEX_TASK] Using embedding provider: {provider}")

            # Create indexer and run
            indexer = ProjectIndexer(
                db=db,
                embedding_provider=provider,
            )

            await indexer.index_project(project_id)
            logger.info(f"[CLONE_INDEX_TASK] Indexing completed successfully for {project_id}")

        except GitServiceError as e:
            logger.error(f"[CLONE_INDEX_TASK] Git service error for project {project_id}: {str(e)}")
            # Update project with error
            stmt = select(Project).where(Project.id == project_id)
            result = await db.execute(stmt)
            project = result.scalar_one_or_none()
            if project:
                project.status = ProjectStatus.ERROR.value
                project.error_message = f"Clone failed: {str(e)}"
                await db.commit()
                logger.info(f"[CLONE_INDEX_TASK] Project status updated to ERROR")

        except Exception as e:
            logger.exception(f"[CLONE_INDEX_TASK] Unexpected error for project {project_id}: {str(e)}")
            # Update project with error
            stmt = select(Project).where(Project.id == project_id)
            result = await db.execute(stmt)
            project = result.scalar_one_or_none()
            if project:
                project.status = ProjectStatus.ERROR.value
                project.error_message = f"Error: {str(e)}"
                await db.commit()
                logger.info(f"[CLONE_INDEX_TASK] Project status updated to ERROR")

    await engine.dispose()
    logger.info(f"[CLONE_INDEX_TASK] Clone and index task completed for project_id={project_id}")


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
    logger.info(f"[INDEX_TASK] Starting indexing task for project_id={project_id}")
    logger.info(f"[INDEX_TASK] Using embedding provider: {embedding_provider}")

    # Create a new database session for background task
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    logger.debug(f"[INDEX_TASK] Database session created for project_id={project_id}")

    async with async_session() as db:
        try:
            # Determine embedding provider
            provider = (
                EmbeddingProvider.VOYAGE
                if embedding_provider == "voyage"
                else EmbeddingProvider.OPENAI
            )
            logger.info(f"[INDEX_TASK] Resolved embedding provider: {provider}")

            # Create indexer and run
            logger.info(f"[INDEX_TASK] Creating ProjectIndexer instance")
            indexer = ProjectIndexer(
                db=db,
                embedding_provider=provider,
            )

            logger.info(f"[INDEX_TASK] Starting indexer.index_project for {project_id}")
            await indexer.index_project(project_id)
            logger.info(f"[INDEX_TASK] Indexing completed successfully for {project_id}")

        except Exception as e:
            logger.exception(f"[INDEX_TASK] Indexing failed for project {project_id}: {str(e)}")
            # Update project with error
            stmt = select(Project).where(Project.id == project_id)
            result = await db.execute(stmt)
            project = result.scalar_one_or_none()
            if project:
                project.status = ProjectStatus.ERROR.value
                project.error_message = f"Indexing failed: {str(e)}"
                await db.commit()
                logger.info(f"[INDEX_TASK] Project status updated to ERROR")

    await engine.dispose()
    logger.info(f"[INDEX_TASK] Index task completed for project_id={project_id}")


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ProjectResponse]:
    """List all projects for current user."""
    logger.info(f"[API] GET /projects - user_id={current_user.id}")
    stmt = select(Project).where(Project.user_id == current_user.id).order_by(
        Project.updated_at.desc()
    )
    result = await db.execute(stmt)
    projects = result.scalars().all()
    logger.info(f"[API] GET /projects - returning {len(projects)} projects")
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
    4. Trigger a background job to clone and index the repository

    Status flow: CLONING → INDEXING → READY (or ERROR)
    """
    logger.info(f"[API] POST /projects - user_id={current_user.id}, github_repo_id={project_data.github_repo_id}")

    # Check if project already exists for this user
    logger.debug(f"[API] Checking if project already exists for repo_id={project_data.github_repo_id}")
    stmt = select(Project).where(
        Project.user_id == current_user.id,
        Project.github_repo_id == project_data.github_repo_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        logger.warning(f"[API] Project already exists for repo_id={project_data.github_repo_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project already exists for this repository.",
        )

    # Fetch repo details from GitHub
    logger.info(f"[API] Fetching repo details from GitHub for repo_id={project_data.github_repo_id}")
    try:
        github_token = decrypt_token(current_user.github_access_token)
        g = Github(github_token)
        repo = g.get_repo(project_data.github_repo_id)
        logger.info(f"[API] GitHub repo found: {repo.full_name}")
    except GithubException as e:
        logger.error(f"[API] GitHub API error: {str(e)}")
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
    logger.info(f"[API] Creating project record for {repo.full_name}")
    project = Project(
        user_id=current_user.id,
        github_repo_id=repo.id,
        name=repo.name,
        repo_full_name=repo.full_name,
        repo_url=repo.html_url,
        default_branch=repo.default_branch or "main",
        status=ProjectStatus.CLONING.value,  # Start cloning immediately
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)
    logger.info(f"[API] Project created with id={project.id}, status={project.status}")

    # Trigger background clone and index job
    logger.info(f"[API] Triggering background clone+index task for project_id={project.id}")
    background_tasks.add_task(
        clone_and_index_project_task,
        str(project.id),
        github_token,
    )

    logger.info(f"[API] POST /projects completed - returning project_id={project.id}")
    return project


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectDetailResponse:
    """Get a specific project by ID."""
    logger.info(f"[API] GET /projects/{project_id} - user_id={current_user.id}")
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        logger.warning(f"[API] Project not found: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    logger.info(f"[API] GET /projects/{project_id} - returning project status={project.status}")
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
    logger.info(f"[API] DELETE /projects/{project_id} - user_id={current_user.id}")

    # Fetch project
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        logger.warning(f"[API] Project not found for deletion: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    logger.info(f"[API] Deleting project {project.repo_full_name}")

    # Cleanup cloned repo directory if it exists
    if project.clone_path:
        logger.info(f"[API] Removing cloned repo directory: {project.clone_path}")
        try:
            shutil.rmtree(project.clone_path, ignore_errors=True)
            logger.info(f"[API] Cloned repo directory removed successfully")
        except Exception as e:
            logger.warning(f"[API] Failed to remove clone directory: {str(e)}")

    # Cleanup vector collection
    logger.info(f"[API] Deleting vector collection for project_id={project.id}")
    try:
        vector_store = VectorStore()
        vector_store.delete_collection(str(project.id))
        logger.info(f"[API] Vector collection deleted successfully")
    except Exception as e:
        logger.warning(f"[API] Failed to delete vector collection: {str(e)}")

    # Delete project (cascade will handle related records)
    await db.delete(project)
    await db.commit()
    logger.info(f"[API] Project {project_id} deleted successfully")


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
    logger.info(f"[API] POST /projects/{project_id}/index - user_id={current_user.id}")

    # Fetch project
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        logger.warning(f"[API] Project not found for indexing: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    logger.info(f"[API] Project found: {project.repo_full_name}, current status={project.status}")

    if project.status == ProjectStatus.INDEXING.value:
        logger.warning(f"[API] Project {project_id} is already being indexed")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project is already being indexed.",
        )

    if project.status == ProjectStatus.CLONING.value:
        logger.warning(f"[API] Project {project_id} is currently being cloned")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project is currently being cloned. Wait for cloning to complete.",
        )

    if not project.clone_path:
        logger.warning(f"[API] Project {project_id} has no clone_path")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has not been cloned yet. Clone the repository first.",
        )

    logger.info(f"[API] Project clone_path: {project.clone_path}")

    # Update status to indexing
    project.status = ProjectStatus.INDEXING.value
    project.error_message = None
    await db.commit()
    await db.refresh(project)
    logger.info(f"[API] Project status updated to INDEXING")

    # Trigger background indexing job
    logger.info(f"[API] Triggering background indexing task for project_id={project.id}")
    background_tasks.add_task(
        index_project_task,
        str(project.id),
    )

    logger.info(f"[API] POST /projects/{project_id}/index completed")
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
    logger.debug(f"[API] GET /projects/{project_id}/index/status - user_id={current_user.id}")

    # Verify project access
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        logger.warning(f"[API] Project not found for status check: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    # Get progress from in-memory tracker
    progress = get_indexing_progress(project_id)
    logger.debug(f"[API] Project {project_id} - DB status={project.status}, in-memory progress={progress is not None}")

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
    if project.status == ProjectStatus.INDEXING.value:
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
    elif project.status == ProjectStatus.READY.value:
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
    elif project.status == ProjectStatus.ERROR.value:
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
    Clone or re-clone a project's repository and re-index it.

    Status flow: CLONING → INDEXING → READY (or ERROR)
    """
    logger.info(f"[API] POST /projects/{project_id}/clone - user_id={current_user.id}")

    # Fetch project
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        logger.warning(f"[API] Project not found for cloning: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    logger.info(f"[API] Project found: {project.repo_full_name}, current status={project.status}")

    if project.status in [ProjectStatus.CLONING.value, ProjectStatus.INDEXING.value]:
        logger.warning(f"[API] Project {project_id} is currently {project.status}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project is currently being {project.status}.",
        )

    # Update status to cloning
    project.status = ProjectStatus.CLONING.value
    project.error_message = None
    await db.commit()
    await db.refresh(project)
    logger.info(f"[API] Project status updated to CLONING")

    # Get GitHub token and trigger clone+index
    logger.info(f"[API] Triggering background clone+index task for project_id={project.id}")
    github_token = decrypt_token(current_user.github_access_token)
    background_tasks.add_task(
        clone_and_index_project_task,
        str(project.id),
        github_token,
    )

    logger.info(f"[API] POST /projects/{project_id}/clone completed")
    return project


# File tree response models
class FileNode(BaseModel):
    """A file or directory node."""
    name: str
    path: str
    type: str  # 'file' or 'directory'
    children: Optional[List["FileNode"]] = None
    indexed: bool = False


class FileContentResponse(BaseModel):
    """Response for file content."""
    path: str
    content: str
    indexed: bool


@router.get("/{project_id}/files", response_model=List[FileNode])
async def get_project_files(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the file tree structure for a project.

    Returns a hierarchical list of files and directories in the cloned repo.
    """
    logger.info(f"[API] GET /projects/{project_id}/files - user_id={current_user.id}")

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

    if not project.clone_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has not been cloned yet.",
        )

    import os

    # Get indexed file paths for marking
    stmt = select(IndexedFile.file_path).where(IndexedFile.project_id == project_id)
    result = await db.execute(stmt)
    indexed_paths = set(row[0] for row in result.fetchall())

    def build_tree(dir_path: str, relative_base: str = "") -> List[dict]:
        """Recursively build the file tree."""
        items = []

        try:
            entries = sorted(os.listdir(dir_path), key=lambda x: (not os.path.isdir(os.path.join(dir_path, x)), x.lower()))
        except PermissionError:
            return items

        for entry in entries:
            # Skip hidden files and common non-essential directories
            if entry.startswith('.') or entry in ['node_modules', 'vendor', '__pycache__', '.git']:
                continue

            full_path = os.path.join(dir_path, entry)
            relative_path = os.path.join(relative_base, entry) if relative_base else entry

            if os.path.isdir(full_path):
                children = build_tree(full_path, relative_path)
                # Only include directories that have children
                if children:
                    items.append({
                        "name": entry,
                        "path": relative_path,
                        "type": "directory",
                        "children": children,
                        "indexed": False,
                    })
            else:
                # Include PHP, Blade, JS, CSS, JSON, and config files
                ext = entry.split('.')[-1].lower() if '.' in entry else ''
                if ext in ['php', 'blade', 'js', 'ts', 'vue', 'jsx', 'tsx', 'css', 'scss', 'json', 'yaml', 'yml', 'md', 'env', 'sql']:
                    items.append({
                        "name": entry,
                        "path": relative_path,
                        "type": "file",
                        "indexed": relative_path in indexed_paths,
                    })

        return items

    tree = build_tree(project.clone_path)
    logger.info(f"[API] Returning file tree with {len(tree)} root items")
    return tree


@router.get("/{project_id}/files/{file_path:path}", response_model=FileContentResponse)
async def get_file_content(
    project_id: str,
    file_path: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the content of a specific file.
    """
    logger.info(f"[API] GET /projects/{project_id}/files/{file_path} - user_id={current_user.id}")

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

    if not project.clone_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has not been cloned yet.",
        )

    import os

    full_path = os.path.join(project.clone_path, file_path)

    # Security check - ensure path is within clone_path
    real_clone_path = os.path.realpath(project.clone_path)
    real_file_path = os.path.realpath(full_path)
    if not real_file_path.startswith(real_clone_path):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    if not os.path.isfile(full_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found.",
        )

    # Check if indexed
    stmt = select(IndexedFile).where(
        IndexedFile.project_id == project_id,
        IndexedFile.file_path == file_path,
    )
    result = await db.execute(stmt)
    indexed_file = result.scalar_one_or_none()

    # Read file content
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Try reading as binary and decode
        with open(full_path, 'rb') as f:
            content = f.read().decode('utf-8', errors='replace')

    return FileContentResponse(
        path=file_path,
        content=content,
        indexed=indexed_file is not None,
    )
