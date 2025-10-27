from __future__ import annotations

import datetime as dt
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session, noload

from app.models import Aggregate, CastMember, Thread
from app.services.show_names import normalize_show_name
from app.schemas.analytics import (
    AggregateMetrics,
    CastAnalytics,
    CastHistoryEntry,
    CastHistoryResponse,
    ThreadCastAnalyticsResponse,
    ThreadSummary,
)


def _metrics_from_aggregate(aggregate: Aggregate) -> AggregateMetrics:
    return AggregateMetrics(
        net_sentiment=aggregate.net_sentiment,
        ci_lower=aggregate.ci_lower,
        ci_upper=aggregate.ci_upper,
        positive_pct=aggregate.positive_pct,
        neutral_pct=aggregate.neutral_pct,
        negative_pct=aggregate.negative_pct,
        agreement_score=aggregate.agreement_score,
        mention_count=aggregate.mention_count or 0,
    )


def _compute_sentiment_shifts(time_windows: Mapping[str, AggregateMetrics]) -> dict[str, float]:
    def _value(window: str) -> float | None:
        metrics = time_windows.get(window)
        return metrics.net_sentiment if metrics else None

    live = _value("live")
    day_of = _value("day_of")
    after = _value("after")

    shifts: dict[str, float] = {}
    if live is not None and day_of is not None:
        shifts["day_of_vs_live"] = day_of - live
    if day_of is not None and after is not None:
        shifts["after_vs_day_of"] = after - day_of
    if live is not None and after is not None:
        shifts["after_vs_live"] = after - live
    return shifts


def _thread_summary(thread: Thread) -> ThreadSummary:
    return ThreadSummary(
        id=thread.id,
        reddit_id=thread.reddit_id,
        title=thread.title,
        air_time_utc=thread.air_time_utc,
        created_utc=thread.created_utc,
    )


def get_thread_cast_analytics(session: Session, thread_id: int) -> ThreadCastAnalyticsResponse:
    thread = session.get(Thread, thread_id)
    if not thread:
        raise LookupError(f"Thread {thread_id} not found.")

    stmt = (
        select(Aggregate, CastMember)
        .join(CastMember, CastMember.id == Aggregate.cast_member_id)
        .where(Aggregate.thread_id == thread_id)
    )
    rows = session.execute(stmt).all()

    cast_map: dict[int, dict[str, object]] = {}
    total_mentions = 0

    for aggregate, cast_member in rows:
        metrics = _metrics_from_aggregate(aggregate)
        entry = cast_map.setdefault(
            cast_member.id,
            {
                "cast_id": cast_member.id,
                "cast_slug": cast_member.slug,
                "full_name": cast_member.full_name,
                "show": normalize_show_name(cast_member.show),
                "overall": None,
                "time_windows": {},
            },
        )
        if aggregate.time_window == "overall":
            entry["overall"] = metrics
            total_mentions += metrics.mention_count
        else:
            entry["time_windows"][aggregate.time_window] = metrics

    cast_responses: list[CastAnalytics] = []

    for data in cast_map.values():
        time_windows: dict[str, AggregateMetrics] = data["time_windows"]  # type: ignore[assignment]
        overall_metrics: AggregateMetrics | None = data["overall"]  # type: ignore[assignment]
        share_of_voice = 0.0
        if total_mentions and overall_metrics:
            share_of_voice = overall_metrics.mention_count / total_mentions
        sentiment_shifts = _compute_sentiment_shifts(time_windows)
        cast_responses.append(
            CastAnalytics(
                cast_id=data["cast_id"],  # type: ignore[arg-type]
                cast_slug=data["cast_slug"],  # type: ignore[arg-type]
                full_name=data["full_name"],  # type: ignore[arg-type]
            show=data["show"],  # type: ignore[arg-type]
                share_of_voice=share_of_voice,
                overall=overall_metrics,
                time_windows=time_windows,
                sentiment_shifts=sentiment_shifts,
            )
        )

    cast_responses.sort(key=lambda c: c.share_of_voice, reverse=True)

    return ThreadCastAnalyticsResponse(
        thread=_thread_summary(thread),
        cast=cast_responses,
        total_mentions=total_mentions,
    )


def get_cast_history(session: Session, cast_slug: str) -> CastHistoryResponse:
    cast_member = session.execute(
        select(CastMember).where(CastMember.slug == cast_slug)
    ).scalar_one_or_none()
    if not cast_member:
        raise LookupError(f"Cast member {cast_slug} not found.")

    stmt = (
        select(Aggregate, Thread)
        .options(noload(Thread.comments), noload(Thread.aggregates))
        .join(Thread, Thread.id == Aggregate.thread_id)
        .where(Aggregate.cast_member_id == cast_member.id)
    )
    rows = session.execute(stmt).all()

    thread_map: dict[int, dict[str, object]] = {}

    for aggregate, thread in rows:
        entry = thread_map.setdefault(
            thread.id,
            {
                "thread": _thread_summary(thread),
                "overall": None,
                "time_windows": {},
            },
        )
        metrics = _metrics_from_aggregate(aggregate)
        if aggregate.time_window == "overall":
            entry["overall"] = metrics
        else:
            entry["time_windows"][aggregate.time_window] = metrics

    history_entries: list[CastHistoryEntry] = []
    for entry in sorted(
        thread_map.values(),
        key=lambda item: item["thread"].created_utc,  # type: ignore[index]
    ):
        history_entries.append(
            CastHistoryEntry(
                thread=entry["thread"],  # type: ignore[arg-type]
                overall=entry["overall"],  # type: ignore[arg-type]
                time_windows=entry["time_windows"],  # type: ignore[arg-type]
            )
        )

    return CastHistoryResponse(
        cast=CastAnalytics(
            cast_id=cast_member.id,
            cast_slug=cast_member.slug,
            full_name=cast_member.full_name,
            show=normalize_show_name(cast_member.show),
            share_of_voice=0.0,
            overall=None,
            time_windows={},
            sentiment_shifts={},
        ),
        history=history_entries,
    )


def get_thread_cast_member(session: Session, thread_id: int, cast_slug: str) -> tuple[ThreadSummary, CastAnalytics]:
    analytics = get_thread_cast_analytics(session, thread_id)
    for cast in analytics.cast:
        if cast.cast_slug == cast_slug or str(cast.cast_id) == cast_slug:
            return analytics.thread, cast
    raise LookupError(f"Cast member {cast_slug} not found for thread {thread_id}.")
