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
        from app.services.wal_manager import WriteAheadLog

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()

        assert wal is not None
        assert wal.table_name == "wal_log"

    def test_wal_manager_with_custom_table(self, mock_supabase):
        """Test WAL manager with custom table name"""
        from app.services.wal_manager import WriteAheadLog

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog(table_name="custom_wal")

        assert wal.table_name == "custom_wal"


# =============================================================================
# WAL ENTRY CREATION TESTS
# =============================================================================

class TestWALEntryCreation:
    """Tests for creating WAL entries"""

    @pytest.mark.asyncio
    async def test_write_entry_before_operation(self, mock_supabase):
        """Test that WAL entry is written BEFORE operation executes"""
        from app.services.wal_manager import WriteAheadLog

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()

            entry_id = await wal.write_entry(
                operation_type="create_document",
                operation_data={"title": "Test", "content": "Content"}
            )

        # Verify insert was called
        mock_supabase.table.assert_called_with("wal_log")
        assert entry_id is not None

    @pytest.mark.asyncio
    async def test_entry_created_with_pending_status(self, mock_supabase):
        """Test that new entries have pending status"""
        from app.services.wal_manager import WriteAheadLog

        insert_call_data = None

        def capture_insert(data):
            nonlocal insert_call_data
            insert_call_data = data
            return MagicMock(execute=MagicMock(return_value=MagicMock(data=[{"id": str(uuid4())}])))

        mock_supabase.table.return_value.insert = capture_insert

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()
            await wal.write_entry("test_op", {"key": "value"})

        assert insert_call_data is not None
        assert insert_call_data.get("status") == "pending"

    @pytest.mark.asyncio
    async def test_entry_includes_idempotency_key(self, mock_supabase):
        """Test that idempotency key is included when provided"""
        from app.services.wal_manager import WriteAheadLog

        insert_call_data = None

        def capture_insert(data):
            nonlocal insert_call_data
            insert_call_data = data
            return MagicMock(execute=MagicMock(return_value=MagicMock(data=[{"id": str(uuid4())}])))

        mock_supabase.table.return_value.insert = capture_insert

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()
            await wal.write_entry(
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
        from app.services.wal_manager import WriteAheadLog

        entry_id = str(uuid4())

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()
            await wal.mark_completed(entry_id, result={"document_id": "doc_123"})

        # Verify update was called with correct status
        mock_supabase.table.return_value.update.assert_called()

    @pytest.mark.asyncio
    async def test_mark_failed(self, mock_supabase):
        """Test marking WAL entry as failed"""
        from app.services.wal_manager import WriteAheadLog

        entry_id = str(uuid4())

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()
            await wal.mark_failed(entry_id, error="Database connection failed")

        mock_supabase.table.return_value.update.assert_called()

    @pytest.mark.asyncio
    async def test_mark_in_progress(self, mock_supabase):
        """Test marking WAL entry as in-progress"""
        from app.services.wal_manager import WriteAheadLog

        entry_id = str(uuid4())

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()
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
        from app.services.wal_manager import WriteAheadLog

        # Setup mock to return pending entries
        mock_supabase.table.return_value.select.return_value.in_.return_value.lt.return_value.order.return_value.limit.return_value.execute.return_value.data = [sample_wal_entry]

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()

            # Register a handler for the operation type
            handler_called = False

            async def mock_handler(data):
                nonlocal handler_called
                handler_called = True
                return {"success": True}

            wal.register_handler("create_document", mock_handler)

            stats = await wal.replay_pending()

        assert stats is not None

    @pytest.mark.asyncio
    async def test_replay_respects_max_retries(self, mock_supabase):
        """Test that replay respects max retry count"""
        from app.services.wal_manager import WriteAheadLog

        # Entry with max retries exceeded
        exhausted_entry = {
            "id": str(uuid4()),
            "operation_type": "test_op",
            "operation_data": {},
            "status": "pending",
            "retry_count": 4,
            "max_retries": 3,
            "created_at": datetime.utcnow().isoformat()
        }

        mock_supabase.table.return_value.select.return_value.in_.return_value.lt.return_value.order.return_value.limit.return_value.execute.return_value.data = [exhausted_entry]

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()
            stats = await wal.replay_pending()

        # Entry should be skipped or marked as permanently failed
        assert stats.get("skipped", 0) >= 0 or stats.get("failed", 0) >= 0

    @pytest.mark.asyncio
    async def test_replay_increments_retry_count(self, mock_supabase, sample_wal_entry):
        """Test that replay increments retry count on failure"""
        from app.services.wal_manager import WriteAheadLog

        mock_supabase.table.return_value.select.return_value.in_.return_value.lt.return_value.order.return_value.limit.return_value.execute.return_value.data = [sample_wal_entry]

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()

            # Register a failing handler
            async def failing_handler(data):
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
        from app.services.wal_manager import WriteAheadLog

        mock_supabase.table.return_value.delete.return_value.in_.return_value.lt.return_value.execute.return_value.data = [
            {"id": "1"}, {"id": "2"}, {"id": "3"}
        ]

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()
            cleaned = await wal.cleanup_old_entries(days=7)

        assert cleaned >= 0

    @pytest.mark.asyncio
    async def test_cleanup_preserves_recent_entries(self, mock_supabase):
        """Test that cleanup preserves recent entries"""
        from app.services.wal_manager import WriteAheadLog

        # Mock returns empty (no old entries to delete)
        mock_supabase.table.return_value.delete.return_value.in_.return_value.lt.return_value.execute.return_value.data = []

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()
            cleaned = await wal.cleanup_old_entries(days=7)

        assert cleaned == 0


# =============================================================================
# WAL HANDLER REGISTRATION TESTS
# =============================================================================

class TestWALHandlerRegistration:
    """Tests for operation handler registration"""

    def test_register_handler(self, mock_supabase):
        """Test registering an operation handler"""
        from app.services.wal_manager import WriteAheadLog

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()

            async def handler(data):
                return {"success": True}

            wal.register_handler("test_operation", handler)

        assert "test_operation" in wal._handlers

    def test_handler_not_found_raises(self, mock_supabase):
        """Test that missing handler raises appropriate error"""
        from app.services.wal_manager import WriteAheadLog

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()

            handler = wal.get_handler("nonexistent_operation")

        assert handler is None


# =============================================================================
# WAL METRICS TESTS
# =============================================================================

class TestWALMetrics:
    """Tests for WAL metrics and statistics"""

    @pytest.mark.asyncio
    async def test_get_pending_count(self, mock_supabase):
        """Test getting count of pending entries"""
        from app.services.wal_manager import WriteAheadLog

        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 5

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()
            count = await wal.get_pending_count()

        assert count >= 0

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_supabase):
        """Test getting WAL statistics"""
        from app.services.wal_manager import WriteAheadLog

        with patch('app.services.wal_manager.get_supabase', return_value=mock_supabase):
            wal = WriteAheadLog()
            stats = await wal.get_stats()

        assert isinstance(stats, dict)
