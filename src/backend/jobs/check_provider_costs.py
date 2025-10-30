"""Daily Provider Cost Check Job

Checks monthly provider costs and sends alerts if budget thresholds exceeded.
Should be run daily via cron/scheduler.
"""
import asyncio
import argparse
import logging
import os
from datetime import datetime

from app.db.session import get_async_session
from app.services.cost_monitor import get_cost_monitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Check provider costs and send budget alerts"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=float(os.getenv("COST_ALERT_THRESHOLD", "500.0")),
        help="Monthly budget threshold in USD (default $500)",
    )
    parser.add_argument(
        "--summary-days",
        type=int,
        default=30,
        help="Number of days for summary report (default 30)",
    )
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("PROVIDER COST CHECK")
    logger.info("=" * 80)
    logger.info(f"Monthly Threshold: ${args.threshold:.2f}")
    logger.info(f"Check Date: {datetime.utcnow().isoformat()}")
    logger.info("=" * 80)

    cost_monitor = get_cost_monitor(monthly_threshold=args.threshold)

    async for session in get_async_session():
        try:
            # Check budget and send alerts if needed
            budget_status = await cost_monitor.check_and_alert(session)

            logger.info("\n" + "=" * 80)
            logger.info("BUDGET STATUS")
            logger.info("=" * 80)
            logger.info(f"Total Monthly Spend:  ${budget_status['total_cost']:.2f}")
            logger.info(f"Monthly Budget:       ${budget_status['monthly_threshold']:.2f}")
            logger.info(f"Percentage Used:      {budget_status['percentage_used']:.1f}%")
            logger.info(f"Remaining Budget:     ${budget_status['remaining_budget']:.2f}")
            logger.info(f"Status:               {budget_status['status']}")

            if budget_status['provider_costs']:
                logger.info("\nProvider Breakdown:")
                for provider, cost in sorted(
                    budget_status['provider_costs'].items(),
                    key=lambda x: x[1],
                    reverse=True
                ):
                    pct = (cost / budget_status['total_cost'] * 100) if budget_status['total_cost'] > 0 else 0
                    logger.info(f"  {provider:15s} ${cost:8.2f} ({pct:5.1f}%)")

            # Get cost summary
            summary = await cost_monitor.get_cost_summary(session, days=args.summary_days)

            logger.info("\n" + "=" * 80)
            logger.info(f"COST SUMMARY (Last {args.summary_days} Days)")
            logger.info("=" * 80)
            logger.info(f"Period:         {summary['start_date']} to {summary['end_date']}")
            logger.info(f"Total Cost:     ${summary['total_cost']:.2f}")
            logger.info(f"Daily Records:  {summary['daily_records']}")

            if summary['provider_totals']:
                logger.info("\nProvider Totals:")
                for provider, totals in sorted(
                    summary['provider_totals'].items(),
                    key=lambda x: x[1]['total_cost'],
                    reverse=True
                ):
                    logger.info(f"\n  {provider.upper()}:")
                    logger.info(f"    Total Cost:         ${totals['total_cost']:.2f}")
                    logger.info(f"    Total Tokens:       {totals['total_tokens']:,}")
                    logger.info(f"    Total Comments:     {totals['total_comments']:,}")
                    logger.info(f"    Cost per 1K tokens: ${totals['cost_per_1k_tokens']:.6f}")
                    logger.info(f"    Cost per comment:   ${totals['cost_per_comment']:.6f}")

            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Cost check failed: {e}", exc_info=True)
            raise
        finally:
            await session.close()


if __name__ == "__main__":
    asyncio.run(main())
