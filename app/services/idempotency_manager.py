"""
Empire v7.3 - Idempotency Manager
Data Persistence P0 Fix - Prevent duplicate processing on retries

The Idempotency Manager ensures operations execute only once by:
1. Caching operation results by idempotency key
2. Returning cached results on retry
3. Supporting both Redis (fast) and Supabase (durable) backends

Usage:
    @router.post("/messages")
    async def create_message(
        request: CreateMessageRequest,
        idempotency_key: str = Header(..., alias="Idempotency-Key")
    ):
        return await idempotency_mgr.execute_idempotent(
            idempotency_key=idempotency_key,
            operation_fn=service.create_message,
            **request.dict()
        )
"""

import hashlib
import json
import time
import asyncio
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, Optional, Union

import structlog
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge

logger = structlog.get_logger(__name__)


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

IDEMPOTENCY_CACHE_HITS = Counter(
    "empire_idempotency_cache_hits_total",
    "Total idempotency cache hits",
    ["operation"]
)

IDEMPOTENCY_CACHE_MISSES = Counter(
    "empire_idempotency_cache_misses_total",
    "Total idempotency cache misses",
    ["operation"]
)

IDEMPOTENCY_DUPLICATES_PREVENTED = Counter(
    "empire_idempotency_duplicates_prevented_total",
    "Total duplicate operations prevented",
    ["operation"]
)

IDEMPOTENCY_ENTRIES = Gauge(
    "empire_idempotency_entries_current",
    "Current number of idempotency entries"
)


# =============================================================================
# MODELS
# =============================================================================

class IdempotencyStatus(str, Enum):
    """Status of an idempotent operation"""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class IdempotencyEntry(BaseModel):
    """An idempotency cache entry"""
    key: str = Field(..., description="Idempotency key")
    operation: str = Field(..., description="Operation name")
    status: IdempotencyStatus = Field(default=IdempotencyStatus.IN_PROGRESS)
    result: Optional[Dict[str, Any]] = Field(None, description="Cached result")
    error: Optional[str] = Field(None, description="Error if failed")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="When the entry expires")
    request_hash: Optional[str] = Field(None, description="Hash of the request for verification")

    class Config:
        json_schema_extra = {
            "example": {
                "key": "user-123-create-message-abc",
                "operation": "create_message",
                "status": "completed",
                "result": {"id": "msg-456", "content": "Hello"},
                "created_at": "2025-01-19T12:00:00Z",
                "expires_at": "2025-01-20T12:00:00Z"
            }
        }


# =============================================================================
# IDEMPOTENCY MANAGER
# =============================================================================

class IdempotencyManager:
    """
    Prevents duplicate processing of operations.

    Features:
    - Redis-backed fast cache (primary)
    - Supabase-backed durable cache (fallback)
    - Request hash verification
    - Configurable TTL per operation
    - In-flight request locking

    Usage:
        mgr = IdempotencyManager(redis_client, supabase_client)
        result = await mgr.execute_idempotent(
            idempotency_key="user-123-request-abc",
            operation_fn=create_resource,
            operation="create_resource",
            **kwargs
        )
    """

    def __init__(
        self,
        redis_client=None,
        supabase_client=None,
        default_ttl_hours: int = 24
    ):
        """
        Initialize the idempotency manager.

        Args:
            redis_client: Redis client for fast cache
            supabase_client: Supabase client for durable cache
            default_ttl_hours: Default time-to-live for entries
        """
        self.redis = redis_client
        self.supabase = supabase_client
        self.default_ttl = timedelta(hours=default_ttl_hours)

        # In-memory lock for in-flight requests
        self._in_flight: Dict[str, float] = {}

        logger.info(
            "Idempotency manager initialized",
            redis_enabled=redis_client is not None,
            supabase_enabled=supabase_client is not None,
            default_ttl_hours=default_ttl_hours
        )

    def _hash_request(self, data: Dict[str, Any]) -> str:
        """Generate a hash of request data for verification"""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def _make_redis_key(self, idempotency_key: str) -> str:
        """Create Redis key for idempotency entry"""
        return f"idempotency:{idempotency_key}"

    async def _get_from_redis(self, key: str) -> Optional[IdempotencyEntry]:
        """Get entry from Redis cache"""
        if not self.redis:
            return None

        try:
            redis_key = self._make_redis_key(key)
            # Use asyncio.to_thread for sync Redis client
            data = await asyncio.to_thread(self.redis.get, redis_key)

            if data:
                entry_dict = json.loads(data)
                return IdempotencyEntry(**entry_dict)

            return None

        except Exception as e:
            logger.warning("Redis idempotency lookup failed", key=key, error=str(e))
            return None

    async def _set_in_redis(
        self,
        entry: IdempotencyEntry,
        ttl_seconds: Optional[int] = None
    ):
        """Store entry in Redis cache"""
        if not self.redis:
            return

        try:
            redis_key = self._make_redis_key(entry.key)
            ttl = ttl_seconds or int(self.default_ttl.total_seconds())

            # Use asyncio.to_thread for sync Redis client
            await asyncio.to_thread(
                self.redis.setex,
                redis_key,
                ttl,
                entry.model_dump_json()
            )

        except Exception as e:
            logger.warning("Redis idempotency store failed", key=entry.key, error=str(e))

    async def _get_from_supabase(self, key: str) -> Optional[IdempotencyEntry]:
        """Get entry from Supabase (durable storage)"""
        if not self.supabase:
            return None

        try:
            result = self.supabase.table("idempotency_keys").select("*").eq(
                "key", key
            ).gt(
                "expires_at", datetime.now(timezone.utc).isoformat()
            ).execute()

            if result.data:
                row = result.data[0]
                return IdempotencyEntry(
                    key=row["key"],
                    operation=row["operation"],
                    status=IdempotencyStatus(row["status"]),
                    result=row.get("result"),
                    error=row.get("error"),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    expires_at=datetime.fromisoformat(row["expires_at"]) if row.get("expires_at") else None,
                    request_hash=row.get("request_hash")
                )

            return None

        except Exception as e:
            logger.warning("Supabase idempotency lookup failed", key=key, error=str(e))
            return None

    async def _set_in_supabase(self, entry: IdempotencyEntry):
        """Store entry in Supabase (durable storage)"""
        if not self.supabase:
            return

        try:
            self.supabase.table("idempotency_keys").upsert({
                "key": entry.key,
                "operation": entry.operation,
                "status": entry.status.value,
                "result": entry.result,
                "error": entry.error,
                "created_at": entry.created_at.isoformat(),
                "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                "request_hash": entry.request_hash
            }).execute()

        except Exception as e:
            logger.warning("Supabase idempotency store failed", key=entry.key, error=str(e))

    async def get_cached_result(
        self,
        idempotency_key: str
    ) -> Optional[IdempotencyEntry]:
        """
        Get cached result for an idempotency key.

        Checks Redis first, falls back to Supabase.

        Args:
            idempotency_key: The idempotency key

        Returns:
            Cached entry if found and not expired
        """
        # Try Redis first (fast)
        entry = await self._get_from_redis(idempotency_key)
        if entry:
            return entry

        # Fall back to Supabase (durable)
        return await self._get_from_supabase(idempotency_key)

    async def cache_result(
        self,
        idempotency_key: str,
        operation: str,
        result: Any,
        request_hash: Optional[str] = None,
        ttl_hours: Optional[int] = None
    ):
        """
        Cache a successful result.

        Args:
            idempotency_key: The idempotency key
            operation: Operation name
            result: Result to cache
            request_hash: Hash of request for verification
            ttl_hours: Custom TTL in hours
        """
        ttl = timedelta(hours=ttl_hours) if ttl_hours else self.default_ttl

        entry = IdempotencyEntry(
            key=idempotency_key,
            operation=operation,
            status=IdempotencyStatus.COMPLETED,
            result={"data": result},  # Always wrap under "data" for consistent retrieval
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + ttl,
            request_hash=request_hash
        )

        # Store in both caches
        await self._set_in_redis(entry, int(ttl.total_seconds()))
        await self._set_in_supabase(entry)

        IDEMPOTENCY_ENTRIES.inc()

        logger.debug(
            "Idempotency result cached",
            key=idempotency_key,
            operation=operation
        )

    async def cache_error(
        self,
        idempotency_key: str,
        operation: str,
        error: str,
        request_hash: Optional[str] = None
    ):
        """
        Cache a failed result (to prevent immediate retry).

        Args:
            idempotency_key: The idempotency key
            operation: Operation name
            error: Error message
            request_hash: Hash of request for verification
        """
        # Use shorter TTL for errors (5 minutes) to allow retry
        ttl = timedelta(minutes=5)

        entry = IdempotencyEntry(
            key=idempotency_key,
            operation=operation,
            status=IdempotencyStatus.FAILED,
            error=error,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + ttl,
            request_hash=request_hash
        )

        # Only store in Redis for errors (short-lived)
        await self._set_in_redis(entry, int(ttl.total_seconds()))

    async def mark_in_progress(
        self,
        idempotency_key: str,
        operation: str,
        request_hash: Optional[str] = None
    ):
        """
        Mark an operation as in-progress.

        Used to prevent concurrent duplicate requests.

        Args:
            idempotency_key: The idempotency key
            operation: Operation name
            request_hash: Hash of request for verification
        """
        entry = IdempotencyEntry(
            key=idempotency_key,
            operation=operation,
            status=IdempotencyStatus.IN_PROGRESS,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),  # 5 min lock
            request_hash=request_hash
        )

        await self._set_in_redis(entry, 300)  # 5 minute lock
        self._in_flight[idempotency_key] = time.time()

    async def execute_idempotent(
        self,
        idempotency_key: str,
        operation_fn: Callable[..., Coroutine[Any, Any, Any]],
        operation: str = "unknown",
        verify_request: bool = True,
        **kwargs
    ) -> Any:
        """
        Execute an operation idempotently.

        If the operation was already executed with this key, returns cached result.
        Otherwise executes the operation and caches the result.

        Args:
            idempotency_key: Unique key for this operation
            operation_fn: Async function to execute
            operation: Operation name for metrics
            verify_request: Whether to verify request hash matches
            **kwargs: Arguments to pass to operation_fn

        Returns:
            Result from operation_fn or cached result

        Raises:
            ValueError: If request hash doesn't match (when verify_request=True)
        """
        request_hash = self._hash_request(kwargs) if verify_request else None

        # Check for cached result
        cached = await self.get_cached_result(idempotency_key)

        if cached:
            # Verify request hash if enabled
            if verify_request and cached.request_hash and cached.request_hash != request_hash:
                raise ValueError(
                    f"Request body does not match original request for idempotency key: {idempotency_key}"
                )

            if cached.status == IdempotencyStatus.COMPLETED:
                IDEMPOTENCY_CACHE_HITS.labels(operation=operation).inc()
                IDEMPOTENCY_DUPLICATES_PREVENTED.labels(operation=operation).inc()

                logger.info(
                    "Returning cached idempotent result",
                    key=idempotency_key,
                    operation=operation
                )

                return cached.result.get("data") if cached.result else None

            elif cached.status == IdempotencyStatus.IN_PROGRESS:
                # Request is in flight - wait briefly and check again
                await asyncio.sleep(1)

                # Check again
                cached = await self.get_cached_result(idempotency_key)
                if cached and cached.status == IdempotencyStatus.COMPLETED:
                    return cached.result.get("data") if cached.result else None

                # Still in progress - raise error
                raise ValueError(
                    f"Operation already in progress for idempotency key: {idempotency_key}"
                )

            elif cached.status == IdempotencyStatus.FAILED:
                # Previous attempt failed - allow retry
                logger.info(
                    "Previous attempt failed, allowing retry",
                    key=idempotency_key,
                    operation=operation
                )

        # Mark as in-progress
        await self.mark_in_progress(idempotency_key, operation, request_hash)
        IDEMPOTENCY_CACHE_MISSES.labels(operation=operation).inc()

        try:
            # Execute the operation
            result = await operation_fn(**kwargs)

            # Cache successful result
            await self.cache_result(
                idempotency_key,
                operation,
                result,
                request_hash
            )

            # Clean up in-flight tracking
            self._in_flight.pop(idempotency_key, None)

            return result

        except Exception as e:
            # Cache error (short TTL)
            await self.cache_error(
                idempotency_key,
                operation,
                str(e),
                request_hash
            )

            # Clean up in-flight tracking
            self._in_flight.pop(idempotency_key, None)

            raise

    async def cleanup_expired(self) -> int:
        """
        Clean up expired idempotency entries from Supabase.

        Returns:
            Number of entries cleaned up
        """
        if not self.supabase:
            return 0

        try:
            result = self.supabase.table("idempotency_keys").delete().lt(
                "expires_at", datetime.now(timezone.utc).isoformat()
            ).execute()

            count = len(result.data) if result.data else 0
            logger.info("Cleaned up expired idempotency entries", count=count)
            return count

        except Exception as e:
            logger.error("Failed to cleanup idempotency entries", error=str(e))
            return 0


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_idempotency_manager: Optional[IdempotencyManager] = None


def get_idempotency_manager() -> Optional[IdempotencyManager]:
    """Get the global idempotency manager instance"""
    return _idempotency_manager


def initialize_idempotency_manager(
    redis_client=None,
    supabase_client=None
) -> IdempotencyManager:
    """Initialize the global idempotency manager"""
    global _idempotency_manager
    _idempotency_manager = IdempotencyManager(redis_client, supabase_client)
    return _idempotency_manager
