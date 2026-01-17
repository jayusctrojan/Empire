"""
Empire v7.3 - Error Handler Middleware
Task 135: Implement Standardized Error Response Model and Handling
Task 154: Standardized Exception Handling Framework
Task 175: Production Readiness Standardized Error Responses (US6)
Task 176: Enhanced Exception Logging

Centralized error handling middleware that provides consistent error responses
across all agent services with comprehensive logging.
"""

import uuid
import traceback
import sys
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timezone

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
    # Task 175: Production Readiness standardized errors
    APIError,
    ErrorCode,
    get_status_for_error_code,
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
# Task 154: Import the new exception hierarchy
from app.exceptions.base import BaseAppException

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

        except APIError as e:
            # Task 175: Handle standardized API errors
            return self._create_standardized_error_response(
                error=e,
                request_id=request_id,
            )

        except BaseAppException as e:
            # Task 154: Handle the new exception hierarchy
            agent_id = e.details.get("agent_id", self._extract_agent_id(request.url.path))
            error_type = ErrorType.RETRIABLE if e.retriable else ErrorType.PERMANENT

            return self._create_error_response(
                error_code=e.error_code,
                message=e.message,
                agent_id=agent_id,
                error_type=error_type,
                details=e.details,
                request_id=request_id,
                severity=ErrorSeverity(e.severity) if e.severity in [s.value for s in ErrorSeverity] else ErrorSeverity.ERROR,
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
            # Handle unexpected exceptions with enhanced logging (Task 176)
            agent_id = self._extract_agent_id(request.url.path)

            # Build comprehensive error context
            context = self._build_error_context(
                request=request,
                exc=e,
                request_id=request_id,
                agent_id=agent_id,
                include_stack_trace=True
            )

            # Log with full exception traceback
            self._log_error(
                message="Unhandled exception in request",
                context=context,
                level="error",
                include_exception=True
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

    def _build_error_context(
        self,
        request: Request,
        exc: Exception,
        request_id: str,
        agent_id: str = "unknown",
        include_stack_trace: bool = False
    ) -> Dict[str, Any]:
        """
        Build comprehensive error context for logging (Task 176).

        This method collects all relevant context information for debugging
        and correlation purposes.

        Args:
            request: The incoming request
            exc: The exception that occurred
            request_id: The request ID for correlation
            agent_id: The agent ID if applicable
            include_stack_trace: Whether to include stack trace

        Returns:
            Dictionary containing error context
        """
        # Get client IP from request state or headers
        client_ip = getattr(request.state, "client_ip", None)
        if not client_ip:
            # Check X-Forwarded-For for proxy scenarios
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()
            elif request.client:
                client_ip = request.client.host
            else:
                client_ip = "unknown"

        # Get user ID if available in request state
        user_id = None
        if hasattr(request.state, "user_id"):
            user_id = request.state.user_id
        elif hasattr(request.state, "user"):
            user = request.state.user
            user_id = getattr(user, "id", None) or getattr(user, "user_id", None)

        # Build base context
        context: Dict[str, Any] = {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "endpoint": request.url.path,
            "method": request.method,
            "request_id": request_id,
            "agent_id": agent_id,
            "client_ip": client_ip,
            "user_agent": request.headers.get("User-Agent", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Add user ID if available
        if user_id:
            context["user_id"] = user_id

        # Add query parameters if present (sanitized)
        if request.query_params:
            # Don't log sensitive params
            sensitive_params = {"token", "key", "secret", "password", "auth"}
            sanitized_params = {
                k: "***" if k.lower() in sensitive_params else v
                for k, v in request.query_params.items()
            }
            context["query_params"] = sanitized_params

        # Add stack trace for unexpected errors
        if include_stack_trace:
            context["stack_trace"] = traceback.format_exc()
            # Include exception chain info
            if exc.__cause__:
                context["caused_by"] = {
                    "type": type(exc.__cause__).__name__,
                    "message": str(exc.__cause__)
                }

        return context

    def _log_error(
        self,
        message: str,
        context: Dict[str, Any],
        level: str = "error",
        include_exception: bool = False
    ) -> None:
        """
        Log an error with the given context (Task 176).

        Args:
            message: The log message
            context: Error context dictionary
            level: Log level (error, warning, info)
            include_exception: Whether to use logger.exception()
        """
        log_method = getattr(logger, level, logger.error)

        if include_exception:
            # Use logger.exception to include traceback
            logger.exception(message, **context)
        else:
            log_method(message, **context)

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

    def _create_standardized_error_response(
        self,
        error: APIError,
        request_id: Optional[str] = None
    ) -> JSONResponse:
        """
        Create a standardized error response (Task 175 - FR-027).

        This produces the production-standard error format:
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
        response_content = error.to_response(request_id)

        headers = {"X-Request-ID": request_id} if request_id else {}

        # Add Retry-After header for rate limit errors
        if hasattr(error, "retry_after") and error.retry_after:
            headers["Retry-After"] = str(error.retry_after)

        # Log the error with appropriate level
        log_level = "warning" if error.status_code < 500 else "error"
        log_method = getattr(logger, log_level, logger.error)
        log_method(
            "Standardized API error",
            error_code=error.code.value,
            message=error.message,
            status_code=error.status_code,
            request_id=request_id,
        )

        return JSONResponse(
            status_code=error.status_code,
            content=response_content,
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
# EXCEPTION HANDLER FOR NEW HIERARCHY
# =============================================================================

async def base_app_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
    """
    Handle BaseAppException from the new exception hierarchy (Task 154).
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    # Determine agent_id from exception details or URL path
    middleware = ErrorHandlerMiddleware(app=None)
    agent_id = exc.details.get("agent_id", middleware._extract_agent_id(request.url.path))

    # Map retriable to error type
    error_type = ErrorType.RETRIABLE if exc.retriable else ErrorType.PERMANENT

    # Map severity string to ErrorSeverity enum
    severity_map = {s.value: s for s in ErrorSeverity}
    severity = severity_map.get(exc.severity, ErrorSeverity.ERROR)

    error_response = AgentErrorResponse(
        error_code=exc.error_code,
        error_type=error_type,
        agent_id=agent_id,
        message=exc.message,
        details=exc.details,
        request_id=request_id,
        timestamp=exc.timestamp,
        severity=severity,
        retry_after=exc.retry_after
    )

    headers = {"X-Request-ID": request_id}
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(mode="json"),
        headers=headers
    )


# =============================================================================
# EXCEPTION HANDLER FOR STANDARDIZED API ERRORS (Task 175)
# =============================================================================

async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """
    Handle APIError exceptions and return standardized error responses.

    This handler produces the production-standard error format (FR-027):
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
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    response_content = exc.to_response(request_id)

    headers = {"X-Request-ID": request_id}

    # Add Retry-After header for rate limit errors
    if hasattr(exc, "retry_after") and exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)

    # Log the error
    if exc.status_code >= 500:
        logger.error(
            "API error",
            error_code=exc.code.value,
            message=exc.message,
            status_code=exc.status_code,
            request_id=request_id,
            path=request.url.path,
        )
    else:
        logger.warning(
            "API error",
            error_code=exc.code.value,
            message=exc.message,
            status_code=exc.status_code,
            request_id=request_id,
            path=request.url.path,
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=response_content,
        headers=headers
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
    app.add_exception_handler(APIError, api_error_handler)  # Task 175: Standardized errors
    app.add_exception_handler(BaseAppException, base_app_exception_handler)  # Task 154
    app.add_exception_handler(RequestValidationError, validation_error_handler)
