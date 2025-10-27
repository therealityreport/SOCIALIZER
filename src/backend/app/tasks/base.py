from __future__ import annotations

import logging

from celery import Task

logger = logging.getLogger(__name__)


class BaseTaskWithRetry(Task):
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    retry_kwargs = {"max_retries": 5}

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning("Retrying task %s due to %s", task_id, exc)
        super().on_retry(exc, task_id, args, kwargs, einfo)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error("Task %s failed: %s", task_id, exc, exc_info=einfo)
        super().on_failure(exc, task_id, args, kwargs, einfo)
