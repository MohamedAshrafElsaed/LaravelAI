"""
SQLAlchemy models for Laravel AI.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import uuid4

from app.models.github_models import GitHubIssue, GitHubAction, GitHubProject, GitHubWikiPage, GitHubInsights
from app.models.team_models import Team, TeamMember
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text,
    Enum as SQLEnum, Index, JSON, Float, Numeric, Date
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


def generate_uuid() -> str:
    return str(uuid4())


class ProjectStatus(str, Enum):
    PENDING = "pending"
    CLONING = "cloning"
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class IssueStatus(str, Enum):
    OPEN = "open"
    FIXED = "fixed"
    IGNORED = "ignored"


class User(Base):
    """User model - authenticated via GitHub OAuth."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    github_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    github_access_token: Mapped[str] = mapped_column(String(500))  # Encrypted token

    # GitHub token refresh (for OAuth apps with token expiration enabled)
    github_refresh_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Encrypted
    github_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Subscription/limits
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    monthly_requests: Mapped[int] = mapped_column(Integer, default=0)
    request_limit: Mapped[int] = mapped_column(Integer, default=100)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    projects: Mapped[list["Project"]] = relationship(
        "Project", back_populates="user", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    owned_teams: Mapped[List["Team"]] = relationship(
        "Team",
        back_populates="owner",
        foreign_keys="Team.owner_id"
    )
    team_memberships: Mapped[List["TeamMember"]] = relationship(
        "TeamMember",
        back_populates="user",
        foreign_keys="TeamMember.user_id"
    )


class Project(Base):
    """Connected GitHub repository."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )

    # GitHub info
    github_repo_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(255))  # repo name only
    repo_full_name: Mapped[str] = mapped_column(String(255))  # owner/repo
    repo_url: Mapped[str] = mapped_column(String(500))
    default_branch: Mapped[str] = mapped_column(String(100), default="main")

    # Clone path for local repository
    clone_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Indexing status (using String for better PostgreSQL compatibility)
    status: Mapped[str] = mapped_column(
        String(20), default=ProjectStatus.PENDING.value
    )
    last_indexed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    indexed_files_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Laravel specific metadata (legacy - now part of stack)
    laravel_version: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    php_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Stack Detection (detected framework, versions, packages)
    stack: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {"backend": {"framework": "laravel", "version": "12.0"}, "frontend": {"framework": "vue", "version": "3.5"}}

    # File Statistics
    file_stats: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {"total_files": 1020, "total_lines": 150000, "by_type": {...}, "by_category": {...}}

    # Structure Analysis
    structure: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {"directories": [...], "key_files": [...], "patterns_detected": ["repository", "service-layer"]}

    # Health Check Results
    health_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0-100
    health_check: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {"score": 72, "categories": {...}, "critical_issues": [...], "warnings": [...]}

    # AI Context (internal - user doesn't see raw form)
    ai_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {"claude_md_content": "...", "key_patterns": [...], "conventions": {...}}

    # Scan Progress
    scan_progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    scan_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    scanned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="projects")
    issues: Mapped[list["ProjectIssue"]] = relationship(
        "ProjectIssue", back_populates="project", cascade="all, delete-orphan"
    )
    indexed_files: Mapped[list["IndexedFile"]] = relationship(
        "IndexedFile", back_populates="project", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="project", cascade="all, delete-orphan"
    )
    git_changes: Mapped[list["GitChange"]] = relationship(
        "GitChange", back_populates="project", cascade="all, delete-orphan"
    )
    # Team reference (ADD THIS FIELD)
    team_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=True
    )

    # Team relationship (ADD THIS)
    team: Mapped[Optional["Team"]] = relationship("Team", back_populates="projects")

    # GitHub data relationships (ADD THESE)
    github_issues: Mapped[List["GitHubIssue"]] = relationship(
        "GitHubIssue",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    github_actions: Mapped[List["GitHubAction"]] = relationship(
        "GitHubAction",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    github_projects_list: Mapped[List["GitHubProject"]] = relationship(
        "GitHubProject",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    github_wiki_pages: Mapped[List["GitHubWikiPage"]] = relationship(
        "GitHubWikiPage",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    github_insights: Mapped[Optional["GitHubInsights"]] = relationship(
        "GitHubInsights",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_projects_user_repo", "user_id", "github_repo_id", unique=True),
    )


class IndexedFile(Base):
    """Indexed file from a Laravel project."""

    __tablename__ = "indexed_files"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE")
    )

    # File info
    file_path: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(50))  # controller, model, etc.
    file_hash: Mapped[str] = mapped_column(String(64))  # For change detection

    # Content
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Parsed file metadata (class names, methods, etc.)
    file_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # e.g., {"class_name": "UserController", "methods": ["index", "store"]}

    # Vector reference
    qdrant_point_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project", back_populates="indexed_files"
    )

    __table_args__ = (
        Index("ix_indexed_files_project_path", "project_id", "file_path", unique=True),
    )


class Conversation(Base):
    """AI conversation/chat session."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE")
    )

    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    project: Mapped["Project"] = relationship(
        "Project", back_populates="conversations"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    git_changes: Mapped[list["GitChange"]] = relationship(
        "GitChange", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """Individual message in a conversation."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="CASCADE")
    )

    role: Mapped[str] = mapped_column(String(20))  # user, assistant, system
    content: Mapped[str] = mapped_column(Text)

    # For assistant messages with code changes
    code_changes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # e.g., {"files": [{"path": "...", "diff": "...", "action": "modify"}]}

    # Full processing data for history replay (intent, plan, steps, validation, events)
    processing_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # e.g., {"intent": {...}, "plan": {...}, "events": [...], "validation": {...}}

    # Token usage tracking
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )
    git_changes: Mapped[list["GitChange"]] = relationship(
        "GitChange", back_populates="message"
    )


class GitChangeStatus(str, Enum):
    """Status of a git change through the git flow."""

    PENDING = "pending"          # Changes generated but not applied
    APPLIED = "applied"          # Changes applied to local branch
    PUSHED = "pushed"            # Branch pushed to remote
    PR_CREATED = "pr_created"    # Pull request created
    PR_MERGED = "pr_merged"      # Pull request merged
    MERGED = "merged"            # Branch merged to default branch
    ROLLED_BACK = "rolled_back"  # Changes rolled back
    DISCARDED = "discarded"      # Changes discarded without applying


class GitChange(Base):
    """
    Track git changes for each conversation.

    Records the lifecycle of code changes from generation through PR creation/merge.
    Supports rollback functionality to revert changes.
    """

    __tablename__ = "git_changes"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE")
    )
    message_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )

    # Branch info
    branch_name: Mapped[str] = mapped_column(String(255))
    base_branch: Mapped[str] = mapped_column(String(100), default="main")
    commit_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Change status
    status: Mapped[str] = mapped_column(
        String(20), default=GitChangeStatus.PENDING.value
    )

    # PR info
    pr_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pr_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pr_state: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Change details
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    files_changed: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Rollback info
    rollback_commit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rolled_back_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rolled_back_from_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pushed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pr_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    merged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="git_changes"
    )
    project: Mapped["Project"] = relationship("Project", back_populates="git_changes")
    message: Mapped[Optional["Message"]] = relationship(
        "Message", back_populates="git_changes"
    )


class ProjectIssue(Base):
    """
    Health check issues found in a project.

    Tracks security, performance, architecture, and other issues
    detected during project scanning and health checks.
    """

    __tablename__ = "project_issues"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE")
    )

    # Issue categorization
    category: Mapped[str] = mapped_column(String(50))  # security, performance, architecture, etc.
    severity: Mapped[str] = mapped_column(
        String(20), default=IssueSeverity.INFO.value
    )  # critical, warning, info

    # Issue details
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)

    # Location (optional)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    line_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Fix information
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auto_fixable: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20), default=IssueStatus.OPEN.value
    )  # open, fixed, ignored

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="issues")

    __table_args__ = (
        Index("ix_project_issues_project_category", "project_id", "category"),
        Index("ix_project_issues_severity", "severity"),
    )


class AIUsageStatus(str, Enum):
    """Status of an AI API call."""
    SUCCESS = "success"
    ERROR = "error"


class AIUsageRequestType(str, Enum):
    """Type of AI request."""
    INTENT = "intent"
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"
    EMBEDDING = "embedding"
    CHAT = "chat"


class AIUsage(Base):
    """
    Track AI API usage for cost monitoring and analytics.

    Records every AI API call with token counts, costs, latency,
    and request/response payloads for debugging and optimization.
    """

    __tablename__ = "ai_usage"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )

    # Provider and model info
    provider: Mapped[str] = mapped_column(String(50))  # claude, openai, voyage
    model: Mapped[str] = mapped_column(String(100))    # claude-haiku-4-5-20251001, etc.
    request_type: Mapped[str] = mapped_column(String(50))  # intent, planning, execution, etc.

    # Token usage
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Cost tracking (Numeric for precise decimal storage)
    input_cost: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    output_cost: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(10, 6), default=0)

    # Request/response payloads (for debugging and analysis)
    request_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Performance metrics
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20), default=AIUsageStatus.SUCCESS.value
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="ai_usage")
    project: Mapped[Optional["Project"]] = relationship("Project", backref="ai_usage")

    __table_args__ = (
        Index("ix_ai_usage_user_id", "user_id"),
        Index("ix_ai_usage_project_id", "project_id"),
        Index("ix_ai_usage_provider", "provider"),
        Index("ix_ai_usage_model", "model"),
        Index("ix_ai_usage_request_type", "request_type"),
        Index("ix_ai_usage_created_at", "created_at"),
        Index("ix_ai_usage_user_created", "user_id", "created_at"),
    )


class AIUsageSummary(Base):
    """
    Aggregated daily AI usage statistics for quick lookups.

    Pre-aggregated summary table for efficient dashboard queries.
    Updated periodically or on-demand from ai_usage table.
    """

    __tablename__ = "ai_usage_summary"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )

    # Aggregation dimensions
    date: Mapped[datetime] = mapped_column(Date)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))

    # Aggregated metrics
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    successful_requests: Mapped[int] = mapped_column(Integer, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, default=0)
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(10, 6), default=0)

    # Performance metrics
    avg_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    min_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    max_latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="ai_usage_summaries")

    __table_args__ = (
        Index("ix_ai_usage_summary_user_date", "user_id", "date"),
        Index("ix_ai_usage_summary_user_provider", "user_id", "provider"),
        Index("ix_ai_usage_summary_date", "date"),
        # Unique constraint for aggregation key
        Index(
            "ix_ai_usage_summary_unique",
            "user_id", "date", "provider", "model",
            unique=True
        ),
    )