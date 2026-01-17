"""Add git_changes table for tracking git flow changes per conversation

Revision ID: 005
Revises: 004
Create Date: 2026-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if table already exists
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'git_changes')"
    ))
    table_exists = result.scalar()

    if table_exists:
        # Table already exists, skip creation
        return

    # Create git_changes table for tracking all git changes per conversation
    op.create_table(
        'git_changes',
        sa.Column('id', UUID(as_uuid=False), primary_key=True),
        sa.Column('conversation_id', UUID(as_uuid=False), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', UUID(as_uuid=False), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('message_id', UUID(as_uuid=False), sa.ForeignKey('messages.id', ondelete='SET NULL'), nullable=True),

        # Branch info
        sa.Column('branch_name', sa.String(255), nullable=False),
        sa.Column('base_branch', sa.String(100), nullable=False, server_default='main'),
        sa.Column('commit_hash', sa.String(64), nullable=True),

        # Change status
        # pending: changes generated but not applied
        # applied: changes applied to local branch
        # pushed: branch pushed to remote
        # pr_created: pull request created
        # pr_merged: pull request merged
        # merged: branch merged to default branch
        # rolled_back: changes rolled back
        # discarded: changes discarded without applying
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),

        # PR info (when PR is created)
        sa.Column('pr_number', sa.Integer, nullable=True),
        sa.Column('pr_url', sa.String(500), nullable=True),
        sa.Column('pr_state', sa.String(20), nullable=True),  # open, closed, merged

        # Change details
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('files_changed', JSON, nullable=True),  # List of file changes with diffs
        sa.Column('change_summary', sa.Text, nullable=True),  # AI-generated summary

        # Rollback info
        sa.Column('rollback_commit', sa.String(64), nullable=True),  # Commit hash if rolled back
        sa.Column('rolled_back_at', sa.DateTime, nullable=True),
        sa.Column('rolled_back_from_status', sa.String(20), nullable=True),  # Status before rollback

        # Timestamps
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('applied_at', sa.DateTime, nullable=True),
        sa.Column('pushed_at', sa.DateTime, nullable=True),
        sa.Column('pr_created_at', sa.DateTime, nullable=True),
        sa.Column('merged_at', sa.DateTime, nullable=True),
    )

    # Create indexes for efficient querying
    op.create_index('ix_git_changes_conversation_id', 'git_changes', ['conversation_id'])
    op.create_index('ix_git_changes_project_id', 'git_changes', ['project_id'])
    op.create_index('ix_git_changes_status', 'git_changes', ['status'])
    op.create_index('ix_git_changes_branch_name', 'git_changes', ['branch_name'])
    op.create_index('ix_git_changes_created_at', 'git_changes', ['created_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_git_changes_created_at', table_name='git_changes')
    op.drop_index('ix_git_changes_branch_name', table_name='git_changes')
    op.drop_index('ix_git_changes_status', table_name='git_changes')
    op.drop_index('ix_git_changes_project_id', table_name='git_changes')
    op.drop_index('ix_git_changes_conversation_id', table_name='git_changes')

    # Drop table
    op.drop_table('git_changes')
