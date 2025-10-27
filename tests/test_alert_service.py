from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import Aggregate, AlertEvent, AlertRule, CastMember, Thread
from app.models.thread import ThreadStatus
from app.services.alerts import AlertDeliveryService, AlertEvaluationService


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    tables = [
        Thread.__table__,
        CastMember.__table__,
        Aggregate.__table__,
        AlertRule.__table__,
        AlertEvent.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    sess = TestingSession()
    try:
        yield sess
    finally:
        sess.close()
        Base.metadata.drop_all(engine, tables=tables)


def _insert_thread(session: Session) -> tuple[Thread, CastMember]:
    created = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    thread = Thread(
        reddit_id="abc123",
        subreddit="bravo",
        title="Premiere",
        url="https://reddit.com/r/bravo/abc123",
        air_time_utc=created,
        created_utc=created,
        status=ThreadStatus.LIVE,
    )
    cast = CastMember(slug="jane-doe", full_name="Jane Doe", show="Bravo Show")
    session.add_all([thread, cast])
    session.flush()
    return thread, cast


def _insert_aggregate(
    session: Session,
    thread_id: int,
    cast_member_id: int,
    window: str,
    net_sentiment: float,
    mentions: int,
) -> None:
    aggregate = Aggregate(
        thread_id=thread_id,
        cast_member_id=cast_member_id,
        time_window=window,
        net_sentiment=net_sentiment,
        mention_count=mentions,
    )
    session.add(aggregate)


def test_sentiment_drop_rule_triggers_event(session: Session) -> None:
    thread, cast = _insert_thread(session)
    _insert_aggregate(session, thread.id, cast.id, "live", net_sentiment=-0.45, mentions=50)
    session.commit()

    rule = AlertRule(
        name="Negative swing",
        rule_type="sentiment_drop",
        condition={"metric": "net_sentiment", "window": "live", "comparison": "lt", "threshold": -0.3},
        thread_id=thread.id,
        cast_member_id=cast.id,
        channels=["slack"],
    )
    session.add(rule)
    session.commit()

    service = AlertEvaluationService(session)
    events = service.evaluate_thread(thread.id)
    session.commit()

    assert len(events) == 1
    payload = events[0].payload
    assert payload["value"] == pytest.approx(-0.45)
    assert payload["threshold"] == pytest.approx(-0.3)


def test_duplicate_events_are_suppressed(session: Session) -> None:
    thread, cast = _insert_thread(session)
    _insert_aggregate(session, thread.id, cast.id, "live", net_sentiment=-0.6, mentions=50)
    session.commit()

    rule = AlertRule(
        name="Repeat check",
        rule_type="sentiment_drop",
        condition={
            "metric": "net_sentiment",
            "window": "live",
            "comparison": "lte",
            "threshold": -0.5,
        },
        thread_id=thread.id,
        cast_member_id=cast.id,
        channels=["slack"],
    )
    session.add(rule)
    session.commit()

    service = AlertEvaluationService(session)
    first_batch = service.evaluate_thread(thread.id)
    session.commit()
    assert len(first_batch) == 1

    second_batch = service.evaluate_thread(thread.id)
    session.commit()
    assert len(second_batch) == 0


def test_baseline_delta_rule(session: Session) -> None:
    thread, cast = _insert_thread(session)
    _insert_aggregate(session, thread.id, cast.id, "overall", net_sentiment=0.2, mentions=100)
    _insert_aggregate(session, thread.id, cast.id, "live", net_sentiment=-0.4, mentions=80)
    session.commit()

    rule = AlertRule(
        name="Delta drop",
        rule_type="sentiment_drop",
        condition={
            "metric": "net_sentiment",
            "window": "live",
            "baseline_window": "overall",
            "comparison": "lt",
            "threshold": -0.4,
        },
        thread_id=thread.id,
        cast_member_id=cast.id,
        channels=["slack", "email"],
    )
    session.add(rule)
    session.commit()

    service = AlertEvaluationService(session)
    events = service.evaluate_thread(thread.id)
    session.commit()

    assert len(events) == 1
    payload = events[0].payload
    assert payload["delta"] == pytest.approx(-0.6)
    assert payload["baseline_value"] == pytest.approx(0.2)


class _FakeSlack:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send(self, text: str, blocks: list[dict[str, object]] | None = None) -> bool:  # noqa: ARG002
        self.messages.append(text)
        return True


class _FakeEmail:
    def __init__(self) -> None:
        self.payloads: list[tuple[list[str], str]] = []

    def send(self, recipients, subject: str, html_content: str, plain_content: str | None = None) -> bool:  # noqa: ARG002
        self.payloads.append((list(recipients), subject))
        return True


def test_alert_delivery_updates_channels(session: Session) -> None:
    thread, cast = _insert_thread(session)
    _insert_aggregate(session, thread.id, cast.id, "live", net_sentiment=-0.7, mentions=60)
    session.commit()

    rule = AlertRule(
        name="Notify everywhere",
        rule_type="sentiment_drop",
        condition={
            "metric": "net_sentiment",
            "window": "live",
            "comparison": "lt",
            "threshold": -0.5,
            "emails": ["alerts@example.com"],
        },
        thread_id=thread.id,
        cast_member_id=cast.id,
        channels=["slack", "email"],
    )
    session.add(rule)
    session.commit()

    event = AlertEvent(
        alert_rule_id=rule.id,
        thread_id=thread.id,
        cast_member_id=cast.id,
        payload={"metric": "net_sentiment", "window": "live", "value": -0.7, "threshold": -0.5},
        delivered_channels=[],
    )
    session.add(event)
    session.commit()

    slack = _FakeSlack()
    email = _FakeEmail()
    service = AlertDeliveryService(session, slack_notifier=slack, email_notifier=email)
    delivered = service.deliver(event)
    session.commit()

    assert set(delivered) == {"slack", "email"}
    assert set(event.delivered_channels) == {"slack", "email"}
    assert slack.messages
    assert email.payloads and email.payloads[0][0] == ["alerts@example.com"]
