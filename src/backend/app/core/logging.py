from __future__ import annotations

import logging
import os
from logging.config import dictConfig
from typing import Iterable

from .config import get_settings


def _mask_secret(secret: str, visible: int = 4) -> str:
    secret = secret.strip()
    if not secret:
        return secret
    if len(secret) <= visible:
        return "*" * len(secret)
    return f"{secret[:visible]}{'*' * (len(secret) - visible)}"


class SecretMaskFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        seen: list[str] = []
        for secret in secrets:
            secret_value = (secret or "").strip()
            if secret_value and secret_value not in seen:
                seen.append(secret_value)
        self._secrets = seen

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        message = record.getMessage()
        sanitized = message
        for secret in self._secrets:
            sanitized = sanitized.replace(secret, _mask_secret(secret))
        if sanitized != message:
            record.msg = sanitized
            record.args = ()
        return True


def configure_logging() -> None:
    settings = get_settings()
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {"format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"}
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "root": {"level": settings.log_level.upper(), "handlers": ["console"]},
        }
    )

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    secrets_to_mask = [
        settings.huggingface_access_token or "",
        settings.huggingface_api_key or "",
        settings.azure_text_analytics_key or "",
        os.getenv("HUGGINGFACE_HUB_TOKEN", ""),
        os.getenv("HF_TOKEN", ""),
        os.getenv("AZURE_TEXT_ANALYTICS_KEY", ""),
    ]
    logging.getLogger().addFilter(SecretMaskFilter(secrets_to_mask))
