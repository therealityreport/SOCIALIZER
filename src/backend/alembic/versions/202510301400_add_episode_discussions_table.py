"""add episode_discussions table

Revision ID: 202510301400
Revises: 202512011230
Create Date: 2025-10-30 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202510301400'
down_revision: Union[str, None] = '202512011230'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create platform enum
    platform_enum = postgresql.ENUM(
        'reddit', 'instagram', 'tiktok', 'x', 'youtube', 'other',
        name='platform_enum',
        create_type=False
    )
    platform_enum.create(op.get_bind(), checkfirst=True)

    # Create discussion_window enum
    discussion_window_enum = postgresql.ENUM(
        'LIVE', 'DAY_OF', 'AFTER',
        name='discussion_window_enum',
        create_type=False
    )
    discussion_window_enum.create(op.get_bind(), checkfirst=True)

    # Create discussion_status enum
    discussion_status_enum = postgresql.ENUM(
        'DRAFT', 'QUEUED', 'RUNNING', 'COMPLETE', 'FAILED',
        name='discussion_status_enum',
        create_type=False
    )
    discussion_status_enum.create(op.get_bind(), checkfirst=True)

    # Create episode_discussions table
    op.create_table(
        'episode_discussions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('show', sa.String(length=120), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('episode', sa.Integer(), nullable=False),
        sa.Column('date_utc', sa.DateTime(timezone=True), nullable=False),
        sa.Column('platform', platform_enum, nullable=False),
        sa.Column('links', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('transcript_ref', sa.String(length=500), nullable=False),
        sa.Column('transcript_text', sa.Text(), nullable=True),
        sa.Column('window', discussion_window_enum, nullable=False),
        sa.Column('cast_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', discussion_status_enum, nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('beats', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('cast_sentiment_baseline', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('analysis_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('analysis_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('total_comments_ingested', sa.Integer(), nullable=False),
        sa.Column('total_mentions_created', sa.Integer(), nullable=False),
        sa.Column('last_ingested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_episode_discussions_show', 'episode_discussions', ['show'], unique=False)
    op.create_index('ix_episode_discussions_status', 'episode_discussions', ['status'], unique=False)
    op.create_index('ix_episode_discussions_date', 'episode_discussions', ['date_utc'], unique=False)
    op.create_index('ix_episode_discussions_season_episode', 'episode_discussions', ['show', 'season', 'episode'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_episode_discussions_season_episode', table_name='episode_discussions')
    op.drop_index('ix_episode_discussions_date', table_name='episode_discussions')
    op.drop_index('ix_episode_discussions_status', table_name='episode_discussions')
    op.drop_index('ix_episode_discussions_show', table_name='episode_discussions')

    # Drop table
    op.drop_table('episode_discussions')

    # Drop enums
    discussion_status_enum = postgresql.ENUM(name='discussion_status_enum')
    discussion_status_enum.drop(op.get_bind(), checkfirst=True)

    discussion_window_enum = postgresql.ENUM(name='discussion_window_enum')
    discussion_window_enum.drop(op.get_bind(), checkfirst=True)

    platform_enum = postgresql.ENUM(name='platform_enum')
    platform_enum.drop(op.get_bind(), checkfirst=True)
