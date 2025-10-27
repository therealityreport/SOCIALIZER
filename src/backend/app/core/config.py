from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, List

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _discover_env_files() -> tuple[str, ...]:
    """Determine which env files should be loaded."""
    files: list[str] = []

    custom_env = os.getenv("ENV_FILE")
    if custom_env and Path(custom_env).is_file():
        files.append(custom_env)

    project_root = Path(__file__).resolve().parents[2]
    default_env = project_root / "config" / "environments" / "development.env"
    if default_env.is_file():
        files.append(str(default_env))

    dot_env = project_root / ".env"
    if dot_env.is_file():
        files.append(str(dot_env))

    return tuple(dict.fromkeys(files))  # Preserve order, remove duplicates


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_discover_env_files(),
        env_file_encoding="utf-8",
        extra="allow",
        protected_namespaces=("settings_",),
    )

    env: str = Field(default="development", alias="ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    secret_key: str = Field(default="changeme-please-change", alias="SECRET_KEY")
    api_version: str = Field(default="v1", alias="API_VERSION")
    allowed_hosts: List[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"], alias="ALLOWED_HOSTS")
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173"], alias="CORS_ORIGINS")

    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    frontend_url: HttpUrl | None = Field(default=None, alias="FRONTEND_URL")
    enable_swagger_ui: bool = Field(default=True, alias="ENABLE_SWAGGER_UI")
    enable_redoc: bool = Field(default=True, alias="ENABLE_REDOC")

    database_url: str = Field(
        default="postgresql+psycopg://ltsr_user:ltsr_password@localhost:5432/ltsr_db",
        alias="DATABASE_URL",
    )
    database_pool_size: int = Field(default=20, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, alias="DATABASE_MAX_OVERFLOW")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_max_connections: int = Field(default=50, alias="REDIS_MAX_CONNECTIONS")

    celery_broker_url: str = Field(default="redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/0", alias="CELERY_RESULT_BACKEND")
    celery_task_time_limit: int = Field(default=1800, alias="CELERY_TASK_TIME_LIMIT")
    celery_worker_prefetch_multiplier: int = Field(default=1, alias="CELERY_WORKER_PREFETCH_MULTIPLIER")
    flower_port: int = Field(default=5555, alias="FLOWER_PORT")

    reddit_client_id: str = Field(default="", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="SOCIALIZER/1.0 (by u/unknown)", alias="REDDIT_USER_AGENT")
    reddit_username: str = Field(default="", alias="REDDIT_USERNAME")
    reddit_password: str = Field(default="", alias="REDDIT_PASSWORD")
    reddit_rate_limit_calls: int = Field(default=5000, alias="REDDIT_RATE_LIMIT_CALLS")
    reddit_rate_limit_period: int = Field(default=60, alias="REDDIT_RATE_LIMIT_PERIOD")

    aws_access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_s3_bucket: str = Field(default="", alias="AWS_S3_BUCKET")
    s3_raw_prefix: str = Field(default="raw/", alias="S3_RAW_PREFIX")
    s3_models_prefix: str = Field(default="models/", alias="S3_MODELS_PREFIX")
    s3_exports_prefix: str = Field(default="exports/", alias="S3_EXPORTS_PREFIX")

    slack_webhook_url: str | None = Field(default=None, alias="SLACK_WEBHOOK_URL")
    slack_channel: str | None = Field(default=None, alias="SLACK_CHANNEL")
    sendgrid_api_key: str | None = Field(default=None, alias="SENDGRID_API_KEY")
    sendgrid_from_email: str | None = Field(default=None, alias="FROM_EMAIL")
    sendgrid_from_name: str | None = Field(default=None, alias="FROM_NAME")

    ml_inference_url: str = Field(default="http://localhost:8500/predict", alias="ML_INFERENCE_URL")
    ml_batch_size: int = Field(default=32, alias="BATCH_SIZE")
    ml_timeout_seconds: int = Field(default=30, alias="ML_TIMEOUT_SECONDS")
    sentiment_threshold: float = Field(default=0.5, alias="SENTIMENT_THRESHOLD")
    sarcasm_threshold: float = Field(default=0.6, alias="SARCASM_THRESHOLD")
    toxicity_threshold: float = Field(default=0.7, alias="TOXICITY_THRESHOLD")
    model_version: str = Field(default="unknown", alias="MODEL_VERSION")
    primary_model: str = Field(
        default="cardiffnlp/twitter-roberta-base-topic-sentiment-latest",
        alias="PRIMARY_MODEL",
    )
    fallback_service: str = Field(
        default="Azure Text Analytics Opinion Mining",
        alias="FALLBACK_SERVICE",
    )
    confidence_threshold: float = Field(default=0.75, alias="CONFIDENCE_THRESHOLD")
    sentiment_min_conf: float = Field(default=0.55, alias="SENTIMENT_MIN_CONF")
    sentiment_min_margin: float = Field(default=0.10, alias="SENTIMENT_MIN_MARGIN")
    fallback_enabled: bool = Field(default=True, alias="FALLBACK_ENABLED")
    huggingface_access_token: str | None = Field(default=None, alias="HUGGINGFACE_ACCESS_TOKEN")
    huggingface_api_key: str | None = Field(default=None, alias="HUGGINGFACE_API_KEY")
    azure_text_analytics_endpoint: str | None = Field(default=None, alias="AZURE_TEXT_ANALYTICS_ENDPOINT")
    azure_text_analytics_key: str | None = Field(default=None, alias="AZURE_TEXT_ANALYTICS_KEY")
    spacy_model_name: str = Field(default="en_core_web_lg", alias="SPACY_MODEL_NAME")
    thread_archive_idle_minutes: int = Field(default=180, alias="THREAD_ARCHIVE_IDLE_MINUTES")
    auth0_domain: str | None = Field(default=None, alias="AUTH0_DOMAIN")
    auth0_audience: str | None = Field(default=None, alias="AUTH0_AUDIENCE")
    auth0_client_id: str | None = Field(default=None, alias="AUTH0_CLIENT_ID")
    auth0_algorithms: List[str] = Field(default_factory=lambda: ["RS256"], alias="AUTH0_ALGORITHMS")

    author_hash_salt: str = Field(default="", alias="AUTHOR_HASH_SALT")
    timezone: str = Field(default="US/Eastern", alias="TIMEZONE")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    secrets_provider: str = Field(default="env", alias="SECRETS_PROVIDER")
    secrets_prefix: str = Field(default="", alias="SECRETS_PREFIX")
    secrets_aws_prefix: str = Field(default="socializer/", alias="SECRETS_AWS_PREFIX")

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _parse_allowed_hosts(cls, value: Any) -> List[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in stripped.split(",") if item.strip()]
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> List[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in stripped.split(",") if item.strip()]
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @field_validator("auth0_algorithms", mode="before")
    @classmethod
    def _ensure_list(cls, value: Any) -> List[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return ["RS256"]

    @field_validator("secrets_provider", mode="before")
    @classmethod
    def _normalize_provider(cls, value: Any) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
        return "env"

    @property
    def auth0_issuer(self) -> str | None:
        if not self.auth0_domain:
            return None
        domain = self.auth0_domain.strip().rstrip("/")
        if not domain:
            return None
        if not domain.startswith("http://") and not domain.startswith("https://"):
            domain = f"https://{domain}"
        return f"{domain}/"

    @property
    def huggingface_token(self) -> str | None:
        return self.huggingface_access_token or self.huggingface_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]
