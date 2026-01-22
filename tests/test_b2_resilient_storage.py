"""
Empire v7.3 - B2 Resilient Storage Tests (Task 157)

Tests for B2 storage error handling including:
- Retry logic with exponential backoff
- Checksum verification
- Dead letter queue
- Prometheus metrics

Author: Claude Code
Date: 2025-01-15
"""

import pytest
import asyncio
import json
import hashlib
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from io import BytesIO

from b2sdk.v2.exception import B2Error, B2ConnectionError, B2RequestTimeout

# Import test subjects
from app.services.b2_resilient_storage import (
    ResilientB2StorageService,
    B2DeadLetterQueue,
    calculate_sha1,
    calculate_sha1_file,
    _verify_checksums_match,
    get_resilient_b2_service,
    DEFAULT_MAX_RETRIES,
    DLQ_NAME,
)
from app.exceptions import (
    B2StorageException,
    ChecksumMismatchException,
    DeadLetterQueueException,
    B2RetryExhaustedException,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_redis():
    """Create a mock Redis client"""
    mock = MagicMock()
    mock.lpush = MagicMock(return_value=1)
    mock.lrange = MagicMock(return_value=[])
    mock.lrem = MagicMock(return_value=1)
    mock.llen = MagicMock(return_value=0)
    mock.delete = MagicMock(return_value=1)
    return mock


@pytest.fixture
def mock_b2_service():
    """Create a mock B2 storage service"""
    mock = MagicMock()
    mock.upload_file = AsyncMock()
    mock.download_file = AsyncMock()
    mock._get_bucket = MagicMock()
    return mock


@pytest.fixture
def dead_letter_queue(mock_redis):
    """Create a dead letter queue with mocked Redis"""
    with patch('app.services.b2_resilient_storage.get_redis') as mock_get_redis:
        mock_get_redis.return_value = mock_redis
        dlq = B2DeadLetterQueue()
        dlq._redis = mock_redis
        return dlq


@pytest.fixture
def resilient_service(mock_b2_service, mock_redis):
    """Create a resilient B2 service with mocked dependencies"""
    with patch('app.services.b2_resilient_storage.get_b2_service') as mock_get_b2:
        mock_get_b2.return_value = mock_b2_service
        with patch('app.services.b2_resilient_storage.get_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_redis
            service = ResilientB2StorageService()
            service.b2_service = mock_b2_service
            service.dead_letter_queue._redis = mock_redis
            return service


@pytest.fixture
def sample_file_content():
    """Sample file content for testing"""
    return b"This is test content for B2 storage testing."


# =============================================================================
# CHECKSUM TESTS
# =============================================================================

class TestChecksumFunctions:
    """Test checksum calculation and verification"""

    def test_calculate_sha1_basic(self, sample_file_content):
        """Test SHA1 calculation for basic content"""
        checksum = calculate_sha1(sample_file_content)
        assert len(checksum) == 40  # SHA1 produces 40-character hex string
        assert checksum.isalnum()

    def test_calculate_sha1_consistency(self, sample_file_content):
        """Test SHA1 produces consistent results"""
        checksum1 = calculate_sha1(sample_file_content)
        checksum2 = calculate_sha1(sample_file_content)
        assert checksum1 == checksum2

    def test_calculate_sha1_different_content(self):
        """Test SHA1 produces different results for different content"""
        checksum1 = calculate_sha1(b"content A")
        checksum2 = calculate_sha1(b"content B")
        assert checksum1 != checksum2

    def test_calculate_sha1_empty_content(self):
        """Test SHA1 for empty content"""
        checksum = calculate_sha1(b"")
        # SHA1 of empty string is known
        assert checksum == "da39a3ee5e6b4b0d3255bfef95601890afd80709"

    def test_verify_checksum_match(self):
        """Test checksum verification with matching checksums"""
        checksum = "abc123def456"
        result = _verify_checksums_match(checksum, checksum, "/test/file.txt")
        assert result is True

    def test_verify_checksum_mismatch(self):
        """Test checksum verification raises exception on mismatch"""
        with pytest.raises(ChecksumMismatchException) as exc_info:
            _verify_checksums_match("checksum_a", "checksum_b", "/test/file.txt")

        assert exc_info.value.error_code == "CHECKSUM_MISMATCH"
        assert "checksum_a" in str(exc_info.value.details.get("actual_checksum", ""))


# =============================================================================
# DEAD LETTER QUEUE TESTS
# =============================================================================

class TestDeadLetterQueue:
    """Test dead letter queue operations"""

    @pytest.mark.asyncio
    async def test_add_failed_operation(self, dead_letter_queue, mock_redis):
        """Test adding operation to DLQ"""
        result = await dead_letter_queue.add_failed_operation(
            operation_type="upload",
            file_path="/test/file.txt",
            error_details="Connection timeout",
            retry_count=3
        )

        assert result is True
        mock_redis.lpush.assert_called_once()

        # Verify the JSON structure
        call_args = mock_redis.lpush.call_args
        entry = json.loads(call_args[0][1])
        assert entry["operation_type"] == "upload"
        assert entry["file_path"] == "/test/file.txt"
        assert entry["retry_count"] == 3

    @pytest.mark.asyncio
    async def test_get_failed_operations_empty(self, dead_letter_queue, mock_redis):
        """Test getting operations from empty DLQ"""
        mock_redis.lrange.return_value = []

        operations = await dead_letter_queue.get_failed_operations(limit=10)

        assert operations == []
        mock_redis.lrange.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_failed_operations_with_data(self, dead_letter_queue, mock_redis):
        """Test getting operations from DLQ with data"""
        mock_entry = json.dumps({
            "operation_type": "download",
            "file_path": "/test/file.txt",
            "error_details": "Timeout",
            "retry_count": 2,
            "status": "pending"
        })
        mock_redis.lrange.return_value = [mock_entry]

        operations = await dead_letter_queue.get_failed_operations(limit=10)

        assert len(operations) == 1
        assert operations[0]["operation_type"] == "download"

    @pytest.mark.asyncio
    async def test_get_queue_size(self, dead_letter_queue, mock_redis):
        """Test getting queue size"""
        mock_redis.llen.return_value = 5

        size = await dead_letter_queue.get_queue_size()

        assert size == 5
        mock_redis.llen.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_queue(self, dead_letter_queue, mock_redis):
        """Test clearing the queue"""
        mock_redis.llen.return_value = 3

        cleared = await dead_letter_queue.clear_queue()

        assert cleared == 3
        mock_redis.delete.assert_called_once()


# =============================================================================
# RESILIENT SERVICE TESTS
# =============================================================================

class TestResilientB2StorageService:
    """Test resilient B2 storage service"""

    def test_service_initialization(self, resilient_service):
        """Test service initializes with correct defaults"""
        assert resilient_service.max_retries == DEFAULT_MAX_RETRIES
        assert resilient_service.b2_service is not None
        assert resilient_service.dead_letter_queue is not None

    def test_get_stats(self, resilient_service):
        """Test service statistics retrieval"""
        stats = resilient_service.get_stats()

        assert "uploads_successful" in stats
        assert "uploads_failed" in stats
        assert "downloads_successful" in stats
        assert "downloads_failed" in stats
        assert stats["service_name"] == "ResilientB2StorageService"

    @pytest.mark.asyncio
    async def test_upload_file_success(self, resilient_service, mock_b2_service, sample_file_content):
        """Test successful file upload"""
        mock_b2_service.upload_file.return_value = {
            "file_id": "file123",
            "file_name": "test.txt",
            "size": len(sample_file_content)
        }

        file_data = BytesIO(sample_file_content)

        result = await resilient_service.upload_file(
            file_data=file_data,
            filename="test.txt",
            verify_checksum=False
        )

        assert result["file_id"] == "file123"
        mock_b2_service.upload_file.assert_called_once()
        assert resilient_service._stats["uploads_successful"] == 1

    @pytest.mark.asyncio
    async def test_upload_file_retry_on_error(self, resilient_service, mock_b2_service, sample_file_content):
        """Test upload retries on transient error then succeeds"""
        # First call fails, second succeeds
        mock_b2_service.upload_file.side_effect = [
            B2ConnectionError("Connection failed"),
            {"file_id": "file123", "file_name": "test.txt", "size": 100}
        ]

        file_data = BytesIO(sample_file_content)

        result = await resilient_service.upload_file(
            file_data=file_data,
            filename="test.txt",
            verify_checksum=False
        )

        assert result["file_id"] == "file123"
        assert mock_b2_service.upload_file.call_count == 2

    @pytest.mark.asyncio
    async def test_upload_file_exhausted_retries(self, resilient_service, mock_b2_service, mock_redis, sample_file_content):
        """Test upload adds to DLQ after exhausting retries"""
        # Reduce retries for faster test
        resilient_service.max_retries = 2

        # All calls fail
        mock_b2_service.upload_file.side_effect = B2ConnectionError("Connection failed")

        file_data = BytesIO(sample_file_content)

        with pytest.raises(B2RetryExhaustedException) as exc_info:
            await resilient_service.upload_file(
                file_data=file_data,
                filename="test.txt",
                verify_checksum=False
            )

        assert exc_info.value.error_code == "B2_RETRY_EXHAUSTED"
        assert resilient_service._stats["uploads_failed"] == 1
        # DLQ should have been called
        mock_redis.lpush.assert_called()

    @pytest.mark.asyncio
    async def test_download_file_success(self, resilient_service, mock_b2_service):
        """Test successful file download"""
        # Mock returns dict matching what the service would return
        mock_b2_service.download_file.return_value = {"success": True, "file_path": "/tmp/test.txt"}

        with patch('os.path.exists', return_value=True):
            with patch('app.services.b2_resilient_storage.calculate_sha1_file', return_value="abc123"):
                result = await resilient_service.download_file(
                    file_id="file123",
                    file_name="test.txt",
                    destination_path="/tmp/test.txt",
                    verify_checksum=True  # Enable checksum verification to get proper result dict
                )

        assert result["success"] is True
        mock_b2_service.download_file.assert_called_once()
        assert resilient_service._stats["downloads_successful"] == 1


# =============================================================================
# EXCEPTION TESTS
# =============================================================================

class TestB2Exceptions:
    """Test B2-specific exception classes"""

    def test_checksum_mismatch_exception(self):
        """Test ChecksumMismatchException"""
        exc = ChecksumMismatchException(
            message="Checksum failed",
            file_path="/test/file.txt",
            expected_checksum="expected123",
            actual_checksum="actual456"
        )

        assert exc.error_code == "CHECKSUM_MISMATCH"
        assert exc.retriable is False
        assert "expected123" in str(exc.details.get("expected_checksum", ""))
        assert "actual456" in str(exc.details.get("actual_checksum", ""))

    def test_dead_letter_queue_exception(self):
        """Test DeadLetterQueueException"""
        exc = DeadLetterQueueException(
            message="DLQ operation failed",
            operation_type="add",
            queue_name="test_queue"
        )

        assert exc.error_code == "DEAD_LETTER_QUEUE_ERROR"
        assert exc.details.get("dlq_operation") == "add"
        assert exc.details.get("queue_name") == "test_queue"

    def test_b2_retry_exhausted_exception(self):
        """Test B2RetryExhaustedException"""
        exc = B2RetryExhaustedException(
            message="All retries failed",
            operation="upload",
            file_path="/test/file.txt",
            retry_count=5,
            last_error="Connection timeout"
        )

        assert exc.error_code == "B2_RETRY_EXHAUSTED"
        assert exc.retriable is False
        assert exc.details.get("retry_count") == 5
        assert exc.details.get("last_error") == "Connection timeout"


# =============================================================================
# CELERY TASK TESTS
# =============================================================================

class TestCeleryTasks:
    """Test Celery maintenance tasks"""

    def test_task_imports(self):
        """Test that task module imports correctly"""
        from app.tasks.b2_maintenance_tasks import (
            process_b2_dead_letter_queue,
            update_b2_storage_metrics,
            recover_b2_orphaned_files,
            b2_full_maintenance
        )

        assert process_b2_dead_letter_queue is not None
        assert update_b2_storage_metrics is not None
        assert recover_b2_orphaned_files is not None
        assert b2_full_maintenance is not None

    @patch('app.services.b2_resilient_storage.get_resilient_b2_service')
    def test_process_dlq_task(self, mock_get_service):
        """Test DLQ processing task"""
        from app.tasks.b2_maintenance_tasks import process_b2_dead_letter_queue

        # Setup mock
        mock_service = MagicMock()

        async def mock_process_dlq(*args, **kwargs):
            return {
                "processed": 5,
                "succeeded": 3,
                "failed": 2
            }

        mock_service.process_dead_letter_queue = mock_process_dlq
        mock_get_service.return_value = mock_service

        # Use run() method to test Celery task directly (standard approach for bound tasks)
        result = process_b2_dead_letter_queue.run(
            batch_size=10,
            max_retry_count=10
        )

        assert result["success"] is True
        assert result["processed"] == 5
        assert result["succeeded"] == 3


# =============================================================================
# INTEGRATION TESTS (MOCK-BASED)
# =============================================================================

class TestIntegration:
    """Integration tests with mocked external services"""

    @pytest.mark.asyncio
    async def test_full_upload_flow_with_checksum(self, resilient_service, mock_b2_service, sample_file_content):
        """Test complete upload flow with checksum verification"""
        expected_checksum = calculate_sha1(sample_file_content)

        mock_b2_service.upload_file.return_value = {
            "file_id": "file123",
            "file_name": "test.txt",
            "size": len(sample_file_content),
            "content_sha1": expected_checksum
        }

        file_data = BytesIO(sample_file_content)

        result = await resilient_service.upload_file(
            file_data=file_data,
            filename="test.txt",
            verify_checksum=True
        )

        assert result["file_id"] == "file123"
        assert result.get("checksum_verified") is True
        assert resilient_service._stats["checksum_verifications"] == 1

    @pytest.mark.asyncio
    async def test_upload_flow_with_checksum_mismatch(self, resilient_service, mock_b2_service, sample_file_content):
        """Test upload detects checksum mismatch"""
        mock_b2_service.upload_file.return_value = {
            "file_id": "file123",
            "file_name": "test.txt",
            "size": len(sample_file_content),
            "content_sha1": "wrong_checksum"
        }

        file_data = BytesIO(sample_file_content)

        with pytest.raises(ChecksumMismatchException):
            await resilient_service.upload_file(
                file_data=file_data,
                filename="test.txt",
                verify_checksum=True
            )

    def test_singleton_pattern(self):
        """Test service singleton works correctly"""
        with patch('app.services.b2_resilient_storage.get_b2_service'):
            with patch('app.services.b2_resilient_storage.get_redis'):
                # Reset singleton
                import app.services.b2_resilient_storage as module
                module._resilient_b2_service = None

                service1 = get_resilient_b2_service()
                service2 = get_resilient_b2_service()

                assert service1 is service2
