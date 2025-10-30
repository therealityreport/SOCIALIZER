"""add_provider_costs_table

Revision ID: 202512011230
Revises: 202512011200
Create Date: 2025-12-01 12:30:00.000000

Creates provider_costs table for tracking LLM API usage and costs.
Also adds provider_selection_log table for tracking automated provider switches.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '202512011230'
down_revision = '202512011200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create provider_costs table
    op.create_table(
        'provider_costs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('tokens_consumed', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=False, server_default='0'),
        sa.Column('comments_analyzed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create indexes
    op.create_index('idx_provider_costs_provider', 'provider_costs', ['provider'])
    op.create_index('idx_provider_costs_date', 'provider_costs', ['date'])
    op.create_index('idx_provider_costs_provider_date', 'provider_costs', ['provider', 'date'], unique=True)

    # Create provider_selection_log table
    op.create_table(
        'provider_selection_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('model', sa.String(64), nullable=False),
        sa.Column('provider_score', sa.Float(), nullable=False),
        sa.Column('mean_confidence', sa.Float(), nullable=True),
        sa.Column('cost_per_1k_tokens', sa.Float(), nullable=True),
        sa.Column('reason', sa.String(128), nullable=False),
        sa.Column('fallback_provider', sa.String(32), nullable=True),
        sa.Column('selected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create index
    op.create_index('idx_provider_selection_log_selected_at', 'provider_selection_log', ['selected_at'])

    # Create drift_checks table
    op.create_table(
        'drift_checks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('check_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('primary_provider', sa.String(32), nullable=False),
        sa.Column('secondary_provider', sa.String(32), nullable=False),
        sa.Column('samples_checked', sa.Integer(), nullable=False),
        sa.Column('agreement_score', sa.Float(), nullable=False),
        sa.Column('sentiment_agreement', sa.Float(), nullable=True),
        sa.Column('sarcasm_agreement', sa.Float(), nullable=True),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('alert_sent', sa.Boolean(), server_default='false', nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create index
    op.create_index('idx_drift_checks_check_date', 'drift_checks', ['check_date'])
    op.create_index('idx_drift_checks_status', 'drift_checks', ['status'])


def downgrade() -> None:
    # Drop tables
    op.drop_index('idx_drift_checks_status', 'drift_checks')
    op.drop_index('idx_drift_checks_check_date', 'drift_checks')
    op.drop_table('drift_checks')

    op.drop_index('idx_provider_selection_log_selected_at', 'provider_selection_log')
    op.drop_table('provider_selection_log')

    op.drop_index('idx_provider_costs_provider_date', 'provider_costs')
    op.drop_index('idx_provider_costs_date', 'provider_costs')
    op.drop_index('idx_provider_costs_provider', 'provider_costs')
    op.drop_table('provider_costs')
