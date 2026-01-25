"""
Empire v7.3 - Document Processing Tasks
Celery tasks for document parsing, validation, and metadata extraction
"""

from app.celery_app import celery_app, PRIORITY_URGENT, PRIORITY_HIGH, PRIORITY_NORMAL, PRIORITY_LOW, PRIORITY_BACKGROUND
from app.services.supabase_storage import get_supabase_storage
from app.services.notification_dispatcher import get_notification_dispatcher
from app.services.b2_workflow import get_workflow_manager
from typing import Dict, Any, Optional
import os
import asyncio
import logging

logger = logging.getLogger(__name__)

# Get notification dispatcher and workflow manager
dispatcher = get_notification_dispatcher()
workflow_manager = get_workflow_manager()


@celery_app.task(name='app.tasks.document_processing.process_document', bind=True)
def process_document(self, file_id: str, filename: str, b2_path: str) -> Dict[str, Any]:
    """
    Process a document: parse, extract metadata, validate

    Args:
        file_id: B2 file ID
        filename: Original filename
        b2_path: Full path in B2 storage

    Returns:
        Processing result with metadata
    """
    supabase_storage = get_supabase_storage()

    try:
        logger.info(f"📄 Processing document: {filename} (file_id: {file_id})")

        # Notify task started
        dispatcher.notify_task_started(
            task_id=self.request.id,
            task_type="document_processing",
            filename=filename
        )

        # Move file from PENDING → PROCESSING in B2
        asyncio.run(workflow_manager.start_processing(
            file_id=file_id,
            processor_id=self.request.id
        ))

        # Update status to "processing" at task start in Supabase
        asyncio.run(supabase_storage.update_document_status(
            b2_file_id=file_id,
            status="processing"
        ))

        # TODO: Call LlamaIndex service for parsing
        # TODO: Extract metadata
        # TODO: Store results

        # Placeholder implementation
        logger.info(f"✅ Document processed successfully: {filename}")

        # Move file from PROCESSING → PROCESSED in B2
        asyncio.run(workflow_manager.complete_processing(
            file_id=file_id,
            result_data={
                "task_id": self.request.id,
                "filename": filename,
                "status": "success"
            }
        ))

        # Update status to "processed" on success in Supabase
        asyncio.run(supabase_storage.update_document_status(
            b2_file_id=file_id,
            status="processed"
        ))

        # Notify task completed
        dispatcher.notify_task_completed(
            task_id=self.request.id,
            task_type="document_processing",
            filename=filename,
            result={
                "status": "success",
                "file_id": file_id,
                "filename": filename
            }
        )

        return {
            "status": "success",
            "file_id": file_id,
            "filename": filename,
            "message": "Document processing completed successfully"
        }

    except Exception as e:
        logger.error(f"❌ Document processing failed for {filename}: {e}")

        # Calculate exponential backoff: 60s, 120s, 240s
        retry_count = self.request.retries
        base_delay = 60  # Base delay in seconds
        countdown = base_delay * (2 ** retry_count)  # Exponential backoff

        logger.info(f"Retry attempt {retry_count + 1}/3 for {filename} - waiting {countdown}s")

        # Notify about retry
        dispatcher.notify_task_retry(
            task_id=self.request.id,
            task_type="document_processing",
            retry_count=retry_count,
            max_retries=3,
            filename=filename
        )

        # Update status to "failed" only if we've exhausted all retries
        if retry_count >= 2:  # Max 3 attempts (0, 1, 2)
            logger.error(f"All retry attempts exhausted for {filename}")

            # Move file from PROCESSING → FAILED in B2
            asyncio.run(workflow_manager.fail_processing(
                file_id=file_id,
                error=str(e),
                retry_count=retry_count
            ))

            # Update status to "failed" in Supabase
            asyncio.run(supabase_storage.update_document_status(
                b2_file_id=file_id,
                status="failed",
                processing_error=str(e)
            ))

            # Notify task failed
            dispatcher.notify_task_failed(
                task_id=self.request.id,
                task_type="document_processing",
                error=str(e),
                filename=filename
            )
        else:
            # Move file from FAILED → PROCESSING for retry (if this is a retry attempt)
            if retry_count > 0:
                asyncio.run(workflow_manager.retry_processing(
                    file_id=file_id,
                    retry_count=retry_count + 1
                ))

        # Retry with exponential backoff
        self.retry(exc=e, countdown=countdown, max_retries=3)


@celery_app.task(name='app.tasks.document_processing.extract_metadata', bind=True)
def extract_metadata(self, document_id: str) -> Dict[str, Any]:
    """
    Extract and classify document metadata

    Args:
        document_id: Unique document identifier

    Returns:
        Extracted metadata including department classification
    """
    try:
        print(f"📋 Extracting metadata for: {document_id}")

        # TODO: Use course classifier service
        # TODO: Extract department, tags, structure
        # TODO: Store in document_metadata table

        return {
            "status": "success",
            "document_id": document_id,
            "message": "Metadata extraction placeholder - implementation pending"
        }

    except Exception as e:
        # Calculate exponential backoff: 60s, 120s, 240s
        retry_count = self.request.retries
        base_delay = 60
        countdown = base_delay * (2 ** retry_count)

        logger.error(f"❌ Metadata extraction failed: {e}")
        logger.info(f"Retry attempt {retry_count + 1}/3 - waiting {countdown}s")

        self.retry(exc=e, countdown=countdown, max_retries=3)


@celery_app.task(name='app.tasks.document_processing.validate_document', bind=True)
def validate_document(self, document_id: str, file_hash: str) -> Dict[str, Any]:
    """
    Validate document for duplicates and integrity

    Args:
        document_id: Unique document identifier
        file_hash: SHA-256 hash of file content

    Returns:
        Validation result
    """
    try:
        print(f"🔍 Validating document: {document_id}")

        # TODO: Check for duplicates by file_hash
        # TODO: Verify file integrity
        # TODO: Check file size and format

        return {
            "status": "success",
            "document_id": document_id,
            "is_duplicate": False,
            "message": "Document validation placeholder - implementation pending"
        }

    except Exception as e:
        # Calculate exponential backoff: 60s, 120s, 240s
        retry_count = self.request.retries
        base_delay = 60
        countdown = base_delay * (2 ** retry_count)

        logger.error(f"❌ Document validation failed: {e}")
        logger.info(f"Retry attempt {retry_count + 1}/3 - waiting {countdown}s")

        self.retry(exc=e, countdown=countdown, max_retries=3)


# Helper functions for submitting tasks with priority
def submit_document_processing(
    file_id: str,
    filename: str,
    b2_path: str,
    priority: int = PRIORITY_NORMAL
) -> Any:
    """
    Submit a document processing task with specified priority

    Args:
        file_id: B2 file ID
        filename: Original filename
        b2_path: Full path in B2 storage
        priority: Task priority (0-9, 9 is highest) - use PRIORITY_* constants

    Returns:
        AsyncResult object

    Example:
        # High priority for user uploads
        submit_document_processing(file_id, filename, b2_path, priority=PRIORITY_HIGH)

        # Background processing for batch imports
        submit_document_processing(file_id, filename, b2_path, priority=PRIORITY_BACKGROUND)
    """
    return process_document.apply_async(
        args=[file_id, filename, b2_path],
        priority=priority
    )


def submit_metadata_extraction(
    document_id: str,
    priority: int = PRIORITY_NORMAL
) -> Any:
    """
    Submit a metadata extraction task with specified priority

    Args:
        document_id: Unique document identifier
        priority: Task priority (0-9, 9 is highest)

    Returns:
        AsyncResult object
    """
    return extract_metadata.apply_async(
        args=[document_id],
        priority=priority
    )


def submit_document_validation(
    document_id: str,
    file_hash: str,
    priority: int = PRIORITY_NORMAL
) -> Any:
    """
    Submit a document validation task with specified priority

    Args:
        document_id: Unique document identifier
        file_hash: SHA-256 hash of file content
        priority: Task priority (0-9, 9 is highest)

    Returns:
        AsyncResult object
    """
    return validate_document.apply_async(
        args=[document_id, file_hash],
        priority=priority
    )
