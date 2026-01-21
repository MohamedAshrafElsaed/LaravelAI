# ============================================================================
# FILE: backend/app/api/teams.py
# ============================================================================
"""
Team management API endpoints.

Provides endpoints for:
- Team CRUD operations
- Team member management
- Team project management
- Access control
"""
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, decrypt_token
from app.models.models import User, Project
from app.models.team_models import Team, TeamMember, TeamRole, TeamMemberStatus
from app.services.team_service import TeamService, TeamServiceError
from app.services.github_sync_service import GitHubSyncService

logger = logging.getLogger(__name__)

router = APIRouter()


# ============== Request/Response Models ==============

class TeamCreateRequest(BaseModel):
    """Request to create a team."""
    name: str
    description: Optional[str] = None
    github_org_name: Optional[str] = None


class TeamUpdateRequest(BaseModel):
    """Request to update a team."""
    name: Optional[str] = None
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    settings: Optional[dict] = None


class TeamResponse(BaseModel):
    """Team response model."""
    id: str
    name: str
    slug: str
    description: Optional[str]
    avatar_url: Optional[str]
    owner_id: str
    is_personal: bool
    github_org_name: Optional[str]
    member_count: int = 0
    project_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TeamMemberResponse(BaseModel):
    """Team member response model."""
    id: str
    team_id: str
    user_id: Optional[str]
    github_id: Optional[int]
    github_username: Optional[str]
    github_avatar_url: Optional[str]
    invited_email: Optional[str]
    role: str
    status: str
    joined_at: Optional[datetime]
    invited_at: datetime
    last_active_at: Optional[datetime]

    class Config:
        from_attributes = True


class InviteMemberRequest(BaseModel):
    """Request to invite a member."""
    github_username: Optional[str] = None
    email: Optional[str] = None
    role: str = "member"


class UpdateMemberRoleRequest(BaseModel):
    """Request to update member role."""
    role: str


class AssignProjectRequest(BaseModel):
    """Request to assign project to team."""
    project_id: str


# ============== Helper Functions ==============

async def get_team_with_access(
        team_id: str,
        user: User,
        db: AsyncSession,
        required_role: Optional[TeamRole] = None,
) -> Team:
    """Get team and verify user has access."""
    service = TeamService(db)
    team = await service.get_team(team_id)

    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    has_access = await service.check_team_access(
        team_id, str(user.id), required_role
    )

    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")

    return team


# ============== Team Endpoints ==============

@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
        request: TeamCreateRequest,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    Create a new team.

    The current user becomes the team owner.
    """
    logger.info(f"[TEAMS API] POST /teams - user={current_user.username}")

    service = TeamService(db)

    try:
        team = await service.create_team(
            owner=current_user,
            name=request.name,
            description=request.description,
            github_org_name=request.github_org_name,
        )

        # Get member count
        members = await service.get_team_members(team.id)
        projects = await service.get_team_projects(team.id)

        return TeamResponse(
            id=team.id,
            name=team.name,
            slug=team.slug,
            description=team.description,
            avatar_url=team.avatar_url,
            owner_id=team.owner_id,
            is_personal=team.is_personal,
            github_org_name=team.github_org_name,
            member_count=len(members),
            project_count=len(projects),
            created_at=team.created_at,
            updated_at=team.updated_at,
        )

    except TeamServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[TeamResponse])
async def list_teams(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    List all teams the current user belongs to.

    Includes personal team and any team memberships.
    """
    logger.info(f"[TEAMS API] GET /teams - user={current_user.username}")

    service = TeamService(db)
    teams = await service.get_user_teams(str(current_user.id))

    response = []
    for team in teams:
        members = await service.get_team_members(team.id)
        projects = await service.get_team_projects(team.id)

        response.append(TeamResponse(
            id=team.id,
            name=team.name,
            slug=team.slug,
            description=team.description,
            avatar_url=team.avatar_url,
            owner_id=team.owner_id,
            is_personal=team.is_personal,
            github_org_name=team.github_org_name,
            member_count=len(members),
            project_count=len(projects),
            created_at=team.created_at,
            updated_at=team.updated_at,
        ))

    return response


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
        team_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Get a specific team."""
    logger.info(f"[TEAMS API] GET /teams/{team_id}")

    team = await get_team_with_access(team_id, current_user, db)
    service = TeamService(db)

    members = await service.get_team_members(team.id)
    projects = await service.get_team_projects(team.id)

    return TeamResponse(
        id=team.id,
        name=team.name,
        slug=team.slug,
        description=team.description,
        avatar_url=team.avatar_url,
        owner_id=team.owner_id,
        is_personal=team.is_personal,
        github_org_name=team.github_org_name,
        member_count=len(members),
        project_count=len(projects),
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


@router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(
        team_id: str,
        request: TeamUpdateRequest,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Update a team (requires admin access)."""
    logger.info(f"[TEAMS API] PATCH /teams/{team_id}")

    team = await get_team_with_access(team_id, current_user, db, TeamRole.ADMIN)

    if request.name:
        team.name = request.name
    if request.description is not None:
        team.description = request.description
    if request.avatar_url is not None:
        team.avatar_url = request.avatar_url
    if request.settings is not None:
        team.settings = {**(team.settings or {}), **request.settings}

    team.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(team)

    service = TeamService(db)
    members = await service.get_team_members(team.id)
    projects = await service.get_team_projects(team.id)

    return TeamResponse(
        id=team.id,
        name=team.name,
        slug=team.slug,
        description=team.description,
        avatar_url=team.avatar_url,
        owner_id=team.owner_id,
        is_personal=team.is_personal,
        github_org_name=team.github_org_name,
        member_count=len(members),
        project_count=len(projects),
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
        team_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Delete a team (owner only, cannot delete personal team)."""
    logger.info(f"[TEAMS API] DELETE /teams/{team_id}")

    team = await get_team_with_access(team_id, current_user, db, TeamRole.OWNER)

    if team.is_personal:
        raise HTTPException(status_code=400, detail="Cannot delete personal team")

    await db.delete(team)
    await db.commit()


# ============== Team Member Endpoints ==============

@router.get("/{team_id}/members", response_model=List[TeamMemberResponse])
async def list_team_members(
        team_id: str,
        status_filter: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """List all members of a team."""
    logger.info(f"[TEAMS API] GET /teams/{team_id}/members")

    await get_team_with_access(team_id, current_user, db)

    service = TeamService(db)
    status = TeamMemberStatus(status_filter) if status_filter else None
    members = await service.get_team_members(team_id, status)

    return [TeamMemberResponse(
        id=m.id,
        team_id=m.team_id,
        user_id=m.user_id,
        github_id=m.github_id,
        github_username=m.github_username,
        github_avatar_url=m.github_avatar_url,
        invited_email=m.invited_email,
        role=m.role,
        status=m.status,
        joined_at=m.joined_at,
        invited_at=m.invited_at,
        last_active_at=m.last_active_at,
    ) for m in members]


@router.post("/{team_id}/members", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
        team_id: str,
        request: InviteMemberRequest,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    Invite a new member to the team.

    Can invite by GitHub username or email.
    Requires admin access.
    """
    logger.info(f"[TEAMS API] POST /teams/{team_id}/members")

    await get_team_with_access(team_id, current_user, db, TeamRole.ADMIN)

    if not request.github_username and not request.email:
        raise HTTPException(
            status_code=400,
            detail="Must provide github_username or email"
        )

    service = TeamService(db)

    try:
        role = TeamRole(request.role)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")

    try:
        member = await service.add_member(
            team_id=team_id,
            invited_by=current_user,
            github_username=request.github_username,
            email=request.email,
            role=role,
        )

        return TeamMemberResponse(
            id=member.id,
            team_id=member.team_id,
            user_id=member.user_id,
            github_id=member.github_id,
            github_username=member.github_username,
            github_avatar_url=member.github_avatar_url,
            invited_email=member.invited_email,
            role=member.role,
            status=member.status,
            joined_at=member.joined_at,
            invited_at=member.invited_at,
            last_active_at=member.last_active_at,
        )

    except TeamServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{team_id}/members/{member_id}", response_model=TeamMemberResponse)
async def update_member_role(
        team_id: str,
        member_id: str,
        request: UpdateMemberRoleRequest,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Update a member's role (requires admin access)."""
    logger.info(f"[TEAMS API] PATCH /teams/{team_id}/members/{member_id}")

    await get_team_with_access(team_id, current_user, db, TeamRole.ADMIN)

    try:
        role = TeamRole(request.role)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")

    service = TeamService(db)

    try:
        member = await service.update_member_role(
            team_id=team_id,
            member_id=member_id,
            new_role=role,
            updated_by=current_user,
        )

        return TeamMemberResponse(
            id=member.id,
            team_id=member.team_id,
            user_id=member.user_id,
            github_id=member.github_id,
            github_username=member.github_username,
            github_avatar_url=member.github_avatar_url,
            invited_email=member.invited_email,
            role=member.role,
            status=member.status,
            joined_at=member.joined_at,
            invited_at=member.invited_at,
            last_active_at=member.last_active_at,
        )

    except TeamServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{team_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
        team_id: str,
        member_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    Remove a member from the team.

    Admins can remove members. Members can remove themselves (leave).
    """
    logger.info(f"[TEAMS API] DELETE /teams/{team_id}/members/{member_id}")

    await get_team_with_access(team_id, current_user, db)

    service = TeamService(db)

    try:
        await service.remove_member(
            team_id=team_id,
            member_id=member_id,
            removed_by=current_user,
        )
    except TeamServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== Team Projects ==============

@router.get("/{team_id}/projects", response_model=List[dict])
async def list_team_projects(
        team_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """List all projects in a team."""
    logger.info(f"[TEAMS API] GET /teams/{team_id}/projects")

    await get_team_with_access(team_id, current_user, db)

    service = TeamService(db)
    projects = await service.get_team_projects(team_id)

    return [{
        "id": p.id,
        "name": p.name,
        "repo_full_name": p.repo_full_name,
        "status": p.status,
        "health_score": p.health_score,
        "indexed_files_count": p.indexed_files_count,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    } for p in projects]


@router.post("/{team_id}/projects", status_code=status.HTTP_200_OK)
async def assign_project_to_team(
        team_id: str,
        request: AssignProjectRequest,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Assign a project to a team (requires admin access)."""
    logger.info(f"[TEAMS API] POST /teams/{team_id}/projects")

    await get_team_with_access(team_id, current_user, db, TeamRole.ADMIN)

    service = TeamService(db)

    try:
        project = await service.assign_project_to_team(
            project_id=request.project_id,
            team_id=team_id,
            user=current_user,
        )

        return {
            "success": True,
            "project_id": project.id,
            "team_id": team_id,
        }

    except TeamServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== GitHub Sync ==============

@router.post("/{team_id}/sync-collaborators")
async def sync_team_collaborators(
        team_id: str,
        project_id: str,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    Sync GitHub collaborators to team members.

    Requires admin access and a valid GitHub token.
    """
    logger.info(f"[TEAMS API] POST /teams/{team_id}/sync-collaborators")

    team = await get_team_with_access(team_id, current_user, db, TeamRole.ADMIN)

    # Get project
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get GitHub token
    if not current_user.github_token_encrypted:
        raise HTTPException(status_code=400, detail="GitHub token not available")

    github_token = decrypt_token(current_user.github_token_encrypted)

    # Sync collaborators
    sync_service = GitHubSyncService(db, github_token)

    try:
        members = await sync_service.sync_collaborators(project, team)

        return {
            "success": True,
            "synced_count": len(members),
            "members": [{"github_username": m.github_username, "role": m.role} for m in members],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))