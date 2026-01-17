"""Add AI usage tracking tables

Revision ID: 007
Revises: 006
Create Date: 2026-01-17

Adds:
- ai_usage table for tracking individual AI API calls
- ai_usage_summary table for aggregated daily statistics
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Helper to check if table exists
    def table_exists(table: str) -> bool:
        result = conn.execute(sa.text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = '{table}'
            )
        """))
        return result.scalar()

    # Create ai_usage table
    if not table_exists('ai_usage'):
        op.create_table(
            'ai_usage',
            sa.Column('id', UUID(as_uuid=False), primary_key=True),
            sa.Column('user_id', UUID(as_uuid=False), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('project_id', UUID(as_uuid=False), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),

            # Provider and model info
            sa.Column('provider', sa.String(50), nullable=False),
            sa.Column('model', sa.String(100), nullable=False),
            sa.Column('request_type', sa.String(50), nullable=False),

            # Token usage
            sa.Column('input_tokens', sa.Integer, nullable=False, server_default='0'),
            sa.Column('output_tokens', sa.Integer, nullable=False, server_default='0'),
            sa.Column('total_tokens', sa.Integer, nullable=False, server_default='0'),

            # Cost tracking (Numeric for precision)
            sa.Column('input_cost', sa.Numeric(10, 6), nullable=False, server_default='0'),
            sa.Column('output_cost', sa.Numeric(10, 6), nullable=False, server_default='0'),
            sa.Column('total_cost', sa.Numeric(10, 6), nullable=False, server_default='0'),

            # Request/response payloads
            sa.Column('request_payload', JSON, nullable=True),
            sa.Column('response_payload', JSON, nullable=True),

            # Performance metrics
            sa.Column('latency_ms', sa.Integer, nullable=False, server_default='0'),

            # Status tracking
            sa.Column('status', sa.String(20), nullable=False, server_default='success'),
            sa.Column('error_message', sa.Text, nullable=True),

            # Timestamp
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )

        # Create indexes for ai_usage
        op.create_index('ix_ai_usage_user_id', 'ai_usage', ['user_id'])
        op.create_index('ix_ai_usage_project_id', 'ai_usage', ['project_id'])
        op.create_index('ix_ai_usage_provider', 'ai_usage', ['provider'])
        op.create_index('ix_ai_usage_model', 'ai_usage', ['model'])
        op.create_index('ix_ai_usage_request_type', 'ai_usage', ['request_type'])
        op.create_index('ix_ai_usage_created_at', 'ai_usage', ['created_at'])
        op.create_index('ix_ai_usage_user_created', 'ai_usage', ['user_id', 'created_at'])

    # Create ai_usage_summary table
    if not table_exists('ai_usage_summary'):
        op.create_table(
            'ai_usage_summary',
            sa.Column('id', UUID(as_uuid=False), primary_key=True),
            sa.Column('user_id', UUID(as_uuid=False), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),

            # Aggregation dimensions
            sa.Column('date', sa.Date, nullable=False),
            sa.Column('provider', sa.String(50), nullable=False),
            sa.Column('model', sa.String(100), nullable=False),

            # Aggregated metrics
            sa.Column('total_requests', sa.Integer, nullable=False, server_default='0'),
            sa.Column('successful_requests', sa.Integer, nullable=False, server_default='0'),
            sa.Column('failed_requests', sa.Integer, nullable=False, server_default='0'),
            sa.Column('total_input_tokens', sa.Integer, nullable=False, server_default='0'),
            sa.Column('total_output_tokens', sa.Integer, nullable=False, server_default='0'),
            sa.Column('total_tokens', sa.Integer, nullable=False, server_default='0'),
            sa.Column('total_cost', sa.Numeric(10, 6), nullable=False, server_default='0'),

            # Performance metrics
            sa.Column('avg_latency_ms', sa.Integer, nullable=False, server_default='0'),
            sa.Column('min_latency_ms', sa.Integer, nullable=False, server_default='0'),
            sa.Column('max_latency_ms', sa.Integer, nullable=False, server_default='0'),

            # Timestamps
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )

        # Create indexes for ai_usage_summary
        op.create_index('ix_ai_usage_summary_user_date', 'ai_usage_summary', ['user_id', 'date'])
        op.create_index('ix_ai_usage_summary_user_provider', 'ai_usage_summary', ['user_id', 'provider'])
        op.create_index('ix_ai_usage_summary_date', 'ai_usage_summary', ['date'])
        op.create_index(
            'ix_ai_usage_summary_unique',
            'ai_usage_summary',
            ['user_id', 'date', 'provider', 'model'],
            unique=True
        )


def downgrade() -> None:
    # Drop ai_usage_summary indexes and table
    op.drop_index('ix_ai_usage_summary_unique', table_name='ai_usage_summary')
    op.drop_index('ix_ai_usage_summary_date', table_name='ai_usage_summary')
    op.drop_index('ix_ai_usage_summary_user_provider', table_name='ai_usage_summary')
    op.drop_index('ix_ai_usage_summary_user_date', table_name='ai_usage_summary')
    op.drop_table('ai_usage_summary')

    # Drop ai_usage indexes and table
    op.drop_index('ix_ai_usage_user_created', table_name='ai_usage')
    op.drop_index('ix_ai_usage_created_at', table_name='ai_usage')
    op.drop_index('ix_ai_usage_request_type', table_name='ai_usage')
    op.drop_index('ix_ai_usage_model', table_name='ai_usage')
    op.drop_index('ix_ai_usage_provider', table_name='ai_usage')
    op.drop_index('ix_ai_usage_project_id', table_name='ai_usage')
    op.drop_index('ix_ai_usage_user_id', table_name='ai_usage')
    op.drop_table('ai_usage')
