"""
Empire v7.3 - Standardized API Response Models
Consistent response formats across all endpoints

Usage:
    from app.models.api_responses import APIResponse, success_response, error_response

    @router.get("/items/{item_id}")
    async def get_item(item_id: str) -> APIResponse[Item]:
        item = await service.get_item(item_id)
        if not item:
            return error_response(
                code="ITEM_NOT_FOUND",
                message=f"Item {item_id} not found",
                status_code=404
            )
        return success_response(data=item)
"""

import uuid
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, Generic, List, Optional, TypeVar, Union

from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse

T = TypeVar('T')


# =============================================================================
# ERROR MODELS
# =============================================================================

class ErrorDetail(BaseModel):
    """Detailed error information"""
    code: str = Field(..., description="Error code (e.g., 'VALIDATION_ERROR', 'NOT_FOUND')")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    field: Optional[str] = Field(None, description="Field that caused the error (for validation)")
    help_url: Optional[str] = Field(None, description="URL to documentation or help")

    class Config:
        json_schema_extra: ClassVar[Dict[str, Any]] = {
            "example": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid email format",
                "details": {"expected_format": "user@domain.com"},
                "field": "email"
            }
        }


class ValidationError(BaseModel):
    """Validation error for a specific field"""
    field: str = Field(..., description="Field path (e.g., 'user.email')")
    message: str = Field(..., description="Validation error message")
    value: Optional[Any] = Field(None, description="The invalid value")


# =============================================================================
# RESPONSE METADATA
# =============================================================================

class ResponseMeta(BaseModel):
    """Response metadata for tracking and debugging"""
    request_id: str = Field(..., description="Unique request identifier")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Response timestamp")
    version: str = Field(default="v1", description="API version")
    duration_ms: Optional[float] = Field(None, description="Request processing time in milliseconds")


class PaginationMeta(BaseModel):
    """Pagination metadata"""
    page: int = Field(..., description="Current page number (1-indexed)")
    per_page: int = Field(..., description="Items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


# =============================================================================
# STANDARD API RESPONSE
# =============================================================================

class APIResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper.

    All API endpoints should return this format for consistency.

    Attributes:
        success: Whether the request was successful
        data: The response data (type T)
        error: Error details if success is False
        meta: Response metadata (request_id, timestamp, etc.)
        pagination: Pagination info for list responses
    """
    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[T] = Field(None, description="Response data")
    error: Optional[ErrorDetail] = Field(None, description="Error details if success is False")
    errors: Optional[List[ErrorDetail]] = Field(None, description="Multiple errors (for validation)")
    meta: Optional[ResponseMeta] = Field(None, description="Response metadata")
    pagination: Optional[PaginationMeta] = Field(None, description="Pagination info for lists")

    class Config:
        json_schema_extra: ClassVar[Dict[str, Any]] = {
            "example": {
                "success": True,
                "data": {"id": "123", "name": "Example"},
                "meta": {
                    "request_id": "req-abc-123",
                    "timestamp": "2025-01-19T12:00:00Z",
                    "version": "v1"
                }
            }
        }


# =============================================================================
# SPECIFIC RESPONSE TYPES
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Overall health status")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Current environment")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    services: Optional[Dict[str, str]] = Field(None, description="Individual service status")


class TaskResponse(BaseModel):
    """Async task response"""
    task_id: str = Field(..., description="Celery task ID")
    status: str = Field(..., description="Task status (pending, started, success, failure)")
    message: str = Field(default="Task submitted successfully")
    result_url: Optional[str] = Field(None, description="URL to poll for results")


class BatchResponse(BaseModel, Generic[T]):
    """Batch operation response"""
    total: int = Field(..., description="Total items in batch")
    successful: int = Field(..., description="Successfully processed items")
    failed: int = Field(..., description="Failed items")
    results: List[T] = Field(default_factory=list, description="Individual results")
    errors: List[ErrorDetail] = Field(default_factory=list, description="Errors for failed items")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def success_response(
    data: Any = None,
    meta: Optional[ResponseMeta] = None,
    pagination: Optional[PaginationMeta] = None,
    request_id: Optional[str] = None
) -> APIResponse:
    """
    Create a successful API response.

    Args:
        data: Response data
        meta: Response metadata
        pagination: Pagination info
        request_id: Request ID (auto-generated if not provided)

    Returns:
        APIResponse with success=True
    """
    if meta is None and request_id:
        meta = ResponseMeta(request_id=request_id)
    elif meta is None:
        meta = ResponseMeta(request_id=str(uuid.uuid4())[:8])

    return APIResponse(
        success=True,
        data=data,
        meta=meta,
        pagination=pagination
    )


def error_response(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    field: Optional[str] = None,
    help_url: Optional[str] = None,
    request_id: Optional[str] = None,
    status_code: int = 400
) -> JSONResponse:
    """
    Create an error API response.

    Args:
        code: Error code
        message: Error message
        details: Additional details
        field: Field that caused the error
        help_url: Help documentation URL
        request_id: Request ID
        status_code: HTTP status code

    Returns:
        JSONResponse with error details
    """
    response = APIResponse(
        success=False,
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
            field=field,
            help_url=help_url
        ),
        meta=ResponseMeta(
            request_id=request_id or str(uuid.uuid4())[:8]
        )
    )

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(exclude_none=True)
    )


def validation_error_response(
    errors: List[ValidationError],
    request_id: Optional[str] = None
) -> JSONResponse:
    """
    Create a validation error response.

    Args:
        errors: List of validation errors
        request_id: Request ID

    Returns:
        JSONResponse with validation errors
    """
    error_details = [
        ErrorDetail(
            code="VALIDATION_ERROR",
            message=e.message,
            field=e.field,
            details={"value": e.value} if e.value is not None else None
        )
        for e in errors
    ]

    response = APIResponse(
        success=False,
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message="One or more validation errors occurred",
            details={"error_count": len(errors)}
        ),
        errors=error_details,
        meta=ResponseMeta(
            request_id=request_id or str(uuid.uuid4())[:8]
        )
    )

    return JSONResponse(
        status_code=422,
        content=response.model_dump(exclude_none=True)
    )


def paginated_response(
    data: List[Any],
    page: int,
    per_page: int,
    total_items: int,
    request_id: Optional[str] = None
) -> APIResponse:
    """
    Create a paginated response.

    Args:
        data: Page data
        page: Current page (1-indexed)
        per_page: Items per page
        total_items: Total items across all pages
        request_id: Request ID

    Returns:
        APIResponse with pagination metadata
    """
    import uuid
    import math

    total_pages = math.ceil(total_items / per_page) if per_page > 0 else 0

    return APIResponse(
        success=True,
        data=data,
        meta=ResponseMeta(
            request_id=request_id or str(uuid.uuid4())[:8]
        ),
        pagination=PaginationMeta(
            page=page,
            per_page=per_page,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
    )


def task_submitted_response(
    task_id: str,
    message: str = "Task submitted successfully",
    result_url: Optional[str] = None,
    request_id: Optional[str] = None
) -> APIResponse:
    """
    Create a task submission response.

    Args:
        task_id: Celery task ID
        message: Status message
        result_url: URL to poll for results
        request_id: Request ID

    Returns:
        APIResponse with task info
    """
    return APIResponse(
        success=True,
        data=TaskResponse(
            task_id=task_id,
            status="pending",
            message=message,
            result_url=result_url
        ),
        meta=ResponseMeta(
            request_id=request_id or str(uuid.uuid4())[:8]
        )
    )


# =============================================================================
# ERROR CODES
# =============================================================================

class ErrorCodes:
    """Standard error codes"""
    # Client errors (4xx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    BAD_REQUEST = "BAD_REQUEST"

    # Server errors (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"

    # Business logic errors
    DOCUMENT_PROCESSING_FAILED = "DOCUMENT_PROCESSING_FAILED"
    EMBEDDING_FAILED = "EMBEDDING_FAILED"
    QUERY_FAILED = "QUERY_FAILED"
    GRAPH_SYNC_FAILED = "GRAPH_SYNC_FAILED"
    LLM_ERROR = "LLM_ERROR"

    # Data persistence errors
    OPTIMISTIC_LOCK_FAILED = "OPTIMISTIC_LOCK_FAILED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    SAGA_COMPENSATION_FAILED = "SAGA_COMPENSATION_FAILED"
    WAL_REPLAY_FAILED = "WAL_REPLAY_FAILED"
