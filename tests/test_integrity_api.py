from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.db.base import Base
from app.main import app
from app.models import Aggregate, AlertEvent, AlertRule, CastMember, Comment, Mention, Thread
from app.models.thread import ThreadStatus


def _setup_db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    tables = [
        Thread.__table__,
        CastMember.__table__,
        AlertRule.__table__,
        AlertEvent.__table__,
        Aggregate.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER,
                thread_id INTEGER NOT NULL,
                reddit_id TEXT,
                author_hash TEXT,
                body TEXT,
                created_utc TEXT,
                score INTEGER DEFAULT 0,
                parent_id TEXT,
                reply_count INTEGER DEFAULT 0,
                time_window TEXT,
                sentiment_label TEXT,
                sentiment_score REAL,
                sentiment_breakdown TEXT,
                sarcasm_confidence REAL,
                is_sarcastic BOOLEAN DEFAULT 0,
                toxicity_confidence REAL,
                is_toxic BOOLEAN DEFAULT 0,
                ml_model_version TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                PRIMARY KEY (id, created_at)
            )
            """
        )
    Mention.__table__.create(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, TestingSession


def _seed_comments(session, thread_id: int) -> None:
    now = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
    authors = ["hash-a", "hash-b", "hash-c", "hash-b", "hash-b", "hash-b", "hash-d"]
    bodies = [
        "Great episode!",
        "I can't believe it",
        "Wow",
        "Another comment",
        "Short",
        "Bot-like",
        "Longer commentary that exceeds the threshold for bot detection.",
    ]
    for idx, (author, body) in enumerate(zip(authors, bodies)):
        created = now + dt.timedelta(minutes=idx)
        comment = Comment(
            thread_id=thread_id,
            reddit_id=f"rid-{idx}",
            author_hash=author,
            body=body,
            created_utc=created,
            score=1,
            time_window="live",
            created_at=created,
            updated_at=created,
        )
        session.add(comment)
    session.commit()


def test_integrity_endpoints() -> None:
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
        created = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        thread = Thread(
            reddit_id="ghi789",
            subreddit="bravo",
            title="Integrity Test",
            url="https://reddit.com",
            air_time_utc=created,
            created_utc=created,
            status=ThreadStatus.LIVE,
            total_comments=10,
        )
        session.add(thread)
        session.commit()
        _seed_comments(session, thread.id)

    brigading = client.get(f"/api/v1/integrity/threads/{thread.id}/brigading")
    assert brigading.status_code == 200
    payload = brigading.json()
    assert "score" in payload and payload["total_comments"] == 7

    bots = client.get(f"/api/v1/integrity/threads/{thread.id}/bots")
    assert bots.status_code == 200
    bots_payload = bots.json()
    assert "flagged_accounts" in bots_payload

    reliability = client.get(f"/api/v1/integrity/threads/{thread.id}/reliability")
    assert reliability.status_code == 200
    reliability_payload = reliability.json()
    assert reliability_payload["ingested_comments"] == 7

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
