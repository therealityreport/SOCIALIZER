from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Sequence, Tuple

HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)


def _require_apify() -> Any:
    try:
        from apify_client import ApifyClient  # type: ignore import-not-found
    except Exception as exc:  # pragma: no cover - import guard for optional dep
        raise RuntimeError("apify-client is required. Install with: pip install apify-client") from exc
    return ApifyClient


def _extract_hashtags(text: str) -> set[str]:
    if not text:
        return set()
    return {m.group(1).lower() for m in HASHTAG_RE.finditer(text)}


def _parse_ts(ts_raw: Any) -> datetime | None:
    try:
        if isinstance(ts_raw, datetime):
            return ts_raw.astimezone(timezone.utc) if ts_raw.tzinfo else ts_raw.replace(tzinfo=timezone.utc)
        if isinstance(ts_raw, str) and ts_raw:
            return datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None
    return None


def call_actor(token: str, usernames: Sequence[str], include_about: bool) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    ApifyClient = _require_apify()
    client = ApifyClient(token)
    run = client.actor("apify/instagram-profile-scraper").call(
        run_input={"usernames": list(usernames), "includeAboutSection": include_about}
    )
    dataset_id = run.get("defaultDatasetId") or run.get("data", {}).get("defaultDatasetId")
    if not dataset_id:
        return run, []
    items = list(client.dataset(dataset_id).iterate_items())
    return run, items


def filter_items(
    items: List[Dict[str, Any]],
    start_dt: datetime,
    end_dt: datetime,
    inc_tags: set[str],
    exc_tags: set[str],
    min_likes: int | None,
    min_comments: int | None,
    max_posts: int | None = None,
) -> Tuple[List[Tuple[Dict[str, Any], Dict[str, Any]]], Dict[str, int], int]:
    kept: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    skipped = {"date": 0, "inc_tag": 0, "exc_tag": 0, "likes": 0, "comments": 0, "private": 0, "other": 0}
    fetched = 0
    kept_count = 0

    inc_tags = {t.lower() for t in (inc_tags or set())}
    exc_tags = {t.lower() for t in (exc_tags or set())}

    for profile in items:
        posts = profile.get("latestPosts") or []
        fetched += len(posts)
        if profile.get("isPrivate"):
            skipped["private"] += len(posts)
            continue

        for post in posts:
            try:
                ts = _parse_ts(post.get("timestamp") or post.get("takenAt") or post.get("taken_at"))
                if (ts is None) or (ts < start_dt) or (ts > end_dt):
                    skipped["date"] += 1
                    continue

                caption = post.get("caption") or ""
                alt = post.get("alt") or ""
                tags = _extract_hashtags(caption) | _extract_hashtags(alt)

                if inc_tags and tags.isdisjoint(inc_tags):
                    skipped["inc_tag"] += 1
                    continue
                if exc_tags and (tags & exc_tags):
                    skipped["exc_tag"] += 1
                    continue
                if min_likes is not None and (post.get("likesCount") or 0) < min_likes:
                    skipped["likes"] += 1
                    continue
                if min_comments is not None and (post.get("commentsCount") or 0) < min_comments:
                    skipped["comments"] += 1
                    continue

                if max_posts is None or kept_count < max_posts:
                    kept.append((profile, post))
                    kept_count += 1
            except Exception:
                skipped["other"] += 1

    return kept, skipped, fetched
