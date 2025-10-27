import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

pytest.importorskip("jose")

ROOT_THREAD_CREATED = dt.datetime(2024, 1, 1, 12, tzinfo=dt.timezone.utc)

from app.db.base import Base  # type: ignore  # noqa: E402
from app.models import Aggregate, AlertEvent, AlertRule, CastAlias, CastMember, Thread
from app.models.thread import ThreadStatus
from app.services import analytics


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", echo=False, future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Thread.__table__,
            CastMember.__table__,
            CastAlias.__table__,
            Aggregate.__table__,
            AlertRule.__table__,
            AlertEvent.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_thread_with_cast(db: Session) -> tuple[Thread, CastMember]:
    thread = Thread(
        reddit_id="abc123",
        subreddit="bravo",
        title="Episode Recap",
        url="https://reddit.com/r/bravo/abc123",
        air_time_utc=ROOT_THREAD_CREATED,
        created_utc=ROOT_THREAD_CREATED,
        status=ThreadStatus.LIVE,
        total_comments=200,
    )
    cast = CastMember(
        slug="jane-doe",
        full_name="Jane Doe",
        show="Bravo Show",
    )
    db.add(thread)
    db.add(cast)
    db.flush()

    aggregates = [
        Aggregate(
            thread_id=thread.id,
            cast_member_id=cast.id,
            time_window="overall",
            net_sentiment=0.25,
            ci_lower=0.1,
            ci_upper=0.4,
            positive_pct=0.6,
            neutral_pct=0.3,
            negative_pct=0.1,
            agreement_score=0.8,
            mention_count=50,
        ),
        Aggregate(
            thread_id=thread.id,
            cast_member_id=cast.id,
            time_window="live",
            net_sentiment=0.2,
            ci_lower=0.0,
            ci_upper=0.4,
            positive_pct=0.55,
            neutral_pct=0.35,
            negative_pct=0.1,
            agreement_score=0.75,
            mention_count=30,
        ),
    ]
    db.add_all(aggregates)
    db.commit()
    return thread, cast


def test_thread_cast_analytics(session: Session) -> None:
    thread, cast = _seed_thread_with_cast(session)

    response = analytics.get_thread_cast_analytics(session, thread.id)

    assert response.thread.id == thread.id
    assert response.total_mentions == 50
    assert len(response.cast) == 1
    cast_metrics = response.cast[0]
    assert cast_metrics.cast_slug == cast.slug
    assert cast_metrics.overall is not None
    assert cast_metrics.overall.mention_count == 50
    assert "live" in cast_metrics.time_windows
    assert "day_of_vs_live" not in cast_metrics.sentiment_shifts  # only live available


def test_cast_history(session: Session) -> None:
    thread, cast = _seed_thread_with_cast(session)

    response = analytics.get_cast_history(session, cast.slug)
    assert response.cast.cast_slug == cast.slug
    assert len(response.history) == 1
    entry = response.history[0]
    assert entry.thread.id == thread.id
    assert entry.overall is not None
