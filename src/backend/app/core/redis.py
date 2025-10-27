from __future__ import annotations

from functools import lru_cache

import redis
from redis import Redis

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    settings = get_settings()
    return redis.Redis.from_url(
        settings.redis_url,
        max_connections=settings.redis_max_connections,
        decode_responses=False,
    )
