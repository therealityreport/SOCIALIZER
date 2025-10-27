from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CheckpointData:
    vocabulary: list[str]
    sentiment_weights: list[list[float]]
    sentiment_bias: list[float]
    sarcasm_weights: list[float]
    sarcasm_bias: float
    toxicity_weights: list[float]
    toxicity_bias: float


def load_checkpoint(path: Path) -> CheckpointData:
    data = json.loads(path.read_text(encoding="utf-8"))
    return CheckpointData(
        vocabulary=data["vocabulary"],
        sentiment_weights=data["sentiment"]["weights"],
        sentiment_bias=data["sentiment"]["bias"],
        sarcasm_weights=data["sarcasm"]["weights"],
        sarcasm_bias=data["sarcasm"]["bias"],
        toxicity_weights=data["toxicity"]["weights"],
        toxicity_bias=data["toxicity"]["bias"],
    )


def save_checkpoint(path: Path, checkpoint: CheckpointData) -> None:
    payload: dict[str, Any] = {
        "vocabulary": checkpoint.vocabulary,
        "sentiment": {"weights": checkpoint.sentiment_weights, "bias": checkpoint.sentiment_bias},
        "sarcasm": {"weights": checkpoint.sarcasm_weights, "bias": checkpoint.sarcasm_bias},
        "toxicity": {"weights": checkpoint.toxicity_weights, "bias": checkpoint.toxicity_bias},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
