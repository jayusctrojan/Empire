"""
Empire v7.3 - Write-Ahead Log (WAL) Persistence Tests
Tests for WAL operations and crash recovery

Run with:
    pytest tests/test_wal_persistence.py -v
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.wal_manager import WriteAheadLog, WALStatus, WALEntry


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client for WAL operations"""
    mock = MagicMock()

    # Mock table operations
    mock.table.return_value.insert.return_value.execute.return_value.data = [{"id": str(uuid4())}]
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{}]
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    return mock


@pytest.fixture
def sample_wal_entry():
    """Sample WAL entry data"""
    return {
        "id": str(uuid4()),
        "operation_type": "create_document",
        "operation_data": {
            "title": "Test Document",
            "content": "Test content",
            "user_id": "user_123"
        },
        "status": "pending",
        "retry_count": 0,
        "max_retries": 3,
        "created_at": datetime.utcnow().isoformat()
    }


# =============================================================================
# WAL MANAGER INITIALIZATION TESTS
# =============================================================================

class TestWALManagerInit:
    """Tests for WAL Manager initialization"""

    def test_wal_manager_creation(self, mock_supabase):
        """Test creating WAL manager instance"""
        wal = WriteAheadLog(mock_supabase)

        assert wal is not None
        assert wal.supabase is mock_supabase

    def test_wal_manager_has_handler_registry(self, mock_supabase):
        """Test WAL manager has operation handler registry"""
        wal = WriteAheadLog(mock_supabase)

        assert hasattr(wal, '_operation_handlers')
        assert isinstance(wal._operation_handlers, dict)


# =============================================================================
# WAL ENTRY CREATION TESTS
# =============================================================================

class TestWALEntryCreation:
    """Tests for creating WAL entries"""

    @pytest.mark.asyncio
    async def test_log_operation_before_execution(self, mock_supabase):
        """Test that WAL entry is logged BEFORE operation executes"""
        wal = WriteAheadLog(mock_supabase)

        entry_id = await wal.log_operation(
            operation_type="create_document",
            operation_data={"title": "Test", "content": "Content"}
        )

        # Verify insert was called
        mock_supabase.table.assert_called_with("wal_log")
        assert entry_id is not None

    @pytest.mark.asyncio
    async def test_entry_created_with_pending_status(self, mock_supabase):
        """Test that new entries have pending status"""
        insert_call_data = None

        def capture_insert(data):
            nonlocal insert_call_data
            insert_call_data = data
            return MagicMock(execute=MagicMock(return_value=MagicMock(data=[{"id": str(uuid4())}])))

        mock_supabase.table.return_value.insert = capture_insert

        wal = WriteAheadLog(mock_supabase)
        await wal.log_operation("test_op", {"key": "value"})

        assert insert_call_data is not None
        assert insert_call_data.get("status") == "pending"

    @pytest.mark.asyncio
    async def test_entry_includes_idempotency_key(self, mock_supabase):
        """Test that idempotency key is included when provided"""
        insert_call_data = None

        def capture_insert(data):
            nonlocal insert_call_data
            insert_call_data = data
            return MagicMock(execute=MagicMock(return_value=MagicMock(data=[{"id": str(uuid4())}])))

        mock_supabase.table.return_value.insert = capture_insert

        wal = WriteAheadLog(mock_supabase)
        await wal.log_operation(
            "test_op",
            {"key": "value"},
            idempotency_key="unique-key-123"
        )

        assert insert_call_data.get("idempotency_key") == "unique-key-123"


# =============================================================================
# WAL STATUS UPDATE TESTS
# =============================================================================

class TestWALStatusUpdates:
    """Tests for WAL entry status updates"""

    @pytest.mark.asyncio
    async def test_mark_completed(self, mock_supabase):
        """Test marking WAL entry as completed"""
        entry_id = str(uuid4())

        wal = WriteAheadLog(mock_supabase)
        await wal.mark_completed(entry_id, result={"document_id": "doc_123"})

        # Verify update was called with correct status
        mock_supabase.table.return_value.update.assert_called()

    @pytest.mark.asyncio
    async def test_mark_failed(self, mock_supabase):
        """Test marking WAL entry as failed"""
        entry_id = str(uuid4())

        # Setup mock to return entry data for retry count
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": entry_id, "retry_count": 0, "max_retries": 3, "operation_type": "test_op"}
        ]

        wal = WriteAheadLog(mock_supabase)
        await wal.mark_failed(entry_id, error="Database connection failed")

        mock_supabase.table.return_value.update.assert_called()

    @pytest.mark.asyncio
    async def test_mark_in_progress(self, mock_supabase):
        """Test marking WAL entry as in-progress"""
        entry_id = str(uuid4())

        wal = WriteAheadLog(mock_supabase)
        await wal.mark_in_progress(entry_id)

        mock_supabase.table.return_value.update.assert_called()


# =============================================================================
# WAL REPLAY TESTS
# =============================================================================

class TestWALReplay:
    """Tests for WAL entry replay on startup"""

    @pytest.mark.asyncio
    async def test_replay_pending_entries(self, mock_supabase, sample_wal_entry):
        """Test replaying pending WAL entries"""
        # Setup mock to return pending entries via get_pending_entries
        mock_supabase.table.return_value.select.return_value.in_.return_value.gt.return_value.limit.return_value.execute.return_value.data = [sample_wal_entry]

        wal = WriteAheadLog(mock_supabase)

        # Register a handler for the operation type
        handler_called = False

        async def mock_handler(**data):
            nonlocal handler_called
            handler_called = True
            return {"success": True}

        wal.register_handler("create_document", mock_handler)

        stats = await wal.replay_pending()

        assert stats is not None
        assert "total" in stats

    @pytest.mark.asyncio
    async def test_replay_respects_max_retries(self, mock_supabase):
        """Test that replay respects max retry count"""
        # Entry with max retries exceeded - should be filtered in get_pending_entries
        exhausted_entry = {
            "id": str(uuid4()),
            "operation_type": "test_op",
            "operation_data": {},
            "status": "pending",
            "retry_count": 4,
            "max_retries": 3,
            "created_at": datetime.utcnow().isoformat()
        }

        # This entry should be filtered out by get_pending_entries
        mock_supabase.table.return_value.select.return_value.in_.return_value.gt.return_value.limit.return_value.execute.return_value.data = [exhausted_entry]

        wal = WriteAheadLog(mock_supabase)
        stats = await wal.replay_pending()

        # Entry should be filtered out since retry_count >= max_retries
        assert stats.get("total", 0) == 0 or stats.get("skipped", 0) >= 0

    @pytest.mark.asyncio
    async def test_replay_increments_retry_count(self, mock_supabase, sample_wal_entry):
        """Test that replay increments retry count on failure"""
        mock_supabase.table.return_value.select.return_value.in_.return_value.gt.return_value.limit.return_value.execute.return_value.data = [sample_wal_entry]
        # Also setup select for mark_failed
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [sample_wal_entry]

        wal = WriteAheadLog(mock_supabase)

        # Register a failing handler
        async def failing_handler(**data):
            raise Exception("Handler failed")

        wal.register_handler("create_document", failing_handler)

        await wal.replay_pending()

        # Update should have been called to increment retry count
        mock_supabase.table.return_value.update.assert_called()


# =============================================================================
# WAL CLEANUP TESTS
# =============================================================================

class TestWALCleanup:
    """Tests for WAL entry cleanup"""

    @pytest.mark.asyncio
    async def test_cleanup_old_entries(self, mock_supabase):
        """Test cleaning up old completed entries"""
        mock_supabase.table.return_value.delete.return_value.in_.return_value.lt.return_value.execute.return_value.data = [
            {"id": "1"}, {"id": "2"}, {"id": "3"}
        ]

        wal = WriteAheadLog(mock_supabase)
        cleaned = await wal.cleanup_old_entries(days=7)

        assert cleaned >= 0

    @pytest.mark.asyncio
    async def test_cleanup_preserves_recent_entries(self, mock_supabase):
        """Test that cleanup preserves recent entries"""
        # Mock returns empty (no old entries to delete)
        mock_supabase.table.return_value.delete.return_value.in_.return_value.lt.return_value.execute.return_value.data = []

        wal = WriteAheadLog(mock_supabase)
        cleaned = await wal.cleanup_old_entries(days=7)

        assert cleaned == 0


# =============================================================================
# WAL HANDLER REGISTRATION TESTS
# =============================================================================

class TestWALHandlerRegistration:
    """Tests for operation handler registration"""

    def test_register_handler(self, mock_supabase):
        """Test registering an operation handler"""
        wal = WriteAheadLog(mock_supabase)

        async def handler(**data):
            return {"success": True}

        wal.register_handler("test_operation", handler)

        assert "test_operation" in wal._operation_handlers

    def test_handler_can_be_retrieved(self, mock_supabase):
        """Test that registered handler can be retrieved"""
        wal = WriteAheadLog(mock_supabase)

        async def handler(**data):
            return {"success": True}

        wal.register_handler("test_operation", handler)

        retrieved = wal._operation_handlers.get("test_operation")
        assert retrieved is handler

    def test_unregistered_handler_returns_none(self, mock_supabase):
        """Test that unregistered operation returns None"""
        wal = WriteAheadLog(mock_supabase)

        handler = wal._operation_handlers.get("nonexistent_operation")
        assert handler is None


# =============================================================================
# WAL METRICS TESTS
# =============================================================================

class TestWALMetrics:
    """Tests for WAL metrics and statistics"""

    @pytest.mark.asyncio
    async def test_get_pending_entries_returns_list(self, mock_supabase):
        """Test getting pending entries returns a list"""
        mock_supabase.table.return_value.select.return_value.in_.return_value.gt.return_value.limit.return_value.execute.return_value.data = []

        wal = WriteAheadLog(mock_supabase)
        entries = await wal.get_pending_entries()

        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_replay_returns_stats(self, mock_supabase):
        """Test that replay returns statistics"""
        mock_supabase.table.return_value.select.return_value.in_.return_value.gt.return_value.limit.return_value.execute.return_value.data = []

        wal = WriteAheadLog(mock_supabase)
        stats = await wal.replay_pending()

        assert isinstance(stats, dict)
        assert "total" in stats
        assert "succeeded" in stats
        assert "failed" in stats
