from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Callable

import pytest

from app.models.thread import Thread, ThreadStatus
from app.services.reddit_ingestion import RedditIngestionService


class _FakeSession:
    def __init__(self, thread: Thread) -> None:
        self._thread = thread
        self.closed = False
        self.committed = False
        self.rolled_back = False
        self.execute_results: list[list[object]] = []

    def get(self, model: type[Thread], identifier: int) -> Thread | None:
        if model is Thread and self._thread.id == identifier:
            return self._thread
        return None

    def add(self, instance) -> None:  # pragma: no cover - compatibility no-op
        del instance

    def flush(self) -> None:  # pragma: no cover - compatibility no-op
        return

    def execute(self, *args, **kwargs):
        values: list[object]
        if self.execute_results:
            values = self.execute_results.pop(0)
        else:
            values = []

        class _FakeScalarResult:
            def __init__(self, items: list[object]) -> None:
                self._items = list(items)

            def all(self) -> list[object]:
                return list(self._items)

            def one_or_none(self) -> object | None:
                if not self._items:
                    return None
                if len(self._items) == 1:
                    return self._items[0]
                raise AssertionError("Expected at most one result")

            def first(self) -> object | None:
                return self._items[0] if self._items else None

            def __iter__(self):
                return iter(self._items)

        class _FakeResult:
            def __init__(self, items: list[object]) -> None:
                self._items = items

            def scalars(self) -> _FakeScalarResult:
                return _FakeScalarResult(self._items)

        return _FakeResult(values)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def _make_thread(thread_id: int, created: dt.datetime, latest_comment: dt.datetime) -> Thread:
    thread = Thread(
        reddit_id="abc123",
        subreddit="bravo",
        title="Test Thread",
        url="https://reddit.com/r/bravo/test",
        air_time_utc=created,
        created_utc=created,
        status=ThreadStatus.LIVE,
        total_comments=1,
    )
    thread.id = thread_id
    thread.latest_comment_utc = latest_comment
    thread.last_polled_at = created
    return thread


def test_incremental_poll_inserts_only_new_comments(monkeypatch: pytest.MonkeyPatch) -> None:
    base_time = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
    newest_existing = base_time + dt.timedelta(minutes=5)
    thread = _make_thread(thread_id=42, created=base_time, latest_comment=newest_existing)

    new_comment_time = newest_existing + dt.timedelta(minutes=2)
    payload = [
        {"id": "old1", "created_utc": newest_existing.timestamp(), "author": "user", "body": "old", "score": 1},
        {"id": "new1", "created_utc": new_comment_time.timestamp(), "author": "user2", "body": "new", "score": 2},
    ]

    inserted_counts: dict[str, int] = {}

    def fake_persist(self, session, thread_obj, comments):
        inserted_counts["count"] = len(comments)
        return {"inserted": len(comments), "skipped": 0, "total": len(comments)}

    fake_session = _FakeSession(thread)

    def session_factory() -> _FakeSession:
        return fake_session

    service = RedditIngestionService(session_factory=session_factory)
    service.client = SimpleNamespace(fetch_comments=lambda *_args, **_kwargs: payload)
    monkeypatch.setattr(RedditIngestionService, "_persist_comments", fake_persist, raising=False)

    result = service.poll_thread(thread.id)

    assert inserted_counts["count"] == 1
    assert result["inserted"] == 1
    assert thread.latest_comment_utc == new_comment_time
    assert thread.total_comments == 2
    assert fake_session.committed is True
    assert fake_session.closed is True
    assert thread.last_polled_at is not None


def test_incremental_poll_updates_existing_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    base_time = dt.datetime(2024, 2, 1, 0, 0, tzinfo=dt.timezone.utc)
    thread = _make_thread(thread_id=99, created=base_time, latest_comment=base_time)

    existing_comment = SimpleNamespace(
        id=555,
        reddit_id="c123",
        author_hash=None,
        body="Original body",
        created_utc=base_time,
        score=3,
        parent_id=None,
        reply_count=0,
        time_window="live",
        updated_at=base_time,
    )

    payload = [
        {
            "id": "c123",
            "created_utc": base_time.timestamp(),
            "author": "user2",
            "body": "Edited body",
            "score": 7,
            "parent_id": None,
        }
    ]

    fake_session = _FakeSession(thread)
    fake_session.execute_results = [[existing_comment]]

    def session_factory() -> _FakeSession:
        return fake_session

    service = RedditIngestionService(session_factory=session_factory)
    service.client = SimpleNamespace(fetch_comments=lambda *_args, **_kwargs: payload)

    result = service.poll_thread(thread.id)

    assert result["inserted"] == 0
    assert result["updated"] == 1
    assert result["comment_ids"] == [existing_comment.id]
    assert existing_comment.body == "Edited body"
    assert existing_comment.score == 7
    assert thread.total_comments == 1
    assert fake_session.committed is True
    assert fake_session.closed is True
