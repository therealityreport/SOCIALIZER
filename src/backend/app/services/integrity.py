from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import Comment, Thread


@dataclass
class BrigadingResult:
    score: float
    status: str
    total_comments: int
    unique_authors: int
    participation_ratio: float
    suspicious_authors: list[tuple[str, int]]
    generated_at: dt.datetime


@dataclass
class BotResult:
    score: float
    status: str
    flagged_accounts: list[tuple[str, int, float]]
    total_accounts: int
    generated_at: dt.datetime


@dataclass
class ReliabilityResult:
    score: float
    status: str
    ingested_comments: int
    reported_comments: int
    coverage_ratio: float
    minutes_since_last_poll: float | None
    last_polled_at: dt.datetime | None
    generated_at: dt.datetime
    notes: str | None


class IntegrityService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def compute_brigading(self, thread_id: int) -> BrigadingResult:
        comment_count = self._session.scalar(
            select(func.count()).select_from(Comment).where(Comment.thread_id == thread_id)
        ) or 0

        unique_authors = self._session.scalar(
            select(func.count(func.distinct(Comment.author_hash))).where(Comment.thread_id == thread_id)
        ) or 0

        participation_ratio = comment_count / max(1, unique_authors)
        score = min(100.0, max(0.0, (participation_ratio - 1.5) * 40.0))
        status = _score_to_status(score)

        suspicious_query: Select[tuple[str, int]] = (
            select(Comment.author_hash, func.count(Comment.id).label("count"))
            .where(Comment.thread_id == thread_id)
            .group_by(Comment.author_hash)
            .having(func.count(Comment.id) >= 5)
            .order_by(func.count(Comment.id).desc())
            .limit(10)
        )
        suspicious = [
            (author_hash or "unknown", count)
            for author_hash, count in self._session.execute(suspicious_query).all()
        ]

        return BrigadingResult(
            score=round(score, 2),
            status=status,
            total_comments=comment_count,
            unique_authors=unique_authors,
            participation_ratio=round(participation_ratio, 2),
            suspicious_authors=suspicious,
            generated_at=dt.datetime.now(dt.timezone.utc),
        )

    def compute_bots(self, thread_id: int) -> BotResult:
        stats_query: Select[tuple[str, int, float]] = (
            select(
                Comment.author_hash,
                func.count(Comment.id).label("count"),
                func.avg(func.length(Comment.body)).label("avg_length"),
            )
            .where(Comment.thread_id == thread_id)
            .group_by(Comment.author_hash)
        )
        stats = self._session.execute(stats_query).all()
        total_accounts = len(stats)

        flagged = [
            (
                author_hash or "unknown",
                comment_count,
                float(avg_length or 0.0),
            )
            for author_hash, comment_count, avg_length in stats
            if comment_count >= 5 and (avg_length or 0.0) <= 80
        ]

        ratio = len(flagged) / max(1, total_accounts)
        score = min(100.0, ratio * 100.0)
        status = _score_to_status(score)

        return BotResult(
            score=round(score, 2),
            status=status,
            flagged_accounts=flagged,
            total_accounts=total_accounts,
            generated_at=dt.datetime.now(dt.timezone.utc),
        )

    def compute_reliability(self, thread_id: int) -> ReliabilityResult:
        thread = self._session.get(Thread, thread_id)
        if not thread:
            raise ValueError(f"Thread {thread_id} not found")

        ingested = self._session.scalar(
            select(func.count()).select_from(Comment).where(Comment.thread_id == thread_id)
        ) or 0

        reported = thread.total_comments or ingested
        coverage_ratio = ingested / max(1, reported)
        score = min(100.0, coverage_ratio * 100.0)
        status = _score_to_status(score)

        now = dt.datetime.now(dt.timezone.utc)
        last_polled = thread.last_polled_at
        minutes_since_last_poll = None
        if last_polled:
            minutes_since_last_poll = (now - last_polled).total_seconds() / 60.0

        notes = None
        if coverage_ratio < 0.8:
            notes = "Coverage below target. Consider forcing a rescan."
        elif minutes_since_last_poll and minutes_since_last_poll > 30:
            notes = "Polling has stalled for over 30 minutes."

        return ReliabilityResult(
            score=round(score, 2),
            status=status,
            ingested_comments=ingested,
            reported_comments=reported,
            coverage_ratio=round(coverage_ratio, 2),
            minutes_since_last_poll=minutes_since_last_poll,
            last_polled_at=last_polled,
            generated_at=now,
            notes=notes,
        )


def _score_to_status(score: float) -> str:
    if score < 40:
        return "green"
    if score < 70:
        return "yellow"
    return "red"
