"""add_llm_signal_fields

Revision ID: 202511301200
Revises: 202411020945
Create Date: 2025-11-30 12:00:00.000000

Adds LLM-driven sentiment fields and computed signal fields to mentions table:
- primary_sentiment enum (POSITIVE, NEUTRAL, NEGATIVE)
- secondary_attitude enum (Admiration/Support, Shady/Humor, etc.)
- emotions JSONB array
- sarcasm_score, sarcasm_label, sarcasm_evidence
- signals JSONB (emoji, media, intensity metrics)
- engagement JSONB (upvotes, replies, awards, velocity)
- spans JSONB for entity linking
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '202511301200'
down_revision = '202411020945'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    primary_sentiment_enum = postgresql.ENUM(
        'POSITIVE', 'NEUTRAL', 'NEGATIVE',
        name='primary_sentiment_enum',
        create_type=False
    )

    secondary_attitude_enum = postgresql.ENUM(
        'Admiration/Support',
        'Shady/Humor',
        'Analytical',
        'Annoyed',
        'Hatred/Disgust',
        'Sadness/Sympathy/Distress',
        name='secondary_attitude_enum',
        create_type=False
    )

    # Create enum types
    op.execute("CREATE TYPE primary_sentiment_enum AS ENUM ('POSITIVE', 'NEUTRAL', 'NEGATIVE')")
    op.execute("""
        CREATE TYPE secondary_attitude_enum AS ENUM (
            'Admiration/Support',
            'Shady/Humor',
            'Analytical',
            'Annoyed',
            'Hatred/Disgust',
            'Sadness/Sympathy/Distress'
        )
    """)

    # Add new columns to mentions table
    op.add_column('mentions', sa.Column('primary_sentiment', primary_sentiment_enum, nullable=True))
    op.add_column('mentions', sa.Column('secondary_attitude', secondary_attitude_enum, nullable=True))
    op.add_column('mentions', sa.Column('emotions', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('mentions', sa.Column('sarcasm_score', sa.Float(), nullable=True))
    op.add_column('mentions', sa.Column('sarcasm_label', sa.String(32), nullable=True))
    op.add_column('mentions', sa.Column('sarcasm_evidence', sa.Text(), nullable=True))
    op.add_column('mentions', sa.Column('signals', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('mentions', sa.Column('engagement', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('mentions', sa.Column('spans', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('mentions', sa.Column('needs_recompute', sa.Boolean(), server_default='false', nullable=False))

    # Create indexes for new fields
    op.create_index('ix_mentions_primary_sentiment', 'mentions', ['primary_sentiment'])
    op.create_index('ix_mentions_secondary_attitude', 'mentions', ['secondary_attitude'])

    # Create GIN indexes for JSONB fields
    op.execute("CREATE INDEX ix_mentions_signals_gin ON mentions USING gin (signals)")
    op.execute("CREATE INDEX ix_mentions_emotions_gin ON mentions USING gin (emotions)")
    op.execute("CREATE INDEX ix_mentions_engagement_gin ON mentions USING gin (engagement)")


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_mentions_engagement_gin', 'mentions')
    op.drop_index('ix_mentions_emotions_gin', 'mentions')
    op.drop_index('ix_mentions_signals_gin', 'mentions')
    op.drop_index('ix_mentions_secondary_attitude', 'mentions')
    op.drop_index('ix_mentions_primary_sentiment', 'mentions')

    # Drop columns
    op.drop_column('mentions', 'needs_recompute')
    op.drop_column('mentions', 'spans')
    op.drop_column('mentions', 'engagement')
    op.drop_column('mentions', 'signals')
    op.drop_column('mentions', 'sarcasm_evidence')
    op.drop_column('mentions', 'sarcasm_label')
    op.drop_column('mentions', 'sarcasm_score')
    op.drop_column('mentions', 'emotions')
    op.drop_column('mentions', 'secondary_attitude')
    op.drop_column('mentions', 'primary_sentiment')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS secondary_attitude_enum")
    op.execute("DROP TYPE IF EXISTS primary_sentiment_enum")
