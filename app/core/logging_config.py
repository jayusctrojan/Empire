"""
Empire v7.3 - Logging Configuration
Task 136: X-Request-ID Tracing Integration

Centralized logging configuration with:
- Structlog for structured logging
- Request ID injection into all log entries
- JSON output for production
- Console output for development
- Standard library logging integration
"""

import logging
import os
import sys
from typing import Any, Dict

import structlog

from app.middleware.request_tracing import (
    add_request_id_processor,
    RequestIdFilter,
    get_request_id,
)


def configure_logging(
    log_level: str = "INFO",
    json_output: bool = False,
    include_timestamps: bool = True,
) -> None:
    """
    Configure application logging with structlog and request ID integration.

    This should be called early in application startup (e.g., in main.py lifespan).

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        json_output: Use JSON formatter (True for production)
        include_timestamps: Include ISO timestamps in output

    Example:
        # In main.py lifespan
        from app.core.logging_config import configure_logging

        configure_logging(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            json_output=os.getenv("ENVIRONMENT") == "production"
        )
    """
    # Determine environment
    environment = os.getenv("ENVIRONMENT", "development")
    is_production = environment == "production"

    # Use JSON in production, console in development
    if json_output or is_production:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )

    # Build processor chain
    processors = [
        # Add log level
        structlog.stdlib.add_log_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add request ID from context (Task 136)
        add_request_id_processor,
        # Add timestamps if enabled
        structlog.processors.TimeStamper(fmt="iso") if include_timestamps else structlog.processors.TimeStamper(fmt=None),
        # Handle positional arguments
        structlog.stdlib.PositionalArgumentsFormatter(),
        # Format stack traces
        structlog.processors.StackInfoRenderer(),
        # Format exceptions
        structlog.processors.format_exc_info,
        # Ensure unicode compatibility
        structlog.processors.UnicodeDecoder(),
        # Final renderer
        renderer,
    ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    _configure_stdlib_logging(log_level, is_production)


def _configure_stdlib_logging(log_level: str, is_production: bool) -> None:
    """
    Configure Python's standard library logging for third-party packages.

    This ensures that logs from httpx, uvicorn, etc. also get
    processed through our logging chain.
    """
    # Get numeric log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create formatter with request_id support
    if is_production:
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "request_id": "%(request_id)s", '
            '"message": "%(message)s"}'
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | "
            "[%(request_id)s] | %(message)s"
        )

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Add request ID filter
    handler.addFilter(RequestIdFilter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers = []
    root_logger.addHandler(handler)

    # Configure specific loggers for quieter third-party logs
    for logger_name in ["httpx", "httpcore", "urllib3", "asyncio"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)

    # Keep uvicorn logs at INFO
    logging.getLogger("uvicorn").setLevel(numeric_level)
    logging.getLogger("uvicorn.access").setLevel(numeric_level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structlog logger with request ID support.

    This is the preferred way to get loggers in Empire.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured structlog logger

    Example:
        from app.core.logging_config import get_logger

        logger = get_logger(__name__)
        logger.info("Processing document", doc_id="123")
        # Output includes request_id automatically
    """
    return structlog.get_logger(name)


class LoggingContext:
    """
    Context manager for adding temporary fields to all logs.

    Example:
        with LoggingContext(user_id="user-123", operation="upload"):
            logger.info("Starting upload")  # Includes user_id and operation
            # ... do work ...
            logger.info("Upload complete")  # Also includes user_id and operation
    """

    def __init__(self, **kwargs: Any):
        self.context = kwargs
        self._token = None

    def __enter__(self):
        self._token = structlog.contextvars.bind_contextvars(**self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._token:
            structlog.contextvars.unbind_contextvars(*self.context.keys())


def log_with_request_id(
    message: str,
    level: str = "info",
    logger_name: str = "empire",
    **kwargs: Any
) -> None:
    """
    Convenience function to log with automatic request ID.

    Args:
        message: Log message
        level: Log level (debug, info, warning, error)
        logger_name: Logger name
        **kwargs: Additional fields

    Example:
        log_with_request_id("User logged in", user_id="123")
    """
    logger = get_logger(logger_name)
    log_func = getattr(logger, level, logger.info)
    log_func(message, **kwargs)


# Pre-configured logger for common imports
logger = get_logger("empire")
