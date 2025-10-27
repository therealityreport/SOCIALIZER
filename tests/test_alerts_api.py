from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.main import app
from app.db.base import Base
from app.models import AlertEvent, AlertRule, CastMember, Thread
from app.models.thread import ThreadStatus


def _setup_db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    tables = [Thread.__table__, CastMember.__table__, AlertRule.__table__, AlertEvent.__table__]
    Base.metadata.create_all(engine, tables=tables)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, TestingSession


def _seed_entities(session: Session) -> tuple[int, int]:
    created = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    thread = Thread(
        reddit_id="def456",
        subreddit="bravo",
        title="Shocking Reveal",
        url="https://reddit.com/r/bravo/def456",
        air_time_utc=created,
        created_utc=created,
        status=ThreadStatus.LIVE,
    )
    cast = CastMember(slug="john-doe", full_name="John Doe", show="Bravo Show")
    session.add_all([thread, cast])
    session.commit()
    return thread.id, cast.id


def test_alert_rule_crud() -> None:
    engine, TestingSession = _setup_db()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[deps.get_db] = override_get_db
    client = TestClient(app)

    with TestingSession() as session:
        thread_id, cast_id = _seed_entities(session)

    create_payload = {
        "name": "Rapid sentiment drop",
        "rule_type": "sentiment_drop",
        "condition": {"metric": "net_sentiment", "window": "live", "comparison": "lt", "threshold": -0.5},
        "thread_id": thread_id,
        "cast_member_id": cast_id,
        "channels": ["slack"],
    }

    response = client.post("/api/v1/alerts/rules", json=create_payload)
    assert response.status_code == 201
    rule = response.json()
    rule_id = rule["id"]
    assert rule["name"] == "Rapid sentiment drop"

    list_response = client.get(f"/api/v1/alerts/rules?thread_id={thread_id}")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = client.put(f"/api/v1/alerts/rules/{rule_id}", json={"is_active": False})
    assert update_response.status_code == 200
    assert update_response.json()["is_active"] is False

    history_response = client.get(f"/api/v1/alerts/history?thread_id={thread_id}")
    assert history_response.status_code == 200
    assert history_response.json() == []

    delete_response = client.delete(f"/api/v1/alerts/rules/{rule_id}")
    assert delete_response.status_code == 204

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
