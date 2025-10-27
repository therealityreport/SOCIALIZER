from __future__ import annotations

import pytest

from app.tasks import ingestion as ingestion_tasks


def test_fetch_thread_triggers_classification_and_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    events: dict[str, object] = {}

    class FakeService:
        def __init__(self) -> None:
            self.args: tuple[str, str] | None = None

        def ingest_thread(self, thread_id: str, subreddit: str) -> dict[str, object]:
            self.args = (thread_id, subreddit)
            return {
                "thread_id": 123,
                "reddit_id": thread_id,
                "stored_comments": 2,
                "skipped_comments": 0,
                "comment_ids": [101, 102],
                "poll_interval_seconds": 30,
                "should_schedule_poll": True,
            }

    fake_service = FakeService()
    monkeypatch.setattr(ingestion_tasks, "RedditIngestionService", lambda: fake_service)
    monkeypatch.setattr(
        ingestion_tasks.classify_comments,
        "delay",
        lambda comment_ids: events.setdefault("classify", comment_ids),
    )
    monkeypatch.setattr(
        ingestion_tasks.classify_comments,
        "apply_async",
        lambda args=None, **_kwargs: events.setdefault("classify", args[0] if args else None),
    )

    def fake_apply_async(*, args=None, countdown=None, **kwargs) -> None:
        events["poll"] = {"args": args, "countdown": countdown}

    monkeypatch.setattr(ingestion_tasks.poll_thread, "apply_async", fake_apply_async)

    result = ingestion_tasks.fetch_thread.apply(args=("abc123", "bravo"))

    assert fake_service.args == ("abc123", "bravo")
    assert events["classify"] == [101, 102]
    assert events["poll"]["args"] == [123]
    assert events["poll"]["countdown"] == 30
    assert result.result["comment_ids"] == [101, 102]


def test_poll_thread_triggers_follow_up_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    events: dict[str, object] = {}

    class FakeService:
        def poll_thread(self, thread_db_id: int) -> dict[str, object]:
            events["service_call"] = thread_db_id
            return {
                "thread_id": thread_db_id,
                "reddit_id": "abc123",
                "inserted": 1,
                "skipped": 0,
                "comment_ids": [201],
                "poll_interval_seconds": 45,
                "should_continue": True,
            }

    monkeypatch.setattr(ingestion_tasks, "RedditIngestionService", lambda: FakeService())
    monkeypatch.setattr(
        ingestion_tasks.classify_comments,
        "delay",
        lambda comment_ids: events.setdefault("classify", comment_ids),
    )
    monkeypatch.setattr(
        ingestion_tasks.classify_comments,
        "apply_async",
        lambda args=None, **_kwargs: events.setdefault("classify", args[0] if args else None),
    )

    def fake_apply_async(*, args=None, countdown=None, **kwargs) -> None:
        events["reschedule"] = {"args": args, "countdown": countdown}

    monkeypatch.setattr(ingestion_tasks.poll_thread, "apply_async", fake_apply_async)

    result = ingestion_tasks.poll_thread.apply(args=(321,))

    assert events["service_call"] == 321
    assert events["classify"] == [201]
    assert events["reschedule"]["args"] == [321]
    assert events["reschedule"]["countdown"] == 45
    assert result.result["comment_ids"] == [201]


def test_poll_thread_stops_when_not_continuing(monkeypatch: pytest.MonkeyPatch) -> None:
    events: dict[str, object] = {}

    class FakeService:
        def poll_thread(self, thread_db_id: int) -> dict[str, object]:
            return {
                "thread_id": thread_db_id,
                "reddit_id": "abc123",
                "inserted": 0,
                "skipped": 0,
                "comment_ids": [],
                "poll_interval_seconds": 60,
                "should_continue": False,
            }

    monkeypatch.setattr(ingestion_tasks, "RedditIngestionService", lambda: FakeService())
    monkeypatch.setattr(
        ingestion_tasks.classify_comments,
        "delay",
        lambda comment_ids: events.setdefault("classify", comment_ids),
    )
    monkeypatch.setattr(
        ingestion_tasks.classify_comments,
        "apply_async",
        lambda args=None, **_kwargs: events.setdefault("classify", args[0] if args else None),
    )

    def fake_apply_async(*, args=None, countdown=None, **kwargs) -> None:
        events["reschedule"] = {"args": args, "countdown": countdown}

    monkeypatch.setattr(ingestion_tasks.poll_thread, "apply_async", fake_apply_async)

    result = ingestion_tasks.poll_thread.apply(args=(999,))

    assert result.result["comment_ids"] == []
    assert "classify" not in events
    assert "reschedule" not in events
