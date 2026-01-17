"""Add project scanner and health check fields

Revision ID: 006
Revises: 005
Create Date: 2026-01-17

Adds:
- stack, file_stats, structure JSON columns to projects
- health_score, health_check columns to projects
- ai_context JSON column to projects
- scan_progress, scan_message, scanned_at to projects
- project_issues table for tracking health check issues
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Helper to check if column exists
    def column_exists(table: str, column: str) -> bool:
        result = conn.execute(sa.text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = '{table}' AND column_name = '{column}'
            )
        """))
        return result.scalar()

    # Helper to check if table exists
    def table_exists(table: str) -> bool:
        result = conn.execute(sa.text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = '{table}'
            )
        """))
        return result.scalar()

    # Add new columns to projects table
    if not column_exists('projects', 'stack'):
        op.add_column('projects', sa.Column('stack', JSON, nullable=True))

    if not column_exists('projects', 'file_stats'):
        op.add_column('projects', sa.Column('file_stats', JSON, nullable=True))

    if not column_exists('projects', 'structure'):
        op.add_column('projects', sa.Column('structure', JSON, nullable=True))

    if not column_exists('projects', 'health_score'):
        op.add_column('projects', sa.Column('health_score', sa.Float, nullable=True))

    if not column_exists('projects', 'health_check'):
        op.add_column('projects', sa.Column('health_check', JSON, nullable=True))

    if not column_exists('projects', 'ai_context'):
        op.add_column('projects', sa.Column('ai_context', JSON, nullable=True))

    if not column_exists('projects', 'scan_progress'):
        op.add_column('projects', sa.Column('scan_progress', sa.Integer, nullable=False, server_default='0'))

    if not column_exists('projects', 'scan_message'):
        op.add_column('projects', sa.Column('scan_message', sa.String(500), nullable=True))

    if not column_exists('projects', 'scanned_at'):
        op.add_column('projects', sa.Column('scanned_at', sa.DateTime, nullable=True))

    # Create project_issues table
    if not table_exists('project_issues'):
        op.create_table(
            'project_issues',
            sa.Column('id', UUID(as_uuid=False), primary_key=True),
            sa.Column('project_id', UUID(as_uuid=False), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),

            # Issue categorization
            sa.Column('category', sa.String(50), nullable=False),  # security, performance, architecture, etc.
            sa.Column('severity', sa.String(20), nullable=False, server_default='info'),  # critical, warning, info

            # Issue details
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('description', sa.Text, nullable=False),

            # Location (optional)
            sa.Column('file_path', sa.String(500), nullable=True),
            sa.Column('line_number', sa.Integer, nullable=True),

            # Fix information
            sa.Column('suggestion', sa.Text, nullable=True),
            sa.Column('auto_fixable', sa.Boolean, nullable=False, server_default='false'),

            # Status tracking
            sa.Column('status', sa.String(20), nullable=False, server_default='open'),  # open, fixed, ignored

            # Timestamps
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )

        # Create indexes for project_issues
        op.create_index('ix_project_issues_project_id', 'project_issues', ['project_id'])
        op.create_index('ix_project_issues_project_category', 'project_issues', ['project_id', 'category'])
        op.create_index('ix_project_issues_severity', 'project_issues', ['severity'])
        op.create_index('ix_project_issues_status', 'project_issues', ['status'])


def downgrade() -> None:
    # Drop project_issues table
    op.drop_index('ix_project_issues_status', table_name='project_issues')
    op.drop_index('ix_project_issues_severity', table_name='project_issues')
    op.drop_index('ix_project_issues_project_category', table_name='project_issues')
    op.drop_index('ix_project_issues_project_id', table_name='project_issues')
    op.drop_table('project_issues')

    # Remove columns from projects
    op.drop_column('projects', 'scanned_at')
    op.drop_column('projects', 'scan_message')
    op.drop_column('projects', 'scan_progress')
    op.drop_column('projects', 'ai_context')
    op.drop_column('projects', 'health_check')
    op.drop_column('projects', 'health_score')
    op.drop_column('projects', 'structure')
    op.drop_column('projects', 'file_stats')
    op.drop_column('projects', 'stack')
