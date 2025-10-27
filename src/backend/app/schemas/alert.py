from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AlertRuleBase(BaseModel):
    name: str
    description: str | None = None
    thread_id: int | None = None
    cast_member_id: int | None = None
    rule_type: str = Field(examples=["sentiment_drop"])
    condition: dict[str, Any]
    is_active: bool = True
    channels: list[str] = Field(default_factory=list)


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    thread_id: int | None = None
    cast_member_id: int | None = None
    rule_type: str | None = None
    condition: dict[str, Any] | None = None
    is_active: bool | None = None
    channels: list[str] | None = None


class AlertRuleRead(AlertRuleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }


class AlertEventRead(BaseModel):
    id: int
    alert_rule_id: int
    thread_id: int
    cast_member_id: int | None = None
    triggered_at: datetime
    payload: dict[str, Any]
    delivered_channels: list[str] = Field(default_factory=list)

    model_config = {
        "from_attributes": True,
    }
