"""Episode Discussion Model

Represents an episode-level discussion with transcript-based analysis.
"""
from __future__ import annotations

import enum
import datetime as dt
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.mention import Mention


class Platform(str, enum.Enum):
    """Social media platforms"""
    REDDIT = "reddit"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    X = "x"
    YOUTUBE = "youtube"
    OTHER = "other"


class DiscussionWindow(str, enum.Enum):
    """Discussion time window relative to episode air date"""
    LIVE = "LIVE"  # During live airing
    DAY_OF = "DAY_OF"  # Day of airing (default)
    AFTER = "AFTER"  # After airing


class DiscussionStatus(str, enum.Enum):
    """Episode discussion processing status"""
    DRAFT = "DRAFT"  # Saved but not analyzed
    QUEUED = "QUEUED"  # Queued for analysis
    RUNNING = "RUNNING"  # Analysis in progress
    COMPLETE = "COMPLETE"  # Analysis complete
    FAILED = "FAILED"  # Analysis failed


class EpisodeDiscussion(TimestampMixin, Base):
    """Episode discussion with transcript and social media comments"""

    __tablename__ = "episode_discussions"
    __table_args__ = (
        Index("ix_episode_discussions_show", "show"),
        Index("ix_episode_discussions_status", "status"),
        Index("ix_episode_discussions_date", "date_utc"),
        Index("ix_episode_discussions_season_episode", "show", "season", "episode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Episode metadata
    show: Mapped[str] = mapped_column(String(120), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    episode: Mapped[int] = mapped_column(Integer, nullable=False)
    date_utc: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Platform and links
    platform: Mapped[Platform] = mapped_column(
        Enum(
            Platform,
            name="platform_enum",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    links: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    # Transcript
    transcript_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    transcript_text: Mapped[Optional[str]] = mapped_column(Text)  # Cached text content

    # Discussion window
    window: Mapped[DiscussionWindow] = mapped_column(
        Enum(
            DiscussionWindow,
            name="discussion_window_enum",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=DiscussionWindow.DAY_OF,
        nullable=False,
    )

    # Cast roster (stored as slugs)
    cast_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    # Processing status
    status: Mapped[DiscussionStatus] = mapped_column(
        Enum(
            DiscussionStatus,
            name="discussion_status_enum",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=DiscussionStatus.DRAFT,
        nullable=False,
    )

    # LLM analysis results
    summary: Mapped[Optional[str]] = mapped_column(Text)  # Episode summary from transcript
    beats: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)  # Key moments/plot beats
    cast_sentiment_baseline: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)  # Initial sentiment per cast

    # Processing metadata
    analysis_started_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    analysis_completed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Comment ingestion stats
    total_comments_ingested: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_mentions_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_ingested_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<EpisodeDiscussion id={self.id} show={self.show!r} S{self.season}E{self.episode} status={self.status}>"
