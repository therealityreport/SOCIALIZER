## Environment Variables Reference

This document summarizes the environment variables consumed by the SOCIALIZER platform. Copy `.env.example` to `.env` and override the values per environment (`config/environments/development.env`, `staging.env`, `production.env`).

### Core Settings

- `ENV`: Runtime environment (`development`, `staging`, `production`).
- `DEBUG`: Enables verbose logging when true.
- `SECRET_KEY`: 32+ character secret used for signing tokens.
- `API_VERSION`: Prefix for API URLs (`v1`).

### Server

- `BACKEND_HOST` / `BACKEND_PORT`: FastAPI host and port.
- `FRONTEND_URL`: Public URL for the web client.
- `CORS_ORIGINS`: Comma-separated origins allowed to access the API.
- `PYTHONPATH`: Ensures Celery/Uvicorn processes resolve backend modules without extra flags (`src/backend` in local environments).

### Database

- `DATABASE_URL`: PostgreSQL connection string for application traffic.
- `DATABASE_POOL_SIZE`: SQLAlchemy connection pool size.
- `DATABASE_MAX_OVERFLOW`: Additional connections allowed beyond pool size.
- `DATABASE_ECHO`: Enable SQL logging when true.
- `TEST_DATABASE_URL`: Separate connection string for tests.

### Redis & Celery

- `REDIS_URL`: Primary Redis instance for caching.
- `REDIS_PASSWORD`: Optional password for Redis.
- `REDIS_MAX_CONNECTIONS`: Max Redis connection pool.
- `CELERY_BROKER_URL`: Redis broker for Celery workers.
- `CELERY_RESULT_BACKEND`: Result backend for Celery.
- `CELERY_TASK_TIME_LIMIT`: Per-task execution limit (seconds).
- `CELERY_WORKER_PREFETCH_MULTIPLIER`: Worker prefetch behaviour.
- `FLOWER_PORT`: Flower monitoring web UI port.

### Reddit API

- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`: OAuth credentials.
- `REDDIT_USERNAME`, `REDDIT_PASSWORD`: Script application credentials.
- `REDDIT_RATE_LIMIT_CALLS`, `REDDIT_RATE_LIMIT_PERIOD`: Rate limit configuration.

### AWS / Object Storage

- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`: AWS credentials.
- `AWS_S3_BUCKET`: Bucket used for persisted artifacts.
- `S3_RAW_PREFIX`, `S3_MODELS_PREFIX`, `S3_EXPORTS_PREFIX`: Folder prefixes.

### Machine Learning

- `PRIMARY_MODEL`: Hugging Face model id used for primary sentiment analysis (`cardiffnlp/twitter-roberta-base-topic-sentiment-latest` by default).
- `FALLBACK_SERVICE`: Label used when Azure Opinion Mining provides the sentiment result.
- `CONFIDENCE_THRESHOLD`: Minimum primary-model confidence before triggering Azure fallback.
- `SENTIMENT_MIN_CONF`, `SENTIMENT_MIN_MARGIN`: Overrideable Hugging Face confidence and margin thresholds before fallback.
- `FALLBACK_ENABLED`: Toggle to disable Azure fallback entirely when set to `false`.
- `AZURE_TEXT_ANALYTICS_ENDPOINT`, `AZURE_TEXT_ANALYTICS_KEY`: Credentials for Azure Text Analytics Opinion Mining (stored in secret manager in production).
- `MODEL_PATH`, `MODEL_VERSION`: Legacy model binary metadata retained for archival workflows.
- `MODEL_DEVICE`: Legacy inference device flag (`cuda` or `cpu`).
- `BATCH_SIZE`, `MAX_SEQUENCE_LENGTH`: Inference/batching parameters.
- `ML_INFERENCE_URL`, `ML_TIMEOUT_SECONDS`: Legacy external inference endpoint and timeout.
- `SPACY_MODEL_NAME`: spaCy pipeline used for entity linking.
- `THREAD_ARCHIVE_IDLE_MINUTES`: Minutes of inactivity before automatically archiving threads.
- Thresholds: `SENTIMENT_THRESHOLD`, `SARCASM_THRESHOLD`, `TOXICITY_THRESHOLD`.

### LLM Configuration (New)

- `LLM_MODEL`: LLM model name or endpoint for sentiment/attitude/emotion/sarcasm analysis.
- `LLM_ENDPOINT`: API endpoint URL for LLM inference service (if using external API).
- `CONFIDENCE_THRESHOLD`: Minimum confidence score for LLM predictions (default 0.75).
- `SARCASM_THRESHOLD`: Sarcasm probability threshold for labeling as sarcastic (default 0.5).
- `WEIGHTING_MODE`: Mode for upvote weighting (`linear`, `logarithmic`, `sqrt`; default `linear`).
- `WEIGHT_CAP`: Maximum upvote weight cap to prevent outlier dominance (default 200).

### Hugging Face & OpenAI Tokens

- `HUGGINGFACE_ACCESS_TOKEN`, `HF_TOKEN`, `HUGGINGFACE_HUB_TOKEN`: Access tokens forwarded to Hugging Face downloads (pipeline also honours `HF_TOKEN` for local CLI parity).
- `HF_HOME`: Explicit cache directory for Hugging Face model artifacts (defaults to `.hf_cache`).
- `OPENAI_API_KEY`: Token for optional OpenAI integrations.

### Auth0

- `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `AUTH0_AUDIENCE`, `AUTH0_ALGORITHM`: Authentication configuration.

### Integrations

- `SENDGRID_API_KEY`, `FROM_EMAIL`, `FROM_NAME`: Transactional email.
- `SLACK_WEBHOOK_URL`, `SLACK_CHANNEL`, `SLACK_BOT_TOKEN`: Slack alerts.

### Monitoring

- `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`: Error reporting.
- `DATADOG_API_KEY`, `DATADOG_APP_KEY`, `DATADOG_SERVICE`, `DATADOG_ENV`: Metrics ingestion.
- `LOG_LEVEL`, `LOG_FORMAT`: Structured logging.

### Feature Flags

- `ENABLE_REAL_TIME_UPDATES`, `ENABLE_WEBSOCKET`, `ENABLE_ALERTS`, `ENABLE_BACKFILL`, `ENABLE_BRIGADE_DETECTION`, `ENABLE_BOT_DETECTION`.

### Limits & Retention

- `API_RATE_LIMIT`, `API_RATE_LIMIT_PERIOD`: Request throttling.
- `MAX_CONCURRENT_THREADS`: Max simultaneous Reddit threads to analyze.
- `RAW_COMMENT_RETENTION`, `AGGREGATE_RETENTION`, `CACHE_TTL_THREAD`, `CACHE_TTL_AGGREGATE`: Retention policies.

### Security

- `ALLOWED_UPLOAD_EXTENSIONS`, `MAX_UPLOAD_SIZE`: Upload restraints.
- `CORS_MAX_AGE`: CORS preflight cache lifetime.
- `SESSION_TIMEOUT`: Web session lifetime in seconds.
- `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AUTH0_CLIENT_ID`, `AUTH0_ALGORITHMS`: Backend Auth0 configuration (JWT issuer, API audience, optional custom algorithm list).

### Testing & Tooling

- `PYTEST_WORKERS`, `COVERAGE_THRESHOLD`: Testing defaults.
- `ENABLE_DEBUG_TOOLBAR`, `ENABLE_SWAGGER_UI`, `ENABLE_REDOC`: Development tooling toggles.

### Frontend

- `VITE_API_URL`: Base REST API URL.
- `VITE_WS_URL`: WebSocket URL.
- `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID`, `VITE_AUTH0_AUDIENCE`: Auth0 config shared with client.

### Deployment

- `DEPLOYMENT_ENV`, `VERSION`, `BUILD_NUMBER`, `GIT_COMMIT`: Build metadata.

### Optional

- `WANDB_API_KEY`, `WANDB_PROJECT`, `WANDB_ENTITY`: Weights & Biases.
- `K8S_NAMESPACE`, `K8S_SERVICE_NAME`, `K8S_REPLICA_COUNT`: Kubernetes hints.
- `CUSTOM_CAST_DICTIONARY_URL`, `CUSTOM_SLANG_LEXICON_URL`, `TIMEZONE`: Customization.
