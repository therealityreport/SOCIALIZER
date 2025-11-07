from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import get_settings, is_dev
from app.schemas.instagram import (
    InstagramIngestRequest,
    InstagramIngestResponse,
    SkipCounts,
    UsernameStats,
)
from app.services.instagram.apify_client import call_actor, filter_items
from app.services.instagram.normalize import normalize_post, normalize_profile
from app.services.instagram.persistence import (
    record_run,
    replace_hashtags,
    upsert_post,
    upsert_profile,
)

router = APIRouter(prefix="/ingest/instagram", tags=["instagram"])


def _date_to_utc_boundary(value: str, end: bool) -> datetime:
    parsed = date.fromisoformat(value)
    boundary = time.max if end else time.min
    return datetime.combine(parsed, boundary, tzinfo=timezone.utc)


@router.post("/profiles", response_model=InstagramIngestResponse)
def ingest_profiles(
    payload: InstagramIngestRequest,
    db: Session = Depends(deps.get_db),
) -> InstagramIngestResponse:
    settings = get_settings()
    token = settings.apify_token
    if not token:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="APIFY_TOKEN not configured.")

    start_dt = _date_to_utc_boundary(payload.startDate, end=False)
    end_dt = _date_to_utc_boundary(payload.endDate, end=True)
    if end_dt < start_dt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="endDate must be on or after startDate")

    if payload.startDate == payload.endDate:
        end_dt = end_dt + timedelta(days=1) - timedelta(microseconds=1)

    try:
        run_meta, items = call_actor(token, payload.usernames, payload.includeAbout)
    except Exception as exc:  # pragma: no cover - network failures bubbled up
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to execute Apify actor.") from exc

    profiles_by_username: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        username = (item.get("username") or "").lower()
        if not username:
            continue
        profiles_by_username[username].append(item)

    per_username: dict[str, UsernameStats] = {}
    total_kept = 0
    include_tags = set(payload.includeTags)
    exclude_tags = set(payload.excludeTags)

    for username in payload.usernames:
        matched_profiles = profiles_by_username.get(username.lower(), [])
        kept_pairs, skipped_counts, fetched = filter_items(
            matched_profiles,
            start_dt,
            end_dt,
            include_tags,
            exclude_tags,
            payload.minLikes,
            payload.minComments,
            payload.maxPostsPerUsername,
        )

        per_username[username] = UsernameStats(
            fetched=fetched,
            kept=len(kept_pairs),
            skipped=SkipCounts(**skipped_counts),
        )
        total_kept += len(kept_pairs)

        if payload.dryRun or not matched_profiles:
            continue

        normalized_profile = normalize_profile(matched_profiles[0])
        try:
            upsert_profile(db, normalized_profile)
            for _, post in kept_pairs:
                normalized_post = normalize_post(normalized_profile["username"], post)
                post_model = upsert_post(db, normalized_post)
                replace_hashtags(db, post_model.shortcode, normalized_post.get("caption"), normalized_post.get("raw_json"))
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive rollback
            db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist Instagram data.") from exc

    actor_payload = {
        "runId": run_meta.get("id") or run_meta.get("data", {}).get("id") or "",
        "status": run_meta.get("status") or run_meta.get("data", {}).get("status") or "UNKNOWN",
        "startedAt": run_meta.get("startedAt") or run_meta.get("data", {}).get("startedAt"),
        "finishedAt": run_meta.get("finishedAt") or run_meta.get("data", {}).get("finishedAt"),
    }

    if not payload.dryRun:
        stats_snapshot = {
            "itemsKept": total_kept,
            "perUsername": {uname: stats.model_dump() for uname, stats in per_username.items()},
        }
        record_run(db, actor_payload, payload.model_dump(), stats_snapshot)
        db.commit()

    return InstagramIngestResponse(actor=actor_payload, perUsername=per_username, itemsKept=total_kept)


@router.post("/test-one")
def test_one_post(
    username: str = Query(default="BravoTV"),
    hours: int = Query(default=24, ge=1, le=168),
    max_posts: int = Query(default=1, ge=1, le=10),
) -> dict[str, Any]:
    if not is_dev():
        raise HTTPException(status_code=404, detail="Not found")

    token = os.environ.get("APIFY_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="APIFY_TOKEN not configured")

    now = datetime.now(timezone.utc)
    try:
        run, items = call_actor(token, username, include_about=False)
        kept, skipped, fetched = filter_items(
            items=items,
            start_dt=now - timedelta(hours=hours),
            end_dt=now + timedelta(hours=1),
            inc_tags=set(),
            exc_tags=set(),
            min_likes=None,
            min_comments=None,
            max_posts=max_posts,
        )

        # Dev-only fallback: if no posts in the requested window, return the most recent post
        if not kept and items:
            # Take first non-private profile and its latest post, ignoring the date filter.
            for profile in items:
                if profile.get("isPrivate"):
                    continue
                posts = profile.get("latestPosts") or []
                if posts:
                    kept = [(profile, posts[0])]
                    break

        post = kept[0][1] if kept else None
    except Exception as exc:  # pragma: no cover - live actor errors
        raise HTTPException(status_code=500, detail=f"Apify call failed: {exc}") from exc

    run_data = run.get("data", {}) if isinstance(run.get("data"), dict) else {}
    return {
        "actor": {
            "runId": run.get("id") or run_data.get("id"),
            "status": run.get("status") or run_data.get("status"),
            "startedAt": run.get("startedAt") or run_data.get("startedAt"),
            "finishedAt": run.get("finishedAt") or run_data.get("finishedAt"),
        },
        "fetched": fetched,
        "kept": len(kept),
        "skipped": skipped,
        "post_sample": post,
    }
