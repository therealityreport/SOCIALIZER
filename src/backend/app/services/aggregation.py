from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from app.models import Aggregate, Comment, Mention
from app.models.cast import CastMember

SentimentLabel = str
TimeWindow = str


@dataclass(frozen=True)
class MentionAggregateInput:
    cast_member_id: int
    sentiment_label: SentimentLabel | None
    comment_score: int | None
    time_window: TimeWindow | None
    weight: float | None = None  # New: pre-calculated weight (upvotes * confidence)


@dataclass
class AggregatedMetrics:
    net_sentiment: float
    ci_lower: float
    ci_upper: float
    positive_pct: float
    neutral_pct: float
    negative_pct: float
    agreement_score: float
    mention_count: int


@dataclass
class CastAggregation:
    cast_member_id: int
    share_of_voice: float
    overall: AggregatedMetrics | None
    time_windows: Mapping[TimeWindow, AggregatedMetrics]
    sentiment_shifts: Mapping[str, float]


@dataclass
class AggregationResult:
    thread_id: int
    total_mentions: int
    cast: Mapping[int, CastAggregation]
    time_windows: Mapping[TimeWindow, AggregatedMetrics]
    time_window_shifts: Mapping[str, float]


class _AggregationAccumulator:
    __slots__ = ("_weighted", "_counts", "_weight_sum")

    def __init__(self) -> None:
        self._weighted: dict[str, float] = {"positive": 0.0, "neutral": 0.0, "negative": 0.0}
        self._counts: dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0}
        self._weight_sum: float = 0.0

    def add(self, label: SentimentLabel | None, score: int | None, weight: float | None = None) -> None:
        normalized = _normalize_label(label)
        # Use pre-calculated weight if available, otherwise fall back to score-based weighting
        if weight is not None:
            calculated_weight = weight
        else:
            calculated_weight = float(max(score or 0, 0) + 1)
        self._counts[normalized] += 1
        self._weighted[normalized] += calculated_weight
        self._weight_sum += calculated_weight

    def finalize(self) -> AggregatedMetrics | None:
        total_count = sum(self._counts.values())
        if total_count == 0:
            return None

        total_weight = sum(self._weighted.values())
        if total_weight == 0:
            # If all weights are zero we still want to reflect mention counts.
            total_weight = float(total_count)

        positive_weight = self._weighted["positive"]
        negative_weight = self._weighted["negative"]

        net_sentiment = _clamp((positive_weight - negative_weight) / total_weight)

        positive_pct = self._counts["positive"] / total_count
        neutral_pct = self._counts["neutral"] / total_count
        negative_pct = self._counts["negative"] / total_count

        se = _sentiment_standard_error(positive_pct, negative_pct, total_count)
        ci_lower = _clamp(net_sentiment - 1.96 * se)
        ci_upper = _clamp(net_sentiment + 1.96 * se)

        agreement_score = self._weight_sum / total_count

        return AggregatedMetrics(
            net_sentiment=net_sentiment,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            positive_pct=positive_pct,
            neutral_pct=neutral_pct,
            negative_pct=negative_pct,
            agreement_score=agreement_score,
            mention_count=total_count,
        )


class AggregationCalculator:
    """Pure aggregation logic that can be unit tested without a database."""

    def __init__(self, thread_id: int, mentions: Iterable[MentionAggregateInput]) -> None:
        self.thread_id = thread_id
        self._mentions = list(mentions)

    def run(self) -> AggregationResult:
        cast_window_acc: dict[tuple[int, TimeWindow], _AggregationAccumulator] = defaultdict(_AggregationAccumulator)
        cast_overall_acc: dict[int, _AggregationAccumulator] = defaultdict(_AggregationAccumulator)
        window_acc: dict[TimeWindow, _AggregationAccumulator] = defaultdict(_AggregationAccumulator)

        for mention in self._mentions:
            cast_id = mention.cast_member_id
            if cast_id is None:
                continue

            window = _normalize_window(mention.time_window)
            acc_key = (cast_id, window)

            cast_window_acc[acc_key].add(mention.sentiment_label, mention.comment_score, mention.weight)
            cast_overall_acc[cast_id].add(mention.sentiment_label, mention.comment_score, mention.weight)
            window_acc[window].add(mention.sentiment_label, mention.comment_score, mention.weight)

        cast_results: dict[int, CastAggregation] = {}
        finalized_overall: dict[int, AggregatedMetrics] = {}

        for cast_id, accumulator in cast_overall_acc.items():
            metrics = accumulator.finalize()
            if metrics:
                finalized_overall[cast_id] = metrics

        total_mentions = sum(metrics.mention_count for metrics in finalized_overall.values())

        for cast_id, overall_acc in cast_overall_acc.items():
            overall_metrics = finalized_overall.get(cast_id)
            windows: dict[TimeWindow, AggregatedMetrics] = {}

            for (candidate_cast_id, window), accumulator in cast_window_acc.items():
                if candidate_cast_id != cast_id:
                    continue
                metrics = accumulator.finalize()
                if metrics:
                    windows[window] = metrics

            share_of_voice = 0.0
            if total_mentions and overall_metrics:
                share_of_voice = overall_metrics.mention_count / total_mentions

            sentiment_shifts = _compute_sentiment_shifts(windows)

            cast_results[cast_id] = CastAggregation(
                cast_member_id=cast_id,
                share_of_voice=share_of_voice,
                overall=overall_metrics,
                time_windows=windows,
                sentiment_shifts=sentiment_shifts,
            )

        time_window_metrics: dict[TimeWindow, AggregatedMetrics] = {}
        for window, accumulator in window_acc.items():
            metrics = accumulator.finalize()
            if metrics:
                time_window_metrics[window] = metrics

        time_window_shifts = _compute_sentiment_shifts(time_window_metrics)

        return AggregationResult(
            thread_id=self.thread_id,
            total_mentions=total_mentions,
            cast=cast_results,
            time_windows=time_window_metrics,
            time_window_shifts=time_window_shifts,
        )


class AggregationService:
    """Load mention data, run aggregation, and persist results."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def compute(self, thread_id: int) -> AggregationResult:
        inputs = self._load_mentions(thread_id)
        calculator = AggregationCalculator(thread_id, inputs)
        result = calculator.run()
        self._persist(thread_id, result)
        return result

    def _load_mentions(self, thread_id: int) -> list[MentionAggregateInput]:
        stmt = (
            select(
                Mention.cast_member_id,
                Mention.sentiment_label,
                Comment.score,
                Comment.time_window,
                Mention.weight,
            )
            .join(
                Comment,
                and_(
                    Mention.comment_id == Comment.id,
                    Mention.comment_created_at == Comment.created_at,
                ),
            )
            .join(CastMember, CastMember.id == Mention.cast_member_id)
            .where(Comment.thread_id == thread_id)
            .where(CastMember.is_active.is_(True))
        )
        rows = self._session.execute(stmt).all()
        return [
            MentionAggregateInput(
                cast_member_id=row.cast_member_id,
                sentiment_label=row.sentiment_label,
                comment_score=row.score,
                time_window=row.time_window,
                weight=row.weight,
            )
            for row in rows
            if row.cast_member_id is not None
        ]

    def _persist(self, thread_id: int, result: AggregationResult) -> None:
        self._session.execute(delete(Aggregate).where(Aggregate.thread_id == thread_id))

        for cast_result in result.cast.values():
            if cast_result.overall:
                self._session.add(
                    Aggregate(
                        thread_id=thread_id,
                        cast_member_id=cast_result.cast_member_id,
                        time_window="overall",
                        net_sentiment=cast_result.overall.net_sentiment,
                        ci_lower=cast_result.overall.ci_lower,
                        ci_upper=cast_result.overall.ci_upper,
                        positive_pct=cast_result.overall.positive_pct,
                        neutral_pct=cast_result.overall.neutral_pct,
                        negative_pct=cast_result.overall.negative_pct,
                        agreement_score=cast_result.overall.agreement_score,
                        mention_count=cast_result.overall.mention_count,
                    )
                )

            for window, metrics in cast_result.time_windows.items():
                self._session.add(
                    Aggregate(
                        thread_id=thread_id,
                        cast_member_id=cast_result.cast_member_id,
                        time_window=window,
                        net_sentiment=metrics.net_sentiment,
                        ci_lower=metrics.ci_lower,
                        ci_upper=metrics.ci_upper,
                        positive_pct=metrics.positive_pct,
                        neutral_pct=metrics.neutral_pct,
                        negative_pct=metrics.negative_pct,
                        agreement_score=metrics.agreement_score,
                        mention_count=metrics.mention_count,
                    )
                )


def _normalize_label(label: SentimentLabel | None) -> SentimentLabel:
    if not label:
        return "neutral"
    lowered = label.lower()
    if lowered in {"positive", "neutral", "negative"}:
        return lowered
    return "neutral"


def _normalize_window(window: TimeWindow | None) -> TimeWindow:
    if not window:
        return "unspecified"
    return window.lower()


def _sentiment_standard_error(positive_pct: float, negative_pct: float, total_count: int) -> float:
    if total_count <= 1:
        return 0.0
    var_pos = positive_pct * (1 - positive_pct) / total_count
    var_neg = negative_pct * (1 - negative_pct) / total_count
    value = var_pos + var_neg
    return math.sqrt(value) if value > 0 else 0.0


def _compute_sentiment_shifts(metrics: Mapping[TimeWindow, AggregatedMetrics]) -> dict[str, float]:
    def _value(window: str) -> float | None:
        data = metrics.get(window)
        return data.net_sentiment if data else None

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


def _clamp(value: float, lower: float = -1.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))
