from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BrigadingAuthorInsight(BaseModel):
    author_hash: str
    comment_count: int


class BrigadingReport(BaseModel):
    score: float
    status: str
    total_comments: int
    unique_authors: int
    participation_ratio: float
    suspicious_authors: list[BrigadingAuthorInsight] = Field(default_factory=list)
    generated_at: datetime


class BotAccountInsight(BaseModel):
    author_hash: str
    comment_count: int
    average_length: float


class BotReport(BaseModel):
    score: float
    status: str
    flagged_accounts: list[BotAccountInsight] = Field(default_factory=list)
    total_accounts: int
    generated_at: datetime


class ReliabilityReport(BaseModel):
    score: float
    status: str
    ingested_comments: int
    reported_comments: int
    coverage_ratio: float
    minutes_since_last_poll: float | None
    last_polled_at: datetime | None
    generated_at: datetime
    notes: str | None = None
