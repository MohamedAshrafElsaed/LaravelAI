"""
GitHub-related models for storing synced data.
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    String, Text, DateTime, ForeignKey, Integer, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.models import Project


def generate_uuid() -> str:
    return str(uuid4())


class GitHubIssue(Base):
    """Cached GitHub issues for a project."""
    __tablename__ = "github_issues"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"))

    github_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="open")

    author_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    author_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    author_avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    labels: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    assignees: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    html_url: Mapped[str] = mapped_column(String(500), nullable=False)

    github_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    github_updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    github_closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="github_issues")


class GitHubAction(Base):
    """Cached GitHub Actions workflow runs."""
    __tablename__ = "github_actions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"))

    github_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    workflow_id: Mapped[int] = mapped_column(Integer, nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(255), nullable=False)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String(50), nullable=False)
    conclusion: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    head_branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    head_sha: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    actor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actor_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    actor_avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    html_url: Mapped[str] = mapped_column(String(500), nullable=False)
    logs_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    github_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    github_updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    run_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="github_actions")


class GitHubProject(Base):
    """Cached GitHub Projects (v2)."""
    __tablename__ = "github_projects"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"))

    github_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="open")

    html_url: Mapped[str] = mapped_column(String(500), nullable=False)
    items_count: Mapped[int] = mapped_column(Integer, default=0)

    github_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    github_updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="github_projects_list")


class GitHubWikiPage(Base):
    """Cached GitHub Wiki pages."""
    __tablename__ = "github_wiki_pages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    html_url: Mapped[str] = mapped_column(String(500), nullable=False)

    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="github_wiki_pages")


class GitHubInsights(Base):
    """Cached GitHub repository insights/statistics."""
    __tablename__ = "github_insights"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
                                            unique=True)

    views_count: Mapped[int] = mapped_column(Integer, default=0)
    views_uniques: Mapped[int] = mapped_column(Integer, default=0)
    clones_count: Mapped[int] = mapped_column(Integer, default=0)
    clones_uniques: Mapped[int] = mapped_column(Integer, default=0)

    stars_count: Mapped[int] = mapped_column(Integer, default=0)
    forks_count: Mapped[int] = mapped_column(Integer, default=0)
    watchers_count: Mapped[int] = mapped_column(Integer, default=0)
    open_issues_count: Mapped[int] = mapped_column(Integer, default=0)

    code_frequency: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    commit_activity: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    contributors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    languages: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="github_insights")