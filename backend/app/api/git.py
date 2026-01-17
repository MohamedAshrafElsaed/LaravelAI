"""
Git operations API endpoints.

Provides endpoints for branch management, applying changes, and creating pull requests.
"""
import logging
from typing import List, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Project, User, ProjectStatus
from app.services.git_service import GitService, GitServiceError

logger = logging.getLogger(__name__)

router = APIRouter()


# ============== Request/Response Models ==============

class FileChange(BaseModel):
    """A single file change."""
    file: str
    action: str  # create, modify, delete
    content: Optional[str] = None


class ApplyChangesRequest(BaseModel):
    """Request to apply changes to a new branch."""
    changes: List[FileChange]
    branch_name: Optional[str] = None  # Auto-generated if not provided
    commit_message: str
    base_branch: Optional[str] = None  # Defaults to main/master


class ApplyChangesResponse(BaseModel):
    """Response after applying changes."""
    branch_name: str
    commit_hash: str
    files_changed: int
    message: str


class CreatePRRequest(BaseModel):
    """Request to create a pull request."""
    branch_name: str
    title: str
    description: Optional[str] = ""
    base_branch: Optional[str] = None  # Defaults to main/master
    ai_summary: Optional[str] = ""


class PRResponse(BaseModel):
    """Pull request creation response."""
    number: int
    url: str
    title: str
    state: str
    created_at: str


class BranchInfo(BaseModel):
    """Branch information."""
    name: str
    is_current: bool
    is_remote: bool = False
    commit: str
    message: str
    author: str
    date: str


class SyncResponse(BaseModel):
    """Response after syncing with remote."""
    success: bool
    message: str
    had_changes: bool


# ============== Helper Functions ==============

async def get_project_with_clone(
    project_id: str,
    user: User,
    db: AsyncSession,
) -> Project:
    """Get project and verify it has a clone path."""
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not project.clone_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has not been cloned yet",
        )

    return project


def generate_branch_name(prefix: str = "ai-changes") -> str:
    """Generate a unique branch name."""
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    short_id = str(uuid4())[:6]
    return f"{prefix}/{timestamp}-{short_id}"


# ============== API Endpoints ==============

@router.get("/{project_id}/branches", response_model=List[BranchInfo])
async def list_branches(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all branches in the project repository.

    Returns local and remote branches with their latest commit info.
    """
    logger.info(f"[GIT API] GET /projects/{project_id}/branches - user_id={current_user.id}")

    project = await get_project_with_clone(project_id, current_user, db)

    try:
        git_service = GitService(current_user.github_access_token)
        branches = git_service.list_branches(project.clone_path)

        return [
            BranchInfo(
                name=b["name"],
                is_current=b.get("is_current", False),
                is_remote=b.get("is_remote", False),
                commit=b["commit"],
                message=b["message"],
                author=b["author"],
                date=b["date"],
            )
            for b in branches
        ]

    except GitServiceError as e:
        logger.error(f"[GIT API] Failed to list branches: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{project_id}/apply", response_model=ApplyChangesResponse)
async def apply_changes(
    project_id: str,
    request: ApplyChangesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Apply changes to a new branch.

    Creates a new branch, applies file changes, and commits them.
    The branch is NOT pushed automatically - use /pr to push and create PR.
    """
    logger.info(f"[GIT API] POST /projects/{project_id}/apply - user_id={current_user.id}")

    project = await get_project_with_clone(project_id, current_user, db)

    try:
        git_service = GitService(current_user.github_access_token)

        # Generate branch name if not provided
        branch_name = request.branch_name or generate_branch_name()

        # Get base branch (default to main/master)
        base_branch = request.base_branch or project.default_branch or "main"

        logger.info(f"[GIT API] Creating branch '{branch_name}' from '{base_branch}'")

        # Create the new branch
        git_service.create_branch(
            clone_path=project.clone_path,
            branch_name=branch_name,
            from_branch=base_branch,
        )

        # Apply changes
        changes = [
            {
                "file": c.file,
                "action": c.action,
                "content": c.content or "",
            }
            for c in request.changes
        ]

        commit_hash = git_service.apply_changes(
            clone_path=project.clone_path,
            changes=changes,
            commit_message=request.commit_message,
            author_name=current_user.username,
            author_email=current_user.email or f"{current_user.username}@users.noreply.github.com",
        )

        logger.info(f"[GIT API] Applied {len(changes)} changes, commit={commit_hash[:8]}")

        return ApplyChangesResponse(
            branch_name=branch_name,
            commit_hash=commit_hash,
            files_changed=len(changes),
            message=f"Applied {len(changes)} changes to branch '{branch_name}'",
        )

    except GitServiceError as e:
        logger.error(f"[GIT API] Failed to apply changes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{project_id}/pr", response_model=PRResponse)
async def create_pull_request(
    project_id: str,
    request: CreatePRRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Push branch and create a pull request.

    Pushes the specified branch to GitHub and creates a PR to merge into base branch.
    """
    logger.info(f"[GIT API] POST /projects/{project_id}/pr - user_id={current_user.id}")

    project = await get_project_with_clone(project_id, current_user, db)

    try:
        git_service = GitService(current_user.github_access_token)

        # Get base branch
        base_branch = request.base_branch or project.default_branch or "main"

        # Checkout the branch to push
        git_service.checkout_branch(project.clone_path, request.branch_name)

        # Push the branch to remote
        logger.info(f"[GIT API] Pushing branch '{request.branch_name}'")
        git_service.push_branch(
            clone_path=project.clone_path,
            branch_name=request.branch_name,
        )

        # Get list of changed files
        diff = git_service.get_diff(project.clone_path, base_branch)
        changed_files = git_service.get_changed_files(project.clone_path, base_branch)

        # Create the PR
        logger.info(f"[GIT API] Creating PR: {request.branch_name} -> {base_branch}")
        pr_data = await git_service.create_pull_request(
            repo_full_name=project.repo_full_name,
            branch_name=request.branch_name,
            base_branch=base_branch,
            title=request.title,
            description=request.description or "",
            files_changed=changed_files,
            ai_summary=request.ai_summary or "Changes applied by Laravel AI",
        )

        logger.info(f"[GIT API] PR created: #{pr_data['number']} - {pr_data['url']}")

        return PRResponse(
            number=pr_data["number"],
            url=pr_data["url"],
            title=pr_data["title"],
            state=pr_data["state"],
            created_at=pr_data["created_at"],
        )

    except GitServiceError as e:
        logger.error(f"[GIT API] Failed to create PR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{project_id}/sync", response_model=SyncResponse)
async def sync_with_remote(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Pull latest changes from remote repository.

    Fetches and merges changes from the remote's default branch.
    """
    logger.info(f"[GIT API] POST /projects/{project_id}/sync - user_id={current_user.id}")

    project = await get_project_with_clone(project_id, current_user, db)

    try:
        git_service = GitService(current_user.github_access_token)

        # First checkout the default branch
        default_branch = project.default_branch or "main"
        try:
            git_service.checkout_branch(project.clone_path, default_branch)
        except GitServiceError:
            # Might be on detached HEAD, try reset
            pass

        # Pull latest changes
        had_changes = git_service.pull_latest(project.clone_path)

        message = "Pulled latest changes successfully" if had_changes else "Already up to date"
        logger.info(f"[GIT API] Sync complete: {message}")

        return SyncResponse(
            success=True,
            message=message,
            had_changes=had_changes,
        )

    except GitServiceError as e:
        logger.error(f"[GIT API] Sync failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{project_id}/reset")
async def reset_to_remote(
    project_id: str,
    branch: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reset local repository to match remote.

    Discards all local changes and resets to the remote branch state.
    Use with caution - this will lose uncommitted work.
    """
    logger.info(f"[GIT API] POST /projects/{project_id}/reset - user_id={current_user.id}")

    project = await get_project_with_clone(project_id, current_user, db)

    try:
        git_service = GitService(current_user.github_access_token)

        branch_name = branch or project.default_branch or "main"
        git_service.reset_to_remote(project.clone_path, branch_name)

        logger.info(f"[GIT API] Reset to remote/{branch_name} complete")

        return {
            "success": True,
            "message": f"Reset to origin/{branch_name} complete",
            "branch": branch_name,
        }

    except GitServiceError as e:
        logger.error(f"[GIT API] Reset failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{project_id}/diff")
async def get_diff(
    project_id: str,
    base_branch: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the diff between current branch and base branch.

    Returns unified diff format showing all changes.
    """
    logger.info(f"[GIT API] GET /projects/{project_id}/diff - user_id={current_user.id}")

    project = await get_project_with_clone(project_id, current_user, db)

    try:
        git_service = GitService(current_user.github_access_token)

        base = base_branch or project.default_branch or "main"
        current_branch = git_service.get_current_branch(project.clone_path)
        diff = git_service.get_diff(project.clone_path, base)
        changed_files = git_service.get_changed_files(project.clone_path, base)

        return {
            "current_branch": current_branch,
            "base_branch": base,
            "diff": diff,
            "files_changed": changed_files,
            "file_count": len(changed_files),
        }

    except GitServiceError as e:
        logger.error(f"[GIT API] Failed to get diff: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
