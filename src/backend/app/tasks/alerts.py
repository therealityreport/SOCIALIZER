from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from app.db.session import SessionLocal
from app.services.alerts import AlertDeliveryService, AlertEvaluationService
from app.models import AlertEvent

logger = logging.getLogger(__name__)


@shared_task(name="app.tasks.alerts.notify_slack")
def notify_slack(message: str, metadata: dict[str, Any] | None = None) -> bool:
    logger.info("Dispatching slack alert: %s", message)
    # Placeholder for Slack webhook integration.
    return True


@shared_task(bind=True, name="app.tasks.alerts.check_alerts")
def check_alerts(self, thread_id: int) -> int:
    session = SessionLocal()
    try:
        service = AlertEvaluationService(session)
        events = service.evaluate_thread(thread_id)
        session.flush()
        event_ids = [event.id for event in events]
        session.commit()
        for event_id in event_ids:
            deliver_alert_event.delay(event_id)
        logger.info("Alert evaluation for thread %s produced %s events", thread_id, len(events))
        return len(events)
    except Exception:
        session.rollback()
        logger.exception("Alert evaluation failed for thread %s", thread_id)
        raise
    finally:
        session.close()


@shared_task(bind=True, name="app.tasks.alerts.deliver_event")
def deliver_alert_event(self, alert_event_id: int) -> int:
    session = SessionLocal()
    try:
        event = session.get(AlertEvent, alert_event_id)
        if not event:
            logger.warning("Alert event %s no longer exists.", alert_event_id)
            return 0
        service = AlertDeliveryService(session)
        delivered_channels = service.deliver(event)
        session.commit()
        logger.info(
            "Delivered alert event %s via channels: %s",
            alert_event_id,
            ", ".join(delivered_channels) or "none",
        )
        return len(delivered_channels)
    except Exception:
        session.rollback()
        logger.exception("Alert delivery failed for event %s", alert_event_id)
        raise
    finally:
        session.close()
