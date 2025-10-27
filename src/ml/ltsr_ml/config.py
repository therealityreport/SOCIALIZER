from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration options for ML training and inference."""

    model_config = SettingsConfigDict(
        env_prefix="ML_",
        env_file=".env",
        env_file_encoding="utf-8",
        protected_namespaces=("settings_",),
        extra="allow",
    )

    # Model / tokenizer
    model_name: str = Field(default="roberta-base", description="Hugging Face model ID used for fine-tuning.")
    model_revision: str | None = Field(default=None, description="Optional Hugging Face revision (tag/commit).")
    model_version: str = Field(default="v0", description="Semantic version of the exported model.")
    max_length: int = Field(default=256, ge=32, le=1024, description="Maximum token length for inference.")

    # Training hyperparameters
    train_batch_size: int = Field(default=16, ge=1, description="Training batch size.")
    eval_batch_size: int = Field(default=32, ge=1, description="Evaluation batch size.")
    learning_rate: float = Field(default=3e-5, gt=0, description="Base learning rate for AdamW.")
    weight_decay: float = Field(default=0.01, ge=0, description="Weight decay applied during training.")
    num_epochs: int = Field(default=3, ge=1, description="Number of fine-tuning epochs.")
    warmup_ratio: float = Field(default=0.1, ge=0, le=1, description="Linear warmup ratio for scheduler.")

    # File system configuration
    data_dir: Path = Field(default=Path("data/raw"), description="Location of raw training data.")
    processed_dir: Path = Field(default=Path("data/processed"), description="Location of processed datasets.")
    checkpoint_dir: Path = Field(default=Path("data/models"), description="Directory for model checkpoints.")

    # Serving configuration
    device: str = Field(default="cpu", description="Compute device identifier (cpu/cuda).")
    inference_batch_size: int = Field(default=32, ge=1, description="Batch size used during inference service.")

    # Experiment tracking
    wandb_project: str | None = Field(default=None, description="Weights & Biases project name.")
    wandb_entity: str | None = Field(default=None, description="Weights & Biases entity/team.")

    # spaCy entity linking (for ML pipeline integration)
    spacy_model: str = Field(default="en_core_web_lg", description="spaCy model for entity linking preprocessing.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
