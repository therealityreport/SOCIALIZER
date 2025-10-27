"""Create core domain models for MVP

Revision ID: 202410150900
Revises: 202410121200
Create Date: 2024-10-15 09:00:00.000000
"""
from __future__ import annotations

import datetime as dt
from typing import Iterable

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = "202410150900"
down_revision = "202410121200"
branch_labels = None
depends_on = None

THREAD_STATUS_ENUM = ("scheduled", "live", "completed", "archived")


def _create_comment_partitions(months: int = 3) -> None:
    """Pre-create monthly partitions starting from the current month."""
    today = dt.date.today().replace(day=1)

    def month_spans(start: dt.date, count: int) -> Iterable[tuple[dt.date, dt.date]]:
        year = start.year
        month = start.month
        for offset in range(count):
            calc_month = month + offset
            target_year = year + (calc_month - 1) // 12
            target_month = ((calc_month - 1) % 12) + 1
            start_date = dt.date(target_year, target_month, 1)
            if target_month == 12:
                end_date = dt.date(target_year + 1, 1, 1)
            else:
                end_date = dt.date(target_year, target_month + 1, 1)
            yield start_date, end_date

    for start_date, end_date in month_spans(today, months):
        partition_name = f"comments_{start_date:%Y_%m}"
        op.execute(
            sa.text(
                f"""
                CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF comments
                FOR VALUES FROM ('{start_date.isoformat()}'::DATE) TO ('{end_date.isoformat()}'::DATE);
                """
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else "postgresql"
    is_sqlite = dialect == "sqlite"

    if not is_sqlite:
        op.execute(
            sa.text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'thread_status') THEN
                        CREATE TYPE thread_status AS ENUM ('scheduled', 'live', 'completed', 'archived');
                    END IF;
                END
                $$;
                """
            )
        )
        thread_status = postgresql.ENUM(*THREAD_STATUS_ENUM, name="thread_status", create_type=False)
    else:
        thread_status = sa.Enum(*THREAD_STATUS_ENUM, name="thread_status")

    op.create_table(
        "threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reddit_id", sa.String(length=16), nullable=False),
        sa.Column("subreddit", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("air_time_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", thread_status, nullable=False, server_default="scheduled"),
        sa.Column("total_comments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("synopsis", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_threads_reddit_id", "threads", ["reddit_id"], unique=True)
    op.create_index("ix_threads_status", "threads", ["status"])
    op.create_index("ix_threads_air_time_utc", "threads", ["air_time_utc"])

    op.create_table(
        "cast_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("show", sa.String(length=120), nullable=False),
        sa.Column("biography", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_cast_members_slug"),
    )
    op.create_index("ix_cast_members_show", "cast_members", ["show"])
    op.create_index("ix_cast_members_is_active", "cast_members", ["is_active"])

    op.create_table(
        "cast_member_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cast_member_id", sa.Integer(), sa.ForeignKey("cast_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("cast_member_id", "alias", name="uq_cast_member_alias"),
    )
    op.create_index("ix_cast_alias_alias", "cast_member_aliases", ["alias"])

    op.create_table(
        "comments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reddit_id", sa.String(length=16), nullable=False),
        sa.Column("author_hash", sa.String(length=64), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_id", sa.String(length=16), nullable=True),
        sa.Column("reply_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("time_window", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", "created_at", name="pk_comments"),
        sa.UniqueConstraint("reddit_id", "created_at", name="uq_comments_reddit_id_created_at"),
        postgresql_partition_by="RANGE (created_at)",
    )
    op.create_index("ix_comments_thread_id", "comments", ["thread_id"])
    op.create_index("ix_comments_created_utc", "comments", ["created_utc"])
    op.create_index("ix_comments_time_window", "comments", ["time_window"])

    op.create_table(
        "mentions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("comment_id", sa.BigInteger(), nullable=False),
        sa.Column("comment_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cast_member_id", sa.Integer(), sa.ForeignKey("cast_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sentiment_label", sa.String(length=16), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("is_sarcastic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_toxic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("method", sa.String(length=32), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["comment_id", "comment_created_at"],
            ["comments.id", "comments.created_at"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_mentions_comment_id", "mentions", ["comment_id"])
    op.create_index("ix_mentions_cast_member_id", "mentions", ["cast_member_id"])
    op.create_index("ix_mentions_sentiment_label", "mentions", ["sentiment_label"])
    op.create_index("ix_mentions_cast_sentiment", "mentions", ["cast_member_id", "sentiment_label"])

    op.create_table(
        "aggregates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cast_member_id", sa.Integer(), sa.ForeignKey("cast_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("time_window", sa.String(length=32), nullable=False),
        sa.Column("net_sentiment", sa.Float(), nullable=True),
        sa.Column("ci_lower", sa.Float(), nullable=True),
        sa.Column("ci_upper", sa.Float(), nullable=True),
        sa.Column("positive_pct", sa.Float(), nullable=True),
        sa.Column("neutral_pct", sa.Float(), nullable=True),
        sa.Column("negative_pct", sa.Float(), nullable=True),
        sa.Column("agreement_score", sa.Float(), nullable=True),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_aggregates_thread_cast", "aggregates", ["thread_id", "cast_member_id"])
    op.create_index("ix_aggregates_time_window", "aggregates", ["time_window"])

    # Seed initial cast roster (Bravo - Real Housewives of Salt Lake City)
    op.bulk_insert(
        table(
            "cast_members",
            column("id", sa.Integer()),
            column("slug", sa.String(120)),
            column("full_name", sa.String(120)),
            column("display_name", sa.String(120)),
            column("show", sa.String(120)),
            column("biography", sa.Text()),
            column("is_active", sa.Boolean()),
        ),
        [
            {
                "id": 1,
                "slug": "lisa-barlow",
                "full_name": "Lisa Barlow",
                "display_name": "Lisa",
                "show": "The Real Housewives of Salt Lake City",
                "biography": "Entrepreneur and tequila brand founder.",
                "is_active": True,
            },
            {
                "id": 2,
                "slug": "heather-gay",
                "full_name": "Heather Gay",
                "display_name": "Heather",
                "show": "The Real Housewives of Salt Lake City",
                "biography": "Beauty Lab + Laser co-founder.",
                "is_active": True,
            },
            {
                "id": 3,
                "slug": "whitney-rose",
                "full_name": "Whitney Rose",
                "display_name": "Whitney",
                "show": "The Real Housewives of Salt Lake City",
                "biography": "Wild Rose Beauty founder.",
                "is_active": True,
            },
            {
                "id": 4,
                "slug": "meredith-marks",
                "full_name": "Meredith Marks",
                "display_name": "Meredith",
                "show": "The Real Housewives of Salt Lake City",
                "biography": "Luxury jewelry designer.",
                "is_active": True,
            },
            {
                "id": 5,
                "slug": "mary-cosby",
                "full_name": "Mary Cosby",
                "display_name": "Mary",
                "show": "The Real Housewives of Salt Lake City",
                "biography": "Pentecostal First Lady.",
                "is_active": True,
            },
            {
                "id": 6,
                "slug": "britani",
                "full_name": "Britani",
                "display_name": "Britani",
                "show": "The Real Housewives of Salt Lake City",
                "biography": "Season 6 arrival shaking up the group dynamics.",
                "is_active": True,
            },
        ],
    )

    op.bulk_insert(
        table(
            "cast_member_aliases",
            column("cast_member_id", sa.Integer()),
            column("alias", sa.String(120)),
        ),
        [
            {"cast_member_id": 1, "alias": "LisaBarlow"},
            {"cast_member_id": 1, "alias": "Tequila Lisa"},
            {"cast_member_id": 2, "alias": "Bad Weather"},
            {"cast_member_id": 2, "alias": "HeatherGay"},
            {"cast_member_id": 3, "alias": "Whit"},
            {"cast_member_id": 3, "alias": "Whitney Wild Rose"},
            {"cast_member_id": 4, "alias": "MeredithMarks"},
            {"cast_member_id": 4, "alias": "Mer"},
            {"cast_member_id": 5, "alias": "MaryM"},
            {"cast_member_id": 5, "alias": "First Lady"},
            {"cast_member_id": 6, "alias": "Britani"},
            {"cast_member_id": 6, "alias": "Brittnay"},
            {"cast_member_id": 6, "alias": "Britney"},
            {"cast_member_id": 6, "alias": "Britain"},
        ],
    )

    if not is_sqlite:
        op.execute(
            sa.text(
                """
                SELECT setval(
                    pg_get_serial_sequence('cast_members', 'id'),
                    GREATEST((SELECT MAX(id) FROM cast_members), 1)
                )
                """
            )
        )

    if not is_sqlite:
        _create_comment_partitions(months=4)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else "postgresql"
    is_sqlite = dialect == "sqlite"
    op.drop_table("aggregates")
    op.drop_index("ix_mentions_cast_sentiment", table_name="mentions")
    op.drop_index("ix_mentions_sentiment_label", table_name="mentions")
    op.drop_index("ix_mentions_cast_member_id", table_name="mentions")
    op.drop_index("ix_mentions_comment_id", table_name="mentions")
    op.drop_table("mentions")
    op.drop_index("ix_comments_time_window", table_name="comments")
    op.drop_index("ix_comments_created_utc", table_name="comments")
    op.drop_index("ix_comments_thread_id", table_name="comments")
    op.drop_table("comments")
    op.drop_index("ix_cast_alias_alias", table_name="cast_member_aliases")
    op.drop_table("cast_member_aliases")
    op.drop_index("ix_cast_members_is_active", table_name="cast_members")
    op.drop_index("ix_cast_members_show", table_name="cast_members")
    op.drop_table("cast_members")
    op.drop_index("ix_threads_air_time_utc", table_name="threads")
    op.drop_index("ix_threads_status", table_name="threads")
    op.drop_index("ix_threads_reddit_id", table_name="threads")
    op.drop_table("threads")
    if not is_sqlite:
        thread_status = postgresql.ENUM(*THREAD_STATUS_ENUM, name="thread_status", create_type=False)
        thread_status.drop(op.get_bind(), checkfirst=True)
