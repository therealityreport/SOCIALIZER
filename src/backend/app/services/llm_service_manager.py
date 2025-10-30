"""LLM Service Manager for Multi-Provider Orchestration

Manages multiple LLM providers for benchmarking and A/B testing.
Supports parallel and sequential evaluation modes.
"""
import asyncio
import logging
import os
from typing import Any, Optional

from app.services.llm_providers import (
    BaseLLMClient,
    LLMAnalysisResult,
    OpenAIClient,
    AnthropicClient,
    GeminiClient,
)

logger = logging.getLogger(__name__)


class LLMServiceManager:
    """Manages multiple LLM providers for benchmarking"""

    def __init__(self, providers: Optional[list[str]] = None):
        """
        Initialize LLM service manager

        Args:
            providers: List of provider names to use (openai, anthropic, gemini)
                      If None, reads from LLM_PROVIDERS env var
        """
        if providers is None:
            providers_str = os.getenv("LLM_PROVIDERS", "openai")
            providers = [p.strip() for p in providers_str.split(",")]

        self.providers = providers
        self.eval_mode = os.getenv("LLM_EVAL_MODE", "parallel")  # parallel or sequential

        # Initialize clients
        self.clients: dict[str, BaseLLMClient] = {}
        self._initialize_clients()

        logger.info(f"LLMServiceManager initialized with providers: {self.providers}")
        logger.info(f"Evaluation mode: {self.eval_mode}")

    def _initialize_clients(self) -> None:
        """Initialize LLM client instances"""
        client_map = {
            "openai": OpenAIClient,
            "anthropic": AnthropicClient,
            "gemini": GeminiClient,
        }

        for provider in self.providers:
            if provider in client_map:
                try:
                    self.clients[provider] = client_map[provider]()
                    logger.info(f"Initialized {provider} client")
                except Exception as e:
                    logger.error(f"Failed to initialize {provider} client: {e}")
            else:
                logger.warning(f"Unknown provider: {provider}")

    async def analyze_with_all(
        self,
        text: str,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, LLMAnalysisResult]:
        """
        Analyze comment with all configured providers

        Args:
            text: Comment text
            context: Episode context

        Returns:
            Dict mapping provider name to LLMAnalysisResult
        """
        if self.eval_mode == "parallel":
            return await self._analyze_parallel(text, context)
        else:
            return await self._analyze_sequential(text, context)

    async def _analyze_parallel(
        self,
        text: str,
        context: Optional[dict[str, Any]],
    ) -> dict[str, LLMAnalysisResult]:
        """Analyze with all providers in parallel"""
        tasks = []
        provider_names = []

        for provider_name, client in self.clients.items():
            tasks.append(client.analyze(text, context))
            provider_names.append(provider_name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        provider_results = {}
        for provider_name, result in zip(provider_names, results):
            if isinstance(result, Exception):
                logger.error(f"{provider_name} analysis failed: {result}")
                # Store error result
                provider_results[provider_name] = LLMAnalysisResult(
                    primary_sentiment="NEUTRAL",
                    secondary_attitude=None,
                    emotions=[],
                    sarcasm_score=0.0,
                    sarcasm_label="not_sarcastic",
                    sarcasm_evidence=None,
                    confidence=0.0,
                    provider=provider_name,
                    model="error",
                    execution_time=0.0,
                )
            else:
                provider_results[provider_name] = result

        return provider_results

    async def _analyze_sequential(
        self,
        text: str,
        context: Optional[dict[str, Any]],
    ) -> dict[str, LLMAnalysisResult]:
        """Analyze with all providers sequentially"""
        provider_results = {}

        for provider_name, client in self.clients.items():
            try:
                result = await client.analyze(text, context)
                provider_results[provider_name] = result
            except Exception as e:
                logger.error(f"{provider_name} analysis failed: {e}")
                provider_results[provider_name] = LLMAnalysisResult(
                    primary_sentiment="NEUTRAL",
                    secondary_attitude=None,
                    emotions=[],
                    sarcasm_score=0.0,
                    sarcasm_label="not_sarcastic",
                    sarcasm_evidence=None,
                    confidence=0.0,
                    provider=provider_name,
                    model="error",
                    execution_time=0.0,
                )

        return provider_results

    def normalize_results(
        self,
        provider_results: dict[str, LLMAnalysisResult],
    ) -> dict[str, dict[str, Any]]:
        """
        Normalize provider results to unified schema

        Args:
            provider_results: Dict of provider name to LLMAnalysisResult

        Returns:
            Dict mapping provider name to normalized result dict
        """
        normalized = {}
        for provider_name, result in provider_results.items():
            normalized[provider_name] = {
                "sentiment_primary": result.primary_sentiment,
                "attitude_secondary": result.secondary_attitude,
                "emotions": result.emotions,
                "sarcasm_score": result.sarcasm_score,
                "sarcasm_label": result.sarcasm_label,
                "sarcasm_evidence": result.sarcasm_evidence,
                "confidence": result.confidence,
                "model": result.model,
                "execution_time": result.execution_time,
                "token_count": result.token_count,
                "cost_estimate": result.cost_estimate,
            }
        return normalized

    def select_preferred_provider(
        self,
        provider_results: dict[str, LLMAnalysisResult],
    ) -> tuple[str, LLMAnalysisResult]:
        """
        Select the preferred provider result based on confidence

        Args:
            provider_results: Dict of provider results

        Returns:
            Tuple of (provider_name, result)
        """
        if not provider_results:
            raise ValueError("No provider results available")

        # Sort by confidence descending
        sorted_results = sorted(
            provider_results.items(),
            key=lambda x: x[1].confidence,
            reverse=True,
        )

        return sorted_results[0]

    def calculate_agreement_score(
        self,
        provider_results: dict[str, LLMAnalysisResult],
    ) -> float:
        """
        Calculate agreement score across providers

        Agreement is based on:
        - Same primary sentiment
        - Similar sarcasm scores

        Returns:
            Agreement score 0.0-1.0
        """
        if len(provider_results) < 2:
            return 1.0

        # Get most common sentiment
        sentiments = [r.primary_sentiment for r in provider_results.values()]
        most_common = max(set(sentiments), key=sentiments.count)
        sentiment_agreement = sentiments.count(most_common) / len(sentiments)

        # Calculate sarcasm score variance
        sarcasm_scores = [r.sarcasm_score for r in provider_results.values()]
        if len(sarcasm_scores) > 1:
            mean_sarcasm = sum(sarcasm_scores) / len(sarcasm_scores)
            variance = sum((s - mean_sarcasm) ** 2 for s in sarcasm_scores) / len(sarcasm_scores)
            sarcasm_agreement = 1.0 - min(variance, 1.0)  # Lower variance = higher agreement
        else:
            sarcasm_agreement = 1.0

        # Weighted average
        agreement = 0.7 * sentiment_agreement + 0.3 * sarcasm_agreement
        return agreement


# Global singleton
_manager: Optional[LLMServiceManager] = None


def get_llm_manager(providers: Optional[list[str]] = None) -> LLMServiceManager:
    """Get or create LLM manager singleton"""
    global _manager
    if _manager is None or providers is not None:
        _manager = LLMServiceManager(providers)
    return _manager
