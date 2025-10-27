from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from ltsr_ml.config import get_settings


@dataclass
class Record:
    text: str
    sentiment: str
    sarcasm: bool
    toxicity: bool


class CommentDatasetBuilder:
    """Simple loader that yields annotated comments for training."""

    def __init__(self, data_path: Path | None = None) -> None:
        self.settings = get_settings()
        self.data_path = data_path or self.settings.processed_dir / "comments.jsonl"

    def __iter__(self) -> Iterator[Record]:
        if not self.data_path.exists():
            raise FileNotFoundError(
                f"Processed dataset not found at {self.data_path}. "
                "Run the data preparation pipeline first.",
            )

        with self.data_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                payload = json.loads(line)
                yield Record(
                    text=payload["text"],
                    sentiment=payload["sentiment"],
                    sarcasm=payload.get("sarcasm", False),
                    toxicity=payload.get("toxicity", False),
                )

    def take(self, limit: int) -> Iterable[Record]:
        for idx, record in enumerate(self):
            if idx >= limit:
                break
            yield record
