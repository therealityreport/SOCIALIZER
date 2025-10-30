"""LLM Provider Cost Monitoring and Alerting Service

Tracks daily costs per provider and sends alerts when approaching monthly budget.
"""
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider_cost import ProviderCost

logger = logging.getLogger(__name__)


class CostMonitor:
    """Monitors LLM provider costs and sends budget alerts"""

    def __init__(
        self,
        monthly_threshold: float = 500.0,
        alert_thresholds: list[float] = None,
    ):
        """
        Initialize cost monitor

        Args:
            monthly_threshold: Monthly budget limit in USD (default $500)
            alert_thresholds: List of alert thresholds as fractions (default [0.75, 0.90])
        """
        self.monthly_threshold = monthly_threshold
        self.alert_thresholds = alert_thresholds or [0.75, 0.90]
        self.alert_sent: dict[float, bool] = {t: False for t in self.alert_thresholds}

    async def log_daily_cost(
        self,
        session: AsyncSession,
        provider: str,
        date: datetime,
        tokens_consumed: int,
        cost_usd: float,
        comments_analyzed: int,
    ) -> None:
        """
        Log daily cost for a provider

        Args:
            session: Database session
            provider: Provider name
            date: Date of cost
            tokens_consumed: Total tokens used
            cost_usd: Total cost in USD
            comments_analyzed: Number of comments processed
        """
        # Check if entry exists
        query = select(ProviderCost).where(
            ProviderCost.provider == provider,
            ProviderCost.date == date.date(),
        )
        result = await session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing entry
            existing.tokens_consumed += tokens_consumed
            existing.cost_usd += cost_usd
            existing.comments_analyzed += comments_analyzed
            logger.info(f"Updated cost for {provider} on {date.date()}: ${cost_usd:.6f}")
        else:
            # Create new entry
            cost_entry = ProviderCost(
                provider=provider,
                date=date.date(),
                tokens_consumed=tokens_consumed,
                cost_usd=cost_usd,
                comments_analyzed=comments_analyzed,
            )
            session.add(cost_entry)
            logger.info(f"Logged cost for {provider} on {date.date()}: ${cost_usd:.6f}")

        await session.commit()

    async def get_monthly_costs(
        self,
        session: AsyncSession,
        start_date: Optional[datetime] = None,
    ) -> dict[str, float]:
        """
        Get monthly costs per provider

        Args:
            session: Database session
            start_date: Start of month (defaults to first day of current month)

        Returns:
            Dict mapping provider name to total monthly cost
        """
        if start_date is None:
            now = datetime.utcnow()
            start_date = datetime(now.year, now.month, 1)

        query = (
            select(
                ProviderCost.provider,
                func.sum(ProviderCost.cost_usd).label("total_cost"),
            )
            .where(ProviderCost.date >= start_date.date())
            .group_by(ProviderCost.provider)
        )

        result = await session.execute(query)
        rows = result.all()

        costs = {row.provider: float(row.total_cost) for row in rows}
        return costs

    async def get_total_monthly_cost(
        self,
        session: AsyncSession,
        start_date: Optional[datetime] = None,
    ) -> float:
        """
        Get total monthly cost across all providers

        Args:
            session: Database session
            start_date: Start of month (defaults to first day of current month)

        Returns:
            Total monthly cost in USD
        """
        costs = await self.get_monthly_costs(session, start_date)
        return sum(costs.values())

    async def check_budget_status(
        self,
        session: AsyncSession,
    ) -> dict:
        """
        Check current budget status

        Args:
            session: Database session

        Returns:
            Dict with budget status information
        """
        monthly_costs = await self.get_monthly_costs(session)
        total_cost = sum(monthly_costs.values())
        percentage_used = (total_cost / self.monthly_threshold) * 100 if self.monthly_threshold > 0 else 0

        # Determine status
        status = "ok"
        for threshold in sorted(self.alert_thresholds, reverse=True):
            if total_cost >= self.monthly_threshold * threshold:
                status = f"warning_{int(threshold * 100)}"
                break

        if total_cost >= self.monthly_threshold:
            status = "critical"

        return {
            "total_cost": total_cost,
            "monthly_threshold": self.monthly_threshold,
            "percentage_used": percentage_used,
            "provider_costs": monthly_costs,
            "status": status,
            "remaining_budget": max(0, self.monthly_threshold - total_cost),
        }

    async def send_alert(
        self,
        budget_status: dict,
        threshold: float,
    ) -> None:
        """
        Send budget alert via email and Slack

        Args:
            budget_status: Budget status dict from check_budget_status()
            threshold: Alert threshold that was exceeded
        """
        alert_email = os.getenv("ALERT_EMAIL")
        slack_webhook = os.getenv("SLACK_WEBHOOK_URL")

        total_cost = budget_status["total_cost"]
        monthly_threshold = budget_status["monthly_threshold"]
        percentage_used = budget_status["percentage_used"]
        provider_costs = budget_status["provider_costs"]

        # Build alert message
        severity = "CRITICAL" if total_cost >= monthly_threshold else "WARNING"
        threshold_pct = int(threshold * 100)

        message = f"""
LLM COST BUDGET ALERT - {severity}

Monthly Budget: ${monthly_threshold:.2f}
Current Spend: ${total_cost:.2f} ({percentage_used:.1f}%)
Remaining: ${budget_status['remaining_budget']:.2f}

Threshold Exceeded: {threshold_pct}%

Provider Breakdown:
"""

        for provider, cost in sorted(provider_costs.items(), key=lambda x: x[1], reverse=True):
            pct = (cost / total_cost * 100) if total_cost > 0 else 0
            message += f"  {provider}: ${cost:.2f} ({pct:.1f}%)\n"

        message += f"\nAction Required: Review usage and consider:\n"
        message += f"- Reducing benchmark frequency\n"
        message += f"- Using lower-cost providers (e.g., gpt-4o-mini)\n"
        message += f"- Decreasing sample rates\n"
        message += f"- Pausing non-essential analysis\n"

        logger.warning(message)

        # TODO: Implement actual email/Slack sending
        # For now, just log the alert
        logger.warning("Alert would be sent to:")
        if alert_email:
            logger.warning(f"  Email: {alert_email}")
        if slack_webhook:
            logger.warning(f"  Slack: {slack_webhook}")

        # In production, implement:
        # if alert_email:
        #     await send_email_alert(alert_email, message)
        # if slack_webhook:
        #     await send_slack_alert(slack_webhook, message)

    async def check_and_alert(
        self,
        session: AsyncSession,
    ) -> dict:
        """
        Check budget status and send alerts if thresholds exceeded

        Args:
            session: Database session

        Returns:
            Budget status dict
        """
        logger.info("Checking provider costs...")

        budget_status = await self.check_budget_status(session)
        total_cost = budget_status["total_cost"]
        percentage_used = budget_status["percentage_used"]

        logger.info(f"Total monthly spend: ${total_cost:.2f} ({percentage_used:.1f}% of ${self.monthly_threshold:.2f})")

        # Check each threshold
        for threshold in sorted(self.alert_thresholds):
            threshold_cost = self.monthly_threshold * threshold

            if total_cost >= threshold_cost and not self.alert_sent[threshold]:
                logger.warning(f"Budget alert: Exceeded {int(threshold * 100)}% threshold")
                await self.send_alert(budget_status, threshold)
                self.alert_sent[threshold] = True
            elif total_cost < threshold_cost:
                # Reset flag if we drop below threshold (e.g., new month)
                self.alert_sent[threshold] = False

        return budget_status

    async def get_daily_costs(
        self,
        session: AsyncSession,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ProviderCost]:
        """
        Get daily cost records for a date range

        Args:
            session: Database session
            start_date: Start date
            end_date: End date

        Returns:
            List of ProviderCost records
        """
        query = (
            select(ProviderCost)
            .where(
                ProviderCost.date >= start_date.date(),
                ProviderCost.date <= end_date.date(),
            )
            .order_by(ProviderCost.date.desc(), ProviderCost.provider)
        )

        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_cost_summary(
        self,
        session: AsyncSession,
        days: int = 30,
    ) -> dict:
        """
        Get cost summary for last N days

        Args:
            session: Database session
            days: Number of days to look back

        Returns:
            Dict with summary statistics
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        costs = await self.get_daily_costs(session, start_date, end_date)

        # Aggregate by provider
        provider_totals = defaultdict(lambda: {
            "total_cost": 0.0,
            "total_tokens": 0,
            "total_comments": 0,
        })

        for cost in costs:
            provider_totals[cost.provider]["total_cost"] += cost.cost_usd
            provider_totals[cost.provider]["total_tokens"] += cost.tokens_consumed
            provider_totals[cost.provider]["total_comments"] += cost.comments_analyzed

        # Calculate averages
        for provider, totals in provider_totals.items():
            if totals["total_tokens"] > 0:
                totals["cost_per_1k_tokens"] = (totals["total_cost"] / totals["total_tokens"]) * 1000
            else:
                totals["cost_per_1k_tokens"] = 0.0

            if totals["total_comments"] > 0:
                totals["cost_per_comment"] = totals["total_cost"] / totals["total_comments"]
            else:
                totals["cost_per_comment"] = 0.0

        total_cost = sum(p["total_cost"] for p in provider_totals.values())

        return {
            "period_days": days,
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "total_cost": total_cost,
            "provider_totals": dict(provider_totals),
            "daily_records": len(costs),
        }


# Global singleton
_monitor: Optional[CostMonitor] = None


def get_cost_monitor(monthly_threshold: Optional[float] = None) -> CostMonitor:
    """Get or create cost monitor singleton"""
    global _monitor
    if _monitor is None or monthly_threshold is not None:
        threshold = monthly_threshold or float(os.getenv("COST_ALERT_THRESHOLD", "500.0"))
        alert_thresholds = [0.75, 0.90]  # 75% and 90%
        _monitor = CostMonitor(threshold, alert_thresholds)
    return _monitor
