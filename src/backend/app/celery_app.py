from __future__ import annotations

from celery import Celery
from kombu import Exchange, Queue

from app.core.config import get_settings
from app.tasks.base import BaseTaskWithRetry

settings = get_settings()

celery_app = Celery(
    "socializer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    task_cls=BaseTaskWithRetry,
)

celery_app.conf.update(
    task_default_queue="default",
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("ingestion", Exchange("ingestion"), routing_key="ingestion"),
        Queue("ml", Exchange("ml"), routing_key="ml"),
        Queue("alerts", Exchange("alerts"), routing_key="alerts"),
    ),
    task_routes={
        "app.tasks.ingestion.*": {"queue": "ingestion"},
        "app.tasks.ml.*": {"queue": "ml"},
        "app.tasks.alerts.*": {"queue": "alerts"},
    },
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    task_time_limit=settings.celery_task_time_limit,
    broker_connection_retry_on_startup=True,
)

celery_app.autodiscover_tasks(["app.tasks"])
