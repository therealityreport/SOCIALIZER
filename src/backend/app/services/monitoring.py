from __future__ import annotations

import logging
import os
from typing import Mapping

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from statsd import StatsClient  # type: ignore
    _STATSD_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    StatsClient = None  # type: ignore[assignment]
    _STATSD_AVAILABLE = False

_STATSD_CLIENT: object | None | bool = None


def _statsd_client() -> object | None:
    global _STATSD_CLIENT
    if _STATSD_CLIENT is False:
        return None
    if _STATSD_CLIENT is not None and _STATSD_CLIENT is not False:
        return _STATSD_CLIENT
    host = os.getenv("STATSD_HOST")
    if not host or not _STATSD_AVAILABLE or StatsClient is None:
        _STATSD_CLIENT = False
        return None
    port = int(os.getenv("STATSD_PORT", "8125"))
    prefix = os.getenv("STATSD_PREFIX", "socializer")
    try:
        _STATSD_CLIENT = StatsClient(host=host, port=port, prefix=prefix)  # type: ignore[call-arg]
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("Unable to initialize StatsD client (%s:%s): %s", host, port, exc)
        _STATSD_CLIENT = False
        return None
    return _STATSD_CLIENT


def _format_tags(tags: Mapping[str, str] | None) -> str:
    if not tags:
        return ""
    return " " + " ".join(f"{key}={value}" for key, value in sorted(tags.items()))


def emit_counter(name: str, value: float = 1.0, *, tags: Mapping[str, str] | None = None) -> None:
    client = _statsd_client()
    if client:
        try:
            client.incr(name, value)
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.debug("StatsD counter emit failed for %s: %s", name, exc)
    logger.debug("metric counter %s=%s%s", name, value, _format_tags(tags))


def observe_histogram(name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
    client = _statsd_client()
    if client:
        try:
            client.timing(name, value)
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.debug("StatsD histogram emit failed for %s: %s", name, exc)
    logger.debug("metric histogram %s=%.4f%s", name, value, _format_tags(tags))


def set_gauge(name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
    client = _statsd_client()
    if client:
        try:
            client.gauge(name, value)
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.debug("StatsD gauge emit failed for %s: %s", name, exc)
    logger.debug("metric gauge %s=%.4f%s", name, value, _format_tags(tags))
