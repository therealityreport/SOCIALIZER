from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import deps

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
def readiness_check(db: Session = Depends(deps.get_db)) -> dict[str, Any]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
