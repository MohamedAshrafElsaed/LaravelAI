"""
GitHub data API endpoints.

Provides endpoints for:
- Issues
- Actions (workflow runs)
- GitHub Projects
- Wiki pages
- Repository insights
"""
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, decrypt_token
from app.models.models import User, Project
from app.models.github_models import (
    GitHubIssue, GitHubAction, GitHubProject, GitHubWikiPage, GitHubInsights
)
from app.services.team_service import TeamService
from app.services.github_sync_service import GitHubSyncService, GitHubSyncError

logger = logging.getLogger(__name__)

router = APIRouter()


# ============== Response Models ==============

class GitHubIssueResponse(BaseModel):
    """GitHub issue response."""
    id: str
    github_id: int
    number: int
    title: str
    body: Optional[str]
    state: str
    author_username: Optional[str]
    author_avatar_url: Optional[str]
    labels: Optional[list]
    assignees: Optional[list]
    comments_count: int
    html_url: str
    github_created_at: datetime
    github_updated_at: datetime
    github_closed_at: Optional[datetime]
    synced_at: datetime

    class Config:
        from_attributes = True


class GitHubActionResponse(BaseModel):
    """GitHub action response."""
    id: str
    github_id: int
    workflow_id: int
    workflow_name: str
    run_number: int
    status: str
    conclusion: Optional[str]
    head_branch: Optional[str]
    head_sha: Optional[str]
    actor_username: Optional[str]
    actor_avatar_url: Optional[str]
    html_url: str
    github_created_at: datetime
    github_updated_at: datetime
    run_started_at: Optional[datetime]
    synced_at: datetime

    class Config:
        from_attributes = True


class GitHubProjectResponse(BaseModel):
    """GitHub project response."""
    id: str
    github_id: int
    number: int
    title: str
    body: Optional[str]
    state: str
    html_url: str
    items_count: int
    github_created_at: datetime
    github_updated_at: datetime
    synced_at: datetime

    class Config:
        from_attributes = True


class GitHubInsightsResponse(BaseModel):
    """GitHub insights response."""
    id: str
    project_id: str
    views_count: int
    views_uniques: int
    clones_count: int
    clones_uniques: int
    stars_count: int
    forks_count: int
    watchers_count: int
    open_issues_count: int
    code_frequency: Optional[list]
    commit_activity: Optional[list]
    contributors: Optional[list]
    languages: Optional[dict]
    synced_at: datetime

    class Config:
        from_attributes = True


class SyncResponse(BaseModel):
    """Sync operation response."""
    success: bool
    synced_count: int
    message: str


class FullSyncResponse(BaseModel):
    """Full sync response."""
    success: bool
    collaborators_count: int
    issues_count: int
    actions_count: int
    projects_count: int
    has_insights: bool
    errors: List[str]


# ============== Helper Functions ==============

async def get_project_with_access(
        project_id: str,
        user: User,
        db: AsyncSession,
) -> Project:
    """Get project and verify user has access."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    service = TeamService(db)
    has_access = await service.check_project_access(project_id, str(user.id))

    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")

    return project


def get_github_token(user: User) -> str:
    """Get decrypted GitHub token."""
    if not user.github_token_encrypted:
        raise HTTPException(
            status_code=400,
            detail="GitHub token not available. Please re-authenticate."
        )
    return decrypt_token(user.github_token_encrypted)


# ============== Issues Endpoints ==============

@router.get("/{project_id}/issues", response_model=List[GitHubIssueResponse])
async def list_issues(
        project_id: str,
        state: Optional[str] = Query(None, description="Filter by state: open, closed, all"),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """List cached GitHub issues for a project."""
    logger.info(f"[GITHUB_DATA] GET /{project_id}/issues")

    await get_project_with_access(project_id, current_user, db)

    stmt = select(GitHubIssue).where(GitHubIssue.project_id == project_id)

    if state and state != "all":
        stmt = stmt.where(GitHubIssue.state == state)

    stmt = stmt.order_by(desc(GitHubIssue.github_updated_at)).offset(offset).limit(limit)

    result = await db.execute(stmt)
    issues = result.scalars().all()

    return issues


@router.post("/{project_id}/sync/issues", response_model=SyncResponse)
async def sync_issues(
        project_id: str,
        state: str = Query("all", description="State to sync: open, closed, all"),
        limit: int = Query(100, ge=1, le=500),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Sync issues from GitHub."""
    logger.info(f"[GITHUB_DATA] POST /{project_id}/sync/issues")

    project = await get_project_with_access(project_id, current_user, db)
    github_token = get_github_token(current_user)

    sync_service = GitHubSyncService(db, github_token)

    try:
        issues = await sync_service.sync_issues(project, state, limit)
        return SyncResponse(
            success=True,
            synced_count=len(issues),
            message=f"Synced {len(issues)} issues from GitHub"
        )
    except GitHubSyncError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Actions Endpoints ==============

@router.get("/{project_id}/actions", response_model=List[GitHubActionResponse])
async def list_actions(
        project_id: str,
        status: Optional[str] = Query(None, description="Filter by status"),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """List cached GitHub Actions workflow runs."""
    logger.info(f"[GITHUB_DATA] GET /{project_id}/actions")

    await get_project_with_access(project_id, current_user, db)

    stmt = select(GitHubAction).where(GitHubAction.project_id == project_id)

    if status:
        stmt = stmt.where(GitHubAction.status == status)

    stmt = stmt.order_by(desc(GitHubAction.github_created_at)).offset(offset).limit(limit)

    result = await db.execute(stmt)
    actions = result.scalars().all()

    return actions


@router.post("/{project_id}/sync/actions", response_model=SyncResponse)
async def sync_actions(
        project_id: str,
        limit: int = Query(50, ge=1, le=200),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Sync GitHub Actions workflow runs."""
    logger.info(f"[GITHUB_DATA] POST /{project_id}/sync/actions")

    project = await get_project_with_access(project_id, current_user, db)
    github_token = get_github_token(current_user)

    sync_service = GitHubSyncService(db, github_token)

    try:
        actions = await sync_service.sync_actions(project, limit)
        return SyncResponse(
            success=True,
            synced_count=len(actions),
            message=f"Synced {len(actions)} action runs from GitHub"
        )
    except GitHubSyncError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== GitHub Projects Endpoints ==============

@router.get("/{project_id}/github-projects", response_model=List[GitHubProjectResponse])
async def list_github_projects(
        project_id: str,
        state: Optional[str] = Query(None, description="Filter by state: open, closed"),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """List cached GitHub Projects."""
    logger.info(f"[GITHUB_DATA] GET /{project_id}/github-projects")

    await get_project_with_access(project_id, current_user, db)

    stmt = select(GitHubProject).where(GitHubProject.project_id == project_id)

    if state:
        stmt = stmt.where(GitHubProject.state == state)

    stmt = stmt.order_by(desc(GitHubProject.github_updated_at))

    result = await db.execute(stmt)
    projects = result.scalars().all()

    return projects


@router.post("/{project_id}/sync/github-projects", response_model=SyncResponse)
async def sync_github_projects(
        project_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Sync GitHub Projects (classic)."""
    logger.info(f"[GITHUB_DATA] POST /{project_id}/sync/github-projects")

    project = await get_project_with_access(project_id, current_user, db)
    github_token = get_github_token(current_user)

    sync_service = GitHubSyncService(db, github_token)

    try:
        gh_projects = await sync_service.sync_projects(project)
        return SyncResponse(
            success=True,
            synced_count=len(gh_projects),
            message=f"Synced {len(gh_projects)} GitHub projects"
        )
    except GitHubSyncError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Insights Endpoints ==============

@router.get("/{project_id}/insights", response_model=GitHubInsightsResponse)
async def get_insights(
        project_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Get cached repository insights."""
    logger.info(f"[GITHUB_DATA] GET /{project_id}/insights")

    await get_project_with_access(project_id, current_user, db)

    stmt = select(GitHubInsights).where(GitHubInsights.project_id == project_id)
    result = await db.execute(stmt)
    insights = result.scalar_one_or_none()

    if not insights:
        raise HTTPException(
            status_code=404,
            detail="Insights not synced yet. Use POST /sync/insights to fetch."
        )

    return insights


@router.post("/{project_id}/sync/insights", response_model=GitHubInsightsResponse)
async def sync_insights(
        project_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Sync repository insights from GitHub."""
    logger.info(f"[GITHUB_DATA] POST /{project_id}/sync/insights")

    project = await get_project_with_access(project_id, current_user, db)
    github_token = get_github_token(current_user)

    sync_service = GitHubSyncService(db, github_token)

    try:
        insights = await sync_service.sync_insights(project)
        return insights
    except GitHubSyncError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Full Sync Endpoint ==============

@router.post("/{project_id}/sync/all", response_model=FullSyncResponse)
async def full_sync(
        project_id: str,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Perform full sync of all GitHub data."""
    logger.info(f"[GITHUB_DATA] POST /{project_id}/sync/all")

    project = await get_project_with_access(project_id, current_user, db)
    github_token = get_github_token(current_user)

    team_service = TeamService(db)

    if project.team_id:
        team = await team_service.get_team(project.team_id)
    else:
        team = await team_service.get_user_personal_team(str(current_user.id))

    if not team:
        raise HTTPException(status_code=400, detail="No team found for project")

    sync_service = GitHubSyncService(db, github_token)

    try:
        results = await sync_service.full_sync(project, team)

        return FullSyncResponse(
            success=len(results["errors"]) == 0,
            collaborators_count=len(results["collaborators"]),
            issues_count=len(results["issues"]),
            actions_count=len(results["actions"]),
            projects_count=len(results["projects"]),
            has_insights=results["insights"] is not None,
            errors=results["errors"],
        )

    except Exception as e:
        logger.error(f"[GITHUB_DATA] Full sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Wiki Endpoints ==============

@router.get("/{project_id}/wiki")
async def list_wiki_pages(
        project_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """List cached wiki pages."""
    logger.info(f"[GITHUB_DATA] GET /{project_id}/wiki")

    await get_project_with_access(project_id, current_user, db)

    stmt = select(GitHubWikiPage).where(GitHubWikiPage.project_id == project_id)
    result = await db.execute(stmt)
    pages = result.scalars().all()

    project = await get_project_with_access(project_id, current_user, db)

    return {
        "pages": pages,
        "wiki_url": f"https://github.com/{project.repo_full_name}/wiki",
        "note": "Wiki content requires manual sync or clone of wiki repository"
    }