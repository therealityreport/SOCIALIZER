"""Episode Discussion Schemas"""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.episode_discussion import DiscussionStatus, DiscussionWindow, Platform


class EpisodeDiscussionBase(BaseModel):
    """Base schema for episode discussions"""
    show: str = Field(..., min_length=1, max_length=120, description="Show name")
    season: int = Field(..., ge=1, description="Season number")
    episode: int = Field(..., ge=1, description="Episode number")
    date_utc: dt.datetime = Field(..., description="Episode air date (UTC)")
    platform: Platform = Field(..., description="Primary social media platform")
    links: list[str] = Field(default_factory=list, description="Links to discussion posts")
    transcript_ref: str = Field(..., min_length=1, max_length=500, description="Path to transcript file")
    window: DiscussionWindow = Field(default=DiscussionWindow.DAY_OF, description="Discussion time window")
    cast_ids: list[str] = Field(default_factory=list, description="Cast member slugs to analyze")


class EpisodeDiscussionCreate(EpisodeDiscussionBase):
    """Schema for creating an episode discussion"""
    transcript_text: Optional[str] = Field(default=None, description="Raw transcript text (optional)")


class EpisodeDiscussionUpdate(BaseModel):
    """Schema for updating an episode discussion"""
    show: Optional[str] = Field(default=None, max_length=120)
    season: Optional[int] = Field(default=None, ge=1)
    episode: Optional[int] = Field(default=None, ge=1)
    date_utc: Optional[dt.datetime] = None
    platform: Optional[Platform] = None
    links: Optional[list[str]] = None
    transcript_ref: Optional[str] = Field(default=None, max_length=500)
    transcript_text: Optional[str] = None
    window: Optional[DiscussionWindow] = None
    cast_ids: Optional[list[str]] = None
    status: Optional[DiscussionStatus] = None


class EpisodeDiscussionRead(EpisodeDiscussionBase):
    """Schema for reading an episode discussion"""
    id: int
    status: DiscussionStatus
    summary: Optional[str] = None
    beats: Optional[dict[str, Any]] = None
    cast_sentiment_baseline: Optional[dict[str, Any]] = None
    analysis_started_at: Optional[dt.datetime] = None
    analysis_completed_at: Optional[dt.datetime] = None
    error_message: Optional[str] = None
    total_comments_ingested: int = 0
    total_mentions_created: int = 0
    last_ingested_at: Optional[dt.datetime] = None
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = ConfigDict(from_attributes=True)


class EpisodeDiscussionAnalyzeRequest(BaseModel):
    """Schema for triggering analysis on an episode discussion"""
    force: bool = Field(default=False, description="Force re-analysis even if already complete")


class EpisodeDiscussionAnalyzeResponse(BaseModel):
    """Response for analysis trigger"""
    discussion_id: int
    status: DiscussionStatus
    message: str
