"""
Empire v7.3 - Error Handler Middleware
Task 135: Implement Standardized Error Response Model and Handling

Centralized error handling middleware that provides consistent error responses
across all agent services.
"""

import uuid
import traceback
from typing import Optional, Callable
from datetime import datetime

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import ValidationError
import structlog

from app.models.errors import (
    AgentErrorResponse,
    ValidationErrorResponse,
    ValidationErrorDetail,
    ErrorType,
    ErrorSeverity,
    create_validation_error,
)
from app.constants.error_codes import (
    INTERNAL_SERVER_ERROR,
    VALIDATION_ERROR,
    AGENT_PROCESSING_ERROR,
    AGENT_TIMEOUT,
    LLM_ERROR,
    SERVICE_UNAVAILABLE,
    RATE_LIMIT_EXCEEDED,
    get_http_status,
    is_retriable,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class AgentError(Exception):
    """Base exception for agent-related errors"""

    def __init__(
        self,
        error_code: str,
        message: str,
        agent_id: str = "unknown",
        details: Optional[dict] = None,
        error_type: ErrorType = ErrorType.PERMANENT,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        retry_after: Optional[int] = None
    ):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.agent_id = agent_id
        self.details = details
        self.error_type = error_type
        self.severity = severity
        self.retry_after = retry_after


class AgentProcessingError(AgentError):
    """Error during agent processing"""

    def __init__(
        self,
        message: str,
        agent_id: str = "unknown",
        details: Optional[dict] = None
    ):
        super().__init__(
            error_code=AGENT_PROCESSING_ERROR,
            message=message,
            agent_id=agent_id,
            details=details,
            error_type=ErrorType.RETRIABLE
        )


class AgentTimeoutError(AgentError):
    """Agent operation timed out"""

    def __init__(
        self,
        message: str,
        agent_id: str = "unknown",
        details: Optional[dict] = None,
        retry_after: int = 30
    ):
        super().__init__(
            error_code=AGENT_TIMEOUT,
            message=message,
            agent_id=agent_id,
            details=details,
            error_type=ErrorType.RETRIABLE,
            retry_after=retry_after
        )


class LLMError(AgentError):
    """Error from LLM service"""

    def __init__(
        self,
        message: str,
        agent_id: str = "unknown",
        details: Optional[dict] = None,
        error_type: ErrorType = ErrorType.RETRIABLE
    ):
        super().__init__(
            error_code=LLM_ERROR,
            message=message,
            agent_id=agent_id,
            details=details,
            error_type=error_type
        )


class ServiceUnavailableError(AgentError):
    """External service unavailable"""

    def __init__(
        self,
        message: str,
        service_name: str,
        agent_id: str = "unknown",
        retry_after: int = 60
    ):
        super().__init__(
            error_code=SERVICE_UNAVAILABLE,
            message=message,
            agent_id=agent_id,
            details={"service_name": service_name},
            error_type=ErrorType.RETRIABLE,
            retry_after=retry_after
        )


class ResourceNotFoundError(AgentError):
    """Requested resource not found"""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        agent_id: str = "unknown"
    ):
        super().__init__(
            error_code=f"{resource_type.upper()}_NOT_FOUND",
            message=f"{resource_type} not found: {resource_id}",
            agent_id=agent_id,
            details={"resource_type": resource_type, "resource_id": resource_id},
            error_type=ErrorType.PERMANENT,
            severity=ErrorSeverity.WARNING
        )


class RateLimitError(AgentError):
    """Rate limit exceeded"""

    def __init__(
        self,
        message: str,
        agent_id: str = "unknown",
        retry_after: int = 60,
        limit: int = 100,
        remaining: int = 0
    ):
        super().__init__(
            error_code=RATE_LIMIT_EXCEEDED,
            message=message,
            agent_id=agent_id,
            details={"limit": limit, "remaining": remaining},
            error_type=ErrorType.RETRIABLE,
            retry_after=retry_after
        )


# =============================================================================
# ERROR HANDLER MIDDLEWARE
# =============================================================================

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware that catches all exceptions and returns standardized error responses.

    This middleware:
    - Catches unhandled exceptions
    - Extracts agent_id from URL path when possible
    - Generates request IDs for tracing
    - Logs errors with context
    - Returns consistent JSON error responses
    """

    # Mapping of URL path prefixes to agent IDs
    AGENT_PATH_MAPPING = {
        "/api/summarizer": "AGENT-002",
        "/api/assets/skill": "AGENT-003",
        "/api/assets/command": "AGENT-004",
        "/api/assets/agent": "AGENT-005",
        "/api/assets/prompt": "AGENT-006",
        "/api/assets/workflow": "AGENT-007",
        "/api/assets": "AGENT-003",  # Default for asset generators
        "/api/classifier": "AGENT-008",
        "/api/document-analysis/research": "AGENT-009",
        "/api/document-analysis/strategy": "AGENT-010",
        "/api/document-analysis/fact-check": "AGENT-011",
        "/api/document-analysis": "AGENT-009",  # Default for analysis
        "/api/orchestration/research": "AGENT-012",
        "/api/orchestration/analyze": "AGENT-013",
        "/api/orchestration/write": "AGENT-014",
        "/api/orchestration/review": "AGENT-015",
        "/api/orchestration": "AGENT-012",  # Default for orchestration
        "/api/content-prep": "AGENT-016",
    }

    async def dispatch(self, request: Request, call_next: Callable):
        """Process the request and handle any exceptions"""
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Add request_id to request state for use by handlers
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response

        except AgentError as e:
            # Handle our custom agent errors
            return self._create_error_response(
                error_code=e.error_code,
                message=e.message,
                agent_id=e.agent_id,
                error_type=e.error_type,
                details=e.details,
                request_id=request_id,
                severity=e.severity,
                retry_after=e.retry_after
            )

        except RequestValidationError as e:
            # Handle FastAPI validation errors
            agent_id = self._extract_agent_id(request.url.path)
            return self._create_validation_error_response(
                errors=e.errors(),
                agent_id=agent_id,
                request_id=request_id
            )

        except ValidationError as e:
            # Handle Pydantic validation errors
            agent_id = self._extract_agent_id(request.url.path)
            return self._create_validation_error_response(
                errors=e.errors(),
                agent_id=agent_id,
                request_id=request_id
            )

        except Exception as e:
            # Handle unexpected exceptions
            agent_id = self._extract_agent_id(request.url.path)

            # Log the full exception
            logger.exception(
                "Unhandled exception in request",
                request_id=request_id,
                agent_id=agent_id,
                path=request.url.path,
                method=request.method,
                error=str(e)
            )

            return self._create_error_response(
                error_code=INTERNAL_SERVER_ERROR,
                message="An unexpected error occurred",
                agent_id=agent_id,
                error_type=ErrorType.RETRIABLE,
                details={"exception_type": type(e).__name__},
                request_id=request_id,
                severity=ErrorSeverity.ERROR
            )

    def _extract_agent_id(self, path: str) -> str:
        """Extract agent ID from URL path"""
        # Check path prefixes in order of specificity (longer paths first)
        sorted_paths = sorted(
            self.AGENT_PATH_MAPPING.keys(),
            key=len,
            reverse=True
        )

        for prefix in sorted_paths:
            if path.startswith(prefix):
                return self.AGENT_PATH_MAPPING[prefix]

        return "unknown"

    def _create_error_response(
        self,
        error_code: str,
        message: str,
        agent_id: str,
        error_type: ErrorType,
        details: Optional[dict] = None,
        request_id: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        retry_after: Optional[int] = None
    ) -> JSONResponse:
        """Create a standardized JSON error response"""
        # Determine if retriable from error code if not explicitly set
        if error_type == ErrorType.PERMANENT and is_retriable(error_code):
            error_type = ErrorType.RETRIABLE

        error_response = AgentErrorResponse(
            error_code=error_code,
            error_type=error_type,
            agent_id=agent_id,
            message=message,
            details=details,
            request_id=request_id,
            timestamp=datetime.utcnow(),
            severity=severity,
            retry_after=retry_after
        )

        http_status = get_http_status(error_code)

        # Build response headers
        headers = {"X-Request-ID": request_id} if request_id else {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)

        # Log the error
        log_method = getattr(logger, severity.value, logger.error)
        log_method(
            "Error response",
            error_code=error_code,
            agent_id=agent_id,
            message=message,
            request_id=request_id,
            http_status=http_status
        )

        return JSONResponse(
            status_code=http_status,
            content=error_response.model_dump(mode="json"),
            headers=headers
        )

    def _create_validation_error_response(
        self,
        errors: list,
        agent_id: str,
        request_id: Optional[str] = None
    ) -> JSONResponse:
        """Create a validation error response"""
        validation_errors = [
            ValidationErrorDetail(
                field=str(e.get("loc", ["unknown"])[-1]),
                message=e.get("msg", "Validation failed"),
                type=e.get("type", "unknown"),
                value=e.get("input")
            )
            for e in errors
        ]

        error_response = ValidationErrorResponse(
            error_code=VALIDATION_ERROR,
            error_type=ErrorType.PERMANENT,
            agent_id=agent_id,
            message=f"Validation failed with {len(errors)} error(s)",
            validation_errors=validation_errors,
            request_id=request_id,
            timestamp=datetime.utcnow(),
            severity=ErrorSeverity.WARNING
        )

        headers = {"X-Request-ID": request_id} if request_id else {}

        logger.warning(
            "Validation error",
            agent_id=agent_id,
            error_count=len(errors),
            request_id=request_id
        )

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response.model_dump(mode="json"),
            headers=headers
        )


# =============================================================================
# EXCEPTION HANDLERS FOR FASTAPI
# =============================================================================

async def agent_error_handler(request: Request, exc: AgentError) -> JSONResponse:
    """Handle AgentError exceptions"""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    error_response = AgentErrorResponse(
        error_code=exc.error_code,
        error_type=exc.error_type,
        agent_id=exc.agent_id,
        message=exc.message,
        details=exc.details,
        request_id=request_id,
        timestamp=datetime.utcnow(),
        severity=exc.severity,
        retry_after=exc.retry_after
    )

    http_status = get_http_status(exc.error_code)
    headers = {"X-Request-ID": request_id}
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)

    return JSONResponse(
        status_code=http_status,
        content=error_response.model_dump(mode="json"),
        headers=headers
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """Handle FastAPI validation errors"""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    # Determine agent ID from path
    middleware = ErrorHandlerMiddleware(app=None)
    agent_id = middleware._extract_agent_id(request.url.path)

    validation_errors = [
        ValidationErrorDetail(
            field=str(e.get("loc", ["unknown"])[-1]),
            message=e.get("msg", "Validation failed"),
            type=e.get("type", "unknown"),
            value=e.get("input")
        )
        for e in exc.errors()
    ]

    error_response = ValidationErrorResponse(
        error_code=VALIDATION_ERROR,
        error_type=ErrorType.PERMANENT,
        agent_id=agent_id,
        message=f"Validation failed with {len(exc.errors())} error(s)",
        validation_errors=validation_errors,
        request_id=request_id,
        timestamp=datetime.utcnow(),
        severity=ErrorSeverity.WARNING
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response.model_dump(mode="json"),
        headers={"X-Request-ID": request_id}
    )


# =============================================================================
# SETUP FUNCTION
# =============================================================================

def setup_error_handling(app):
    """
    Set up error handling for the FastAPI application.

    Usage:
        from app.middleware.error_handler import setup_error_handling
        app = FastAPI()
        setup_error_handling(app)

    Args:
        app: FastAPI application instance
    """
    from fastapi.exceptions import RequestValidationError

    # Add the error handler middleware
    app.add_middleware(ErrorHandlerMiddleware)

    # Add exception handlers
    app.add_exception_handler(AgentError, agent_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
