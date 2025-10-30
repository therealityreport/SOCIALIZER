"""Episode Discussion API Routes

Endpoints for creating and managing episode-level discussions with transcript analysis.
"""
from __future__ import annotations

import logging
from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.episode_discussion import DiscussionStatus, EpisodeDiscussion
from app.models.mention import Mention
from app.schemas.episode_discussion import (
    EpisodeDiscussionAnalyzeRequest,
    EpisodeDiscussionAnalyzeResponse,
    EpisodeDiscussionCreate,
    EpisodeDiscussionRead,
    EpisodeDiscussionUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/episode-discussions", tags=["episode-discussions"])


@router.post("", response_model=EpisodeDiscussionRead, status_code=status.HTTP_201_CREATED)
async def create_episode_discussion(
    discussion_in: EpisodeDiscussionCreate,
    db: AsyncSession = Depends(get_db),
) -> EpisodeDiscussion:
    """
    Create a new episode discussion

    Args:
        discussion_in: Episode discussion data
        db: Database session

    Returns:
        Created episode discussion
    """
    # Create discussion
    discussion = EpisodeDiscussion(
        show=discussion_in.show,
        season=discussion_in.season,
        episode=discussion_in.episode,
        date_utc=discussion_in.date_utc,
        platform=discussion_in.platform,
        links=discussion_in.links,
        transcript_ref=discussion_in.transcript_ref,
        transcript_text=discussion_in.transcript_text,
        window=discussion_in.window,
        cast_ids=discussion_in.cast_ids,
        status=DiscussionStatus.DRAFT,
    )

    db.add(discussion)
    try:
        await db.commit()
        await db.refresh(discussion)
    except IntegrityError as exc:
        await db.rollback()
        logger.error(f"Failed to create episode discussion: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create episode discussion. Check for duplicate entries.",
        ) from exc

    logger.info(f"Created episode discussion: {discussion.id} for {discussion.show} S{discussion.season}E{discussion.episode}")
    return discussion


@router.get("", response_model=list[EpisodeDiscussionRead])
async def list_episode_discussions(
    db: AsyncSession = Depends(get_db),
    show: str | None = Query(default=None, description="Filter by show"),
    status_filter: DiscussionStatus | None = Query(default=None, alias="status", description="Filter by status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> Sequence[EpisodeDiscussion]:
    """
    List episode discussions

    Args:
        db: Database session
        show: Optional show filter
        status_filter: Optional status filter
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of episode discussions
    """
    query = select(EpisodeDiscussion).order_by(EpisodeDiscussion.date_utc.desc())

    if show:
        query = query.where(EpisodeDiscussion.show == show)
    if status_filter:
        query = query.where(EpisodeDiscussion.status == status_filter)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{discussion_id}", response_model=EpisodeDiscussionRead)
async def get_episode_discussion(
    discussion_id: int,
    db: AsyncSession = Depends(get_db),
) -> EpisodeDiscussion:
    """
    Get a single episode discussion by ID

    Args:
        discussion_id: Episode discussion ID
        db: Database session

    Returns:
        Episode discussion
    """
    discussion = await db.get(EpisodeDiscussion, discussion_id)
    if not discussion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Episode discussion {discussion_id} not found",
        )
    return discussion


@router.patch("/{discussion_id}", response_model=EpisodeDiscussionRead)
async def update_episode_discussion(
    discussion_id: int,
    discussion_update: EpisodeDiscussionUpdate,
    db: AsyncSession = Depends(get_db),
) -> EpisodeDiscussion:
    """
    Update an episode discussion

    Args:
        discussion_id: Episode discussion ID
        discussion_update: Fields to update
        db: Database session

    Returns:
        Updated episode discussion
    """
    discussion = await db.get(EpisodeDiscussion, discussion_id)
    if not discussion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Episode discussion {discussion_id} not found",
        )

    # Update fields
    update_data = discussion_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(discussion, field, value)

    try:
        await db.commit()
        await db.refresh(discussion)
    except IntegrityError as exc:
        await db.rollback()
        logger.error(f"Failed to update episode discussion {discussion_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update episode discussion",
        ) from exc

    logger.info(f"Updated episode discussion: {discussion_id}")
    return discussion


@router.delete("/{discussion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_episode_discussion(
    discussion_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete an episode discussion

    Args:
        discussion_id: Episode discussion ID
        db: Database session
    """
    discussion = await db.get(EpisodeDiscussion, discussion_id)
    if not discussion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Episode discussion {discussion_id} not found",
        )

    await db.delete(discussion)
    await db.commit()
    logger.info(f"Deleted episode discussion: {discussion_id}")


@router.post("/{discussion_id}/analyze", response_model=EpisodeDiscussionAnalyzeResponse)
async def analyze_episode_discussion(
    discussion_id: int,
    request: EpisodeDiscussionAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
) -> EpisodeDiscussionAnalyzeResponse:
    """
    Trigger LLM analysis for an episode discussion

    This endpoint queues the following tasks:
    1. Analyze transcript for summary, beats, and cast sentiment baseline
    2. Ingest comments from provided links
    3. Perform LLM sentiment analysis on all comments

    Args:
        discussion_id: Episode discussion ID
        request: Analysis request options
        db: Database session

    Returns:
        Analysis response with new status
    """
    discussion = await db.get(EpisodeDiscussion, discussion_id)
    if not discussion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Episode discussion {discussion_id} not found",
        )

    # Check if already complete
    if discussion.status == DiscussionStatus.COMPLETE and not request.force:
        return EpisodeDiscussionAnalyzeResponse(
            discussion_id=discussion_id,
            status=discussion.status,
            message="Analysis already complete. Use force=true to re-analyze.",
        )

    # Check if already queued or running
    if discussion.status in (DiscussionStatus.QUEUED, DiscussionStatus.RUNNING) and not request.force:
        return EpisodeDiscussionAnalyzeResponse(
            discussion_id=discussion_id,
            status=discussion.status,
            message=f"Analysis already {discussion.status.value}. Use force=true to restart.",
        )

    # Update status to QUEUED
    discussion.status = DiscussionStatus.QUEUED
    discussion.error_message = None

    try:
        await db.commit()
        await db.refresh(discussion)
    except Exception as exc:
        await db.rollback()
        logger.error(f"Failed to update status for discussion {discussion_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue analysis",
        ) from exc

    # TODO: Trigger background job to analyze transcript and ingest comments
    # from app.tasks.episode_analysis import analyze_episode_discussion_task
    # analyze_episode_discussion_task.delay(discussion_id)

    logger.info(f"Queued analysis for episode discussion: {discussion_id}")

    return EpisodeDiscussionAnalyzeResponse(
        discussion_id=discussion_id,
        status=discussion.status,
        message="Analysis queued successfully. Check status for progress.",
    )


@router.get("/{discussion_id}/mentions")
async def get_episode_discussion_mentions(
    discussion_id: int,
    db: AsyncSession = Depends(get_db),
    cast_id: int | None = Query(default=None, description="Filter by cast member ID"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    """
    Get mentions for an episode discussion

    Args:
        discussion_id: Episode discussion ID
        db: Database session
        cast_id: Optional cast member ID filter
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of mentions with sentiment analysis
    """
    discussion = await db.get(EpisodeDiscussion, discussion_id)
    if not discussion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Episode discussion {discussion_id} not found",
        )

    # TODO: Add episode_discussion_id field to Mention model
    # For now, return empty list with a message
    # In future implementation:
    # query = select(Mention).where(Mention.episode_discussion_id == discussion_id)
    # if cast_id:
    #     query = query.where(Mention.cast_member_id == cast_id)
    # query = query.offset(skip).limit(limit)
    # result = await db.execute(query)
    # return list(result.scalars().all())

    return {
        "message": "Mentions endpoint not yet fully implemented. Requires episode_discussion_id field on Mention model.",
        "discussion_id": discussion_id,
        "cast_id": cast_id,
        "mentions": [],
    }
