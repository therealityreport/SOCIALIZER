"""Create core tables

Revision ID: 202410121200
Revises: 
Create Date: 2024-10-12 12:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202410121200"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "reddit_threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=16), nullable=False),
        sa.Column("subreddit", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("author", sa.String(length=80), nullable=True),
        sa.Column("flair", sa.String(length=120), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("num_comments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_reddit_threads_subreddit", "reddit_threads", ["subreddit"], unique=False)
    op.create_index("ix_reddit_threads_external_id", "reddit_threads", ["external_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_reddit_threads_external_id", table_name="reddit_threads")
    op.drop_index("ix_reddit_threads_subreddit", table_name="reddit_threads")
    op.drop_table("reddit_threads")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
