"""Provider Selection Service

Automated selection of optimal LLM provider based on benchmark results.
"""
import csv
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider_cost import ProviderSelectionLog

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Active provider configuration"""

    provider: str
    model: str
    selected_at: str
    provider_score: float
    mean_confidence: float
    cost_per_1k_tokens: float
    reason: str
    fallback_provider: str
    fallback_model: str


class ProviderSelector:
    """Handles automated provider selection"""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize provider selector

        Args:
            config_path: Path to active_provider.json (default: config/active_provider.json)
        """
        if config_path is None:
            config_path = Path("config/active_provider.json")

        self.config_path = config_path
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def read_benchmark_summary(self, summary_path: Path) -> list[dict[str, Any]]:
        """
        Read benchmark summary CSV

        Args:
            summary_path: Path to benchmark_summary.csv

        Returns:
            List of provider metrics dicts
        """
        if not summary_path.exists():
            raise FileNotFoundError(f"Benchmark summary not found: {summary_path}")

        providers = []
        with open(summary_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numeric fields
                row['provider_score'] = float(row['provider_score'])
                row['mean_confidence'] = float(row['mean_confidence'])
                row['cost_per_1k_tokens'] = float(row['cost_per_1k_tokens'])
                row['mean_latency'] = float(row['mean_latency'])
                row['mean_agreement'] = float(row['mean_agreement'])
                providers.append(row)

        return providers

    def select_provider(
        self,
        providers: list[dict[str, Any]],
        threshold_pct: float = 0.15,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Select optimal provider based on score

        Args:
            providers: List of provider metrics
            threshold_pct: Select providers within this % of max score (default 0.15 = 15%)

        Returns:
            Tuple of (primary_provider, fallback_provider)
        """
        if not providers:
            raise ValueError("No providers available")

        # Sort by provider_score descending
        sorted_providers = sorted(
            providers,
            key=lambda p: p['provider_score'],
            reverse=True,
        )

        # Get max score
        max_score = sorted_providers[0]['provider_score']

        # Find providers within threshold
        threshold = (1.0 - threshold_pct) * max_score
        candidates = [p for p in sorted_providers if p['provider_score'] >= threshold]

        if len(candidates) == 0:
            candidates = [sorted_providers[0]]

        # Among high performers, choose lowest cost
        primary = min(candidates, key=lambda p: p['cost_per_1k_tokens'])

        # Select fallback (second best by score)
        fallback = sorted_providers[1] if len(sorted_providers) > 1 else sorted_providers[0]

        logger.info(f"Selected primary provider: {primary['provider']} (score={primary['provider_score']:.4f})")
        logger.info(f"Selected fallback provider: {fallback['provider']} (score={fallback['provider_score']:.4f})")

        return primary, fallback

    def get_model_for_provider(self, provider: str) -> str:
        """Get model name for provider from environment"""
        model_map = {
            "openai": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            "gemini": os.getenv("GEMINI_MODEL", "gemini-1.5-pro"),
        }
        return model_map.get(provider, "unknown")

    def build_config(
        self,
        primary: dict[str, Any],
        fallback: dict[str, Any],
        reason: str = "highest_score",
    ) -> ProviderConfig:
        """
        Build provider configuration

        Args:
            primary: Primary provider metrics
            fallback: Fallback provider metrics
            reason: Reason for selection

        Returns:
            ProviderConfig
        """
        return ProviderConfig(
            provider=primary['provider'],
            model=self.get_model_for_provider(primary['provider']),
            selected_at=datetime.utcnow().isoformat() + "Z",
            provider_score=primary['provider_score'],
            mean_confidence=primary['mean_confidence'],
            cost_per_1k_tokens=primary['cost_per_1k_tokens'],
            reason=reason,
            fallback_provider=fallback['provider'],
            fallback_model=self.get_model_for_provider(fallback['provider']),
        )

    def write_config(self, config: ProviderConfig) -> None:
        """
        Write provider config to JSON file

        Args:
            config: Provider configuration
        """
        config_dict = {
            "provider": config.provider,
            "model": config.model,
            "selected_at": config.selected_at,
            "provider_score": config.provider_score,
            "mean_confidence": config.mean_confidence,
            "cost_per_1k_tokens": config.cost_per_1k_tokens,
            "reason": config.reason,
            "fallback_provider": config.fallback_provider,
            "fallback_model": config.fallback_model,
        }

        with open(self.config_path, 'w') as f:
            json.dump(config_dict, f, indent=2)

        logger.info(f"Wrote provider config to {self.config_path}")

    def read_config(self) -> Optional[ProviderConfig]:
        """
        Read current provider config

        Returns:
            ProviderConfig or None if not found
        """
        if not self.config_path.exists():
            return None

        with open(self.config_path, 'r') as f:
            data = json.load(f)

        return ProviderConfig(**data)

    async def log_selection(
        self,
        session: AsyncSession,
        config: ProviderConfig,
    ) -> None:
        """
        Log provider selection to database

        Args:
            session: Database session
            config: Provider configuration
        """
        log_entry = ProviderSelectionLog(
            provider=config.provider,
            model=config.model,
            provider_score=config.provider_score,
            mean_confidence=config.mean_confidence,
            cost_per_1k_tokens=config.cost_per_1k_tokens,
            reason=config.reason,
            fallback_provider=config.fallback_provider,
        )

        session.add(log_entry)
        await session.commit()

        logger.info(f"Logged provider selection: {config.provider}")

    def update_environment(self, config: ProviderConfig) -> None:
        """
        Update PROVIDER_PREFERRED environment variable

        Args:
            config: Provider configuration

        Note:
            This only updates the current process environment.
            For persistent changes, update .env file or system environment.
        """
        os.environ["PROVIDER_PREFERRED"] = config.provider
        logger.info(f"Updated PROVIDER_PREFERRED={config.provider}")

    async def select_and_update(
        self,
        session: AsyncSession,
        summary_path: Path = Path("qa_reports/benchmark_summary.csv"),
        force: bool = False,
    ) -> ProviderConfig:
        """
        Main workflow: select provider and update configuration

        Args:
            session: Database session
            summary_path: Path to benchmark summary
            force: Force update even if provider hasn't changed

        Returns:
            ProviderConfig
        """
        # Read current config
        current_config = self.read_config()

        # Read benchmark results
        providers = self.read_benchmark_summary(summary_path)

        # Select optimal provider
        primary, fallback = self.select_provider(providers)

        # Build new config
        new_config = self.build_config(primary, fallback)

        # Check if provider changed
        if current_config and current_config.provider == new_config.provider and not force:
            logger.info(f"Provider unchanged: {new_config.provider}")
            return current_config

        # Update configuration
        self.write_config(new_config)
        self.update_environment(new_config)

        # Log selection
        await self.log_selection(session, new_config)

        logger.info(f"Provider updated: {current_config.provider if current_config else 'None'} → {new_config.provider}")

        return new_config


def get_active_provider() -> str:
    """
    Get currently active provider

    Returns:
        Provider name (openai, anthropic, or gemini)
    """
    # First check environment variable
    provider = os.getenv("PROVIDER_PREFERRED")
    if provider:
        return provider

    # Fall back to config file
    config_path = Path("config/active_provider.json")
    if config_path.exists():
        with open(config_path, 'r') as f:
            data = json.load(f)
            return data.get("provider", "openai")

    # Default to openai
    return "openai"


def get_fallback_provider() -> str:
    """
    Get fallback provider

    Returns:
        Fallback provider name
    """
    config_path = Path("config/active_provider.json")
    if config_path.exists():
        with open(config_path, 'r') as f:
            data = json.load(f)
            return data.get("fallback_provider", "openai")

    # Default fallback
    return "openai"
