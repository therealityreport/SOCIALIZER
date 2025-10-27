import os
import pathlib
import sys

import pytest

if sys.version_info < (3, 10):  # pragma: no cover - CI guard for base interpreter
    pytest.skip("Aggregation tests require Python 3.10+", allow_module_level=True)

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("DATABASE_POOL_SIZE", "5")
os.environ.setdefault("DATABASE_MAX_OVERFLOW", "0")

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND_PATH = ROOT / "src" / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.services.aggregation import AggregationCalculator, MentionAggregateInput


def test_aggregation_calculator_computes_vote_weighted_metrics():
    mentions = [
        MentionAggregateInput(cast_member_id=1, sentiment_label="positive", comment_score=10, time_window="live"),
        MentionAggregateInput(cast_member_id=1, sentiment_label="negative", comment_score=2, time_window="day_of"),
        MentionAggregateInput(cast_member_id=2, sentiment_label="neutral", comment_score=0, time_window="live"),
        MentionAggregateInput(cast_member_id=2, sentiment_label="negative", comment_score=-3, time_window="after"),
    ]

    result = AggregationCalculator(thread_id=99, mentions=mentions).run()

    assert result.thread_id == 99
    assert result.total_mentions == 4
    assert set(result.cast.keys()) == {1, 2}
    assert set(result.time_windows.keys()) == {"live", "day_of", "after"}

    cast_one = result.cast[1]
    assert cast_one.overall is not None
    assert cast_one.overall.mention_count == 2
    assert cast_one.share_of_voice == pytest.approx(0.5, rel=1e-3)
    assert cast_one.overall.net_sentiment == pytest.approx(8 / 14, rel=1e-3)
    assert "day_of_vs_live" in cast_one.sentiment_shifts

    live_metrics = cast_one.time_windows["live"]
    assert live_metrics.net_sentiment == pytest.approx(1.0, abs=1e-6)
    assert live_metrics.positive_pct == pytest.approx(1.0, abs=1e-6)

    cast_two = result.cast[2]
    assert cast_two.overall is not None
    assert cast_two.overall.net_sentiment == pytest.approx(-0.5, rel=1e-3)
    assert cast_two.share_of_voice == pytest.approx(0.5, rel=1e-3)
    assert "after_vs_day_of" not in cast_two.sentiment_shifts  # no day_of window for cast two

    assert result.time_window_shifts["day_of_vs_live"] == pytest.approx(-1.9167, rel=1e-3)


def test_aggregation_calculator_handles_empty_payload():
    result = AggregationCalculator(thread_id=123, mentions=[]).run()

    assert result.thread_id == 123
    assert result.total_mentions == 0
    assert result.cast == {}
    assert result.time_windows == {}
    assert result.time_window_shifts == {}
