from __future__ import annotations

import datetime as dt
import re
from typing import Dict, List

from pydantic import BaseModel, Field, field_validator

USERNAME_RE = re.compile(r"^@?([A-Za-z0-9._]+)$")
TAG_RE = re.compile(r"^[a-z0-9_]+$")


class SkipCounts(BaseModel):
    date: int = 0
    inc_tag: int = 0
    exc_tag: int = 0
    likes: int = 0
    comments: int = 0
    private: int = 0
    other: int = 0


class UsernameStats(BaseModel):
    fetched: int
    kept: int
    skipped: SkipCounts


class InstagramIngestRequest(BaseModel):
    usernames: List[str]
    startDate: str
    endDate: str
    includeTags: List[str] = Field(default_factory=list)
    excludeTags: List[str] = Field(default_factory=list)
    minLikes: int | None = None
    minComments: int | None = None
    maxPostsPerUsername: int | None = 500
    includeAbout: bool = False
    dryRun: bool = False

    @field_validator("usernames")
    @classmethod
    def _normalize_usernames(cls, value: List[str]) -> List[str]:
        normalized: list[str] = []
        for username in value:
            if not isinstance(username, str):
                raise ValueError("Username must be a string.")
            match = USERNAME_RE.match(username.strip())
            if not match:
                raise ValueError(f"Invalid username: {username}")
            normalized.append(match.group(1))
        if not normalized:
            raise ValueError("At least one username is required.")
        return normalized

    @field_validator("startDate", "endDate")
    @classmethod
    def _validate_date(cls, value: str) -> str:
        try:
            dt.date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Dates must be provided in YYYY-MM-DD format.") from exc
        return value

    @field_validator("includeTags", "excludeTags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: List[str]) -> List[str]:
        normalized: list[str] = []
        for entry in value or []:
            token = (entry or "").strip().lower().lstrip("#")
            if not token:
                continue
            if not TAG_RE.match(token):
                raise ValueError(f"Tags must match [a-z0-9_]+: {entry}")
            normalized.append(token)
        return normalized

    @field_validator("maxPostsPerUsername")
    @classmethod
    def _validate_max_posts(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value <= 0:
            raise ValueError("maxPostsPerUsername must be greater than zero")
        return value


class InstagramIngestResponse(BaseModel):
    actor: Dict[str, str | None]
    perUsername: Dict[str, UsernameStats]
    itemsKept: int
