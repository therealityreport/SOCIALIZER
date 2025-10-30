"""Automated LLM Provider Selection Job

Runs nightly to select optimal LLM provider based on benchmark results.
Updates config/active_provider.json and PROVIDER_PREFERRED environment variable.
"""
import asyncio
import argparse
import logging
import sys
from pathlib import Path

from app.db.session import get_async_session
from app.services.provider_selection import ProviderSelector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Automated LLM provider selection"
    )
    parser.add_argument(
        "--summary-path",
        type=str,
        default="qa_reports/benchmark_summary.csv",
        help="Path to benchmark summary CSV",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force update even if provider hasn't changed",
    )
    parser.add_argument(
        "--config-path",
        type=str,
        default="config/active_provider.json",
        help="Path to active provider config file",
    )
    args = parser.parse_args()

    summary_path = Path(args.summary_path)
    config_path = Path(args.config_path)

    logger.info("=" * 80)
    logger.info("AUTOMATED PROVIDER SELECTION JOB")
    logger.info("=" * 80)
    logger.info(f"Summary path: {summary_path}")
    logger.info(f"Config path: {config_path}")
    logger.info(f"Force update: {args.force}")
    logger.info("=" * 80)

    # Check if benchmark summary exists
    if not summary_path.exists():
        logger.error(f"Benchmark summary not found: {summary_path}")
        logger.error("Please run benchmark first: python jobs/backfill_reddit_mentions.py --benchmark-mode")
        sys.exit(1)

    # Initialize selector
    selector = ProviderSelector(config_path=config_path)

    # Run selection
    async for session in get_async_session():
        try:
            config = await selector.select_and_update(
                session,
                summary_path=summary_path,
                force=args.force,
            )

            logger.info("\n" + "=" * 80)
            logger.info("PROVIDER SELECTION COMPLETE")
            logger.info("=" * 80)
            logger.info(f"Active Provider:     {config.provider}")
            logger.info(f"Model:               {config.model}")
            logger.info(f"Provider Score:      {config.provider_score:.4f}")
            logger.info(f"Mean Confidence:     {config.mean_confidence:.4f}")
            logger.info(f"Cost per 1K tokens:  ${config.cost_per_1k_tokens:.6f}")
            logger.info(f"Fallback Provider:   {config.fallback_provider}")
            logger.info(f"Fallback Model:      {config.fallback_model}")
            logger.info(f"Reason:              {config.reason}")
            logger.info(f"Selected At:         {config.selected_at}")
            logger.info("=" * 80)

            # Reminder about environment variable
            logger.info("\nNOTE: PROVIDER_PREFERRED environment variable updated in current process.")
            logger.info("For persistent changes, update your .env file:")
            logger.info(f"  PROVIDER_PREFERRED={config.provider}")

        except FileNotFoundError as e:
            logger.error(f"Error: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Provider selection failed: {e}", exc_info=True)
            sys.exit(1)
        finally:
            await session.close()


if __name__ == "__main__":
    asyncio.run(main())
