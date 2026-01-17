"""Add GitHub token refresh fields to users table

Revision ID: 008
Revises: 007
Create Date: 2026-01-18

Adds:
- github_refresh_token: Encrypted refresh token for OAuth token refresh
- github_token_expires_at: Timestamp when the access token expires
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
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

    # Add github_refresh_token column to users table
    if not column_exists('users', 'github_refresh_token'):
        op.add_column(
            'users',
            sa.Column('github_refresh_token', sa.String(500), nullable=True)
        )

    # Add github_token_expires_at column to users table
    if not column_exists('users', 'github_token_expires_at'):
        op.add_column(
            'users',
            sa.Column('github_token_expires_at', sa.DateTime, nullable=True)
        )


def downgrade() -> None:
    # Remove the columns
    op.drop_column('users', 'github_token_expires_at')
    op.drop_column('users', 'github_refresh_token')
