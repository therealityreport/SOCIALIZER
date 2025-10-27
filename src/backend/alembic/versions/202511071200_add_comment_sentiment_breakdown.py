"""Add sentiment breakdown column to comments

Revision ID: 202511071200
Revises: 202510211030
Create Date: 2025-11-07 12:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "202511071200"
down_revision = "202510211030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind and bind.dialect.name == "sqlite":
        op.add_column("comments", sa.Column("sentiment_breakdown", sa.Text(), nullable=True))
    else:
        op.add_column(
            "comments",
            sa.Column("sentiment_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("comments", "sentiment_breakdown")
