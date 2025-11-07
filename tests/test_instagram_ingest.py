from __future__ import annotations

import datetime as dt

import pytest

from app.schemas.instagram import InstagramIngestRequest
from app.services.instagram.apify_client import filter_items


def _make_post(shortcode: str, timestamp: dt.datetime, caption: str, likes: int, comments: int) -> dict:
    return {
        "shortcode": shortcode,
        "timestamp": timestamp.isoformat(),
        "caption": caption,
        "likesCount": likes,
        "commentsCount": comments,
        "url": "https://instagram.com/p/" + shortcode,
    }


def test_filter_items_applies_rules_and_limits() -> None:
    now = dt.datetime(2025, 1, 10, tzinfo=dt.timezone.utc)
    profile = {
        "username": "demo",
        "isPrivate": False,
        "latestPosts": [
            _make_post("a1", now - dt.timedelta(days=1), "#Bravo wins", 50, 10),
            _make_post("a2", now - dt.timedelta(days=5), "Outside window", 50, 10),
            _make_post("a3", now - dt.timedelta(hours=1), "Missing tag", 50, 10),
            _make_post("a4", now - dt.timedelta(hours=2), "#Bravo low likes", 1, 10),
            _make_post("a5", now - dt.timedelta(hours=3), "#Bravo low comments", 50, 0),
        ],
    }
    private_profile = {
        "username": "secret",
        "isPrivate": True,
        "latestPosts": [_make_post("b1", now, "#Bravo", 50, 50)],
    }

    kept, skipped, fetched = filter_items(
        [profile, private_profile],
        start_dt=now - dt.timedelta(days=2),
        end_dt=now,
        inc_tags={"bravo"},
        exc_tags=set(),
        min_likes=10,
        min_comments=5,
        max_posts=1,
    )

    assert fetched == 6
    assert len(kept) == 1  # limited by max_posts
    assert skipped["date"] == 1  # a2 outside window
    assert skipped["inc_tag"] == 1  # a3 missing tag
    assert skipped["likes"] == 1  # a4 low likes
    assert skipped["comments"] == 1  # a5 low comments
    assert skipped["private"] == 1  # private profile post skipped wholesale


def test_instagram_ingest_request_normalizes_fields() -> None:
    payload = InstagramIngestRequest(
        usernames=["@BravoTV", " second.user "],
        startDate="2025-01-01",
        endDate="2025-01-31",
        includeTags=["#TagOne", "tag_two"],
        excludeTags=["#BadTag"],
        maxPostsPerUsername=500,
    )

    assert payload.usernames == ["BravoTV", "second.user"]
    assert payload.includeTags == ["tagone", "tag_two"]
    assert payload.excludeTags == ["badtag"]


def test_instagram_ingest_request_rejects_invalid_tag() -> None:
    with pytest.raises(ValueError):
        InstagramIngestRequest(
            usernames=["valid"],
            startDate="2025-01-01",
            endDate="2025-01-02",
            includeTags=["Invalid tag"],
        )
