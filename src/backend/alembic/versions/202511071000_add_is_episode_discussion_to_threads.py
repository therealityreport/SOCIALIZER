"""add is_episode_discussion to threads

Revision ID: 202511071000
Revises: 202512011230
Create Date: 2025-11-07 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '202511071000'
down_revision = '202510301400'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_episode_discussion column to threads table with default True
    op.add_column('threads', sa.Column('is_episode_discussion', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    # Remove is_episode_discussion column
    op.drop_column('threads', 'is_episode_discussion')
