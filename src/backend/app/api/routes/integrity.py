from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.integrity import BotReport, BrigadingReport, ReliabilityReport
from app.services.integrity import IntegrityService

router = APIRouter(prefix="/integrity", tags=["integrity"])


@router.get("/threads/{thread_id}/brigading", response_model=BrigadingReport)
def brigading(thread_id: int, db: Session = Depends(deps.get_db)) -> BrigadingReport:
    service = IntegrityService(db)
    result = service.compute_brigading(thread_id)
    return BrigadingReport(
        score=result.score,
        status=result.status,
        total_comments=result.total_comments,
        unique_authors=result.unique_authors,
        participation_ratio=result.participation_ratio,
        suspicious_authors=[
            {"author_hash": author, "comment_count": count} for author, count in result.suspicious_authors
        ],
        generated_at=result.generated_at,
    )


@router.get("/threads/{thread_id}/bots", response_model=BotReport)
def bots(thread_id: int, db: Session = Depends(deps.get_db)) -> BotReport:
    service = IntegrityService(db)
    result = service.compute_bots(thread_id)
    return BotReport(
        score=result.score,
        status=result.status,
        flagged_accounts=[
            {"author_hash": author, "comment_count": count, "average_length": avg_len}
            for author, count, avg_len in result.flagged_accounts
        ],
        total_accounts=result.total_accounts,
        generated_at=result.generated_at,
    )


@router.get("/threads/{thread_id}/reliability", response_model=ReliabilityReport)
def reliability(thread_id: int, db: Session = Depends(deps.get_db)) -> ReliabilityReport:
    service = IntegrityService(db)
    try:
        result = service.compute_reliability(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ReliabilityReport(
        score=result.score,
        status=result.status,
        ingested_comments=result.ingested_comments,
        reported_comments=result.reported_comments,
        coverage_ratio=result.coverage_ratio,
        minutes_since_last_poll=result.minutes_since_last_poll,
        last_polled_at=result.last_polled_at,
        generated_at=result.generated_at,
        notes=result.notes,
    )
