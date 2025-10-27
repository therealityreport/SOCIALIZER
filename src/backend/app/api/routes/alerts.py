from __future__ import annotations

from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api import deps
from app.models import AlertEvent, AlertRule
from app.schemas.alert import (
    AlertEventRead,
    AlertRuleCreate,
    AlertRuleRead,
    AlertRuleUpdate,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/rules", response_model=list[AlertRuleRead])
def list_alert_rules(
    thread_id: int | None = Query(default=None, ge=1),
    include_global: bool = Query(default=True),
    db: Session = Depends(deps.get_db),
) -> Sequence[AlertRule]:
    stmt = select(AlertRule)
    if thread_id is not None:
        if include_global:
            stmt = stmt.where((AlertRule.thread_id == thread_id) | (AlertRule.thread_id.is_(None)))
        else:
            stmt = stmt.where(AlertRule.thread_id == thread_id)
    rules = db.execute(stmt.order_by(AlertRule.created_at.desc())).scalars().all()
    return rules


@router.post("/rules", response_model=AlertRuleRead, status_code=status.HTTP_201_CREATED)
def create_alert_rule(payload: AlertRuleCreate, db: Session = Depends(deps.get_db)) -> AlertRule:
    rule = AlertRule(**payload.model_dump())
    db.add(rule)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to create alert rule.") from exc
    db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=AlertRuleRead)
def update_alert_rule(rule_id: int, payload: AlertRuleUpdate, db: Session = Depends(deps.get_db)) -> AlertRule:
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to update alert rule.") from exc
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_alert_rule(rule_id: int, db: Session = Depends(deps.get_db)) -> Response:
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found.")
    db.delete(rule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/history", response_model=list[AlertEventRead])
def list_alert_history(
    thread_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(deps.get_db),
) -> Sequence[AlertEvent]:
    stmt = select(AlertEvent)
    if thread_id is not None:
        stmt = stmt.where(AlertEvent.thread_id == thread_id)
    events = (
        db.execute(stmt.order_by(AlertEvent.triggered_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return events
