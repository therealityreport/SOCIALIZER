from __future__ import annotations

import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.thread import ThreadStatus


class ThreadBase(BaseModel):
    reddit_id: str = Field(..., min_length=3, max_length=32)
    subreddit: Optional[str] = Field(default=None, max_length=64)
    title: str = Field(..., min_length=1, max_length=500)
    url: str = Field(..., max_length=500)
    air_time_utc: Optional[dt.datetime] = None
    created_utc: dt.datetime
    status: ThreadStatus = ThreadStatus.SCHEDULED
    total_comments: int = 0
    synopsis: Optional[str] = None


class ThreadCreate(ThreadBase):
    pass


class ThreadUpdate(BaseModel):
    subreddit: Optional[str] = Field(default=None, max_length=64)
    title: Optional[str] = Field(default=None, max_length=500)
    url: Optional[str] = Field(default=None, max_length=500)
    air_time_utc: Optional[dt.datetime] = None
    status: Optional[ThreadStatus] = None
    total_comments: Optional[int] = None
    synopsis: Optional[str] = None


class ThreadRead(ThreadBase):
    id: int
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = ConfigDict(from_attributes=True)


class ThreadLookupResponse(BaseModel):
    reddit_id: str
    subreddit: Optional[str]
    title: str
    url: str
    created_utc: dt.datetime
    air_time_utc: Optional[dt.datetime]
    num_comments: int = 0
    synopsis: Optional[str] = None
