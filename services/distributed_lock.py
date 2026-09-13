"""Distributed locking and leader lease management.

Supports Redis (preferred) with automatic fallback to PostgreSQL advisory locks.
Coordinates background workers and prevents duplicate work across multiple
worker processes or instances.
"""
import asyncio
import hashlib
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Any
from sqlalchemy import text
from db import get_db_session

logger = logging.getLogger(__name__)


def _key_to_int64(key: str) -> int:
    """Hash a string key to a signed 64-bit integer for PostgreSQL advisory locks."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


class DistributedLock:
    """Distributed lock / lease supporting Redis with Postgres advisory lock fallback."""

    def __init__(
        self,
        key: str,
        ttl_seconds: int = 60,
        redis_client=None,
        session=None,
    ):
        self.key = key
        self.ttl_seconds = ttl_seconds
        self.token = str(uuid.uuid4())
        self._redis = redis_client
        self._session = session
        self._own_session = False
        self._ctx = None
        self._acquired_backend: str | None = None

    def _resolve_redis(self):
        if self._redis is not None:
            return self._redis
        try:
            from repositories.batstore_product import BatStoreProductRepository
            return getattr(BatStoreProductRepository, "_redis", None)
        except Exception:
            return None

    async def acquire(self) -> bool:
        """Attempt to acquire the distributed lock. Returns True if acquired, False otherwise."""
        redis = self._resolve_redis()

        # 1. Try Redis if available
        if redis is not None:
            try:
                res = await redis.set(self.key, self.token, nx=True, ex=self.ttl_seconds)
                if res:
                    self._acquired_backend = "redis"
                    return True
                # Redis key already held by another worker
                return False
            except Exception as e:
                logger.debug("Redis lock acquisition failed for key %s: %s (falling back to Postgres)", self.key, e)

        # 2. Fallback to PostgreSQL advisory lock
        try:
            lock_id = _key_to_int64(self.key)
            if self._session is None:
                ctx = get_db_session()
                self._session = await ctx.__aenter__()
                self._own_session = True
                self._ctx = ctx

            res = await self._session.execute(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": lock_id},
            )
            acquired = bool(res.scalar())
            if acquired:
                self._acquired_backend = "postgres"
                return True
            return False
        except Exception as e:
            logger.warning("Postgres advisory lock acquisition failed for key %s: %s", self.key, e)
            return False

    async def release(self) -> None:
        """Release the lock if acquired."""
        if not self._acquired_backend:
            return

        if self._acquired_backend == "redis":
            redis = self._resolve_redis()
            if redis is not None:
                try:
                    # Safe release script: deletes only if token matches
                    lua_release = """
                    if redis.call('get', KEYS[1]) == ARGV[1] then
                        return redis.call('del', KEYS[1])
                    else
                        return 0
                    end
                    """
                    await redis.eval(lua_release, 1, self.key, self.token)
                except Exception as e:
                    logger.debug("Error releasing Redis lock %s: %s", self.key, e)

        elif self._acquired_backend == "postgres":
            try:
                lock_id = _key_to_int64(self.key)
                if self._session is not None:
                    await self._session.execute(
                        text("SELECT pg_advisory_unlock(:lock_id)"),
                        {"lock_id": lock_id},
                    )
            except Exception as e:
                logger.debug("Error releasing Postgres advisory lock %s: %s", self.key, e)
            finally:
                if self._own_session and self._ctx is not None:
                    try:
                        await self._ctx.__aexit__(None, None, None)
                    except Exception:
                        pass
                    self._session = None

        self._acquired_backend = None

    async def __aenter__(self) -> bool:
        return await self.acquire()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.release()


@asynccontextmanager
async def leader_lease(
    job_name: str,
    ttl_seconds: int = 60,
    redis_client=None,
    session=None,
) -> AsyncIterator[bool]:
    """Leader lease context manager.
    Yields True if current worker holds the lease for this job, False otherwise.
    """
    lock_key = f"ghstore:leader:{job_name}"
    lock = DistributedLock(lock_key, ttl_seconds=ttl_seconds, redis_client=redis_client, session=session)
    acquired = await lock.acquire()
    try:
        yield acquired
    finally:
        if acquired:
            await lock.release()


@asynccontextmanager
async def order_lock(
    order_id: int,
    ttl_seconds: int = 60,
    redis_client=None,
    session=None,
) -> AsyncIterator[bool]:
    """Per-order distributed lock preventing concurrent fulfillment or polling of the same order."""
    lock_key = f"ghstore:lock:order:{order_id}"
    lock = DistributedLock(lock_key, ttl_seconds=ttl_seconds, redis_client=redis_client, session=session)
    acquired = await lock.acquire()
    try:
        yield acquired
    finally:
        if acquired:
            await lock.release()


@asynccontextmanager
async def sms_lock(
    activation_id: int | str,
    ttl_seconds: int = 60,
    redis_client=None,
    session=None,
) -> AsyncIterator[bool]:
    """Per-activation distributed lock preventing duplicate processing of the same SMS order."""
    lock_key = f"ghstore:lock:sms:{activation_id}"
    lock = DistributedLock(lock_key, ttl_seconds=ttl_seconds, redis_client=redis_client, session=session)
    acquired = await lock.acquire()
    try:
        yield acquired
    finally:
        if acquired:
            await lock.release()
