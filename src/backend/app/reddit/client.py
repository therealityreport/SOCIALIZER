from __future__ import annotations

import logging
from typing import Any

import praw
from praw.exceptions import APIException, ClientException
from prawcore import OAuthException, ResponseException
from tenacity import RetryCallState, retry, retry_if_exception_type, stop_after_attempt

from app.core.config import Settings, get_settings
from app.core.redis import get_redis_client
from app.reddit.rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)


class RedditRateLimitError(Exception):
    """Raised when Reddit responds with HTTP 429."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after or 0.0
        super().__init__(f"Rate limited by Reddit. Retry after {self.retry_after:.2f}s")


def wait_for_rate_limit(retry_state: RetryCallState) -> float:
    """Custom wait strategy respecting Retry-After headers when available."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, RedditRateLimitError) and exc.retry_after:
        return max(exc.retry_after, 1.0)
    attempt = retry_state.attempt_number
    return min(30.0, 2 ** (attempt - 1))


class RedditClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.redis = get_redis_client()
        self.rate_limiter = RedisRateLimiter(
            redis_client=self.redis,
            max_calls=self.settings.reddit_rate_limit_calls,
            period=self.settings.reddit_rate_limit_period,
        )
        self.client = praw.Reddit(
            client_id=self.settings.reddit_client_id,
            client_secret=self.settings.reddit_client_secret,
            user_agent=self.settings.reddit_user_agent,
            username=self.settings.reddit_username or None,
            password=self.settings.reddit_password or None,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_for_rate_limit,
        retry=retry_if_exception_type(
            (
                APIException,
                ClientException,
                OAuthException,
                ResponseException,
                RedditRateLimitError,
            )
        ),
        reraise=True,
    )
    def get_submission(self, submission_id: str) -> Any:
        self.rate_limiter.acquire()
        try:
            submission = self.client.submission(id=submission_id)
            submission._fetch()  # Ensure full payload is hydrated.
            return submission
        except ResponseException as exc:
            if self._is_rate_limit(exc):
                self._handle_rate_limit(exc)
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_for_rate_limit,
        retry=retry_if_exception_type(
            (
                APIException,
                ClientException,
                OAuthException,
                ResponseException,
                RedditRateLimitError,
            )
        ),
        reraise=True,
    )
    def fetch_submission_raw(self, submission_id: str) -> dict[str, Any]:
        """Return the raw JSON payload for the submission."""
        self.rate_limiter.acquire()
        try:
            response = self.client.request(
                method="GET",
                path="/api/info",
                params={"id": f"t3_{submission_id}", "raw_json": 1},
            )
        except ResponseException as exc:
            if self._is_rate_limit(exc):
                self._handle_rate_limit(exc)
            raise
        if isinstance(response, dict):
            return response
        raise ValueError("Unexpected response from Reddit API")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_for_rate_limit,
        retry=retry_if_exception_type(
            (
                APIException,
                ClientException,
                OAuthException,
                ResponseException,
                RedditRateLimitError,
            )
        ),
        reraise=True,
    )
    def fetch_comments(
        self,
        submission_id: str,
        *,
        return_submission: bool = False,
    ) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], Any]:
        submission = self.get_submission(submission_id)
        try:
            self.rate_limiter.acquire()
            submission.comments.replace_more(limit=None)
        except ResponseException as exc:
            if self._is_rate_limit(exc):
                self._handle_rate_limit(exc)
            raise

        comments = []
        for comment in submission.comments.list():
            comments.append(
                {
                    "id": comment.id,
                    "author": str(comment.author) if comment.author else "[deleted]",
                    "body": comment.body,
                    "score": comment.score,
                    "created_utc": comment.created_utc,
                    "parent_id": comment.parent_id,
                }
            )
        if return_submission:
            return comments, submission
        return comments

    def _is_rate_limit(self, exc: ResponseException) -> bool:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        return status == 429

    def _handle_rate_limit(self, exc: ResponseException) -> None:
        retry_after = self._extract_retry_after(exc)
        if retry_after:
            logger.warning("Reddit rate limited request; retrying after %ss", retry_after)
            self.rate_limiter.block_for(retry_after)
        raise RedditRateLimitError(retry_after=retry_after) from exc

    @staticmethod
    def _extract_retry_after(exc: ResponseException) -> float | None:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", {}) or {}
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except (TypeError, ValueError):
                logger.debug("Retry-After header not numeric: %s", retry_after)
        return None
