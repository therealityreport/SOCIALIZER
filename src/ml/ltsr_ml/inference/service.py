from __future__ import annotations

from typing import Iterable, List

from importlib import resources
from pathlib import Path

from ltsr_ml.config import Settings, get_settings
from ltsr_ml.models.bow import BagOfWordsMultiTaskModel
from ltsr_ml.models.checkpoint import load_checkpoint
from ltsr_ml.schemas import BinaryResult, CommentInference, InferenceResponse, SentimentResult, SlangInsights, SlangMatch

_DEFAULT_CHECKPOINT = resources.files("ltsr_ml.assets").joinpath("bow_checkpoint.json")


class InferenceService:
    """Deterministic inference service backed by a fine-tuned bag-of-words checkpoint."""

    def __init__(self, settings: Settings | None = None, checkpoint_path: Path | None = None) -> None:
        self.settings = settings or get_settings()
        self.model = self._load_model(checkpoint_path)

    def _load_model(self, checkpoint_path: Path | None) -> BagOfWordsMultiTaskModel:
        candidates: list[Path] = []
        if checkpoint_path:
            candidates.append(checkpoint_path)
        default_disk = self.settings.checkpoint_dir / "bow_checkpoint.json"
        candidates.append(default_disk)

        for candidate in candidates:
            if candidate.exists():
                return BagOfWordsMultiTaskModel(load_checkpoint(candidate))

        with resources.as_file(_DEFAULT_CHECKPOINT) as embedded_path:
            data = load_checkpoint(embedded_path)
        return BagOfWordsMultiTaskModel(data)

    def predict(self, texts: Iterable[str]) -> InferenceResponse:
        raw_predictions = self.model.predict(texts)
        results: List[CommentInference] = []

        for sentiment, sarcasm, toxicity, slang in raw_predictions:
            slang_matches = [
                SlangMatch(term=match.term, weight=round(match.weight, 3), count=match.count, tags=list(match.tags))
                for match in slang.matches
            ]
            slang_payload = SlangInsights(score=round(slang.score, 3), matches=slang_matches)
            results.append(
                CommentInference(
                    sentiment=SentimentResult(label=sentiment.label, confidence=round(sentiment.confidence, 4)),
                    sarcasm=BinaryResult(is_positive=sarcasm.is_positive, confidence=round(sarcasm.confidence, 4)),
                    toxicity=BinaryResult(is_positive=toxicity.is_positive, confidence=round(toxicity.confidence, 4)),
                    slang=slang_payload,
                )
            )

        return InferenceResponse(model_version=self.settings.model_version, results=results)
