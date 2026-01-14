"""
Empire v7.3 - Request Tracing Utilities
Task 136: X-Request-ID Tracing Across Agent Chains

Utility functions for propagating request IDs through:
- HTTP client calls to downstream services
- Agent-to-agent communication
- Background task execution
- Logging and metrics correlation

This module re-exports core functions from the middleware and adds
additional utilities for agent chain propagation.
"""

from typing import Dict, Any, Optional, Callable, TypeVar
from functools import wraps
import httpx
import structlog

# Re-export from middleware for convenience
from app.middleware.request_tracing import (
    get_request_id,
    set_request_id,
    generate_request_id,
    get_request_context,
    request_id_var,
    request_context_var,
)

logger = structlog.get_logger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

# Header name constant
REQUEST_ID_HEADER = "X-Request-ID"


# ============================================================================
# HTTP Client Propagation
# ============================================================================


def with_request_id(headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Add current request ID to outgoing HTTP headers.

    Use this when making HTTP calls to downstream services to maintain
    request tracing through the entire call chain.

    Args:
        headers: Existing headers dict (optional, creates new if None)

    Returns:
        Headers dict with X-Request-ID added

    Example:
        # With httpx
        headers = with_request_id({"Authorization": "Bearer token"})
        response = httpx.get("http://service/api", headers=headers)

        # With requests
        headers = with_request_id()
        response = requests.post("http://service/api", headers=headers, json=data)
    """
    if headers is None:
        headers = {}
    else:
        headers = dict(headers)  # Don't mutate original

    request_id = get_request_id()
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id

    return headers


def propagate_request_id(
    client: httpx.AsyncClient,
    request_id: Optional[str] = None
) -> httpx.AsyncClient:
    """
    Configure an httpx AsyncClient to propagate request ID on all requests.

    This modifies the client's event hooks to add the X-Request-ID header
    to every request made through this client.

    Args:
        client: httpx.AsyncClient to configure
        request_id: Optional explicit request ID (uses current context if None)

    Returns:
        The configured client (same instance)

    Example:
        async with httpx.AsyncClient() as client:
            propagate_request_id(client)
            # All requests will now include X-Request-ID
            response = await client.get("http://service/api")
    """
    async def add_request_id_hook(request: httpx.Request):
        rid = request_id or get_request_id()
        if rid and REQUEST_ID_HEADER not in request.headers:
            request.headers[REQUEST_ID_HEADER] = rid

    # Add to existing hooks
    existing_hooks = client.event_hooks.get("request", [])
    existing_hooks.append(add_request_id_hook)
    client.event_hooks["request"] = existing_hooks

    return client


# ============================================================================
# Agent Chain Propagation
# ============================================================================


def agent_context(
    agent_id: str,
    parent_request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create context dict for agent-to-agent communication.

    Use this when delegating work to another agent to maintain
    the request chain and track parent-child relationships.

    Args:
        agent_id: ID of the agent receiving the delegation
        parent_request_id: Parent request ID (uses current if None)

    Returns:
        Context dict with tracing information

    Example:
        # In orchestrator agent
        ctx = agent_context("AGENT-002")
        await delegate_to_summarizer(content, context=ctx)

        # In receiving agent
        set_request_id(ctx["request_id"])
        logger.info("Processing", parent_request=ctx["parent_request_id"])
    """
    current_id = parent_request_id or get_request_id()
    current_context = get_request_context()

    return {
        "request_id": current_id or generate_request_id(),
        "parent_request_id": current_id,
        "delegating_agent": current_context.get("agent_id"),
        "target_agent": agent_id,
        "chain_depth": current_context.get("chain_depth", 0) + 1,
    }


def start_agent_span(
    agent_id: str,
    operation: str,
    parent_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Start a new span for agent processing.

    Creates tracing context for a specific agent operation,
    useful for timing and debugging agent chains.

    Args:
        agent_id: ID of the agent starting work
        operation: Name of the operation being performed
        parent_context: Optional parent context from delegation

    Returns:
        Span context dict

    Example:
        span = start_agent_span("AGENT-002", "summarize_document")
        try:
            result = await summarize(content)
            span["status"] = "success"
        except Exception as e:
            span["status"] = "error"
            span["error"] = str(e)
        finally:
            end_agent_span(span)
    """
    import time

    request_id = parent_context.get("request_id") if parent_context else get_request_id()
    if request_id:
        set_request_id(request_id)

    return {
        "agent_id": agent_id,
        "operation": operation,
        "request_id": request_id or generate_request_id(),
        "parent_request_id": parent_context.get("parent_request_id") if parent_context else None,
        "chain_depth": parent_context.get("chain_depth", 1) if parent_context else 1,
        "start_time": time.perf_counter(),
        "status": "in_progress",
    }


def end_agent_span(span: Dict[str, Any]) -> Dict[str, Any]:
    """
    End an agent span and log metrics.

    Args:
        span: Span context from start_agent_span

    Returns:
        Completed span with duration

    Example:
        span = start_agent_span("AGENT-002", "summarize")
        # ... do work ...
        completed = end_agent_span(span)
        # completed["duration_ms"] now available
    """
    import time

    span["end_time"] = time.perf_counter()
    span["duration_ms"] = round(
        (span["end_time"] - span["start_time"]) * 1000, 2
    )

    logger.info(
        "Agent span completed",
        agent_id=span["agent_id"],
        operation=span["operation"],
        request_id=span["request_id"],
        duration_ms=span["duration_ms"],
        status=span.get("status", "unknown"),
        chain_depth=span.get("chain_depth", 0),
    )

    return span


# ============================================================================
# Logging Utilities
# ============================================================================


def log_with_context(
    message: str,
    level: str = "info",
    **kwargs: Any
) -> None:
    """
    Log a message with automatic request context injection.

    Convenience function that adds request_id and any current
    context to log entries.

    Args:
        message: Log message
        level: Log level (debug, info, warning, error)
        **kwargs: Additional fields to log

    Example:
        log_with_context("Processing document", document_id="doc-123")
        # Output includes request_id automatically
    """
    request_id = get_request_id()
    context = get_request_context()

    log_data = {
        "request_id": request_id,
        **kwargs
    }

    # Add useful context fields if available
    if context.get("method"):
        log_data["method"] = context["method"]
    if context.get("path"):
        log_data["path"] = context["path"]

    log_func = getattr(logger, level, logger.info)
    log_func(message, **log_data)


# ============================================================================
# Decorators
# ============================================================================


def traced(operation: Optional[str] = None) -> Callable[[F], F]:
    """
    Decorator to add request tracing to a function.

    Automatically logs entry/exit with request context and timing.

    Args:
        operation: Operation name (defaults to function name)

    Example:
        @traced("fetch_documents")
        async def fetch_documents(user_id: str):
            # Function is automatically traced with request_id
            return await db.fetch(user_id)
    """
    def decorator(func: F) -> F:
        op_name = operation or func.__name__

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            request_id = get_request_id()
            import time
            start = time.perf_counter()

            logger.debug(
                f"Starting {op_name}",
                request_id=request_id,
                operation=op_name
            )

            try:
                result = await func(*args, **kwargs)
                duration = round((time.perf_counter() - start) * 1000, 2)

                logger.debug(
                    f"Completed {op_name}",
                    request_id=request_id,
                    operation=op_name,
                    duration_ms=duration,
                    status="success"
                )
                return result

            except Exception as e:
                duration = round((time.perf_counter() - start) * 1000, 2)

                logger.error(
                    f"Failed {op_name}",
                    request_id=request_id,
                    operation=op_name,
                    duration_ms=duration,
                    status="error",
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            request_id = get_request_id()
            import time
            start = time.perf_counter()

            logger.debug(
                f"Starting {op_name}",
                request_id=request_id,
                operation=op_name
            )

            try:
                result = func(*args, **kwargs)
                duration = round((time.perf_counter() - start) * 1000, 2)

                logger.debug(
                    f"Completed {op_name}",
                    request_id=request_id,
                    operation=op_name,
                    duration_ms=duration,
                    status="success"
                )
                return result

            except Exception as e:
                duration = round((time.perf_counter() - start) * 1000, 2)

                logger.error(
                    f"Failed {op_name}",
                    request_id=request_id,
                    operation=op_name,
                    duration_ms=duration,
                    status="error",
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


# ============================================================================
# Background Task Support
# ============================================================================


def with_tracing_context(
    request_id: Optional[str] = None
) -> Callable[[F], F]:
    """
    Decorator for background tasks to preserve request context.

    Use this on Celery tasks or other background functions that
    should maintain the request tracing chain.

    Args:
        request_id: Explicit request ID (captures current if None)

    Example:
        @celery.task
        @with_tracing_context()
        def process_document(doc_id: str):
            # request_id is available via get_request_id()
            logger.info("Processing", doc_id=doc_id)
    """
    def decorator(func: F) -> F:
        captured_id = request_id or get_request_id()

        @wraps(func)
        def wrapper(*args, **kwargs):
            if captured_id:
                set_request_id(captured_id)
            return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if captured_id:
                set_request_id(captured_id)
            return await func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore

    return decorator


def create_task_context() -> Dict[str, str]:
    """
    Create a serializable context dict for passing to background tasks.

    Returns a dict that can be JSON-serialized and passed to
    Celery or other task systems.

    Example:
        # In API handler
        ctx = create_task_context()
        process_document.delay(doc_id, tracing_context=ctx)

        # In Celery task
        @celery.task
        def process_document(doc_id: str, tracing_context: dict = None):
            if tracing_context:
                set_request_id(tracing_context.get("request_id"))
            # ... process
    """
    return {
        "request_id": get_request_id() or generate_request_id(),
        "parent_context": get_request_context(),
    }


def restore_task_context(context: Dict[str, Any]) -> None:
    """
    Restore tracing context in a background task.

    Args:
        context: Context dict from create_task_context()

    Example:
        @celery.task
        def process_document(doc_id: str, tracing_context: dict = None):
            if tracing_context:
                restore_task_context(tracing_context)
            log_with_context("Processing document", doc_id=doc_id)
    """
    request_id = context.get("request_id")
    if request_id:
        set_request_id(request_id)
