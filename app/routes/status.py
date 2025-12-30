"""
Empire v7.3 - REST Status Endpoints - Task 11
Provides REST endpoints for polling processing status as a WebSocket fallback

This module provides:
- Unified status polling for documents, queries, and batch operations
- Consistent response schema aligned with WebSocket messages
- Rate limiting to prevent polling abuse
- Support for both Celery task IDs and resource IDs
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Union, Literal
from datetime import datetime
from enum import Enum
import structlog

from app.middleware.rate_limit import limiter
from app.middleware.clerk_auth import verify_clerk_token
from app.core.supabase_client import get_supabase_client

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/status", tags=["status"])


# ============================================================================
# Response Models (Task 11.2)
# ============================================================================

class ResourceType(str, Enum):
    """Types of resources that can be polled for status."""
    DOCUMENT = "document"
    QUERY = "query"
    BATCH_OPERATION = "batch_operation"
    TASK = "task"  # Generic Celery task


class ProcessingStatus(str, Enum):
    """Status values aligned with WebSocket messages."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    STARTED = "started"  # Celery compatibility
    SUCCESS = "success"
    COMPLETED = "completed"
    FAILURE = "failure"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ProgressInfo(BaseModel):
    """Progress information for long-running operations."""
    current: int = Field(0, description="Current progress value")
    total: int = Field(100, description="Total progress value")
    percentage: float = Field(0.0, description="Progress percentage (0-100)")
    message: str = Field("", description="Current status message")
    stage: Optional[str] = Field(None, description="Current processing stage")
    stage_details: Optional[dict] = Field(None, description="Stage-specific details")


class StatusResponse(BaseModel):
    """
    Unified status response schema.

    This schema is designed to be consistent with WebSocket status messages
    to simplify frontend integration when switching between WebSocket and REST.
    """
    # Resource identification
    resource_id: str = Field(..., description="ID of the resource (document, query, task)")
    resource_type: ResourceType = Field(..., description="Type of resource")

    # Status information
    status: ProcessingStatus = Field(..., description="Current processing status")
    status_message: str = Field("", description="Human-readable status message")

    # Progress tracking
    progress: Optional[ProgressInfo] = Field(None, description="Progress info for long-running ops")

    # Timestamps
    created_at: Optional[datetime] = Field(None, description="When the resource was created")
    updated_at: Optional[datetime] = Field(None, description="When status was last updated")
    completed_at: Optional[datetime] = Field(None, description="When processing completed")

    # Result data (only populated on completion)
    result: Optional[dict] = Field(None, description="Result data (when completed)")
    error: Optional[str] = Field(None, description="Error message (when failed)")
    error_details: Optional[dict] = Field(None, description="Detailed error information")

    # Metadata
    metadata: Optional[dict] = Field(None, description="Additional resource metadata")

    # Polling hints for frontend
    poll_interval_ms: int = Field(
        2000,
        description="Recommended polling interval in milliseconds"
    )
    should_continue_polling: bool = Field(
        True,
        description="Whether client should continue polling"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "resource_id": "doc-123-456",
                "resource_type": "document",
                "status": "processing",
                "status_message": "Extracting text from PDF...",
                "progress": {
                    "current": 45,
                    "total": 100,
                    "percentage": 45.0,
                    "message": "Page 5 of 11",
                    "stage": "text_extraction"
                },
                "created_at": "2025-01-15T10:30:00Z",
                "updated_at": "2025-01-15T10:30:45Z",
                "poll_interval_ms": 2000,
                "should_continue_polling": True
            }
        }


class BatchStatusResponse(BaseModel):
    """Response for batch status queries."""
    statuses: List[StatusResponse] = Field(..., description="List of status responses")
    total_count: int = Field(..., description="Total items requested")
    found_count: int = Field(..., description="Items found with status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


# ============================================================================
# Helper Functions
# ============================================================================

def normalize_status(raw_status: str) -> ProcessingStatus:
    """
    Normalize status strings from various sources to ProcessingStatus enum.

    Args:
        raw_status: Raw status string from Celery, database, etc.

    Returns:
        Normalized ProcessingStatus enum value
    """
    status_map = {
        # Celery states
        "PENDING": ProcessingStatus.PENDING,
        "STARTED": ProcessingStatus.STARTED,
        "SUCCESS": ProcessingStatus.SUCCESS,
        "FAILURE": ProcessingStatus.FAILURE,
        "RETRY": ProcessingStatus.PROCESSING,
        "REVOKED": ProcessingStatus.CANCELLED,

        # Database states
        "pending": ProcessingStatus.PENDING,
        "queued": ProcessingStatus.QUEUED,
        "processing": ProcessingStatus.PROCESSING,
        "in_progress": ProcessingStatus.PROCESSING,
        "completed": ProcessingStatus.COMPLETED,
        "success": ProcessingStatus.SUCCESS,
        "failed": ProcessingStatus.FAILED,
        "failure": ProcessingStatus.FAILURE,
        "cancelled": ProcessingStatus.CANCELLED,
        "canceled": ProcessingStatus.CANCELLED,
    }

    return status_map.get(raw_status.lower() if raw_status else "", ProcessingStatus.UNKNOWN)


def determine_poll_interval(status: ProcessingStatus) -> int:
    """
    Determine recommended polling interval based on status.

    Args:
        status: Current processing status

    Returns:
        Recommended polling interval in milliseconds
    """
    if status in [ProcessingStatus.SUCCESS, ProcessingStatus.COMPLETED,
                  ProcessingStatus.FAILURE, ProcessingStatus.FAILED,
                  ProcessingStatus.CANCELLED]:
        return 0  # No need to continue polling
    elif status == ProcessingStatus.PENDING:
        return 5000  # Poll less frequently for pending
    elif status == ProcessingStatus.QUEUED:
        return 3000  # Slightly faster for queued
    else:
        return 2000  # Standard interval for processing


def should_continue_polling(status: ProcessingStatus) -> bool:
    """
    Determine if client should continue polling.

    Args:
        status: Current processing status

    Returns:
        True if polling should continue, False otherwise
    """
    terminal_states = [
        ProcessingStatus.SUCCESS,
        ProcessingStatus.COMPLETED,
        ProcessingStatus.FAILURE,
        ProcessingStatus.FAILED,
        ProcessingStatus.CANCELLED
    ]
    return status not in terminal_states


async def get_celery_task_status(task_id: str) -> dict:
    """
    Get status of a Celery task.

    Args:
        task_id: Celery task ID

    Returns:
        Dict with status information
    """
    try:
        from celery.result import AsyncResult
        from app.celery_app import celery_app

        task = AsyncResult(task_id, app=celery_app)

        result_data = None
        error_msg = None
        progress = None

        if task.successful():
            result_data = task.result
        elif task.failed():
            error_msg = str(task.result) if task.result else "Task failed"
        elif task.state == "STARTED" and task.info:
            # Task is in progress with metadata
            progress = task.info

        return {
            "status": task.state,
            "result": result_data,
            "error": error_msg,
            "progress": progress
        }

    except Exception as e:
        logger.error("Failed to get Celery task status", task_id=task_id, error=str(e))
        return {
            "status": "UNKNOWN",
            "result": None,
            "error": str(e),
            "progress": None
        }


async def get_document_status(document_id: str) -> dict:
    """
    Get processing status for a document.

    Args:
        document_id: Document ID

    Returns:
        Dict with status information
    """
    try:
        supabase = get_supabase_client()

        # Query documents_v2 table for document status
        result = supabase.table("documents_v2").select(
            "id, status, processing_stage, progress, created_at, updated_at, error_message, metadata"
        ).eq("id", document_id).execute()

        if not result.data or len(result.data) == 0:
            return None

        doc = result.data[0]

        progress_info = None
        if doc.get("progress"):
            progress_data = doc["progress"]
            progress_info = {
                "current": progress_data.get("current", 0),
                "total": progress_data.get("total", 100),
                "percentage": progress_data.get("percentage", 0),
                "message": progress_data.get("message", ""),
                "stage": doc.get("processing_stage")
            }

        return {
            "status": doc.get("status", "unknown"),
            "progress": progress_info,
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
            "error": doc.get("error_message"),
            "metadata": doc.get("metadata")
        }

    except Exception as e:
        logger.error("Failed to get document status", document_id=document_id, error=str(e))
        return None


async def get_batch_operation_status(operation_id: str) -> dict:
    """
    Get status of a batch operation.

    Args:
        operation_id: Batch operation ID

    Returns:
        Dict with status information
    """
    try:
        supabase = get_supabase_client()

        result = supabase.table("batch_operations").select("*").eq("id", operation_id).execute()

        if not result.data or len(result.data) == 0:
            return None

        op = result.data[0]

        # Calculate progress
        total = op.get("total_items", 0)
        processed = op.get("processed_items", 0)
        percentage = (processed / total * 100) if total > 0 else 0

        return {
            "status": op.get("status", "unknown"),
            "progress": {
                "current": processed,
                "total": total,
                "percentage": round(percentage, 2),
                "message": f"Processed {processed} of {total} items",
                "stage": op.get("operation_type")
            },
            "created_at": op.get("created_at"),
            "updated_at": op.get("updated_at"),
            "completed_at": op.get("completed_at"),
            "error": op.get("error_message"),
            "metadata": {
                "operation_type": op.get("operation_type"),
                "successful_items": op.get("successful_items", 0),
                "failed_items": op.get("failed_items", 0)
            }
        }

    except Exception as e:
        logger.error("Failed to get batch operation status", operation_id=operation_id, error=str(e))
        return None


# ============================================================================
# Endpoints (Task 11.1)
# ============================================================================

@router.get(
    "/task/{task_id}",
    response_model=StatusResponse,
    summary="Get Celery task status",
    description="Poll status for any Celery async task. Rate limited to 60 requests/minute."
)
@limiter.limit("60/minute")
async def get_task_status_endpoint(
    request: Request,
    task_id: str,
    user: dict = Depends(verify_clerk_token)
):
    """
    Get status of a Celery async task.

    Use this endpoint to poll for results from async operations like:
    - /api/query/adaptive/async
    - /api/query/auto/async
    - /api/query/batch

    **Rate Limited**: 60 requests per minute per user/IP

    Args:
        task_id: Celery task ID returned from async submission

    Returns:
        StatusResponse with task status and result (when complete)
    """
    logger.info("Task status poll", task_id=task_id, user_id=user["user_id"])

    task_info = await get_celery_task_status(task_id)

    status = normalize_status(task_info["status"])
    poll_interval = determine_poll_interval(status)
    continue_polling = should_continue_polling(status)

    # Build progress info if available
    progress = None
    if task_info.get("progress") and isinstance(task_info["progress"], dict):
        prog_data = task_info["progress"]
        progress = ProgressInfo(
            current=prog_data.get("iteration", prog_data.get("current", 0)),
            total=prog_data.get("max_iterations", prog_data.get("total", 100)),
            percentage=prog_data.get("percentage", 0),
            message=prog_data.get("message", ""),
            stage=prog_data.get("stage"),
            stage_details=prog_data.get("details")
        )

    # Build status message
    status_message = "Task processing"
    if status == ProcessingStatus.PENDING:
        status_message = "Task is waiting to start"
    elif status == ProcessingStatus.STARTED:
        status_message = "Task is currently processing"
    elif status == ProcessingStatus.SUCCESS:
        status_message = "Task completed successfully"
    elif status == ProcessingStatus.FAILURE:
        status_message = f"Task failed: {task_info.get('error', 'Unknown error')}"

    return StatusResponse(
        resource_id=task_id,
        resource_type=ResourceType.TASK,
        status=status,
        status_message=status_message,
        progress=progress,
        result=task_info.get("result") if status == ProcessingStatus.SUCCESS else None,
        error=task_info.get("error"),
        poll_interval_ms=poll_interval,
        should_continue_polling=continue_polling,
        updated_at=datetime.utcnow()
    )


@router.get(
    "/document/{document_id}",
    response_model=StatusResponse,
    summary="Get document processing status",
    description="Poll status for document upload/processing. Rate limited to 60 requests/minute."
)
@limiter.limit("60/minute")
async def get_document_status_endpoint(
    request: Request,
    document_id: str,
    user: dict = Depends(verify_clerk_token)
):
    """
    Get processing status for a document.

    Use this as a fallback to WebSocket /ws/document/{document_id} endpoint.

    **Rate Limited**: 60 requests per minute per user/IP

    Args:
        document_id: Document ID to check status for

    Returns:
        StatusResponse with document processing status
    """
    logger.info("Document status poll", document_id=document_id, user_id=user["user_id"])

    doc_info = await get_document_status(document_id)

    if doc_info is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document {document_id} not found"
        )

    status = normalize_status(doc_info["status"])
    poll_interval = determine_poll_interval(status)
    continue_polling = should_continue_polling(status)

    # Build progress info
    progress = None
    if doc_info.get("progress"):
        prog_data = doc_info["progress"]
        progress = ProgressInfo(
            current=prog_data.get("current", 0),
            total=prog_data.get("total", 100),
            percentage=prog_data.get("percentage", 0),
            message=prog_data.get("message", ""),
            stage=prog_data.get("stage")
        )

    # Build status message
    status_message = f"Document {status.value}"
    if progress and progress.stage:
        status_message = f"Processing: {progress.stage}"

    return StatusResponse(
        resource_id=document_id,
        resource_type=ResourceType.DOCUMENT,
        status=status,
        status_message=status_message,
        progress=progress,
        created_at=datetime.fromisoformat(doc_info["created_at"]) if doc_info.get("created_at") else None,
        updated_at=datetime.fromisoformat(doc_info["updated_at"]) if doc_info.get("updated_at") else None,
        error=doc_info.get("error"),
        metadata=doc_info.get("metadata"),
        poll_interval_ms=poll_interval,
        should_continue_polling=continue_polling
    )


@router.get(
    "/batch/{operation_id}",
    response_model=StatusResponse,
    summary="Get batch operation status",
    description="Poll status for batch operations. Rate limited to 60 requests/minute."
)
@limiter.limit("60/minute")
async def get_batch_operation_status_endpoint(
    request: Request,
    operation_id: str,
    user: dict = Depends(verify_clerk_token)
):
    """
    Get status of a batch operation.

    Use this to poll for bulk upload, bulk delete, or bulk reprocess operations.

    **Rate Limited**: 60 requests per minute per user/IP

    Args:
        operation_id: Batch operation ID

    Returns:
        StatusResponse with batch operation status
    """
    logger.info("Batch operation status poll", operation_id=operation_id, user_id=user["user_id"])

    batch_info = await get_batch_operation_status(operation_id)

    if batch_info is None:
        raise HTTPException(
            status_code=404,
            detail=f"Batch operation {operation_id} not found"
        )

    status = normalize_status(batch_info["status"])
    poll_interval = determine_poll_interval(status)
    continue_polling = should_continue_polling(status)

    # Build progress info
    progress = None
    if batch_info.get("progress"):
        prog_data = batch_info["progress"]
        progress = ProgressInfo(
            current=prog_data.get("current", 0),
            total=prog_data.get("total", 100),
            percentage=prog_data.get("percentage", 0),
            message=prog_data.get("message", ""),
            stage=prog_data.get("stage")
        )

    return StatusResponse(
        resource_id=operation_id,
        resource_type=ResourceType.BATCH_OPERATION,
        status=status,
        status_message=f"Batch operation {status.value}",
        progress=progress,
        created_at=datetime.fromisoformat(batch_info["created_at"]) if batch_info.get("created_at") else None,
        updated_at=datetime.fromisoformat(batch_info["updated_at"]) if batch_info.get("updated_at") else None,
        completed_at=datetime.fromisoformat(batch_info["completed_at"]) if batch_info.get("completed_at") else None,
        error=batch_info.get("error"),
        metadata=batch_info.get("metadata"),
        poll_interval_ms=poll_interval,
        should_continue_polling=continue_polling
    )


@router.post(
    "/batch-check",
    response_model=BatchStatusResponse,
    summary="Batch status check",
    description="Check status of multiple resources in a single request. Rate limited to 30 requests/minute."
)
@limiter.limit("30/minute")
async def batch_status_check(
    request: Request,
    resource_ids: List[str] = Query(..., description="List of resource IDs to check", max_length=50),
    resource_type: ResourceType = Query(..., description="Type of resources to check"),
    user: dict = Depends(verify_clerk_token)
):
    """
    Check status of multiple resources in a single request.

    More efficient than making individual requests for each resource.
    Useful for dashboard views or progress bars showing multiple items.

    **Rate Limited**: 30 requests per minute per user/IP
    **Max Items**: 50 resource IDs per request

    Args:
        resource_ids: List of resource IDs to check (max 50)
        resource_type: Type of all resources (must be same type)

    Returns:
        BatchStatusResponse with status for each found resource
    """
    logger.info(
        "Batch status check",
        resource_type=resource_type,
        count=len(resource_ids),
        user_id=user["user_id"]
    )

    statuses = []

    for resource_id in resource_ids:
        try:
            if resource_type == ResourceType.TASK:
                info = await get_celery_task_status(resource_id)
                if info:
                    status = normalize_status(info["status"])
                    statuses.append(StatusResponse(
                        resource_id=resource_id,
                        resource_type=resource_type,
                        status=status,
                        status_message=f"Task {status.value}",
                        result=info.get("result"),
                        error=info.get("error"),
                        poll_interval_ms=determine_poll_interval(status),
                        should_continue_polling=should_continue_polling(status)
                    ))

            elif resource_type == ResourceType.DOCUMENT:
                info = await get_document_status(resource_id)
                if info:
                    status = normalize_status(info["status"])
                    statuses.append(StatusResponse(
                        resource_id=resource_id,
                        resource_type=resource_type,
                        status=status,
                        status_message=f"Document {status.value}",
                        poll_interval_ms=determine_poll_interval(status),
                        should_continue_polling=should_continue_polling(status)
                    ))

            elif resource_type == ResourceType.BATCH_OPERATION:
                info = await get_batch_operation_status(resource_id)
                if info:
                    status = normalize_status(info["status"])
                    statuses.append(StatusResponse(
                        resource_id=resource_id,
                        resource_type=resource_type,
                        status=status,
                        status_message=f"Batch {status.value}",
                        poll_interval_ms=determine_poll_interval(status),
                        should_continue_polling=should_continue_polling(status)
                    ))

        except Exception as e:
            logger.warning(
                "Failed to get status for resource",
                resource_id=resource_id,
                error=str(e)
            )

    return BatchStatusResponse(
        statuses=statuses,
        total_count=len(resource_ids),
        found_count=len(statuses),
        timestamp=datetime.utcnow()
    )


@router.get(
    "/health",
    summary="Status service health check",
    description="Health check for the status polling service."
)
async def status_service_health():
    """
    Health check for the status polling service.

    Returns:
        Health status and capabilities
    """
    return {
        "status": "healthy",
        "service": "status_polling",
        "capabilities": [
            "task_status",
            "document_status",
            "batch_operation_status",
            "batch_check"
        ],
        "rate_limits": {
            "individual_status": "60/minute",
            "batch_check": "30/minute"
        },
        "websocket_fallback": True,
        "timestamp": datetime.utcnow().isoformat()
    }
