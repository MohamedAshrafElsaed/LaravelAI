# ============================================================================
# FILE: backend/app/services/team_service.py
# ============================================================================
"""
Team management service.

Handles team creation, member management, and access control.
Automatically creates personal teams for new users.
"""
import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.team_models import Team, TeamMember, TeamRole, TeamMemberStatus
from app.models.models import User, Project

logger = logging.getLogger(__name__)


class TeamServiceError(Exception):
    """Team service error."""
    pass


class TeamService:
    """
    Service for managing teams and team members.

    Features:
    - Automatic personal team creation on signup
    - Role-based access control
    - GitHub collaborator sync
    - Team project management
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== Team Creation ==========

    async def create_personal_team(self, user: User) -> Team:
        """
        Create a personal team for a new user.
        Called automatically during user registration.

        Args:
            user: The newly registered user

        Returns:
            The created personal team
        """
        logger.info(f"[TEAM_SERVICE] Creating personal team for user: {user.username}")

        slug = self._generate_slug(user.username)

        team = Team(
            id=str(uuid4()),
            name=f"{user.username}'s Team",
            slug=slug,
            description=f"Personal workspace for {user.username}",
            avatar_url=user.avatar_url,
            owner_id=str(user.id),
            is_personal=True,
            settings={
                "default_branch": "main",
                "auto_sync_collaborators": True,
                "notifications_enabled": True,
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(team)
        await self.db.flush()

        # Add owner as team member
        owner_member = TeamMember(
            id=str(uuid4()),
            team_id=team.id,
            user_id=str(user.id),
            github_id=user.github_id,
            github_username=user.username,
            github_avatar_url=user.avatar_url,
            role=TeamRole.OWNER.value,
            status=TeamMemberStatus.ACTIVE.value,
            joined_at=datetime.utcnow(),
            invited_at=datetime.utcnow(),
            last_active_at=datetime.utcnow(),
        )

        self.db.add(owner_member)
        await self.db.commit()
        await self.db.refresh(team)

        logger.info(f"[TEAM_SERVICE] Personal team created: {team.id}")
        return team

    async def create_team(
            self,
            owner: User,
            name: str,
            description: Optional[str] = None,
            github_org_id: Optional[int] = None,
            github_org_name: Optional[str] = None,
    ) -> Team:
        """
        Create a new team.

        Args:
            owner: User creating the team
            name: Team name
            description: Optional description
            github_org_id: Optional GitHub organization ID
            github_org_name: Optional GitHub organization name

        Returns:
            The created team
        """
        logger.info(f"[TEAM_SERVICE] Creating team '{name}' for user: {owner.username}")

        slug = self._generate_slug(name)

        # Check if slug exists
        existing = await self.get_team_by_slug(slug)
        if existing:
            slug = f"{slug}-{str(uuid4())[:8]}"

        team = Team(
            id=str(uuid4()),
            name=name,
            slug=slug,
            description=description,
            avatar_url=owner.avatar_url,
            owner_id=str(owner.id),
            is_personal=False,
            github_org_id=github_org_id,
            github_org_name=github_org_name,
            settings={
                "default_branch": "main",
                "auto_sync_collaborators": True,
                "notifications_enabled": True,
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(team)
        await self.db.flush()

        # Add owner as team member
        owner_member = TeamMember(
            id=str(uuid4()),
            team_id=team.id,
            user_id=str(owner.id),
            github_id=owner.github_id,
            github_username=owner.username,
            github_avatar_url=owner.avatar_url,
            role=TeamRole.OWNER.value,
            status=TeamMemberStatus.ACTIVE.value,
            joined_at=datetime.utcnow(),
            invited_at=datetime.utcnow(),
            last_active_at=datetime.utcnow(),
        )

        self.db.add(owner_member)
        await self.db.commit()
        await self.db.refresh(team)

        logger.info(f"[TEAM_SERVICE] Team created: {team.id}")
        return team

    # ========== Team Retrieval ==========

    async def get_team(self, team_id: str) -> Optional[Team]:
        """Get team by ID."""
        stmt = select(Team).where(Team.id == team_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_team_by_slug(self, slug: str) -> Optional[Team]:
        """Get team by slug."""
        stmt = select(Team).where(Team.slug == slug)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_teams(self, user_id: str) -> List[Team]:
        """Get all teams a user belongs to."""
        stmt = (
            select(Team)
            .join(TeamMember, Team.id == TeamMember.team_id)
            .where(
                TeamMember.user_id == user_id,
                TeamMember.status == TeamMemberStatus.ACTIVE.value,
            )
            .order_by(Team.is_personal.desc(), Team.name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_personal_team(self, user_id: str) -> Optional[Team]:
        """Get user's personal team."""
        stmt = select(Team).where(
            Team.owner_id == user_id,
            Team.is_personal == True,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_team_with_members(self, team_id: str) -> Optional[Team]:
        """Get team with members loaded."""
        stmt = (
            select(Team)
            .options(selectinload(Team.members))
            .where(Team.id == team_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ========== Member Management ==========

    async def add_member(
            self,
            team_id: str,
            invited_by: User,
            user_id: Optional[str] = None,
            github_username: Optional[str] = None,
            github_id: Optional[int] = None,
            github_avatar_url: Optional[str] = None,
            email: Optional[str] = None,
            role: TeamRole = TeamRole.MEMBER,
    ) -> TeamMember:
        """
        Add a member to a team.

        Can add by user_id (existing user) or github_username (pending).
        """
        logger.info(f"[TEAM_SERVICE] Adding member to team {team_id}")

        # Check if already a member
        existing = await self.get_team_member(team_id, user_id, github_username)
        if existing:
            if existing.status == TeamMemberStatus.ACTIVE.value:
                raise TeamServiceError("User is already a member of this team")
            # Reactivate if inactive
            existing.status = TeamMemberStatus.ACTIVE.value
            existing.role = role.value
            existing.joined_at = datetime.utcnow()
            await self.db.commit()
            return existing

        member = TeamMember(
            id=str(uuid4()),
            team_id=team_id,
            user_id=user_id,
            github_id=github_id,
            github_username=github_username,
            github_avatar_url=github_avatar_url,
            invited_email=email,
            invited_by_id=str(invited_by.id),
            role=role.value,
            status=TeamMemberStatus.PENDING.value if not user_id else TeamMemberStatus.ACTIVE.value,
            invited_at=datetime.utcnow(),
            joined_at=datetime.utcnow() if user_id else None,
        )

        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)

        logger.info(f"[TEAM_SERVICE] Member added: {member.id}")
        return member

    async def get_team_member(
            self,
            team_id: str,
            user_id: Optional[str] = None,
            github_username: Optional[str] = None,
    ) -> Optional[TeamMember]:
        """Get a team member by user_id or github_username."""
        conditions = [TeamMember.team_id == team_id]

        if user_id:
            conditions.append(TeamMember.user_id == user_id)
        elif github_username:
            conditions.append(TeamMember.github_username == github_username)
        else:
            return None

        stmt = select(TeamMember).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_team_members(
            self,
            team_id: str,
            status: Optional[TeamMemberStatus] = None,
    ) -> List[TeamMember]:
        """Get all members of a team."""
        stmt = select(TeamMember).where(TeamMember.team_id == team_id)

        if status:
            stmt = stmt.where(TeamMember.status == status.value)

        stmt = stmt.order_by(TeamMember.role, TeamMember.joined_at)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_member_role(
            self,
            team_id: str,
            member_id: str,
            new_role: TeamRole,
            updated_by: User,
    ) -> TeamMember:
        """Update a member's role."""
        member = await self._get_member_by_id(member_id, team_id)

        # Can't change owner role
        if member.role == TeamRole.OWNER.value:
            raise TeamServiceError("Cannot change owner role")

        # Check permissions
        updater = await self.get_team_member(team_id, str(updated_by.id))
        if not updater or updater.role not in [TeamRole.OWNER.value, TeamRole.ADMIN.value]:
            raise TeamServiceError("Insufficient permissions to update member role")

        member.role = new_role.value
        await self.db.commit()
        await self.db.refresh(member)

        return member

    async def remove_member(
            self,
            team_id: str,
            member_id: str,
            removed_by: User,
    ) -> bool:
        """Remove a member from a team."""
        member = await self._get_member_by_id(member_id, team_id)

        # Can't remove owner
        if member.role == TeamRole.OWNER.value:
            raise TeamServiceError("Cannot remove team owner")

        # Check permissions (owners and admins can remove, or member can leave)
        remover = await self.get_team_member(team_id, str(removed_by.id))
        is_self = member.user_id == str(removed_by.id)

        if not is_self and (not remover or remover.role not in [TeamRole.OWNER.value, TeamRole.ADMIN.value]):
            raise TeamServiceError("Insufficient permissions to remove member")

        await self.db.delete(member)
        await self.db.commit()

        logger.info(f"[TEAM_SERVICE] Member removed: {member_id}")
        return True

    async def accept_invitation(self, member_id: str, user: User) -> TeamMember:
        """Accept a team invitation."""
        stmt = select(TeamMember).where(
            TeamMember.id == member_id,
            TeamMember.status == TeamMemberStatus.PENDING.value,
        )
        result = await self.db.execute(stmt)
        member = result.scalar_one_or_none()

        if not member:
            raise TeamServiceError("Invitation not found or already processed")

        # Link user to member
        member.user_id = str(user.id)
        member.github_id = user.github_id
        member.github_username = user.username
        member.github_avatar_url = user.avatar_url
        member.status = TeamMemberStatus.ACTIVE.value
        member.joined_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(member)

        return member

    # ========== Access Control ==========

    async def check_team_access(
            self,
            team_id: str,
            user_id: str,
            required_role: Optional[TeamRole] = None,
    ) -> bool:
        """Check if user has access to team with optional role requirement."""
        member = await self.get_team_member(team_id, user_id)

        if not member or member.status != TeamMemberStatus.ACTIVE.value:
            return False

        if required_role:
            role_hierarchy = {
                TeamRole.OWNER.value: 4,
                TeamRole.ADMIN.value: 3,
                TeamRole.MEMBER.value: 2,
                TeamRole.VIEWER.value: 1,
            }
            return role_hierarchy.get(member.role, 0) >= role_hierarchy.get(required_role.value, 0)

        return True

    async def check_project_access(
            self,
            project_id: str,
            user_id: str,
    ) -> bool:
        """Check if user has access to a project (via team membership)."""
        stmt = (
            select(Project)
            .where(Project.id == project_id)
        )
        result = await self.db.execute(stmt)
        project = result.scalar_one_or_none()

        if not project:
            return False

        # Check if user owns the project directly (legacy)
        if project.user_id == user_id:
            return True

        # Check team membership
        if project.team_id:
            return await self.check_team_access(project.team_id, user_id)

        return False

    # ========== Project Assignment ==========

    async def assign_project_to_team(
            self,
            project_id: str,
            team_id: str,
            user: User,
    ) -> Project:
        """Assign a project to a team."""
        # Verify team access
        if not await self.check_team_access(team_id, str(user.id), TeamRole.ADMIN):
            raise TeamServiceError("Insufficient permissions to assign project to team")

        stmt = select(Project).where(Project.id == project_id)
        result = await self.db.execute(stmt)
        project = result.scalar_one_or_none()

        if not project:
            raise TeamServiceError("Project not found")

        # Only owner can assign their projects
        if project.user_id != str(user.id):
            raise TeamServiceError("Only project owner can assign to team")

        project.team_id = team_id
        await self.db.commit()
        await self.db.refresh(project)

        return project

    async def get_team_projects(self, team_id: str) -> List[Project]:
        """Get all projects belonging to a team."""
        stmt = (
            select(Project)
            .where(Project.team_id == team_id)
            .order_by(Project.updated_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ========== Helper Methods ==========

    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from name."""
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')

    async def _get_member_by_id(self, member_id: str, team_id: str) -> TeamMember:
        """Get member by ID with team verification."""
        stmt = select(TeamMember).where(
            TeamMember.id == member_id,
            TeamMember.team_id == team_id,
        )
        result = await self.db.execute(stmt)
        member = result.scalar_one_or_none()

        if not member:
            raise TeamServiceError("Member not found")

        return member

    async def update_member_activity(self, team_id: str, user_id: str) -> None:
        """Update member's last activity timestamp."""
        member = await self.get_team_member(team_id, user_id)
        if member:
            member.last_active_at = datetime.utcnow()
            await self.db.commit()