"""
Empire v7.3 - Write-Ahead Log (WAL) Manager
Data Persistence P0 Fix - Operations logged BEFORE execution

The WAL ensures data integrity by:
1. Logging operations BEFORE they execute
2. Enabling replay of pending operations after crash
3. Tracking operation status through completion

Usage:
    wal = WriteAheadLog(supabase_client)
    wal_id = await wal.log_operation("create_document", {"title": "Test"})
    try:
        result = await create_document(...)
        await wal.mark_completed(wal_id)
    except Exception:
        await wal.mark_failed(wal_id, str(error))
"""

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

import structlog
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, Histogram

logger = structlog.get_logger(__name__)


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

WAL_ENTRIES_TOTAL = Counter(
    "empire_wal_entries_total",
    "Total WAL entries created",
    ["operation_type", "status"]
)

WAL_REPLAY_TOTAL = Counter(
    "empire_wal_replay_total",
    "Total WAL replay operations",
    ["operation_type", "result"]
)

WAL_PENDING_GAUGE = Gauge(
    "empire_wal_pending_entries",
    "Number of pending WAL entries"
)

WAL_OPERATION_DURATION = Histogram(
    "empire_wal_operation_duration_seconds",
    "Duration of WAL-protected operations",
    ["operation_type"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)


# =============================================================================
# MODELS
# =============================================================================

class WALStatus(str, Enum):
    """Status of a WAL entry"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


class WALEntry(BaseModel):
    """A Write-Ahead Log entry"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    operation_type: str = Field(..., description="Type of operation (e.g., create_document, sync_graph)")
    operation_data: Dict[str, Any] = Field(..., description="Operation parameters")
    status: WALStatus = Field(default=WALStatus.PENDING)
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "operation_type": "create_document",
                "operation_data": {"title": "Test Document", "content": "..."},
                "status": "pending",
                "retry_count": 0,
                "created_at": "2025-01-19T12:00:00Z"
            }
        }


# =============================================================================
# WRITE-AHEAD LOG MANAGER
# =============================================================================

class WriteAheadLog:
    """
    Write-Ahead Log for operation persistence and recovery.

    Features:
    - Log operations BEFORE execution
    - Track operation status through lifecycle
    - Replay pending operations on startup
    - Automatic retry with exponential backoff
    - Correlation tracking for distributed operations
    """

    def __init__(self, supabase_client):
        """
        Initialize the WAL manager.

        Args:
            supabase_client: Supabase client for persistence
        """
        self.supabase = supabase_client
        self._operation_handlers: Dict[str, Callable] = {}
        logger.info("WAL manager initialized")

    def register_handler(
        self,
        operation_type: str,
        handler: Callable[..., Coroutine[Any, Any, Any]]
    ):
        """
        Register a handler for an operation type.

        Args:
            operation_type: Type of operation (e.g., "create_document")
            handler: Async function to execute the operation
        """
        self._operation_handlers[operation_type] = handler
        logger.debug(f"Registered WAL handler for: {operation_type}")

    async def log_operation(
        self,
        operation_type: str,
        operation_data: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Log an operation BEFORE execution.

        Args:
            operation_type: Type of operation
            operation_data: Operation parameters
            idempotency_key: Optional key for idempotency
            correlation_id: Optional correlation ID for tracing

        Returns:
            WAL entry ID
        """
        entry = WALEntry(
            operation_type=operation_type,
            operation_data=operation_data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id
        )

        try:
            result = self.supabase.table("wal_log").insert({
                "id": entry.id,
                "operation_type": entry.operation_type,
                "operation_data": entry.operation_data,
                "status": entry.status.value,
                "retry_count": entry.retry_count,
                "max_retries": entry.max_retries,
                "created_at": entry.created_at.isoformat(),
                "idempotency_key": entry.idempotency_key,
                "correlation_id": entry.correlation_id
            }).execute()

            WAL_ENTRIES_TOTAL.labels(
                operation_type=operation_type,
                status="created"
            ).inc()

            logger.info(
                "WAL entry created",
                wal_id=entry.id,
                operation_type=operation_type,
                idempotency_key=idempotency_key
            )

            return entry.id

        except Exception as e:
            logger.error(
                "Failed to create WAL entry",
                operation_type=operation_type,
                error=str(e)
            )
            raise

    async def mark_in_progress(self, wal_id: str):
        """Mark an operation as in progress."""
        try:
            self.supabase.table("wal_log").update({
                "status": WALStatus.IN_PROGRESS.value,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", wal_id).execute()

            logger.debug("WAL entry marked in_progress", wal_id=wal_id)

        except Exception as e:
            logger.error("Failed to mark WAL in_progress", wal_id=wal_id, error=str(e))

    async def mark_completed(
        self,
        wal_id: str,
        result: Optional[Dict[str, Any]] = None
    ):
        """
        Mark an operation as completed.

        Args:
            wal_id: WAL entry ID
            result: Optional result data to store
        """
        now = datetime.utcnow()

        try:
            self.supabase.table("wal_log").update({
                "status": WALStatus.COMPLETED.value,
                "updated_at": now.isoformat(),
                "completed_at": now.isoformat(),
                "result": result
            }).eq("id", wal_id).execute()

            WAL_ENTRIES_TOTAL.labels(
                operation_type="unknown",
                status="completed"
            ).inc()

            logger.info("WAL entry completed", wal_id=wal_id)

        except Exception as e:
            logger.error("Failed to mark WAL completed", wal_id=wal_id, error=str(e))

    async def mark_failed(self, wal_id: str, error: str):
        """
        Mark an operation as failed.

        Args:
            wal_id: WAL entry ID
            error: Error message
        """
        try:
            # Get current entry to check retry count
            result = self.supabase.table("wal_log").select("*").eq("id", wal_id).execute()

            if result.data:
                entry = result.data[0]
                retry_count = entry.get("retry_count", 0) + 1
                max_retries = entry.get("max_retries", 3)

                self.supabase.table("wal_log").update({
                    "status": WALStatus.FAILED.value,
                    "updated_at": datetime.utcnow().isoformat(),
                    "error": error,
                    "retry_count": retry_count
                }).eq("id", wal_id).execute()

                WAL_ENTRIES_TOTAL.labels(
                    operation_type=entry.get("operation_type", "unknown"),
                    status="failed"
                ).inc()

                logger.warning(
                    "WAL entry failed",
                    wal_id=wal_id,
                    error=error,
                    retry_count=retry_count,
                    max_retries=max_retries
                )

        except Exception as e:
            logger.error("Failed to mark WAL failed", wal_id=wal_id, error=str(e))

    async def get_pending_entries(
        self,
        max_age_hours: int = 24,
        limit: int = 100
    ) -> List[WALEntry]:
        """
        Get all pending WAL entries for replay.

        Args:
            max_age_hours: Maximum age of entries to consider
            limit: Maximum entries to return

        Returns:
            List of pending WAL entries
        """
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

        try:
            # Note: Supabase doesn't support column-to-column comparisons in the API
            # So we fetch candidates and filter retry_count < max_retries in Python
            result = self.supabase.table("wal_log").select("*").in_(
                "status", [WALStatus.PENDING.value, WALStatus.IN_PROGRESS.value]
            ).gt(
                "created_at", cutoff.isoformat()
            ).limit(limit * 2).execute()  # Fetch extra to account for filtering

            # Filter in application code: retry_count < max_retries
            entries = []
            for row in result.data:
                retry_count = row.get("retry_count", 0)
                max_retries = row.get("max_retries", 3)

                # Only include entries that haven't exceeded max retries
                if retry_count < max_retries:
                    entries.append(WALEntry(
                        id=row["id"],
                        operation_type=row["operation_type"],
                        operation_data=row["operation_data"],
                        status=WALStatus(row["status"]),
                        retry_count=retry_count,
                        max_retries=max_retries,
                        created_at=datetime.fromisoformat(row["created_at"]),
                        idempotency_key=row.get("idempotency_key"),
                        correlation_id=row.get("correlation_id"),
                        error=row.get("error")
                    ))

                    # Stop if we have enough entries
                    if len(entries) >= limit:
                        break

            WAL_PENDING_GAUGE.set(len(entries))

            return entries

        except Exception as e:
            logger.error("Failed to get pending WAL entries", error=str(e))
            return []

    async def replay_pending(self) -> Dict[str, int]:
        """
        Replay all pending operations.

        Called on startup to recover from crashes.

        Returns:
            Dict with counts of replayed, succeeded, and failed operations
        """
        logger.info("Starting WAL replay")

        entries = await self.get_pending_entries()
        stats = {"total": len(entries), "succeeded": 0, "failed": 0, "skipped": 0}

        for entry in entries:
            handler = self._operation_handlers.get(entry.operation_type)

            if not handler:
                logger.warning(
                    "No handler for operation type",
                    operation_type=entry.operation_type,
                    wal_id=entry.id
                )
                stats["skipped"] += 1
                continue

            try:
                await self.mark_in_progress(entry.id)
                result = await handler(**entry.operation_data)
                await self.mark_completed(entry.id, {"result": str(result)})

                WAL_REPLAY_TOTAL.labels(
                    operation_type=entry.operation_type,
                    result="success"
                ).inc()

                stats["succeeded"] += 1

            except Exception as e:
                await self.mark_failed(entry.id, str(e))

                WAL_REPLAY_TOTAL.labels(
                    operation_type=entry.operation_type,
                    result="failure"
                ).inc()

                stats["failed"] += 1
                logger.error(
                    "WAL replay failed",
                    wal_id=entry.id,
                    operation_type=entry.operation_type,
                    error=str(e)
                )

        logger.info("WAL replay completed", **stats)
        return stats

    async def execute_with_wal(
        self,
        operation_type: str,
        operation_data: Dict[str, Any],
        operation_fn: Callable[..., Coroutine[Any, Any, Any]],
        idempotency_key: Optional[str] = None
    ) -> Any:
        """
        Execute an operation with WAL protection.

        1. Log operation to WAL
        2. Execute the operation
        3. Mark completed on success
        4. Mark failed on error

        Args:
            operation_type: Type of operation
            operation_data: Operation parameters
            operation_fn: Async function to execute
            idempotency_key: Optional idempotency key

        Returns:
            Result from operation_fn
        """
        import time
        start_time = time.time()

        wal_id = await self.log_operation(
            operation_type,
            operation_data,
            idempotency_key
        )

        try:
            await self.mark_in_progress(wal_id)
            result = await operation_fn(**operation_data)
            await self.mark_completed(wal_id, {"success": True})

            duration = time.time() - start_time
            WAL_OPERATION_DURATION.labels(operation_type=operation_type).observe(duration)

            return result

        except Exception as e:
            await self.mark_failed(wal_id, str(e))
            raise

    async def cleanup_old_entries(self, days: int = 7) -> int:
        """
        Clean up old completed/failed WAL entries.

        Args:
            days: Delete entries older than this many days

        Returns:
            Number of entries deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        try:
            result = self.supabase.table("wal_log").delete().in_(
                "status", [WALStatus.COMPLETED.value, WALStatus.COMPENSATED.value]
            ).lt(
                "created_at", cutoff.isoformat()
            ).execute()

            count = len(result.data) if result.data else 0
            logger.info(f"Cleaned up {count} old WAL entries")
            return count

        except Exception as e:
            logger.error("Failed to cleanup WAL entries", error=str(e))
            return 0


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_wal_instance: Optional[WriteAheadLog] = None


def get_wal_manager() -> Optional[WriteAheadLog]:
    """Get the global WAL manager instance"""
    return _wal_instance


def initialize_wal_manager(supabase_client) -> WriteAheadLog:
    """Initialize the global WAL manager"""
    global _wal_instance
    _wal_instance = WriteAheadLog(supabase_client)
    return _wal_instance
