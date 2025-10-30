"""Episode Discussion Analysis Job

Analyzes episode discussions by:
1. Analyzing transcript for summary, beats, and cast sentiment baseline
2. Ingesting comments from provided social media links
3. Running LLM sentiment analysis on all comments
"""
import asyncio
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.models.episode_discussion import DiscussionStatus, EpisodeDiscussion
from app.models.cast import CastMember
from app.services.transcript_analyzer import get_transcript_analyzer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EpisodeAnalysisJob:
    """Job to analyze an episode discussion"""

    def __init__(self, discussion_id: int):
        """
        Initialize job

        Args:
            discussion_id: EpisodeDiscussion ID to analyze
        """
        self.discussion_id = discussion_id
        self.transcript_analyzer = get_transcript_analyzer()

    async def run(self, session: AsyncSession) -> dict[str, Any]:
        """
        Run analysis job

        Args:
            session: Database session

        Returns:
            Job stats
        """
        logger.info("=" * 80)
        logger.info(f"Starting episode discussion analysis for ID {self.discussion_id}")
        logger.info("=" * 80)

        # Get discussion
        discussion = await session.get(EpisodeDiscussion, self.discussion_id)
        if not discussion:
            raise ValueError(f"Episode discussion {self.discussion_id} not found")

        # Update status to RUNNING
        discussion.status = DiscussionStatus.RUNNING
        discussion.analysis_started_at = datetime.utcnow()
        discussion.error_message = None
        await session.commit()

        try:
            # Step 1: Load and analyze transcript
            await self._analyze_transcript(session, discussion)

            # Step 2: Ingest comments from links
            await self._ingest_comments(session, discussion)

            # Step 3: Mark as complete
            discussion.status = DiscussionStatus.COMPLETE
            discussion.analysis_completed_at = datetime.utcnow()
            await session.commit()

            logger.info("=" * 80)
            logger.info("EPISODE ANALYSIS COMPLETE")
            logger.info("=" * 80)
            logger.info(f"Discussion ID: {discussion.id}")
            logger.info(f"Show: {discussion.show} S{discussion.season}E{discussion.episode}")
            logger.info(f"Comments ingested: {discussion.total_comments_ingested}")
            logger.info(f"Mentions created: {discussion.total_mentions_created}")
            logger.info("=" * 80)

            return {
                "discussion_id": discussion.id,
                "status": discussion.status.value,
                "comments_ingested": discussion.total_comments_ingested,
                "mentions_created": discussion.total_mentions_created,
            }

        except Exception as e:
            logger.error(f"Episode analysis failed: {e}", exc_info=True)
            discussion.status = DiscussionStatus.FAILED
            discussion.error_message = str(e)
            discussion.analysis_completed_at = datetime.utcnow()
            await session.commit()
            raise

    async def _analyze_transcript(
        self,
        session: AsyncSession,
        discussion: EpisodeDiscussion,
    ) -> None:
        """
        Analyze transcript and update discussion

        Args:
            session: Database session
            discussion: EpisodeDiscussion to update
        """
        logger.info(f"Analyzing transcript: {discussion.transcript_ref}")

        # Load transcript text if not already cached
        if not discussion.transcript_text:
            transcript_path = Path(discussion.transcript_ref)
            if not transcript_path.exists():
                raise FileNotFoundError(f"Transcript not found: {discussion.transcript_ref}")

            with open(transcript_path, 'r', encoding='utf-8') as f:
                discussion.transcript_text = f.read()

        # Get cast members for this show
        query = select(CastMember).where(
            CastMember.show == discussion.show,
            CastMember.is_active == True
        )
        result = await session.execute(query)
        cast_members = list(result.scalars().all())
        cast_names = [cm.full_name for cm in cast_members if cm.slug in discussion.cast_ids]

        if not cast_names:
            logger.warning(f"No cast members found for show '{discussion.show}' with IDs {discussion.cast_ids}")
            cast_names = discussion.cast_ids  # Use slugs as fallback

        # Analyze transcript
        logger.info(f"Running LLM analysis on transcript ({len(discussion.transcript_text)} chars)")
        analysis = await self.transcript_analyzer.analyze_transcript(
            transcript=discussion.transcript_text,
            show=discussion.show,
            season=discussion.season,
            episode=discussion.episode,
            cast_members=cast_names,
        )

        # Update discussion with results
        discussion.summary = analysis.get("summary")
        discussion.beats = analysis.get("beats", [])
        discussion.cast_sentiment_baseline = analysis.get("cast_sentiment_baseline", {})

        await session.commit()
        logger.info("Transcript analysis complete")

    async def _ingest_comments(
        self,
        session: AsyncSession,
        discussion: EpisodeDiscussion,
    ) -> None:
        """
        Ingest and analyze comments from discussion links

        Args:
            session: Database session
            discussion: EpisodeDiscussion to process
        """
        if not discussion.links:
            logger.info("No links provided, skipping comment ingestion")
            return

        logger.info(f"Ingesting comments from {len(discussion.links)} links")

        # TODO: Implement comment ingestion based on platform
        # For Reddit: Use existing Reddit ingestion logic
        # For Instagram/TikTok/X/YouTube: Implement platform-specific scrapers

        for link in discussion.links:
            logger.info(f"Processing link: {link}")

            # Placeholder: In production, this would:
            # 1. Detect platform from URL
            # 2. Use appropriate API/scraper
            # 3. Store comments with episode_discussion_id reference
            # 4. Run LLM analysis on each comment
            # 5. Create Mention records

            # For now, just log
            logger.warning(f"Comment ingestion not yet implemented for: {link}")

        discussion.total_comments_ingested = 0  # Update once implemented
        discussion.total_mentions_created = 0
        discussion.last_ingested_at = datetime.utcnow()

        await session.commit()
        logger.info("Comment ingestion complete (placeholder)")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Analyze episode discussion with transcript and comments"
    )
    parser.add_argument(
        "discussion_id",
        type=int,
        help="Episode discussion ID to analyze"
    )
    args = parser.parse_args()

    job = EpisodeAnalysisJob(args.discussion_id)

    async for session in get_async_session():
        try:
            await job.run(session)
        except Exception as e:
            logger.error(f"Job failed: {e}", exc_info=True)
            raise
        finally:
            await session.close()


if __name__ == "__main__":
    asyncio.run(main())
