from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Comment, Mention, Thread

CSV_HEADERS = [
    "comment_id",
    "reddit_id",
    "parent_reddit_id",
    "thread_id",
    "author_hash",
    "body",
    "created_utc",
    "updated_at",
    "score",
    "reply_count",
    "time_window",
    "sentiment_label",
    "sentiment_score",
    "sentiment_combined_score",
    "sentiment_final_label",
    "sentiment_final_source",
    "sentiment_breakdown",
    "is_sarcastic",
    "sarcasm_confidence",
    "is_toxic",
    "toxicity_confidence",
    "mentions",
]


def generate_thread_comments_csv(session: Session, thread: Thread) -> tuple[str, bytes]:
    """Build a CSV export containing every stored comment for a thread."""
    stmt = (
        select(Comment)
        .options(selectinload(Comment.mentions).selectinload(Mention.cast_member))
        .where(Comment.thread_id == thread.id)
        .order_by(Comment.created_utc.asc(), Comment.id.asc())
    )
    comments = session.execute(stmt).scalars().unique().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADERS)

    for comment in comments:
        breakdown = comment.sentiment_breakdown if isinstance(comment.sentiment_breakdown, dict) else {}
        combined = breakdown.get("combined_score")
        final_label = breakdown.get("final_label")
        final_source = breakdown.get("final_source")

        mentions_payload = []
        for mention in comment.mentions:
            cast_member = getattr(mention, "cast_member", None)
            mentions_payload.append(
                {
                    "cast_slug": getattr(cast_member, "slug", None),
                    "cast_name": getattr(cast_member, "full_name", None),
                    "sentiment_label": mention.sentiment_label,
                    "sentiment_score": mention.sentiment_score,
                    "quote": mention.quote,
                }
            )

        writer.writerow(
            [
                comment.id,
                comment.reddit_id,
                comment.parent_id or "",
                thread.id,
                comment.author_hash or "",
                comment.body,
                _format_datetime(comment.created_utc),
                _format_datetime(comment.updated_at),
                comment.score,
                comment.reply_count,
                comment.time_window or "",
                comment.sentiment_label or "",
                _format_float(comment.sentiment_score),
                _format_float(combined),
                final_label or "",
                final_source or "",
                _serialize_json(breakdown),
                "true" if comment.is_sarcastic else "false",
                _format_float(comment.sarcasm_confidence),
                "true" if comment.is_toxic else "false",
                _format_float(comment.toxicity_confidence),
                _serialize_json(mentions_payload),
            ]
        )

    content = buffer.getvalue().encode("utf-8")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"thread-{thread.id}-comments-{timestamp}.csv"
    return filename, content


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
        iso = value.isoformat()
        return iso.replace("+00:00", "Z")
    return value.isoformat()


def _format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}"


def _serialize_json(value: object) -> str:
    if not value:
        return ""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
