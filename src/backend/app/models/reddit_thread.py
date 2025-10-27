from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin


class RedditThread(TimestampMixin, Base):
    __tablename__ = "reddit_threads"
    __table_args__ = (
        Index("ix_reddit_threads_subreddit", "subreddit"),
        Index("ix_reddit_threads_external_id", "external_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(16), nullable=False)
    subreddit: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(80))
    flair: Mapped[Optional[str]] = mapped_column(String(120))
    score: Mapped[int] = mapped_column(Integer, default=0)
    num_comments: Mapped[int] = mapped_column(Integer, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_json: Mapped[Optional[str]] = mapped_column(Text)
