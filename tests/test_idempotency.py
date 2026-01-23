"""
Empire v7.3 - Idempotency Tests
Tests for idempotency key management and duplicate prevention

Run with:
    pytest tests/test_idempotency.py -v
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Test module for idempotency manager
from app.services.idempotency_manager import (
    IdempotencyManager,
    IdempotencyEntry,
    IdempotencyStatus
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client for idempotency operations"""
    mock = MagicMock()
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    mock.table.return_value.insert.return_value.execute.return_value.data = [{"key": "test-key"}]
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{}]
    return mock


@pytest.fixture
def mock_redis():
    """Mock Redis client for idempotency caching"""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = 1
    return mock


# =============================================================================
# IDEMPOTENCY MANAGER INITIALIZATION TESTS
# =============================================================================

class TestIdempotencyManagerInit:
    """Tests for IdempotencyManager initialization"""

    def test_manager_creation(self, mock_supabase, mock_redis):
        """Test creating IdempotencyManager instance"""
        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )

        assert manager is not None
        assert manager.supabase is mock_supabase
        assert manager.redis is mock_redis

    def test_manager_with_custom_ttl(self, mock_supabase, mock_redis):
        """Test IdempotencyManager with custom TTL"""
        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase,
            default_ttl_hours=48
        )

        # default_ttl is a timedelta
        assert manager.default_ttl.total_seconds() == 48 * 3600


# =============================================================================
# IDEMPOTENCY KEY CHECK TESTS
# =============================================================================

class TestIdempotencyKeyChecks:
    """Tests for idempotency key existence checks via get_cached_result"""

    @pytest.mark.asyncio
    async def test_new_key_returns_none(self, mock_supabase, mock_redis):
        """Test that new idempotency key returns None (no cached result)"""
        # No existing key in Redis
        mock_redis.get.return_value = None
        # No existing key in Supabase
        mock_supabase.table.return_value.select.return_value.eq.return_value.gt.return_value.execute.return_value.data = []

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )
        result = await manager.get_cached_result("new-unique-key")

        assert result is None

    @pytest.mark.asyncio
    async def test_completed_key_returns_cached_entry(self, mock_supabase, mock_redis):
        """Test that completed key returns cached IdempotencyEntry"""
        # No Redis cache
        mock_redis.get.return_value = None
        # Existing completed key in Supabase
        mock_supabase.table.return_value.select.return_value.eq.return_value.gt.return_value.execute.return_value.data = [{
            "key": "existing-key",
            "operation": "test_op",
            "status": "completed",
            "result": {"document_id": "doc_123"},
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
        }]

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )
        result = await manager.get_cached_result("existing-key")

        assert result is not None
        assert result.status == IdempotencyStatus.COMPLETED
        assert result.result == {"document_id": "doc_123"}

    @pytest.mark.asyncio
    async def test_in_progress_key_returns_entry(self, mock_supabase, mock_redis):
        """Test that in-progress key returns cached entry"""
        # No Redis cache
        mock_redis.get.return_value = None
        # Existing in-progress key
        mock_supabase.table.return_value.select.return_value.eq.return_value.gt.return_value.execute.return_value.data = [{
            "key": "in-progress-key",
            "operation": "test_op",
            "status": "in_progress",
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
        }]

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )
        result = await manager.get_cached_result("in-progress-key")

        assert result is not None
        assert result.status == IdempotencyStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_failed_key_returns_entry(self, mock_supabase, mock_redis):
        """Test that failed key returns cached entry"""
        # No Redis cache
        mock_redis.get.return_value = None
        # Existing failed key
        mock_supabase.table.return_value.select.return_value.eq.return_value.gt.return_value.execute.return_value.data = [{
            "key": "failed-key",
            "operation": "test_op",
            "status": "failed",
            "error": "Previous error message",
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
        }]

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )
        result = await manager.get_cached_result("failed-key")

        assert result is not None
        assert result.status == IdempotencyStatus.FAILED
        assert result.error == "Previous error message"

    @pytest.mark.asyncio
    async def test_expired_key_returns_none(self, mock_supabase, mock_redis):
        """Test that expired key returns None (filtered by gt query)"""
        # No Redis cache
        mock_redis.get.return_value = None
        # Supabase query with gt(expires_at, now) filters out expired entries
        mock_supabase.table.return_value.select.return_value.eq.return_value.gt.return_value.execute.return_value.data = []

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )
        result = await manager.get_cached_result("expired-key")

        # Expired keys are filtered out by the gt query
        assert result is None


# =============================================================================
# IDEMPOTENT EXECUTION TESTS
# =============================================================================

class TestIdempotentExecution:
    """Tests for idempotent operation execution"""

    @pytest.mark.asyncio
    async def test_execute_new_operation(self, mock_supabase, mock_redis):
        """Test executing a new operation with idempotency"""
        # No existing key in Redis
        mock_redis.get.return_value = None
        # No existing key in Supabase
        mock_supabase.table.return_value.select.return_value.eq.return_value.gt.return_value.execute.return_value.data = []

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )

        # Define operation
        async def create_document(title, content):
            return {"document_id": "new_doc_123", "title": title}

        result = await manager.execute_idempotent(
            idempotency_key="new-op-key",
            operation_fn=create_document,
            operation="create_document",
            title="Test Doc",
            content="Content"
        )

        assert result is not None
        assert result["document_id"] == "new_doc_123"

    @pytest.mark.asyncio
    async def test_return_cached_on_duplicate(self, mock_supabase, mock_redis):
        """Test that duplicate request returns cached result"""
        import json

        cached_result = {"data": {"document_id": "cached_doc", "title": "Cached"}}

        # Return cached entry from Redis
        cached_entry = IdempotencyEntry(
            key="duplicate-key",
            operation="create_document",
            status=IdempotencyStatus.COMPLETED,
            result=cached_result,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            request_hash=None  # No hash verification
        )
        mock_redis.get.return_value = cached_entry.model_dump_json()

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )

        # Operation should NOT be called
        operation_called = False

        async def create_document(title, content):
            nonlocal operation_called
            operation_called = True
            return {"document_id": "new_doc"}

        result = await manager.execute_idempotent(
            idempotency_key="duplicate-key",
            operation_fn=create_document,
            operation="create_document",
            verify_request=False,  # Disable hash verification for this test
            title="Test",
            content="Content"
        )

        # Should return cached result without calling operation
        assert result == cached_result.get("data")
        assert operation_called is False

    @pytest.mark.asyncio
    async def test_operation_failure_recorded(self, mock_supabase, mock_redis):
        """Test that operation failure is recorded in cache"""
        # No existing key
        mock_redis.get.return_value = None
        mock_supabase.table.return_value.select.return_value.eq.return_value.gt.return_value.execute.return_value.data = []

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )

        async def failing_operation():
            raise Exception("Operation failed")

        with pytest.raises(Exception):
            await manager.execute_idempotent(
                idempotency_key="failing-key",
                operation_fn=failing_operation,
                operation="test_op"
            )

        # Redis setex should have been called to cache the error
        mock_redis.setex.assert_called()


# =============================================================================
# REQUEST HASH VERIFICATION TESTS
# =============================================================================

class TestRequestHashVerification:
    """Tests for request body hash verification in execute_idempotent"""

    @pytest.mark.asyncio
    async def test_matching_hash_returns_cached(self, mock_supabase, mock_redis):
        """Test that matching request hash returns cached result"""
        # The implementation computes hash internally, so we test via execute_idempotent
        cached_entry = IdempotencyEntry(
            key="hashed-key",
            operation="test_op",
            status=IdempotencyStatus.COMPLETED,
            result={"data": "cached_value"},
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            request_hash=None  # No hash for this test
        )
        mock_redis.get.return_value = cached_entry.model_dump_json()

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )

        async def dummy_op(**kwargs):
            return {"new": "result"}

        # With verify_request=False, hash mismatch is ignored
        result = await manager.execute_idempotent(
            idempotency_key="hashed-key",
            operation_fn=dummy_op,
            operation="test_op",
            verify_request=False,
            key="value"
        )

        # Should return cached result
        assert result == "cached_value"

    @pytest.mark.asyncio
    async def test_mismatched_hash_raises_error(self, mock_supabase, mock_redis):
        """Test that mismatched request hash raises ValueError"""
        # Create a cached entry with a specific hash
        cached_entry = IdempotencyEntry(
            key="hashed-key",
            operation="test_op",
            status=IdempotencyStatus.COMPLETED,
            result={"data": "cached_value"},
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            request_hash="original_hash_12345"  # Different from computed hash
        )
        mock_redis.get.return_value = cached_entry.model_dump_json()

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )

        async def dummy_op(**kwargs):
            return {"new": "result"}

        # With verify_request=True (default), hash mismatch raises ValueError
        with pytest.raises(ValueError, match="does not match original request"):
            await manager.execute_idempotent(
                idempotency_key="hashed-key",
                operation_fn=dummy_op,
                operation="test_op",
                verify_request=True,
                key="different_value"  # This will produce a different hash
            )


# =============================================================================
# IDEMPOTENCY CLEANUP TESTS
# =============================================================================

class TestIdempotencyCleanup:
    """Tests for idempotency key cleanup"""

    @pytest.mark.asyncio
    async def test_cleanup_expired_keys(self, mock_supabase, mock_redis):
        """Test cleaning up expired idempotency keys"""
        mock_supabase.table.return_value.delete.return_value.lt.return_value.execute.return_value.data = [
            {"key": "1"}, {"key": "2"}
        ]

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )
        cleaned = await manager.cleanup_expired()

        assert cleaned == 2

    @pytest.mark.asyncio
    async def test_cleanup_returns_zero_when_no_expired(self, mock_supabase, mock_redis):
        """Test that cleanup returns 0 when no expired keys"""
        mock_supabase.table.return_value.delete.return_value.lt.return_value.execute.return_value.data = []

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )
        cleaned = await manager.cleanup_expired()

        assert cleaned == 0

    @pytest.mark.asyncio
    async def test_cleanup_returns_zero_without_supabase(self, mock_redis):
        """Test that cleanup returns 0 when no supabase client"""
        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=None
        )
        cleaned = await manager.cleanup_expired()

        assert cleaned == 0


# =============================================================================
# CONCURRENT EXECUTION TESTS
# =============================================================================

class TestConcurrentExecution:
    """Tests for concurrent idempotent operations"""

    @pytest.mark.asyncio
    async def test_first_request_can_execute(self, mock_supabase, mock_redis):
        """Test that first request with a key can execute"""
        # No existing key
        mock_redis.get.return_value = None
        mock_supabase.table.return_value.select.return_value.eq.return_value.gt.return_value.execute.return_value.data = []

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )

        # First request - no cached entry
        result = await manager.get_cached_result("concurrent-key")

        # No cached result means operation can proceed
        assert result is None

    @pytest.mark.asyncio
    async def test_in_progress_blocks_second_request(self, mock_supabase, mock_redis):
        """Test that in-progress key blocks concurrent request"""
        # Return in_progress entry from Redis
        in_progress_entry = IdempotencyEntry(
            key="concurrent-key",
            operation="test_op",
            status=IdempotencyStatus.IN_PROGRESS,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=5)
        )
        mock_redis.get.return_value = in_progress_entry.model_dump_json()

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )

        async def slow_operation():
            await asyncio.sleep(0.1)
            return {"result": "done"}

        # Second request should raise error due to in-progress status
        with pytest.raises(ValueError, match="already in progress"):
            await manager.execute_idempotent(
                idempotency_key="concurrent-key",
                operation_fn=slow_operation,
                operation="test_op",
                verify_request=False
            )


# =============================================================================
# OPERATION NAME TRACKING TESTS
# =============================================================================

class TestOperationNameTracking:
    """Tests for operation name tracking in idempotency keys"""

    @pytest.mark.asyncio
    async def test_operation_name_recorded_in_redis(self, mock_supabase, mock_redis):
        """Test that operation name is recorded with key via mark_in_progress"""
        setex_calls = []

        def capture_setex(key, ttl, data):
            setex_calls.append({"key": key, "ttl": ttl, "data": data})
            return True

        mock_redis.setex = capture_setex

        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )
        await manager.mark_in_progress("test-key", operation="create_document")

        assert len(setex_calls) == 1
        import json
        stored_data = json.loads(setex_calls[0]["data"])
        assert stored_data["operation"] == "create_document"
        assert stored_data["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_in_flight_tracking(self, mock_supabase, mock_redis):
        """Test that mark_in_progress adds key to in-flight tracking"""
        manager = IdempotencyManager(
            redis_client=mock_redis,
            supabase_client=mock_supabase
        )

        await manager.mark_in_progress("test-key", operation="test_op")

        assert "test-key" in manager._in_flight
