# ============================================================================
# FILE: backend/alembic/versions/2026_01_20_0001_add_teams_and_github_sync.py
# ============================================================================
"""
Add teams, team members, and GitHub sync tables.

Revision ID: 003_teams_github
Revises: 002 (or your latest revision)
Create Date: 2026-01-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_teams_github"
down_revision = "008"  # Update to your latest revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE teamrole AS ENUM ('owner', 'admin', 'member', 'viewer')")
    op.execute("CREATE TYPE teammemberstatus AS ENUM ('pending', 'active', 'inactive', 'declined')")

    # ========== Teams Table ==========
    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_personal", sa.Boolean(), default=False),
        sa.Column("settings", postgresql.JSON(), nullable=True),
        sa.Column("github_org_id", sa.Integer(), nullable=True),
        sa.Column("github_org_name", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_teams_owner_id", "teams", ["owner_id"])
    op.create_index("ix_teams_slug", "teams", ["slug"])

    # ========== Team Members Table ==========
    op.create_table(
        "team_members",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("github_id", sa.Integer(), nullable=True),
        sa.Column("github_username", sa.String(100), nullable=True),
        sa.Column("github_avatar_url", sa.String(500), nullable=True),
        sa.Column("invited_email", sa.String(255), nullable=True),
        sa.Column("invited_by_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role", postgresql.ENUM('owner', 'admin', 'member', 'viewer',
                                          name='teamrole', create_type=False), default='member'),
        sa.Column("status", postgresql.ENUM('pending', 'active', 'inactive', 'declined',
                                            name='teammemberstatus', create_type=False), default='pending'),
        sa.Column("permissions", postgresql.JSON(), nullable=True),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.Column("invited_at", sa.DateTime(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"])
    op.create_unique_constraint("uq_team_member", "team_members", ["team_id", "user_id"])
    op.create_unique_constraint("uq_team_github_member", "team_members", ["team_id", "github_username"])

    # ========== Add team_id to Projects ==========
    op.add_column("projects", sa.Column("team_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.create_foreign_key("fk_projects_team_id", "projects", "teams", ["team_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_projects_team_id", "projects", ["team_id"])

    # ========== GitHub Issues Table ==========
    op.create_table(
        "github_issues",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("github_id", sa.Integer(), unique=True, nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("state", sa.String(20), default="open"),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("author_username", sa.String(100), nullable=True),
        sa.Column("author_avatar_url", sa.String(500), nullable=True),
        sa.Column("labels", postgresql.JSON(), nullable=True),
        sa.Column("assignees", postgresql.JSON(), nullable=True),
        sa.Column("comments_count", sa.Integer(), default=0),
        sa.Column("html_url", sa.String(500), nullable=False),
        sa.Column("github_created_at", sa.DateTime(), nullable=False),
        sa.Column("github_updated_at", sa.DateTime(), nullable=False),
        sa.Column("github_closed_at", sa.DateTime(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_github_issues_project_id", "github_issues", ["project_id"])
    op.create_index("ix_github_issues_state", "github_issues", ["state"])

    # ========== GitHub Actions Table ==========
    op.create_table(
        "github_actions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("github_id", sa.Integer(), unique=True, nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("workflow_name", sa.String(255), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("conclusion", sa.String(50), nullable=True),
        sa.Column("head_branch", sa.String(255), nullable=True),
        sa.Column("head_sha", sa.String(40), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(100), nullable=True),
        sa.Column("actor_avatar_url", sa.String(500), nullable=True),
        sa.Column("html_url", sa.String(500), nullable=False),
        sa.Column("logs_url", sa.String(500), nullable=True),
        sa.Column("github_created_at", sa.DateTime(), nullable=False),
        sa.Column("github_updated_at", sa.DateTime(), nullable=False),
        sa.Column("run_started_at", sa.DateTime(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_github_actions_project_id", "github_actions", ["project_id"])
    op.create_index("ix_github_actions_status", "github_actions", ["status"])

    # ========== GitHub Projects Table ==========
    op.create_table(
        "github_projects",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("github_id", sa.Integer(), unique=True, nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("state", sa.String(20), default="open"),
        sa.Column("html_url", sa.String(500), nullable=False),
        sa.Column("items_count", sa.Integer(), default=0),
        sa.Column("github_created_at", sa.DateTime(), nullable=False),
        sa.Column("github_updated_at", sa.DateTime(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_github_projects_project_id", "github_projects", ["project_id"])

    # ========== GitHub Wiki Pages Table ==========
    op.create_table(
        "github_wiki_pages",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("html_url", sa.String(500), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_github_wiki_project_id", "github_wiki_pages", ["project_id"])

    # ========== GitHub Insights Table ==========
    op.create_table(
        "github_insights",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("views_count", sa.Integer(), default=0),
        sa.Column("views_uniques", sa.Integer(), default=0),
        sa.Column("clones_count", sa.Integer(), default=0),
        sa.Column("clones_uniques", sa.Integer(), default=0),
        sa.Column("stars_count", sa.Integer(), default=0),
        sa.Column("forks_count", sa.Integer(), default=0),
        sa.Column("watchers_count", sa.Integer(), default=0),
        sa.Column("open_issues_count", sa.Integer(), default=0),
        sa.Column("code_frequency", postgresql.JSON(), nullable=True),
        sa.Column("commit_activity", postgresql.JSON(), nullable=True),
        sa.Column("contributors", postgresql.JSON(), nullable=True),
        sa.Column("languages", postgresql.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("github_insights")
    op.drop_table("github_wiki_pages")
    op.drop_table("github_projects")
    op.drop_table("github_actions")
    op.drop_table("github_issues")

    op.drop_constraint("fk_projects_team_id", "projects", type_="foreignkey")
    op.drop_index("ix_projects_team_id", "projects")
    op.drop_column("projects", "team_id")

    op.drop_table("team_members")
    op.drop_table("teams")

    op.execute("DROP TYPE teammemberstatus")
    op.execute("DROP TYPE teamrole")