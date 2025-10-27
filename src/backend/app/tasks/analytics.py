from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from app.db.session import SessionLocal
from app.services.aggregation import AggregationService
from app.tasks.alerts import check_alerts

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="app.tasks.analytics.compute_aggregates")
def compute_aggregates(self, thread_id: int) -> dict[str, Any]:
    session = SessionLocal()
    try:
        service = AggregationService(session)
        result = service.compute(thread_id)
        session.commit()

        cast_count = len(result.cast)
        details = {
            "thread_id": thread_id,
            "cast_count": cast_count,
            "total_mentions": result.total_mentions,
            "time_windows": list(result.time_windows.keys()),
        }
        logger.info(
            "Computed aggregates for thread %s: cast=%s mentions=%s windows=%s",
            thread_id,
            cast_count,
            result.total_mentions,
            ",".join(details["time_windows"]) or "none",
        )
        check_alerts.delay(thread_id)
        return details
    except Exception:
        session.rollback()
        logger.exception("Failed to compute aggregates for thread %s", thread_id)
        raise
    finally:
        session.close()
