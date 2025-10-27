from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass
class BagOfWordsFeaturizer:
    vocabulary: list[str]

    def __post_init__(self) -> None:
        self._patterns: list[re.Pattern[str]] = [
            re.compile(rf"\b{re.escape(term)}\b", flags=re.IGNORECASE) if " " not in term else re.compile(re.escape(term), flags=re.IGNORECASE)
            for term in self.vocabulary
        ]

    def transform(self, text: str) -> np.ndarray:
        if not text:
            return np.zeros(len(self.vocabulary), dtype=np.float32)

        lower = text.lower()
        counts = []
        tokens = re.findall(r"\b\w+\b", lower)
        token_counts = {token: tokens.count(token) for token in set(tokens)}

        for term, pattern in zip(self.vocabulary, self._patterns):
            if " " in term:
                counts.append(len(pattern.findall(lower)))
            else:
                counts.append(float(token_counts.get(term.lower(), 0)))

        vector = np.array(counts, dtype=np.float32)
        return vector

    def batch_transform(self, texts: Iterable[str]) -> np.ndarray:
        return np.stack([self.transform(text) for text in texts])
