from __future__ import annotations

import hashlib
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def hash_username(username: str | None) -> str | None:
    """Return a salted hash of the username for privacy."""
    if not username:
        return None

    sanitized = username.strip()
    if not sanitized or sanitized == "[deleted]":
        return None

    settings = get_settings()
    salt = settings.author_hash_salt.strip()
    if not salt:
        logger.debug("AUTHOR_HASH_SALT is not configured; skipping username hashing.")
        return None

    digest = hashlib.sha256()
    digest.update(salt.encode("utf-8"))
    digest.update(sanitized.lower().encode("utf-8"))
    return digest.hexdigest()
