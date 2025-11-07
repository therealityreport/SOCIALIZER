from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def normalize_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "username": profile.get("username"),
        "full_name": profile.get("fullName"),
        "biography": profile.get("biography"),
        "followers_count": profile.get("followersCount"),
        "follows_count": profile.get("followsCount"),
        "posts_count": profile.get("postsCount"),
        "external_url": profile.get("externalUrl"),
        "is_verified": bool(profile.get("isVerified")),
        "is_private": bool(profile.get("isPrivate")),
        "about_json": {key: value for key, value in profile.items() if key != "latestPosts"},
    }


def normalize_post(username: str, post: Dict[str, Any]) -> Dict[str, Any]:
    timestamp = post.get("timestamp") or post.get("takenAt")
    posted_at = None
    if timestamp:
        try:
            posted_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            posted_at = None

    return {
        "shortcode": post.get("shortcode") or post.get("id"),
        "username": username,
        "caption": post.get("caption"),
        "posted_at": posted_at.isoformat() if posted_at else None,
        "media_type": post.get("mediaType"),
        "product_type": post.get("productType"),
        "url": post.get("url"),
        "comments_count": post.get("commentsCount"),
        "likes_count": post.get("likesCount"),
        "raw_json": post,
    }
