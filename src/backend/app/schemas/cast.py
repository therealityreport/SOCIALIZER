from __future__ import annotations

import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CastAliasBase(BaseModel):
    alias: str = Field(..., min_length=1, max_length=120)


class CastAliasCreate(CastAliasBase):
    pass


class CastAliasRead(CastAliasBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class CastMemberBase(BaseModel):
    slug: Optional[str] = Field(default=None, max_length=120)
    full_name: str = Field(..., min_length=1, max_length=120)
    display_name: Optional[str] = Field(default=None, max_length=120)
    show: str = Field(..., min_length=1, max_length=120)
    biography: Optional[str] = None
    is_active: bool = True
    aliases: list[str] = Field(default_factory=list)


class CastMemberCreate(CastMemberBase):
    pass


class CastMemberUpdate(BaseModel):
    slug: Optional[str] = Field(default=None, max_length=120)
    full_name: Optional[str] = Field(default=None, max_length=120)
    display_name: Optional[str] = Field(default=None, max_length=120)
    show: Optional[str] = Field(default=None, max_length=120)
    biography: Optional[str] = None
    is_active: Optional[bool] = None
    aliases: Optional[list[str]] = None


class CastMemberRead(CastMemberBase):
    id: int
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = ConfigDict(from_attributes=True)
