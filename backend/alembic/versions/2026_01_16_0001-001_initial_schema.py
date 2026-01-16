"""Initial schema with User, Project, IndexedFile, Conversation, and Message tables

Revision ID: 001
Revises:
Create Date: 2026-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("github_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("github_access_token", sa.String(500), nullable=False),  # Encrypted
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("monthly_requests", sa.Integer(), default=0, nullable=False),
        sa.Column("request_limit", sa.Integer(), default=100, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_github_id", "users", ["github_id"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # Create project_status enum
    project_status_enum = postgresql.ENUM(
        "pending", "indexing", "ready", "error",
        name="projectstatus",
        create_type=True,
    )
    project_status_enum.create(op.get_bind())

    # Create projects table
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("github_repo_id", sa.Integer(), nullable=False),
        sa.Column("repo_full_name", sa.String(255), nullable=False),
        sa.Column("repo_url", sa.String(500), nullable=False),
        sa.Column("default_branch", sa.String(100), default="main", nullable=False),
        sa.Column(
            "status",
            project_status_enum,
            default="pending",
            nullable=False,
        ),
        sa.Column("last_indexed_at", sa.DateTime(), nullable=True),
        sa.Column("indexed_files_count", sa.Integer(), default=0, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("laravel_version", sa.String(20), nullable=True),
        sa.Column("php_version", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_projects_github_repo_id", "projects", ["github_repo_id"])
    op.create_index(
        "ix_projects_user_repo",
        "projects",
        ["user_id", "github_repo_id"],
        unique=True,
    )

    # Create indexed_files table
    op.create_table(
        "indexed_files",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("file_metadata", postgresql.JSON(), nullable=True),
        sa.Column("qdrant_point_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_indexed_files_project_path",
        "indexed_files",
        ["project_id", "file_path"],
        unique=True,
    )

    # Create conversations table
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # Create messages table
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("code_changes", postgresql.JSON(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("indexed_files")
    op.drop_table("projects")

    # Drop enum type
    project_status_enum = postgresql.ENUM(
        "pending", "indexing", "ready", "error",
        name="projectstatus",
    )
    project_status_enum.drop(op.get_bind())

    op.drop_table("users")
