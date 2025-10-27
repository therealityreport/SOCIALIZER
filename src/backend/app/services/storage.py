from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class S3Storage:
    """Lightweight helper around boto3 for storing JSON artefacts."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.bucket = (self.settings.aws_s3_bucket or "").strip()
        self.default_prefix = (self.settings.s3_raw_prefix or "raw/").strip("/")

        session = boto3.session.Session(
            aws_access_key_id=self.settings.aws_access_key_id or None,
            aws_secret_access_key=self.settings.aws_secret_access_key or None,
            region_name=self.settings.aws_region or None,
        )
        self.client = session.client("s3")

    def put_json(self, key: str, payload: Any) -> str | None:
        """Serialize payload to JSON and upload it to S3. Returns the object key."""
        if not self.bucket:
            logger.warning("Skipping S3 upload because AWS_S3_BUCKET is not configured.")
            return None

        object_key = self._normalize_key(key)
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=body,
                ContentType="application/json",
            )
        except (BotoCoreError, ClientError) as exc:
            logger.error("Failed to upload object to S3 bucket=%s key=%s: %s", self.bucket, object_key, exc)
            raise

        return object_key

    def _normalize_key(self, key: str) -> str:
        key = key.strip("/")
        prefix = self.default_prefix
        if prefix:
            return f"{prefix}/{key}"
        return key


@lru_cache(maxsize=1)
def get_s3_storage() -> S3Storage:
    return S3Storage()
