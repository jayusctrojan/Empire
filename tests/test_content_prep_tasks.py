"""
Empire v7.3 - Content Prep Tasks Test Suite (Task 131)

Feature: 007-content-prep-agent
Tests for Celery tasks in content_prep_tasks.py
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from uuid import uuid4


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_content_prep_agent():
    """Mock ContentPrepAgent."""
    # Patch at the source module since tasks use lazy imports
    # Also mock dependencies to prevent initialization errors
    with patch('app.services.content_prep_agent.ContentPrepAgent') as MockAgent, \
         patch('app.services.content_prep_agent.get_supabase_client'), \
         patch('app.services.content_prep_agent.B2StorageService'):
        agent = MagicMock()
        MockAgent.return_value = agent
        yield agent


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    with patch('app.core.supabase_client.get_supabase_client') as mock_get:
        client = MagicMock()
        mock_get.return_value = client
        yield client


@pytest.fixture
def mock_monitoring_metrics():
    """Mock monitoring metrics."""
    with patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_RUNS') as runs, \
         patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_DELETED') as deleted, \
         patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_DURATION') as duration, \
         patch('app.tasks.content_prep_tasks.CONTENT_SETS_DELETED') as sets_deleted:
        yield {
            'runs': runs,
            'deleted': deleted,
            'duration': duration,
            'sets_deleted': sets_deleted,
        }


@pytest.fixture
def sample_content_sets():
    """Sample content sets for cleanup tests."""
    return [
        {"id": str(uuid4()), "processing_status": "complete", "completed_at": "2024-01-01T00:00:00"},
        {"id": str(uuid4()), "processing_status": "complete", "completed_at": "2024-01-15T00:00:00"},
        {"id": str(uuid4()), "processing_status": "complete", "completed_at": "2024-02-01T00:00:00"},
    ]


# ============================================================================
# Detect Content Sets Task Tests
# ============================================================================

class TestDetectContentSetsTask:
    """Tests for detect_content_sets task."""

    def test_detect_content_sets_success(self, mock_content_prep_agent):
        """Test successful content set detection."""
        from app.tasks.content_prep_tasks import detect_content_sets, run_async

        mock_content_prep_agent.analyze_folder = AsyncMock(return_value={
            "content_sets": [{"id": "set-1", "name": "Course 1"}],
            "standalone_files": [],
            "analysis_time_ms": 100,
        })

        # Call the task directly (not through Celery)
        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            result = detect_content_sets(
                b2_folder="pending/courses/",
                detection_mode="auto"
            )

            assert result["status"] == "success"
            assert "content_sets" in result

    def test_detect_content_sets_empty_folder(self, mock_content_prep_agent):
        """Test detection on empty folder."""
        from app.tasks.content_prep_tasks import detect_content_sets

        mock_content_prep_agent.analyze_folder = AsyncMock(return_value={
            "content_sets": [],
            "standalone_files": [],
            "analysis_time_ms": 50,
        })

        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            result = detect_content_sets(
                b2_folder="pending/empty/",
                detection_mode="auto"
            )

            assert result["status"] == "success"
            assert len(result["content_sets"]) == 0

    def test_detect_content_sets_error_retry(self, mock_content_prep_agent):
        """Test that errors trigger retry."""
        from app.tasks.content_prep_tasks import detect_content_sets

        mock_content_prep_agent.analyze_folder = AsyncMock(side_effect=Exception("B2 error"))

        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            with pytest.raises(Exception, match="B2 error"):
                detect_content_sets(b2_folder="pending/")


# ============================================================================
# Validate Content Set Task Tests
# ============================================================================

class TestValidateContentSetTask:
    """Tests for validate_content_set task."""

    def test_validate_complete_set(self, mock_content_prep_agent):
        """Test validating a complete content set."""
        from app.tasks.content_prep_tasks import validate_content_set

        mock_content_prep_agent.validate_completeness = AsyncMock(return_value={
            "is_complete": True,
            "missing_files": [],
            "total_files": 5,
            "gaps_detected": 0,
            "can_proceed": True,
            "requires_acknowledgment": False,
        })

        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            result = validate_content_set(content_set_id="test-id")

            assert result["status"] == "success"
            assert result["is_complete"] is True

    def test_validate_incomplete_set(self, mock_content_prep_agent):
        """Test validating an incomplete content set."""
        from app.tasks.content_prep_tasks import validate_content_set

        mock_content_prep_agent.validate_completeness = AsyncMock(return_value={
            "is_complete": False,
            "missing_files": ["#3"],
            "total_files": 4,
            "gaps_detected": 1,
            "can_proceed": True,
            "requires_acknowledgment": True,
        })

        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            result = validate_content_set(content_set_id="test-id")

            assert result["status"] == "success"
            assert result["is_complete"] is False
            assert result["requires_acknowledgment"] is True

    def test_validate_not_found(self, mock_content_prep_agent):
        """Test validating non-existent content set."""
        from app.tasks.content_prep_tasks import validate_content_set

        mock_content_prep_agent.validate_completeness = AsyncMock(
            side_effect=ValueError("Content set not found")
        )

        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            result = validate_content_set(content_set_id="nonexistent")

            assert result["status"] == "error"


# ============================================================================
# Generate Manifest Task Tests
# ============================================================================

class TestGenerateManifestTask:
    """Tests for generate_manifest task."""

    def test_generate_manifest_success(self, mock_content_prep_agent):
        """Test successful manifest generation."""
        from app.tasks.content_prep_tasks import generate_manifest

        mock_content_prep_agent.generate_manifest = AsyncMock(return_value={
            "manifest_id": "manifest-123",
            "content_set_name": "Test Course",
            "ordered_files": [
                {"sequence": 1, "file": "01-intro.pdf"},
                {"sequence": 2, "file": "02-basics.pdf"},
            ],
            "total_files": 2,
            "warnings": [],
            "estimated_time_seconds": 60,
            "context": {},
            "created_at": datetime.utcnow().isoformat(),
        })

        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            result = generate_manifest(content_set_id="test-id")

            assert result["status"] == "success"
            assert result["manifest_id"] == "manifest-123"
            assert result["total_files"] == 2

    def test_generate_manifest_incomplete_blocked(self, mock_content_prep_agent):
        """Test manifest generation blocked for incomplete set."""
        from app.tasks.content_prep_tasks import generate_manifest

        mock_content_prep_agent.generate_manifest = AsyncMock(
            side_effect=ValueError("Content set is incomplete")
        )

        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            result = generate_manifest(
                content_set_id="test-id",
                proceed_incomplete=False
            )

            assert result["status"] == "error"
            assert "incomplete" in result["error"].lower()

    def test_generate_manifest_proceed_incomplete(self, mock_content_prep_agent):
        """Test manifest generation with proceed_incomplete=True."""
        from app.tasks.content_prep_tasks import generate_manifest

        mock_content_prep_agent.generate_manifest = AsyncMock(return_value={
            "manifest_id": "manifest-123",
            "content_set_name": "Test Course",
            "ordered_files": [],
            "total_files": 3,
            "warnings": ["#2 (missing)"],
            "estimated_time_seconds": 90,
            "context": {},
            "created_at": datetime.utcnow().isoformat(),
        })

        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            result = generate_manifest(
                content_set_id="test-id",
                proceed_incomplete=True
            )

            assert result["status"] == "success"
            assert len(result["warnings"]) > 0


# ============================================================================
# Process Content Set Task Tests
# ============================================================================

class TestProcessContentSetTask:
    """Tests for process_content_set task."""

    def test_process_complete_set(self, mock_content_prep_agent):
        """Test processing a complete content set."""
        from app.tasks.content_prep_tasks import process_content_set

        mock_content_prep_agent.validate_completeness = AsyncMock(return_value={
            "is_complete": True,
        })
        mock_content_prep_agent.generate_manifest = AsyncMock(return_value={
            "manifest_id": "manifest-123",
            "ordered_files": [
                {"b2_path": "pending/01.pdf", "file": "01.pdf", "sequence": 1},
                {"b2_path": "pending/02.pdf", "file": "02.pdf", "sequence": 2},
            ],
            "warnings": [],
            "context": {"set_name": "Test"},
        })

        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            result = process_content_set(content_set_id="test-id")

            assert result["status"] == "success"
            assert result["total_files"] == 2

    def test_process_incomplete_blocked(self, mock_content_prep_agent):
        """Test processing blocked for incomplete set."""
        from app.tasks.content_prep_tasks import process_content_set

        mock_content_prep_agent.validate_completeness = AsyncMock(return_value={
            "is_complete": False,
            "missing_files": ["#3"],
        })

        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            result = process_content_set(
                content_set_id="test-id",
                proceed_incomplete=False
            )

            assert result["status"] == "blocked"


# ============================================================================
# Analyze Pending Folders Task Tests
# ============================================================================

class TestAnalyzePendingFoldersTask:
    """Tests for analyze_pending_folders task."""

    def test_analyze_default_folder(self):
        """Test analyzing default pending folder."""
        from app.tasks.content_prep_tasks import analyze_pending_folders

        with patch('app.tasks.content_prep_tasks.detect_content_sets') as mock_detect:
            mock_detect.return_value = {
                "status": "success",
                "content_sets": [{"id": "set-1"}],
                "standalone_files": [],
            }

            result = analyze_pending_folders()

            assert result["status"] == "success"
            assert result["folders_analyzed"] == 1

    def test_analyze_multiple_folders(self):
        """Test analyzing multiple folders."""
        from app.tasks.content_prep_tasks import analyze_pending_folders

        with patch('app.tasks.content_prep_tasks.detect_content_sets') as mock_detect:
            mock_detect.return_value = {
                "status": "success",
                "content_sets": [{"id": "set-1"}],
                "standalone_files": [],
            }

            result = analyze_pending_folders(
                folders=["pending/courses/", "pending/docs/", "pending/training/"]
            )

            assert result["status"] == "success"
            assert result["folders_analyzed"] == 3

    def test_analyze_partial_failure(self):
        """Test analyzing with some folders failing."""
        from app.tasks.content_prep_tasks import analyze_pending_folders

        call_count = [0]

        def mock_detect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Folder not found")
            return {
                "status": "success",
                "content_sets": [],
                "standalone_files": [],
            }

        with patch('app.tasks.content_prep_tasks.detect_content_sets', side_effect=mock_detect):
            result = analyze_pending_folders(
                folders=["folder1/", "folder2/", "folder3/"]
            )

            assert result["status"] == "success"
            # Should have recorded the error for folder2
            folder_results = result["folder_results"]
            assert any(r.get("status") == "error" for r in folder_results)


# ============================================================================
# Clarify Ordering Async Task Tests
# ============================================================================

class TestClarifyOrderingAsyncTask:
    """Tests for clarify_ordering_async task."""

    def test_clarify_high_confidence(self, mock_content_prep_agent):
        """Test clarification not needed for high confidence."""
        from app.tasks.content_prep_tasks import clarify_ordering_async

        mock_content_prep_agent.resolve_order_with_clarification = AsyncMock(return_value={
            "status": "success",
            "content_set_id": "test-id",
            "ordering_confidence": 0.95,
            "clarification_requested": False,
            "ordered_files": [],
        })

        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            result = clarify_ordering_async(
                content_set_id="test-id",
                user_id="user-123",
                confidence_threshold=0.8,
            )

            assert result["status"] == "success"
            assert result["clarification_requested"] is False

    def test_clarify_low_confidence(self, mock_content_prep_agent):
        """Test clarification requested for low confidence."""
        from app.tasks.content_prep_tasks import clarify_ordering_async

        mock_content_prep_agent.resolve_order_with_clarification = AsyncMock(return_value={
            "status": "success",
            "content_set_id": "test-id",
            "ordering_confidence": 0.6,
            "clarification_requested": True,
            "clarification_answered": True,
            "ordered_files": [],
        })

        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            result = clarify_ordering_async(
                content_set_id="test-id",
                user_id="user-123",
                confidence_threshold=0.8,
            )

            assert result["status"] == "success"
            assert result["clarification_requested"] is True

    def test_clarify_error(self, mock_content_prep_agent):
        """Test clarification task error handling."""
        from app.tasks.content_prep_tasks import clarify_ordering_async

        mock_content_prep_agent.resolve_order_with_clarification = AsyncMock(
            side_effect=Exception("Agent error")
        )

        with patch('app.services.content_prep_agent.ContentPrepAgent', return_value=mock_content_prep_agent):
            result = clarify_ordering_async(
                content_set_id="test-id",
                user_id="user-123",
            )

            assert result["status"] == "error"


# ============================================================================
# Cleanup Old Content Sets Task Tests (Task 130)
# ============================================================================

class TestCleanupOldContentSetsTask:
    """Tests for cleanup_old_content_sets task."""

    def test_cleanup_no_sets_to_delete(self):
        """Test cleanup when no old sets exist."""
        from app.tasks.content_prep_tasks import cleanup_old_content_sets

        with patch('app.tasks.content_prep_tasks.get_supabase_client') as mock_get:
            mock_client = MagicMock()
            mock_result = MagicMock()
            mock_result.data = []

            mock_client.table().select().eq().lt().execute.return_value = mock_result
            mock_get.return_value = mock_client

            # Mock metrics
            with patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_RUNS') as mock_runs, \
                 patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_DURATION') as mock_duration:

                result = cleanup_old_content_sets(retention_days=90)

                assert result["status"] == "success"
                assert result["deleted_count"] == 0
                mock_runs.labels.assert_called_with(status="success")

    def test_cleanup_deletes_old_sets(self, sample_content_sets):
        """Test cleanup deletes old content sets."""
        from app.tasks.content_prep_tasks import cleanup_old_content_sets

        with patch('app.tasks.content_prep_tasks.get_supabase_client') as mock_get:
            mock_client = MagicMock()
            mock_result = MagicMock()
            mock_result.data = sample_content_sets

            mock_client.table().select().eq().lt().execute.return_value = mock_result
            mock_client.table().delete().eq().execute.return_value = MagicMock()
            mock_get.return_value = mock_client

            # Mock metrics
            with patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_RUNS'), \
                 patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_DELETED'), \
                 patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_DURATION'), \
                 patch('app.tasks.content_prep_tasks.CONTENT_SETS_DELETED'):

                result = cleanup_old_content_sets(retention_days=90)

                assert result["status"] == "success"
                assert result["deleted_count"] == 3
                assert len(result["deleted_ids"]) == 3

    def test_cleanup_custom_retention(self):
        """Test cleanup with custom retention period."""
        from app.tasks.content_prep_tasks import cleanup_old_content_sets

        with patch('app.tasks.content_prep_tasks.get_supabase_client') as mock_get:
            mock_client = MagicMock()
            mock_result = MagicMock()
            mock_result.data = []

            mock_client.table().select().eq().lt().execute.return_value = mock_result
            mock_get.return_value = mock_client

            with patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_RUNS'), \
                 patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_DURATION'):

                result = cleanup_old_content_sets(retention_days=30)

                assert result["retention_days"] == 30

    def test_cleanup_error_handling(self):
        """Test cleanup error handling and metrics."""
        from app.tasks.content_prep_tasks import cleanup_old_content_sets

        with patch('app.tasks.content_prep_tasks.get_supabase_client') as mock_get:
            mock_client = MagicMock()
            mock_client.table().select().eq().lt().execute.side_effect = Exception("DB error")
            mock_get.return_value = mock_client

            with patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_RUNS') as mock_runs, \
                 patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_DURATION') as mock_duration:

                with pytest.raises(Exception, match="DB error"):
                    cleanup_old_content_sets(retention_days=90)

                # Should record error in metrics
                mock_runs.labels.assert_called_with(status="error")

    def test_cleanup_batch_processing(self):
        """Test cleanup processes in batches."""
        from app.tasks.content_prep_tasks import cleanup_old_content_sets

        # Create 100 content sets
        many_sets = [{"id": str(uuid4())} for _ in range(100)]

        with patch('app.tasks.content_prep_tasks.get_supabase_client') as mock_get:
            mock_client = MagicMock()
            mock_result = MagicMock()
            mock_result.data = many_sets

            mock_client.table().select().eq().lt().execute.return_value = mock_result
            mock_client.table().delete().eq().execute.return_value = MagicMock()
            mock_get.return_value = mock_client

            with patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_RUNS'), \
                 patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_DELETED'), \
                 patch('app.tasks.content_prep_tasks.RETENTION_CLEANUP_DURATION'), \
                 patch('app.tasks.content_prep_tasks.CONTENT_SETS_DELETED'):

                result = cleanup_old_content_sets(retention_days=90)

                assert result["deleted_count"] == 100


# ============================================================================
# Task Configuration Tests
# ============================================================================

class TestTaskConfiguration:
    """Tests for task configuration and decorators."""

    def test_detect_content_sets_config(self):
        """Test detect_content_sets task configuration."""
        from app.tasks.content_prep_tasks import detect_content_sets

        assert detect_content_sets.name == 'app.tasks.content_prep_tasks.detect_content_sets'
        assert detect_content_sets.max_retries == 3

    def test_validate_content_set_config(self):
        """Test validate_content_set task configuration."""
        from app.tasks.content_prep_tasks import validate_content_set

        assert validate_content_set.name == 'app.tasks.content_prep_tasks.validate_content_set'
        assert validate_content_set.max_retries == 2

    def test_generate_manifest_config(self):
        """Test generate_manifest task configuration."""
        from app.tasks.content_prep_tasks import generate_manifest

        assert generate_manifest.name == 'app.tasks.content_prep_tasks.generate_manifest'
        assert generate_manifest.max_retries == 2

    def test_process_content_set_config(self):
        """Test process_content_set task configuration."""
        from app.tasks.content_prep_tasks import process_content_set

        assert process_content_set.name == 'app.tasks.content_prep_tasks.process_content_set'
        assert process_content_set.max_retries == 3

    def test_cleanup_old_content_sets_config(self):
        """Test cleanup_old_content_sets task configuration."""
        from app.tasks.content_prep_tasks import cleanup_old_content_sets

        assert cleanup_old_content_sets.name == 'app.tasks.content_prep_tasks.cleanup_old_content_sets'
        assert cleanup_old_content_sets.max_retries == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
