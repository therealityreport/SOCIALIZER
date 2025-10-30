"""add_llm_results_and_provider_fields

Revision ID: 202512011200
Revises: 202511301200
Create Date: 2025-12-01 12:00:00.000000

Adds fields for multi-LLM provider benchmarking:
- llm_results JSONB: Stores results from all providers (OpenAI, Anthropic, Gemini)
- provider_preferred TEXT: Indicates which provider's result was chosen as primary
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '202512011200'
down_revision = '202511301200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to mentions table
    op.add_column('mentions', sa.Column('llm_results', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('mentions', sa.Column('provider_preferred', sa.String(32), nullable=True))

    # Create index on provider_preferred for filtering
    op.create_index('idx_mentions_provider_preferred', 'mentions', ['provider_preferred'])

    # Create GIN index for JSONB field
    op.execute("CREATE INDEX idx_mentions_llm_results_gin ON mentions USING gin (llm_results)")


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_mentions_llm_results_gin', 'mentions')
    op.drop_index('idx_mentions_provider_preferred', 'mentions')

    # Drop columns
    op.drop_column('mentions', 'provider_preferred')
    op.drop_column('mentions', 'llm_results')
