from __future__ import annotations

import datetime as dt
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.instagram import (
    InstagramPost,
    InstagramPostHashtag,
    InstagramProfile,
    InstagramRun,
)

_HASHTAG_RE = re.compile(r"#([A-Za-z0-9_]+)")


def _extract_hashtags(text: str | None) -> set[str]:
    if not text:
        return set()
    return {match.group(1).lower() for match in _HASHTAG_RE.finditer(text)}


def _parse_posted_at(posted_at: str | None) -> dt.datetime | None:
    if not posted_at:
        return None
    try:
        normalized = posted_at.replace("Z", "+00:00")
        return dt.datetime.fromisoformat(normalized)
    except ValueError:
        return None


def upsert_profile(session: Session, normalized_profile: dict[str, Any]) -> InstagramProfile:
    username = normalized_profile.get("username")
    if not username:
        raise ValueError("Profile missing username.")

    profile = session.get(InstagramProfile, username)
    if profile is None:
        profile = InstagramProfile(username=username)
        session.add(profile)

    for field in (
        "full_name",
        "biography",
        "followers_count",
        "follows_count",
        "posts_count",
        "external_url",
        "is_verified",
        "is_private",
        "about_json",
    ):
        setattr(profile, field, normalized_profile.get(field))

    return profile


def upsert_post(session: Session, normalized_post: dict[str, Any]) -> InstagramPost:
    shortcode = normalized_post.get("shortcode")
    if not shortcode:
        raise ValueError("Post missing shortcode.")

    post = session.get(InstagramPost, shortcode)
    if post is None:
        post = InstagramPost(shortcode=shortcode)
        session.add(post)

    post.username = normalized_post.get("username") or post.username
    post.caption = normalized_post.get("caption")
    post.posted_at = _parse_posted_at(normalized_post.get("posted_at"))
    post.media_type = normalized_post.get("media_type")
    post.product_type = normalized_post.get("product_type")
    post.url = normalized_post.get("url")
    post.comments_count = normalized_post.get("comments_count") or 0
    post.likes_count = normalized_post.get("likes_count") or 0
    post.raw_json = normalized_post.get("raw_json")

    return post


def replace_hashtags(session: Session, shortcode: str, caption: str | None, raw_post: dict[str, Any] | None) -> None:
    tags = _extract_hashtags(caption)
    if raw_post:
        tags |= _extract_hashtags(raw_post.get("alt"))
    session.query(InstagramPostHashtag).filter_by(post_shortcode=shortcode).delete(synchronize_session=False)
    for tag in sorted(tags):
        session.add(InstagramPostHashtag(post_shortcode=shortcode, tag=tag))


def record_run(
    session: Session,
    actor_meta: dict[str, Any],
    ingest_payload: dict[str, Any],
    stats: dict[str, Any],
) -> InstagramRun:
    run = InstagramRun(
        actor_run_id=actor_meta.get("runId"),
        status=actor_meta.get("status", "UNKNOWN"),
        started_at=_parse_posted_at(actor_meta.get("startedAt")),
        finished_at=_parse_posted_at(actor_meta.get("finishedAt")),
        input_json=ingest_payload,
        stats_json=stats,
    )
    session.add(run)
    return run
