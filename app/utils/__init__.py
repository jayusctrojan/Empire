"""
Empire v7.3 - Utility Functions

This package contains utility modules for various system functions.
"""

from app.utils.tracing import (
    get_request_id,
    set_request_id,
    generate_request_id,
    get_request_context,
    with_request_id,
    propagate_request_id,
    log_with_context,
)

# Task 154: Error logging utilities
from app.utils.error_logging import (
    ErrorLogger,
    ErrorContext,
    ErrorAggregator,
    log_errors,
)

__all__ = [
    # Tracing utilities
    "get_request_id",
    "set_request_id",
    "generate_request_id",
    "get_request_context",
    "with_request_id",
    "propagate_request_id",
    "log_with_context",
    # Error logging utilities (Task 154)
    "ErrorLogger",
    "ErrorContext",
    "ErrorAggregator",
    "log_errors",
]
