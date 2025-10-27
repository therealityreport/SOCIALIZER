"""Add polling metadata fields to threads

Revision ID: 202411020930
Revises: 202410150900
Create Date: 2024-11-02 09:30:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202411020930"
down_revision = "202410150900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else "postgresql"
    op.add_column("threads", sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("threads", sa.Column("latest_comment_utc", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "threads",
        sa.Column("poll_interval_seconds", sa.Integer(), nullable=False, server_default=sa.text("60")),
    )
    if dialect != "sqlite":
        op.alter_column("threads", "poll_interval_seconds", server_default=None)


def downgrade() -> None:
    op.drop_column("threads", "poll_interval_seconds")
    op.drop_column("threads", "latest_comment_utc")
    op.drop_column("threads", "last_polled_at")
