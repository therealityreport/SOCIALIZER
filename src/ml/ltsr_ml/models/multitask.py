from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

try:  # Optional heavy imports
    import torch
    from torch import nn
except ImportError:  # pragma: no cover - optional dependency
    torch = None
    nn = None

try:  # Transformers may be unavailable in some environments
    from transformers import AutoModel
except ImportError:  # pragma: no cover
    AutoModel = None


@dataclass
class MultiTaskConfig:
    base_model: str = "roberta-base"
    sentiment_labels: int = 3
    sarcasm_labels: int = 2
    toxicity_labels: int = 2
    dropout: float = 0.2


class MultiTaskSentimentModel(nn.Module if nn else object):  # type: ignore[misc]
    """Minimal multi-task head on top of a Transformer backbone."""

    def __init__(self, config: MultiTaskConfig) -> None:
        if nn is None or torch is None or AutoModel is None:
            raise RuntimeError(
                "PyTorch and transformers must be installed to use MultiTaskSentimentModel. "
                "Please install the ML extras listed in src/ml/requirements.txt.",
            )

        super().__init__()
        self.config = config

        self.backbone = AutoModel.from_pretrained(config.base_model)
        hidden_size = getattr(self.backbone.config, "hidden_size", 768)
        dropout = getattr(nn, "Dropout")(config.dropout)  # type: ignore[call-arg]

        self.dropout = dropout
        self.sentiment_head = nn.Linear(hidden_size, config.sentiment_labels)
        self.sarcasm_head = nn.Linear(hidden_size, config.sarcasm_labels)
        self.toxicity_head = nn.Linear(hidden_size, config.toxicity_labels)

    def forward(self, input_ids: Any, attention_mask: Any) -> Dict[str, Any]:  # pragma: no cover - requires torch
        backbone_outputs = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        pooled = backbone_outputs.last_hidden_state[:, 0]
        pooled = self.dropout(pooled)

        return {
            "sentiment": self.sentiment_head(pooled),
            "sarcasm": self.sarcasm_head(pooled),
            "toxicity": self.toxicity_head(pooled),
        }
