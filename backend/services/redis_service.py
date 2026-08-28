"""Redis service for connection pooling, locks, and rate limiting."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as redis
from redis.exceptions import LockError

from backend.config import settings

logger = logging.getLogger(__name__)

# Global redis pool
_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Get the global redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the global redis client."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


@asynccontextmanager
async def acquire_lock(key: str, timeout: int = 10, user_id: str | None = None) -> AsyncGenerator[bool, None]:
    """
    Acquire a distributed lock.
    Yields True if lock acquired, otherwise yields False.
    Auto-releases upon exit if it was acquired.
    """
    client = get_redis_client()
    lock_name = f"lock:{key}"
    if user_id:
        lock_name = f"lock:{user_id}:{key}"

    # blocking_timeout=0 means non-blocking
    lock = client.lock(name=lock_name, timeout=timeout)
    acquired = await lock.acquire(blocking_timeout=0)

    try:
        yield acquired
    finally:
        if acquired:
            try:
                await lock.release()
            except LockError:
                # Lock might have expired already
                logger.warning(f"Lock {lock_name} already expired or released.")


async def check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """
    Simple counter-based rate limit.
    Returns True if allowed, False if exceeded.
    """
    client = get_redis_client()
    current = await client.get(key)
    if current is not None and int(current) >= limit:
        return False

    async with client.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        # expire if not set yet (nx=True for expire supported in newer redis, fallback to set if needed)
        # using expire directly since nx=True might not be in older redis
        # the standard pattern is incr, and if it's 1, set expire.
        pipe.ttl(key)
        results = await pipe.execute()

        # If the TTL is -1 (no expiration), set it
        if results[1] == -1:
            await client.expire(key, window_seconds)

    return True
