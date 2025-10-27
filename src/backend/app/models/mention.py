from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.cast import CastMember
    from app.models.comment import Comment


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

    comment: Mapped["Comment"] = relationship(back_populates="mentions", lazy="joined")
    cast_member: Mapped["CastMember"] = relationship(back_populates="mentions", lazy="joined")

    def __repr__(self) -> str:
        return f"<Mention id={self.id} cast_member_id={self.cast_member_id}>"
