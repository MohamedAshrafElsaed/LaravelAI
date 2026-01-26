"""Add summary_data field to conversations table.

Revision ID: add_conv_summary_data
Revises: [SET_TO_YOUR_LATEST_REVISION]
Create Date: 2025-01-26
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers - UPDATE THESE
revision = 'b7a52b4fdc56'
down_revision = "34e197305dbd"  # <-- SET THIS TO YOUR LATEST REVISION ID
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add summary_data column to conversations table."""
    op.add_column(
        'conversations',
        sa.Column('summary_data', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Remove summary_data column."""
    op.drop_column('conversations', 'summary_data')