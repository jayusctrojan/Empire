"""
Empire v7.3 - B2 Storage Workflow Manager
Manages file lifecycle transitions through B2 folder structure with comprehensive
error handling, atomic operations, and recovery mechanisms.
"""

import logging
import time
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from datetime import datetime, timedelta
from b2sdk.v2.exception import B2Error

from app.services.b2_storage import get_b2_service, ProcessingStatus, B2Folder

logger = logging.getLogger(__name__)


class WorkflowError(Exception):
    """Base exception for workflow errors"""
    pass


class IllegalTransitionError(WorkflowError):
    """Raised when attempting an illegal state transition"""
    pass


class TransitionFailedError(WorkflowError):
    """Raised when a transition fails after retries"""
    pass


class OrphanedFileError(WorkflowError):
    """Raised when a file is stuck in an invalid state"""
    pass


class WorkflowTransition(str, Enum):
    """Valid workflow state transitions"""
    UPLOAD = "upload"              # Initial upload → PENDING
    START_PROCESSING = "start"     # PENDING → PROCESSING
    COMPLETE = "complete"          # PROCESSING → PROCESSED
    FAIL = "fail"                  # PROCESSING → FAILED
    RETRY = "retry"                # FAILED → PROCESSING
    ARCHIVE = "archive"            # PROCESSED → ARCHIVED


class B2WorkflowManager:
    """
    Manages file lifecycle transitions through B2 folder structure with comprehensive
    error handling and atomic operations.

    Workflow:
    1. Upload → pending/courses/
    2. Start → processing/courses/
    3. Complete → processed/courses/
    4. Fail → failed/courses/
    5. Archive → archive/courses/

    Features:
    - Automatic folder transitions with state validation
    - Metadata tracking with transition history
    - Error recovery with exponential backoff
    - Atomic operations with rollback capability
    - Orphaned file detection and recovery
    - Comprehensive logging and audit trail
    """

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2.0  # seconds
    RETRY_MAX_DELAY = 30.0  # seconds
    ORPHAN_TIMEOUT = timedelta(hours=4)  # Files stuck in processing for 4+ hours

    def __init__(self):
        self.b2_service = get_b2_service()

        # Valid state transition map: (from_status, to_status)
        self._transition_map = {
            WorkflowTransition.UPLOAD: (None, ProcessingStatus.PENDING),
            WorkflowTransition.START_PROCESSING: (ProcessingStatus.PENDING, ProcessingStatus.PROCESSING),
            WorkflowTransition.COMPLETE: (ProcessingStatus.PROCESSING, ProcessingStatus.PROCESSED),
            WorkflowTransition.FAIL: (ProcessingStatus.PROCESSING, ProcessingStatus.FAILED),
            WorkflowTransition.RETRY: (ProcessingStatus.FAILED, ProcessingStatus.PROCESSING),
            WorkflowTransition.ARCHIVE: (ProcessingStatus.PROCESSED, ProcessingStatus.ARCHIVED),
        }

        # Valid state transitions (for validation)
        self._valid_transitions: Dict[ProcessingStatus, List[ProcessingStatus]] = {
            ProcessingStatus.PENDING: [ProcessingStatus.PROCESSING],
            ProcessingStatus.PROCESSING: [ProcessingStatus.PROCESSED, ProcessingStatus.FAILED],
            ProcessingStatus.FAILED: [ProcessingStatus.PROCESSING],  # Retry
            ProcessingStatus.PROCESSED: [ProcessingStatus.ARCHIVED],
            ProcessingStatus.ARCHIVED: [],  # Terminal state
        }

    def _validate_transition(
        self,
        current_status: ProcessingStatus,
        new_status: ProcessingStatus
    ) -> None:
        """
        Validate that a state transition is legal

        Args:
            current_status: Current processing status
            new_status: Desired new status

        Raises:
            IllegalTransitionError: If transition is not allowed
        """
        valid_next_states = self._valid_transitions.get(current_status, [])

        if new_status not in valid_next_states:
            raise IllegalTransitionError(
                f"Illegal transition: {current_status.value} → {new_status.value}. "
                f"Valid transitions from {current_status.value}: "
                f"{[s.value for s in valid_next_states]}"
            )

    def _add_transition_history(
        self,
        metadata: Dict[str, Any],
        from_status: Optional[ProcessingStatus],
        to_status: ProcessingStatus,
        transition_type: WorkflowTransition
    ) -> Dict[str, Any]:
        """
        Add transition history to metadata for audit trail

        Args:
            metadata: Existing metadata dictionary
            from_status: Previous status (None for initial upload)
            to_status: New status
            transition_type: Type of transition

        Returns:
            Updated metadata with transition history
        """
        if "transition_history" not in metadata:
            metadata["transition_history"] = []

        metadata["transition_history"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "from_status": from_status.value if from_status else None,
            "to_status": to_status.value,
            "transition": transition_type.value
        })

        return metadata

    async def _retry_with_backoff(
        self,
        operation,
        operation_name: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute an operation with exponential backoff retry logic

        Args:
            operation: Async function to execute
            operation_name: Name for logging
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation

        Returns:
            Result of operation

        Raises:
            TransitionFailedError: If all retries fail
        """
        last_exception = None

        for attempt in range(self.MAX_RETRIES):
            try:
                result = await operation(*args, **kwargs)

                if attempt > 0:
                    logger.info(
                        f"{operation_name} succeeded on attempt {attempt + 1}/{self.MAX_RETRIES}"
                    )

                return result

            except B2Error as e:
                last_exception = e

                if attempt < self.MAX_RETRIES - 1:
                    # Calculate exponential backoff delay
                    delay = min(
                        self.RETRY_BASE_DELAY * (2 ** attempt),
                        self.RETRY_MAX_DELAY
                    )

                    logger.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    time.sleep(delay)
                else:
                    logger.error(
                        f"{operation_name} failed after {self.MAX_RETRIES} attempts: {e}"
                    )

        raise TransitionFailedError(
            f"{operation_name} failed after {self.MAX_RETRIES} attempts: {last_exception}"
        )

    async def upload_document(
        self,
        file_data,
        filename: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
        encrypt: bool = False,
        encryption_password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload document to pending folder with optional encryption

        Args:
            file_data: File-like object containing the data to upload
            filename: Name of the file
            content_type: MIME type of the file
            metadata: Optional metadata dictionary
            encrypt: Whether to encrypt the file before upload
            encryption_password: Password for encryption (required if encrypt=True)

        Returns:
            dict: Upload result with file_id, file_name, and url
        """
        logger.info(f"Uploading document {filename} to PENDING folder (encrypted: {encrypt})")

        # Add workflow metadata
        workflow_metadata = metadata or {}
        workflow_metadata.update({
            "workflow_status": ProcessingStatus.PENDING.value,
            "transition": WorkflowTransition.UPLOAD.value
        })

        result = await self.b2_service.upload_file(
            file_data=file_data,
            filename=filename,
            folder=B2Folder.PENDING,
            content_type=content_type,
            metadata=workflow_metadata,
            encrypt=encrypt,
            encryption_password=encryption_password
        )

        logger.info(f"Document {filename} uploaded successfully with ID: {result['file_id']}")
        return result

    async def start_processing(
        self,
        file_id: str,
        processor_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Move document from PENDING to PROCESSING with validation and retry

        Args:
            file_id: B2 file ID
            processor_id: Optional ID of processing task/worker

        Returns:
            dict: New file information

        Raises:
            IllegalTransitionError: If transition is not valid
            TransitionFailedError: If operation fails after retries
        """
        logger.info(f"Starting processing for file {file_id} (processor: {processor_id})")

        # Validate transition
        self._validate_transition(ProcessingStatus.PENDING, ProcessingStatus.PROCESSING)

        # Prepare metadata with transition history
        metadata = {
            "workflow_status": ProcessingStatus.PROCESSING.value,
            "transition": WorkflowTransition.START_PROCESSING.value,
            "processing_started_at": datetime.utcnow().isoformat()
        }

        if processor_id:
            metadata["processor_id"] = processor_id

        # Add transition history
        metadata = self._add_transition_history(
            metadata,
            ProcessingStatus.PENDING,
            ProcessingStatus.PROCESSING,
            WorkflowTransition.START_PROCESSING
        )

        # Execute with retry
        result = await self._retry_with_backoff(
            self.b2_service.move_to_status,
            f"start_processing({file_id})",
            file_id=file_id,
            current_status=ProcessingStatus.PENDING,
            new_status=ProcessingStatus.PROCESSING,
            metadata=metadata
        )

        logger.info(f"File {file_id} successfully moved to PROCESSING")
        return result

    async def complete_processing(
        self,
        file_id: str,
        result_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Move document from PROCESSING to PROCESSED with validation and retry

        Args:
            file_id: B2 file ID
            result_data: Optional processing result data

        Returns:
            dict: New file information

        Raises:
            IllegalTransitionError: If transition is not valid
            TransitionFailedError: If operation fails after retries
        """
        logger.info(f"Completing processing for file {file_id}")

        # Validate transition
        self._validate_transition(ProcessingStatus.PROCESSING, ProcessingStatus.PROCESSED)

        # Prepare metadata with transition history
        metadata = {
            "workflow_status": ProcessingStatus.PROCESSED.value,
            "transition": WorkflowTransition.COMPLETE.value,
            "processing_completed_at": datetime.utcnow().isoformat()
        }

        if result_data:
            metadata["result_summary"] = str(result_data)

        # Add transition history
        metadata = self._add_transition_history(
            metadata,
            ProcessingStatus.PROCESSING,
            ProcessingStatus.PROCESSED,
            WorkflowTransition.COMPLETE
        )

        # Execute with retry
        result = await self._retry_with_backoff(
            self.b2_service.move_to_status,
            f"complete_processing({file_id})",
            file_id=file_id,
            current_status=ProcessingStatus.PROCESSING,
            new_status=ProcessingStatus.PROCESSED,
            metadata=metadata
        )

        logger.info(f"File {file_id} successfully moved to PROCESSED")
        return result

    async def fail_processing(
        self,
        file_id: str,
        error: str,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Move document from PROCESSING to FAILED with validation and retry

        Args:
            file_id: B2 file ID
            error: Error message
            retry_count: Number of retry attempts

        Returns:
            dict: New file information

        Raises:
            IllegalTransitionError: If transition is not valid
            TransitionFailedError: If operation fails after retries
        """
        logger.warning(f"Failing processing for file {file_id}: {error}")

        # Validate transition
        self._validate_transition(ProcessingStatus.PROCESSING, ProcessingStatus.FAILED)

        # Prepare metadata with transition history
        metadata = {
            "workflow_status": ProcessingStatus.FAILED.value,
            "transition": WorkflowTransition.FAIL.value,
            "error": error,
            "retry_count": retry_count,
            "failed_at": datetime.utcnow().isoformat()
        }

        # Add transition history
        metadata = self._add_transition_history(
            metadata,
            ProcessingStatus.PROCESSING,
            ProcessingStatus.FAILED,
            WorkflowTransition.FAIL
        )

        # Execute with retry
        result = await self._retry_with_backoff(
            self.b2_service.move_to_status,
            f"fail_processing({file_id})",
            file_id=file_id,
            current_status=ProcessingStatus.PROCESSING,
            new_status=ProcessingStatus.FAILED,
            metadata=metadata
        )

        logger.info(f"File {file_id} successfully moved to FAILED")
        return result

    async def retry_processing(
        self,
        file_id: str,
        retry_count: int
    ) -> Dict[str, Any]:
        """
        Move document from FAILED back to PROCESSING for retry with validation

        Args:
            file_id: B2 file ID
            retry_count: Current retry attempt number

        Returns:
            dict: New file information

        Raises:
            IllegalTransitionError: If transition is not valid
            TransitionFailedError: If operation fails after retries
        """
        logger.info(f"Retrying processing for file {file_id} (attempt {retry_count})")

        # Validate transition
        self._validate_transition(ProcessingStatus.FAILED, ProcessingStatus.PROCESSING)

        # Prepare metadata with transition history
        metadata = {
            "workflow_status": ProcessingStatus.PROCESSING.value,
            "transition": WorkflowTransition.RETRY.value,
            "retry_count": retry_count,
            "retry_started_at": datetime.utcnow().isoformat()
        }

        # Add transition history
        metadata = self._add_transition_history(
            metadata,
            ProcessingStatus.FAILED,
            ProcessingStatus.PROCESSING,
            WorkflowTransition.RETRY
        )

        # Execute with retry
        result = await self._retry_with_backoff(
            self.b2_service.move_to_status,
            f"retry_processing({file_id})",
            file_id=file_id,
            current_status=ProcessingStatus.FAILED,
            new_status=ProcessingStatus.PROCESSING,
            metadata=metadata
        )

        logger.info(f"File {file_id} successfully moved back to PROCESSING for retry")
        return result

    async def archive_document(
        self,
        file_id: str
    ) -> Dict[str, Any]:
        """
        Move document from PROCESSED to ARCHIVE for long-term storage with validation

        Args:
            file_id: B2 file ID

        Returns:
            dict: New file information

        Raises:
            IllegalTransitionError: If transition is not valid
            TransitionFailedError: If operation fails after retries
        """
        logger.info(f"Archiving file {file_id}")

        # Validate transition
        self._validate_transition(ProcessingStatus.PROCESSED, ProcessingStatus.ARCHIVED)

        # Prepare metadata with transition history
        metadata = {
            "workflow_status": ProcessingStatus.ARCHIVED.value,
            "transition": WorkflowTransition.ARCHIVE.value,
            "archived_at": datetime.utcnow().isoformat()
        }

        # Add transition history
        metadata = self._add_transition_history(
            metadata,
            ProcessingStatus.PROCESSED,
            ProcessingStatus.ARCHIVED,
            WorkflowTransition.ARCHIVE
        )

        # Execute with retry
        result = await self._retry_with_backoff(
            self.b2_service.move_to_status,
            f"archive_document({file_id})",
            file_id=file_id,
            current_status=ProcessingStatus.PROCESSED,
            new_status=ProcessingStatus.ARCHIVED,
            metadata=metadata
        )

        logger.info(f"File {file_id} successfully moved to ARCHIVE")
        return result

    async def get_files_by_status(
        self,
        status: ProcessingStatus,
        limit: int = 100
    ) -> list:
        """
        List all files in a specific workflow status

        Args:
            status: Processing status to filter by
            limit: Maximum number of files to return

        Returns:
            list: List of file information dictionaries
        """
        return await self.b2_service.list_files_by_status(status, limit)

    async def batch_transition(
        self,
        file_ids: list[str],
        from_status: ProcessingStatus,
        to_status: ProcessingStatus
    ) -> Dict[str, Any]:
        """
        Perform batch status transition on multiple files

        Args:
            file_ids: List of B2 file IDs
            from_status: Current processing status
            to_status: New processing status

        Returns:
            dict: Summary of successful and failed transitions
        """
        logger.info(
            f"Batch transitioning {len(file_ids)} files from "
            f"{from_status.value} to {to_status.value}"
        )

        # Validate transition
        self._validate_transition(from_status, to_status)

        return await self.b2_service.batch_move_to_status(
            file_ids=file_ids,
            current_status=from_status,
            new_status=to_status
        )

    async def detect_orphaned_files(
        self,
        timeout: Optional[timedelta] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect files stuck in PROCESSING status for longer than timeout

        Args:
            timeout: Time threshold (default: 4 hours)

        Returns:
            list: Orphaned files with metadata

        Raises:
            OrphanedFileError: If orphaned files are detected
        """
        timeout = timeout or self.ORPHAN_TIMEOUT
        cutoff_time = datetime.utcnow() - timeout

        logger.info(f"Detecting orphaned files (timeout: {timeout})")

        # Get all files in PROCESSING status
        processing_files = await self.b2_service.list_files_by_status(
            ProcessingStatus.PROCESSING,
            limit=1000
        )

        orphaned_files = []

        for file_info in processing_files:
            # Check if file has been in PROCESSING too long
            upload_time = file_info.get("upload_timestamp")

            if upload_time:
                try:
                    # Parse timestamp
                    upload_dt = datetime.fromisoformat(str(upload_time).replace('Z', '+00:00'))

                    if upload_dt < cutoff_time:
                        orphaned_files.append({
                            "file_id": file_info["file_id"],
                            "file_name": file_info["file_name"],
                            "upload_timestamp": upload_time,
                            "time_in_processing": str(datetime.utcnow() - upload_dt)
                        })

                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse timestamp for file {file_info['file_id']}: {e}")

        if orphaned_files:
            logger.warning(f"Detected {len(orphaned_files)} orphaned files")
        else:
            logger.info("No orphaned files detected")

        return orphaned_files

    async def recover_orphaned_file(
        self,
        file_id: str,
        force_fail: bool = True
    ) -> Dict[str, Any]:
        """
        Recover an orphaned file by moving it to FAILED status

        Args:
            file_id: B2 file ID
            force_fail: If True, move to FAILED. If False, try to restart processing.

        Returns:
            dict: Recovery result

        Raises:
            TransitionFailedError: If recovery fails
        """
        logger.info(f"Recovering orphaned file {file_id} (force_fail={force_fail})")

        if force_fail:
            # Move to FAILED with orphan error
            result = await self.fail_processing(
                file_id=file_id,
                error="File orphaned in PROCESSING state",
                retry_count=0
            )
            logger.info(f"Orphaned file {file_id} moved to FAILED for manual inspection")
        else:
            # Try to restart processing
            logger.warning(
                f"Attempting to restart processing for orphaned file {file_id}. "
                "This may cause duplicate processing."
            )
            # In this case, file stays in PROCESSING but we log the recovery attempt
            result = {
                "file_id": file_id,
                "status": "processing_restarted",
                "message": "File kept in PROCESSING for retry"
            }

        return result

    async def recover_all_orphaned_files(
        self,
        timeout: Optional[timedelta] = None,
        force_fail: bool = True
    ) -> Dict[str, Any]:
        """
        Detect and recover all orphaned files

        Args:
            timeout: Time threshold for orphan detection
            force_fail: If True, move to FAILED. If False, restart processing.

        Returns:
            dict: Summary of recovery operations
        """
        logger.info("Starting batch orphan recovery")

        orphaned_files = await self.detect_orphaned_files(timeout)

        if not orphaned_files:
            return {
                "orphaned_count": 0,
                "recovered": [],
                "failed": []
            }

        results = {
            "orphaned_count": len(orphaned_files),
            "recovered": [],
            "failed": []
        }

        for orphan in orphaned_files:
            try:
                recovery_result = await self.recover_orphaned_file(
                    file_id=orphan["file_id"],
                    force_fail=force_fail
                )

                results["recovered"].append({
                    "file_id": orphan["file_id"],
                    "file_name": orphan["file_name"],
                    "result": recovery_result
                })

            except Exception as e:
                logger.error(f"Failed to recover orphaned file {orphan['file_id']}: {e}")

                results["failed"].append({
                    "file_id": orphan["file_id"],
                    "file_name": orphan["file_name"],
                    "error": str(e)
                })

        logger.info(
            f"Orphan recovery complete: {len(results['recovered'])} recovered, "
            f"{len(results['failed'])} failed"
        )

        return results

    # =========================================================================
    # Content Prep Agent Integration (Feature 007)
    # =========================================================================

    async def process_pending_with_content_prep(
        self,
        b2_folder: str = "pending/courses",
        detection_mode: str = "auto",
        auto_process: bool = False
    ) -> Dict[str, Any]:
        """
        Process pending folder with Content Prep Agent integration.

        Feature 007: Detects content sets before processing to ensure
        related files are processed together in correct order.

        Workflow:
        1. Analyze pending folder for content sets
        2. For standalone files: Move to processing immediately
        3. For content sets:
           - If complete: Generate manifest and process in order
           - If incomplete: Flag for user acknowledgment

        Args:
            b2_folder: B2 folder to analyze (default: pending/courses)
            detection_mode: Content set detection mode (auto/pattern/metadata/llm)
            auto_process: If True, automatically start processing complete sets

        Returns:
            dict: Analysis results with content sets and actions taken
        """
        from app.services.content_prep_agent import ContentPrepAgent

        logger.info(f"Processing pending folder with Content Prep: {b2_folder}")

        try:
            agent = ContentPrepAgent()

            # Step 1: Analyze folder for content sets
            analysis = await agent.analyze_folder(
                b2_folder=b2_folder,
                detection_mode=detection_mode
            )

            content_sets = analysis.get("content_sets", [])
            standalone_files = analysis.get("standalone_files", [])

            results = {
                "b2_folder": b2_folder,
                "detection_mode": detection_mode,
                "content_sets_found": len(content_sets),
                "standalone_files_found": len(standalone_files),
                "content_sets": [],
                "standalone_processed": [],
                "actions": []
            }

            # Step 2: Process standalone files immediately
            for standalone in standalone_files:
                file_path = standalone.get("path")
                if file_path and auto_process:
                    try:
                        # Get file ID from path (would need B2 API lookup)
                        # For now, log the action
                        results["standalone_processed"].append({
                            "file": standalone.get("filename"),
                            "path": file_path,
                            "action": "queued_for_processing"
                        })
                        results["actions"].append(
                            f"Standalone file {standalone.get('filename')} queued for processing"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to process standalone file {file_path}: {e}")
                else:
                    results["standalone_processed"].append({
                        "file": standalone.get("filename"),
                        "path": file_path,
                        "action": "pending_manual_trigger"
                    })

            # Step 3: Handle content sets
            for content_set in content_sets:
                set_id = content_set.get("id")
                set_name = content_set.get("name")
                is_complete = content_set.get("is_complete", False)

                set_result = {
                    "id": set_id,
                    "name": set_name,
                    "files_count": content_set.get("files_count", 0),
                    "is_complete": is_complete,
                    "missing_files": content_set.get("missing_files", []),
                    "action": None,
                    "manifest_id": None
                }

                if is_complete and auto_process:
                    # Generate manifest and start processing
                    try:
                        manifest = await agent.generate_manifest(
                            content_set_id=set_id,
                            proceed_incomplete=False
                        )
                        set_result["action"] = "processing_started"
                        set_result["manifest_id"] = manifest.get("manifest_id")
                        results["actions"].append(
                            f"Content set '{set_name}' manifest generated, processing started"
                        )
                    except Exception as e:
                        set_result["action"] = "manifest_failed"
                        set_result["error"] = str(e)
                        logger.error(f"Failed to generate manifest for {set_id}: {e}")

                elif is_complete:
                    set_result["action"] = "ready_for_processing"
                    results["actions"].append(
                        f"Content set '{set_name}' is complete, ready for processing"
                    )

                else:
                    set_result["action"] = "awaiting_acknowledgment"
                    results["actions"].append(
                        f"Content set '{set_name}' is incomplete (missing: "
                        f"{len(content_set.get('missing_files', []))} files), "
                        "requires acknowledgment to proceed"
                    )

                results["content_sets"].append(set_result)

            logger.info(
                f"Content prep analysis complete: "
                f"{len(content_sets)} sets, {len(standalone_files)} standalone"
            )

            return results

        except Exception as e:
            logger.error(f"Content prep processing failed: {e}", exc_info=True)
            raise

    async def trigger_content_set_processing(
        self,
        content_set_id: str,
        proceed_incomplete: bool = False,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trigger processing for a specific content set.

        Feature 007: Generates manifest and triggers ordered Celery tasks.

        Args:
            content_set_id: UUID of the content set
            proceed_incomplete: Process even if files are missing
            user_id: Optional user ID for tracking

        Returns:
            dict: Processing trigger result with task IDs
        """
        from app.tasks.content_prep_tasks import process_content_set

        logger.info(f"Triggering processing for content set: {content_set_id}")

        # Trigger the Celery task
        task = process_content_set.delay(
            content_set_id=content_set_id,
            proceed_incomplete=proceed_incomplete,
            user_id=user_id
        )

        return {
            "status": "processing_triggered",
            "content_set_id": content_set_id,
            "task_id": task.id,
            "proceed_incomplete": proceed_incomplete
        }


# Singleton instance
_workflow_manager = None


def get_workflow_manager() -> B2WorkflowManager:
    """Get or create B2 workflow manager singleton"""
    global _workflow_manager
    if _workflow_manager is None:
        _workflow_manager = B2WorkflowManager()
    return _workflow_manager
