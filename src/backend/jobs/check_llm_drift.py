"""LLM Quality Drift Monitoring Job

Weekly job to detect quality drift in active LLM provider.
Samples recent comments and re-analyzes with secondary provider.
Generates drift reports and alerts on low agreement.
"""
import asyncio
import argparse
import csv
import logging
import os
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.models.comment import Comment
from app.models.mention import Mention
from app.models.provider_cost import DriftCheck
from app.models.thread import Thread
from app.services.llm_service_manager import get_llm_manager
from app.services.provider_selection import get_active_provider, get_fallback_provider

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DriftMonitor:
    """Monitors LLM provider quality drift"""

    def __init__(
        self,
        sample_rate: float = 0.05,
        agreement_threshold: float = 0.8,
    ):
        """
        Initialize drift monitor

        Args:
            sample_rate: Fraction of comments to sample (default 0.05 = 5%)
            agreement_threshold: Alert threshold (default 0.8)
        """
        self.sample_rate = sample_rate
        self.agreement_threshold = agreement_threshold
        self.primary_provider = get_active_provider()
        self.secondary_provider = get_fallback_provider()

    async def get_recent_comments(
        self,
        session: AsyncSession,
        days: int = 7,
    ) -> list[Comment]:
        """
        Get recent comments analyzed by primary provider

        Args:
            session: Database session
            days: Number of days to look back

        Returns:
            List of Comment objects
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        query = (
            select(Comment)
            .join(Mention, Mention.comment_id == Comment.id)
            .where(Comment.created_utc >= cutoff)
            .where(Mention.provider_preferred == self.primary_provider)
            .distinct()
        )

        result = await session.execute(query)
        return list(result.scalars().all())

    async def sample_comments(
        self,
        comments: list[Comment],
    ) -> list[Comment]:
        """
        Sample comments for drift check

        Args:
            comments: All available comments

        Returns:
            Sampled subset
        """
        sample_size = max(int(len(comments) * self.sample_rate), 10)
        sample_size = min(sample_size, len(comments))

        sampled = random.sample(comments, sample_size)
        logger.info(f"Sampled {len(sampled)} comments from {len(comments)} total")

        return sampled

    async def reanalyze_with_secondary(
        self,
        session: AsyncSession,
        comments: list[Comment],
    ) -> dict[int, dict[str, Any]]:
        """
        Re-analyze comments with secondary provider

        Args:
            session: Database session
            comments: Comments to re-analyze

        Returns:
            Dict mapping comment_id to analysis results
        """
        llm_manager = get_llm_manager([self.secondary_provider])
        results = {}

        for comment in comments:
            try:
                # Get episode context
                thread = await session.get(Thread, comment.thread_id)
                context = {
                    "synopsis": thread.synopsis if thread else "",
                    "title": thread.title if thread else "",
                    "cast_roster": [],  # Could fetch cast list here
                }

                # Analyze with secondary provider
                provider_results = await llm_manager.analyze_with_all(
                    comment.body,
                    context,
                )

                if self.secondary_provider in provider_results:
                    result = provider_results[self.secondary_provider]
                    results[comment.id] = {
                        "primary_sentiment": result.primary_sentiment,
                        "sarcasm_score": result.sarcasm_score,
                        "confidence": result.confidence,
                    }

            except Exception as e:
                logger.error(f"Failed to re-analyze comment {comment.id}: {e}")
                continue

        logger.info(f"Re-analyzed {len(results)} comments with {self.secondary_provider}")
        return results

    async def get_primary_results(
        self,
        session: AsyncSession,
        comment_ids: list[int],
    ) -> dict[int, dict[str, Any]]:
        """
        Get original analysis results from primary provider

        Args:
            session: Database session
            comment_ids: Comment IDs to fetch

        Returns:
            Dict mapping comment_id to original results
        """
        query = (
            select(Mention)
            .where(Mention.comment_id.in_(comment_ids))
            .where(Mention.provider_preferred == self.primary_provider)
        )

        result = await session.execute(query)
        mentions = result.scalars().all()

        results = {}
        for mention in mentions:
            if mention.comment_id not in results:  # Take first mention per comment
                results[mention.comment_id] = {
                    "primary_sentiment": mention.primary_sentiment.value if mention.primary_sentiment else "NEUTRAL",
                    "sarcasm_score": mention.sarcasm_score or 0.0,
                    "confidence": mention.confidence or 0.0,
                }

        return results

    def calculate_agreement(
        self,
        primary_results: dict[int, dict[str, Any]],
        secondary_results: dict[int, dict[str, Any]],
    ) -> dict[str, float]:
        """
        Calculate agreement scores between providers

        Args:
            primary_results: Primary provider results
            secondary_results: Secondary provider results

        Returns:
            Dict with agreement metrics
        """
        # Find common comment IDs
        common_ids = set(primary_results.keys()) & set(secondary_results.keys())

        if not common_ids:
            return {
                "agreement_score": 0.0,
                "sentiment_agreement": 0.0,
                "sarcasm_agreement": 0.0,
                "samples_compared": 0,
            }

        # Sentiment agreement
        sentiment_matches = 0
        for comment_id in common_ids:
            if primary_results[comment_id]["primary_sentiment"] == secondary_results[comment_id]["primary_sentiment"]:
                sentiment_matches += 1

        sentiment_agreement = sentiment_matches / len(common_ids)

        # Sarcasm agreement (lower variance = higher agreement)
        sarcasm_scores_primary = [primary_results[cid]["sarcasm_score"] for cid in common_ids]
        sarcasm_scores_secondary = [secondary_results[cid]["sarcasm_score"] for cid in common_ids]

        mean_sarcasm = sum(sarcasm_scores_primary + sarcasm_scores_secondary) / (2 * len(common_ids))
        variance = sum(
            (primary_results[cid]["sarcasm_score"] - mean_sarcasm) ** 2 +
            (secondary_results[cid]["sarcasm_score"] - mean_sarcasm) ** 2
            for cid in common_ids
        ) / (2 * len(common_ids))

        sarcasm_agreement = 1.0 - min(variance, 1.0)

        # Overall agreement (weighted)
        agreement_score = 0.7 * sentiment_agreement + 0.3 * sarcasm_agreement

        return {
            "agreement_score": agreement_score,
            "sentiment_agreement": sentiment_agreement,
            "sarcasm_agreement": sarcasm_agreement,
            "samples_compared": len(common_ids),
        }

    async def log_drift_check(
        self,
        session: AsyncSession,
        metrics: dict[str, float],
    ) -> None:
        """
        Log drift check to database

        Args:
            session: Database session
            metrics: Agreement metrics
        """
        status = "ok"
        if metrics["agreement_score"] < 0.7:
            status = "critical"
        elif metrics["agreement_score"] < self.agreement_threshold:
            status = "warning"

        check = DriftCheck(
            primary_provider=self.primary_provider,
            secondary_provider=self.secondary_provider,
            samples_checked=metrics["samples_compared"],
            agreement_score=metrics["agreement_score"],
            sentiment_agreement=metrics["sentiment_agreement"],
            sarcasm_agreement=metrics["sarcasm_agreement"],
            status=status,
            alert_sent=False,  # Will be updated if alert sent
        )

        session.add(check)
        await session.commit()

        logger.info(f"Logged drift check: status={status} agreement={metrics['agreement_score']:.3f}")

    def generate_drift_summary(
        self,
        metrics: dict[str, float],
        output_path: Path = Path("qa_reports/drift_summary.csv"),
    ) -> None:
        """
        Generate drift summary CSV

        Args:
            metrics: Agreement metrics
            output_path: Path to output CSV
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if file exists
        file_exists = output_path.exists()

        with open(output_path, 'a', newline='') as f:
            fieldnames = [
                "check_date",
                "primary_provider",
                "secondary_provider",
                "samples_compared",
                "agreement_score",
                "sentiment_agreement",
                "sarcasm_agreement",
                "status",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            status = "ok"
            if metrics["agreement_score"] < 0.7:
                status = "critical"
            elif metrics["agreement_score"] < self.agreement_threshold:
                status = "warning"

            writer.writerow({
                "check_date": datetime.utcnow().isoformat(),
                "primary_provider": self.primary_provider,
                "secondary_provider": self.secondary_provider,
                "samples_compared": metrics["samples_compared"],
                "agreement_score": f"{metrics['agreement_score']:.4f}",
                "sentiment_agreement": f"{metrics['sentiment_agreement']:.4f}",
                "sarcasm_agreement": f"{metrics['sarcasm_agreement']:.4f}",
                "status": status,
            })

        logger.info(f"Generated drift summary: {output_path}")

    async def send_alert(self, metrics: dict[str, float]) -> None:
        """
        Send drift alert if agreement below threshold

        Args:
            metrics: Agreement metrics
        """
        if metrics["agreement_score"] >= self.agreement_threshold:
            logger.info("Agreement within threshold, no alert needed")
            return

        alert_email = os.getenv("ALERT_EMAIL")
        slack_webhook = os.getenv("SLACK_WEBHOOK_URL")

        message = f"""
LLM QUALITY DRIFT ALERT

Primary Provider: {self.primary_provider}
Secondary Provider: {self.secondary_provider}
Agreement Score: {metrics['agreement_score']:.3f} (threshold: {self.agreement_threshold})
Sentiment Agreement: {metrics['sentiment_agreement']:.3f}
Sarcasm Agreement: {metrics['sarcasm_agreement']:.3f}
Samples Compared: {metrics['samples_compared']}

Status: {"CRITICAL" if metrics["agreement_score"] < 0.7 else "WARNING"}

Action Required: Review recent analyses and consider re-benchmarking providers.
"""

        logger.warning(message)

        # TODO: Implement actual email/Slack sending
        # For now, just log the alert
        logger.warning("Alert would be sent to:")
        if alert_email:
            logger.warning(f"  Email: {alert_email}")
        if slack_webhook:
            logger.warning(f"  Slack: {slack_webhook}")

    async def run(self, session: AsyncSession) -> dict[str, Any]:
        """
        Run drift check workflow

        Args:
            session: Database session

        Returns:
            Drift metrics
        """
        logger.info("=" * 80)
        logger.info("LLM QUALITY DRIFT CHECK")
        logger.info("=" * 80)
        logger.info(f"Primary Provider:   {self.primary_provider}")
        logger.info(f"Secondary Provider: {self.secondary_provider}")
        logger.info(f"Sample Rate:        {self.sample_rate * 100:.1f}%")
        logger.info(f"Alert Threshold:    {self.agreement_threshold}")
        logger.info("=" * 80)

        # Get recent comments
        comments = await self.get_recent_comments(session)
        logger.info(f"Found {len(comments)} recent comments")

        if not comments:
            logger.warning("No comments to check, skipping drift analysis")
            return {}

        # Sample comments
        sampled = await self.sample_comments(comments)

        # Get primary provider results
        comment_ids = [c.id for c in sampled]
        primary_results = await self.get_primary_results(session, comment_ids)

        # Re-analyze with secondary provider
        secondary_results = await self.reanalyze_with_secondary(session, sampled)

        # Calculate agreement
        metrics = self.calculate_agreement(primary_results, secondary_results)

        logger.info("\n" + "=" * 80)
        logger.info("DRIFT CHECK RESULTS")
        logger.info("=" * 80)
        logger.info(f"Samples Compared:     {metrics['samples_compared']}")
        logger.info(f"Agreement Score:      {metrics['agreement_score']:.4f}")
        logger.info(f"Sentiment Agreement:  {metrics['sentiment_agreement']:.4f}")
        logger.info(f"Sarcasm Agreement:    {metrics['sarcasm_agreement']:.4f}")

        if metrics['agreement_score'] < self.agreement_threshold:
            logger.warning(f"⚠️  DRIFT DETECTED: Agreement below threshold ({self.agreement_threshold})")
        else:
            logger.info(f"✓  No drift detected (agreement >= {self.agreement_threshold})")

        logger.info("=" * 80)

        # Log to database
        await self.log_drift_check(session, metrics)

        # Generate summary CSV
        self.generate_drift_summary(metrics)

        # Send alert if needed
        await self.send_alert(metrics)

        return metrics


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="LLM quality drift monitoring"
    )
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=float(os.getenv("DRIFT_SAMPLE_RATE", "0.05")),
        help="Fraction of comments to sample (default 0.05 = 5%%)",
    )
    parser.add_argument(
        "--agreement-threshold",
        type=float,
        default=float(os.getenv("DRIFT_AGREEMENT_THRESHOLD", "0.8")),
        help="Agreement threshold for alerts (default 0.8)",
    )
    args = parser.parse_args()

    monitor = DriftMonitor(
        sample_rate=args.sample_rate,
        agreement_threshold=args.agreement_threshold,
    )

    async for session in get_async_session():
        try:
            await monitor.run(session)
        except Exception as e:
            logger.error(f"Drift check failed: {e}", exc_info=True)
            raise
        finally:
            await session.close()


if __name__ == "__main__":
    asyncio.run(main())
