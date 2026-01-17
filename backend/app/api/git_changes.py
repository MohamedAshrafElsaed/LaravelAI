"""
Git Changes API endpoints.

Provides endpoints for tracking, listing, and managing git changes per conversation.
Includes rollback functionality for reverting changes.
"""
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, decrypt_token
from app.models.models import (
    Project, User, Conversation, Message, GitChange, GitChangeStatus
)
from app.services.git_service import GitService, GitServiceError

logger = logging.getLogger(__name__)

router = APIRouter()


# ============== Request/Response Models ==============

class FileChangeDetail(BaseModel):
    """Details of a single file change."""
    file: str
    action: str  # create, modify, delete
    content: Optional[str] = None
    diff: Optional[str] = None
    original_content: Optional[str] = None


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
    force: bool = False  # Force rollback even if PR is open


class RollbackResponse(BaseModel):
    """Response after rollback."""
    success: bool
    message: str
    rollback_commit: Optional[str] = None
    previous_status: str


# ============== Helper Functions ==============

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
    # First verify project ownership
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


# ============== API Endpoints ==============

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
    """
    List all git changes for a project.

    Optionally filter by status or conversation.
    Returns changes sorted by created_at descending (newest first).
    """
    logger.info(f"[GIT CHANGES API] GET /projects/{project_id}/changes - user_id={current_user.id}")

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
    logger.info(f"[GIT CHANGES API] GET /projects/{project_id}/changes/{change_id}")

    change = await get_git_change(change_id, project_id, current_user, db)
    return change_to_response(change)


@router.post("/{project_id}/changes", response_model=GitChangeResponse)
async def create_change(
    project_id: str,
    request: GitChangeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new git change record.

    Used when AI generates code changes to track them before applying.
    """
    logger.info(f"[GIT CHANGES API] POST /projects/{project_id}/changes")

    project = await get_project_for_user(project_id, current_user, db)

    # Verify conversation belongs to project
    stmt = select(Conversation).where(
        Conversation.id == request.conversation_id,
        Conversation.project_id == project_id,
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or doesn't belong to this project",
        )

    # Create the git change record
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

    logger.info(f"[GIT CHANGES API] Created git change {change.id} for conversation {request.conversation_id}")

    return change_to_response(change)


@router.patch("/{project_id}/changes/{change_id}", response_model=GitChangeResponse)
async def update_change(
    project_id: str,
    change_id: str,
    request: GitChangeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a git change record.

    Used to update status as changes progress through the git flow.
    """
    logger.info(f"[GIT CHANGES API] PATCH /projects/{project_id}/changes/{change_id}")

    change = await get_git_change(change_id, project_id, current_user, db)

    # Update fields
    if request.status:
        old_status = change.status
        change.status = request.status

        # Update timestamps based on status change
        now = datetime.utcnow()
        if request.status == GitChangeStatus.APPLIED.value:
            change.applied_at = now
        elif request.status == GitChangeStatus.PUSHED.value:
            change.pushed_at = now
        elif request.status == GitChangeStatus.PR_CREATED.value:
            change.pr_created_at = now
        elif request.status in [GitChangeStatus.PR_MERGED.value, GitChangeStatus.MERGED.value]:
            change.merged_at = now

        logger.info(f"[GIT CHANGES API] Status changed: {old_status} -> {request.status}")

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
    """
    Rollback a git change.

    Reverts the changes by:
    - For applied changes: checkout base branch and delete feature branch
    - For pushed changes: reset to base branch (local only, remote branch remains)
    - For PR changes: can't rollback unless force=True (warns about open PR)
    """
    logger.info(f"[GIT CHANGES API] POST /projects/{project_id}/changes/{change_id}/rollback")

    change = await get_git_change(change_id, project_id, current_user, db)
    project = await get_project_for_user(project_id, current_user, db)

    if not project.clone_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has not been cloned yet",
        )

    # Check if rollback is allowed
    if change.status == GitChangeStatus.ROLLED_BACK.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Change has already been rolled back",
        )

    if change.status == GitChangeStatus.DISCARDED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Change was discarded and cannot be rolled back",
        )

    if change.status in [GitChangeStatus.PR_MERGED.value, GitChangeStatus.MERGED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot rollback merged changes. Please create a revert commit instead.",
        )

    if change.status == GitChangeStatus.PR_CREATED.value and not request.force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pull request is open. Use force=true to rollback anyway (PR will remain open on GitHub).",
        )

    previous_status = change.status
    rollback_commit = None

    try:
        git_service = GitService(decrypt_token(current_user.github_access_token))

        # Perform rollback based on status
        if change.status in [GitChangeStatus.APPLIED.value, GitChangeStatus.PUSHED.value, GitChangeStatus.PR_CREATED.value]:
            # Checkout base branch
            git_service.checkout_branch(project.clone_path, change.base_branch)

            # Try to delete the feature branch locally
            try:
                repo = git_service._get_repo(project.clone_path)
                if change.branch_name in [b.name for b in repo.branches]:
                    repo.delete_head(change.branch_name, force=True)
                    logger.info(f"[GIT CHANGES API] Deleted local branch: {change.branch_name}")
            except Exception as e:
                logger.warning(f"[GIT CHANGES API] Could not delete branch: {e}")

            # Get current commit as rollback reference
            repo = git_service._get_repo(project.clone_path)
            rollback_commit = repo.head.commit.hexsha

        elif change.status == GitChangeStatus.PENDING.value:
            # Just mark as discarded, no git operations needed
            change.status = GitChangeStatus.DISCARDED.value
            await db.commit()
            await db.refresh(change)

            return RollbackResponse(
                success=True,
                message="Pending changes discarded",
                previous_status=previous_status,
            )

        # Update the change record
        change.status = GitChangeStatus.ROLLED_BACK.value
        change.rolled_back_at = datetime.utcnow()
        change.rolled_back_from_status = previous_status
        change.rollback_commit = rollback_commit

        await db.commit()
        await db.refresh(change)

        logger.info(f"[GIT CHANGES API] Rolled back change {change_id} from status {previous_status}")

        return RollbackResponse(
            success=True,
            message=f"Successfully rolled back changes from {previous_status}",
            rollback_commit=rollback_commit,
            previous_status=previous_status,
        )

    except GitServiceError as e:
        logger.error(f"[GIT CHANGES API] Rollback failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback: {str(e)}",
        )


@router.delete("/{project_id}/changes/{change_id}")
async def delete_change(
    project_id: str,
    change_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a git change record.

    Only allows deletion of pending or discarded changes.
    """
    logger.info(f"[GIT CHANGES API] DELETE /projects/{project_id}/changes/{change_id}")

    change = await get_git_change(change_id, project_id, current_user, db)

    if change.status not in [GitChangeStatus.PENDING.value, GitChangeStatus.DISCARDED.value, GitChangeStatus.ROLLED_BACK.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete pending, discarded, or rolled back changes",
        )

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
    """
    List all git changes for a specific conversation.

    Returns changes sorted by created_at ascending (chronological order).
    """
    logger.info(f"[GIT CHANGES API] GET /projects/{project_id}/conversations/{conversation_id}/changes")

    await get_project_for_user(project_id, current_user, db)

    # Verify conversation exists
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.project_id == project_id,
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Get changes for this conversation
    stmt = select(GitChange).where(
        GitChange.conversation_id == conversation_id,
        GitChange.project_id == project_id,
    ).order_by(GitChange.created_at)

    result = await db.execute(stmt)
    changes = result.scalars().all()

    return [change_to_response(c) for c in changes]


@router.post("/{project_id}/changes/{change_id}/apply", response_model=GitChangeResponse)
async def apply_change(
    project_id: str,
    change_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Apply a pending git change to the repository.

    Creates a new branch, applies file changes, and commits them.
    """
    logger.info(f"[GIT CHANGES API] POST /projects/{project_id}/changes/{change_id}/apply")

    change = await get_git_change(change_id, project_id, current_user, db)
    project = await get_project_for_user(project_id, current_user, db)

    if not project.clone_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has not been cloned yet",
        )

    if change.status != GitChangeStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only apply pending changes. Current status: {change.status}",
        )

    if not change.files_changed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file changes to apply",
        )

    try:
        git_service = GitService(decrypt_token(current_user.github_access_token))

        # Create the branch
        git_service.create_branch(
            clone_path=project.clone_path,
            branch_name=change.branch_name,
            from_branch=change.base_branch,
        )

        # Apply changes
        changes_to_apply = [
            {
                "file": f["file"],
                "action": f["action"],
                "content": f.get("content", ""),
            }
            for f in change.files_changed
        ]

        commit_message = change.title or f"AI changes: {len(changes_to_apply)} file(s) modified"
        commit_hash = git_service.apply_changes(
            clone_path=project.clone_path,
            changes=changes_to_apply,
            commit_message=commit_message,
            author_name=current_user.username,
            author_email=current_user.email or f"{current_user.username}@users.noreply.github.com",
        )

        # Update change record
        change.status = GitChangeStatus.APPLIED.value
        change.commit_hash = commit_hash
        change.applied_at = datetime.utcnow()

        await db.commit()
        await db.refresh(change)

        logger.info(f"[GIT CHANGES API] Applied change {change_id}, commit={commit_hash[:8]}")

        return change_to_response(change)

    except GitServiceError as e:
        logger.error(f"[GIT CHANGES API] Failed to apply change: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{project_id}/changes/{change_id}/push", response_model=GitChangeResponse)
async def push_change(
    project_id: str,
    change_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Push an applied change to the remote repository.
    """
    logger.info(f"[GIT CHANGES API] POST /projects/{project_id}/changes/{change_id}/push")

    change = await get_git_change(change_id, project_id, current_user, db)
    project = await get_project_for_user(project_id, current_user, db)

    if not project.clone_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has not been cloned yet",
        )

    if change.status != GitChangeStatus.APPLIED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only push applied changes. Current status: {change.status}",
        )

    try:
        git_service = GitService(decrypt_token(current_user.github_access_token))

        # Checkout the branch
        git_service.checkout_branch(project.clone_path, change.branch_name)

        # Push to remote
        git_service.push_branch(
            clone_path=project.clone_path,
            branch_name=change.branch_name,
        )

        # Update change record
        change.status = GitChangeStatus.PUSHED.value
        change.pushed_at = datetime.utcnow()

        await db.commit()
        await db.refresh(change)

        logger.info(f"[GIT CHANGES API] Pushed change {change_id} to remote")

        return change_to_response(change)

    except GitServiceError as e:
        logger.error(f"[GIT CHANGES API] Failed to push change: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{project_id}/changes/{change_id}/create-pr", response_model=GitChangeResponse)
async def create_pr_for_change(
    project_id: str,
    change_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a pull request for a pushed change.
    """
    logger.info(f"[GIT CHANGES API] POST /projects/{project_id}/changes/{change_id}/create-pr")

    change = await get_git_change(change_id, project_id, current_user, db)
    project = await get_project_for_user(project_id, current_user, db)

    if change.status not in [GitChangeStatus.PUSHED.value, GitChangeStatus.APPLIED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Change must be pushed first. Current status: {change.status}",
        )

    # If not pushed yet, push first
    if change.status == GitChangeStatus.APPLIED.value:
        try:
            git_service = GitService(decrypt_token(current_user.github_access_token))
            git_service.checkout_branch(project.clone_path, change.branch_name)
            git_service.push_branch(project.clone_path, change.branch_name)
            change.status = GitChangeStatus.PUSHED.value
            change.pushed_at = datetime.utcnow()
        except GitServiceError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to push branch: {str(e)}",
            )

    try:
        git_service = GitService(decrypt_token(current_user.github_access_token))

        # Get files changed for PR body
        files_changed = [f["file"] for f in (change.files_changed or [])]

        # Create PR
        pr_title = title or change.title or f"AI changes from {change.branch_name}"
        pr_description = description or change.description or ""

        pr_data = await git_service.create_pull_request(
            repo_full_name=project.repo_full_name,
            branch_name=change.branch_name,
            base_branch=change.base_branch,
            title=pr_title,
            description=pr_description,
            files_changed=files_changed,
            ai_summary=change.change_summary or f"Modified {len(files_changed)} file(s)",
        )

        # Update change record
        change.status = GitChangeStatus.PR_CREATED.value
        change.pr_number = pr_data["number"]
        change.pr_url = pr_data["url"]
        change.pr_state = pr_data["state"]
        change.pr_created_at = datetime.utcnow()
        change.title = pr_title
        change.description = pr_description

        await db.commit()
        await db.refresh(change)

        logger.info(f"[GIT CHANGES API] Created PR #{pr_data['number']} for change {change_id}")

        return change_to_response(change)

    except GitServiceError as e:
        logger.error(f"[GIT CHANGES API] Failed to create PR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
