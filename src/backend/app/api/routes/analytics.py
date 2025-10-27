from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.analytics import CastAnalytics, CastHistoryResponse, ThreadCastAnalyticsResponse
from app.services import analytics as analytics_service


router = APIRouter(tags=["analytics"])


@router.get("/threads/{thread_id}/cast", response_model=ThreadCastAnalyticsResponse)
def list_thread_cast(
    thread_id: int = Path(..., description="Internal thread identifier."),
    db: Session = Depends(deps.get_db),
) -> ThreadCastAnalyticsResponse:
    try:
        return analytics_service.get_thread_cast_analytics(db, thread_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/threads/{thread_id}/cast/{cast_slug}", response_model=CastAnalytics)
def get_thread_cast_member(
    thread_id: int,
    cast_slug: str,
    db: Session = Depends(deps.get_db),
) -> CastAnalytics:
    try:
        _, cast = analytics_service.get_thread_cast_member(db, thread_id, cast_slug)
        return cast
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cast/{cast_slug}/history", response_model=CastHistoryResponse)
def get_cast_history(
    cast_slug: str,
    db: Session = Depends(deps.get_db),
) -> CastHistoryResponse:
    try:
        return analytics_service.get_cast_history(db, cast_slug)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
