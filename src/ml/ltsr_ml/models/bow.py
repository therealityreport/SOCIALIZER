from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from ltsr_ml.models.checkpoint import CheckpointData
from ltsr_ml.utils.slang import SlangAnalysisResult, SlangLexicon, load_default_lexicon
from ltsr_ml.utils.text import BagOfWordsFeaturizer


@dataclass
class SentimentPrediction:
    label: str
    confidence: float


@dataclass
class BinaryPrediction:
    is_positive: bool
    confidence: float


class BagOfWordsMultiTaskModel:
    """Simple multi-task classifier backed by a bag-of-words checkpoint."""

    def __init__(self, checkpoint: CheckpointData, lexicon: SlangLexicon | None = None) -> None:
        self.featurizer = BagOfWordsFeaturizer(checkpoint.vocabulary)
        self.sentiment_weights = np.array(checkpoint.sentiment_weights, dtype=np.float32)
        self.sentiment_bias = np.array(checkpoint.sentiment_bias, dtype=np.float32)
        self.sarcasm_weights = np.array(checkpoint.sarcasm_weights, dtype=np.float32)
        self.sarcasm_bias = float(checkpoint.sarcasm_bias)
        self.toxicity_weights = np.array(checkpoint.toxicity_weights, dtype=np.float32)
        self.toxicity_bias = float(checkpoint.toxicity_bias)
        self.slang_lexicon = lexicon or load_default_lexicon()

    def predict_sentiment(self, vector: np.ndarray, slang_score: float = 0.0) -> SentimentPrediction:
        logits = self.sentiment_weights @ vector + self.sentiment_bias
        if slang_score:
            logits = self._apply_slang_adjustment(logits, slang_score)
        return self._logits_to_prediction(logits)

    def predict_binary(self, vector: np.ndarray, weights: np.ndarray, bias: float) -> BinaryPrediction:
        logit = float(weights @ vector + bias)
        conf = 1.0 / (1.0 + math.exp(-logit))
        return BinaryPrediction(is_positive=conf >= 0.5, confidence=conf)

    def predict(self, texts: Iterable[str]) -> list[tuple[SentimentPrediction, BinaryPrediction, BinaryPrediction, SlangAnalysisResult]]:
        predictions = []
        for text in texts:
            vector = self.featurizer.transform(text)
            slang_analysis = self.slang_lexicon.analyze(text)
            sentiment = self.predict_sentiment(vector, slang_analysis.score)
            sarcasm = self.predict_binary(vector, self.sarcasm_weights, self.sarcasm_bias)
            toxicity = self.predict_binary(vector, self.toxicity_weights, self.toxicity_bias)
            predictions.append((sentiment, sarcasm, toxicity, slang_analysis))
        return predictions

    def _apply_slang_adjustment(self, logits: np.ndarray, slang_score: float) -> np.ndarray:
        adjusted = logits.astype(np.float32, copy=True)
        delta = float(np.clip(slang_score, -2.0, 2.0))
        if delta > 0:
            adjusted[0] += delta
            adjusted[2] -= delta * 0.5
        elif delta < 0:
            value = abs(delta)
            adjusted[2] += value
            adjusted[0] -= value * 0.5
        return adjusted

    def _logits_to_prediction(self, logits: np.ndarray) -> SentimentPrediction:
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / exp_logits.sum()
        idx = int(np.argmax(probs))
        label = ["positive", "neutral", "negative"][idx]
        return SentimentPrediction(label=label, confidence=float(probs[idx]))
