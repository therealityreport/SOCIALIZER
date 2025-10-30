"""Backfill Reddit Mentions with LLM Analysis and Signal Extraction

Processes all existing Reddit threads and comments to apply:
1. LLM-driven sentiment/attitude/emotion/sarcasm analysis
2. Computed signal extraction (emoji, media, engagement)
3. Upvote-weighted aggregation

Includes idempotency, dry-run mode, progress tracking, and QA output.
"""
import asyncio
import csv
import logging
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.models.cast import CastMember
from app.models.comment import Comment
from app.models.mention import Mention, PrimarySentiment, SecondaryAttitude
from app.models.thread import Thread
from app.services.entity_linker import EntityLinker
from app.services.llm_service import get_llm_service
from app.services.signal_extractor import SignalExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BackfillStats:
    """Track backfill statistics"""

    def __init__(self):
        self.threads_processed = 0
        self.comments_processed = 0
        self.mentions_created = 0
        self.mentions_updated = 0
        self.llm_calls = 0
        self.llm_errors = 0
        self.cache_hits = 0
        self.start_time = datetime.now()
        self.thread_durations: dict[int, float] = {}

    def report(self) -> dict[str, Any]:
        """Generate final report"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return {
            "threads_processed": self.threads_processed,
            "comments_processed": self.comments_processed,
            "mentions_created": self.mentions_created,
            "mentions_updated": self.mentions_updated,
            "llm_calls": self.llm_calls,
            "llm_errors": self.llm_errors,
            "cache_hits": self.cache_hits,
            "total_duration_seconds": elapsed,
            "avg_duration_per_thread": elapsed / max(1, self.threads_processed),
            "thread_durations": self.thread_durations,
        }


class BackfillJob:
    """Backfill job for Reddit mentions analysis"""

    def __init__(
        self,
        dry_run: bool = False,
        thread_id: Optional[int] = None,
        batch_size: int = 100,
    ):
        """
        Initialize backfill job

        Args:
            dry_run: If True, don't write to database
            thread_id: Optional specific thread to process
            batch_size: Number of comments to process at once
        """
        self.dry_run = dry_run
        self.thread_id = thread_id
        self.batch_size = batch_size

        self.stats = BackfillStats()
        self.llm_service = get_llm_service()
        self.signal_extractor = SignalExtractor()
        self.entity_linker = EntityLinker()

        # QA data collection
        self.qa_data: dict[int, list[dict[str, Any]]] = defaultdict(list)

    async def run(self, session: AsyncSession) -> dict[str, Any]:
        """
        Run backfill job

        Args:
            session: Database session

        Returns:
            Stats report
        """
        logger.info("=" * 80)
        logger.info("Starting backfill job")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info(f"Thread ID filter: {self.thread_id}")
        logger.info("=" * 80)

        # Get threads to process
        threads = await self._get_threads(session)
        logger.info(f"Found {len(threads)} threads to process")

        # Process each thread
        for thread in threads:
            await self._process_thread(session, thread)

        # Generate QA CSV files
        self._generate_qa_files()

        # Generate final report
        report = self.stats.report()
        self._print_report(report)

        return report

    async def _get_threads(self, session: AsyncSession) -> list[Thread]:
        """Get threads to process"""
        query = select(Thread).where(Thread.status != "deleted")

        if self.thread_id:
            query = query.where(Thread.id == self.thread_id)

        result = await session.execute(query)
        return list(result.scalars().all())

    async def _process_thread(self, session: AsyncSession, thread: Thread) -> None:
        """Process a single thread"""
        thread_start = datetime.now()
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Processing thread {thread.id}: {thread.title}")
        logger.info(f"{'=' * 80}")

        # Get thread context for LLM
        context = await self._build_thread_context(session, thread)

        # Get all comments for this thread
        comments = await self._get_comments(session, thread.id)
        logger.info(f"Found {len(comments)} comments")

        # Process comments in batches
        for i in range(0, len(comments), self.batch_size):
            batch = comments[i:i + self.batch_size]
            await self._process_comment_batch(session, batch, context, thread)

        # Update stats
        thread_duration = (datetime.now() - thread_start).total_seconds()
        self.stats.thread_durations[thread.id] = thread_duration
        self.stats.threads_processed += 1

        logger.info(f"Thread {thread.id} completed in {thread_duration:.2f}s")

    async def _build_thread_context(
        self,
        session: AsyncSession,
        thread: Thread,
    ) -> dict[str, Any]:
        """Build context for LLM analysis"""
        # Get cast roster
        result = await session.execute(select(CastMember))
        cast_members = result.scalars().all()
        cast_roster = [cm.canonical_name for cm in cast_members]

        return {
            "synopsis": thread.synopsis or "",
            "title": thread.title,
            "subreddit": thread.subreddit,
            "cast_roster": cast_roster,
            "cast_aliases": {cm.canonical_name: cm.aliases for cm in cast_members},
        }

    async def _get_comments(
        self,
        session: AsyncSession,
        thread_id: int,
    ) -> list[Comment]:
        """Get all comments for a thread"""
        query = (
            select(Comment)
            .where(Comment.thread_id == thread_id)
            .order_by(Comment.created_utc)
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def _process_comment_batch(
        self,
        session: AsyncSession,
        comments: list[Comment],
        context: dict[str, Any],
        thread: Thread,
    ) -> None:
        """Process a batch of comments"""
        for comment in comments:
            await self._process_comment(session, comment, context, thread)
            self.stats.comments_processed += 1

            if self.stats.comments_processed % 100 == 0:
                logger.info(f"Processed {self.stats.comments_processed} comments...")

    async def _process_comment(
        self,
        session: AsyncSession,
        comment: Comment,
        context: dict[str, Any],
        thread: Thread,
    ) -> None:
        """Process a single comment"""
        # Step 1: Entity linking to find cast mentions
        cast_ids = self.entity_linker.extract_cast_mentions(
            comment.body,
            context["cast_aliases"]
        )

        # If no cast mentions found, still analyze if comment is substantial
        if not cast_ids and len(comment.body) > 20:
            cast_ids = [None]  # Create episode-level mention

        # Step 2: Extract signals
        comment_data = {
            "score": comment.score,
            "reply_count": comment.reply_count,
            "parent_id": comment.parent_id,
            "created_utc": comment.created_utc,
            "all_awardings": [],  # TODO: Extract from Reddit data if available
        }
        signals = self.signal_extractor.extract(comment.body, comment_data)

        # Step 3: LLM analysis
        try:
            llm_result = await self.llm_service.analyze(comment.body, context)
            self.stats.llm_calls += 1
        except Exception as e:
            logger.error(f"LLM analysis failed for comment {comment.id}: {e}")
            self.stats.llm_errors += 1
            return

        # Step 4: Create or update mentions
        for cast_id in cast_ids:
            await self._upsert_mention(
                session,
                comment,
                cast_id,
                llm_result,
                signals,
                thread,
            )

    async def _upsert_mention(
        self,
        session: AsyncSession,
        comment: Comment,
        cast_id: Optional[int],
        llm_result: Any,
        signals: Any,
        thread: Thread,
    ) -> None:
        """Create or update a mention with idempotency"""
        # Build mention data
        mention_data = {
            "comment_id": comment.id,
            "comment_created_at": comment.created_at,
            "cast_member_id": cast_id,
            "sentiment_label": llm_result.primary_sentiment.lower(),
            "sentiment_score": self._sentiment_to_score(llm_result.primary_sentiment),
            "confidence": llm_result.confidence,
            "method": llm_result.method,
            # LLM fields
            "primary_sentiment": llm_result.primary_sentiment,
            "secondary_attitude": llm_result.secondary_attitude,
            "emotions": llm_result.emotions if llm_result.emotions else None,
            "sarcasm_score": llm_result.sarcasm_score,
            "sarcasm_label": llm_result.sarcasm_label,
            "sarcasm_evidence": llm_result.sarcasm_evidence,
            # Signal fields
            "signals": signals.to_dict(),
            "engagement": signals.engagement_dict(),
            # Weight calculation
            "weight": self._calculate_weight(signals, llm_result),
            "is_sarcastic": llm_result.sarcasm_score >= 0.5,
            "is_toxic": False,  # TODO: Add toxicity from LLM
        }

        if not self.dry_run:
            # Upsert with conflict resolution
            stmt = insert(Mention).values(**mention_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["comment_id", "comment_created_at", "cast_member_id"],
                set_=mention_data,
            )
            await session.execute(stmt)
            await session.commit()
            self.stats.mentions_created += 1

        # Collect QA data (top weighted mentions)
        if signals.upvotes_new > 10:  # Only track high-engagement comments
            self.qa_data[thread.id].append({
                "comment_id": comment.id,
                "cast_id": cast_id,
                "text": comment.body[:200],
                "primary_sentiment": llm_result.primary_sentiment,
                "secondary_attitude": llm_result.secondary_attitude,
                "sarcasm_score": llm_result.sarcasm_score,
                "upvotes": signals.upvotes_new,
                "weight": mention_data["weight"],
                "confidence": llm_result.confidence,
            })

    def _sentiment_to_score(self, sentiment: str) -> float:
        """Convert sentiment label to numeric score"""
        mapping = {
            "POSITIVE": 1.0,
            "NEUTRAL": 0.0,
            "NEGATIVE": -1.0,
        }
        return mapping.get(sentiment, 0.0)

    def _calculate_weight(self, signals: Any, llm_result: Any) -> float:
        """Calculate upvote-weighted score"""
        weight_cap = int(os.getenv("WEIGHT_CAP", "200"))
        upvotes = min(signals.upvotes_new, weight_cap)
        weight = max(1, upvotes) * llm_result.confidence
        return weight

    def _generate_qa_files(self) -> None:
        """Generate QA CSV files for top weighted mentions per thread"""
        qa_dir = Path("qa_reports")
        qa_dir.mkdir(exist_ok=True)

        for thread_id, mentions in self.qa_data.items():
            # Sort by weight descending
            mentions_sorted = sorted(mentions, key=lambda x: x["weight"], reverse=True)
            top_50 = mentions_sorted[:50]

            # Write CSV
            csv_path = qa_dir / f"qa_top_weighted_mentions_thread_{thread_id}.csv"
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                if top_50:
                    writer = csv.DictWriter(f, fieldnames=top_50[0].keys())
                    writer.writeheader()
                    writer.writerows(top_50)

            logger.info(f"Generated QA report: {csv_path}")

    def _print_report(self, report: dict[str, Any]) -> None:
        """Print final report"""
        print("\n" + "=" * 80)
        print("BACKFILL JOB COMPLETE")
        print("=" * 80)
        print(f"Threads processed:    {report['threads_processed']}")
        print(f"Comments processed:   {report['comments_processed']}")
        print(f"Mentions created:     {report['mentions_created']}")
        print(f"Mentions updated:     {report['mentions_updated']}")
        print(f"LLM calls:            {report['llm_calls']}")
        print(f"LLM errors:           {report['llm_errors']}")
        print(f"Cache hits:           {report['cache_hits']}")
        print(f"Total duration:       {report['total_duration_seconds']:.2f}s")
        print(f"Avg per thread:       {report['avg_duration_per_thread']:.2f}s")
        print("=" * 80)


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Backfill Reddit mentions with LLM analysis")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no database writes)")
    parser.add_argument("--thread-id", type=int, help="Process specific thread ID only")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")
    args = parser.parse_args()

    job = BackfillJob(
        dry_run=args.dry_run,
        thread_id=args.thread_id,
        batch_size=args.batch_size,
    )

    async for session in get_async_session():
        try:
            await job.run(session)
        finally:
            await session.close()


if __name__ == "__main__":
    asyncio.run(main())
