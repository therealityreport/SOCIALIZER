from __future__ import annotations

import logging
import threading
import time

import redis
from redis import Redis

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    """Distributed rate limiter backed by Redis with local fallback."""

    def __init__(self, redis_client: Redis, max_calls: int, period: int, namespace: str = "reddit:rate") -> None:
        self.redis = redis_client
        self.max_calls = max(1, max_calls)
        self.period = max(1, period)
        self.namespace = namespace.rstrip(":")

        self.counter_prefix = f"{self.namespace}:counter"
        self.block_key = f"{self.namespace}:blocked_until"

        self._redis_available = True
        self._lock = threading.Lock()
        self._local_allowance = float(self.max_calls)
        self._local_last_check = time.monotonic()
        self._local_block_until = 0.0

    def acquire(self) -> None:
        """Block until a token is available."""
        if not self._redis_available:
            self._acquire_local()
            return

        try:
            self._respect_distributed_block()
            self._acquire_distributed()
        except redis.RedisError as exc:
            logger.warning("Redis rate limiter unavailable, falling back to local limiter: %s", exc)
            self._redis_available = False
            self._acquire_local()

    def block_for(self, seconds: float) -> None:
        """Inform the limiter that the upstream is rate limited for a period of time."""
        wait_for = max(int(seconds), 0)
        if wait_for <= 0:
            return

        self._set_local_block(wait_for)

        if not self._redis_available:
            return

        try:
            blocked_until = int(time.time()) + wait_for
            self.redis.set(self.block_key, blocked_until, ex=wait_for)
        except redis.RedisError as exc:
            logger.debug("Unable to persist distributed block window: %s", exc)
            self._redis_available = False

    def _acquire_distributed(self) -> None:
        while True:
            window = int(time.time()) // self.period
            key = f"{self.counter_prefix}:{window}"

            wait_for = 0.0
            with self.redis.pipeline() as pipe:
                try:
                    pipe.watch(key)
                    current_raw = pipe.get(key)
                    current = int(current_raw) if current_raw else 0

                    if current < self.max_calls:
                        pipe.multi()
                        pipe.incr(key, 1)
                        pipe.expire(key, self.period + 1)
                        pipe.execute()
                        return

                    ttl = pipe.ttl(key)
                    wait_for = float(ttl if ttl and ttl > 0 else self.period)
                except redis.WatchError:
                    continue

            if wait_for > 0:
                time.sleep(wait_for)

    def _respect_distributed_block(self) -> None:
        try:
            blocked_raw = self.redis.get(self.block_key)
        except redis.RedisError as exc:
            logger.debug("Failed to read distributed block value: %s", exc)
            self._redis_available = False
            self._wait_local_block()
            return

        if not blocked_raw:
            self._wait_local_block()
            return

        blocked_until = float(int(blocked_raw))
        now = time.time()
        wait_for = blocked_until - now
        if wait_for > 0:
            logger.debug("Rate limiter waiting for distributed block to clear (%.2fs)", wait_for)
            time.sleep(wait_for)

        self._wait_local_block()

    def _set_local_block(self, seconds: int) -> None:
        unblock_at = time.monotonic() + seconds
        with self._lock:
            self._local_block_until = max(self._local_block_until, unblock_at)

    def _wait_local_block(self) -> None:
        now = time.monotonic()
        with self._lock:
            if now >= self._local_block_until:
                return
            wait_for = self._local_block_until - now
        logger.debug("Rate limiter waiting for local block to clear (%.2fs)", wait_for)
        time.sleep(wait_for)

    def _acquire_local(self) -> None:
        while True:
            wait_for = 0.0
            with self._lock:
                now = time.monotonic()
                if now < self._local_block_until:
                    wait_for = self._local_block_until - now
                else:
                    time_passed = now - self._local_last_check
                    self._local_last_check = now
                    self._local_allowance += time_passed * (self.max_calls / self.period)
                    if self._local_allowance > self.max_calls:
                        self._local_allowance = float(self.max_calls)

                    if self._local_allowance >= 1.0:
                        self._local_allowance -= 1.0
                        return

                    wait_for = (1.0 - self._local_allowance) * (self.period / self.max_calls)

            if wait_for > 0:
                time.sleep(wait_for)
