from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.db.base import Base
from app.main import app
from app.models import Aggregate, CastAlias, CastMember, Comment, Export, Mention, Thread
from app.tasks import ingestion as ingestion_tasks
from app.api.routes import threads as thread_routes
from celery.app import task as celery_task


@pytest.fixture()
def test_client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    from app.models.alert import AlertEvent, AlertRule

    tables = [
        Thread.__table__,
        CastMember.__table__,
        CastAlias.__table__,
        Aggregate.__table__,
        Export.__table__,
        AlertRule.__table__,
        AlertEvent.__table__,
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
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id INTEGER NOT NULL,
                comment_created_at TEXT NOT NULL,
                cast_member_id INTEGER NOT NULL,
                sentiment_label TEXT NOT NULL,
                sentiment_score REAL,
                confidence REAL,
                is_sarcastic BOOLEAN DEFAULT 0,
                is_toxic BOOLEAN DEFAULT 0,
                weight REAL,
                method TEXT,
                quote TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db() -> Session:
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[deps.get_db] = override_get_db

    with TestClient(app) as client:
        yield client, TestingSession

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine, tables=tables)


def test_full_thread_workflow(test_client: tuple[TestClient, sessionmaker[Session]] , monkeypatch: pytest.MonkeyPatch) -> None:
    client, SessionLocal = test_client

    scheduled: dict[str, tuple[str, str]] = {}

    def fake_apply_async(self, args=None, kwargs=None, **_options):
        call_args = args or ()
        if not call_args and kwargs:
            call_args = tuple(kwargs.get(key) for key in ("thread_id", "subreddit") if key in kwargs)
        if self.name == "app.tasks.ingestion.fetch_thread":
            reddit_id = call_args[0] if len(call_args) > 0 else kwargs.get("thread_id")
            subreddit = call_args[1] if len(call_args) > 1 else kwargs.get("subreddit")
            scheduled["fetch"] = (reddit_id, subreddit)
        return None

    monkeypatch.setattr(celery_task.Task, "apply_async", fake_apply_async, raising=False)

    create_payload = {
        'reddit_id': 'abc123',
        'subreddit': 'bravo',
        'title': 'Episode Premiere',
        'url': 'https://www.reddit.com/r/bravo/comments/abc123/episode_premiere',
        'air_time_utc': dt.datetime(2024, 1, 1, 1, tzinfo=dt.timezone.utc).isoformat(),
        'created_utc': dt.datetime(2024, 1, 1, 0, tzinfo=dt.timezone.utc).isoformat(),
        'status': 'scheduled',
        'total_comments': 0,
        'synopsis': None
    }

    create_response = client.post('/api/v1/threads', json=create_payload)
    assert create_response.status_code == 201
    thread = create_response.json()
    thread_id = thread['id']
    assert scheduled["fetch"] == (create_payload["reddit_id"], create_payload["subreddit"])

    cast_id = None

    with SessionLocal() as db:
        cast = CastMember(slug='jane-doe', full_name='Jane Doe', show='Bravo Show')
        db.add(cast)
        db.flush()
        cast_id = cast.id

        aggregates = [
            Aggregate(
                thread_id=thread_id,
                cast_member_id=cast.id,
                time_window='overall',
                net_sentiment=0.2,
                ci_lower=0.1,
                ci_upper=0.3,
                positive_pct=0.6,
                neutral_pct=0.3,
                negative_pct=0.1,
                agreement_score=0.75,
                mention_count=40,
            ),
            Aggregate(
                thread_id=thread_id,
                cast_member_id=cast.id,
                time_window='live',
                net_sentiment=0.3,
                ci_lower=0.1,
                ci_upper=0.5,
                positive_pct=0.7,
                neutral_pct=0.2,
                negative_pct=0.1,
                agreement_score=0.8,
                mention_count=25,
            ),
        ]
        db.add_all(aggregates)
        db.commit()
        cast_slug = cast.slug

    analytics_response = client.get(f'/api/v1/threads/{thread_id}/cast')
    assert analytics_response.status_code == 200
    analytics_payload = analytics_response.json()
    assert analytics_payload['thread']['id'] == thread_id
    assert analytics_payload['total_mentions'] == 40
    assert analytics_payload['cast'][0]['cast_slug'] == cast_slug

    history_response = client.get(f'/api/v1/cast/{cast_slug}/history')
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload['cast']['cast_slug'] == cast_slug
    assert len(history_payload['history']) == 1

    export_response = client.post('/api/v1/exports/csv', json={'thread_id': thread_id})
    assert export_response.status_code == 201
    export_meta = export_response.json()
    export_id = export_meta['id']

    download_response = client.get(f'/api/v1/exports/{export_id}')
    assert download_response.status_code == 200
    assert download_response.headers['content-type'].startswith('text/csv')
    assert 'cast_slug' in download_response.text

    comment_timestamp = dt.datetime(2024, 1, 1, 2, tzinfo=dt.timezone.utc)
    with SessionLocal() as db:
        comment = Comment(
            id=1,
            thread_id=thread_id,
            reddit_id='cmt123',
            author_hash='hash-xyz',
            body='Loved this episode, especially Jane!',
            created_utc=comment_timestamp,
            score=12,
            reply_count=3,
            time_window='live',
            sentiment_label='positive',
            sentiment_score=0.92,
            sentiment_breakdown={
                'models': [
                    {
                        'name': 'ml-primary',
                        'sentiment_label': 'positive',
                        'sentiment_score': 0.92,
                        'reasoning': 'High praise detected.',
                    }
                ],
                'combined_score': 0.92,
                'final_label': 'positive',
                'final_source': 'ml-primary',
            },
            is_sarcastic=False,
            sarcasm_confidence=None,
            is_toxic=False,
            toxicity_confidence=None,
        )
        comment.created_at = comment_timestamp
        comment.updated_at = comment_timestamp
        db.add(comment)
        db.flush()

        if cast_id is not None:
            mention = Mention(
                comment_id=comment.id,
                comment_created_at=comment.created_at,
                cast_member_id=cast_id,
                sentiment_label='positive',
                sentiment_score=0.88,
                quote='Jane stole the episode.',
            )
            db.add(mention)
        db.commit()

    comments_export = client.get(f'/api/v1/threads/{thread_id}/comments/export')
    assert comments_export.status_code == 200
    assert comments_export.headers['content-type'].startswith('text/csv')
    csv_payload = comments_export.text
    assert 'comment_id' in csv_payload
    assert 'Loved this episode' in csv_payload
    assert 'Jane Doe' in csv_payload
