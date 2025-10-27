from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(slots=True)
class SentimentMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float


def calculate_metrics(true_labels: Sequence[int], predicted_labels: Sequence[int]) -> SentimentMetrics:
    if not true_labels:
        raise ValueError("true_labels must not be empty.")
    if len(true_labels) != len(predicted_labels):
        raise ValueError("true_labels and predicted_labels must have the same length.")

    total = len(true_labels)
    correct = sum(1 for t, p in zip(true_labels, predicted_labels, strict=True) if t == p)

    tp = sum(1 for t, p in zip(true_labels, predicted_labels, strict=True) if t == p == 1)
    fp = sum(1 for t, p in zip(true_labels, predicted_labels, strict=True) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(true_labels, predicted_labels, strict=True) if t == 1 and p == 0)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) else 0.0

    return SentimentMetrics(
        accuracy=correct / total,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def confusion_matrix(true_labels: Iterable[int], predicted_labels: Iterable[int]) -> tuple[int, int, int, int]:
    tp = fp = tn = fn = 0
    for t, p in zip(true_labels, predicted_labels):
        if t == 1 and p == 1:
            tp += 1
        elif t == 0 and p == 1:
            fp += 1
        elif t == 0 and p == 0:
            tn += 1
        else:
            fn += 1
    return tp, fp, tn, fn
