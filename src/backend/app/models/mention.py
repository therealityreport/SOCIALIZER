from __future__ import annotations

import datetime as dt
import enum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.cast import CastMember
    from app.models.comment import Comment


class PrimarySentiment(str, enum.Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class SecondaryAttitude(str, enum.Enum):
    ADMIRATION_SUPPORT = "Admiration/Support"
    SHADY_HUMOR = "Shady/Humor"
    ANALYTICAL = "Analytical"
    ANNOYED = "Annoyed"
    HATRED_DISGUST = "Hatred/Disgust"
    SADNESS_SYMPATHY = "Sadness/Sympathy/Distress"


class Mention(TimestampMixin, Base):
    __tablename__ = "mentions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["comment_id", "comment_created_at"],
            ["comments.id", "comments.created_at"],
            ondelete="CASCADE",
        ),
        Index("ix_mentions_comment_id", "comment_id"),
        Index("ix_mentions_cast_member_id", "cast_member_id"),
        Index("ix_mentions_sentiment_label", "sentiment_label"),
        Index("ix_mentions_cast_sentiment", "cast_member_id", "sentiment_label"),
    )

    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True, primary_key=True)
    comment_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    comment_created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cast_member_id: Mapped[int] = mapped_column(ForeignKey("cast_members.id", ondelete="CASCADE"), nullable=False)
    sentiment_label: Mapped[str] = mapped_column(String(16), nullable=False)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    is_sarcastic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_toxic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    weight: Mapped[Optional[float]] = mapped_column(Float)
    method: Mapped[Optional[str]] = mapped_column(String(32))
    quote: Mapped[Optional[str]] = mapped_column(Text)

    # New LLM-driven fields
    primary_sentiment: Mapped[Optional[PrimarySentiment]] = mapped_column(Enum(PrimarySentiment), nullable=True)
    secondary_attitude: Mapped[Optional[SecondaryAttitude]] = mapped_column(Enum(SecondaryAttitude), nullable=True)
    emotions: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    sarcasm_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sarcasm_label: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    sarcasm_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Computed signal fields
    signals: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    engagement: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    spans: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    needs_recompute: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Multi-LLM provider benchmarking fields
    llm_results: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    provider_preferred: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    comment: Mapped["Comment"] = relationship(back_populates="mentions", lazy="joined")
    cast_member: Mapped["CastMember"] = relationship(back_populates="mentions", lazy="joined")

    def __repr__(self) -> str:
        return f"<Mention id={self.id} cast_member_id={self.cast_member_id}>"
