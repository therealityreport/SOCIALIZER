from __future__ import annotations

import logging
from typing import Iterable


def configure_logging(level: int = logging.INFO, handlers: Iterable[logging.Handler] | None = None) -> None:
    """Configure a basic logging setup for scripts and services."""
    if handlers:
        root = logging.getLogger()
        root.handlers[:] = []
        for handler in handlers:
            root.addHandler(handler)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
