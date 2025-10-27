from __future__ import annotations

import datetime as dt
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field


class AggregateMetrics(BaseModel):
    net_sentiment: float | None = Field(default=None)
    ci_lower: float | None = Field(default=None)
    ci_upper: float | None = Field(default=None)
    positive_pct: float | None = Field(default=None)
    neutral_pct: float | None = Field(default=None)
    negative_pct: float | None = Field(default=None)
    agreement_score: float | None = Field(default=None)
    mention_count: int = 0


class CastAnalytics(BaseModel):
    cast_id: int
    cast_slug: str
    full_name: str
    show: str
    share_of_voice: float = 0.0
    overall: AggregateMetrics | None = None
    time_windows: Mapping[str, AggregateMetrics] = Field(default_factory=dict)
    sentiment_shifts: Mapping[str, float] = Field(default_factory=dict)


class ThreadSummary(BaseModel):
    id: int
    reddit_id: str
    title: str
    air_time_utc: dt.datetime | None = None
    created_utc: dt.datetime

    model_config = ConfigDict(from_attributes=True)


class ThreadCastAnalyticsResponse(BaseModel):
    thread: ThreadSummary
    cast: list[CastAnalytics]
    total_mentions: int = 0


class CastHistoryEntry(BaseModel):
    thread: ThreadSummary
    time_windows: Mapping[str, AggregateMetrics] = Field(default_factory=dict)
    overall: AggregateMetrics | None = None


class CastHistoryResponse(BaseModel):
    cast: CastAnalytics
    history: list[CastHistoryEntry]


class EmojiStat(BaseModel):
    emoji: str
    count: int


class KeywordStat(BaseModel):
    term: str
    count: int


class NameStat(BaseModel):
    name: str
    count: int
    is_cast: bool = False
    cast_member_id: int | None = None


class MediaItem(BaseModel):
    comment_id: int
    url: str
    media_type: str
    created_utc: dt.datetime | None = None


class ThreadInsightsResponse(BaseModel):
    thread_id: int
    generated_at: dt.datetime
    emojis: list[EmojiStat] = Field(default_factory=list)
    hot_topics: list[KeywordStat] = Field(default_factory=list)
    names: list[NameStat] = Field(default_factory=list)
    media: list[MediaItem] = Field(default_factory=list)
