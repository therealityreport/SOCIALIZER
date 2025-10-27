from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, List

from rapidfuzz import fuzz, process

from app.core.config import get_settings

logger = logging.getLogger(__name__)

try:
    import spacy
    from spacy.language import Language
except ImportError as exc:  # pragma: no cover - spaCy might be optional in some envs
    spacy = None
    Language = None
    logger.error("spaCy is required for entity linking but is not installed: %s", exc)


@dataclass
class CastCatalogEntry:
    cast_member_id: int
    canonical_name: str
    aliases: set[str] = field(default_factory=set)


@dataclass
class MentionCandidate:
    cast_member_id: int
    confidence: float
    method: str
    quote: str


def load_spacy_model() -> Language:
    if spacy is None:
        raise RuntimeError("spaCy is not installed. Install it to enable entity linking.")
    settings = get_settings()
    model_name = settings.spacy_model_name
    try:
        return spacy.load(model_name)
    except OSError as exc:
        logger.warning(
            "spaCy model '%s' unavailable; falling back to blank English pipeline. "
            "Install the model (python -m spacy download %s) for improved entity linking.",
            model_name,
            model_name,
        )
        return spacy.blank("en")


@lru_cache(maxsize=1)
def get_spacy_model() -> Language:
    return load_spacy_model()


class EntityLinker:
    def __init__(self, catalog: Iterable[CastCatalogEntry]) -> None:
        self.catalog: List[CastCatalogEntry] = list(catalog)
        self.alias_lookup: dict[str, int] = {}
        self.alias_choices: list[str] = []
        self.alias_patterns: dict[str, re.Pattern[str]] = {}

        for entry in self.catalog:
            canonical = entry.canonical_name.strip().lower()
            if canonical:
                self._register_alias(canonical, entry.cast_member_id)

            for alias in entry.aliases:
                normalized = alias.strip().lower()
                if len(normalized) < 3:
                    continue
                self._register_alias(normalized, entry.cast_member_id)

        self.nlp = get_spacy_model()

    def _register_alias(self, alias: str, cast_member_id: int) -> None:
        self.alias_lookup[alias] = cast_member_id
        self.alias_choices.append(alias)
        self.alias_patterns[alias] = re.compile(rf"(?<![0-9a-z]){re.escape(alias)}(?![0-9a-z])")

    def find_mentions(self, text: str) -> list[MentionCandidate]:
        if not text:
            return []

        lower_text = text.lower()
        candidates: dict[int, MentionCandidate] = {}

        # Exact substring matches against known aliases
        for alias, cast_id in self.alias_lookup.items():
            pattern = self.alias_patterns.get(alias)
            if not pattern:
                continue
            match = pattern.search(lower_text)
            if match:
                quote = self._extract_quote(text, match.group(0))
                self._register_candidate(candidates, cast_id, confidence=0.95, method="exact", quote=quote)

        # spaCy entity recognition with fuzzy fallback
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.label_ not in {"PERSON", "ORG", "WORK_OF_ART"}:
                continue

            normalized_ent = ent.text.lower()
            if normalized_ent in self.alias_lookup:
                cast_id = self.alias_lookup[normalized_ent]
                self._register_candidate(candidates, cast_id, confidence=0.98, method="exact_ner", quote=ent.text)
                continue

            if not self.alias_choices:
                continue

            match = process.extractOne(
                normalized_ent,
                self.alias_choices,
                scorer=fuzz.partial_ratio,
            )
            if not match:
                continue

            alias, score, _ = match
            if score < 85:
                continue

            cast_id = self.alias_lookup.get(alias)

            if not cast_id:
                continue

            confidence = score / 100.0
            self._register_candidate(candidates, cast_id, confidence=confidence, method="fuzzy", quote=ent.text)

        return list(candidates.values())

    def _register_candidate(
        self,
        candidates: dict[int, MentionCandidate],
        cast_id: int,
        confidence: float,
        method: str,
        quote: str,
    ) -> None:
        existing = candidates.get(cast_id)
        if not existing or confidence > existing.confidence:
            candidates[cast_id] = MentionCandidate(
                cast_member_id=cast_id,
                confidence=confidence,
                method=method,
                quote=quote,
            )

    @staticmethod
    def _extract_quote(text: str, alias: str) -> str:
        pattern = re.compile(re.escape(alias), re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return match.group(0)
        return alias
