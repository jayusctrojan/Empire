"""
Empire v7.3 - Standardized Error Response Models
Task 135: Implement Standardized Error Response Model and Handling

Provides consistent error response structures across all agent services.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
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
        description="Machine-readable error code (e.g., VALIDATION_ERROR, AGENT_TIMEOUT)"
    )
    error_type: ErrorType = Field(
        ...,
        description="Whether the error is retriable or permanent"
    )
    agent_id: str = Field(
        ...,
        description="ID of the agent that generated the error (e.g., AGENT-003)"
    )
    message: str = Field(
        ...,
        description="Human-readable error message"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details or context"
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Unique identifier for request tracing"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the error occurred"
    )
    severity: ErrorSeverity = Field(
        default=ErrorSeverity.ERROR,
        description="Severity level of the error"
    )
    retry_after: Optional[int] = Field(
        default=None,
        description="Suggested retry delay in seconds (for retriable errors)"
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
                "retry_after": 30
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
        default_factory=list,
        description="List of individual validation errors"
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
                        "value": ""
                    }
                ],
                "request_id": "req-xyz123",
                "timestamp": "2025-01-13T10:30:00Z",
                "severity": "warning"
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
                "timestamp": "2025-01-13T10:59:00Z"
            }
        }


class ServiceUnavailableResponse(AgentErrorResponse):
    """
    Extended error response for service unavailable errors.
    """
    service_name: str = Field(..., description="Name of the unavailable service")
    dependencies_status: Optional[Dict[str, str]] = Field(
        default=None,
        description="Status of dependent services"
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
                    "redis": "healthy"
                },
                "retry_after": 30,
                "request_id": "req-xyz123",
                "timestamp": "2025-01-13T10:30:00Z"
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
    retry_after: Optional[int] = None
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
        retry_after=retry_after
    )


def create_validation_error(
    agent_id: str,
    message: str,
    validation_errors: List[Dict[str, Any]],
    request_id: Optional[str] = None
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
            value=e.get("input")
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
        severity=ErrorSeverity.WARNING
    )
