"""
Empire v7.3 - B2 Workflow Manager Tests
Tests for file lifecycle management, state transitions, and error recovery
"""

import pytest
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import AsyncMock, Mock, patch
from b2sdk.v2.exception import B2Error

from app.services.b2_storage import ProcessingStatus, B2Folder
from app.services.b2_workflow import (
    B2WorkflowManager,
    WorkflowTransition,
    IllegalTransitionError,
    TransitionFailedError,
    OrphanedFileError
)


class TestWorkflowTransitionValidation:
    """Test state transition validation"""

    def test_valid_pending_to_processing(self, workflow_manager):
        """Test valid transition from PENDING to PROCESSING"""
        # Should not raise exception
        workflow_manager._validate_transition(
            ProcessingStatus.PENDING,
            ProcessingStatus.PROCESSING
        )

    def test_valid_processing_to_processed(self, workflow_manager):
        """Test valid transition from PROCESSING to PROCESSED"""
        workflow_manager._validate_transition(
            ProcessingStatus.PROCESSING,
            ProcessingStatus.PROCESSED
        )

    def test_valid_processing_to_failed(self, workflow_manager):
        """Test valid transition from PROCESSING to FAILED"""
        workflow_manager._validate_transition(
            ProcessingStatus.PROCESSING,
            ProcessingStatus.FAILED
        )

    def test_valid_failed_to_processing(self, workflow_manager):
        """Test valid transition from FAILED to PROCESSING (retry)"""
        workflow_manager._validate_transition(
            ProcessingStatus.FAILED,
            ProcessingStatus.PROCESSING
        )

    def test_valid_processed_to_archived(self, workflow_manager):
        """Test valid transition from PROCESSED to ARCHIVED"""
        workflow_manager._validate_transition(
            ProcessingStatus.PROCESSED,
            ProcessingStatus.ARCHIVED
        )

    def test_invalid_pending_to_processed(self, workflow_manager):
        """Test invalid direct transition from PENDING to PROCESSED"""
        with pytest.raises(IllegalTransitionError, match="Illegal transition"):
            workflow_manager._validate_transition(
                ProcessingStatus.PENDING,
                ProcessingStatus.PROCESSED
            )

    def test_invalid_pending_to_failed(self, workflow_manager):
        """Test invalid transition from PENDING to FAILED"""
        with pytest.raises(IllegalTransitionError):
            workflow_manager._validate_transition(
                ProcessingStatus.PENDING,
                ProcessingStatus.FAILED
            )

    def test_invalid_archived_transitions(self, workflow_manager):
        """Test that ARCHIVED is a terminal state"""
        with pytest.raises(IllegalTransitionError):
            workflow_manager._validate_transition(
                ProcessingStatus.ARCHIVED,
                ProcessingStatus.PROCESSING
            )


class TestTransitionHistory:
    """Test transition history tracking"""

    def test_add_transition_history(self, workflow_manager):
        """Test adding transition history to metadata"""
        metadata = {}

        updated = workflow_manager._add_transition_history(
            metadata,
            ProcessingStatus.PENDING,
            ProcessingStatus.PROCESSING,
            WorkflowTransition.START_PROCESSING
        )

        assert "transition_history" in updated
        assert len(updated["transition_history"]) == 1

        history_entry = updated["transition_history"][0]
        assert history_entry["from_status"] == "pending"
        assert history_entry["to_status"] == "processing"
        assert history_entry["transition"] == "start"
        assert "timestamp" in history_entry

    def test_append_transition_history(self, workflow_manager):
        """Test appending to existing transition history"""
        metadata = {
            "transition_history": [
                {
                    "timestamp": "2025-01-01T00:00:00",
                    "from_status": None,
                    "to_status": "pending",
                    "transition": "upload"
                }
            ]
        }

        updated = workflow_manager._add_transition_history(
            metadata,
            ProcessingStatus.PENDING,
            ProcessingStatus.PROCESSING,
            WorkflowTransition.START_PROCESSING
        )

        assert len(updated["transition_history"]) == 2


class TestWorkflowTransitions:
    """Test workflow transition methods"""

    @pytest.mark.asyncio
    async def test_start_processing(self, workflow_manager, mock_b2_service):
        """Test start_processing transition"""
        result = await workflow_manager.start_processing(
            file_id="test_file_123",
            processor_id="worker_1"
        )

        # Verify B2 service was called correctly
        mock_b2_service.move_to_status.assert_called_once()
        call_args = mock_b2_service.move_to_status.call_args

        assert call_args.kwargs["file_id"] == "test_file_123"
        assert call_args.kwargs["current_status"] == ProcessingStatus.PENDING
        assert call_args.kwargs["new_status"] == ProcessingStatus.PROCESSING

        # Check metadata
        metadata = call_args.kwargs["metadata"]
        assert metadata["processor_id"] == "worker_1"
        assert metadata["workflow_status"] == "processing"
        assert "processing_started_at" in metadata
        assert "transition_history" in metadata

    @pytest.mark.asyncio
    async def test_complete_processing(self, workflow_manager, mock_b2_service):
        """Test complete_processing transition"""
        result_data = {"task_id": "123", "status": "success"}

        result = await workflow_manager.complete_processing(
            file_id="test_file_123",
            result_data=result_data
        )

        # Verify call
        mock_b2_service.move_to_status.assert_called_once()
        call_args = mock_b2_service.move_to_status.call_args

        assert call_args.kwargs["current_status"] == ProcessingStatus.PROCESSING
        assert call_args.kwargs["new_status"] == ProcessingStatus.PROCESSED

        metadata = call_args.kwargs["metadata"]
        assert "processing_completed_at" in metadata
        assert metadata["result_summary"] == str(result_data)

    @pytest.mark.asyncio
    async def test_fail_processing(self, workflow_manager, mock_b2_service):
        """Test fail_processing transition"""
        error_msg = "Processing failed due to timeout"

        result = await workflow_manager.fail_processing(
            file_id="test_file_123",
            error=error_msg,
            retry_count=2
        )

        # Verify call
        call_args = mock_b2_service.move_to_status.call_args

        assert call_args.kwargs["current_status"] == ProcessingStatus.PROCESSING
        assert call_args.kwargs["new_status"] == ProcessingStatus.FAILED

        metadata = call_args.kwargs["metadata"]
        assert metadata["error"] == error_msg
        assert metadata["retry_count"] == 2
        assert "failed_at" in metadata

    @pytest.mark.asyncio
    async def test_retry_processing(self, workflow_manager, mock_b2_service):
        """Test retry_processing transition"""
        result = await workflow_manager.retry_processing(
            file_id="test_file_123",
            retry_count=1
        )

        # Verify call
        call_args = mock_b2_service.move_to_status.call_args

        assert call_args.kwargs["current_status"] == ProcessingStatus.FAILED
        assert call_args.kwargs["new_status"] == ProcessingStatus.PROCESSING

        metadata = call_args.kwargs["metadata"]
        assert metadata["retry_count"] == 1
        assert "retry_started_at" in metadata

    @pytest.mark.asyncio
    async def test_archive_document(self, workflow_manager, mock_b2_service):
        """Test archive_document transition"""
        result = await workflow_manager.archive_document(file_id="test_file_123")

        # Verify call
        call_args = mock_b2_service.move_to_status.call_args

        assert call_args.kwargs["current_status"] == ProcessingStatus.PROCESSED
        assert call_args.kwargs["new_status"] == ProcessingStatus.ARCHIVED

        metadata = call_args.kwargs["metadata"]
        assert "archived_at" in metadata


class TestRetryWithBackoff:
    """Test exponential backoff retry logic"""

    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self, workflow_manager):
        """Test operation succeeds on first attempt"""
        mock_operation = AsyncMock(return_value={"success": True})

        result = await workflow_manager._retry_with_backoff(
            mock_operation,
            "test_operation"
        )

        assert result == {"success": True}
        assert mock_operation.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_success_on_second_attempt(self, workflow_manager):
        """Test operation succeeds after one retry"""
        mock_operation = AsyncMock(
            side_effect=[B2Error("Temporary error"), {"success": True}]
        )

        with patch('time.sleep'):  # Mock sleep to speed up test
            result = await workflow_manager._retry_with_backoff(
                mock_operation,
                "test_operation"
            )

        assert result == {"success": True}
        assert mock_operation.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_fails_after_max_attempts(self, workflow_manager):
        """Test operation fails after max retries"""
        mock_operation = AsyncMock(side_effect=B2Error("Persistent error"))

        with patch('time.sleep'):
            with pytest.raises(TransitionFailedError, match="failed after 3 attempts"):
                await workflow_manager._retry_with_backoff(
                    mock_operation,
                    "test_operation"
                )

        assert mock_operation.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exponential_backoff_delays(self, workflow_manager):
        """Test exponential backoff delay calculation"""
        mock_operation = AsyncMock(side_effect=B2Error("Error"))
        delays = []

        def mock_sleep(delay):
            delays.append(delay)

        with patch('time.sleep', side_effect=mock_sleep):
            with pytest.raises(TransitionFailedError):
                await workflow_manager._retry_with_backoff(
                    mock_operation,
                    "test_operation"
                )

        # Check exponential backoff: 2s, 4s
        assert len(delays) == 2
        assert delays[0] == 2.0  # 2^0 * 2
        assert delays[1] == 4.0  # 2^1 * 2


class TestOrphanDetectionAndRecovery:
    """Test orphaned file detection and recovery"""

    @pytest.mark.asyncio
    async def test_detect_orphaned_files(self, workflow_manager, mock_b2_service):
        """Test orphaned file detection"""
        # Mock list_files_by_status to return an old file
        old_timestamp = (datetime.utcnow() - timedelta(hours=5)).isoformat()
        mock_b2_service.list_files_by_status = AsyncMock(return_value=[
            {
                "file_id": "old_file_1",
                "file_name": "processing/courses/old.pdf",
                "upload_timestamp": old_timestamp,
                "size": 1024
            }
        ])

        orphans = await workflow_manager.detect_orphaned_files()

        assert len(orphans) == 1
        assert orphans[0]["file_id"] == "old_file_1"
        assert "time_in_processing" in orphans[0]

    @pytest.mark.asyncio
    async def test_no_orphaned_files(self, workflow_manager, mock_b2_service):
        """Test when there are no orphaned files"""
        # Mock recent file
        recent_timestamp = (datetime.utcnow() - timedelta(minutes=30)).isoformat()
        mock_b2_service.list_files_by_status = AsyncMock(return_value=[
            {
                "file_id": "recent_file",
                "file_name": "processing/courses/recent.pdf",
                "upload_timestamp": recent_timestamp,
                "size": 1024
            }
        ])

        orphans = await workflow_manager.detect_orphaned_files()

        assert len(orphans) == 0

    @pytest.mark.asyncio
    async def test_recover_orphaned_file_force_fail(self, workflow_manager, mock_b2_service):
        """Test orphan recovery by moving to FAILED"""
        result = await workflow_manager.recover_orphaned_file(
            file_id="orphan_123",
            force_fail=True
        )

        # Should call fail_processing
        mock_b2_service.move_to_status.assert_called_once()
        call_args = mock_b2_service.move_to_status.call_args

        metadata = call_args.kwargs["metadata"]
        assert "orphaned" in metadata["error"].lower()

    @pytest.mark.asyncio
    async def test_recover_orphaned_file_restart(self, workflow_manager):
        """Test orphan recovery by restarting processing"""
        result = await workflow_manager.recover_orphaned_file(
            file_id="orphan_123",
            force_fail=False
        )

        assert result["status"] == "processing_restarted"

    @pytest.mark.asyncio
    async def test_recover_all_orphaned_files(self, workflow_manager, mock_b2_service):
        """Test batch orphan recovery"""
        # Mock orphaned files
        old_timestamp = (datetime.utcnow() - timedelta(hours=5)).isoformat()
        mock_b2_service.list_files_by_status = AsyncMock(return_value=[
            {
                "file_id": "orphan_1",
                "file_name": "processing/courses/file1.pdf",
                "upload_timestamp": old_timestamp,
                "size": 1024
            },
            {
                "file_id": "orphan_2",
                "file_name": "processing/courses/file2.pdf",
                "upload_timestamp": old_timestamp,
                "size": 2048
            }
        ])

        results = await workflow_manager.recover_all_orphaned_files(force_fail=True)

        assert results["orphaned_count"] == 2
        assert len(results["recovered"]) == 2
        assert len(results["failed"]) == 0

    @pytest.mark.asyncio
    async def test_recover_all_no_orphans(self, workflow_manager, mock_b2_service):
        """Test batch recovery when no orphans exist"""
        mock_b2_service.list_files_by_status = AsyncMock(return_value=[])

        results = await workflow_manager.recover_all_orphaned_files()

        assert results["orphaned_count"] == 0
        assert len(results["recovered"]) == 0
        assert len(results["failed"]) == 0


class TestBatchOperations:
    """Test batch workflow operations"""

    @pytest.mark.asyncio
    async def test_batch_transition_validation(self, workflow_manager, mock_b2_service):
        """Test batch transition validates state changes"""
        file_ids = ["file_1", "file_2", "file_3"]

        result = await workflow_manager.batch_transition(
            file_ids=file_ids,
            from_status=ProcessingStatus.PROCESSING,
            to_status=ProcessingStatus.PROCESSED
        )

        # Should validate transition before calling B2
        mock_b2_service.batch_move_to_status.assert_called_once_with(
            file_ids=file_ids,
            current_status=ProcessingStatus.PROCESSING,
            new_status=ProcessingStatus.PROCESSED
        )

    @pytest.mark.asyncio
    async def test_batch_transition_invalid(self, workflow_manager):
        """Test batch transition rejects invalid transitions"""
        file_ids = ["file_1", "file_2"]

        with pytest.raises(IllegalTransitionError):
            await workflow_manager.batch_transition(
                file_ids=file_ids,
                from_status=ProcessingStatus.PENDING,
                to_status=ProcessingStatus.ARCHIVED  # Invalid
            )

    @pytest.mark.asyncio
    async def test_get_files_by_status(self, workflow_manager, mock_b2_service):
        """Test getting files by status"""
        files = await workflow_manager.get_files_by_status(
            ProcessingStatus.PROCESSING,
            limit=50
        )

        mock_b2_service.list_files_by_status.assert_called_once_with(
            ProcessingStatus.PROCESSING,
            50
        )


class TestUploadDocument:
    """Test document upload with workflow integration"""

    @pytest.mark.asyncio
    async def test_upload_document(self, workflow_manager, mock_b2_service, sample_metadata):
        """Test document upload to PENDING folder"""
        file_data = BytesIO(b"test content")

        result = await workflow_manager.upload_document(
            file_data=file_data,
            filename="test.pdf",
            content_type="application/pdf",
            metadata=sample_metadata,
            encrypt=False
        )

        # Verify B2 upload was called
        mock_b2_service.upload_file.assert_called_once()
        call_args = mock_b2_service.upload_file.call_args

        assert call_args.kwargs["filename"] == "test.pdf"
        assert call_args.kwargs["folder"] == B2Folder.PENDING
        assert call_args.kwargs["encrypt"] is False

        # Check metadata
        metadata = call_args.kwargs["metadata"]
        assert metadata["workflow_status"] == "pending"
        assert metadata["transition"] == "upload"

    @pytest.mark.asyncio
    async def test_upload_document_with_encryption(self, workflow_manager, mock_b2_service):
        """Test encrypted document upload"""
        file_data = BytesIO(b"sensitive content")

        result = await workflow_manager.upload_document(
            file_data=file_data,
            filename="secret.pdf",
            encrypt=True,
            encryption_password="test_password"
        )

        # Verify encryption parameters passed
        call_args = mock_b2_service.upload_file.call_args
        assert call_args.kwargs["encrypt"] is True
        assert call_args.kwargs["encryption_password"] == "test_password"
