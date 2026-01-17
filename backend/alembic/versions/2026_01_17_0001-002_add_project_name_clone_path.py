"""Add name and clone_path columns to projects, add cloning status

Revision ID: 002
Revises: 001
Create Date: 2026-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'cloning' value to projectstatus enum
    # Must be outside transaction for PostgreSQL enum changes
    op.execute("COMMIT")
    op.execute("ALTER TYPE projectstatus ADD VALUE IF NOT EXISTS 'cloning'")

    # Add name column to projects (nullable first)
    op.add_column(
        "projects",
        sa.Column("name", sa.String(255), nullable=True),
    )

    # Populate name from repo_full_name (extract repo name after /)
    op.execute(
        "UPDATE projects SET name = split_part(repo_full_name, '/', 2) WHERE name IS NULL"
    )

    # Make name not nullable
    op.alter_column("projects", "name", nullable=False)

    # Add clone_path column (nullable)
    op.add_column(
        "projects",
        sa.Column("clone_path", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    # Remove clone_path column
    op.drop_column("projects", "clone_path")

    # Remove name column
    op.drop_column("projects", "name")

    # Note: PostgreSQL doesn't support removing enum values easily
    # The 'cloning' value will remain in the enum after downgrade
