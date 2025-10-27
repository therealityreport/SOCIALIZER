"""Create alert rule and event tables

Revision ID: 202411020945
Revises: 202411020930
Create Date: 2024-11-02 09:45:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202411020945"
down_revision = "202411020930"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else "postgresql"
    is_sqlite = dialect == "sqlite"
    json_default = sa.text("'[]'::json") if not is_sqlite else sa.text("'[]'")

    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("threads.id", ondelete="CASCADE"), nullable=True),
        sa.Column("cast_member_id", sa.Integer(), sa.ForeignKey("cast_members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rule_type", sa.String(length=32), nullable=False),
        sa.Column("condition", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("channels", sa.JSON(), nullable=False, server_default=json_default if not is_sqlite else None),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_alert_rules_thread_active", "alert_rules", ["thread_id", "is_active"])
    if not is_sqlite:
        op.alter_column("alert_rules", "is_active", server_default=None)
        op.alter_column("alert_rules", "channels", server_default=None)

    op.create_table(
        "alert_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_rule_id", sa.Integer(), sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cast_member_id", sa.Integer(), sa.ForeignKey("cast_members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("delivered_channels", sa.JSON(), nullable=False, server_default=json_default if not is_sqlite else None),
    )
    op.create_index("ix_alert_events_rule", "alert_events", ["alert_rule_id"])
    op.create_index("ix_alert_events_triggered_at", "alert_events", ["triggered_at"])
    if not is_sqlite:
        op.alter_column("alert_events", "delivered_channels", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_alert_events_triggered_at", table_name="alert_events")
    op.drop_index("ix_alert_events_rule", table_name="alert_events")
    op.drop_table("alert_events")

    op.drop_index("ix_alert_rules_thread_active", table_name="alert_rules")
    op.drop_table("alert_rules")
