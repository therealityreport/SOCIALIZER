from __future__ import annotations

import logging
from typing import Iterable

import re
from celery import shared_task

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import CastMember, Comment, Mention
from app.services.cast_roster import resolve_aliases
from app.services.entity_linking import CastCatalogEntry, EntityLinker, MentionCandidate
from app.tasks.analytics import compute_aggregates
from app.services.sentiment_pipeline import NormalizedSentiment, SentimentAnalysisResult, get_sentiment_pipeline

logger = logging.getLogger(__name__)


def _chunked(sequence: list[Comment], size: int) -> Iterable[list[Comment]]:
    for index in range(0, len(sequence), size):
        yield sequence[index : index + size]


def _clamp_score(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _normalized_model_version(settings) -> str:
    label = settings.primary_model or settings.model_version or ""
    return str(label)[:32]


def _attenuate_sentiment_score(score: float | None, comment: Comment, settings) -> float | None:
    if score is None:
        return None

    adjusted = float(score)
    sarcasm_conf = float(comment.sarcasm_confidence or 0.0)
    if getattr(comment, "is_sarcastic", False):
        adjusted *= 0.6
    elif sarcasm_conf >= getattr(settings, "sarcasm_threshold", 0.0) and sarcasm_conf > 0:
        adjusted *= max(0.0, 1.0 - 0.4 * min(sarcasm_conf, 1.0))

    toxicity_conf = float(comment.toxicity_confidence or 0.0)
    if getattr(comment, "is_toxic", False):
        adjusted *= 0.75
    elif toxicity_conf >= getattr(settings, "toxicity_threshold", 0.0) and toxicity_conf > 0:
        adjusted *= max(0.0, 1.0 - 0.25 * min(toxicity_conf, 1.0))

    return _clamp_score(adjusted)


@shared_task(bind=True, name="app.tasks.ml.classify_comments", queue="ml")
def classify_comments(self, comment_ids: list[int]) -> dict[str, int]:
    if not comment_ids:
        return {"processed": 0, "classified": 0}

    settings = get_settings()
    pipeline = get_sentiment_pipeline(settings)

    session = SessionLocal()
    try:
        stmt = select(Comment).where(Comment.id.in_(comment_ids))
        comments = session.execute(stmt).scalars().all()
        if not comments:
            return {"processed": 0, "classified": 0}

        classified = 0
        batch_size = max(1, settings.ml_batch_size)
        updated_comment_ids: list[int] = []

        model_version = _normalized_model_version(settings)

        for batch in _chunked(comments, batch_size):
            for comment in batch:
                analysis = pipeline.analyze_comment(comment.body)
                _apply_comment_sentiment(comment, analysis)
                comment.ml_model_version = model_version
                logger.info(
                    "Comment %s sentiment sourced from %s: %s (%.3f)",
                    comment.id,
                    analysis.final.source_model,
                    analysis.final.sentiment_label,
                    analysis.final.sentiment_score,
                )
                classified += 1
                updated_comment_ids.append(comment.id)

        session.commit()
        if updated_comment_ids:
            link_entities.apply_async(args=[updated_comment_ids], queue="ml")
        return {"processed": len(comments), "classified": classified}
    except Exception as exc:
        session.rollback()
        logger.exception("Failed to classify comments: %s", exc)
        raise
    finally:
        session.close()


def _apply_comment_sentiment(comment: Comment, analysis: SentimentAnalysisResult) -> None:
    final = analysis.final
    comment.sentiment_label = final.sentiment_label
    comment.sentiment_score = float(final.sentiment_score)
    comment.sentiment_breakdown = {
        "models": [
            {
                "name": entry.name,
                "sentiment_label": entry.sentiment_label,
                "sentiment_score": float(entry.sentiment_score) if entry.sentiment_score is not None else None,
                "reasoning": entry.reasoning,
            }
            for entry in analysis.models
        ],
        "combined_score": float(analysis.combined_score),
        "final_label": final.sentiment_label,
        "final_source": final.source_model,
    }
    comment.sarcasm_confidence = None
    comment.is_sarcastic = False
    comment.toxicity_confidence = None
    comment.is_toxic = False


@shared_task(bind=True, name="app.tasks.ml.link_entities", queue="ml")
def link_entities(self, comment_ids: list[int]) -> dict[str, int]:
    if not comment_ids:
        return {"processed": 0, "linked": 0}

    session = SessionLocal()
    try:
        comments = session.execute(select(Comment).where(Comment.id.in_(comment_ids))).scalars().all()
        if not comments:
            return {"processed": 0, "linked": 0}

        settings = get_settings()
        catalog_entries = _load_cast_catalog(session)
        if not catalog_entries:
            logger.info("Entity linking skipped: no active cast members configured.")
            return {"processed": len(comments), "linked": 0}

        linker = EntityLinker(catalog_entries)
        catalog_lookup = {entry.cast_member_id: entry for entry in catalog_entries}
        pipeline = get_sentiment_pipeline(settings)

        total_mentions = 0
        thread_ids: set[int] = set()

        for comment in comments:
            thread_ids.add(comment.thread_id)
            # Remove previous mentions for idempotency
            session.execute(
                delete(Mention).where(
                    Mention.comment_id == comment.id,
                    Mention.comment_created_at == comment.created_at,
                )
            )

            candidates = linker.find_mentions(comment.body)
            inherited_contexts: dict[int, str] = {}

            inherited_candidates = _inherit_parent_mentions(
                session=session,
                comment=comment,
                catalog_lookup=catalog_lookup,
                existing_cast_ids={candidate.cast_member_id for candidate in candidates},
            )
            for inherited_candidate, parent_context in inherited_candidates:
                candidates.append(inherited_candidate)
                if parent_context:
                    inherited_contexts[inherited_candidate.cast_member_id] = parent_context
            for candidate in candidates:
                total_mentions += 1

            mention_contexts = [_extract_context(comment.body, candidate.quote) for candidate in candidates]
            for idx, candidate in enumerate(candidates):
                if candidate.method != "inherited_context":
                    continue
                parent_body = inherited_contexts.get(candidate.cast_member_id)
                if not parent_body:
                    continue
                parent_context = _extract_context(parent_body, candidate.quote)
                current_context = mention_contexts[idx]
                segments = [segment.strip() for segment in (current_context, parent_context) if segment and segment.strip()]
                if segments:
                    mention_contexts[idx] = " ".join(segments)
                else:
                    mention_contexts[idx] = parent_body

            mention_sentiments: list[NormalizedSentiment] = []
            if candidates:
                mention_sentiments = pipeline.analyze_mentions(
                    comment_text=comment.body,
                    candidates=candidates,
                    contexts=mention_contexts,
                    catalog=catalog_lookup,
                )

            for idx, candidate in enumerate(candidates):
                context = mention_contexts[idx] if idx < len(mention_contexts) else comment.body
                sentiment_result = mention_sentiments[idx] if idx < len(mention_sentiments) else None

                sentiment_label = (comment.sentiment_label or "neutral") or "neutral"
                source_model = settings.primary_model
                raw_sentiment_score: float | None = float(comment.sentiment_score) if comment.sentiment_score is not None else None

                if sentiment_result:
                    if sentiment_result.sentiment_label:
                        sentiment_label = sentiment_result.sentiment_label
                    source_model = sentiment_result.source_model
                    if sentiment_result.sentiment_score is not None:
                        raw_sentiment_score = float(sentiment_result.sentiment_score)
                elif comment.sentiment_label:
                    sentiment_label = comment.sentiment_label

                adjusted_score = _attenuate_sentiment_score(raw_sentiment_score, comment, settings)

                if sentiment_result:
                    logger.info(
                        "Mention comment=%s cast=%s sentiment from %s: %s (raw=%s, adjusted=%s)",
                        comment.id,
                        sentiment_result.cast_member or candidate.cast_member_id,
                        source_model,
                        sentiment_label,
                        f"{raw_sentiment_score:.3f}" if raw_sentiment_score is not None else "n/a",
                        f"{adjusted_score:.3f}" if adjusted_score is not None else "n/a",
                    )
                else:
                    logger.info(
                        "Mention comment=%s cast_id=%s fell back to comment sentiment from %s: %s (raw=%s, adjusted=%s)",
                        comment.id,
                        candidate.cast_member_id,
                        source_model,
                        sentiment_label,
                        f"{raw_sentiment_score:.3f}" if raw_sentiment_score is not None else "n/a",
                        f"{adjusted_score:.3f}" if adjusted_score is not None else "n/a",
                    )

                mention = Mention(
                    comment_id=comment.id,
                    comment_created_at=comment.created_at,
                    cast_member_id=candidate.cast_member_id,
                    sentiment_label=sentiment_label,
                    sentiment_score=adjusted_score,
                    confidence=raw_sentiment_score,
                    weight=candidate.confidence,
                    method=candidate.method,
                    quote=context,
                    is_sarcastic=comment.is_sarcastic,
                    is_toxic=comment.is_toxic,
                )
                session.add(mention)

        session.commit()
        for thread_id in thread_ids:
            compute_aggregates.delay(thread_id)
        return {"processed": len(comments), "linked": total_mentions}
    except (SQLAlchemyError, RuntimeError) as exc:
        session.rollback()
        logger.exception("Failed to link entities: %s", exc)
        raise
    finally:
        session.close()


def _load_cast_catalog(session: Session) -> list[CastCatalogEntry]:
    stmt = (
        select(CastMember)
        .options(selectinload(CastMember.aliases))
        .where(CastMember.is_active.is_(True))
    )
    members = session.execute(stmt).scalars().all()
    catalog: list[CastCatalogEntry] = []

    for member in members:
        aliases = {
            member.full_name,
            member.display_name or "",
            member.slug.replace("-", " "),
        }
        aliases.update(resolve_aliases(member.full_name, member.slug))
        aliases.update(alias.alias for alias in member.aliases)
        clean_aliases = {alias for alias in aliases if alias}
        catalog.append(
            CastCatalogEntry(
                cast_member_id=member.id,
                canonical_name=member.full_name,
                aliases=clean_aliases,
            )
        )
    return catalog


def _extract_context(text: str, quote: str | None, window: int = 200) -> str:
    if not text:
        return quote or ""
    if not quote:
        return text[:window].strip()

    pattern = re.compile(re.escape(quote), re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        quote_lower = quote.lower()
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for sentence in sentences:
            if quote_lower in sentence.lower():
                return sentence.strip()
        return quote

    start = match.start()
    end = match.end()
    context_start = max(0, start - window // 2)
    context_end = min(len(text), end + window // 2)
    snippet = text[context_start:context_end].strip()

    sentences = re.split(r"(?<=[.!?])\s+", snippet)
    for sentence in sentences:
        if quote.lower() in sentence.lower():
            return sentence.strip()

    return snippet or quote


def _inherit_parent_mentions(
    session: Session,
    comment: Comment,
    catalog_lookup: dict[int, CastCatalogEntry],
    existing_cast_ids: set[int],
) -> list[tuple[MentionCandidate, str]]:
    parent_reddit_id = _normalize_parent_reddit_id(comment.parent_id)
    if not parent_reddit_id:
        return []

    parent_row = session.execute(
        select(Comment)
        .options(selectinload(Comment.mentions))
        .where(Comment.reddit_id == parent_reddit_id)
        .order_by(Comment.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not parent_row:
        return []

    parent_comment_id = parent_row.id
    parent_created_at = parent_row.created_at
    parent_body = parent_row.body or ""

    parent_mentions = session.execute(
        select(Mention.cast_member_id, Mention.quote)
        .where(Mention.comment_id == parent_comment_id)
        .where(Mention.comment_created_at == parent_created_at)
    ).all()

    inherited: list[tuple[MentionCandidate, str]] = []
    for cast_member_id, quote in parent_mentions:
        if cast_member_id in existing_cast_ids:
            continue
        if cast_member_id not in catalog_lookup:
            continue
        candidate_quote = quote or catalog_lookup[cast_member_id].canonical_name
        inherited.append(
            (
                MentionCandidate(
                    cast_member_id=cast_member_id,
                    confidence=0.55,
                    method="inherited_context",
                    quote=candidate_quote,
                ),
                parent_body,
            )
        )
    return inherited


def _normalize_parent_reddit_id(parent_id: str | None) -> str | None:
    if not parent_id:
        return None
    if "_" in parent_id:
        prefix, value = parent_id.split("_", 1)
        if prefix in {"t1", "t3"}:
            return value
    return parent_id
