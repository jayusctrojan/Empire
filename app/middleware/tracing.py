"""
Empire v7.3 - OpenTelemetry Tracing Middleware
Task 189: Distributed tracing middleware for FastAPI

Provides:
- Automatic span creation for HTTP requests
- Trace ID injection into response headers
- Integration with existing X-Request-ID middleware
- Automatic instrumentation of FastAPI routes
"""

import time
from typing import Optional, Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import FastAPI

import structlog

from opentelemetry import trace
from opentelemetry.trace import StatusCode, Status

from app.core.tracing import (
    get_tracer,
    extract_trace_context,
    get_current_trace_id,
    get_current_span_id,
    setup_tracing,
    TRACING_ENABLED,
)

logger = structlog.get_logger(__name__)


class OpenTelemetryMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for OpenTelemetry distributed tracing.

    Creates spans for all HTTP requests with:
    - Request method, path, and query parameters
    - Response status code and timing
    - User ID and session ID (if available)
    - Error details on failure

    Also adds trace context headers to responses:
    - X-Trace-ID: Current trace ID
    - X-Span-ID: Current span ID
    - traceparent: W3C TraceContext header (if requested)
    """

    def __init__(
        self,
        app,
        exclude_paths: Optional[list] = None,
        include_headers: bool = True,
        propagate_traceparent: bool = True
    ):
        """
        Initialize the OpenTelemetry middleware.

        Args:
            app: FastAPI application
            exclude_paths: Paths to exclude from tracing (e.g., /health, /metrics)
            include_headers: Add trace headers to responses
            propagate_traceparent: Include W3C traceparent in response headers
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/health",
            "/health/live",
            "/health/ready",
            "/monitoring/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]
        self.include_headers = include_headers
        self.propagate_traceparent = propagate_traceparent
        self.tracer = get_tracer()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request with OpenTelemetry tracing."""

        # Skip tracing for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Skip if tracing is disabled
        if not TRACING_ENABLED:
            return await call_next(request)

        # Extract trace context from incoming headers
        headers = dict(request.headers)
        parent_context = extract_trace_context(headers)

        # Create span for this request
        span_name = f"{request.method} {request.url.path}"

        with self.tracer.start_as_current_span(
            span_name,
            context=parent_context,
            kind=trace.SpanKind.SERVER,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.scheme": request.url.scheme,
                "http.host": request.url.hostname or "",
                "http.target": request.url.path,
                "http.user_agent": request.headers.get("user-agent", ""),
                "net.host.port": request.url.port or (443 if request.url.scheme == "https" else 80),
            }
        ) as span:
            # Add query parameters as attribute
            if request.url.query:
                span.set_attribute("http.query", request.url.query[:500])

            # Add user context if available
            user_id = request.headers.get("x-user-id")
            if user_id:
                span.set_attribute("user.id", user_id)

            session_id = request.headers.get("x-session-id")
            if session_id:
                span.set_attribute("session.id", session_id)

            # Add request ID correlation
            request_id = request.headers.get("x-request-id")
            if request_id:
                span.set_attribute("request.id", request_id)

            start_time = time.perf_counter()

            try:
                # Process the request
                response = await call_next(request)

                # Record response attributes
                duration_ms = (time.perf_counter() - start_time) * 1000
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.response_time_ms", round(duration_ms, 2))

                # Set span status based on response code
                if response.status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                elif response.status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                else:
                    span.set_status(Status(StatusCode.OK))

                # Add trace headers to response
                if self.include_headers:
                    trace_id = get_current_trace_id()
                    span_id = get_current_span_id()

                    if trace_id:
                        response.headers["X-Trace-ID"] = trace_id
                    if span_id:
                        response.headers["X-Span-ID"] = span_id

                    # Add traceparent for downstream correlation
                    if self.propagate_traceparent and trace_id and span_id:
                        ctx = span.get_span_context()
                        flags = format(ctx.trace_flags, "02x")
                        response.headers["traceparent"] = f"00-{trace_id}-{span_id}-{flags}"

                return response

            except Exception as e:
                # Record exception in span
                duration_ms = (time.perf_counter() - start_time) * 1000
                span.set_attribute("http.response_time_ms", round(duration_ms, 2))
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise


def configure_tracing(
    app: FastAPI,
    exclude_paths: Optional[list] = None,
    auto_instrument: bool = True
) -> None:
    """
    Configure OpenTelemetry tracing for a FastAPI application.

    Args:
        app: FastAPI application instance
        exclude_paths: Additional paths to exclude from tracing
        auto_instrument: Use OpenTelemetry auto-instrumentation (recommended)

    Example:
        from fastapi import FastAPI
        from app.middleware.tracing import configure_tracing

        app = FastAPI()
        configure_tracing(app)
    """
    # Initialize tracing
    setup_tracing()

    # Add custom middleware
    default_exclude = [
        "/health",
        "/health/live",
        "/health/ready",
        "/monitoring/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]

    if exclude_paths:
        default_exclude.extend(exclude_paths)

    app.add_middleware(
        OpenTelemetryMiddleware,
        exclude_paths=default_exclude,
        include_headers=True,
        propagate_traceparent=True
    )

    # Auto-instrument FastAPI if requested
    if auto_instrument:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app)
            logger.info("OpenTelemetry FastAPI auto-instrumentation enabled")
        except ImportError:
            logger.warning(
                "opentelemetry-instrumentation-fastapi not installed, "
                "using manual middleware only"
            )
        except Exception as e:
            logger.warning(f"Failed to enable FastAPI auto-instrumentation: {e}")

    logger.info(
        "OpenTelemetry tracing middleware configured",
        exclude_paths=default_exclude,
        auto_instrument=auto_instrument
    )


def instrument_httpx():
    """
    Instrument httpx for outbound HTTP tracing.

    Call this at application startup to automatically trace
    all outbound HTTP requests made with httpx.
    """
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
        logger.info("OpenTelemetry httpx instrumentation enabled")
    except ImportError:
        logger.warning("opentelemetry-instrumentation-httpx not installed")
    except Exception as e:
        logger.warning(f"Failed to instrument httpx: {e}")


def instrument_redis():
    """
    Instrument redis-py for Redis tracing.

    Call this at application startup to automatically trace
    all Redis operations.
    """
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()
        logger.info("OpenTelemetry Redis instrumentation enabled")
    except ImportError:
        logger.warning("opentelemetry-instrumentation-redis not installed")
    except Exception as e:
        logger.warning(f"Failed to instrument Redis: {e}")


def instrument_all():
    """
    Enable all available OpenTelemetry instrumentations.

    Call this at application startup to enable tracing for:
    - httpx (outbound HTTP)
    - Redis
    - Celery (if available)
    """
    instrument_httpx()
    instrument_redis()

    # Celery instrumentation
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        CeleryInstrumentor().instrument()
        logger.info("OpenTelemetry Celery instrumentation enabled")
    except ImportError:
        logger.warning("opentelemetry-instrumentation-celery not installed")
    except Exception as e:
        logger.warning(f"Failed to instrument Celery: {e}")

    # Logging instrumentation
    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        LoggingInstrumentor().instrument(set_logging_format=True)
        logger.info("OpenTelemetry logging instrumentation enabled")
    except ImportError:
        logger.warning("opentelemetry-instrumentation-logging not installed")
    except Exception as e:
        logger.warning(f"Failed to instrument logging: {e}")
