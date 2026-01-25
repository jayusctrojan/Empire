"""
Empire v7.3 - Request Tracing Middleware
Task 136: X-Request-ID Tracing Across Agent Chains

Provides end-to-end request tracing through:
- X-Request-ID header generation and propagation
- Context variable storage for request IDs
- Logging integration with request IDs
- Metrics correlation support

This enables tracing requests through multi-agent workflows,
making debugging and monitoring significantly easier.
"""

import uuid
import time
from contextvars import ContextVar
from typing import Optional, Dict, Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import structlog

logger = structlog.get_logger(__name__)


# ============================================================================
# Context Variables for Request Tracing
# ============================================================================


# Request ID context - thread-safe storage for async contexts
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

# Request context - additional metadata for the current request
request_context_var: ContextVar[Dict[str, Any]] = ContextVar(
    "request_context", default={}
)


# ============================================================================
# Request Tracing Middleware
# ============================================================================


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for X-Request-ID generation and propagation.

    Features:
    - Generates UUID if X-Request-ID not provided
    - Preserves incoming X-Request-ID for distributed tracing
    - Stores request ID in context variable for logging/metrics
    - Adds X-Request-ID to all response headers
    - Tracks request timing for performance monitoring

    Usage:
        app.add_middleware(RequestTracingMiddleware)

    Access request ID anywhere:
        from app.middleware.request_tracing import get_request_id
        current_id = get_request_id()
    """

    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-Request-ID",
        log_requests: bool = True,
        include_path: bool = True,
        include_timing: bool = True,
    ):
        """
        Initialize request tracing middleware.

        Args:
            app: FastAPI/Starlette application
            header_name: Header name to use for request ID (default: X-Request-ID)
            log_requests: Whether to log incoming/outgoing requests
            include_path: Include request path in logs
            include_timing: Include request duration in response headers
        """
        super().__init__(app)
        self.header_name = header_name
        self.log_requests = log_requests
        self.include_path = include_path
        self.include_timing = include_timing

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Process request with tracing context.

        1. Extract or generate request ID
        2. Set context variables
        3. Process request
        4. Add response headers
        5. Log if enabled
        """
        start_time = time.perf_counter()

        # Extract existing request ID or generate new one
        request_id = request.headers.get(self.header_name)
        is_generated = False

        if not request_id:
            request_id = str(uuid.uuid4())
            is_generated = True

        # Validate UUID format (accept any string but log warning if invalid)
        try:
            uuid.UUID(request_id)
        except ValueError:
            # Accept non-UUID values but log warning
            logger.warning(
                "Received non-UUID request ID",
                request_id=request_id,
                path=request.url.path
            )

        # Set context variables for this request
        request_id_token = request_id_var.set(request_id)
        context_token = request_context_var.set({
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_host": request.client.host if request.client else None,
            "start_time": start_time,
            "is_generated": is_generated,
        })

        # Log incoming request
        if self.log_requests:
            logger.info(
                "Request started",
                request_id=request_id,
                method=request.method,
                path=request.url.path if self.include_path else "[redacted]",
                generated_id=is_generated
            )

        try:
            # Process the request
            response = await call_next(request)

            # Calculate processing time
            process_time = time.perf_counter() - start_time

            # Add response headers
            response.headers[self.header_name] = request_id

            if self.include_timing:
                response.headers["X-Process-Time"] = f"{process_time:.4f}"

            # Log completed request
            if self.log_requests:
                logger.info(
                    "Request completed",
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path if self.include_path else "[redacted]",
                    status_code=response.status_code,
                    duration_ms=round(process_time * 1000, 2)
                )

            return response

        except Exception as e:
            # Calculate time even on error
            process_time = time.perf_counter() - start_time

            # Log error with request context
            logger.error(
                "Request failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path if self.include_path else "[redacted]",
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(process_time * 1000, 2)
            )
            raise

        finally:
            # Always reset context variables
            request_id_var.reset(request_id_token)
            request_context_var.reset(context_token)


# ============================================================================
# Context Access Functions
# ============================================================================


def get_request_id() -> Optional[str]:
    """
    Get the current request ID from context.

    Returns:
        The request ID for the current request, or None if not in request context.

    Example:
        from app.middleware.request_tracing import get_request_id

        request_id = get_request_id()
        logger.info("Processing", request_id=request_id)
    """
    return request_id_var.get()


def get_request_context() -> Dict[str, Any]:
    """
    Get the full request context.

    Returns:
        Dictionary containing request metadata:
        - request_id: The request ID
        - method: HTTP method
        - path: Request path
        - client_host: Client IP address
        - start_time: Request start timestamp
        - is_generated: Whether ID was generated (vs provided)

    Example:
        ctx = get_request_context()
        print(f"Request {ctx['method']} {ctx['path']}")
    """
    return request_context_var.get().copy()


def set_request_id(request_id: str) -> None:
    """
    Manually set the request ID (for background tasks, etc.).

    Use this when starting a background task that should be
    associated with a particular request.

    Args:
        request_id: The request ID to set

    Example:
        # In a Celery task
        set_request_id(task_request_id)
        logger.info("Background task started")  # Will include request_id
    """
    request_id_var.set(request_id)

    # Update context as well
    current_context = request_context_var.get()
    updated_context = {**current_context, "request_id": request_id}
    request_context_var.set(updated_context)


def generate_request_id() -> str:
    """
    Generate a new request ID (UUID4).

    Useful for starting new trace chains in background tasks
    or async workflows.

    Returns:
        A new UUID4 string

    Example:
        new_id = generate_request_id()
        set_request_id(new_id)
    """
    return str(uuid.uuid4())


# ============================================================================
# Structlog Processor for Request ID
# ============================================================================


def add_request_id_processor(
    logger: Any,
    method_name: str,
    event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Structlog processor that adds request_id to all log entries.

    Add this to your structlog configuration to automatically
    include request_id in all logs.

    Example structlog configuration:
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                add_request_id_processor,  # Add this
                structlog.processors.JSONRenderer(),
            ]
        )
    """
    request_id = get_request_id()
    if request_id and "request_id" not in event_dict:
        event_dict["request_id"] = request_id
    return event_dict


# ============================================================================
# Request ID Logging Filter (for stdlib logging)
# ============================================================================


class RequestIdFilter:
    """
    Standard library logging filter that adds request_id and trace context to log records.

    Use with Python's standard logging to include request_id, trace_id, and span_id:

    Example:
        import logging

        handler = logging.StreamHandler()
        handler.addFilter(RequestIdFilter())

        formatter = logging.Formatter(
            '%(asctime)s [%(request_id)s] trace=%(trace_id)s %(levelname)s: %(message)s'
        )
        handler.setFormatter(formatter)
    """

    def filter(self, record):
        """Add request_id and trace context to log record."""
        record.request_id = get_request_id() or "no-request-id"

        # Task 189: Add OpenTelemetry trace context
        try:
            from app.core.tracing import get_current_trace_id, get_current_span_id
            record.trace_id = get_current_trace_id() or "no-trace"
            record.span_id = get_current_span_id() or "no-span"
        except ImportError:
            # Tracing module not available
            record.trace_id = "no-trace"
            record.span_id = "no-span"

        return True


# ============================================================================
# Configuration Helper
# ============================================================================


def configure_request_tracing(
    app,
    header_name: str = "X-Request-ID",
    log_requests: bool = True,
    include_path: bool = True,
    include_timing: bool = True,
) -> None:
    """
    Configure request tracing for a FastAPI application.

    This is a convenience function that adds the middleware
    with the specified settings.

    Args:
        app: FastAPI application
        header_name: Header name for request ID
        log_requests: Whether to log requests
        include_path: Whether to include paths in logs
        include_timing: Whether to add timing headers

    Example:
        from app.middleware.request_tracing import configure_request_tracing

        app = FastAPI()
        configure_request_tracing(app)
    """
    app.add_middleware(
        RequestTracingMiddleware,
        header_name=header_name,
        log_requests=log_requests,
        include_path=include_path,
        include_timing=include_timing,
    )

    logger.info(
        "Request tracing configured",
        header_name=header_name,
        log_requests=log_requests,
        include_timing=include_timing
    )
