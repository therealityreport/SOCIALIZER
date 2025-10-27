from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict

from app.models.export import ExportFormat


class ExportCreateRequest(BaseModel):
    thread_id: int


class ExportResponse(BaseModel):
    id: int
    thread_id: int
    format: ExportFormat
    filename: str
    created_at: dt.datetime

    model_config = ConfigDict(from_attributes=True)
