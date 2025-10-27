from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

import pytest
from prawcore import ResponseException

from app.reddit.client import RedditClient, RedditRateLimitError


class DummyLimiter:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.acquire_calls = 0
        self.block_calls: list[float] = []

    def acquire(self) -> None:
        self.acquire_calls += 1

    def block_for(self, seconds: float) -> None:
        self.block_calls.append(seconds)


class FakeComments:
    def __init__(self, values: list[Any]) -> None:
        self._values = values
        self.replace_more_called = False

    def replace_more(self, limit: int | None = None) -> None:
        self.replace_more_called = True

    def list(self) -> list[Any]:
        return self._values


class FakeSubmission:
    def __init__(self, comments: FakeComments) -> None:
        self.comments = comments
        self.fetch_called = False

    def _fetch(self) -> None:
        self.fetch_called = True


class FakeReddit:
    def __init__(
        self,
        submission_factory: Callable[[str], FakeSubmission],
        request_handler: Callable[..., Any],
    ) -> None:
        self._submission_factory = submission_factory
        self._request_handler = request_handler
        self.submission_calls: list[str] = []
        self.request_calls: list[tuple[str, str, dict[str, Any]]] = []

    def submission(self, id: str) -> FakeSubmission:
        self.submission_calls.append(id)
        return self._submission_factory(id)

    def request(self, *, method: str, path: str, params: dict[str, Any]) -> Any:
        self.request_calls.append((method, path, params))
        return self._request_handler(method=method, path=path, params=params)


def _make_settings() -> SimpleNamespace:
    return SimpleNamespace(
        reddit_client_id="client",
        reddit_client_secret="secret",
        reddit_user_agent="agent",
        reddit_username="",
        reddit_password="",
        reddit_rate_limit_calls=10,
        reddit_rate_limit_period=60,
    )


def _build_client(monkeypatch: pytest.MonkeyPatch, submission: FakeSubmission, request_handler: Callable[..., Any]) -> tuple[RedditClient, DummyLimiter]:
    limiter = DummyLimiter()
    fake_reddit = FakeReddit(lambda _id: submission, request_handler)

    monkeypatch.setattr("app.reddit.client.RedisRateLimiter", lambda *args, **kwargs: limiter)
    monkeypatch.setattr("app.reddit.client.get_redis_client", lambda: object())
    monkeypatch.setattr("app.reddit.client.get_settings", _make_settings)
    monkeypatch.setattr("app.reddit.client.wait_for_rate_limit", lambda state: 0.0)
    monkeypatch.setattr("app.reddit.client.praw.Reddit", lambda **kwargs: fake_reddit)

    client = RedditClient()
    return client, limiter


def _make_rate_limit_exception(status_code: int = 429, retry_after: str | None = "4") -> ResponseException:
    response = SimpleNamespace(status_code=status_code, headers={"Retry-After": retry_after} if retry_after else {})
    return ResponseException(response=response)


def test_get_submission_fetches_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    comments = FakeComments([])
    submission = FakeSubmission(comments=comments)

    client, limiter = _build_client(monkeypatch, submission, request_handler=lambda **_: {})

    result = client.get_submission("abc123")

    assert result is submission
    assert submission.fetch_called is True
    assert limiter.acquire_calls == 1  # acquire called before hitting Reddit


def test_fetch_submission_raw_returns_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    comments = FakeComments([])
    submission = FakeSubmission(comments=comments)
    payload = {"data": "value"}

    client, _ = _build_client(monkeypatch, submission, request_handler=lambda **_: payload)

    response = client.fetch_submission_raw("xyz789")
    assert response == payload


def test_fetch_submission_raw_raises_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    comments = FakeComments([])
    submission = FakeSubmission(comments=comments)
    attempts = {"count": 0}

    def raising_request(**_: Any) -> Any:
        attempts["count"] += 1
        raise _make_rate_limit_exception()

    client, limiter = _build_client(monkeypatch, submission, request_handler=raising_request)

    with pytest.raises(RedditRateLimitError) as excinfo:
        client.fetch_submission_raw("limited")

    assert attempts["count"] == 3  # retry decorator exhausts attempts
    assert limiter.block_calls  # limiter informed of block window
    assert excinfo.value.retry_after == pytest.approx(4.0)


def test_fetch_comments_hydrates_comment_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    comment_objects = [
        SimpleNamespace(id="c1", author="user1", body="Great episode!", score=10, created_utc=1700000000, parent_id="t3_thread"),
        SimpleNamespace(id="c2", author=None, body="Controversial take", score=-2, created_utc=1700001000, parent_id="c1"),
    ]
    comments = FakeComments(comment_objects)
    submission = FakeSubmission(comments=comments)

    client, limiter = _build_client(monkeypatch, submission, request_handler=lambda **_: {})

    result = client.fetch_comments("thread123")

    assert limiter.acquire_calls >= 2  # once for submission fetch, once before replace_more
    assert comments.replace_more_called is True
    assert result == [
        {
            "id": "c1",
            "author": "user1",
            "body": "Great episode!",
            "score": 10,
            "created_utc": 1700000000,
            "parent_id": "t3_thread",
        },
        {
            "id": "c2",
            "author": "[deleted]",
            "body": "Controversial take",
            "score": -2,
            "created_utc": 1700001000,
            "parent_id": "c1",
        },
    ]
