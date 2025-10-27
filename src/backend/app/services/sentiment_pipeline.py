from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence, Set

from huggingface_hub import HfApi

from app.core.config import Settings, get_settings
from app.services import monitoring
from app.services.cast_roster import get_cast_roster_entries
from app.services.entity_linking import CastCatalogEntry, MentionCandidate, get_spacy_model

MODEL_LABELS: Dict[int, str] = {0: "negative", 1: "neutral", 2: "positive"}
DEFAULT_MIN_CONFIDENCE = 0.55
DEFAULT_MIN_MARGIN = 0.10
DEFAULT_MAX_LENGTH = 128
HF_CACHE_DIRNAME = ".hf_cache"
ALIAS_CONFIG_RELATIVE = Path("config") / "sentiment" / "aliases.json"
CACHE_GAUGE_INTERVAL_SECONDS = 300.0
PRONOUN_TOKENS = {"she", "her", "hers"}

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised via dependency injection in tests
    import torch
    from torch import Tensor
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
except ImportError as exc:  # pragma: no cover - fails fast when deps missing
    torch = None  # type: ignore[assignment]
    Tensor = None  # type: ignore[assignment]
    AutoModelForSequenceClassification = None  # type: ignore[assignment]
    AutoTokenizer = None  # type: ignore[assignment]
    logger.error("Sentiment pipeline dependencies are missing: %s", exc)

try:  # pragma: no cover - Azure optional at import time
    from azure.ai.textanalytics import TextAnalyticsClient
    from azure.core.credentials import AzureKeyCredential
    from azure.core.exceptions import AzureError
except ImportError:  # pragma: no cover - Azure fallback optional
    TextAnalyticsClient = None  # type: ignore[assignment]
    AzureKeyCredential = None  # type: ignore[assignment]

    class AzureError(Exception):  # type: ignore[override, misc]
        """Typed alias when azure-core is unavailable."""


@dataclass(slots=True)
class NormalizedSentiment:
    cast_member_id: int | None
    cast_member: str | None
    sentiment_label: str
    sentiment_score: float
    source_model: str
    reasoning: str | None = None
    probabilities: Dict[str, float] | None = None
    margin: float | None = None


@dataclass(slots=True)
class ModelSentiment:
    name: str
    sentiment_label: str
    sentiment_score: float
    reasoning: str | None = None


@dataclass(slots=True)
class SentimentAnalysisResult:
    final: NormalizedSentiment
    models: list[ModelSentiment]
    combined_score: float


@dataclass(slots=True)
class PrimaryPrediction:
    label: str
    score: float
    margin: float
    probabilities: Dict[str, float]


@dataclass(slots=True)
class TargetMetadata:
    name: str
    slug: str | None
    aliases: Set[str]
    normalized_aliases: Set[str]


@dataclass(slots=True)
class TargetSpec:
    key: str
    metadata: TargetMetadata | None
    alias_tokens: Set[str]


def _normalize_text(value: str) -> str:
    value = value.strip().casefold()
    value = re.sub(r"[@#]", " ", value)
    value = re.sub(r"[^a-z0-9\s]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _project_root() -> Path:
    path = Path(__file__).resolve()
    max_depth = len(path.parents) - 1
    for depth in (4, 5):
        try:
            candidate = path.parents[depth]
        except IndexError:
            continue
        if (candidate / "data").exists() or (candidate / "src").exists():
            return candidate
    if max_depth >= 0:
        return path.parents[max_depth]
    return path.parent


class SentimentPipeline:
    """Primary + fallback sentiment pipeline with Hugging Face and Azure opinion mining."""

    def __init__(self, settings: Settings) -> None:
        if AutoTokenizer is None or AutoModelForSequenceClassification is None or torch is None:
            raise RuntimeError(
                "transformers and torch are required for the sentiment pipeline. "
                "Install the optional dependencies to enable this feature."
            )

        self.settings = settings
        self._project_root = _project_root()
        self._cache_dir = self._project_root / HF_CACHE_DIRNAME
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Unable to ensure HF cache directory %s: %s", self._cache_dir, exc)
        os.environ.setdefault("HF_HOME", str(self._cache_dir))
        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

        self.primary_model = settings.primary_model
        self.fallback_service = settings.fallback_service
        self.fallback_enabled = bool(settings.fallback_enabled)
        self.model_revision = "unknown"
        try:
            api = HfApi()
            info = api.model_info(self.primary_model)
            self.model_revision = getattr(info, "sha", "unknown") or "unknown"
        except Exception as exc:  # pragma: no cover - network
            logger.warning("Unable to resolve revision for %s: %s", self.primary_model, exc)

        configured_confidence = settings.sentiment_min_conf or settings.confidence_threshold or 0.0
        self.min_confidence = max(float(configured_confidence), DEFAULT_MIN_CONFIDENCE)
        configured_margin = settings.sentiment_min_margin or 0.0
        self.min_margin = max(float(configured_margin), DEFAULT_MIN_MARGIN)
        self.threshold = self.min_confidence
        self._huggingface_token = settings.huggingface_token
        self._token_used = bool(self._huggingface_token)
        token_kwargs: dict[str, Any] = {}
        if self._huggingface_token:
            os.environ.setdefault("HUGGINGFACE_HUB_TOKEN", self._huggingface_token)
            token_kwargs["token"] = self._huggingface_token

        self._tokenizer = AutoTokenizer.from_pretrained(self.primary_model, **token_kwargs)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.primary_model, **token_kwargs)
        self._model.eval()
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model.to(self._device)

        raw_labels = getattr(self._model.config, "id2label", {}) or {}
        self._id2label: dict[int, str] = {}
        for key, value in raw_labels.items():
            try:
                index = int(key)
            except (TypeError, ValueError):
                continue
            label = str(value).lower()
            self._id2label[index] = self._normalize_label(label)
        for idx, label in MODEL_LABELS.items():
            self._id2label.setdefault(idx, label)
        logger.info(
            "Loaded sentiment model %s (rev=%s) | cache=%s",
            self.primary_model,
            self.model_revision,
            self._cache_dir,
        )

        self._targets: Dict[str, dict[str, Any]] = {}
        self._lookup: Dict[str, str] = {}
        self._register_cast_roster_targets()
        self._register_config_targets()
        self._cache_size_cached: int = 0
        self._cache_size_timestamp: float = 0.0

        self._azure_client = self._build_azure_client(settings)
        if self.fallback_enabled:
            self._run_fallback_canary()
        self._nlp = None

    def _register_cast_roster_targets(self) -> None:
        for entry in get_cast_roster_entries():
            aliases = set(entry.aliases)
            if entry.slug:
                aliases.add(entry.slug)
                aliases.add(entry.slug.replace("-", " "))
            self._register_target(entry.canonical_name, entry.slug, aliases)

    def _register_config_targets(self) -> None:
        config_path = self._project_root / ALIAS_CONFIG_RELATIVE
        if not config_path.exists():
            return
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Unable to parse sentiment alias configuration at %s: %s", config_path, exc)
            return

        entries = payload.get("targets")
        if not isinstance(entries, list):
            logger.warning("Alias configuration at %s missing 'targets' list.", config_path)
            return

        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            name = str(entry.get("name") or "").strip()
            slug = str(entry.get("slug") or "").strip() or None
            aliases = entry.get("aliases") or []
            if not aliases:
                aliases = []
            if not isinstance(aliases, list):
                aliases = []
            aliases_iter = [str(alias).strip() for alias in aliases if str(alias).strip()]
            target_key = name or (slug or "")
            if not target_key:
                continue
            self._register_target(name or target_key, slug, aliases_iter)

    def _register_target(self, name: str, slug: str | None, aliases: Iterable[str]) -> None:
        canonical = name.strip()
        if not canonical and slug:
            canonical = slug.strip()
        if not canonical:
            return

        metadata = self._targets.get(canonical)
        if metadata is None:
            metadata = TargetMetadata(
                name=canonical,
                slug=slug.strip() if slug else None,
                aliases=set(),
                normalized_aliases=set(),
            )
            self._targets[canonical] = metadata
        elif slug and not metadata.slug:
            metadata.slug = slug.strip()

        alias_set = metadata.aliases
        alias_set.add(canonical)
        if metadata.slug:
            alias_set.add(metadata.slug)
            alias_set.add(metadata.slug.replace("-", " "))
        for alias in aliases:
            cleaned = alias.strip()
            if cleaned:
                alias_set.add(cleaned)

        normalized_aliases = {_normalize_text(alias) for alias in alias_set}
        metadata.normalized_aliases = {alias for alias in normalized_aliases if alias}
        for normalized in metadata.normalized_aliases:
            self._lookup.setdefault(normalized, metadata)

    def _metadata_for_target(self, label: str) -> TargetMetadata | None:
        normalized = _normalize_text(label)
        if normalized:
            metadata = self._lookup.get(normalized)
            if metadata:
                return metadata
        stripped = label.strip()
        if stripped:
            return self._targets.get(stripped)
        return None

    def _aliases_for_target_label(self, label: str) -> Set[str]:
        metadata = self._metadata_for_target(label)
        if metadata:
            return set(metadata.normalized_aliases)
        normalized = _normalize_text(label)
        return {normalized} if normalized else set()

    def _detect_targets(self, text: str) -> list[TargetMetadata]:
        normalized_text = _normalize_text(text)
        if not normalized_text:
            return []
        found: dict[str, TargetMetadata] = {}
        for alias, metadata in self._lookup.items():
            if alias and alias in normalized_text:
                found[metadata.name] = metadata
        return list(found.values())

    def _prepare_target_specs(self, text: str, targets: Sequence[str] | None) -> list[TargetSpec]:
        if targets:
            specs: list[TargetSpec] = []
            for target in targets:
                alias_tokens = self._aliases_for_target_label(target)
                metadata = self._metadata_for_target(target)
                specs.append(TargetSpec(key=target, metadata=metadata, alias_tokens=alias_tokens))
            return specs

        detected = self._detect_targets(text)
        if detected:
            return [
                TargetSpec(key=metadata.name, metadata=metadata, alias_tokens=set(metadata.normalized_aliases))
                for metadata in detected
            ]

        return [TargetSpec(key="comment", metadata=None, alias_tokens=set())]

    def _fallback_available(self) -> bool:
        return self.fallback_enabled and self._azure_client is not None

    def _should_use_fallback(self, prediction: PrimaryPrediction | None, has_context: bool) -> bool:
        if not self._fallback_available():
            return False
        if prediction is None:
            return True
        if not has_context:
            return True
        return prediction.score < self.min_confidence or prediction.margin < self.min_margin

    def _run_fallback_canary(self) -> None:
        if not self._fallback_available():
            return
        try:
            start = time.perf_counter()
            response = self._azure_client.analyze_sentiment(["sentiment fallback canary"], show_opinion_mining=True)
            latency_ms = (time.perf_counter() - start) * 1000.0
            document = next(iter(response), None)
            if document is None or getattr(document, "is_error", False):
                logger.warning("Azure fallback canary returned no document or reported error.")
                monitoring.emit_counter("sentiment.infer.error", tags={"scope": "canary"})
                return
            logger.info("Azure fallback canary ok | latency_ms=%.2f", latency_ms)
            monitoring.emit_counter("sentiment.infer.ok", tags={"scope": "canary"})
            monitoring.observe_histogram("sentiment.latency_ms", latency_ms, tags={"scope": "canary"})
        except AzureError as exc:  # pragma: no cover - network/service failures
            logger.warning("Azure fallback canary failed: %s", exc)
            monitoring.emit_counter("sentiment.infer.error", tags={"scope": "canary"})
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Unexpected Azure fallback canary failure: %s", exc)
            monitoring.emit_counter("sentiment.infer.error", tags={"scope": "canary"})

    # ---- Public API -----------------------------------------------------------------

    def analyze_comment(self, text: str) -> SentimentAnalysisResult:
        """Return normalized sentiment along with per-model breakdown for a comment."""
        models: list[ModelSentiment] = []
        start_time = time.perf_counter()
        fallback_used = False
        primary_error = False

        default_breakdown = {"negative": 0.0, "neutral": 1.0, "positive": 0.0}
        try:
            prediction = self._score_primary([text])[0]
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Primary sentiment failed for comment: %s", exc)
            primary_error = True
            prediction = PrimaryPrediction(label="neutral", score=0.0, margin=0.0, probabilities=default_breakdown)

        primary_reason = self._format_primary_reasoning(prediction.label, prediction.score, subject="comment")
        primary_result = NormalizedSentiment(
            cast_member_id=None,
            cast_member=None,
            sentiment_label=prediction.label,
            sentiment_score=prediction.score,
            source_model=self.primary_model,
            reasoning=primary_reason,
            probabilities=prediction.probabilities,
            margin=prediction.margin,
        )
        models.append(
            ModelSentiment(
                name=self.primary_model,
                sentiment_label=prediction.label,
                sentiment_score=prediction.score,
                reasoning=primary_reason,
            )
        )

        final_result = primary_result

        if self._should_use_fallback(prediction, has_context=True):
            azure_document = self._fetch_azure_document([text])
            fallback = self._document_sentiment(
                azure_document,
                cast_member_name=None,
                cast_member_id=None,
                subject="comment",
            )
            if fallback:
                fallback_used = True
                models.append(
                    ModelSentiment(
                        name=fallback.source_model,
                        sentiment_label=fallback.sentiment_label,
                        sentiment_score=fallback.sentiment_score,
                        reasoning=fallback.reasoning,
                    )
                )
                final_result = fallback

        combined_score = sum(entry.sentiment_score for entry in models if entry.sentiment_score is not None)

        self._log_model_results("comment", final_result, models)
        latency = time.perf_counter() - start_time
        status = "fallback" if fallback_used else ("error" if primary_error else "ok")
        self._emit_metrics(
            "comment",
            prediction,
            fallback_used,
            latency,
            targets_found=1,
            confidence=final_result.sentiment_score,
            status=status,
        )

        return SentimentAnalysisResult(
            final=final_result,
            models=models,
            combined_score=float(combined_score),
        )

    def analyze_mentions(
        self,
        comment_text: str,
        candidates: Sequence[MentionCandidate],
        contexts: Sequence[str],
        catalog: dict[int, CastCatalogEntry],
    ) -> list[NormalizedSentiment]:
        """Return normalized sentiment for each mention candidate within a comment."""
        if not candidates or not contexts:
            return []

        unique_cast_ids = {candidate.cast_member_id for candidate in candidates if candidate.cast_member_id is not None}
        if len(unique_cast_ids) <= 1:
            return self._analyze_single_target_mentions(
                comment_text=comment_text,
                candidates=candidates,
                contexts=contexts,
                catalog=catalog,
            )

        return self._analyze_multi_target_mentions(
            comment_text=comment_text,
            candidates=candidates,
            contexts=contexts,
            catalog=catalog,
        )

    # ---- Internal helper entry points -----------------------------------------

    def _analyze_single_target_mentions(
        self,
        comment_text: str,
        candidates: Sequence[MentionCandidate],
        contexts: Sequence[str],
        catalog: dict[int, CastCatalogEntry],
    ) -> list[NormalizedSentiment]:
        paired = list(zip(candidates, contexts))
        if not paired:
            return []

        primary_error = False
        try:
            primary_predictions = self._score_primary([context for _, context in paired])
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Primary sentiment failed for mentions: %s", exc)
            primary_error = True
            default_prediction = PrimaryPrediction(
                label="neutral",
                score=0.0,
                margin=0.0,
                probabilities={"negative": 0.0, "neutral": 1.0, "positive": 0.0},
            )
            primary_predictions = [default_prediction] * len(paired)

        if len(primary_predictions) != len(paired):  # pragma: no cover - defensive alignment
            logger.warning(
                "Primary sentiment produced %s scores for %s contexts; trimming to align.",
                len(primary_predictions),
                len(paired),
            )
            limit = min(len(primary_predictions), len(paired))
            paired = paired[:limit]
            primary_predictions = primary_predictions[:limit]

        azure_document = None
        results: list[NormalizedSentiment] = []

        for (candidate, context), prediction in zip(paired, primary_predictions):
            loop_start = time.perf_counter()
            entry = catalog.get(candidate.cast_member_id)
            cast_name = entry.canonical_name if entry else None
            subject = cast_name or "mention"
            primary_reason = self._format_primary_reasoning(prediction.label, prediction.score, subject=subject)

            model_entries: list[ModelSentiment] = [
                ModelSentiment(
                    name=self.primary_model,
                    sentiment_label=prediction.label,
                    sentiment_score=prediction.score,
                    reasoning=primary_reason,
                )
            ]

            result = NormalizedSentiment(
                cast_member_id=candidate.cast_member_id,
                cast_member=cast_name,
                sentiment_label=prediction.label,
                sentiment_score=prediction.score,
                source_model=self.primary_model,
                reasoning=primary_reason,
                probabilities=prediction.probabilities,
                margin=prediction.margin,
            )

            fallback_used = False
            has_context = bool(context and context.strip())
            if self._should_use_fallback(prediction, has_context=has_context):
                if azure_document is None:
                    azure_document = self._fetch_azure_document([comment_text])
                fallback = self._opinion_sentiment(
                    azure_document,
                    candidate=candidate,
                    entry=entry,
                )
                if fallback is None and azure_document is not None:
                    fallback = self._document_sentiment(
                        azure_document,
                        cast_member_name=cast_name,
                        cast_member_id=candidate.cast_member_id,
                        subject=subject,
                    )
                if fallback is not None:
                    model_entries.append(
                        ModelSentiment(
                            name=fallback.source_model,
                            sentiment_label=fallback.sentiment_label,
                            sentiment_score=fallback.sentiment_score,
                            reasoning=fallback.reasoning,
                        )
                    )
                    result = fallback
                    fallback_used = True

            self._log_model_results("mention", result, model_entries, candidate=candidate)
            latency = time.perf_counter() - loop_start
            status = "fallback" if fallback_used else ("error" if primary_error else "ok")
            self._emit_metrics(
                "mention",
                prediction,
                fallback_used,
                latency,
                targets_found=1,
                confidence=result.sentiment_score,
                status=status,
            )
            results.append(result)

        return results

    def analyze_freeform(self, text: str, targets: Sequence[str] | None = None) -> Dict[str, Any]:
        text = text or ""
        sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
        if not sentences:
            sentences = [text.strip()] if text.strip() else []

        specs = self._prepare_target_specs(text, targets)
        contexts_map: Dict[str, list[str]] = {spec.key: [] for spec in specs}
        normalized_sentences = [(sentence, _normalize_text(sentence)) for sentence in sentences]

        last_target: str | None = None
        for original_sentence, normalized_sentence in normalized_sentences:
            matched: list[str] = []
            for spec in specs:
                if spec.alias_tokens and any(alias in normalized_sentence for alias in spec.alias_tokens):
                    contexts_map[spec.key].append(original_sentence)
                    matched.append(spec.key)
            if matched:
                last_target = matched[-1]
                continue
            if last_target and any(token in normalized_sentence.split() for token in PRONOUN_TOKENS):
                contexts_map[last_target].append(original_sentence)

        score_inputs: list[str] = []
        for spec in specs:
            context_text = " ".join(contexts_map.get(spec.key, [])) or text
            score_inputs.append(context_text.strip() or text)

        primary_error = False
        default_prediction = PrimaryPrediction(
            label="neutral",
            score=0.0,
            margin=0.0,
            probabilities={"negative": 0.0, "neutral": 1.0, "positive": 0.0},
        )

        try:
            predictions = self._score_primary(score_inputs)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Primary sentiment failed for freeform text: %s", exc)
            primary_error = True
            predictions = [default_prediction for _ in score_inputs]

        if len(predictions) != len(score_inputs):  # pragma: no cover - defensive alignment
            logger.warning(
                "Primary sentiment returned %s predictions for %s inputs; normalizing lengths.",
                len(predictions),
                len(score_inputs),
            )
            primary_error = True
            adjusted: list[PrimaryPrediction] = list(predictions[: len(score_inputs)])
            while len(adjusted) < len(score_inputs):
                adjusted.append(default_prediction)
            predictions = adjusted

        azure_document = None
        targets_found = sum(1 for spec in specs if contexts_map.get(spec.key))
        if not targets:
            targets_found = 1 if text else 0

        target_results: Dict[str, Dict[str, Any]] = {}
        fallback_used_any = False

        for spec, context_text, prediction in zip(specs, score_inputs, predictions):
            loop_start = time.perf_counter()
            has_context = bool(contexts_map.get(spec.key))
            fallback_used = False
            final_label = prediction.label
            final_score = prediction.score
            final_probs = prediction.probabilities
            final_margin = prediction.margin
            source = "primary"

            if self._should_use_fallback(prediction, has_context=has_context):
                if azure_document is None:
                    azure_document = self._fetch_azure_document([text])
                fallback = None
                if azure_document is not None:
                    candidate = MentionCandidate(
                        cast_member_id=-1,
                        confidence=1.0,
                        method="alias",
                        quote=spec.metadata.slug if spec.metadata and spec.metadata.slug else spec.key,
                    )
                    fallback = self._opinion_sentiment(azure_document, candidate=candidate, entry=None)
                    if fallback is None:
                        fallback = self._document_sentiment(
                            azure_document,
                            cast_member_name=spec.metadata.name if spec.metadata else spec.key,
                            cast_member_id=None,
                            subject="target",
                        )
                if fallback is not None:
                    final_label = fallback.sentiment_label
                    final_score = fallback.sentiment_score
                    final_probs = fallback.probabilities or final_probs
                    final_margin = fallback.margin or final_margin
                    source = "fallback"
                    fallback_used = True

            status = "fallback" if fallback_used else ("error" if primary_error else "ok")
            self._emit_metrics(
                "freeform",
                prediction,
                fallback_used,
                time.perf_counter() - loop_start,
                targets_found=max(targets_found, 1),
                confidence=final_score,
                status=status,
            )
            fallback_used_any |= fallback_used
            target_results[spec.key] = {
                "label": final_label,
                "score": self._round_score(final_score),
                "probs": self._format_probabilities(final_probs),
                "margin": self._round_score(final_margin or prediction.margin),
                "source": source,
            }

        return {
            "text": text,
            "model": {"id": self.primary_model, "rev": self.model_revision, "source": "hf"},
            "targets": target_results,
            "fallback_used": fallback_used_any,
        }
    def _analyze_multi_target_mentions(
        self,
        comment_text: str,
        candidates: Sequence[MentionCandidate],
        contexts: Sequence[str],
        catalog: dict[int, CastCatalogEntry],
    ) -> list[NormalizedSentiment]:
        paired = list(zip(candidates, contexts))
        if not paired:
            return []

        primary_error = False
        try:
            primary_predictions = self._score_primary([context for _, context in paired])
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Primary sentiment failed for mentions: %s", exc)
            primary_error = True
            default_prediction = PrimaryPrediction(
                label="neutral",
                score=0.0,
                margin=0.0,
                probabilities={"negative": 0.0, "neutral": 1.0, "positive": 0.0},
            )
            primary_predictions = [default_prediction] * len(paired)

        if len(primary_predictions) != len(paired):  # pragma: no cover - defensive alignment
            logger.warning(
                "Primary sentiment produced %s scores for %s contexts; trimming to align.",
                len(primary_predictions),
                len(paired),
            )
            limit = min(len(primary_predictions), len(paired))
            paired = paired[:limit]
            primary_predictions = primary_predictions[:limit]

        azure_document = self._fetch_azure_document([comment_text])
        parsed_doc = self._parse_comment_for_heuristics(comment_text)
        results: list[NormalizedSentiment] = []

        for (candidate, context), prediction in zip(paired, primary_predictions):
            loop_start = time.perf_counter()
            entry = catalog.get(candidate.cast_member_id)
            cast_name = entry.canonical_name if entry else None
            subject = cast_name or "mention"
            primary_reason = self._format_primary_reasoning(prediction.label, prediction.score, subject=subject)

            model_entries: list[ModelSentiment] = [
                ModelSentiment(
                    name=self.primary_model,
                    sentiment_label=prediction.label,
                    sentiment_score=prediction.score,
                    reasoning=primary_reason,
                )
            ]

            result = NormalizedSentiment(
                cast_member_id=candidate.cast_member_id,
                cast_member=cast_name,
                sentiment_label=prediction.label,
                sentiment_score=prediction.score,
                source_model=self.primary_model,
                reasoning=primary_reason,
                probabilities=prediction.probabilities,
                margin=prediction.margin,
            )

            fallback_used = False
            fallback = None
            has_context = bool(context and context.strip())
            if self._should_use_fallback(prediction, has_context=has_context) and azure_document is not None:
                fallback = self._opinion_sentiment(
                    azure_document,
                    candidate=candidate,
                    entry=entry,
                )
                if fallback is None:
                    fallback = self._document_sentiment(
                        azure_document,
                        cast_member_name=cast_name,
                        cast_member_id=candidate.cast_member_id,
                        subject=subject,
                    )

            if fallback is not None:
                model_entries.append(
                    ModelSentiment(
                        name=fallback.source_model,
                        sentiment_label=fallback.sentiment_label,
                        sentiment_score=fallback.sentiment_score,
                        reasoning=fallback.reasoning,
                    )
                )
                result = fallback
                fallback_used = True
            else:
                heuristic = self._heuristic_sentiment(
                    doc=parsed_doc,
                    candidate=candidate,
                    entry=entry,
                    default_label=prediction.label,
                    default_score=prediction.score,
                    context=context,
                )
                if heuristic is not None:
                    model_entries.append(
                        ModelSentiment(
                            name=heuristic.source_model,
                            sentiment_label=heuristic.sentiment_label,
                            sentiment_score=heuristic.sentiment_score,
                            reasoning=heuristic.reasoning,
                        )
                    )
                    result = heuristic

            self._log_model_results("mention", result, model_entries, candidate=candidate)
            latency = time.perf_counter() - loop_start
            status = "fallback" if fallback_used else ("error" if primary_error else "ok")
            self._emit_metrics(
                "mention",
                prediction,
                fallback_used,
                latency,
                targets_found=1,
                confidence=result.sentiment_score,
                status=status,
            )
            results.append(result)

        return results

    def _parse_comment_for_heuristics(self, text: str):
        if not text:
            return None
        nlp = self._ensure_nlp()
        if nlp is None:
            return None
        try:
            return nlp(text)
        except Exception as exc:  # pragma: no cover - spaCy parsing guard
            logger.debug("spaCy parsing failed for sentiment heuristics: %s", exc)
            return None

    def _ensure_nlp(self):
        if self._nlp is not None:
            return self._nlp
        try:
            self._nlp = get_spacy_model()
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.warning("spaCy heuristics unavailable: %s", exc)
            self._nlp = None
        return self._nlp

    def _heuristic_sentiment(
        self,
        doc: Any,
        candidate: MentionCandidate,
        entry: CastCatalogEntry | None,
        default_label: str,
        default_score: float,
        context: str,
    ) -> NormalizedSentiment | None:
        if doc is None:
            return None

        aliases = self._candidate_aliases(candidate, entry)
        lowered_aliases = {alias.lower() for alias in aliases}
        if not lowered_aliases:
            return None

        sentence = self._candidate_sentence(doc, lowered_aliases)
        if sentence is None:
            return None

        clause_text, pivot = self._select_clause(sentence, lowered_aliases)
        text_to_score = (clause_text or context or sentence.text or "").strip()
        if not text_to_score:
            return None

        try:
            heuristic_prediction = self._score_primary([text_to_score])[0]
            heuristic_label = heuristic_prediction.label
            heuristic_score = heuristic_prediction.score
        except Exception as exc:  # pragma: no cover - fallback on failure
            logger.debug("Heuristic sentiment scoring failed, using defaults: %s", exc)
            heuristic_label, heuristic_score = default_label, default_score
            heuristic_prediction = None

        cast_name = entry.canonical_name if entry else None
        reasoning_base = f"Heuristic clause selection used {self.primary_model} on '{text_to_score[:80]}'"
        if pivot:
            reasoning = f"{reasoning_base}, prioritizing clause after '{pivot}'."
        else:
            reasoning = f"{reasoning_base}."

        return NormalizedSentiment(
            cast_member_id=candidate.cast_member_id,
            cast_member=cast_name,
            sentiment_label=heuristic_label,
            sentiment_score=float(heuristic_score),
            source_model=f"{self.primary_model}+heuristic",
            reasoning=reasoning,
            probabilities=heuristic_prediction.probabilities if heuristic_prediction else None,
            margin=heuristic_prediction.margin if heuristic_prediction else None,
        )

    def _candidate_sentence(self, doc: Any, lowered_aliases: set[str]):
        try:
            sentences = doc.sents  # type: ignore[attr-defined]
        except AttributeError:  # pragma: no cover - when doc lacks sentences
            return None

        for sentence in sentences:
            sentence_text = getattr(sentence, "text", "")
            if not sentence_text:
                continue
            lower_sentence = sentence_text.lower()
            if any(alias in lower_sentence for alias in lowered_aliases):
                return sentence
        return None

    def _select_clause(self, sentence: Any, lowered_aliases: set[str]) -> tuple[str | None, str | None]:
        text = getattr(sentence, "text", "")
        if not text:
            return None, None

        lowered = text.lower()
        alias_positions = [
            lowered.find(alias)
            for alias in lowered_aliases
            if lowered.find(alias) != -1
        ]
        alias_index = min(alias_positions) if alias_positions else -1

        pivot_terms = [
            " however ",
            " but ",
            " though ",
            " although ",
            " yet ",
            " nevertheless ",
            " still ",
        ]
        for pivot in pivot_terms:
            pivot_index = lowered.rfind(pivot)
            if pivot_index == -1:
                continue

            pivot_clean = pivot.strip()
            pivot_end = pivot_index + len(pivot)

            if alias_index != -1 and alias_index >= pivot_end:
                clause = text[pivot_end:].strip(" ,;-")
                if clause:
                    return clause, pivot_clean
            elif alias_index != -1:
                clause = text[:pivot_index].strip(" ,;-")
                if clause:
                    return clause, pivot_clean

        # Dependency-based refinement: use subtree around the alias token.
        tokens = []
        try:
            tokens = [token for token in sentence if token.text.lower() in lowered_aliases]
        except Exception:  # pragma: no cover - spaCy token access failure
            tokens = []

        for token in tokens:
            try:
                subtree_tokens = list(token.subtree)
            except Exception:  # pragma: no cover - safety
                continue
            if not subtree_tokens:
                continue
            start = min(tok.i for tok in subtree_tokens)
            end = max(tok.i for tok in subtree_tokens) + 1
            doc = getattr(sentence, "doc", None)
            if doc is None:
                continue
            span = doc[start:end]
            clause = span.text.strip()
            if clause and clause.lower() != lowered:
                return clause, None

        return None, None

    # ---- Internal helpers -----------------------------------------------------------

    def _score_primary(self, texts: Sequence[str]) -> list[PrimaryPrediction]:
        encoded = self._tokenizer(
            list(texts),
            truncation=True,
            padding=True,
            max_length=DEFAULT_MAX_LENGTH,
            return_tensors="pt",
        )
        encoded = {key: value.to(self._device) for key, value in encoded.items()}
        with torch.no_grad():
            outputs = self._model(**encoded)
            logits: Tensor = outputs.logits  # type: ignore[assignment]
            probabilities = torch.softmax(logits, dim=-1).detach().cpu()

        predictions: list[PrimaryPrediction] = []
        for row in probabilities:
            probs = row.tolist()
            if not probs:
                predictions.append(
                    PrimaryPrediction(
                        label="neutral",
                        score=0.0,
                        margin=0.0,
                        probabilities={"negative": 0.0, "neutral": 0.0, "positive": 0.0},
                    )
                )
                continue
            best_idx = max(range(len(probs)), key=probs.__getitem__)
            sorted_probs = sorted(probs, reverse=True)
            margin = sorted_probs[0] - (sorted_probs[1] if len(sorted_probs) > 1 else 0.0)
            label_raw = self._id2label.get(best_idx, MODEL_LABELS.get(best_idx, str(best_idx)))
            label = self._normalize_label(label_raw)
            breakdown: Dict[str, float] = {}
            for idx, prob in enumerate(probs):
                label_key = self._normalize_label(self._id2label.get(idx, MODEL_LABELS.get(idx, str(idx))))
                breakdown[label_key] = float(prob)
            predictions.append(
                PrimaryPrediction(
                    label=label,
                    score=float(probs[best_idx]),
                    margin=float(margin),
                    probabilities=breakdown,
                )
            )
        return predictions

    def _fetch_azure_document(self, documents: Sequence[str]):
        if not documents or self._azure_client is None:
            return None
        try:
            response = self._azure_client.analyze_sentiment(
                list(documents),
                show_opinion_mining=True,
            )
        except AzureError as exc:  # pragma: no cover - network/service failures
            logger.warning("Azure opinion mining failed: %s", exc)
            return None
        except Exception as exc:  # pragma: no cover - generic defensive catch
            logger.warning("Unexpected Azure sentiment error: %s", exc)
            return None

        document = next(iter(response), None)
        if document is None:  # pragma: no cover - defensive
            logger.warning("Azure sentiment response empty.")
        return document

    def _document_sentiment(
        self,
        document,
        cast_member_name: str | None,
        cast_member_id: int | None,
        subject: str,
    ) -> NormalizedSentiment | None:
        if document is None or getattr(document, "is_error", False):
            return None

        label = self._normalize_label(getattr(document, "sentiment", "neutral"))
        scores = getattr(document, "confidence_scores", None)
        probabilities = self._azure_scores_to_probabilities(scores)
        score_value = None
        if probabilities and label in probabilities:
            score_value = probabilities[label]
        elif probabilities:
            score_value = max(probabilities.values(), default=0.0)
        if score_value is None:
            score_value = 0.0

        reasoning = (
            f"{self.fallback_service} inferred {label} sentiment ({score_value:.1%}) for the {cast_member_name or subject}."
        )

        return NormalizedSentiment(
            cast_member_id=cast_member_id,
            cast_member=cast_member_name,
            sentiment_label=label,
            sentiment_score=float(score_value),
            source_model=self.fallback_service,
            reasoning=reasoning,
            probabilities=probabilities,
        )

    def _opinion_sentiment(
        self,
        document,
        candidate: MentionCandidate,
        entry: CastCatalogEntry | None,
    ) -> NormalizedSentiment | None:
        if document is None or getattr(document, "is_error", False):
            return None

        aliases = self._candidate_aliases(candidate, entry)
        for sentence in getattr(document, "sentences", []):
            for opinion in getattr(sentence, "opinions", []):
                target = getattr(opinion, "target", None)
                if target is None:
                    continue
                target_text = getattr(target, "text", "") or ""
                normalized_target = target_text.lower()
                if not aliases or any(alias in normalized_target for alias in aliases):
                    label = self._normalize_label(getattr(target, "sentiment", "neutral"))
                    scores = getattr(target, "confidence_scores", None)
                    probabilities = self._azure_scores_to_probabilities(scores)
                    score_value = None
                    if probabilities and label in probabilities:
                        score_value = probabilities[label]
                    elif probabilities:
                        score_value = max(probabilities.values(), default=0.0)
                    if score_value is None:
                        score_value = 0.0
                    cast_name = entry.canonical_name if entry else getattr(target, "text", None)
                    reasoning = (
                        f"{self.fallback_service} opinion target '{target_text}' predicted {label} sentiment ({score_value:.1%})."
                    )
                    return NormalizedSentiment(
                        cast_member_id=candidate.cast_member_id,
                        cast_member=cast_name,
                        sentiment_label=label,
                        sentiment_score=float(score_value),
                        source_model=self.fallback_service,
                        reasoning=reasoning,
                        probabilities=probabilities,
                    )
        return None

    def _candidate_aliases(self, candidate: MentionCandidate, entry: CastCatalogEntry | None) -> set[str]:
        aliases: set[str] = set()
        if entry:
            aliases.add(entry.canonical_name.lower())
            aliases.update(alias.lower() for alias in entry.aliases)
        if candidate.quote:
            aliases.add(candidate.quote.lower())
        return {alias for alias in aliases if alias}

    def _format_primary_reasoning(self, label: str, score: float, subject: str) -> str:
        return f"{self.primary_model} predicted {label} with {score:.1%} confidence for the {subject}."

    def _round_score(self, value: float | None) -> float:
        if value is None:
            return 0.0
        return round(float(value), 2)

    def _format_probabilities(self, probabilities: Dict[str, float] | None) -> Dict[str, float]:
        formatted = {"neg": 0.0, "neu": 0.0, "pos": 0.0}
        if not probabilities:
            return formatted
        for source_key, target_key in (
            ("negative", "neg"),
            ("neg", "neg"),
            ("neutral", "neu"),
            ("neu", "neu"),
            ("positive", "pos"),
            ("pos", "pos"),
        ):
            value = probabilities.get(source_key)
            if value is not None:
                formatted[target_key] = self._round_score(value)
        return formatted

    def _azure_scores_to_probabilities(self, scores: Any) -> Dict[str, float] | None:
        if scores is None:
            return None
        values: Dict[str, float] = {}
        for attribute in ("positive", "neutral", "negative"):
            value = getattr(scores, attribute, None)
            if value is None:
                continue
            values[self._normalize_label(attribute)] = float(value)
        return values or None

    def _cache_size_bytes(self) -> int:
        now = time.time()
        if (now - self._cache_size_timestamp) < CACHE_GAUGE_INTERVAL_SECONDS and self._cache_size_cached:
            return self._cache_size_cached
        size = 0
        try:
            for path in self._cache_dir.rglob("*"):
                if path.is_file():
                    try:
                        size += path.stat().st_size
                    except OSError:
                        continue
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Unable to compute cache size for %s: %s", self._cache_dir, exc)
        else:
            self._cache_size_cached = size
            self._cache_size_timestamp = now
        return self._cache_size_cached

    def _normalize_label(self, label: str) -> str:
        normalized = label.lower()
        if normalized in {"label_0", "negative"}:
            return "negative"
        if normalized in {"label_1", "neutral"}:
            return "neutral"
        if normalized in {"label_2", "positive"}:
            return "positive"
        if normalized in {"negative or neutral", "neutral or negative", "positive or neutral", "neutral or positive"}:
            return "mixed"
        return normalized

    def _build_azure_client(self, settings: Settings):
        if not settings.azure_text_analytics_endpoint or not settings.azure_text_analytics_key:
            return None
        if TextAnalyticsClient is None or AzureKeyCredential is None:
            logger.warning(
                "Azure Text Analytics credentials provided but azure-ai-textanalytics is not installed."
            )
            return None
        endpoint = settings.azure_text_analytics_endpoint.rstrip("/")
        credential = AzureKeyCredential(settings.azure_text_analytics_key)
        try:
            return TextAnalyticsClient(endpoint=endpoint, credential=credential)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to initialize Azure Text Analytics client: %s", exc)
            return None

    def _log_result(
        self,
        scope: str,
        result: NormalizedSentiment,
        candidate: MentionCandidate | None = None,
    ) -> None:
        target = result.cast_member or (candidate.quote if candidate else "comment")
        logger.info(
            "Sentiment %s resolved via %s for %s -> %s (%.3f)%s",
            scope,
            result.source_model,
            target,
            result.sentiment_label,
            result.sentiment_score,
            f" | {result.reasoning}" if result.reasoning else "",
        )

    def _log_model_results(
        self,
        scope: str,
        final_result: NormalizedSentiment,
        models: Sequence[ModelSentiment],
        candidate: MentionCandidate | None = None,
    ) -> None:
        target = final_result.cast_member or (candidate.quote if candidate else "comment")
        for entry in models:
            logger.info(
                "Sentiment %s model %s for %s -> %s (%.3f)%s",
                scope,
                entry.name,
                target,
                entry.sentiment_label,
                entry.sentiment_score,
                f" | {entry.reasoning}" if entry.reasoning else "",
            )
        logger.info(
            "Sentiment %s final selection via %s for %s -> %s (%.3f)",
            scope,
            final_result.source_model,
            target,
            final_result.sentiment_label,
            final_result.sentiment_score,
        )

    def _emit_metrics(
        self,
        scope: str,
        prediction: PrimaryPrediction | None,
        fallback_used: bool,
        latency_seconds: float,
        targets_found: int,
        confidence: float,
        status: str,
    ) -> None:
        latency_ms = latency_seconds * 1000.0
        top_prob = prediction.score if prediction else 0.0
        margin = prediction.margin if prediction else 0.0
        logger.info(
            "Sentiment metrics | scope=%s status=%s model_id=%s revision=%s latency_ms=%.2f targets=%s top_prob=%.3f margin=%.3f fallback=%s confidence=%.3f",
            scope,
            status,
            self.primary_model,
            self.model_revision,
            latency_ms,
            targets_found,
            top_prob,
            margin,
            fallback_used,
            confidence,
        )

        if status == "fallback":
            monitoring.emit_counter("sentiment.infer.fallback", tags={"scope": scope})
        elif status == "error":
            monitoring.emit_counter("sentiment.infer.error", tags={"scope": scope})
        else:
            monitoring.emit_counter("sentiment.infer.ok", tags={"scope": scope})

        monitoring.observe_histogram("sentiment.latency_ms", latency_ms, tags={"scope": scope})
        monitoring.set_gauge("sentiment.cache.size", float(self._cache_size_bytes()), tags={"scope": scope})


_PIPELINE: SentimentPipeline | None = None
_PIPELINE_LOCK = threading.Lock()


def get_sentiment_pipeline(settings: Settings | None = None) -> SentimentPipeline:
    global _PIPELINE
    if settings is None:
        settings = get_settings()
    with _PIPELINE_LOCK:
        if _PIPELINE is None:
            _PIPELINE = SentimentPipeline(settings)
    return _PIPELINE


def analyze_text(text: str, targets: Sequence[str] | None = None) -> Dict[str, Any]:
    pipeline = get_sentiment_pipeline()
    return pipeline.analyze_freeform(text=text, targets=targets)


def sentiment_pipeline_healthcheck() -> Dict[str, Any]:
    pipeline = get_sentiment_pipeline()
    start = time.perf_counter()
    prediction = pipeline._score_primary(["health check probe"])[0]
    latency = time.perf_counter() - start
    return {
        "model_id": pipeline.primary_model,
        "revision": pipeline.model_revision,
        "token_used": pipeline._token_used,
        "latency_ms": latency * 1000.0,
        "label": prediction.label,
        "confidence": prediction.score,
        "fallback_enabled": pipeline.fallback_enabled,
        "min_confidence": pipeline.min_confidence,
        "min_margin": pipeline.min_margin,
        "cache_bytes": pipeline._cache_size_bytes(),
        "targets_indexed": len(pipeline._targets),
    }


def health_check() -> Dict[str, Any]:
    """Convenience wrapper used by cache warming scripts."""
    return sentiment_pipeline_healthcheck()
