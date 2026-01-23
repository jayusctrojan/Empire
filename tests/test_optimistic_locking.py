"""
Empire v7.3 - Optimistic Locking Tests
Tests for race condition prevention with version numbers

Run with:
    pytest tests/test_optimistic_locking.py -v
"""

import asyncio
from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.optimistic_locking import (
    update_with_lock,
    update_with_retry,
    get_current_version,
    batch_update_with_lock,
    OptimisticLockException,
    RecordNotFoundException,
    LockResult
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client for optimistic locking operations"""
    mock = MagicMock()
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "doc_123", "version": 1, "title": "Original"}
    ]
    mock.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"id": "doc_123", "version": 2, "title": "Updated"}
    ]
    return mock


@pytest.fixture
def sample_document():
    """Sample document for testing"""
    return {
        "id": str(uuid4()),
        "title": "Test Document",
        "content": "Test content",
        "version": 1,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


# =============================================================================
# OPTIMISTIC LOCK INITIALIZATION TESTS
# =============================================================================

class TestOptimisticLockInit:
    """Tests for OptimisticLock module imports"""

    def test_functions_importable(self):
        """Test that optimistic locking functions are importable"""
        assert update_with_lock is not None
        assert update_with_retry is not None
        assert get_current_version is not None
        assert batch_update_with_lock is not None

    def test_exceptions_importable(self):
        """Test that exceptions are importable"""
        assert OptimisticLockException is not None
        assert RecordNotFoundException is not None


# =============================================================================
# VERSION CHECK TESTS
# =============================================================================

class TestVersionChecks:
    """Tests for version checking during updates"""

    @pytest.mark.asyncio
    async def test_update_with_correct_version(self, mock_supabase, sample_document):
        """Test successful update with correct version"""
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {**sample_document, "version": 2, "title": "Updated"}
        ]

        result = await update_with_lock(
            supabase=mock_supabase,
            table="documents_v2",
            record_id=sample_document["id"],
            expected_version=1,
            updates={"title": "Updated"}
        )

        assert result.success is True
        assert result.new_version == 2

    @pytest.mark.asyncio
    async def test_update_with_wrong_version_fails(self, mock_supabase, sample_document):
        """Test that update fails with wrong version"""
        # Return empty data to simulate version mismatch
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        # Select query returns current version (different from expected)
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": sample_document["id"], "version": 5}  # Actual version is 5
        ]

        with pytest.raises(OptimisticLockException) as exc_info:
            await update_with_lock(
                supabase=mock_supabase,
                table="documents_v2",
                record_id=sample_document["id"],
                expected_version=1,  # Expected 1 but actual is 5
                updates={"title": "Updated"}
            )

        assert exc_info.value.expected_version == 1
        assert exc_info.value.actual_version == 5

    @pytest.mark.asyncio
    async def test_concurrent_modification_detected(self, mock_supabase, sample_document):
        """Test that concurrent modification is detected"""
        # Update returns empty (version changed during update)
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        # Select query returns current version (different from expected)
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": sample_document["id"], "version": 2}
        ]

        with pytest.raises(OptimisticLockException):
            await update_with_lock(
                supabase=mock_supabase,
                table="documents_v2",
                record_id=sample_document["id"],
                expected_version=1,
                updates={"title": "Updated"}
            )


# =============================================================================
# VERSION INCREMENT TESTS
# =============================================================================

class TestVersionIncrement:
    """Tests for automatic version incrementing"""

    @pytest.mark.asyncio
    async def test_version_auto_incremented(self, mock_supabase, sample_document):
        """Test that version is automatically incremented on update"""
        update_data = None

        def capture_update(data):
            nonlocal update_data
            update_data = data
            return MagicMock(eq=MagicMock(return_value=MagicMock(eq=MagicMock(return_value=MagicMock(
                execute=MagicMock(return_value=MagicMock(data=[{**sample_document, "version": 2}]))
            )))))

        mock_supabase.table.return_value.update = capture_update

        await update_with_lock(
            supabase=mock_supabase,
            table="documents_v2",
            record_id=sample_document["id"],
            expected_version=1,
            updates={"title": "Updated"}
        )

        # Version should be incremented
        assert update_data is not None
        assert update_data.get("version") == 2

    @pytest.mark.asyncio
    async def test_version_returned_in_result(self, mock_supabase, sample_document):
        """Test that new version is returned in result"""
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {**sample_document, "version": 5}
        ]

        result = await update_with_lock(
            supabase=mock_supabase,
            table="documents_v2",
            record_id=sample_document["id"],
            expected_version=4,
            updates={"title": "Updated"}
        )

        assert result.success is True
        assert result.new_version == 5


# =============================================================================
# RECORD NOT FOUND TESTS
# =============================================================================

class TestRecordNotFound:
    """Tests for handling non-existent records"""

    @pytest.mark.asyncio
    async def test_update_nonexistent_record(self, mock_supabase):
        """Test updating a record that doesn't exist"""
        # No record found on select
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        with pytest.raises(RecordNotFoundException) as exc_info:
            await update_with_lock(
                supabase=mock_supabase,
                table="documents_v2",
                record_id="nonexistent_id",
                expected_version=1,
                updates={"title": "Updated"}
            )

        assert exc_info.value.record_id == "nonexistent_id"

    @pytest.mark.asyncio
    async def test_get_current_version_not_found(self, mock_supabase):
        """Test getting version of non-existent record"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        with pytest.raises(RecordNotFoundException):
            await get_current_version(
                supabase=mock_supabase,
                table="documents_v2",
                record_id="nonexistent"
            )


# =============================================================================
# RETRY LOGIC TESTS
# =============================================================================

class TestRetryLogic:
    """Tests for retry logic on version conflicts"""

    @pytest.mark.asyncio
    async def test_update_with_retry_succeeds(self, mock_supabase, sample_document):
        """Test update with automatic retry on version conflict"""
        call_count = 0

        def mock_update(data):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First attempt fails (version conflict)
                return MagicMock(eq=MagicMock(return_value=MagicMock(eq=MagicMock(return_value=MagicMock(
                    execute=MagicMock(return_value=MagicMock(data=[]))
                )))))
            else:
                # Retry succeeds
                return MagicMock(eq=MagicMock(return_value=MagicMock(eq=MagicMock(return_value=MagicMock(
                    execute=MagicMock(return_value=MagicMock(data=[{**sample_document, "version": 3}]))
                )))))

        mock_supabase.table.return_value.update = mock_update

        # Return different versions on each select
        select_count = 0

        def mock_select(*args):
            nonlocal select_count
            select_count += 1
            version = 1 if select_count % 2 == 1 else 2
            return MagicMock(eq=MagicMock(return_value=MagicMock(
                execute=MagicMock(return_value=MagicMock(data=[
                    {**sample_document, "version": version}
                ]))
            )))

        mock_supabase.table.return_value.select = mock_select

        result = await update_with_retry(
            supabase=mock_supabase,
            table="documents_v2",
            record_id=sample_document["id"],
            update_fn=lambda record: {"title": f"Updated {record['version']}"},
            max_retries=3,
            retry_delay=0.01  # Fast retry for tests
        )

        # Should succeed on retry
        assert result.success is True

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, mock_supabase, sample_document):
        """Test that update fails after max retries exceeded"""
        # Always return empty (continuous conflicts)
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {**sample_document, "version": 1}
        ]

        with pytest.raises(OptimisticLockException):
            await update_with_retry(
                supabase=mock_supabase,
                table="documents_v2",
                record_id=sample_document["id"],
                update_fn=lambda record: {"title": "Updated"},
                max_retries=2,
                retry_delay=0.01  # Fast retry for tests
            )


# =============================================================================
# CONCURRENT UPDATE SIMULATION TESTS
# =============================================================================

class TestConcurrentUpdates:
    """Tests for simulating concurrent update scenarios"""

    @pytest.mark.asyncio
    async def test_two_concurrent_updates_one_wins(self, mock_supabase, sample_document):
        """Test that only one of two concurrent updates succeeds"""
        # Simulate that first update changes version
        call_count = 0

        def mock_update(data):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First update succeeds
                return MagicMock(eq=MagicMock(return_value=MagicMock(eq=MagicMock(return_value=MagicMock(
                    execute=MagicMock(return_value=MagicMock(data=[{**sample_document, "version": 2}]))
                )))))
            else:
                # Second update fails (version already changed)
                return MagicMock(eq=MagicMock(return_value=MagicMock(eq=MagicMock(return_value=MagicMock(
                    execute=MagicMock(return_value=MagicMock(data=[]))
                )))))

        mock_supabase.table.return_value.update = mock_update
        # After first update fails, select returns new version
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {**sample_document, "version": 2}
        ]

        # First update succeeds
        result1 = await update_with_lock(
            supabase=mock_supabase,
            table="documents_v2",
            record_id=sample_document["id"],
            expected_version=1,
            updates={"title": "Update 1"}
        )
        assert result1.success is True

        # Second update fails (version already changed)
        with pytest.raises(OptimisticLockException):
            await update_with_lock(
                supabase=mock_supabase,
                table="documents_v2",
                record_id=sample_document["id"],
                expected_version=1,
                updates={"title": "Update 2"}
            )


# =============================================================================
# BATCH UPDATE TESTS
# =============================================================================

class TestBatchUpdates:
    """Tests for batch updates with optimistic locking"""

    @pytest.mark.asyncio
    async def test_batch_update_all_succeed(self, mock_supabase):
        """Test batch update where all records have correct versions"""
        # All updates succeed
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"version": 2}
        ]

        # Note: batch_update_with_lock expects updates with 'id', 'version', and update fields
        results = await batch_update_with_lock(
            supabase=mock_supabase,
            table="documents_v2",
            updates=[
                {"id": "1", "version": 1, "status": "updated"},
                {"id": "2", "version": 1, "status": "updated"},
                {"id": "3", "version": 1, "status": "updated"}
            ]
        )

        # All should succeed
        successes = sum(1 for r in results if r.success)
        assert successes == 3

    @pytest.mark.asyncio
    async def test_batch_update_partial_failure(self, mock_supabase):
        """Test batch update where some records fail version check"""
        call_count = 0

        def mock_update(data):
            nonlocal call_count
            call_count += 1

            # Second record fails
            if call_count == 2:
                return MagicMock(eq=MagicMock(return_value=MagicMock(eq=MagicMock(return_value=MagicMock(
                    execute=MagicMock(return_value=MagicMock(data=[]))
                )))))
            else:
                return MagicMock(eq=MagicMock(return_value=MagicMock(eq=MagicMock(return_value=MagicMock(
                    execute=MagicMock(return_value=MagicMock(data=[{"version": 2}]))
                )))))

        mock_supabase.table.return_value.update = mock_update
        # For failed update, select returns different version
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "2", "version": 5}
        ]

        results = await batch_update_with_lock(
            supabase=mock_supabase,
            table="documents_v2",
            updates=[
                {"id": "1", "version": 1, "status": "updated"},
                {"id": "2", "version": 1, "status": "updated"},
                {"id": "3", "version": 1, "status": "updated"}
            ]
        )

        # Should report partial success
        successes = sum(1 for r in results if r.success)
        failures = sum(1 for r in results if not r.success)
        assert failures >= 1
