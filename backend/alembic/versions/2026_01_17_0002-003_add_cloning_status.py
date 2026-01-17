"""Add cloning status to projectstatus enum

Revision ID: 003
Revises: 002
Create Date: 2026-01-17

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'cloning' value to projectstatus enum
    # PostgreSQL requires ALTER TYPE to add new enum values
    op.execute("ALTER TYPE projectstatus ADD VALUE IF NOT EXISTS 'cloning' AFTER 'pending'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values easily
    # We'd need to recreate the type, which is complex
    # For now, just leave it - unused enum values don't hurt
    pass
