"""
Celery tasks for bulk document operations
"""

import os
import uuid
from datetime import datetime
from typing import List, Dict, Any
from celery import group, chain
import structlog
from app.celery_app import celery_app
from app.models.documents import (
    DocumentStatus,
    BatchOperationStatus,
    DocumentOperationResult
)

logger = structlog.get_logger(__name__)


@celery_app.task(name='app.tasks.bulk_operations.bulk_upload_documents', bind=True)
def bulk_upload_documents(
    self,
    operation_id: str,
    documents: List[Dict[str, Any]],
    user_id: str,
    auto_process: bool = True
) -> Dict[str, Any]:
    """
    Bulk upload documents and optionally trigger processing

    Args:
        operation_id: Unique operation ID for tracking
        documents: List of document items with file_path, filename, metadata
        user_id: User performing the operation
        auto_process: Whether to automatically process documents

    Returns:
        Dict with operation results
    """
    logger.info(
        "Starting bulk upload",
        operation_id=operation_id,
        document_count=len(documents),
        user_id=user_id
    )

    results = []
    successful = 0
    failed = 0

    try:
        # Update operation status to in_progress
        _update_operation_status(
            operation_id=operation_id,
            status=BatchOperationStatus.IN_PROGRESS,
            processed_items=0,
            successful_items=0,
            failed_items=0
        )

        for idx, doc in enumerate(documents):
            try:
                # Import here to avoid circular dependencies
                from app.services.document_management import process_document_upload

                # Process document upload
                result = process_document_upload(
                    file_path=doc['file_path'],
                    filename=doc['filename'],
                    metadata=doc.get('metadata'),
                    user_id=user_id,
                    auto_process=auto_process
                )

                results.append(DocumentOperationResult(
                    document_id=result.get('document_id'),
                    filename=doc['filename'],
                    status="success",
                    message="Document uploaded successfully"
                ))
                successful += 1

            except Exception as e:
                logger.error(
                    "Failed to upload document",
                    filename=doc['filename'],
                    error=str(e)
                )
                results.append(DocumentOperationResult(
                    filename=doc['filename'],
                    status="failed",
                    error=str(e)
                ))
                failed += 1

            # Update progress
            _update_operation_status(
                operation_id=operation_id,
                status=BatchOperationStatus.IN_PROGRESS,
                processed_items=idx + 1,
                successful_items=successful,
                failed_items=failed
            )

        # Determine final status
        if failed == 0:
            final_status = BatchOperationStatus.COMPLETED
        elif successful > 0:
            final_status = BatchOperationStatus.PARTIAL_SUCCESS
        else:
            final_status = BatchOperationStatus.FAILED

        # Update final status
        _update_operation_status(
            operation_id=operation_id,
            status=final_status,
            processed_items=len(documents),
            successful_items=successful,
            failed_items=failed,
            results=[r.dict() for r in results]
        )

        logger.info(
            "Bulk upload completed",
            operation_id=operation_id,
            successful=successful,
            failed=failed,
            status=final_status
        )

        return {
            "operation_id": operation_id,
            "status": final_status,
            "total_items": len(documents),
            "successful_items": successful,
            "failed_items": failed,
            "results": [r.dict() for r in results]
        }

    except Exception as e:
        logger.error("Bulk upload task failed", operation_id=operation_id, error=str(e))
        _update_operation_status(
            operation_id=operation_id,
            status=BatchOperationStatus.FAILED,
            processed_items=len(documents),
            successful_items=successful,
            failed_items=failed,
            error_message=str(e)
        )
        raise


@celery_app.task(name='app.tasks.bulk_operations.bulk_delete_documents', bind=True)
def bulk_delete_documents(
    self,
    operation_id: str,
    document_ids: List[str],
    user_id: str,
    soft_delete: bool = True
) -> Dict[str, Any]:
    """
    Bulk delete documents

    Args:
        operation_id: Unique operation ID for tracking
        document_ids: List of document IDs to delete
        user_id: User performing the operation
        soft_delete: Whether to soft delete (mark as deleted) vs hard delete

    Returns:
        Dict with operation results
    """
    logger.info(
        "Starting bulk delete",
        operation_id=operation_id,
        document_count=len(document_ids),
        user_id=user_id,
        soft_delete=soft_delete
    )

    results = []
    successful = 0
    failed = 0

    try:
        # Update operation status to in_progress
        _update_operation_status(
            operation_id=operation_id,
            status=BatchOperationStatus.IN_PROGRESS,
            processed_items=0,
            successful_items=0,
            failed_items=0
        )

        for idx, doc_id in enumerate(document_ids):
            try:
                # Import here to avoid circular dependencies
                from app.services.document_management import delete_document

                # Delete document
                delete_document(
                    document_id=doc_id,
                    user_id=user_id,
                    soft_delete=soft_delete
                )

                results.append(DocumentOperationResult(
                    document_id=doc_id,
                    status="success",
                    message=f"Document {'soft' if soft_delete else 'hard'} deleted successfully"
                ))
                successful += 1

            except Exception as e:
                logger.error(
                    "Failed to delete document",
                    document_id=doc_id,
                    error=str(e)
                )
                results.append(DocumentOperationResult(
                    document_id=doc_id,
                    status="failed",
                    error=str(e)
                ))
                failed += 1

            # Update progress
            _update_operation_status(
                operation_id=operation_id,
                status=BatchOperationStatus.IN_PROGRESS,
                processed_items=idx + 1,
                successful_items=successful,
                failed_items=failed
            )

        # Determine final status
        if failed == 0:
            final_status = BatchOperationStatus.COMPLETED
        elif successful > 0:
            final_status = BatchOperationStatus.PARTIAL_SUCCESS
        else:
            final_status = BatchOperationStatus.FAILED

        # Update final status
        _update_operation_status(
            operation_id=operation_id,
            status=final_status,
            processed_items=len(document_ids),
            successful_items=successful,
            failed_items=failed,
            results=[r.dict() for r in results]
        )

        logger.info(
            "Bulk delete completed",
            operation_id=operation_id,
            successful=successful,
            failed=failed,
            status=final_status
        )

        return {
            "operation_id": operation_id,
            "status": final_status,
            "total_items": len(document_ids),
            "successful_items": successful,
            "failed_items": failed,
            "results": [r.dict() for r in results]
        }

    except Exception as e:
        logger.error("Bulk delete task failed", operation_id=operation_id, error=str(e))
        _update_operation_status(
            operation_id=operation_id,
            status=BatchOperationStatus.FAILED,
            processed_items=len(document_ids),
            successful_items=successful,
            failed_items=failed,
            error_message=str(e)
        )
        raise


@celery_app.task(name='app.tasks.bulk_operations.bulk_reprocess_documents', bind=True)
def bulk_reprocess_documents(
    self,
    operation_id: str,
    document_ids: List[str],
    user_id: str,
    options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Bulk reprocess documents

    Args:
        operation_id: Unique operation ID for tracking
        document_ids: List of document IDs to reprocess
        user_id: User performing the operation
        options: Reprocessing options (force_reparse, update_embeddings, etc.)

    Returns:
        Dict with operation results
    """
    options = options or {}

    logger.info(
        "Starting bulk reprocess",
        operation_id=operation_id,
        document_count=len(document_ids),
        user_id=user_id,
        options=options
    )

    results = []
    successful = 0
    failed = 0

    try:
        # Update operation status to in_progress
        _update_operation_status(
            operation_id=operation_id,
            status=BatchOperationStatus.IN_PROGRESS,
            processed_items=0,
            successful_items=0,
            failed_items=0
        )

        for idx, doc_id in enumerate(document_ids):
            try:
                # Import here to avoid circular dependencies
                from app.services.document_management import reprocess_document

                # Reprocess document
                result = reprocess_document(  # noqa: F841
                    document_id=doc_id,
                    user_id=user_id,
                    force_reparse=options.get('force_reparse', False),
                    update_embeddings=options.get('update_embeddings', True),
                    preserve_metadata=options.get('preserve_metadata', True)
                )

                results.append(DocumentOperationResult(
                    document_id=doc_id,
                    status="success",
                    message="Document reprocessed successfully"
                ))
                successful += 1

            except Exception as e:
                logger.error(
                    "Failed to reprocess document",
                    document_id=doc_id,
                    error=str(e)
                )
                results.append(DocumentOperationResult(
                    document_id=doc_id,
                    status="failed",
                    error=str(e)
                ))
                failed += 1

            # Update progress
            _update_operation_status(
                operation_id=operation_id,
                status=BatchOperationStatus.IN_PROGRESS,
                processed_items=idx + 1,
                successful_items=successful,
                failed_items=failed
            )

        # Determine final status
        if failed == 0:
            final_status = BatchOperationStatus.COMPLETED
        elif successful > 0:
            final_status = BatchOperationStatus.PARTIAL_SUCCESS
        else:
            final_status = BatchOperationStatus.FAILED

        # Update final status
        _update_operation_status(
            operation_id=operation_id,
            status=final_status,
            processed_items=len(document_ids),
            successful_items=successful,
            failed_items=failed,
            results=[r.dict() for r in results]
        )

        logger.info(
            "Bulk reprocess completed",
            operation_id=operation_id,
            successful=successful,
            failed=failed,
            status=final_status
        )

        return {
            "operation_id": operation_id,
            "status": final_status,
            "total_items": len(document_ids),
            "successful_items": successful,
            "failed_items": failed,
            "results": [r.dict() for r in results]
        }

    except Exception as e:
        logger.error("Bulk reprocess task failed", operation_id=operation_id, error=str(e))
        _update_operation_status(
            operation_id=operation_id,
            status=BatchOperationStatus.FAILED,
            processed_items=len(document_ids),
            successful_items=successful,
            failed_items=failed,
            error_message=str(e)
        )
        raise


@celery_app.task(name='app.tasks.bulk_operations.bulk_update_metadata', bind=True)
def bulk_update_metadata(
    self,
    operation_id: str,
    updates: List[Dict[str, Any]],
    user_id: str
) -> Dict[str, Any]:
    """
    Bulk update document metadata

    Args:
        operation_id: Unique operation ID for tracking
        updates: List of metadata updates (document_id + metadata dict)
        user_id: User performing the operation

    Returns:
        Dict with operation results
    """
    logger.info(
        "Starting bulk metadata update",
        operation_id=operation_id,
        update_count=len(updates),
        user_id=user_id
    )

    results = []
    successful = 0
    failed = 0

    try:
        # Update operation status to in_progress
        _update_operation_status(
            operation_id=operation_id,
            status=BatchOperationStatus.IN_PROGRESS,
            processed_items=0,
            successful_items=0,
            failed_items=0
        )

        for idx, update_item in enumerate(updates):
            doc_id = update_item['document_id']
            metadata = update_item['metadata']

            try:
                # Import here to avoid circular dependencies
                from app.services.document_management import update_document_metadata

                # Update metadata
                update_document_metadata(
                    document_id=doc_id,
                    metadata=metadata,
                    user_id=user_id
                )

                results.append(DocumentOperationResult(
                    document_id=doc_id,
                    status="success",
                    message="Metadata updated successfully"
                ))
                successful += 1

            except Exception as e:
                logger.error(
                    "Failed to update metadata",
                    document_id=doc_id,
                    error=str(e)
                )
                results.append(DocumentOperationResult(
                    document_id=doc_id,
                    status="failed",
                    error=str(e)
                ))
                failed += 1

            # Update progress
            _update_operation_status(
                operation_id=operation_id,
                status=BatchOperationStatus.IN_PROGRESS,
                processed_items=idx + 1,
                successful_items=successful,
                failed_items=failed
            )

        # Determine final status
        if failed == 0:
            final_status = BatchOperationStatus.COMPLETED
        elif successful > 0:
            final_status = BatchOperationStatus.PARTIAL_SUCCESS
        else:
            final_status = BatchOperationStatus.FAILED

        # Update final status
        _update_operation_status(
            operation_id=operation_id,
            status=final_status,
            processed_items=len(updates),
            successful_items=successful,
            failed_items=failed,
            results=[r.dict() for r in results]
        )

        logger.info(
            "Bulk metadata update completed",
            operation_id=operation_id,
            successful=successful,
            failed=failed,
            status=final_status
        )

        return {
            "operation_id": operation_id,
            "status": final_status,
            "total_items": len(updates),
            "successful_items": successful,
            "failed_items": failed,
            "results": [r.dict() for r in results]
        }

    except Exception as e:
        logger.error("Bulk metadata update task failed", operation_id=operation_id, error=str(e))
        _update_operation_status(
            operation_id=operation_id,
            status=BatchOperationStatus.FAILED,
            processed_items=len(updates),
            successful_items=successful,
            failed_items=failed,
            error_message=str(e)
        )
        raise


def _update_operation_status(
    operation_id: str,
    status: BatchOperationStatus,
    processed_items: int,
    successful_items: int,
    failed_items: int,
    results: List[Dict] = None,
    error_message: str = None
):
    """
    Update batch operation status in Supabase

    Args:
        operation_id: Unique operation ID
        status: Operation status
        processed_items: Number of processed items
        successful_items: Number of successful items
        failed_items: Number of failed items
        results: Optional list of operation results
        error_message: Optional error message
    """
    try:
        # Import here to avoid circular dependencies
        from app.core.supabase_client import get_supabase_client

        supabase = get_supabase_client()

        update_data = {
            "status": status,
            "processed_items": processed_items,
            "successful_items": successful_items,
            "failed_items": failed_items,
            "updated_at": datetime.utcnow().isoformat()
        }

        if results is not None:
            update_data["results"] = results

        if error_message:
            update_data["error_message"] = error_message

        if status in [BatchOperationStatus.COMPLETED, BatchOperationStatus.PARTIAL_SUCCESS, BatchOperationStatus.FAILED]:
            update_data["completed_at"] = datetime.utcnow().isoformat()

        # Update batch_operations table
        supabase.table("batch_operations").update(update_data).eq("id", operation_id).execute()

    except Exception as e:
        logger.error("Failed to update operation status", operation_id=operation_id, error=str(e))
