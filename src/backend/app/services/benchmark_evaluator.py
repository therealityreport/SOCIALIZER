"""Benchmark Evaluator for LLM Provider Comparison

Scores and compares multiple LLM providers based on:
- Confidence levels
- Execution time/latency
- Cost per token
- Agreement with other providers
- Overall provider score
"""
import csv
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.llm_providers import LLMAnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class ProviderMetrics:
    """Metrics for a single provider"""

    provider: str
    call_count: int
    mean_confidence: float
    std_confidence: float
    mean_latency: float
    std_latency: float
    total_tokens: int
    total_cost: float
    cost_per_1k_tokens: float
    agreement_scores: list[float]
    mean_agreement: float
    provider_score: float  # Composite score

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "provider": self.provider,
            "call_count": self.call_count,
            "mean_confidence": round(self.mean_confidence, 4),
            "std_confidence": round(self.std_confidence, 4),
            "mean_latency": round(self.mean_latency, 4),
            "std_latency": round(self.std_latency, 4),
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 6),
            "cost_per_1k_tokens": round(self.cost_per_1k_tokens, 6),
            "mean_agreement": round(self.mean_agreement, 4),
            "provider_score": round(self.provider_score, 4),
        }


class BenchmarkEvaluator:
    """Evaluates and compares LLM provider performance"""

    def __init__(self):
        """Initialize benchmark evaluator"""
        self.provider_data: dict[str, list[LLMAnalysisResult]] = defaultdict(list)
        self.agreement_scores: dict[str, list[float]] = defaultdict(list)

    def add_result(
        self,
        provider: str,
        result: LLMAnalysisResult,
        agreement_score: float,
    ) -> None:
        """
        Add a provider result to the benchmark data

        Args:
            provider: Provider name
            result: LLM analysis result
            agreement_score: Agreement score with other providers
        """
        self.provider_data[provider].append(result)
        self.agreement_scores[provider].append(agreement_score)

    def calculate_metrics(self) -> dict[str, ProviderMetrics]:
        """
        Calculate aggregate metrics for all providers

        Returns:
            Dict mapping provider name to ProviderMetrics
        """
        metrics = {}

        for provider, results in self.provider_data.items():
            if not results:
                continue

            # Confidence stats
            confidences = [r.confidence for r in results]
            mean_confidence = sum(confidences) / len(confidences)
            variance_conf = sum((c - mean_confidence) ** 2 for c in confidences) / len(confidences)
            std_confidence = variance_conf ** 0.5

            # Latency stats
            latencies = [r.execution_time for r in results]
            mean_latency = sum(latencies) / len(latencies)
            variance_lat = sum((l - mean_latency) ** 2 for l in latencies) / len(latencies)
            std_latency = variance_lat ** 0.5

            # Token and cost stats
            total_tokens = sum(r.token_count or 0 for r in results)
            total_cost = sum(r.cost_estimate or 0.0 for r in results)
            cost_per_1k_tokens = (total_cost / (total_tokens / 1000)) if total_tokens > 0 else 0.0

            # Agreement stats
            agreements = self.agreement_scores[provider]
            mean_agreement = sum(agreements) / len(agreements) if agreements else 0.0

            # Calculate composite provider score
            # Formula: 0.4 * confidence + 0.3 * agreement + 0.2 * (1 - normalized_latency) + 0.1 * (1 - normalized_cost)
            max_latency = max(latencies) if latencies else 1.0
            normalized_latency = mean_latency / max_latency if max_latency > 0 else 0.0

            max_cost = max(cost_per_1k_tokens for _ in self.provider_data.values()) if cost_per_1k_tokens > 0 else 1.0
            normalized_cost = cost_per_1k_tokens / max_cost if max_cost > 0 else 0.0

            provider_score = (
                0.4 * mean_confidence +
                0.3 * mean_agreement +
                0.2 * (1.0 - normalized_latency) +
                0.1 * (1.0 - normalized_cost)
            )

            metrics[provider] = ProviderMetrics(
                provider=provider,
                call_count=len(results),
                mean_confidence=mean_confidence,
                std_confidence=std_confidence,
                mean_latency=mean_latency,
                std_latency=std_latency,
                total_tokens=total_tokens,
                total_cost=total_cost,
                cost_per_1k_tokens=cost_per_1k_tokens,
                agreement_scores=agreements,
                mean_agreement=mean_agreement,
                provider_score=provider_score,
            )

        return metrics

    def generate_summary_report(
        self,
        output_path: Path,
    ) -> None:
        """
        Generate summary CSV report of provider performance

        Args:
            output_path: Path to output CSV file
        """
        metrics = self.calculate_metrics()

        if not metrics:
            logger.warning("No metrics to report")
            return

        # Write summary CSV
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', newline='') as f:
            fieldnames = [
                "provider",
                "call_count",
                "mean_confidence",
                "std_confidence",
                "mean_latency",
                "std_latency",
                "total_tokens",
                "total_cost",
                "cost_per_1k_tokens",
                "mean_agreement",
                "provider_score",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for metric in sorted(metrics.values(), key=lambda m: m.provider_score, reverse=True):
                writer.writerow(metric.to_dict())

        logger.info(f"Generated summary report: {output_path}")

    def generate_detail_report(
        self,
        output_path: Path,
        comment_data: list[dict[str, Any]],
    ) -> None:
        """
        Generate detailed per-comment comparison CSV

        Args:
            output_path: Path to output CSV file
            comment_data: List of dicts with comment metadata and provider results
        """
        if not comment_data:
            logger.warning("No comment data to report")
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Determine all providers from first comment
        providers = []
        if comment_data:
            first_comment = comment_data[0]
            providers = [k for k in first_comment.keys() if k.endswith("_sentiment")]
            providers = [p.replace("_sentiment", "") for p in providers]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ["comment_id", "cast_member", "text"]

            # Add provider-specific columns
            for provider in providers:
                fieldnames.extend([
                    f"{provider}_sentiment",
                    f"{provider}_confidence",
                    f"{provider}_sarcasm",
                ])

            fieldnames.extend(["agreement_score", "best_provider"])

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(comment_data)

        logger.info(f"Generated detail report: {output_path}")

    def print_summary(self) -> None:
        """Print summary of benchmark results to console"""
        metrics = self.calculate_metrics()

        if not metrics:
            print("No benchmark data available")
            return

        print("\n" + "=" * 80)
        print("LLM PROVIDER BENCHMARK SUMMARY")
        print("=" * 80)

        for provider, metric in sorted(metrics.items(), key=lambda x: x[1].provider_score, reverse=True):
            print(f"\n{provider.upper()}:")
            print(f"  Calls:              {metric.call_count}")
            print(f"  Mean Confidence:    {metric.mean_confidence:.4f} ± {metric.std_confidence:.4f}")
            print(f"  Mean Latency:       {metric.mean_latency:.4f}s ± {metric.std_latency:.4f}s")
            print(f"  Total Tokens:       {metric.total_tokens:,}")
            print(f"  Total Cost:         ${metric.total_cost:.6f}")
            print(f"  Cost per 1K tokens: ${metric.cost_per_1k_tokens:.6f}")
            print(f"  Mean Agreement:     {metric.mean_agreement:.4f}")
            print(f"  PROVIDER SCORE:     {metric.provider_score:.4f}")

        print("=" * 80 + "\n")

    def get_best_provider(self) -> str:
        """Get the name of the best-performing provider"""
        metrics = self.calculate_metrics()
        if not metrics:
            return "unknown"

        best = max(metrics.values(), key=lambda m: m.provider_score)
        return best.provider
