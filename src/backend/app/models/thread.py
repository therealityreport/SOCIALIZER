from __future__ import annotations

import enum
import datetime as dt
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.aggregate import Aggregate
    from app.models.alert import AlertEvent, AlertRule
    from app.models.comment import Comment


class ThreadStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Thread(TimestampMixin, Base):
    __tablename__ = "threads"
    __table_args__ = (
        Index("ix_threads_reddit_id", "reddit_id", unique=True),
        Index("ix_threads_status", "status"),
        Index("ix_threads_air_time_utc", "air_time_utc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reddit_id: Mapped[str] = mapped_column(String(16), nullable=False)
    subreddit: Mapped[Optional[str]] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    air_time_utc: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    created_utc: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ThreadStatus] = mapped_column(
        Enum(
            ThreadStatus,
            name="thread_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=ThreadStatus.SCHEDULED,
        nullable=False,
    )
    total_comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    synopsis: Mapped[Optional[str]] = mapped_column(Text)
    is_episode_discussion: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_polled_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    latest_comment_utc: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    comments: Mapped[list["Comment"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    aggregates: Mapped[list["Aggregate"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    alert_rules: Mapped[list["AlertRule"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    alert_events: Mapped[list["AlertEvent"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Thread id={self.id} reddit_id={self.reddit_id!r} status={self.status}>"
