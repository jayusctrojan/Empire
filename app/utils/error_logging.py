"""
Empire v7.3 - Contextual Error Logging Utility
Task 154: Standardized Exception Handling Framework

Provides contextual error logging with request tracing, caller identification,
and structured context for debugging and monitoring.
"""

import inspect
import traceback
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from functools import wraps

import structlog
from fastapi import Request

from app.exceptions.base import BaseAppException

logger = structlog.get_logger(__name__)


class ErrorLogger:
    """
    Contextual error logging utility for Empire v7.3.

    Provides methods to log errors with full context including:
    - Request information (ID, path, method, client IP)
    - Caller information (function name, module)
    - Exception details and stack traces
    - Custom context data
    """

    @staticmethod
    def log_error(
        error: Exception,
        request: Optional[Request] = None,
        context: Optional[Dict[str, Any]] = None,
        level: str = "error",
        include_traceback: bool = True
    ) -> str:
        """
        Log an error with full context.

        Args:
            error: The exception to log
            request: Optional FastAPI request object for request context
            context: Optional additional context dictionary
            level: Log level (debug, info, warning, error, critical)
            include_traceback: Whether to include the full traceback

        Returns:
            The request_id for correlation
        """
        # Get calling function and module
        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller_frame = frame.f_back
            func_name = caller_frame.f_code.co_name
            module_name = caller_frame.f_globals.get("__name__", "unknown")
        else:
            func_name = "unknown"
            module_name = "unknown"

        # Build error context
        error_context: Dict[str, Any] = {
            "exception_type": type(error).__name__,
            "exception_message": str(error),
            "caller_function": func_name,
            "caller_module": module_name,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add request context if available
        request_id = str(uuid.uuid4())
        if request:
            request_id = getattr(request.state, "request_id", request_id)
            error_context.update({
                "request_id": request_id,
                "request_path": str(request.url.path),
                "request_method": request.method,
                "client_ip": request.client.host if request.client else "unknown",
                "query_params": dict(request.query_params) if request.query_params else {},
            })

            # Add user context if available
            user_id = getattr(request.state, "user_id", None)
            if user_id:
                error_context["user_id"] = user_id
        else:
            error_context["request_id"] = request_id

        # Add BaseAppException-specific details
        if isinstance(error, BaseAppException):
            error_context.update({
                "error_code": error.error_code,
                "status_code": error.status_code,
                "error_details": error.details,
                "retriable": error.retriable,
                "severity": error.severity,
            })

        # Add custom context
        if context:
            error_context["custom_context"] = context

        # Add traceback if requested
        if include_traceback:
            error_context["traceback"] = traceback.format_exc()

        # Get the appropriate log method
        log_method = getattr(logger, level, logger.error)

        # Log the error
        log_method(
            f"{type(error).__name__} in {module_name}.{func_name}: {str(error)}",
            **error_context
        )

        return request_id

    @staticmethod
    def log_warning(
        message: str,
        request: Optional[Request] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log a warning message with context.

        Args:
            message: Warning message
            request: Optional FastAPI request object
            context: Optional additional context

        Returns:
            The request_id for correlation
        """
        # Get calling function and module
        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller_frame = frame.f_back
            func_name = caller_frame.f_code.co_name
            module_name = caller_frame.f_globals.get("__name__", "unknown")
        else:
            func_name = "unknown"
            module_name = "unknown"

        # Build context
        log_context: Dict[str, Any] = {
            "caller_function": func_name,
            "caller_module": module_name,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add request context
        request_id = str(uuid.uuid4())
        if request:
            request_id = getattr(request.state, "request_id", request_id)
            log_context.update({
                "request_id": request_id,
                "request_path": str(request.url.path),
                "request_method": request.method,
            })
        else:
            log_context["request_id"] = request_id

        # Add custom context
        if context:
            log_context.update(context)

        logger.warning(message, **log_context)
        return request_id

    @staticmethod
    def log_info(
        message: str,
        request: Optional[Request] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log an info message with context.

        Args:
            message: Info message
            request: Optional FastAPI request object
            context: Optional additional context

        Returns:
            The request_id for correlation
        """
        # Build context
        log_context: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
        }

        request_id = str(uuid.uuid4())
        if request:
            request_id = getattr(request.state, "request_id", request_id)
            log_context["request_id"] = request_id

        if context:
            log_context.update(context)

        logger.info(message, **log_context)
        return request_id


class ErrorContext:
    """
    Context manager for capturing and logging errors in a code block.

    Usage:
        with ErrorContext(request=request, context={"operation": "process_document"}):
            # Code that might raise an exception
            result = await process_document(doc_id)
    """

    def __init__(
        self,
        request: Optional[Request] = None,
        context: Optional[Dict[str, Any]] = None,
        reraise: bool = True,
        log_level: str = "error"
    ):
        """
        Initialize the error context.

        Args:
            request: Optional FastAPI request for context
            context: Additional context to include in logs
            reraise: Whether to re-raise caught exceptions
            log_level: Log level for errors (default: error)
        """
        self.request = request
        self.context = context or {}
        self.reraise = reraise
        self.log_level = log_level
        self.error: Optional[Exception] = None
        self.request_id: Optional[str] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            self.error = exc_val
            self.request_id = ErrorLogger.log_error(
                error=exc_val,
                request=self.request,
                context=self.context,
                level=self.log_level
            )

            if not self.reraise:
                return True  # Suppress the exception

        return False  # Re-raise if reraise=True


def log_errors(
    context: Optional[Dict[str, Any]] = None,
    reraise: bool = True,
    log_level: str = "error"
):
    """
    Decorator for automatically logging errors from functions.

    Usage:
        @log_errors(context={"service": "document_processor"})
        async def process_document(doc_id: str):
            # Code that might raise an exception
            pass

    Args:
        context: Additional context to include in logs
        reraise: Whether to re-raise caught exceptions
        log_level: Log level for errors (default: error)
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Try to extract request from args or kwargs
                request = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
                if not request:
                    request = kwargs.get("request")

                # Build context with function info
                error_context = context.copy() if context else {}
                error_context["decorated_function"] = func.__name__
                error_context["args_count"] = len(args)
                error_context["kwargs_keys"] = list(kwargs.keys())

                ErrorLogger.log_error(
                    error=e,
                    request=request,
                    context=error_context,
                    level=log_level
                )

                if reraise:
                    raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                request = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
                if not request:
                    request = kwargs.get("request")

                error_context = context.copy() if context else {}
                error_context["decorated_function"] = func.__name__

                ErrorLogger.log_error(
                    error=e,
                    request=request,
                    context=error_context,
                    level=log_level
                )

                if reraise:
                    raise

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class ErrorAggregator:
    """
    Aggregates multiple errors for batch operations.

    Useful for collecting errors during batch processing without
    stopping on the first error.

    Usage:
        aggregator = ErrorAggregator()

        for item in items:
            try:
                process_item(item)
            except Exception as e:
                aggregator.add_error(e, context={"item_id": item.id})

        if aggregator.has_errors:
            aggregator.log_all(request=request)
            raise aggregator.to_exception()
    """

    def __init__(self):
        self.errors: List[Dict[str, Any]] = []

    def add_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ):
        """Add an error to the aggregator."""
        self.errors.append({
            "exception": error,
            "exception_type": type(error).__name__,
            "message": str(error),
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat(),
        })

    @property
    def has_errors(self) -> bool:
        """Check if any errors have been collected."""
        return len(self.errors) > 0

    @property
    def error_count(self) -> int:
        """Get the number of collected errors."""
        return len(self.errors)

    def log_all(
        self,
        request: Optional[Request] = None,
        level: str = "error"
    ) -> str:
        """
        Log all collected errors.

        Returns:
            The request_id for correlation
        """
        if not self.errors:
            return ""

        request_id = str(uuid.uuid4())
        if request:
            request_id = getattr(request.state, "request_id", request_id)

        log_context = {
            "request_id": request_id,
            "error_count": len(self.errors),
            "errors": [
                {
                    "type": e["exception_type"],
                    "message": e["message"],
                    "context": e["context"],
                }
                for e in self.errors
            ],
        }

        log_method = getattr(logger, level, logger.error)
        log_method(
            f"Batch operation completed with {len(self.errors)} error(s)",
            **log_context
        )

        return request_id

    def to_exception(self) -> BaseAppException:
        """
        Convert aggregated errors to a single exception.

        Returns:
            BaseAppException with all error details
        """
        from app.exceptions import InternalServerException

        return InternalServerException(
            message=f"Batch operation failed with {len(self.errors)} error(s)",
            details={
                "error_count": len(self.errors),
                "errors": [
                    {
                        "type": e["exception_type"],
                        "message": e["message"],
                        "context": e["context"],
                    }
                    for e in self.errors
                ],
            }
        )

    def clear(self):
        """Clear all collected errors."""
        self.errors = []
