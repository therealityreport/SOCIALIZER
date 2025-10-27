from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, PrimaryKeyConstraint, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.mention import Mention
    from app.models.thread import Thread


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at", name="pk_comments"),
        UniqueConstraint("reddit_id", "created_at", name="uq_comments_reddit_id_created_at"),
        Index("ix_comments_thread_id", "thread_id"),
        Index("ix_comments_created_utc", "created_utc"),
        Index("ix_comments_time_window", "time_window"),
        {
            "postgresql_partition_by": "RANGE (created_at)",
        },
    )

    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True, primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    reddit_id: Mapped[str] = mapped_column(String(16), nullable=False)
    author_hash: Mapped[Optional[str]] = mapped_column(String(64))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_utc: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(String(16))
    reply_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_window: Mapped[Optional[str]] = mapped_column(String(20))
    sentiment_label: Mapped[Optional[str]] = mapped_column(String(16))
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float)
    sentiment_breakdown: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    sarcasm_confidence: Mapped[Optional[float]] = mapped_column(Float)
    is_sarcastic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    toxicity_confidence: Mapped[Optional[float]] = mapped_column(Float)
    is_toxic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ml_model_version: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        primary_key=True,
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    thread: Mapped["Thread"] = relationship(back_populates="comments")
    mentions: Mapped[list["Mention"]] = relationship(
        back_populates="comment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Comment id={self.id} thread_id={self.thread_id}>"
