from __future__ import annotations

import datetime as dt
import math
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.db.base import Base
from app.main import app
from app.models import Aggregate, CastAlias, CastMember, Comment, Mention, Thread
from app.models.thread import ThreadStatus
from app.tasks import analytics as analytics_tasks
from app.tasks import alerts as alerts_tasks
from app.tasks import ml as ml_tasks
from app.tasks.analytics import compute_aggregates
from app.tasks.ml import classify_comments
from app.services.sentiment_pipeline import ModelSentiment, NormalizedSentiment, SentimentAnalysisResult
from app.services.entity_linking import MentionCandidate


@pytest.fixture()
def pipeline_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    tables = [
        Thread.__table__,
        CastMember.__table__,
        CastAlias.__table__,
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
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                name TEXT,
                description TEXT,
                cast_member_id INTEGER,
                rule_type TEXT,
                condition TEXT,
                is_active BOOLEAN DEFAULT 1,
                channels TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS alert_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                alert_rule_id INTEGER,
                cast_member_id INTEGER,
                triggered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                payload TEXT,
                delivered_channels TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    monkeypatch.setattr(ml_tasks, "SessionLocal", TestingSession)
    monkeypatch.setattr(analytics_tasks, "SessionLocal", TestingSession)
    monkeypatch.setattr(alerts_tasks, "SessionLocal", TestingSession)

    def override_get_db() -> Iterator[Session]:
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


def test_classification_and_linking_pipeline_populates_analytics(
    pipeline_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _client, SessionLocal = pipeline_client

    class FakePipeline:
        def analyze_comment(self, text: str) -> SentimentAnalysisResult:
            final = NormalizedSentiment(
                cast_member_id=None,
                cast_member=None,
                sentiment_label="positive",
                sentiment_score=0.9,
                source_model="fake-primary",
                reasoning="Primary model confidence 90%.",
            )
            models = [
                ModelSentiment(
                    name="fake-primary",
                    sentiment_label="positive",
                    sentiment_score=0.9,
                    reasoning="Primary model confidence 90%.",
                )
            ]
            return SentimentAnalysisResult(final=final, models=models, combined_score=0.9)

        def analyze_mentions(
            self,
            comment_text: str,
            candidates: list[MentionCandidate],
            contexts: list[str],
            catalog: dict[int, object],
        ) -> list[NormalizedSentiment]:
            results: list[NormalizedSentiment] = []
            for candidate in candidates:
                entry = catalog.get(candidate.cast_member_id)
                cast_name = getattr(entry, "canonical_name", None)
                results.append(
                    NormalizedSentiment(
                        cast_member_id=candidate.cast_member_id,
                        cast_member=cast_name,
                        sentiment_label="positive",
                        sentiment_score=0.88,
                        source_model="fake-primary",
                        reasoning="Primary model confidence 88%.",
                    )
                )
            return results

    class FakeLinker:
        def __init__(self, catalog) -> None:
            self.catalog = list(catalog)

        def find_mentions(self, text: str) -> list[MentionCandidate]:
            if not self.catalog:
                return []
            cast_id = self.catalog[0].cast_member_id
            return [
                MentionCandidate(
                    cast_member_id=cast_id,
                    confidence=0.95,
                    method="exact",
                    quote=text[:32] or "quote",
                )
            ]

    fake_pipeline = FakePipeline()
    monkeypatch.setattr(ml_tasks, "get_sentiment_pipeline", lambda *_args, **_kwargs: fake_pipeline)
    monkeypatch.setattr(ml_tasks, "EntityLinker", lambda catalog: FakeLinker(catalog))

    def immediate_link_entities(comment_ids: list[int]) -> None:
        ml_tasks.link_entities.apply(args=(comment_ids,))

    monkeypatch.setattr(ml_tasks.link_entities, "delay", immediate_link_entities)

    def immediate_apply_async(*_call_args, **call_kwargs) -> None:
        task_args = call_kwargs.get("args") or []
        comment_ids_arg = task_args[0] if task_args else []
        immediate_link_entities(comment_ids_arg)

    monkeypatch.setattr(ml_tasks.link_entities, "apply_async", immediate_apply_async)

    def immediate_compute(thread_id: int) -> None:
        compute_aggregates.apply(args=(thread_id,))

    monkeypatch.setattr(analytics_tasks.compute_aggregates, "delay", immediate_compute)
    monkeypatch.setattr(ml_tasks, "compute_aggregates", analytics_tasks.compute_aggregates)
    monkeypatch.setattr(alerts_tasks.check_alerts, "delay", lambda _thread_id: None)

    with SessionLocal() as db:
        thread = Thread(
            reddit_id="abc123",
            subreddit="bravo",
            title="Episode Night",
            url="https://reddit.com/r/bravo/comments/abc123",
            air_time_utc=dt.datetime(2024, 1, 1, 1, tzinfo=dt.timezone.utc),
            created_utc=dt.datetime(2024, 1, 1, 0, tzinfo=dt.timezone.utc),
            status=ThreadStatus.LIVE,
            total_comments=0,
        )
        db.add(thread)
        db.flush()

        cast = CastMember(slug="jane-doe", full_name="Jane Doe", show="Bravo Show")
        db.add(cast)
        db.flush()

        now = dt.datetime.now(dt.timezone.utc)
        comment = Comment(
            id=1,
            thread_id=thread.id,
            reddit_id="c1",
            author_hash="hash",
            body="I think Jane Doe was amazing tonight!",
            created_utc=now,
            score=5,
            parent_id=None,
            reply_count=0,
            time_window="live",
            created_at=now,
            updated_at=now,
        )
        db.add(comment)
        db.commit()
        comment_id = comment.id
        thread_id = thread.id
        cast_id = cast.id

    classify_result = classify_comments.apply(args=([comment_id],))
    assert classify_result.result["classified"] == 1

    with SessionLocal() as db:
        stored_comment = db.query(Comment).filter(Comment.id == comment_id).one()
        assert stored_comment.sentiment_breakdown is not None
        assert stored_comment.sentiment_breakdown.get("models")
        assert math.isclose(stored_comment.sentiment_breakdown.get("combined_score"), 0.9, rel_tol=1e-6)

        aggregates = db.query(Aggregate).filter(Aggregate.thread_id == thread_id).all()
        assert aggregates, "Expected aggregates to be populated."
        overall = next((agg for agg in aggregates if agg.cast_member_id == cast_id and agg.time_window == "overall"), None)
        assert overall is not None
        assert overall.mention_count == 1

    response = _client.get(f"/api/v1/threads/{thread_id}/cast")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_mentions"] == 1
    assert payload["cast"][0]["cast_slug"] == "jane-doe"
    assert payload["cast"][0]["overall"]["mention_count"] == 1


def test_reply_inherits_parent_mentions(
    pipeline_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, SessionLocal = pipeline_client

    class FakePipeline:
        def analyze_comment(self, text: str) -> SentimentAnalysisResult:
            final = NormalizedSentiment(
                cast_member_id=None,
                cast_member=None,
                sentiment_label="positive",
                sentiment_score=0.8,
                source_model="fake-primary",
                reasoning="Primary model confidence 80%.",
            )
            models = [
                ModelSentiment(
                    name="fake-primary",
                    sentiment_label="positive",
                    sentiment_score=0.8,
                    reasoning="Primary model confidence 80%.",
                )
            ]
            return SentimentAnalysisResult(final=final, models=models, combined_score=0.8)

        def analyze_mentions(
            self,
            comment_text: str,
            candidates: list[MentionCandidate],
            contexts: list[str],
            catalog: dict[int, object],
        ) -> list[NormalizedSentiment]:
            results: list[NormalizedSentiment] = []
            for candidate in candidates:
                entry = catalog.get(candidate.cast_member_id)
                cast_name = getattr(entry, "canonical_name", None)
                results.append(
                    NormalizedSentiment(
                        cast_member_id=candidate.cast_member_id,
                        cast_member=cast_name,
                        sentiment_label="positive",
                        sentiment_score=0.75,
                        source_model="fake-primary",
                        reasoning="Primary model confidence 75%.",
                    )
                )
            return results

    class FakeLinker:
        def __init__(self, catalog) -> None:
            self.catalog = list(catalog)

        def find_mentions(self, text: str) -> list[MentionCandidate]:
            text_lower = text.lower()
            if not self.catalog:
                return []
            cast_id = self.catalog[0].cast_member_id
            if "jane doe" in text_lower:
                return [
                    MentionCandidate(
                        cast_member_id=cast_id,
                        confidence=0.95,
                        method="exact",
                        quote="Jane Doe",
                    )
                ]
            return []

    monkeypatch.setattr(ml_tasks, "get_sentiment_pipeline", lambda *_args, **_kwargs: FakePipeline())
    monkeypatch.setattr(ml_tasks, "EntityLinker", lambda catalog: FakeLinker(catalog))

    def immediate_link_entities(comment_ids: list[int]) -> None:
        ml_tasks.link_entities.apply(args=(comment_ids,))

    monkeypatch.setattr(ml_tasks.link_entities, "delay", immediate_link_entities)

    def immediate_apply_async(*_call_args, **call_kwargs) -> None:
        task_args = call_kwargs.get("args") or []
        comment_ids_arg = task_args[0] if task_args else []
        immediate_link_entities(comment_ids_arg)

    monkeypatch.setattr(ml_tasks.link_entities, "apply_async", immediate_apply_async)

    def immediate_compute(thread_id: int) -> None:
        compute_aggregates.apply(args=(thread_id,))

    monkeypatch.setattr(analytics_tasks.compute_aggregates, "delay", immediate_compute)
    monkeypatch.setattr(ml_tasks, "compute_aggregates", analytics_tasks.compute_aggregates)
    monkeypatch.setattr(alerts_tasks.check_alerts, "delay", lambda _thread_id: None)

    with SessionLocal() as db:
        thread = Thread(
            reddit_id="abc123",
            subreddit="bravo",
            title="Episode Night",
            url="https://reddit.com/r/bravo/comments/abc123",
            air_time_utc=dt.datetime(2024, 1, 1, 1, tzinfo=dt.timezone.utc),
            created_utc=dt.datetime(2024, 1, 1, 0, tzinfo=dt.timezone.utc),
            status=ThreadStatus.LIVE,
            total_comments=0,
        )
        db.add(thread)
        db.flush()

        cast = CastMember(slug="jane-doe", full_name="Jane Doe", show="Bravo Show")
        db.add(cast)
        db.flush()

        now = dt.datetime.now(dt.timezone.utc)
        parent_comment = Comment(
            id=10,
            thread_id=thread.id,
            reddit_id="cparent",
            author_hash="hash",
            body="Jane Doe absolutely owned the episode tonight!",
            created_utc=now,
            score=4,
            parent_id=None,
            reply_count=1,
            time_window="live",
            created_at=now,
            updated_at=now,
        )
        db.add(parent_comment)
        db.commit()
        parent_id = parent_comment.id
        thread_id = thread.id
        cast_id = cast.id

    classify_comments.apply(args=([parent_id],))

    with SessionLocal() as db:
        reply_time = dt.datetime.now(dt.timezone.utc)
        reply_comment = Comment(
            id=11,
            thread_id=thread.id,
            reddit_id="creply",
            author_hash="hash2",
            body="She was a total scene stealer again tonight.",
            created_utc=reply_time,
            score=2,
            parent_id="t1_cparent",
            reply_count=0,
            time_window="live",
            created_at=reply_time,
            updated_at=reply_time,
        )
        db.add(reply_comment)
        db.commit()
        reply_id = reply_comment.id

    classify_comments.apply(args=([reply_id],))

    with SessionLocal() as db:
        mentions = (
            db.query(Mention)
            .filter(Mention.comment_id == reply_id)
            .all()
        )
        assert mentions, "Expected inherited mention for reply comment"
        assert any(mention.cast_member_id == cast_id for mention in mentions)
        assert any(mention.method == "inherited_context" for mention in mentions)
        assert any((mention.sentiment_label or "").lower() == "positive" for mention in mentions)
