from __future__ import annotations

import datetime as dt
from typing import Dict, Sequence

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api import deps
from app.models import CastMember, Comment, Mention, Thread
from app.schemas.analytics import ThreadInsightsResponse
from app.schemas.comment import CommentListResponse, CommentMentionRead, CommentRead
from app.schemas.thread import ThreadCreate, ThreadLookupResponse, ThreadRead, ThreadUpdate
from app.services.discussion_insights import generate_thread_insights
from app.tasks.analytics import compute_aggregates
from app.tasks.ingestion import fetch_thread, poll_thread
from app.tasks.ml import link_entities
from app.reddit.client import RedditClient, RedditRateLimitError

router = APIRouter(prefix="/threads", tags=["threads"])

_poll_request_cache: Dict[int, dt.datetime] = {}


def _extract_submission_id(reddit_url: str) -> tuple[str, str | None]:
    parsed = urlparse(reddit_url)
    if not parsed.netloc.endswith("reddit.com"):
        raise ValueError("URL must point to reddit.com")
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        raise ValueError("Invalid Reddit URL")
    try:
        if segments[0] == "r" and len(segments) >= 4 and segments[2] == "comments":
            subreddit = segments[1]
            submission_id = segments[3] if len(segments) > 3 else None
        elif segments[0] == "comments" and len(segments) >= 2:
            subreddit = None
            submission_id = segments[1]
        else:
            raise ValueError
    except ValueError as exc:
        raise ValueError("Unable to extract submission id from URL") from exc

    if not submission_id:
        raise ValueError("Missing submission id in URL")
    return submission_id, subreddit


@router.post("", response_model=ThreadRead, status_code=status.HTTP_201_CREATED)
def create_thread(thread_in: ThreadCreate, db: Session = Depends(deps.get_db)) -> Thread:
    thread = Thread(
        reddit_id=thread_in.reddit_id,
        subreddit=thread_in.subreddit,
        title=thread_in.title,
        url=thread_in.url,
        air_time_utc=thread_in.air_time_utc,
        created_utc=thread_in.created_utc,
        status=thread_in.status,
        total_comments=thread_in.total_comments,
        synopsis=thread_in.synopsis,
    )
    db.add(thread)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thread with this reddit_id already exists.") from exc
    db.refresh(thread)
    subreddit = thread.subreddit or thread_in.subreddit or ""
    fetch_thread.delay(thread.reddit_id, subreddit)
    return thread


@router.get("", response_model=list[ThreadRead])
def list_threads(
    db: Session = Depends(deps.get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> Sequence[Thread]:
    threads = (
        db.query(Thread)
        .order_by(Thread.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return threads


@router.get("/{thread_id}", response_model=ThreadRead)
def get_thread(thread_id: int, db: Session = Depends(deps.get_db)) -> Thread:
    thread = db.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")
    _schedule_poll_if_stale(thread)
    return thread


@router.get("/lookup", response_model=ThreadLookupResponse)
def lookup_thread(reddit_url: str = Query(..., alias="url")) -> ThreadLookupResponse:
    try:
        submission_id, subreddit_hint = _extract_submission_id(reddit_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    client = RedditClient()
    try:
        submission = client.get_submission(submission_id)
    except RedditRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to fetch Reddit submission.") from exc

    created_utc = dt.datetime.fromtimestamp(submission.created_utc, tz=dt.timezone.utc)
    synopsis = submission.selftext or None
    if synopsis:
        synopsis = synopsis.strip()[:500] or None

    canonical_url = f"https://www.reddit.com{submission.permalink}" if getattr(submission, "permalink", None) else reddit_url
    subreddit = getattr(submission.subreddit, "display_name", None) or subreddit_hint

    return ThreadLookupResponse(
        reddit_id=submission.id,
        subreddit=subreddit,
        title=submission.title,
        url=canonical_url,
        created_utc=created_utc,
        air_time_utc=created_utc,
        num_comments=int(getattr(submission, "num_comments", 0) or 0),
        synopsis=synopsis,
    )


@router.put("/{thread_id}", response_model=ThreadRead)
def update_thread(thread_id: int, thread_in: ThreadUpdate, db: Session = Depends(deps.get_db)) -> Thread:
    thread = db.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")

    update_data = thread_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(thread, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Update violates constraints.") from exc
    db.refresh(thread)
    return thread


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_thread(thread_id: int, db: Session = Depends(deps.get_db)) -> Response:
    thread = db.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")
    db.delete(thread)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


SORT_ORDER = {
    "new": (Comment.updated_at.desc(), Comment.created_utc.desc(), Comment.id.desc()),
    "old": (Comment.updated_at.asc(), Comment.created_utc.asc(), Comment.id.asc()),
    "latest": (Comment.updated_at.desc(), Comment.created_utc.desc(), Comment.id.desc()),
    "most_replies": (Comment.reply_count.desc(), Comment.created_utc.desc()),
    "most_upvotes": (Comment.score.desc(), Comment.created_utc.desc()),
    "most_likes": (Comment.score.desc(), Comment.created_utc.desc()),
    "sentiment_desc": (Comment.sentiment_score.desc(), Comment.created_utc.desc(), Comment.id.desc()),
    "sentiment_asc": (Comment.sentiment_score.asc(), Comment.created_utc.desc(), Comment.id.desc()),
}


@router.get("/{thread_id}/comments", response_model=CommentListResponse)
def list_thread_comments(
    thread_id: int,
    cast_slug: str | None = Query(default=None),
    sort: str = Query(default="new"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    unassigned_only: bool = Query(default=False),
    db: Session = Depends(deps.get_db),
) -> CommentListResponse:
    thread = db.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")
    _schedule_poll_if_stale(thread)

    sort_key = sort.lower()
    if sort_key not in SORT_ORDER:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sort option.")

    order_clauses = SORT_ORDER[sort_key]

    if cast_slug and unassigned_only:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot combine cast slug with unassigned filter.")

    filters_query = select(
        Comment.id,
        Comment.created_utc,
        Comment.updated_at,
        Comment.reply_count,
        Comment.score,
    ).where(Comment.thread_id == thread_id)

    if cast_slug:
        filters_query = filters_query.where(
            Comment.id.in_(
                select(Mention.comment_id)
                .join(Mention.cast_member)
                .where(CastMember.slug == cast_slug)
            )
        )

    if unassigned_only:
        mention_exists = (
            select(Mention.id)
            .where(Mention.comment_id == Comment.id)
            .limit(1)
            .exists()
        )
        filters_query = filters_query.where(~mention_exists)

    count_stmt = select(func.count()).select_from(filters_query.subquery())

    paged_ids = filters_query.order_by(*order_clauses).offset(offset).limit(limit).subquery()

    comments_stmt = (
        select(Comment)
        .join(paged_ids, Comment.id == paged_ids.c.id)
        .options(selectinload(Comment.mentions).selectinload(Mention.cast_member))
        .order_by(*order_clauses)
    )

    total = db.scalar(count_stmt) or 0
    comments = db.scalars(comments_stmt).unique().all()

    payload = [
        _serialize_comment(db, comment, cast_slug=cast_slug)
        for comment in comments
    ]

    return CommentListResponse(comments=payload, total=total, limit=limit, offset=offset)


@router.get("/{thread_id}/insights", response_model=ThreadInsightsResponse)
def get_thread_insights(thread_id: int, db: Session = Depends(deps.get_db)) -> ThreadInsightsResponse:
    thread = db.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")
    return generate_thread_insights(db, thread)


@router.post("/{thread_id}/reanalyze", status_code=status.HTTP_202_ACCEPTED)
def reanalyze_thread(thread_id: int, db: Session = Depends(deps.get_db)) -> dict[str, object]:
    thread = db.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")

    comment_ids = db.scalars(select(Comment.id).where(Comment.thread_id == thread_id)).all()
    if not comment_ids:
        return {"status": "scheduled", "comment_count": 0}

    chunk_size = 500
    for index in range(0, len(comment_ids), chunk_size):
        chunk = comment_ids[index : index + chunk_size]
        link_entities.apply_async(args=[chunk], queue="ml")

    compute_aggregates.delay(thread_id)
    return {"status": "scheduled", "comment_count": len(comment_ids)}


def _schedule_poll_if_stale(thread: Thread) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    last_polled = thread.last_polled_at
    poll_interval = max(thread.poll_interval_seconds, 30)

    if last_polled and now - last_polled < dt.timedelta(seconds=poll_interval):
        return

    last_requested = _poll_request_cache.get(thread.id)
    if last_requested and now - last_requested < dt.timedelta(seconds=poll_interval):
        return

    _poll_request_cache[thread.id] = now
    poll_thread.apply_async(args=[thread.id], queue="ingestion")


def _serialize_comment(
    session: Session,
    comment: Comment,
    *,
    cast_slug: str | None = None,
    _visited: set[str] | None = None,
) -> CommentRead:
    breakdown = comment.sentiment_breakdown or {}
    sentiment_models: list[dict[str, object]] = []
    sentiment_combined_score: float | None = None
    sentiment_final_source: str | None = None

    if isinstance(breakdown, dict):
        model_entries = breakdown.get("models")
        if isinstance(model_entries, list):
            for entry in model_entries:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                if not isinstance(name, str) or not name:
                    continue
                sentiment_label = entry.get("sentiment_label")
                if isinstance(sentiment_label, str):
                    sentiment_label = sentiment_label
                else:
                    sentiment_label = None
                score = entry.get("sentiment_score")
                score_value: float | None
                if isinstance(score, (int, float)):
                    score_value = float(score)
                else:
                    score_value = None
                reasoning = entry.get("reasoning")
                if not isinstance(reasoning, str):
                    reasoning = None
                sentiment_models.append(
                    {
                        "name": name,
                        "sentiment_label": sentiment_label,
                        "sentiment_score": score_value,
                        "reasoning": reasoning,
                    }
                )
        combined = breakdown.get("combined_score")
        if isinstance(combined, (int, float)):
            sentiment_combined_score = float(combined)
        final_source = breakdown.get("final_source")
        if isinstance(final_source, str) and final_source:
            sentiment_final_source = final_source

    if _visited is None:
        _visited = set()
    if comment.reddit_id in _visited:
        return CommentRead(
            id=comment.id,
            reddit_id=comment.reddit_id,
            body=comment.body,
            created_utc=comment.created_utc,
            author_hash=comment.author_hash,
            score=comment.score,
            time_window=comment.time_window,
            sentiment_label=comment.sentiment_label,
            sentiment_score=comment.sentiment_score,
            sentiment_models=sentiment_models,
            sentiment_combined_score=sentiment_combined_score,
            sentiment_final_source=sentiment_final_source,
            is_sarcastic=comment.is_sarcastic,
            sarcasm_confidence=comment.sarcasm_confidence,
            is_toxic=comment.is_toxic,
            toxicity_confidence=comment.toxicity_confidence,
            mentions=[
                CommentMentionRead(
                    cast_slug=mention.cast_member.slug,
                    cast_name=mention.cast_member.full_name,
                    sentiment_label=mention.sentiment_label,
                    sentiment_score=mention.sentiment_score,
                    quote=mention.quote,
                )
                for mention in comment.mentions
            ],
            replies=[],
        )

    _visited.add(comment.reddit_id)

    replies_stmt = (
        select(Comment)
        .options(selectinload(Comment.mentions).selectinload(Mention.cast_member))
        .where(Comment.parent_id == comment.reddit_id)
        .order_by(Comment.created_utc.asc())
    )
    replies = session.scalars(replies_stmt).unique().all()

    replies_payload = [
        _serialize_comment(session, reply, cast_slug=None, _visited=_visited)
        for reply in replies
    ]

    return CommentRead(
        id=comment.id,
        reddit_id=comment.reddit_id,
        body=comment.body,
        created_utc=comment.created_utc,
        author_hash=comment.author_hash,
        score=comment.score,
        time_window=comment.time_window,
        sentiment_label=comment.sentiment_label,
        sentiment_score=comment.sentiment_score,
        sentiment_models=sentiment_models,
        sentiment_combined_score=sentiment_combined_score,
        sentiment_final_source=sentiment_final_source,
        is_sarcastic=comment.is_sarcastic,
        sarcasm_confidence=comment.sarcasm_confidence,
        is_toxic=comment.is_toxic,
        toxicity_confidence=comment.toxicity_confidence,
        mentions=[
            CommentMentionRead(
                cast_slug=mention.cast_member.slug,
                cast_name=mention.cast_member.full_name,
                sentiment_label=mention.sentiment_label,
                sentiment_score=mention.sentiment_score,
                quote=mention.quote,
            )
            for mention in comment.mentions
        ],
        replies=replies_payload,
    )
