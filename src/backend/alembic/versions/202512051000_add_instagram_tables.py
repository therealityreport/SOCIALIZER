"""add_instagram_tables

Revision ID: 202512051000
Revises: 202512011230
Create Date: 2025-12-05 10:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '202512051000'
down_revision = '202512011230'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'instagram_profiles',
        sa.Column('username', sa.String(length=128), nullable=False),
        sa.Column('full_name', sa.String(length=300), nullable=True),
        sa.Column('biography', sa.Text(), nullable=True),
        sa.Column('followers_count', sa.Integer(), nullable=True),
        sa.Column('follows_count', sa.Integer(), nullable=True),
        sa.Column('posts_count', sa.Integer(), nullable=True),
        sa.Column('external_url', sa.String(length=500), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_private', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('about_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), server_onupdate=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('username'),
    )

    op.create_table(
        'instagram_posts',
        sa.Column('shortcode', sa.String(length=64), nullable=False),
        sa.Column('username', sa.String(length=128), nullable=False),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('media_type', sa.String(length=32), nullable=True),
        sa.Column('product_type', sa.String(length=32), nullable=True),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('comments_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('likes_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('raw_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('inserted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), server_onupdate=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['username'], ['instagram_profiles.username'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('shortcode'),
    )
    op.create_index('ix_instagram_posts_username', 'instagram_posts', ['username'])
    op.create_index('ix_instagram_posts_posted_at', 'instagram_posts', ['posted_at'])

    op.create_table(
        'instagram_post_hashtags',
        sa.Column('post_shortcode', sa.String(length=64), nullable=False),
        sa.Column('tag', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['post_shortcode'], ['instagram_posts.shortcode'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('post_shortcode', 'tag'),
    )
    op.create_index('ix_instagram_post_hashtags_tag', 'instagram_post_hashtags', ['tag'])

    op.create_table(
        'instagram_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('actor_run_id', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('input_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('stats_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('instagram_runs')
    op.drop_index('ix_instagram_post_hashtags_tag', table_name='instagram_post_hashtags')
    op.drop_table('instagram_post_hashtags')
    op.drop_index('ix_instagram_posts_posted_at', table_name='instagram_posts')
    op.drop_index('ix_instagram_posts_username', table_name='instagram_posts')
    op.drop_table('instagram_posts')
    op.drop_table('instagram_profiles')
