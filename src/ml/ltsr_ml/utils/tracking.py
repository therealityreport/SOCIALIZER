from __future__ import annotations

import contextlib
from typing import Iterator

try:
    import wandb
except ImportError:  # pragma: no cover - optional dependency
    wandb = None

from ltsr_ml.config import Settings, get_settings


@contextlib.contextmanager
def maybe_init_wandb(run_name: str, settings: Settings | None = None) -> Iterator[object | None]:
    """Context manager that yields an active W&B module when configured."""
    cfg = settings or get_settings()
    if wandb is None or not cfg.wandb_project:
        yield None
        return

    run = wandb.init(project=cfg.wandb_project, entity=cfg.wandb_entity, name=run_name, config=cfg.model_dump())
    try:
        yield wandb
    finally:
        run.finish()
