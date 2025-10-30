"""LLM Management API Routes

Endpoints for LLM provider monitoring, cost tracking, and drift detection.
"""
import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.provider_cost import ProviderCost, ProviderSelectionLog, DriftCheck
from app.services.cost_monitor import get_cost_monitor
from app.services.provider_selection import ProviderSelector

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/active-provider")
async def get_active_provider() -> dict[str, Any]:
    """Get current active provider configuration"""
    selector = ProviderSelector()
    config = selector.read_config()

    if not config:
        raise HTTPException(status_code=404, detail="No active provider configuration found")

    return {
        "provider": config.provider,
        "model": config.model,
        "selected_at": config.selected_at,
        "provider_score": config.provider_score,
        "mean_confidence": config.mean_confidence,
        "cost_per_1k_tokens": config.cost_per_1k_tokens,
        "reason": config.reason,
    }


@router.get("/budget-status")
async def get_budget_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Get current monthly budget status"""
    cost_monitor = get_cost_monitor()
    budget_status = await cost_monitor.check_budget_status(db)
    return budget_status


@router.get("/performance-metrics")
async def get_performance_metrics(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Get today's performance metrics for active provider"""
    today = datetime.utcnow().date()

    # Get today's costs
    query = select(ProviderCost).where(ProviderCost.date == today)
    result = await db.execute(query)
    costs = list(result.scalars().all())

    if not costs:
        return {
            "daily_calls": 0,
            "daily_cost": 0.0,
            "mean_latency": 0.0,
            "mean_confidence": 0.0,
            "error_rate": 0.0,
        }

    total_calls = sum(c.comments_analyzed for c in costs)
    total_cost = sum(c.cost_usd for c in costs)

    # TODO: Track latency and confidence in ProviderCost table
    # For now, return placeholder values
    return {
        "daily_calls": total_calls,
        "daily_cost": total_cost,
        "mean_latency": 1.5,  # Placeholder
        "mean_confidence": 0.88,  # Placeholder
        "error_rate": 0.0,  # Placeholder
    }


@router.get("/benchmark-summary")
async def get_benchmark_summary() -> dict[str, Any]:
    """Get latest benchmark summary from CSV"""
    summary_path = Path("qa_reports/benchmark_summary.csv")

    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="No benchmark data available")

    providers = []
    with open(summary_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            providers.append({
                "provider": row["provider"],
                "call_count": int(row["call_count"]),
                "mean_confidence": float(row["mean_confidence"]),
                "std_confidence": float(row["std_confidence"]),
                "mean_latency": float(row["mean_latency"]),
                "std_latency": float(row["std_latency"]),
                "total_tokens": int(row["total_tokens"]),
                "total_cost": float(row["total_cost"]),
                "cost_per_1k_tokens": float(row["cost_per_1k_tokens"]),
                "mean_agreement": float(row["mean_agreement"]),
                "provider_score": float(row["provider_score"]),
            })

    # Get last modified time
    last_updated = datetime.fromtimestamp(summary_path.stat().st_mtime).isoformat()

    return {
        "providers": providers,
        "last_updated": last_updated,
    }


@router.get("/drift-latest")
async def get_latest_drift_check(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Get latest drift check result"""
    query = select(DriftCheck).order_by(desc(DriftCheck.check_date)).limit(1)
    result = await db.execute(query)
    check = result.scalar_one_or_none()

    if not check:
        raise HTTPException(status_code=404, detail="No drift check data available")

    return {
        "check_date": check.check_date.isoformat(),
        "primary_provider": check.primary_provider,
        "secondary_provider": check.secondary_provider,
        "samples_checked": check.samples_checked,
        "agreement_score": check.agreement_score,
        "sentiment_agreement": check.sentiment_agreement,
        "sarcasm_agreement": check.sarcasm_agreement,
        "status": check.status,
        "alert_sent": check.alert_sent,
    }


@router.get("/drift-trend")
async def get_drift_trend(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get drift trend over last N days"""
    start_date = datetime.utcnow() - timedelta(days=days)

    query = (
        select(DriftCheck)
        .where(DriftCheck.check_date >= start_date)
        .order_by(DriftCheck.check_date)
    )
    result = await db.execute(query)
    checks = result.scalars().all()

    return [
        {
            "date": check.check_date.isoformat(),
            "agreement_score": check.agreement_score,
            "sentiment_agreement": check.sentiment_agreement,
            "sarcasm_agreement": check.sarcasm_agreement,
        }
        for check in checks
    ]


@router.get("/cost-summary")
async def get_cost_summary(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get cost summary for last N days"""
    cost_monitor = get_cost_monitor()
    summary = await cost_monitor.get_cost_summary(db, days=days)
    return summary


@router.get("/selection-history")
async def get_selection_history(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get provider selection history"""
    query = (
        select(ProviderSelectionLog)
        .order_by(desc(ProviderSelectionLog.selected_at))
        .limit(limit)
    )
    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "provider": log.provider,
            "model": log.model,
            "provider_score": log.provider_score,
            "mean_confidence": log.mean_confidence,
            "cost_per_1k_tokens": log.cost_per_1k_tokens,
            "reason": log.reason,
            "fallback_provider": log.fallback_provider,
            "selected_at": log.selected_at.isoformat(),
        }
        for log in logs
    ]
