from __future__ import annotations

import datetime as dt
import json
import logging
import os
from collections import Counter
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models import Comment, RedditThread, Thread
from app.models.thread import ThreadStatus
from app.reddit.client import RedditClient
from app.services.hashing import hash_username
from app.services.storage import get_s3_storage
from app.services.time_window import determine_time_window

logger = logging.getLogger(__name__)

AUTO_ARCHIVE = os.getenv("AUTO_ARCHIVE_ON_IDLE", "false").lower() == "true"


class RedditIngestionService:
    def __init__(self, settings: Settings | None = None, session_factory: Callable[[], Session] | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = RedditClient(self.settings)
        self.storage = get_s3_storage()
        self._session_factory: Callable[[], Session] = session_factory or SessionLocal

    def ingest_thread(self, thread_id: str, subreddit: str) -> dict[str, Any]:
        submission = self.client.get_submission(thread_id)
        raw_payload = self.client.fetch_submission_raw(thread_id)

        s3_key = self._store_raw_payload(subreddit, thread_id, raw_payload)

        session = self._session_factory()
        try:
            reddit_thread = self._upsert_reddit_thread(session, submission, raw_payload, s3_key)
            thread = self._upsert_thread(session, submission, subreddit)
            comments_payload = self.client.fetch_comments(thread_id)
            comment_stats = self._persist_comments(session, thread, comments_payload)

            thread.total_comments = submission.num_comments or comment_stats["total"]
            now = dt.datetime.now(dt.timezone.utc)
            thread.last_polled_at = now
            latest_comment = _latest_comment_timestamp(comments_payload)
            if latest_comment:
                thread.latest_comment_utc = latest_comment
            elif not thread.latest_comment_utc:
                thread.latest_comment_utc = thread.created_utc
            self._apply_archive_policy(thread, now, submission=submission)
            result = {
                "thread_id": thread.id,
                "reddit_id": thread.reddit_id,
                "subreddit": thread.subreddit,
                "stored_comments": comment_stats["inserted"],
                "updated_comments": comment_stats.get("updated", 0),
                "skipped_comments": comment_stats["skipped"],
                "s3_key": s3_key,
                "reddit_thread_id": reddit_thread.id,
                "comment_ids": comment_stats.get("comment_ids", []),
                "poll_interval_seconds": thread.poll_interval_seconds,
                "thread_status": thread.status.value,
                "archived": thread.status == ThreadStatus.ARCHIVED,
                "should_schedule_poll": thread.status == ThreadStatus.LIVE,
            }
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("Database error while ingesting thread %s", thread_id)
            raise
        finally:
            session.close()

        return result

    def _store_raw_payload(self, subreddit: str, thread_id: str, payload: dict[str, Any]) -> str | None:
        timestamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        safe_subreddit = subreddit.strip().lower() or "unknown"
        key = f"reddit/{safe_subreddit}/{thread_id}/{timestamp}.json"
        try:
            return self.storage.put_json(key, payload)
        except Exception:
            logger.exception("Failed to archive raw Reddit payload for thread %s", thread_id)
            return None

    def _upsert_reddit_thread(self, session: Session, submission: Any, payload: dict[str, Any], s3_key: str | None) -> RedditThread:
        external_id = submission.id
        stmt = select(RedditThread).where(RedditThread.external_id == external_id)
        reddit_thread = session.execute(stmt).scalars().one_or_none()

        created_utc = dt.datetime.fromtimestamp(submission.created_utc, tz=dt.timezone.utc)
        raw_json = json.dumps({"payload": payload, "s3_key": s3_key}, ensure_ascii=False)

        data = {
            "external_id": external_id,
            "subreddit": getattr(submission.subreddit, "display_name", None) or "",
            "title": submission.title,
            "url": submission.url or f"https://reddit.com{submission.permalink}",
            "author": str(submission.author) if submission.author else None,
            "flair": getattr(submission, "link_flair_text", None),
            "score": submission.score or 0,
            "num_comments": submission.num_comments or 0,
            "is_archived": bool(getattr(submission, "archived", False)),
            "created_utc": created_utc,
            "raw_json": raw_json,
        }

        if reddit_thread:
            for field, value in data.items():
                setattr(reddit_thread, field, value)
        else:
            reddit_thread = RedditThread(**data)
            session.add(reddit_thread)
            session.flush()

        return reddit_thread

    def _upsert_thread(self, session: Session, submission: Any, subreddit: str) -> Thread:
        reddit_id = submission.id
        stmt = select(Thread).where(Thread.reddit_id == reddit_id)
        thread = session.execute(stmt).scalars().one_or_none()

        created_utc = dt.datetime.fromtimestamp(submission.created_utc, tz=dt.timezone.utc)
        air_time = getattr(thread, "air_time_utc", None) or created_utc
        url = submission.url or f"https://reddit.com{submission.permalink}"

        synopsis = None
        if submission.is_self and submission.selftext:
            synopsis = submission.selftext[:500]

        archived_flag = bool(getattr(submission, "archived", False))
        status = ThreadStatus.ARCHIVED if archived_flag else ThreadStatus.LIVE

        data = {
            "subreddit": subreddit or getattr(submission.subreddit, "display_name", None),
            "title": submission.title,
            "url": url,
            "air_time_utc": air_time,
            "created_utc": created_utc,
            "status": status,
            "total_comments": submission.num_comments or 0,
        }
        if synopsis:
            data["synopsis"] = synopsis

        if thread:
            for field, value in data.items():
                if field == "status":
                    continue
                setattr(thread, field, value)
            if archived_flag:
                thread.status = ThreadStatus.ARCHIVED
            elif thread.status not in (ThreadStatus.ARCHIVED, ThreadStatus.COMPLETED):
                thread.status = status
        else:
            thread = Thread(reddit_id=reddit_id, **data)
            session.add(thread)
            session.flush()

        return thread

    def _persist_comments(self, session: Session, thread: Thread, raw_comments: list[dict[str, Any]]) -> dict[str, int]:
        if not raw_comments:
            return {"inserted": 0, "skipped": 0, "total": 0, "comment_ids": []}

        reddit_ids = [comment["id"] for comment in raw_comments if comment.get("id")]
        existing_comments: dict[str, Comment] = {}
        if reddit_ids:
            stmt = (
                select(Comment)
                .where(Comment.thread_id == thread.id)
                .where(Comment.reddit_id.in_(reddit_ids))
            )
            existing_comments = {
                db_comment.reddit_id: db_comment for db_comment in session.execute(stmt).scalars().all()
            }
        existing_ids: set[str] = set(existing_comments.keys())

        parent_counter: Counter[str] = Counter()
        ancestor_ids: set[str] = set()
        inserted = 0
        updated = 0
        inserted_models: list[Comment] = []
        classification_ids: list[int] = []

        for comment in raw_comments:
            reddit_id = comment.get("id")
            if not reddit_id:
                continue

            created_utc = dt.datetime.fromtimestamp(comment.get("created_utc", 0), tz=dt.timezone.utc)
            existing = existing_comments.get(reddit_id)
            if existing:
                changed = False
                reclassify = False

                author_hash = hash_username(comment.get("author"))
                if author_hash != existing.author_hash:
                    existing.author_hash = author_hash
                    changed = True

                new_body = comment.get("body") or ""
                if new_body != existing.body:
                    existing.body = new_body
                    changed = True
                    reclassify = True

                new_score = int(comment.get("score") or 0)
                if new_score != existing.score:
                    existing.score = new_score
                    changed = True

                parent_id = comment.get("parent_id")
                normalized_parent = None
                if parent_id and parent_id.startswith("t1_"):
                    normalized_parent = parent_id.split("_", 1)[1]
                if normalized_parent != existing.parent_id:
                    existing.parent_id = normalized_parent
                    changed = True

                updated_time_window = determine_time_window(created_utc, thread.air_time_utc)
                if updated_time_window != existing.time_window:
                    existing.time_window = updated_time_window
                    changed = True

                if changed:
                    updated += 1
                    if existing.id is not None:
                        if reclassify:
                            classification_ids.append(existing.id)
                continue

            author_hash = hash_username(comment.get("author"))
            parent_id = comment.get("parent_id")
            normalized_parent = None
            if parent_id and parent_id.startswith("t1_"):
                normalized_parent = parent_id.split("_", 1)[1]
                parent_counter[normalized_parent] += 1
                ancestor_ids.add(normalized_parent)

            model = Comment(
                thread_id=thread.id,
                reddit_id=reddit_id,
                author_hash=author_hash,
                body=comment.get("body") or "",
                created_utc=created_utc,
                score=int(comment.get("score") or 0),
                parent_id=normalized_parent,
                time_window=determine_time_window(created_utc, thread.air_time_utc),
            )
            session.add(model)
            inserted += 1
            inserted_models.append(model)

        if inserted:
            session.flush()
            inserted_ids = [model.id for model in inserted_models if model.id is not None]
        else:
            inserted_ids = []

        if inserted_ids:
            classification_ids.extend(inserted_ids)

        ancestor_map: dict[str, Comment] = {}
        pending_ids = set(parent_counter.keys()) if parent_counter else set()
        pending_ids |= ancestor_ids

        while pending_ids:
            chunk = list(pending_ids)
            parent_stmt = (
                select(Comment)
                .where(Comment.thread_id == thread.id)
                .where(Comment.reddit_id.in_(chunk))
            )
            found_parents = session.execute(parent_stmt).scalars().all()
            next_ids: set[str] = set()
            for parent in found_parents:
                if parent.reddit_id in ancestor_map:
                    continue
                ancestor_map[parent.reddit_id] = parent
                if parent.parent_id:
                    next_ids.add(parent.parent_id)
            pending_ids = next_ids - set(ancestor_map.keys())

        for reddit_parent_id, increment in parent_counter.items():
            parent = ancestor_map.get(reddit_parent_id)
            if not parent:
                continue
            parent.reply_count = (parent.reply_count or 0) + increment

        if inserted_models and ancestor_map:
            for model in inserted_models:
                current_parent = model.parent_id
                while current_parent:
                    parent = ancestor_map.get(current_parent)
                    if not parent:
                        break
                    if parent.updated_at is None or parent.updated_at < model.created_utc:
                        parent.updated_at = model.created_utc
                    current_parent = parent.parent_id

        total = len(existing_ids) + inserted
        skipped = len(existing_ids) - updated
        comment_ids: list[int] = []
        if classification_ids:
            comment_ids = list(dict.fromkeys(classification_ids))
        return {
            "inserted": inserted,
            "updated": updated,
            "skipped": max(skipped, 0),
            "total": total,
            "comment_ids": comment_ids,
        }

    def poll_thread(self, thread_id: int) -> dict[str, Any]:
        session = self._session_factory()
        try:
            thread = session.get(Thread, thread_id)
            if not thread:
                raise ValueError(f"Thread {thread_id} not found.")
            if not thread.reddit_id:
                raise ValueError(f"Thread {thread_id} missing reddit_id.")

            now = dt.datetime.now(dt.timezone.utc)
            last_seen = thread.latest_comment_utc or thread.created_utc

            payload = self.client.fetch_comments(thread.reddit_id, return_submission=True)
            if isinstance(payload, tuple):
                comments_payload, submission = payload
            else:  # Backward compatibility guard
                comments_payload = payload
                submission = None
            new_comments: list[dict[str, Any]] = []
            for payload in comments_payload:
                created_utc = dt.datetime.fromtimestamp(payload.get("created_utc", 0), tz=dt.timezone.utc)
                if last_seen and created_utc <= last_seen:
                    continue
                new_comments.append(payload)

            stats = {"inserted": 0, "skipped": 0, "total": 0, "comment_ids": []}
            if new_comments:
                stats = self._persist_comments(session, thread, new_comments)
                latest_comment = _latest_comment_timestamp(new_comments)
                if latest_comment and (not thread.latest_comment_utc or latest_comment > thread.latest_comment_utc):
                    thread.latest_comment_utc = latest_comment
                thread.total_comments = (thread.total_comments or 0) + stats["inserted"]

            thread.last_polled_at = now
            archived_now = self._apply_archive_policy(thread, now, submission=submission)
            result = {
                "thread_id": thread.id,
                "reddit_id": thread.reddit_id,
                "inserted": stats["inserted"],
                "updated": stats.get("updated", 0),
                "skipped": stats["skipped"],
                "last_polled_at": now.isoformat(),
                "latest_comment_utc": thread.latest_comment_utc.isoformat() if thread.latest_comment_utc else None,
                "comment_ids": stats.get("comment_ids", []),
                "poll_interval_seconds": thread.poll_interval_seconds,
                "thread_status": thread.status.value,
                "archived": thread.status == ThreadStatus.ARCHIVED,
                "should_continue": thread.status == ThreadStatus.LIVE,
            }
            session.commit()
            return result
        except Exception:
            session.rollback()
            logger.exception("Incremental polling failed for thread %s", thread_id)
            raise
        finally:
            session.close()

    def _apply_archive_policy(
        self,
        thread: Thread,
        now: dt.datetime,
        submission: Any | None = None,
    ) -> bool:
        archived = False

        if submission is not None and bool(getattr(submission, "archived", False)):
            if thread.status != ThreadStatus.ARCHIVED:
                logger.info("Marking thread id=%s as archived (Reddit archived flag).", thread.id)
                thread.status = ThreadStatus.ARCHIVED
                archived = True
            else:
                return True

        if thread.status == ThreadStatus.ARCHIVED:
            return archived

        if not AUTO_ARCHIVE:
            if thread.status not in (ThreadStatus.COMPLETED, ThreadStatus.ARCHIVED):
                thread.status = ThreadStatus.LIVE
            return archived

        idle_minutes = int(getattr(self.settings, "thread_archive_idle_minutes", 0) or 0)
        if idle_minutes <= 0:
            return archived

        latest_activity = thread.latest_comment_utc or thread.created_utc
        if not latest_activity:
            return archived

        if now - latest_activity >= dt.timedelta(minutes=idle_minutes):
            logger.info(
                "Marking thread id=%s as archived after %s minutes without new comments.",
                thread.id,
                idle_minutes,
            )
            thread.status = ThreadStatus.ARCHIVED
            archived = True

        return archived


def _latest_comment_timestamp(raw_comments: list[dict[str, Any]]) -> dt.datetime | None:
    if not raw_comments:
        return None
    timestamps = [
        dt.datetime.fromtimestamp(comment.get("created_utc", 0), tz=dt.timezone.utc)
        for comment in raw_comments
        if comment.get("created_utc")
    ]
    if not timestamps:
        return None
    return max(timestamps)
