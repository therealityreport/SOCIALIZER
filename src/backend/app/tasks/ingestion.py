from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from app.services.reddit_ingestion import RedditIngestionService
from app.tasks.ml import classify_comments

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="app.tasks.ingestion.fetch_thread", queue="ingestion")
def fetch_thread(self, thread_id: str, subreddit: str) -> dict[str, Any]:
    logger.info("Starting Reddit ingestion for thread %s (%s)", thread_id, subreddit)
    service = RedditIngestionService()
    result = service.ingest_thread(thread_id=thread_id, subreddit=subreddit)
    logger.info(
        "Completed Reddit ingestion for %s: stored=%s updated=%s skipped=%s",
        thread_id,
        result.get("stored_comments"),
        result.get("updated_comments", 0),
        result.get("skipped_comments"),
    )
    comment_ids = result.get("comment_ids") or []
    if comment_ids:
        logger.info("Queueing ML classification for %s new comments", len(comment_ids))
        classify_comments.apply_async(args=[comment_ids], queue="ml")

    if result.get("should_schedule_poll"):
        poll_interval = max(1, int(result.get("poll_interval_seconds") or 60))
        thread_db_id = result.get("thread_id")
        if thread_db_id:
            logger.info("Scheduling poll_thread in %s seconds for thread id=%s", poll_interval, thread_db_id)
            poll_thread.apply_async(args=[thread_db_id], countdown=poll_interval, queue="ingestion")
    return result


@shared_task(bind=True, name="app.tasks.ingestion.poll_thread", queue="ingestion")
def poll_thread(self, thread_db_id: int) -> dict[str, Any]:
    logger.info("Polling thread id=%s for incremental updates", thread_db_id)
    service = RedditIngestionService()
    result = service.poll_thread(thread_db_id)
    logger.info(
        "Completed poll for thread id=%s: inserted=%s updated=%s skipped=%s",
        thread_db_id,
        result.get("inserted"),
        result.get("updated", 0),
        result.get("skipped"),
    )
    comment_ids = result.get("comment_ids") or []
    if comment_ids:
        logger.info("Queueing ML classification for %s new comments (poll)", len(comment_ids))
        classify_comments.apply_async(args=[comment_ids], queue="ml")

    if result.get("should_continue"):
        poll_interval = max(1, int(result.get("poll_interval_seconds") or 60))
        logger.info("Rescheduling poll_thread in %s seconds for thread id=%s", poll_interval, thread_db_id)
        poll_thread.apply_async(args=[thread_db_id], countdown=poll_interval, queue="ingestion")
    return result
