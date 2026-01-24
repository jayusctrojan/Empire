"""
Empire v7.3 - Standardized Error Response Models
Task 135: Implement Standardized Error Response Model and Handling
Task 175: Production Readiness Standardized Error Responses (US6)

Provides consistent error response structures across all API endpoints.

Production Error Format (FR-027, FR-028):
{
    "error": {
        "code": "VALIDATION_ERROR | AUTHENTICATION_ERROR | ...",
        "message": "Human-readable message",
        "details": {...},
        "request_id": "uuid",
        "timestamp": "ISO datetime"
    }
}
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ErrorType(str, Enum):
    """Classification of errors for client handling"""

    RETRIABLE = "retriable"  # Temporary errors that may succeed on retry
    PERMANENT = "permanent"  # Errors that will not succeed on retry


class ErrorSeverity(str, Enum):
    """Severity level of errors for logging and alerting"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AgentErrorResponse(BaseModel):
    """
    Standardized error response model for all agent services.

    This model provides a consistent structure for error responses,
    making it easier for clients to parse and handle errors uniformly.
    """

    error_code: str = Field(
        ...,
        description="Machine-readable error code (e.g., VALIDATION_ERROR, AGENT_TIMEOUT)",
    )
    error_type: ErrorType = Field(
        ..., description="Whether the error is retriable or permanent"
    )
    agent_id: str = Field(
        ..., description="ID of the agent that generated the error (e.g., AGENT-003)"
    )
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional error details or context"
    )
    request_id: Optional[str] = Field(
        default=None, description="Unique identifier for request tracing"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When the error occurred"
    )
    severity: ErrorSeverity = Field(
        default=ErrorSeverity.ERROR, description="Severity level of the error"
    )
    retry_after: Optional[int] = Field(
        default=None,
        description="Suggested retry delay in seconds (for retriable errors)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "error_code": "AGENT_PROCESSING_ERROR",
                "error_type": "retriable",
                "agent_id": "AGENT-016",
                "message": "Failed to process content set",
                "details": {"reason": "Invalid file format", "file": "document.xyz"},
                "request_id": "req-a1b2c3d4-e5f6-7890",
                "timestamp": "2025-01-13T10:30:00Z",
                "severity": "error",
                "retry_after": 30,
            }
        }


class ValidationErrorDetail(BaseModel):
    """Detail for a single validation error"""

    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    type: str = Field(..., description="Type of validation error")
    value: Optional[Any] = Field(default=None, description="The invalid value")


class ValidationErrorResponse(AgentErrorResponse):
    """
    Extended error response for validation errors with field-level details.
    """

    validation_errors: List[ValidationErrorDetail] = Field(
        default_factory=list, description="List of individual validation errors"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "error_code": "VALIDATION_ERROR",
                "error_type": "permanent",
                "agent_id": "AGENT-003",
                "message": "Request validation failed",
                "validation_errors": [
                    {
                        "field": "name",
                        "message": "String should have at least 1 character",
                        "type": "string_too_short",
                        "value": "",
                    }
                ],
                "request_id": "req-xyz123",
                "timestamp": "2025-01-13T10:30:00Z",
                "severity": "warning",
            }
        }


class RateLimitErrorResponse(AgentErrorResponse):
    """
    Extended error response for rate limit errors.
    """

    limit: int = Field(..., description="Rate limit threshold")
    remaining: int = Field(default=0, description="Remaining requests")
    reset_at: datetime = Field(..., description="When the rate limit resets")

    class Config:
        json_schema_extra = {
            "example": {
                "error_code": "RATE_LIMIT_EXCEEDED",
                "error_type": "retriable",
                "agent_id": "AGENT-003",
                "message": "Rate limit exceeded",
                "limit": 100,
                "remaining": 0,
                "reset_at": "2025-01-13T11:00:00Z",
                "retry_after": 60,
                "request_id": "req-xyz123",
                "timestamp": "2025-01-13T10:59:00Z",
            }
        }


class ServiceUnavailableResponse(AgentErrorResponse):
    """
    Extended error response for service unavailable errors.
    """

    service_name: str = Field(..., description="Name of the unavailable service")
    dependencies_status: Optional[Dict[str, str]] = Field(
        default=None, description="Status of dependent services"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "error_code": "SERVICE_UNAVAILABLE",
                "error_type": "retriable",
                "agent_id": "AGENT-012",
                "message": "External service temporarily unavailable",
                "service_name": "Neo4j",
                "dependencies_status": {
                    "neo4j": "unhealthy",
                    "supabase": "healthy",
                    "redis": "healthy",
                },
                "retry_after": 30,
                "request_id": "req-xyz123",
                "timestamp": "2025-01-13T10:30:00Z",
            }
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_agent_error(
    error_code: str,
    agent_id: str,
    message: str,
    error_type: ErrorType = ErrorType.PERMANENT,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    retry_after: Optional[int] = None,
) -> AgentErrorResponse:
    """
    Factory function to create an AgentErrorResponse.

    Args:
        error_code: Machine-readable error code
        agent_id: ID of the agent generating the error
        message: Human-readable error message
        error_type: Whether the error is retriable or permanent
        details: Additional error context
        request_id: Request tracing ID
        severity: Error severity level
        retry_after: Suggested retry delay for retriable errors

    Returns:
        AgentErrorResponse instance
    """
    return AgentErrorResponse(
        error_code=error_code,
        error_type=error_type,
        agent_id=agent_id,
        message=message,
        details=details,
        request_id=request_id,
        severity=severity,
        retry_after=retry_after,
    )


def create_validation_error(
    agent_id: str,
    message: str,
    validation_errors: List[Dict[str, Any]],
    request_id: Optional[str] = None,
) -> ValidationErrorResponse:
    """
    Factory function to create a ValidationErrorResponse.

    Args:
        agent_id: ID of the agent generating the error
        message: Human-readable error message
        validation_errors: List of validation error dictionaries
        request_id: Request tracing ID

    Returns:
        ValidationErrorResponse instance
    """
    errors = [
        ValidationErrorDetail(
            field=str(e.get("loc", ["unknown"])[-1]),
            message=e.get("msg", "Validation failed"),
            type=e.get("type", "unknown"),
            value=e.get("input"),
        )
        for e in validation_errors
    ]

    return ValidationErrorResponse(
        error_code="VALIDATION_ERROR",
        error_type=ErrorType.PERMANENT,
        agent_id=agent_id,
        message=message,
        validation_errors=errors,
        request_id=request_id,
        severity=ErrorSeverity.WARNING,
    )


# =============================================================================
# PRODUCTION READINESS STANDARDIZED ERROR MODELS (Task 175 - US6)
# =============================================================================


class ErrorCode(str, Enum):
    """
    Standard error codes for API responses (FR-028).

    These codes provide consistent error classification across all endpoints.
    """

    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class StandardError(BaseModel):
    """
    Standard error structure for API responses (FR-027).

    This model provides the consistent error format required for production:
    - code: Error code from ErrorCode enum
    - message: Human-readable error message
    - details: Optional additional error context
    - request_id: Unique identifier for request correlation
    - timestamp: When the error occurred (ISO 8601 format)
    """

    code: ErrorCode = Field(..., description="Error code identifying the type of error")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details (field-specific errors, etc.)",
    )
    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique request identifier for correlation",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the error occurred",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid input parameters",
                "details": {"field": "email", "reason": "Invalid email format"},
                "request_id": "123e4567-e89b-12d3-a456-426614174000",
                "timestamp": "2025-01-15T12:00:00Z",
            }
        }


class ErrorResponse(BaseModel):
    """
    API error response wrapper (FR-027).

    All API errors are returned in this format:
    {
        "error": {
            "code": "...",
            "message": "...",
            "details": {...},
            "request_id": "...",
            "timestamp": "..."
        }
    }
    """

    error: StandardError = Field(..., description="The error details")

    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input parameters",
                    "details": {"field": "email", "reason": "Invalid email format"},
                    "request_id": "123e4567-e89b-12d3-a456-426614174000",
                    "timestamp": "2025-01-15T12:00:00Z",
                }
            }
        }


# HTTP status code mapping for ErrorCode values
ERROR_CODE_STATUS_MAP: Dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.AUTHENTICATION_ERROR: 401,
    ErrorCode.AUTHORIZATION_ERROR: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.EXTERNAL_SERVICE_ERROR: 502,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    ErrorCode.INTERNAL_ERROR: 500,
}


def get_status_for_error_code(code: ErrorCode) -> int:
    """
    Get the HTTP status code for a given error code.

    Args:
        code: The ErrorCode enum value

    Returns:
        HTTP status code (e.g., 400, 401, 404, 500)
    """
    return ERROR_CODE_STATUS_MAP.get(code, 500)


# =============================================================================
# STANDARDIZED API EXCEPTIONS (Task 175 - US6)
# =============================================================================


class APIError(Exception):
    """
    Base exception class for API errors.

    Provides a standardized way to raise errors that will be converted
    to the ErrorResponse format by the error handler middleware.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
    ):
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code or get_status_for_error_code(code)
        super().__init__(self.message)

    def to_response(self, request_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert exception to ErrorResponse dictionary.

        Args:
            request_id: Optional request ID for correlation

        Returns:
            Dictionary in ErrorResponse format
        """
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
                "request_id": request_id or str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }


class ValidationAPIError(APIError):
    """Validation error (400 Bad Request)."""

    def __init__(
        self,
        message: str = "Invalid input parameters",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(ErrorCode.VALIDATION_ERROR, message, details)


class AuthenticationAPIError(APIError):
    """Authentication error (401 Unauthorized)."""

    def __init__(
        self,
        message: str = "Authentication required",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(ErrorCode.AUTHENTICATION_ERROR, message, details)


class AuthorizationAPIError(APIError):
    """Authorization error (403 Forbidden)."""

    def __init__(
        self,
        message: str = "Not authorized to perform this action",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(ErrorCode.AUTHORIZATION_ERROR, message, details)


class NotFoundAPIError(APIError):
    """Resource not found error (404 Not Found)."""

    def __init__(
        self,
        message: str = "Resource not found",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(ErrorCode.NOT_FOUND, message, details)


class RateLimitedAPIError(APIError):
    """Rate limit exceeded error (429 Too Many Requests)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please try again later.",
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
    ):
        if retry_after and details is None:
            details = {"retry_after": retry_after}
        elif retry_after and details:
            details["retry_after"] = retry_after
        super().__init__(ErrorCode.RATE_LIMITED, message, details)
        self.retry_after = retry_after


class ExternalServiceAPIError(APIError):
    """External service error (502 Bad Gateway)."""

    def __init__(
        self,
        message: str = "External service error",
        details: Optional[Dict[str, Any]] = None,
        service_name: Optional[str] = None,
    ):
        if service_name:
            message = f"{service_name} service error"
            if details is None:
                details = {"service": service_name}
            else:
                details["service"] = service_name
        super().__init__(ErrorCode.EXTERNAL_SERVICE_ERROR, message, details)


class ServiceUnavailableAPIError(APIError):
    """Service unavailable error (503 Service Unavailable)."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(ErrorCode.SERVICE_UNAVAILABLE, message, details)


class InternalAPIError(APIError):
    """Internal server error (500 Internal Server Error)."""

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(ErrorCode.INTERNAL_ERROR, message, details)


# =============================================================================
# STANDARDIZED ERROR RESPONSE HELPERS
# =============================================================================


def create_error_response(
    code: ErrorCode,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a standardized error response dictionary.

    Args:
        code: Error code from ErrorCode enum
        message: Human-readable error message
        details: Optional additional error context
        request_id: Optional request ID for correlation

    Returns:
        Dictionary in ErrorResponse format

    Example:
        >>> response = create_error_response(
        ...     ErrorCode.VALIDATION_ERROR,
        ...     "Invalid email format",
        ...     details={"field": "email"}
        ... )
    """
    return {
        "error": {
            "code": code.value,
            "message": message,
            "details": details,
            "request_id": request_id or str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }


def create_validation_error_response(
    message: str,
    field_errors: Optional[Dict[str, str]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a validation error response with field-level details.

    Args:
        message: Human-readable error message
        field_errors: Dictionary mapping field names to error messages
        request_id: Optional request ID for correlation

    Returns:
        Dictionary in ErrorResponse format with validation details
    """
    details = {"fields": field_errors} if field_errors else None
    return create_error_response(
        ErrorCode.VALIDATION_ERROR,
        message,
        details=details,
        request_id=request_id,
    )


def create_external_service_error_response(
    service_name: str,
    reason: str = "timeout",
    timeout_seconds: Optional[float] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create an external service error response.

    Args:
        service_name: Name of the service that failed
        reason: Reason for failure (timeout, connection_failed, etc.)
        timeout_seconds: Configured timeout value (for timeout errors)
        request_id: Optional request ID for correlation

    Returns:
        Dictionary in ErrorResponse format with service details
    """
    details: Dict[str, Any] = {
        "service": service_name,
        "reason": reason,
    }
    if timeout_seconds is not None:
        details["timeout_seconds"] = timeout_seconds

    return create_error_response(
        ErrorCode.EXTERNAL_SERVICE_ERROR,
        f"{service_name} service {reason}",
        details=details,
        request_id=request_id,
    )
