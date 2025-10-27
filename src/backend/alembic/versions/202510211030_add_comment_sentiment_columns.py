"""Add sentiment and toxicity fields to comments

Revision ID: 202510211030
Revises: f3f31799e504
Create Date: 2025-10-21 10:30:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202510211030"
down_revision = "f3f31799e504"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("comments", sa.Column("sentiment_label", sa.String(length=16), nullable=True))
    op.add_column("comments", sa.Column("sentiment_score", sa.Float(), nullable=True))
    op.add_column("comments", sa.Column("sarcasm_confidence", sa.Float(), nullable=True))
    op.add_column(
        "comments",
        sa.Column("is_sarcastic", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("comments", sa.Column("toxicity_confidence", sa.Float(), nullable=True))
    op.add_column(
        "comments",
        sa.Column("is_toxic", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("comments", sa.Column("ml_model_version", sa.String(length=32), nullable=True))

    # Drop server defaults now that existing rows are backfilled (or nonexistent in a fresh DB)
    op.alter_column("comments", "is_sarcastic", server_default=None)
    op.alter_column("comments", "is_toxic", server_default=None)


def downgrade() -> None:
    op.drop_column("comments", "ml_model_version")
    op.drop_column("comments", "is_toxic")
    op.drop_column("comments", "toxicity_confidence")
    op.drop_column("comments", "is_sarcastic")
    op.drop_column("comments", "sarcasm_confidence")
    op.drop_column("comments", "sentiment_score")
    op.drop_column("comments", "sentiment_label")
