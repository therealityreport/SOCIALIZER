from __future__ import annotations

import base64
import logging
import os
from functools import lru_cache
from typing import Any

try:  # pragma: no cover - boto3 optional in some environments
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover
    boto3 = None
    BotoCoreError = ClientError = Exception  # type: ignore[assignment]

from fastapi import HTTPException, status

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class SecretsManager:
    """Pluggable secret resolution with environment and AWS backends."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider = settings.secrets_provider
        self._cache: dict[str, str] = {}
        self._aws_client = None

        if self.provider == "aws":
            if boto3 is None:
                raise RuntimeError("boto3 is required for AWS Secrets Manager integration.")
            self._aws_client = boto3.client("secretsmanager", region_name=settings.aws_region)

    def get_secret(self, name: str, default: str | None = None, *, use_cache: bool = True) -> str | None:
        if not name:
            raise ValueError("Secret name must be provided.")

        cache_key = f"{self.provider}:{name}"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        if self.provider == "aws":
            value = self._get_from_aws(name, default=default)
        else:
            value = self._get_from_env(name, default=default)

        if use_cache and value is not None:
            self._cache[cache_key] = value
        return value

    def require_secret(self, name: str) -> str:
        value = self.get_secret(name)
        if value is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Missing secret: {name}")
        return value

    def _env_key(self, name: str) -> str:
        prefix = self.settings.secrets_prefix or ""
        return f"{prefix}{name}".upper()

    def _get_from_env(self, name: str, default: str | None = None) -> str | None:
        env_key = self._env_key(name)
        return os.getenv(env_key, default)

    def _aws_secret_id(self, name: str) -> str:
        prefix = self.settings.secrets_aws_prefix or ""
        if prefix and not prefix.endswith("/"):
            prefix = f"{prefix}/"
        return f"{prefix}{name}"

    def _get_from_aws(self, name: str, default: str | None = None) -> str | None:
        if self._aws_client is None:
            raise RuntimeError("AWS Secrets Manager client not initialized.")

        secret_id = self._aws_secret_id(name)
        try:
            response = self._aws_client.get_secret_value(SecretId=secret_id)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                logger.warning("AWS secret %s not found; falling back to default.", secret_id)
                return default
            logger.error("Error fetching secret %s: %s", secret_id, exc)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Secrets service failure.") from exc
        except BotoCoreError as exc:  # pragma: no cover - network errors
            logger.error("AWS Secrets Manager error for %s: %s", secret_id, exc)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Secrets service failure.") from exc

        if "SecretString" in response and response["SecretString"] is not None:
            return response["SecretString"]

        binary_secret = response.get("SecretBinary")
        if binary_secret is None:
            return default

        decoded = base64.b64decode(binary_secret)
        return decoded.decode("utf-8")


@lru_cache(maxsize=1)
def get_secrets_manager() -> SecretsManager:
    settings = get_settings()
    return SecretsManager(settings)


def resolve_secret(name: str, default: str | None = None) -> str | None:
    manager = get_secrets_manager()
    return manager.get_secret(name, default=default)
