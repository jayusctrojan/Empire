"""
Empire v7.3 - Optimistic Locking
Data Persistence P0 Fix - Prevent race conditions with version numbers

Optimistic locking ensures data consistency in concurrent environments by:
1. Including a version number with each record
2. Incrementing version on updates
3. Rejecting updates if version doesn't match (concurrent modification)

Usage:
    # Update with lock
    try:
        updated = await update_with_lock(
            supabase=supabase,
            table="documents_v2",
            record_id="doc-123",
            updates={"title": "New Title"},
            expected_version=5
        )
    except OptimisticLockException:
        # Record was modified by another request - handle conflict
        pass
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import structlog
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram

logger = structlog.get_logger(__name__)


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

LOCK_ATTEMPTS_TOTAL = Counter(
    "empire_optimistic_lock_attempts_total",
    "Total optimistic lock attempts",
    ["table", "result"]
)

LOCK_CONFLICTS_TOTAL = Counter(
    "empire_optimistic_lock_conflicts_total",
    "Total optimistic lock conflicts",
    ["table"]
)

LOCK_RETRIES_TOTAL = Counter(
    "empire_optimistic_lock_retries_total",
    "Total optimistic lock retry attempts",
    ["table"]
)


# =============================================================================
# EXCEPTIONS
# =============================================================================

class OptimisticLockException(Exception):
    """Raised when optimistic lock fails due to concurrent modification"""

    def __init__(
        self,
        table: str,
        record_id: str,
        expected_version: int,
        actual_version: Optional[int] = None
    ):
        self.table = table
        self.record_id = record_id
        self.expected_version = expected_version
        self.actual_version = actual_version

        message = (
            f"Optimistic lock failed for {table}.{record_id}: "
            f"expected version {expected_version}"
        )
        if actual_version is not None:
            message += f", found version {actual_version}"
        else:
            message += ", record was modified by another request"

        super().__init__(message)


class RecordNotFoundException(Exception):
    """Raised when record is not found"""

    def __init__(self, table: str, record_id: str):
        self.table = table
        self.record_id = record_id
        super().__init__(f"Record not found: {table}.{record_id}")


# =============================================================================
# MODELS
# =============================================================================

class VersionedRecord(BaseModel):
    """A record with version tracking"""
    id: str
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LockResult(BaseModel):
    """Result of a lock operation"""
    success: bool
    record_id: str
    new_version: int
    updates_applied: Dict[str, Any]


# =============================================================================
# OPTIMISTIC LOCKING FUNCTIONS
# =============================================================================

async def get_current_version(
    supabase,
    table: str,
    record_id: str,
    id_column: str = "id"
) -> Tuple[int, Dict[str, Any]]:
    """
    Get the current version of a record.

    Args:
        supabase: Supabase client
        table: Table name
        record_id: Record ID
        id_column: Name of the ID column

    Returns:
        Tuple of (version, full_record)

    Raises:
        RecordNotFoundException: If record doesn't exist
    """
    result = supabase.table(table).select("*").eq(id_column, record_id).execute()

    if not result.data:
        raise RecordNotFoundException(table, record_id)

    record = result.data[0]
    version = record.get("version", 1)

    return version, record


async def update_with_lock(
    supabase,
    table: str,
    record_id: str,
    updates: Dict[str, Any],
    expected_version: Optional[int] = None,
    id_column: str = "id"
) -> LockResult:
    """
    Update a record with optimistic locking.

    Increments version only if current version matches expected.

    Args:
        supabase: Supabase client
        table: Table name
        record_id: Record ID to update
        updates: Dict of field updates
        expected_version: Expected version (if None, will fetch current)
        id_column: Name of the ID column

    Returns:
        LockResult with new version

    Raises:
        OptimisticLockException: If version doesn't match
        RecordNotFoundException: If record doesn't exist
    """
    LOCK_ATTEMPTS_TOTAL.labels(table=table, result="attempt").inc()

    # If no expected version provided, fetch current
    if expected_version is None:
        expected_version, _ = await get_current_version(supabase, table, record_id, id_column)

    # Prepare update with version increment
    update_data = {
        **updates,
        "version": expected_version + 1,
        "updated_at": datetime.utcnow().isoformat()
    }

    # Attempt update with version check
    result = supabase.table(table).update(update_data).eq(
        id_column, record_id
    ).eq(
        "version", expected_version
    ).execute()

    if not result.data:
        # Update failed - check why
        LOCK_CONFLICTS_TOTAL.labels(table=table).inc()
        LOCK_ATTEMPTS_TOTAL.labels(table=table, result="conflict").inc()

        try:
            current_version, _ = await get_current_version(supabase, table, record_id, id_column)
            raise OptimisticLockException(
                table=table,
                record_id=record_id,
                expected_version=expected_version,
                actual_version=current_version
            )
        except RecordNotFoundException:
            raise

    LOCK_ATTEMPTS_TOTAL.labels(table=table, result="success").inc()

    logger.debug(
        "Optimistic lock update succeeded",
        table=table,
        record_id=record_id,
        old_version=expected_version,
        new_version=expected_version + 1
    )

    return LockResult(
        success=True,
        record_id=record_id,
        new_version=expected_version + 1,
        updates_applied=updates
    )


async def update_with_retry(
    supabase,
    table: str,
    record_id: str,
    update_fn,
    max_retries: int = 3,
    retry_delay: float = 0.1,
    id_column: str = "id"
) -> LockResult:
    """
    Update a record with automatic retry on conflict.

    Useful when updates are computed from current state.

    Args:
        supabase: Supabase client
        table: Table name
        record_id: Record ID
        update_fn: Function that takes current record and returns updates dict
        max_retries: Maximum retry attempts
        retry_delay: Base delay between retries (exponential backoff)
        id_column: Name of the ID column

    Returns:
        LockResult with new version

    Raises:
        OptimisticLockException: If all retries fail
        RecordNotFoundException: If record doesn't exist
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            # Fetch current state
            version, record = await get_current_version(supabase, table, record_id, id_column)

            # Compute updates based on current state
            updates = update_fn(record)

            # Attempt update
            result = await update_with_lock(
                supabase=supabase,
                table=table,
                record_id=record_id,
                updates=updates,
                expected_version=version,
                id_column=id_column
            )

            return result

        except OptimisticLockException as e:
            last_error = e
            LOCK_RETRIES_TOTAL.labels(table=table).inc()

            if attempt < max_retries - 1:
                # Exponential backoff
                delay = retry_delay * (2 ** attempt)
                logger.warning(
                    "Optimistic lock conflict, retrying",
                    table=table,
                    record_id=record_id,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay=delay
                )
                await asyncio.sleep(delay)

    raise last_error


async def batch_update_with_lock(
    supabase,
    table: str,
    updates: List[Dict[str, Any]],
    id_column: str = "id"
) -> List[LockResult]:
    """
    Update multiple records with optimistic locking.

    Each update dict must include 'id' and 'version' fields.

    Args:
        supabase: Supabase client
        table: Table name
        updates: List of update dicts with id, version, and fields to update
        id_column: Name of the ID column

    Returns:
        List of LockResult for each update

    Note:
        This is NOT transactional - some updates may succeed while others fail
    """
    results = []

    for update in updates:
        record_id = update.pop(id_column)
        expected_version = update.pop("version")

        try:
            result = await update_with_lock(
                supabase=supabase,
                table=table,
                record_id=record_id,
                updates=update,
                expected_version=expected_version,
                id_column=id_column
            )
            results.append(result)

        except (OptimisticLockException, RecordNotFoundException) as e:
            results.append(LockResult(
                success=False,
                record_id=record_id,
                new_version=-1,
                updates_applied={}
            ))
            logger.warning(
                "Batch update failed for record",
                table=table,
                record_id=record_id,
                error=str(e)
            )

    return results


# =============================================================================
# VERSIONED RECORD HELPERS
# =============================================================================

async def create_versioned_record(
    supabase,
    table: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a new record with version 1.

    Args:
        supabase: Supabase client
        table: Table name
        data: Record data

    Returns:
        Created record with version
    """
    now = datetime.utcnow().isoformat()
    record_data = {
        **data,
        "version": 1,
        "created_at": now,
        "updated_at": now
    }

    result = supabase.table(table).insert(record_data).execute()

    if result.data:
        return result.data[0]

    raise Exception(f"Failed to create record in {table}")


async def delete_with_lock(
    supabase,
    table: str,
    record_id: str,
    expected_version: int,
    id_column: str = "id"
) -> bool:
    """
    Delete a record with optimistic locking.

    Args:
        supabase: Supabase client
        table: Table name
        record_id: Record ID
        expected_version: Expected version
        id_column: Name of the ID column

    Returns:
        True if deleted

    Raises:
        OptimisticLockException: If version doesn't match
    """
    result = supabase.table(table).delete().eq(
        id_column, record_id
    ).eq(
        "version", expected_version
    ).execute()

    if not result.data:
        # Check if record exists with different version
        try:
            current_version, _ = await get_current_version(supabase, table, record_id, id_column)
            raise OptimisticLockException(
                table=table,
                record_id=record_id,
                expected_version=expected_version,
                actual_version=current_version
            )
        except RecordNotFoundException:
            # Record already deleted
            return True

    return True


# =============================================================================
# DECORATOR FOR VERSIONED OPERATIONS
# =============================================================================

def with_optimistic_lock(
    table: str,
    id_param: str = "record_id",
    version_param: str = "version",
    max_retries: int = 3
):
    """
    Decorator for functions that need optimistic locking.

    Usage:
        @with_optimistic_lock(table="documents_v2", id_param="doc_id")
        async def update_document(doc_id: str, version: int, title: str):
            return {"title": title}

    Note: The decorated function should return a dict of updates to apply.
    For async functions, ensure the updates are simple dicts (not coroutines).
    """
    import functools

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract parameters
            from app.core.connections import get_supabase

            supabase = get_supabase()
            record_id = kwargs.get(id_param)

            if not record_id:
                raise ValueError(f"Missing required parameter: {id_param}")

            # Remove version from kwargs (version is handled by update_with_retry)
            kwargs_copy = kwargs.copy()
            if version_param in kwargs_copy:
                del kwargs_copy[version_param]

            # For async-compatible update function
            async def get_updates_async(record):
                # Remove id_param to avoid passing it to function
                call_kwargs = {k: v for k, v in kwargs_copy.items() if k != id_param}
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **call_kwargs)
                return func(*args, **call_kwargs)

            # Sync wrapper for update_with_retry (which expects sync update_fn)
            def get_updates(record):
                call_kwargs = {k: v for k, v in kwargs_copy.items() if k != id_param}
                # For sync functions, call directly
                if not asyncio.iscoroutinefunction(func):
                    return func(*args, **call_kwargs)
                # For async, we need a different approach - use the result already computed
                raise ValueError(
                    "Async functions are not supported with with_optimistic_lock decorator. "
                    "Use update_with_retry directly for async update functions."
                )

            return await update_with_retry(
                supabase=supabase,
                table=table,
                record_id=record_id,
                update_fn=get_updates,
                max_retries=max_retries
            )

        return wrapper
    return decorator
