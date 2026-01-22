"""
Empire v7.3 - Resilient B2 Storage Service (Task 157)

Enhanced B2 storage service with comprehensive error handling:
- Retry logic with exponential backoff (tenacity)
- SHA1 checksum verification for data integrity
- Redis-based dead letter queue for failed operations
- Prometheus metrics for monitoring

Author: Claude Code
Date: 2025-01-15
"""

import os
import json
import hashlib
import time
import asyncio
import logging
from typing import Optional, Dict, Any, List, BinaryIO, Callable
from datetime import datetime, timedelta
from enum import Enum
from io import BytesIO

import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError,
)
from prometheus_client import Counter, Histogram, Gauge
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from b2sdk.v2.exception import B2Error, B2ConnectionError, B2RequestTimeout, FileNotPresent

from app.services.b2_storage import get_b2_service, B2StorageService, B2Folder, ProcessingStatus
from app.core.connections import get_redis
from app.exceptions import (
    B2StorageException,
    ChecksumMismatchException,
    DeadLetterQueueException,
    B2RetryExhaustedException,
    FileUploadException,
    FileDownloadException,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

# Operation counters
B2_OPERATION_COUNTER = Counter(
    'empire_b2_operations_total',
    'Total number of B2 storage operations',
    ['operation_type', 'status']
)

# Operation latency histogram
B2_OPERATION_LATENCY = Histogram(
    'empire_b2_operation_latency_seconds',
    'Latency of B2 operations in seconds',
    ['operation_type'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# Storage usage gauge
B2_STORAGE_USAGE = Gauge(
    'empire_b2_storage_usage_bytes',
    'Current B2 storage usage in bytes'
)

# Dead letter queue size
B2_DLQ_SIZE = Gauge(
    'empire_b2_dlq_size',
    'Number of operations in B2 dead letter queue'
)

# Retry counters
B2_RETRY_COUNTER = Counter(
    'empire_b2_retries_total',
    'Total number of B2 operation retries',
    ['operation_type']
)

# Checksum verification counters
B2_CHECKSUM_COUNTER = Counter(
    'empire_b2_checksum_verifications_total',
    'Total number of checksum verifications',
    ['status']  # success, failure
)


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_MIN_WAIT = 2  # seconds
DEFAULT_RETRY_MAX_WAIT = 60  # seconds
DLQ_NAME = "b2_dead_letter_queue"
CHUNK_SIZE = 8192  # For checksum calculation


# =============================================================================
# DEAD LETTER QUEUE
# =============================================================================

class B2DeadLetterQueue:
    """
    Redis-based dead letter queue for failed B2 operations.

    Stores failed operations for later retry or manual intervention.
    """

    def __init__(self, queue_name: str = DLQ_NAME):
        """
        Initialize dead letter queue.

        Args:
            queue_name: Redis key for the queue
        """
        self.queue_name = queue_name
        self._redis = None

    def _get_redis(self):
        """Get Redis client lazily"""
        if self._redis is None:
            self._redis = get_redis()
        return self._redis

    async def add_failed_operation(
        self,
        operation_type: str,
        file_path: str,
        error_details: str,
        retry_count: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a failed operation to the dead letter queue.

        Args:
            operation_type: Type of operation (upload/download)
            file_path: Path to the file
            error_details: Error message
            retry_count: Number of retries attempted
            metadata: Additional operation metadata

        Returns:
            bool: True if successfully added
        """
        try:
            redis = self._get_redis()

            entry = {
                "operation_type": operation_type,
                "file_path": file_path,
                "error_details": error_details,
                "retry_count": retry_count,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow().isoformat(),
                "status": "pending"
            }

            await asyncio.to_thread(
                redis.lpush,
                self.queue_name,
                json.dumps(entry)
            )

            # Update DLQ size metric
            size = await self.get_queue_size()
            B2_DLQ_SIZE.set(size)

            logger.info(
                "Added failed operation to DLQ",
                operation_type=operation_type,
                file_path=file_path,
                retry_count=retry_count
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to add operation to DLQ",
                error=str(e),
                operation_type=operation_type
            )
            raise DeadLetterQueueException(
                message=f"Failed to add operation to DLQ: {e}",
                operation_type="add",
                queue_name=self.queue_name
            )

    async def get_failed_operations(
        self,
        limit: int = 100,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get failed operations from the queue.

        Args:
            limit: Maximum number of entries to return
            status_filter: Filter by status (pending/processing/retried)

        Returns:
            List of failed operation entries
        """
        try:
            redis = self._get_redis()

            entries = await asyncio.to_thread(
                redis.lrange,
                self.queue_name,
                0,
                limit - 1
            )

            operations = [json.loads(entry) for entry in entries]

            if status_filter:
                operations = [
                    op for op in operations
                    if op.get("status") == status_filter
                ]

            return operations

        except Exception as e:
            logger.error("Failed to get DLQ operations", error=str(e))
            raise DeadLetterQueueException(
                message=f"Failed to retrieve operations from DLQ: {e}",
                operation_type="get",
                queue_name=self.queue_name
            )

    async def remove_operation(self, entry_json: str) -> bool:
        """
        Remove an operation from the queue.

        Args:
            entry_json: JSON string of the entry to remove

        Returns:
            bool: True if removed
        """
        try:
            redis = self._get_redis()
            await asyncio.to_thread(
                redis.lrem,
                self.queue_name,
                1,
                entry_json
            )

            # Update DLQ size metric
            size = await self.get_queue_size()
            B2_DLQ_SIZE.set(size)

            return True

        except Exception as e:
            logger.error("Failed to remove DLQ entry", error=str(e))
            raise DeadLetterQueueException(
                message=f"Failed to remove operation from DLQ: {e}",
                operation_type="remove",
                queue_name=self.queue_name
            )

    async def get_queue_size(self) -> int:
        """Get the current size of the dead letter queue."""
        try:
            redis = self._get_redis()
            return await asyncio.to_thread(redis.llen, self.queue_name)
        except Exception:
            return 0

    async def clear_queue(self) -> int:
        """
        Clear all entries from the queue.

        Returns:
            int: Number of entries cleared
        """
        try:
            redis = self._get_redis()
            size = await self.get_queue_size()
            await asyncio.to_thread(redis.delete, self.queue_name)
            B2_DLQ_SIZE.set(0)
            return size

        except Exception as e:
            logger.error("Failed to clear DLQ", error=str(e))
            raise DeadLetterQueueException(
                message=f"Failed to clear DLQ: {e}",
                operation_type="clear",
                queue_name=self.queue_name
            )


# =============================================================================
# CHECKSUM UTILITIES
# =============================================================================

def calculate_sha1(data: bytes) -> str:
    """
    Calculate SHA1 checksum for data.

    Args:
        data: Bytes to calculate checksum for

    Returns:
        str: Hexadecimal SHA1 checksum
    """
    sha1 = hashlib.sha1()
    sha1.update(data)
    return sha1.hexdigest()


def calculate_sha1_file(file_path: str) -> str:
    """
    Calculate SHA1 checksum for a file.

    Args:
        file_path: Path to the file

    Returns:
        str: Hexadecimal SHA1 checksum
    """
    sha1 = hashlib.sha1()
    with open(file_path, 'rb') as f:
        while chunk := f.read(CHUNK_SIZE):
            sha1.update(chunk)
    return sha1.hexdigest()


def _verify_checksums_match(
    local_checksum: str,
    remote_checksum: str,
    file_path: str
) -> bool:
    """
    Verify that checksums match.

    Args:
        local_checksum: Calculated local checksum
        remote_checksum: Checksum from B2
        file_path: File path for error reporting

    Returns:
        bool: True if checksums match

    Raises:
        ChecksumMismatchException: If checksums don't match
    """
    if local_checksum != remote_checksum:
        B2_CHECKSUM_COUNTER.labels(status="failure").inc()
        raise ChecksumMismatchException(
            message=f"Checksum verification failed for {file_path}",
            file_path=file_path,
            expected_checksum=remote_checksum,
            actual_checksum=local_checksum
        )

    B2_CHECKSUM_COUNTER.labels(status="success").inc()
    return True


# =============================================================================
# RESILIENT B2 STORAGE SERVICE
# =============================================================================

class ResilientB2StorageService:
    """
    Enhanced B2 storage service with comprehensive error handling.

    Features:
    - Automatic retry with exponential backoff
    - SHA1 checksum verification
    - Dead letter queue for failed operations
    - Prometheus metrics collection
    """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        min_wait: int = DEFAULT_RETRY_MIN_WAIT,
        max_wait: int = DEFAULT_RETRY_MAX_WAIT
    ):
        """
        Initialize resilient B2 storage service.

        Args:
            max_retries: Maximum retry attempts
            min_wait: Minimum wait between retries (seconds)
            max_wait: Maximum wait between retries (seconds)
        """
        self.b2_service = get_b2_service()
        self.dead_letter_queue = B2DeadLetterQueue()
        self.max_retries = max_retries
        self.min_wait = min_wait
        self.max_wait = max_wait

        # Stats tracking
        self._stats = {
            "uploads_successful": 0,
            "uploads_failed": 0,
            "downloads_successful": 0,
            "downloads_failed": 0,
            "checksum_verifications": 0,
            "dlq_entries_added": 0,
            "dlq_entries_processed": 0,
        }

    def _create_retry_decorator(self, operation_name: str):
        """Create a tenacity retry decorator for the given operation."""
        return retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(
                multiplier=1,
                min=self.min_wait,
                max=self.max_wait
            ),
            retry=retry_if_exception_type((
                B2Error,
                B2ConnectionError,
                B2RequestTimeout,
                ConnectionError,
                TimeoutError
            )),
            before_sleep=before_sleep_log(logger, logging.INFO),
            reraise=False  # Raise RetryError so we can convert to B2RetryExhaustedException
        )

    async def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        folder: B2Folder = B2Folder.PENDING,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
        encrypt: bool = False,
        encryption_password: Optional[str] = None,
        verify_checksum: bool = True
    ) -> Dict[str, Any]:
        """
        Upload a file with retry logic and checksum verification.

        Args:
            file_data: File-like object to upload
            filename: Name of the file
            folder: Destination folder
            content_type: MIME type
            metadata: File metadata
            encrypt: Whether to encrypt
            encryption_password: Encryption password
            verify_checksum: Whether to verify checksum after upload

        Returns:
            Dict with upload result

        Raises:
            B2RetryExhaustedException: If all retries fail
            ChecksumMismatchException: If checksum verification fails
        """
        start_time = time.time()
        retry_count = 0
        last_error = None

        # Read file data for checksum calculation
        file_bytes = file_data.read()
        local_checksum = calculate_sha1(file_bytes) if verify_checksum else None

        # Reset file position
        file_data = BytesIO(file_bytes)

        try:
            # Create retry wrapper
            @self._create_retry_decorator("upload")
            async def _do_upload():
                nonlocal retry_count
                retry_count += 1
                if retry_count > 1:
                    B2_RETRY_COUNTER.labels(operation_type="upload").inc()

                # Reset BytesIO position for retry
                file_data.seek(0)

                return await self.b2_service.upload_file(
                    file_data=file_data,
                    filename=filename,
                    folder=folder,
                    content_type=content_type,
                    metadata=metadata,
                    encrypt=encrypt,
                    encryption_password=encryption_password
                )

            result = await _do_upload()

            # Verify checksum if requested
            if verify_checksum and local_checksum:
                # B2 stores SHA1 in content_sha1 field
                remote_checksum = result.get("content_sha1")
                if remote_checksum:
                    _verify_checksums_match(local_checksum, remote_checksum, filename)
                    result["checksum_verified"] = True
                    self._stats["checksum_verifications"] += 1

            # Record success metrics
            duration = time.time() - start_time
            B2_OPERATION_COUNTER.labels(operation_type="upload", status="success").inc()
            B2_OPERATION_LATENCY.labels(operation_type="upload").observe(duration)

            self._stats["uploads_successful"] += 1

            logger.info(
                "File uploaded successfully",
                filename=filename,
                retry_count=retry_count,
                duration=duration
            )

            return result

        except RetryError as e:
            last_error = str(e.last_attempt.exception()) if e.last_attempt.exception() else str(e)

            # Record failure metrics
            duration = time.time() - start_time
            B2_OPERATION_COUNTER.labels(operation_type="upload", status="failure").inc()
            B2_OPERATION_LATENCY.labels(operation_type="upload").observe(duration)

            self._stats["uploads_failed"] += 1

            # Add to dead letter queue
            await self.dead_letter_queue.add_failed_operation(
                operation_type="upload",
                file_path=filename,
                error_details=last_error,
                retry_count=retry_count,
                metadata={
                    "folder": folder.value if isinstance(folder, B2Folder) else folder,
                    "content_type": content_type,
                    "checksum": local_checksum
                }
            )
            self._stats["dlq_entries_added"] += 1

            logger.error(
                "Upload failed after all retries",
                filename=filename,
                retry_count=retry_count,
                error=last_error
            )

            raise B2RetryExhaustedException(
                message=f"Upload failed after {retry_count} attempts",
                operation="upload",
                file_path=filename,
                retry_count=retry_count,
                last_error=last_error
            )

        except Exception as e:
            # Record failure for non-retry exceptions
            duration = time.time() - start_time
            B2_OPERATION_COUNTER.labels(operation_type="upload", status="failure").inc()
            B2_OPERATION_LATENCY.labels(operation_type="upload").observe(duration)

            self._stats["uploads_failed"] += 1

            logger.error("Upload failed", filename=filename, error=str(e))
            raise

    async def download_file(
        self,
        file_id: str,
        file_name: str,
        destination_path: str,
        verify_checksum: bool = True,
        expected_checksum: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Download a file with retry logic and checksum verification.

        Args:
            file_id: B2 file ID
            file_name: File name in B2
            destination_path: Local path to save file
            verify_checksum: Whether to verify checksum
            expected_checksum: Expected SHA1 checksum

        Returns:
            Dict with download result

        Raises:
            B2RetryExhaustedException: If all retries fail
            ChecksumMismatchException: If checksum verification fails
        """
        start_time = time.time()
        retry_count = 0
        last_error = None

        try:
            @self._create_retry_decorator("download")
            async def _do_download():
                nonlocal retry_count
                retry_count += 1
                if retry_count > 1:
                    B2_RETRY_COUNTER.labels(operation_type="download").inc()

                return await self.b2_service.download_file(
                    file_id=file_id,
                    file_name=file_name,
                    destination_path=destination_path
                )

            result = await _do_download()

            # Verify checksum if requested
            if verify_checksum and os.path.exists(destination_path):
                local_checksum = calculate_sha1_file(destination_path)

                if expected_checksum:
                    _verify_checksums_match(local_checksum, expected_checksum, destination_path)
                    self._stats["checksum_verifications"] += 1

                result = {
                    "success": True,
                    "file_path": destination_path,
                    "checksum": local_checksum,
                    "checksum_verified": expected_checksum is not None
                }

            # Record success metrics
            duration = time.time() - start_time
            B2_OPERATION_COUNTER.labels(operation_type="download", status="success").inc()
            B2_OPERATION_LATENCY.labels(operation_type="download").observe(duration)

            self._stats["downloads_successful"] += 1

            logger.info(
                "File downloaded successfully",
                file_name=file_name,
                destination=destination_path,
                retry_count=retry_count
            )

            return result

        except RetryError as e:
            last_error = str(e.last_attempt.exception()) if e.last_attempt.exception() else str(e)

            # Record failure metrics
            duration = time.time() - start_time
            B2_OPERATION_COUNTER.labels(operation_type="download", status="failure").inc()
            B2_OPERATION_LATENCY.labels(operation_type="download").observe(duration)

            self._stats["downloads_failed"] += 1

            # Add to dead letter queue
            await self.dead_letter_queue.add_failed_operation(
                operation_type="download",
                file_path=file_name,
                error_details=last_error,
                retry_count=retry_count,
                metadata={
                    "file_id": file_id,
                    "destination_path": destination_path,
                    "expected_checksum": expected_checksum
                }
            )
            self._stats["dlq_entries_added"] += 1

            logger.error(
                "Download failed after all retries",
                file_name=file_name,
                retry_count=retry_count,
                error=last_error
            )

            raise B2RetryExhaustedException(
                message=f"Download failed after {retry_count} attempts",
                operation="download",
                file_path=file_name,
                retry_count=retry_count,
                last_error=last_error
            )

        except Exception as e:
            duration = time.time() - start_time
            B2_OPERATION_COUNTER.labels(operation_type="download", status="failure").inc()
            B2_OPERATION_LATENCY.labels(operation_type="download").observe(duration)

            self._stats["downloads_failed"] += 1

            logger.error("Download failed", file_name=file_name, error=str(e))
            raise

    async def process_dead_letter_queue(
        self,
        batch_size: int = 10,
        max_retry_count: int = 10
    ) -> Dict[str, Any]:
        """
        Process entries in the dead letter queue.

        Args:
            batch_size: Number of entries to process
            max_retry_count: Maximum retries before permanent failure

        Returns:
            Dict with processing results
        """
        logger.info("Processing dead letter queue", batch_size=batch_size)

        failed_operations = await self.dead_letter_queue.get_failed_operations(
            limit=batch_size,
            status_filter="pending"
        )

        results = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "permanent_failures": 0,
            "details": []
        }

        for operation in failed_operations:
            entry_json = json.dumps(operation)
            operation_type = operation.get("operation_type")
            file_path = operation.get("file_path")
            current_retry_count = operation.get("retry_count", 0)

            if current_retry_count >= max_retry_count:
                logger.warning(
                    "Operation exceeded max retries, marking as permanent failure",
                    file_path=file_path,
                    retry_count=current_retry_count
                )
                results["permanent_failures"] += 1
                results["details"].append({
                    "file_path": file_path,
                    "status": "permanent_failure",
                    "retry_count": current_retry_count
                })
                continue

            try:
                results["processed"] += 1

                if operation_type == "upload":
                    # Re-upload would need the original file data
                    # This is a placeholder - actual implementation would need file access
                    logger.info(
                        "DLQ upload retry skipped - requires original file",
                        file_path=file_path
                    )
                    results["details"].append({
                        "file_path": file_path,
                        "status": "skipped",
                        "reason": "requires_original_file"
                    })

                elif operation_type == "download":
                    metadata = operation.get("metadata", {})
                    await self.download_file(
                        file_id=metadata.get("file_id"),
                        file_name=file_path,
                        destination_path=metadata.get("destination_path"),
                        expected_checksum=metadata.get("expected_checksum")
                    )

                    # Remove from queue on success
                    await self.dead_letter_queue.remove_operation(entry_json)
                    results["succeeded"] += 1
                    results["details"].append({
                        "file_path": file_path,
                        "status": "success"
                    })

                self._stats["dlq_entries_processed"] += 1

            except Exception as e:
                logger.error(
                    "DLQ retry failed",
                    file_path=file_path,
                    error=str(e)
                )
                results["failed"] += 1
                results["details"].append({
                    "file_path": file_path,
                    "status": "failed",
                    "error": str(e)
                })

        logger.info(
            "Dead letter queue processing complete",
            processed=results["processed"],
            succeeded=results["succeeded"],
            failed=results["failed"]
        )

        return results

    async def update_storage_metrics(self) -> Dict[str, Any]:
        """
        Update storage metrics from B2.

        Returns:
            Dict with current storage metrics
        """
        try:
            # Get bucket info to calculate storage usage
            bucket = self.b2_service._get_bucket()

            # List all files to calculate total size
            total_size = 0
            file_count = 0

            for file_version, _ in bucket.ls(fetch_count=1000):
                total_size += file_version.size
                file_count += 1

            B2_STORAGE_USAGE.set(total_size)

            # Update DLQ size
            dlq_size = await self.dead_letter_queue.get_queue_size()
            B2_DLQ_SIZE.set(dlq_size)

            metrics = {
                "total_storage_bytes": total_size,
                "total_storage_mb": total_size / (1024 * 1024),
                "file_count": file_count,
                "dlq_size": dlq_size,
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info("Storage metrics updated", **metrics)

            return metrics

        except Exception as e:
            logger.error("Failed to update storage metrics", error=str(e))
            return {"error": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            **self._stats,
            "service_name": "ResilientB2StorageService",
            "max_retries": self.max_retries,
            "min_wait_seconds": self.min_wait,
            "max_wait_seconds": self.max_wait
        }


# =============================================================================
# SINGLETON
# =============================================================================

_resilient_b2_service: Optional[ResilientB2StorageService] = None


def get_resilient_b2_service() -> ResilientB2StorageService:
    """Get or create resilient B2 storage service singleton."""
    global _resilient_b2_service
    if _resilient_b2_service is None:
        _resilient_b2_service = ResilientB2StorageService()
    return _resilient_b2_service
