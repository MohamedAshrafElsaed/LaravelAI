"""Convert projectstatus enum to varchar for better compatibility

Revision ID: 004
Revises: 003
Create Date: 2026-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert status column from enum to varchar
    # This avoids PostgreSQL enum complexity and makes migrations easier

    # First, create a temporary column
    op.add_column('projects', sa.Column('status_new', sa.String(20), nullable=True))

    # Copy data, handling both uppercase and lowercase enum values
    op.execute("""
        UPDATE projects
        SET status_new = LOWER(status::text)
    """)

    # Drop the old column
    op.drop_column('projects', 'status')

    # Rename new column to status
    op.alter_column('projects', 'status_new', new_column_name='status')

    # Set default and not null
    op.execute("UPDATE projects SET status = 'pending' WHERE status IS NULL")
    op.alter_column('projects', 'status', nullable=False, server_default='pending')

    # Optionally drop the enum type (comment out if other tables use it)
    # op.execute("DROP TYPE IF EXISTS projectstatus")


def downgrade() -> None:
    # Convert back to enum if needed (simplified - just keeps varchar)
    pass
