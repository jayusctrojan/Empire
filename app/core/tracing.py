"""
Empire v7.3 - OpenTelemetry Distributed Tracing
Task 189: Distributed tracing across all services

Provides:
- OpenTelemetry tracer configuration
- Span creation and context propagation
- Integration with structlog for trace IDs in logs
- Celery task tracing support
- OTLP exporter for backend (Jaeger, Tempo, etc.)
"""

import os
from typing import Optional, Dict, Any
from contextlib import contextmanager

import structlog

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.trace import StatusCode, Status
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagate import set_global_textmap, get_global_textmap
from opentelemetry.propagators.composite import CompositePropagator

logger = structlog.get_logger(__name__)

# Service configuration
SERVICE_NAME_VALUE = os.getenv("OTEL_SERVICE_NAME", "empire-api")
SERVICE_VERSION_VALUE = os.getenv("SERVICE_VERSION", "7.3.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# OTLP exporter configuration
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
OTLP_INSECURE = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"

# Enable/disable tracing
TRACING_ENABLED = os.getenv("OTEL_TRACING_ENABLED", "true").lower() == "true"

# Global tracer instance
_tracer: Optional[trace.Tracer] = None
_tracer_provider: Optional[TracerProvider] = None


def setup_tracing() -> trace.Tracer:
    """
    Configure OpenTelemetry tracing for Empire.

    Sets up:
    - TracerProvider with service resource
    - OTLP exporter (if configured) or Console exporter (dev)
    - W3C TraceContext propagator for distributed tracing

    Returns:
        Configured tracer instance
    """
    global _tracer, _tracer_provider

    if not TRACING_ENABLED:
        logger.info("OpenTelemetry tracing is disabled")
        return trace.get_tracer(SERVICE_NAME_VALUE, SERVICE_VERSION_VALUE)

    # Create resource with service information
    resource = Resource.create({
        SERVICE_NAME: SERVICE_NAME_VALUE,
        SERVICE_VERSION: SERVICE_VERSION_VALUE,
        "deployment.environment": ENVIRONMENT,
        "service.namespace": "empire",
    })

    # Create tracer provider
    _tracer_provider = TracerProvider(resource=resource)

    # Configure span processor and exporter
    if OTLP_ENDPOINT:
        try:
            # Use OTLP exporter for production (Jaeger, Tempo, etc.)
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            otlp_exporter = OTLPSpanExporter(
                endpoint=OTLP_ENDPOINT,
                insecure=OTLP_INSECURE
            )
            _tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(
                "OpenTelemetry OTLP exporter configured",
                endpoint=OTLP_ENDPOINT,
                insecure=OTLP_INSECURE
            )
        except Exception as e:
            logger.warning(f"Failed to configure OTLP exporter: {e}, falling back to console")
            _tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        # Use console exporter for development
        if ENVIRONMENT == "development":
            _tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            logger.info("OpenTelemetry console exporter configured (development mode)")
        else:
            logger.info("OpenTelemetry tracing configured without exporter (production mode, no endpoint)")

    # Set the global tracer provider
    trace.set_tracer_provider(_tracer_provider)

    # Configure propagators for distributed tracing (W3C TraceContext + Baggage)
    propagator = CompositePropagator([
        TraceContextTextMapPropagator(),
        W3CBaggagePropagator()
    ])
    set_global_textmap(propagator)

    # Get tracer instance
    _tracer = trace.get_tracer(SERVICE_NAME_VALUE, SERVICE_VERSION_VALUE)

    logger.info(
        "OpenTelemetry tracing initialized",
        service_name=SERVICE_NAME_VALUE,
        service_version=SERVICE_VERSION_VALUE,
        environment=ENVIRONMENT
    )

    return _tracer


def get_tracer() -> trace.Tracer:
    """
    Get the configured tracer instance.

    Initializes tracing if not already done.

    Returns:
        Tracer instance
    """
    global _tracer
    if _tracer is None:
        _tracer = setup_tracing()
    return _tracer


def shutdown_tracing():
    """Shutdown the tracer provider and flush pending spans."""
    if _tracer_provider:
        _tracer_provider.shutdown()
        logger.info("OpenTelemetry tracing shutdown complete")


# ==============================================================================
# Trace Context Propagation
# ==============================================================================


def inject_trace_context(carrier: Dict[str, str]) -> Dict[str, str]:
    """
    Inject current trace context into a carrier (headers dict).

    Use this when making outbound HTTP calls or Celery tasks.

    Args:
        carrier: Dict to inject trace context into

    Returns:
        Carrier with trace context headers
    """
    propagator = get_global_textmap()
    propagator.inject(carrier)
    return carrier


def extract_trace_context(carrier: Dict[str, str]):
    """
    Extract trace context from a carrier (headers dict).

    Use this when receiving requests or processing Celery tasks.

    Args:
        carrier: Dict containing trace context headers

    Returns:
        OpenTelemetry Context object
    """
    propagator = get_global_textmap()
    return propagator.extract(carrier)


def get_current_trace_id() -> Optional[str]:
    """
    Get the current trace ID as a hex string.

    Returns:
        Trace ID string or None if no active span
    """
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().trace_id, "032x")
    return None


def get_current_span_id() -> Optional[str]:
    """
    Get the current span ID as a hex string.

    Returns:
        Span ID string or None if no active span
    """
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().span_id, "016x")
    return None


def get_traceparent() -> Optional[str]:
    """
    Get the W3C traceparent header value for the current span.

    Returns:
        Traceparent string (00-{trace_id}-{span_id}-{flags}) or None
    """
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        ctx = span.get_span_context()
        trace_id = format(ctx.trace_id, "032x")
        span_id = format(ctx.span_id, "016x")
        flags = format(ctx.trace_flags, "02x")
        return f"00-{trace_id}-{span_id}-{flags}"
    return None


# ==============================================================================
# Span Creation Utilities
# ==============================================================================


@contextmanager
def create_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
    parent_context=None
):
    """
    Context manager for creating OpenTelemetry spans.

    Args:
        name: Span name (operation being performed)
        attributes: Key-value attributes to add to span
        kind: Span kind (INTERNAL, SERVER, CLIENT, PRODUCER, CONSUMER)
        parent_context: Optional parent context for distributed tracing

    Yields:
        Active span

    Example:
        with create_span("document.process", {"document_id": doc_id}) as span:
            result = process_document(doc_id)
            span.set_attribute("result_size", len(result))
    """
    tracer = get_tracer()

    if parent_context:
        with tracer.start_as_current_span(
            name,
            context=parent_context,
            kind=kind,
            attributes=attributes or {}
        ) as span:
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    else:
        with tracer.start_as_current_span(
            name,
            kind=kind,
            attributes=attributes or {}
        ) as span:
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise


def start_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
    parent_context=None
) -> trace.Span:
    """
    Start a new span (must be manually ended).

    Use create_span() context manager instead when possible.

    Args:
        name: Span name
        attributes: Span attributes
        kind: Span kind
        parent_context: Optional parent context

    Returns:
        Started span (remember to call span.end())
    """
    tracer = get_tracer()

    if parent_context:
        span = tracer.start_span(
            name,
            context=parent_context,
            kind=kind,
            attributes=attributes or {}
        )
    else:
        span = tracer.start_span(
            name,
            kind=kind,
            attributes=attributes or {}
        )

    return span


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    Add an event to the current span.

    Args:
        name: Event name
        attributes: Event attributes
    """
    span = trace.get_current_span()
    if span:
        span.add_event(name, attributes=attributes or {})


def set_span_attribute(key: str, value: Any):
    """
    Set an attribute on the current span.

    Args:
        key: Attribute key
        value: Attribute value
    """
    span = trace.get_current_span()
    if span:
        span.set_attribute(key, value)


def set_span_error(error: Exception, message: Optional[str] = None):
    """
    Mark the current span as error and record the exception.

    Args:
        error: Exception that occurred
        message: Optional error message
    """
    span = trace.get_current_span()
    if span:
        span.set_status(Status(StatusCode.ERROR, message or str(error)))
        span.record_exception(error)


# ==============================================================================
# Structlog Integration
# ==============================================================================


def add_trace_context_processor(_, __, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Structlog processor that adds trace context to log entries.

    Add this to your structlog configuration to include trace_id and span_id
    in all log messages.

    Example:
        structlog.configure(
            processors=[
                add_trace_context_processor,
                structlog.processors.JSONRenderer(),
            ]
        )
    """
    trace_id = get_current_trace_id()
    span_id = get_current_span_id()

    if trace_id:
        event_dict["trace_id"] = trace_id
    if span_id:
        event_dict["span_id"] = span_id

    return event_dict


def get_trace_context_for_logging() -> Dict[str, str]:
    """
    Get trace context as a dict for manual logging.

    Returns:
        Dict with trace_id and span_id (if available)
    """
    result = {}
    trace_id = get_current_trace_id()
    span_id = get_current_span_id()

    if trace_id:
        result["trace_id"] = trace_id
    if span_id:
        result["span_id"] = span_id

    return result


# ==============================================================================
# Celery Task Tracing Support
# ==============================================================================


def create_celery_task_context() -> Dict[str, str]:
    """
    Create trace context dict for passing to Celery tasks.

    Returns:
        Dict with traceparent header for context propagation

    Example:
        # In API handler
        ctx = create_celery_task_context()
        process_document.delay(doc_id, trace_context=ctx)

        # In Celery task
        @celery_app.task
        def process_document(doc_id, trace_context=None):
            if trace_context:
                parent_ctx = restore_celery_task_context(trace_context)
                with create_span("process_document", parent_context=parent_ctx):
                    # ... process
    """
    context = {}
    inject_trace_context(context)
    return context


def restore_celery_task_context(context: Dict[str, str]):
    """
    Restore trace context from Celery task headers.

    Args:
        context: Dict with traceparent header

    Returns:
        OpenTelemetry Context for creating child spans
    """
    return extract_trace_context(context)


# ==============================================================================
# Decorator for Automatic Span Creation
# ==============================================================================


def traced(
    name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL
):
    """
    Decorator to automatically create spans for functions.

    Args:
        name: Span name (defaults to function name)
        attributes: Static attributes to add to span
        kind: Span kind

    Example:
        @traced("document.upload", {"service": "document_management"})
        async def upload_document(file_path: str, project_id: str):
            # ... upload logic
    """
    def decorator(func):
        import asyncio
        from functools import wraps

        span_name = name or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with create_span(span_name, attributes=attributes, kind=kind) as span:
                # Add function arguments as span attributes
                for i, arg in enumerate(args[:3]):  # Limit to first 3 args
                    if isinstance(arg, (str, int, float, bool)):
                        span.set_attribute(f"arg_{i}", str(arg)[:100])

                result = await func(*args, **kwargs)
                return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with create_span(span_name, attributes=attributes, kind=kind) as span:
                # Add function arguments as span attributes
                for i, arg in enumerate(args[:3]):  # Limit to first 3 args
                    if isinstance(arg, (str, int, float, bool)):
                        span.set_attribute(f"arg_{i}", str(arg)[:100])

                result = func(*args, **kwargs)
                return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
