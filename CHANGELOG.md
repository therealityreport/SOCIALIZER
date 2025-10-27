# Changelog

## [1.1.0] - 2025-11-07

### Added
- Stable sentiment contract via `analyze_text`, including target alias expansion from cast rosters and config-driven fallbacks.
- Runtime instrumentation that emits counters (`sentiment.infer.*`), latency histograms, and cache gauges while logging model id, revision, and inference telemetry.
- Optional Azure fallback canary executed at startup with secret-aware logging.
- Environment defaults for `PYTHONPATH`, `HF_HOME`, `HF_TOKEN`, `HUGGINGFACE_HUB_TOKEN`, `SENTIMENT_MIN_CONF`, `SENTIMENT_MIN_MARGIN`, and `FALLBACK_ENABLED` to harden Celery/Uvicorn runtime exports.

### Changed
- Hugging Face model remains pinned to `cardiffnlp/twitter-roberta-base-topic-sentiment-latest`; revision is now resolved via `HfApi` and surfaced in logs and health checks.
- CI pipeline ensures model cache directories and tokens are available before running sentiment tests.

### Database
- Migration `202511071200_add_comment_sentiment_breakdown` verified with rollback coverage for the new `comments.sentiment_breakdown` column.
