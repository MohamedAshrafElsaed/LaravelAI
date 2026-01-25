"""
Team and TeamMember models for multi-tenant collaboration.
"""
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from enum import Enum
from uuid import uuid4
from sqlalchemy.dialects.postgresql import UUID, ENUM

from sqlalchemy import (
    String, Text, DateTime, ForeignKey, Integer, Boolean, JSON, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.models import User, Project


def generate_uuid() -> str:
    return str(uuid4())


class TeamRole(str, Enum):
    """Team member roles with different permission levels."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class TeamMemberStatus(str, Enum):
    """Team member invitation status."""
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DECLINED = "declined"


class Team(Base):
    """Team model for grouping users and projects."""
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    is_personal: Mapped[bool] = mapped_column(Boolean, default=False)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    github_org_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    github_org_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="owned_teams", foreign_keys=[owner_id])
    members: Mapped[List["TeamMember"]] = relationship("TeamMember", back_populates="team",
                                                       cascade="all, delete-orphan")
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="team")


class TeamMember(Base):
    """Team membership with role-based access."""
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint('team_id', 'user_id', name='uq_team_member'),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )

    team_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )

    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    github_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    github_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    github_avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    invited_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    invited_by_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    role: Mapped[str] = mapped_column(
        ENUM('owner', 'admin', 'member', 'viewer', name='teamrole', create_type=False),
        default=TeamRole.MEMBER.value
    )
    status: Mapped[str] = mapped_column(
        ENUM('pending', 'active', 'inactive', 'declined', name='teammemberstatus', create_type=False),
        default=TeamMemberStatus.PENDING.value
    )

    permissions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    invited_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="members")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="team_memberships", foreign_keys=[user_id])
    invited_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[invited_by_id])