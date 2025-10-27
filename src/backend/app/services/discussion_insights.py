from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CastMember, Comment, Thread
from app.schemas.analytics import (
    EmojiStat,
    KeywordStat,
    MediaItem,
    NameStat,
    ThreadInsightsResponse,
)

EMOJI_PATTERN = re.compile(
    "[\U0001F1E0-\U0001F1FF\U0001F300-\U0001F5FF\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FAFF"
    "\U00002600-\U000026FF\U00002700-\U000027BF]",
    flags=re.UNICODE,
)
WORD_PATTERN = re.compile(r"[A-Za-z']{3,}")
NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b")
URL_PATTERN = re.compile(r"(https?://[^\s)]+)")

STOP_WORDS = {
    "https",
    "http",
    "www",
    "reddit",
    "com",
    "that",
    "this",
    "with",
    "have",
    "from",
    "about",
    "would",
    "could",
    "there",
    "their",
    "them",
    "just",
    "what",
    "when",
    "were",
    "your",
    "they",
    "because",
    "really",
    "still",
    "where",
    "being",
    "into",
    "after",
    "before",
    "while",
    "we're",
    "you're",
    "it's",
    "dont",
    "cant",
    "doesnt",
    " wasnt",
    "didn't",
}

MEDIA_EXTENSIONS = {
    "image": {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".svg"},
    "gif": {".gif"},
    "video": {".mp4", ".mov", ".avi", ".webm", ".mkv"},
}


def _classify_media(url: str) -> str:
    lower = url.lower()
    for media_type, extensions in MEDIA_EXTENSIONS.items():
        if any(lower.endswith(ext) for ext in extensions):
            return media_type
    if "giphy" in lower or "tenor" in lower:
        return "gif"
    if any(domain in lower for domain in ("youtube.com", "youtu.be", "vimeo.com", "tiktok.com")):
        return "video"
    return "link"


def _normalize_name(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split())


def _load_cast_directory(session: Session) -> dict[str, NameStat]:
    directory: dict[str, NameStat] = {}
    stmt = select(CastMember).options(selectinload(CastMember.aliases))
    members = session.execute(stmt).scalars().all()
    for member in members:
        normalized = member.full_name.strip().lower()
        directory[normalized] = NameStat(
            name=member.full_name,
            count=0,
            is_cast=True,
            cast_member_id=member.id,
        )
        if member.display_name:
            directory[member.display_name.strip().lower()] = NameStat(
                name=member.display_name,
                count=0,
                is_cast=True,
                cast_member_id=member.id,
            )
        for alias in member.aliases:
            alias_value = alias.alias.strip().lower()
            if alias_value:
                directory[alias_value] = NameStat(
                    name=_normalize_name(alias.alias),
                    count=0,
                    is_cast=True,
                    cast_member_id=member.id,
                )
    return directory


def _iter_comments(session: Session, thread: Thread) -> Iterable[Comment]:
    stmt = select(Comment).where(Comment.thread_id == thread.id)
    return session.execute(stmt).scalars().all()


def generate_thread_insights(session: Session, thread: Thread, top_n: int = 10) -> ThreadInsightsResponse:
    comments = _iter_comments(session, thread)
    if not comments:
        now = dt.datetime.now(dt.timezone.utc)
        return ThreadInsightsResponse(
            thread_id=thread.id,
            generated_at=now,
            emojis=[],
            hot_topics=[],
            names=[],
            media=[],
        )

    emoji_counter: Counter[str] = Counter()
    word_counter: Counter[str] = Counter()
    name_counter: Counter[str] = Counter()
    media_items: list[MediaItem] = []
    seen_media: set[str] = set()

    cast_directory = _load_cast_directory(session)

    for comment in comments:
        body = comment.body or ""

        # Emojis
        for emoji in EMOJI_PATTERN.findall(body):
            emoji_counter[emoji] += 1

        # Keywords
        for word in WORD_PATTERN.findall(body):
            normalized = word.lower()
            if len(normalized) <= 2:
                continue
            if normalized in STOP_WORDS:
                continue
            word_counter[normalized] += 1

        # Names
        for name in NAME_PATTERN.findall(body):
            normalized_name = name.strip()
            if not normalized_name:
                continue
            lower = normalized_name.lower()
            if lower in STOP_WORDS:
                continue
            name_counter[lower] += 1

        # Media
        for raw_url in URL_PATTERN.findall(body):
            cleaned = raw_url.rstrip(',.!?")')
            if not cleaned:
                continue
            if cleaned in seen_media:
                continue
            seen_media.add(cleaned)
            media_type = _classify_media(cleaned)
            media_items.append(
                MediaItem(
                    comment_id=comment.id,
                    url=cleaned,
                    media_type=media_type,
                    created_utc=comment.created_utc,
                )
            )

    emojis = [EmojiStat(emoji=item[0], count=item[1]) for item in emoji_counter.most_common(top_n)]
    topics = [KeywordStat(term=item[0], count=item[1]) for item in word_counter.most_common(top_n)]

    names: list[NameStat] = []
    for value, count in name_counter.most_common(top_n * 2):
        base = cast_directory.get(value)
        if base:
            names.append(NameStat(name=base.name, count=count, is_cast=True, cast_member_id=base.cast_member_id))
        else:
            pretty = _normalize_name(value)
            names.append(NameStat(name=pretty, count=count, is_cast=False, cast_member_id=None))
        if len(names) >= top_n:
            break

    media_items.sort(key=lambda item: item.created_utc or dt.datetime.min, reverse=True)
    if len(media_items) > top_n:
        media_items = media_items[: top_n * 3]

    return ThreadInsightsResponse(
        thread_id=thread.id,
        generated_at=dt.datetime.now(dt.timezone.utc),
        emojis=emojis,
        hot_topics=topics,
        names=names,
        media=media_items,
    )
