"""
Git operations API endpoints.

Provides endpoints for:
- Branch management
- Applying changes and creating pull requests
- Git change tracking per conversation
- Rollback functionality
"""
import logging
from typing import List, Optional, Callable, Any
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, decrypt_token
from app.models.models import (
    Project, User, ProjectStatus, Conversation, GitChange, GitChangeStatus
)
from app.services.git_service import GitService, GitServiceError
from app.services.github_token_service import (
    ensure_valid_token,
    handle_auth_failure,
    TokenInvalidError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============== Request/Response Models ==============

class FileChange(BaseModel):
    """A single file change."""
    file: str
    action: str  # create, modify, delete
    content: Optional[str] = None


class FileChangeDetail(BaseModel):
    """Details of a single file change (for tracking)."""
    file: str
    action: str
    content: Optional[str] = None
    diff: Optional[str] = None
    original_content: Optional[str] = None


class ApplyChangesRequest(BaseModel):
    """Request to apply changes to a new branch."""
    changes: List[FileChange]
    branch_name: Optional[str] = None
    commit_message: str
    base_branch: Optional[str] = None


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
    base_branch: Optional[str] = None
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


# Git Change Tracking Models
class GitChangeCreate(BaseModel):
    """Request to create a git change record."""
    conversation_id: str
    message_id: Optional[str] = None
    branch_name: str
    base_branch: str = "main"
    title: Optional[str] = None
    description: Optional[str] = None
    files_changed: Optional[List[FileChangeDetail]] = None
    change_summary: Optional[str] = None


class GitChangeUpdate(BaseModel):
    """Request to update a git change status."""
    status: Optional[str] = None
    commit_hash: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    pr_state: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None


class GitChangeResponse(BaseModel):
    """Response for a git change."""
    id: str
    conversation_id: str
    project_id: str
    message_id: Optional[str]
    branch_name: str
    base_branch: str
    commit_hash: Optional[str]
    status: str
    pr_number: Optional[int]
    pr_url: Optional[str]
    pr_state: Optional[str]
    title: Optional[str]
    description: Optional[str]
    files_changed: Optional[List[dict]]
    change_summary: Optional[str]
    rollback_commit: Optional[str]
    rolled_back_at: Optional[str]
    rolled_back_from_status: Optional[str]
    created_at: str
    updated_at: str
    applied_at: Optional[str]
    pushed_at: Optional[str]
    pr_created_at: Optional[str]
    merged_at: Optional[str]

    class Config:
        from_attributes = True


class RollbackRequest(BaseModel):
    """Request to rollback a git change."""
    force: bool = False


class RollbackResponse(BaseModel):
    """Response after rollback."""
    success: bool
    message: str
    rollback_commit: Optional[str] = None
    previous_status: str


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


async def get_project_for_user(
    project_id: str,
    user: User,
    db: AsyncSession,
) -> Project:
    """Get project and verify ownership."""
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
    return project


async def get_git_change(
    change_id: str,
    project_id: str,
    user: User,
    db: AsyncSession,
) -> GitChange:
    """Get a git change and verify ownership."""
    await get_project_for_user(project_id, user, db)

    stmt = select(GitChange).where(
        GitChange.id == change_id,
        GitChange.project_id == project_id,
    )
    result = await db.execute(stmt)
    change = result.scalar_one_or_none()

    if not change:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Git change not found",
        )
    return change


def generate_branch_name(prefix: str = "ai-changes") -> str:
    """Generate a unique branch name."""
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    short_id = str(uuid4())[:6]
    return f"{prefix}/{timestamp}-{short_id}"


async def get_valid_git_service(user: User, db: AsyncSession) -> GitService:
    """Get a GitService with a validated token."""
    try:
        token = await ensure_valid_token(user, db)
        return GitService(token)
    except TokenInvalidError as e:
        logger.error(f"[GIT API] Token invalid for user {user.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"X-Token-Refresh-Required": "true"},
        )


async def execute_with_token_refresh(
    user: User,
    db: AsyncSession,
    operation: Callable[[GitService], Any],
    operation_name: str = "Git operation",
) -> Any:
    """Execute a git operation with automatic token refresh on auth failure."""
    try:
        git_service = await get_valid_git_service(user, db)
        return operation(git_service)
    except GitServiceError as e:
        error_str = str(e).lower()
        if "authentication failed" in error_str or "token" in error_str:
            logger.warning(f"[GIT API] Auth failure during {operation_name}, attempting token refresh")
            new_token = await handle_auth_failure(user, db)
            if new_token:
                logger.info(f"[GIT API] Token refreshed, retrying {operation_name}")
                try:
                    git_service = GitService(new_token)
                    return operation(git_service)
                except GitServiceError as retry_error:
                    logger.error(f"[GIT API] {operation_name} failed after token refresh: {retry_error}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=str(retry_error),
                    )
            else:
                logger.error(f"[GIT API] Token refresh failed, cannot recover")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="GitHub authentication failed. Please re-authenticate with GitHub.",
                    headers={"X-Token-Refresh-Required": "true"},
                )
        raise


async def execute_async_with_token_refresh(
    user: User,
    db: AsyncSession,
    operation: Callable[[GitService], Any],
    operation_name: str = "Git operation",
) -> Any:
    """Execute an async git operation with automatic token refresh."""
    try:
        git_service = await get_valid_git_service(user, db)
        return await operation(git_service)
    except GitServiceError as e:
        error_str = str(e).lower()
        if "authentication failed" in error_str or "token" in error_str:
            logger.warning(f"[GIT API] Auth failure during {operation_name}, attempting token refresh")
            new_token = await handle_auth_failure(user, db)
            if new_token:
                logger.info(f"[GIT API] Token refreshed, retrying {operation_name}")
                try:
                    git_service = GitService(new_token)
                    return await operation(git_service)
                except GitServiceError as retry_error:
                    logger.error(f"[GIT API] {operation_name} failed after token refresh: {retry_error}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=str(retry_error),
                    )
            else:
                logger.error(f"[GIT API] Token refresh failed, cannot recover")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="GitHub authentication failed. Please re-authenticate with GitHub.",
                    headers={"X-Token-Refresh-Required": "true"},
                )
        raise


def change_to_response(change: GitChange) -> GitChangeResponse:
    """Convert GitChange model to response."""
    return GitChangeResponse(
        id=change.id,
        conversation_id=change.conversation_id,
        project_id=change.project_id,
        message_id=change.message_id,
        branch_name=change.branch_name,
        base_branch=change.base_branch,
        commit_hash=change.commit_hash,
        status=change.status,
        pr_number=change.pr_number,
        pr_url=change.pr_url,
        pr_state=change.pr_state,
        title=change.title,
        description=change.description,
        files_changed=change.files_changed,
        change_summary=change.change_summary,
        rollback_commit=change.rollback_commit,
        rolled_back_at=change.rolled_back_at.isoformat() if change.rolled_back_at else None,
        rolled_back_from_status=change.rolled_back_from_status,
        created_at=change.created_at.isoformat(),
        updated_at=change.updated_at.isoformat(),
        applied_at=change.applied_at.isoformat() if change.applied_at else None,
        pushed_at=change.pushed_at.isoformat() if change.pushed_at else None,
        pr_created_at=change.pr_created_at.isoformat() if change.pr_created_at else None,
        merged_at=change.merged_at.isoformat() if change.merged_at else None,
    )


# ============== Branch Endpoints ==============

@router.get("/{project_id}/branches", response_model=List[BranchInfo])
async def list_branches(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all branches in the project repository."""
    logger.info(f"[GIT API] GET /{project_id}/branches")

    project = await get_project_with_clone(project_id, current_user, db)

    def do_list_branches(git_service: GitService) -> List[BranchInfo]:
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

    try:
        return await execute_with_token_refresh(
            user=current_user, db=db,
            operation=do_list_branches,
            operation_name="list branches",
        )
    except GitServiceError as e:
        logger.error(f"[GIT API] Failed to list branches: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{project_id}/apply", response_model=ApplyChangesResponse)
async def apply_changes(
    project_id: str,
    request: ApplyChangesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply changes to a new branch."""
    logger.info(f"[GIT API] POST /{project_id}/apply")

    project = await get_project_with_clone(project_id, current_user, db)
    branch_name = request.branch_name or generate_branch_name()
    base_branch = request.base_branch or project.default_branch or "main"

    def do_apply_changes(git_service: GitService) -> ApplyChangesResponse:
        git_service.create_branch(
            clone_path=project.clone_path,
            branch_name=branch_name,
            from_branch=base_branch,
        )
        changes = [{"file": c.file, "action": c.action, "content": c.content or ""} for c in request.changes]
        commit_hash = git_service.apply_changes(
            clone_path=project.clone_path,
            changes=changes,
            commit_message=request.commit_message,
            author_name=current_user.username,
            author_email=current_user.email or f"{current_user.username}@users.noreply.github.com",
        )
        return ApplyChangesResponse(
            branch_name=branch_name,
            commit_hash=commit_hash,
            files_changed=len(changes),
            message=f"Applied {len(changes)} changes to branch '{branch_name}'",
        )

    try:
        return await execute_with_token_refresh(
            user=current_user, db=db,
            operation=do_apply_changes,
            operation_name="apply changes",
        )
    except GitServiceError as e:
        logger.error(f"[GIT API] Failed to apply changes: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{project_id}/pr", response_model=PRResponse)
async def create_pull_request(
    project_id: str,
    request: CreatePRRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Push branch and create a pull request."""
    logger.info(f"[GIT API] POST /{project_id}/pr")

    project = await get_project_with_clone(project_id, current_user, db)
    base_branch = request.base_branch or project.default_branch or "main"

    async def do_push_and_create_pr(git_service: GitService) -> PRResponse:
        git_service.checkout_branch(project.clone_path, request.branch_name)
        git_service.push_branch(clone_path=project.clone_path, branch_name=request.branch_name)
        changed_files = git_service.get_changed_files(project.clone_path, base_branch)
        pr_data = await git_service.create_pull_request(
            repo_full_name=project.repo_full_name,
            branch_name=request.branch_name,
            base_branch=base_branch,
            title=request.title,
            description=request.description or "",
            files_changed=changed_files,
            ai_summary=request.ai_summary or "Changes applied by Laravel AI",
        )
        return PRResponse(
            number=pr_data["number"],
            url=pr_data["url"],
            title=pr_data["title"],
            state=pr_data["state"],
            created_at=pr_data["created_at"],
        )

    try:
        return await execute_async_with_token_refresh(
            user=current_user, db=db,
            operation=do_push_and_create_pr,
            operation_name="push and create PR",
        )
    except GitServiceError as e:
        logger.error(f"[GIT API] Failed to create PR: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{project_id}/sync", response_model=SyncResponse)
async def sync_with_remote(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pull latest changes from remote repository."""
    logger.info(f"[GIT API] POST /{project_id}/sync")

    project = await get_project_with_clone(project_id, current_user, db)
    default_branch = project.default_branch or "main"

    def do_sync(git_service: GitService) -> SyncResponse:
        try:
            git_service.checkout_branch(project.clone_path, default_branch)
        except GitServiceError:
            pass
        had_changes = git_service.pull_latest(project.clone_path)
        return SyncResponse(
            success=True,
            message="Pulled latest changes successfully" if had_changes else "Already up to date",
            had_changes=had_changes,
        )

    try:
        return await execute_with_token_refresh(
            user=current_user, db=db,
            operation=do_sync,
            operation_name="sync with remote",
        )
    except GitServiceError as e:
        logger.error(f"[GIT API] Sync failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{project_id}/reset")
async def reset_to_remote(
    project_id: str,
    branch: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset local repository to match remote."""
    logger.info(f"[GIT API] POST /{project_id}/reset")

    project = await get_project_with_clone(project_id, current_user, db)
    branch_name = branch or project.default_branch or "main"

    def do_reset(git_service: GitService) -> dict:
        git_service.reset_to_remote(project.clone_path, branch_name)
        return {"success": True, "message": f"Reset to origin/{branch_name} complete", "branch": branch_name}

    try:
        return await execute_with_token_refresh(
            user=current_user, db=db,
            operation=do_reset,
            operation_name="reset to remote",
        )
    except GitServiceError as e:
        logger.error(f"[GIT API] Reset failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{project_id}/diff")
async def get_diff(
    project_id: str,
    base_branch: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the diff between current branch and base branch."""
    logger.info(f"[GIT API] GET /{project_id}/diff")

    project = await get_project_with_clone(project_id, current_user, db)
    base = base_branch or project.default_branch or "main"

    def do_get_diff(git_service: GitService) -> dict:
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

    try:
        return await execute_with_token_refresh(
            user=current_user, db=db,
            operation=do_get_diff,
            operation_name="get diff",
        )
    except GitServiceError as e:
        logger.error(f"[GIT API] Failed to get diff: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ============== Git Change Tracking Endpoints ==============

@router.get("/{project_id}/changes", response_model=List[GitChangeResponse])
async def list_project_changes(
    project_id: str,
    status_filter: Optional[str] = None,
    conversation_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all git changes for a project."""
    logger.info(f"[GIT API] GET /{project_id}/changes")

    await get_project_for_user(project_id, current_user, db)

    stmt = select(GitChange).where(GitChange.project_id == project_id)
    if status_filter:
        stmt = stmt.where(GitChange.status == status_filter)
    if conversation_id:
        stmt = stmt.where(GitChange.conversation_id == conversation_id)
    stmt = stmt.order_by(desc(GitChange.created_at)).offset(offset).limit(limit)

    result = await db.execute(stmt)
    changes = result.scalars().all()
    return [change_to_response(c) for c in changes]


@router.get("/{project_id}/changes/{change_id}", response_model=GitChangeResponse)
async def get_change(
    project_id: str,
    change_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific git change by ID."""
    logger.info(f"[GIT API] GET /{project_id}/changes/{change_id}")
    change = await get_git_change(change_id, project_id, current_user, db)
    return change_to_response(change)


@router.post("/{project_id}/changes", response_model=GitChangeResponse)
async def create_change(
    project_id: str,
    request: GitChangeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new git change record."""
    logger.info(f"[GIT API] POST /{project_id}/changes")

    await get_project_for_user(project_id, current_user, db)

    stmt = select(Conversation).where(
        Conversation.id == request.conversation_id,
        Conversation.project_id == project_id,
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or doesn't belong to this project",
        )

    change = GitChange(
        conversation_id=request.conversation_id,
        project_id=project_id,
        message_id=request.message_id,
        branch_name=request.branch_name,
        base_branch=request.base_branch,
        title=request.title,
        description=request.description,
        files_changed=[f.model_dump() for f in request.files_changed] if request.files_changed else None,
        change_summary=request.change_summary,
        status=GitChangeStatus.PENDING.value,
    )

    db.add(change)
    await db.commit()
    await db.refresh(change)
    return change_to_response(change)


@router.patch("/{project_id}/changes/{change_id}", response_model=GitChangeResponse)
async def update_change(
    project_id: str,
    change_id: str,
    request: GitChangeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a git change record."""
    logger.info(f"[GIT API] PATCH /{project_id}/changes/{change_id}")

    change = await get_git_change(change_id, project_id, current_user, db)

    if request.status:
        change.status = request.status
        now = datetime.utcnow()
        if request.status == GitChangeStatus.APPLIED.value:
            change.applied_at = now
        elif request.status == GitChangeStatus.PUSHED.value:
            change.pushed_at = now
        elif request.status == GitChangeStatus.PR_CREATED.value:
            change.pr_created_at = now
        elif request.status in [GitChangeStatus.PR_MERGED.value, GitChangeStatus.MERGED.value]:
            change.merged_at = now

    if request.commit_hash:
        change.commit_hash = request.commit_hash
    if request.pr_number is not None:
        change.pr_number = request.pr_number
    if request.pr_url:
        change.pr_url = request.pr_url
    if request.pr_state:
        change.pr_state = request.pr_state
    if request.title:
        change.title = request.title
    if request.description:
        change.description = request.description

    await db.commit()
    await db.refresh(change)
    return change_to_response(change)


@router.post("/{project_id}/changes/{change_id}/rollback", response_model=RollbackResponse)
async def rollback_change(
    project_id: str,
    change_id: str,
    request: RollbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rollback a git change."""
    logger.info(f"[GIT API] POST /{project_id}/changes/{change_id}/rollback")

    change = await get_git_change(change_id, project_id, current_user, db)
    project = await get_project_for_user(project_id, current_user, db)

    if not project.clone_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project has not been cloned yet")

    if change.status == GitChangeStatus.ROLLED_BACK.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Change has already been rolled back")

    if change.status == GitChangeStatus.DISCARDED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Change was discarded and cannot be rolled back")

    if change.status in [GitChangeStatus.PR_MERGED.value, GitChangeStatus.MERGED.value]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot rollback merged changes. Please create a revert commit instead.")

    if change.status == GitChangeStatus.PR_CREATED.value and not request.force:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pull request is open. Use force=true to rollback anyway.")

    previous_status = change.status

    if change.status == GitChangeStatus.PENDING.value:
        change.status = GitChangeStatus.DISCARDED.value
        await db.commit()
        await db.refresh(change)
        return RollbackResponse(success=True, message="Pending changes discarded", previous_status=previous_status)

    def do_rollback(git_service: GitService) -> str:
        git_service.checkout_branch(project.clone_path, change.base_branch)
        try:
            repo = git_service._get_repo(project.clone_path)
            if change.branch_name in [b.name for b in repo.branches]:
                repo.delete_head(change.branch_name, force=True)
        except Exception as e:
            logger.warning(f"[GIT API] Could not delete branch: {e}")
        repo = git_service._get_repo(project.clone_path)
        return repo.head.commit.hexsha

    try:
        rollback_commit = await execute_with_token_refresh(
            user=current_user, db=db,
            operation=do_rollback,
            operation_name="rollback change",
        )

        change.status = GitChangeStatus.ROLLED_BACK.value
        change.rolled_back_at = datetime.utcnow()
        change.rolled_back_from_status = previous_status
        change.rollback_commit = rollback_commit

        await db.commit()
        await db.refresh(change)

        return RollbackResponse(
            success=True,
            message=f"Successfully rolled back changes from {previous_status}",
            rollback_commit=rollback_commit,
            previous_status=previous_status,
        )
    except GitServiceError as e:
        logger.error(f"[GIT API] Rollback failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to rollback: {str(e)}")


@router.delete("/{project_id}/changes/{change_id}")
async def delete_change(
    project_id: str,
    change_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a git change record."""
    logger.info(f"[GIT API] DELETE /{project_id}/changes/{change_id}")

    change = await get_git_change(change_id, project_id, current_user, db)

    if change.status not in [GitChangeStatus.PENDING.value, GitChangeStatus.DISCARDED.value, GitChangeStatus.ROLLED_BACK.value]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only delete pending, discarded, or rolled back changes")

    await db.delete(change)
    await db.commit()
    return {"success": True, "message": "Change record deleted"}


@router.get("/{project_id}/conversations/{conversation_id}/changes", response_model=List[GitChangeResponse])
async def list_conversation_changes(
    project_id: str,
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all git changes for a specific conversation."""
    logger.info(f"[GIT API] GET /{project_id}/conversations/{conversation_id}/changes")

    await get_project_for_user(project_id, current_user, db)

    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.project_id == project_id,
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    stmt = select(GitChange).where(
        GitChange.conversation_id == conversation_id,
        GitChange.project_id == project_id,
    ).order_by(GitChange.created_at)

    result = await db.execute(stmt)
    changes = result.scalars().all()
    return [change_to_response(c) for c in changes]


@router.post("/{project_id}/changes/{change_id}/apply", response_model=GitChangeResponse)
async def apply_tracked_change(
    project_id: str,
    change_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply a pending git change to the repository."""
    logger.info(f"[GIT API] POST /{project_id}/changes/{change_id}/apply")

    change = await get_git_change(change_id, project_id, current_user, db)
    project = await get_project_for_user(project_id, current_user, db)

    if not project.clone_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project has not been cloned yet")

    if change.status != GitChangeStatus.PENDING.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Can only apply pending changes. Current status: {change.status}")

    if not change.files_changed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file changes to apply")

    changes_to_apply = [{"file": f["file"], "action": f["action"], "content": f.get("content", "")} for f in change.files_changed]
    commit_message = change.title or f"AI changes: {len(changes_to_apply)} file(s) modified"

    def do_apply(git_service: GitService) -> str:
        git_service.create_branch(clone_path=project.clone_path, branch_name=change.branch_name, from_branch=change.base_branch)
        return git_service.apply_changes(
            clone_path=project.clone_path,
            changes=changes_to_apply,
            commit_message=commit_message,
            author_name=current_user.username,
            author_email=current_user.email or f"{current_user.username}@users.noreply.github.com",
        )

    try:
        commit_hash = await execute_with_token_refresh(user=current_user, db=db, operation=do_apply, operation_name="apply change")

        change.status = GitChangeStatus.APPLIED.value
        change.commit_hash = commit_hash
        change.applied_at = datetime.utcnow()

        await db.commit()
        await db.refresh(change)
        return change_to_response(change)
    except GitServiceError as e:
        logger.error(f"[GIT API] Failed to apply change: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{project_id}/changes/{change_id}/push", response_model=GitChangeResponse)
async def push_change(
    project_id: str,
    change_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Push an applied change to the remote repository."""
    logger.info(f"[GIT API] POST /{project_id}/changes/{change_id}/push")

    change = await get_git_change(change_id, project_id, current_user, db)
    project = await get_project_for_user(project_id, current_user, db)

    if not project.clone_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project has not been cloned yet")

    if change.status != GitChangeStatus.APPLIED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Can only push applied changes. Current status: {change.status}")

    def do_push(git_service: GitService) -> None:
        git_service.checkout_branch(project.clone_path, change.branch_name)
        git_service.push_branch(clone_path=project.clone_path, branch_name=change.branch_name)

    try:
        await execute_with_token_refresh(user=current_user, db=db, operation=do_push, operation_name="push change")

        change.status = GitChangeStatus.PUSHED.value
        change.pushed_at = datetime.utcnow()

        await db.commit()
        await db.refresh(change)
        return change_to_response(change)
    except GitServiceError as e:
        logger.error(f"[GIT API] Failed to push change: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{project_id}/changes/{change_id}/create-pr", response_model=GitChangeResponse)
async def create_pr_for_change(
    project_id: str,
    change_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a pull request for a pushed change."""
    logger.info(f"[GIT API] POST /{project_id}/changes/{change_id}/create-pr")

    change = await get_git_change(change_id, project_id, current_user, db)
    project = await get_project_for_user(project_id, current_user, db)

    if change.status not in [GitChangeStatus.PUSHED.value, GitChangeStatus.APPLIED.value]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Change must be pushed first. Current status: {change.status}")

    files_changed = [f["file"] for f in (change.files_changed or [])]
    pr_title = title or change.title or f"AI changes from {change.branch_name}"
    pr_description = description or change.description or ""

    if change.status == GitChangeStatus.APPLIED.value:
        def do_push(git_service: GitService) -> None:
            git_service.checkout_branch(project.clone_path, change.branch_name)
            git_service.push_branch(project.clone_path, change.branch_name)

        try:
            await execute_with_token_refresh(user=current_user, db=db, operation=do_push, operation_name="push branch before PR")
            change.status = GitChangeStatus.PUSHED.value
            change.pushed_at = datetime.utcnow()
        except GitServiceError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to push branch: {str(e)}")

    async def do_create_pr(git_service: GitService) -> dict:
        return await git_service.create_pull_request(
            repo_full_name=project.repo_full_name,
            branch_name=change.branch_name,
            base_branch=change.base_branch,
            title=pr_title,
            description=pr_description,
            files_changed=files_changed,
            ai_summary=change.change_summary or f"Modified {len(files_changed)} file(s)",
        )

    try:
        pr_data = await execute_async_with_token_refresh(user=current_user, db=db, operation=do_create_pr, operation_name="create PR")

        change.status = GitChangeStatus.PR_CREATED.value
        change.pr_number = pr_data["number"]
        change.pr_url = pr_data["url"]
        change.pr_state = pr_data["state"]
        change.pr_created_at = datetime.utcnow()
        change.title = pr_title
        change.description = pr_description

        await db.commit()
        await db.refresh(change)
        return change_to_response(change)
    except GitServiceError as e:
        logger.error(f"[GIT API] Failed to create PR: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))