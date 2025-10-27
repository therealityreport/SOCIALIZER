from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

try:  # pragma: no cover - heavy dependencies
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, Dataset
    from transformers.optimization import get_linear_schedule_with_warmup
except ImportError as exc:  # pragma: no cover - runtime guard
    raise RuntimeError(
        "PyTorch and transformers are required for the training pipeline. Install extras from src/ml/requirements.txt."
    ) from exc

from ltsr_ml.config import Settings, get_settings
from ltsr_ml.models.checkpoint import CheckpointData, load_checkpoint, save_checkpoint
from ltsr_ml.training.datasets import CommentDatasetBuilder, Record
from ltsr_ml.utils.text import BagOfWordsFeaturizer
from ltsr_ml.utils.tracking import maybe_init_wandb

logger = logging.getLogger(__name__)

_DEFAULT_CHECKPOINT_RESOURCE = resources.files("ltsr_ml.assets").joinpath("bow_checkpoint.json")
_SENTIMENT_TO_INDEX = {"positive": 0, "neutral": 1, "negative": 2}


@dataclass
class TrainingConfig:
    output_dir: Path
    settings: Settings


class _CommentDataset(Dataset[dict[str, torch.Tensor]]):
    def __init__(self, records: Sequence[Record], featurizer: BagOfWordsFeaturizer) -> None:
        self.featurizer = featurizer
        self.features = np.stack([self.featurizer.transform(record.text) for record in records]).astype(np.float32)
        self.sentiment = np.array([_SENTIMENT_TO_INDEX.get(record.sentiment.lower(), 1) for record in records], dtype=np.int64)
        self.sarcasm = np.array([1 if record.sarcasm else 0 for record in records], dtype=np.float32)
        self.toxicity = np.array([1 if record.toxicity else 0 for record in records], dtype=np.float32)

    def __len__(self) -> int:
        return len(self.features)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        return {
            "features": torch.from_numpy(self.features[idx]),
            "sentiment": torch.tensor(self.sentiment[idx]),
            "sarcasm": torch.tensor(self.sarcasm[idx]),
            "toxicity": torch.tensor(self.toxicity[idx]),
        }


class _BagOfWordsModule(nn.Module):
    def __init__(self, checkpoint: CheckpointData) -> None:
        super().__init__()
        vocab_size = len(checkpoint.vocabulary)

        self.sentiment_weights = nn.Parameter(torch.tensor(checkpoint.sentiment_weights, dtype=torch.float32))
        self.sentiment_bias = nn.Parameter(torch.tensor(checkpoint.sentiment_bias, dtype=torch.float32))
        self.sarcasm_weights = nn.Parameter(torch.tensor(checkpoint.sarcasm_weights, dtype=torch.float32).unsqueeze(0))
        self.sarcasm_bias = nn.Parameter(torch.tensor([checkpoint.sarcasm_bias], dtype=torch.float32))
        self.toxicity_weights = nn.Parameter(torch.tensor(checkpoint.toxicity_weights, dtype=torch.float32).unsqueeze(0))
        self.toxicity_bias = nn.Parameter(torch.tensor([checkpoint.toxicity_bias], dtype=torch.float32))

        if self.sentiment_weights.shape[1] != vocab_size:
            raise ValueError("Checkpoint weights do not align with vocabulary size.")

    def forward(self, inputs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        sentiment_logits = torch.matmul(inputs, self.sentiment_weights.t()) + self.sentiment_bias
        sarcasm_logits = torch.matmul(inputs, self.sarcasm_weights.t()).squeeze(-1) + self.sarcasm_bias.squeeze(-1)
        toxicity_logits = torch.matmul(inputs, self.toxicity_weights.t()).squeeze(-1) + self.toxicity_bias.squeeze(-1)
        return sentiment_logits, sarcasm_logits, toxicity_logits

    def to_checkpoint(self, vocabulary: list[str]) -> CheckpointData:
        return CheckpointData(
            vocabulary=vocabulary,
            sentiment_weights=self.sentiment_weights.detach().cpu().tolist(),
            sentiment_bias=self.sentiment_bias.detach().cpu().tolist(),
            sarcasm_weights=self.sarcasm_weights.detach().cpu().squeeze(0).tolist(),
            sarcasm_bias=float(self.sarcasm_bias.detach().cpu().item()),
            toxicity_weights=self.toxicity_weights.detach().cpu().squeeze(0).tolist(),
            toxicity_bias=float(self.toxicity_bias.detach().cpu().item()),
        )


class TrainingPipeline:
    def __init__(self, config: TrainingConfig | None = None) -> None:
        settings = get_settings()
        self.config = config or TrainingConfig(output_dir=settings.checkpoint_dir, settings=settings)
        self.dataset_builder = CommentDatasetBuilder()

        with resources.as_file(_DEFAULT_CHECKPOINT_RESOURCE) as default_path:
            self.base_checkpoint = load_checkpoint(default_path)
        self.featurizer = BagOfWordsFeaturizer(self.base_checkpoint.vocabulary)

    def prepare_dataset(self) -> Iterable[Record]:
        try:
            sample = list(self.dataset_builder.take(limit=100))
        except FileNotFoundError:
            sample = []
        if sample:
            return sample
        logger.warning("No processed dataset found; using synthetic bootstrap examples for training preview.")
        return self._synthetic_dataset()

    def _synthetic_dataset(self) -> list[Record]:
        return [
            Record(text="I love this episode so much", sentiment="positive", sarcasm=False, toxicity=False),
            Record(text="That plot twist was terrible and boring", sentiment="negative", sarcasm=False, toxicity=False),
            Record(text="Sure Jan, that went well /s", sentiment="negative", sarcasm=True, toxicity=False),
            Record(text="The reunion was meh but not awful", sentiment="neutral", sarcasm=False, toxicity=False),
            Record(text="They acted like idiots, absolutely stupid", sentiment="negative", sarcasm=False, toxicity=True),
        ]

    def train(self) -> Path:
        settings = self.config.settings
        device = torch.device(settings.device if settings.device != "cuda" or torch.cuda.is_available() else "cpu")

        records = list(self.prepare_dataset())
        dataset = _CommentDataset(records, self.featurizer)
        dataloader = DataLoader(dataset, batch_size=settings.train_batch_size, shuffle=True)
        total_steps = settings.num_epochs * max(1, len(dataloader))
        warmup_steps = int(total_steps * settings.warmup_ratio)

        model = _BagOfWordsModule(self.base_checkpoint).to(device)

        optimizer = torch.optim.AdamW(model.parameters(), lr=settings.learning_rate, weight_decay=settings.weight_decay)
        scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps)

        sentiment_loss = nn.CrossEntropyLoss()
        binary_loss = nn.BCEWithLogitsLoss()

        global_step = 0
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = self.config.output_dir / "bow_checkpoint.json"

        with maybe_init_wandb("bow-multitask-training", settings) as wandb_ref:
            for epoch in range(settings.num_epochs):
                model.train()
                epoch_loss = 0.0

                for batch in dataloader:
                    features = batch["features"].to(device)
                    target_sentiment = batch["sentiment"].to(device)
                    target_sarcasm = batch["sarcasm"].to(device)
                    target_toxicity = batch["toxicity"].to(device)

                    optimizer.zero_grad()

                    sent_logits, sarcasm_logits, toxicity_logits = model(features)
                    loss_sentiment = sentiment_loss(sent_logits, target_sentiment)
                    loss_sarcasm = binary_loss(sarcasm_logits, target_sarcasm)
                    loss_toxicity = binary_loss(toxicity_logits, target_toxicity)

                    loss = loss_sentiment + loss_sarcasm + loss_toxicity
                    loss.backward()
                    nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

                    optimizer.step()
                    scheduler.step()

                    epoch_loss += float(loss.detach().cpu().item())
                    global_step += 1

                    if wandb_ref:
                        wandb_ref.log(  # type: ignore[call-arg]
                            {
                                "loss/total": float(loss.detach().cpu().item()),
                                "loss/sentiment": float(loss_sentiment.detach().cpu().item()),
                                "loss/sarcasm": float(loss_sarcasm.detach().cpu().item()),
                                "loss/toxicity": float(loss_toxicity.detach().cpu().item()),
                            },
                            step=global_step,
                        )

                avg_loss = epoch_loss / max(1, len(dataloader))
                logger.info("Epoch %s/%s - loss=%.4f", epoch + 1, settings.num_epochs, avg_loss)

        checkpoint = model.to_checkpoint(self.base_checkpoint.vocabulary)
        save_checkpoint(checkpoint_path, checkpoint)
        logger.info("Saved updated checkpoint to %s", checkpoint_path)
        return checkpoint_path
