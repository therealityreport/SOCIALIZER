"""Normalize show names

Revision ID: 202511071210
Revises: 202511071200
Create Date: 2025-11-07 12:10:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202511071210"
down_revision = "202511071200"
branch_labels = None
depends_on = None


_RENAMES: dict[str, str] = {
    "RHOSLC": "The Real Housewives of Salt Lake City",
    "rhoslc": "The Real Housewives of Salt Lake City",
    "Real Housewives of Salt Lake City": "The Real Housewives of Salt Lake City",
}


def upgrade() -> None:
    cast_members = sa.table(
        "cast_members",
        sa.column("show", sa.String()),
    )
    for old, new in _RENAMES.items():
        op.execute(
            cast_members.update().where(cast_members.c.show == old).values(show=new)
        )


def downgrade() -> None:
    # No-op: we cannot safely determine the original casing/alias after normalization
    pass

