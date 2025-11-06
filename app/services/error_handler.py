"""
Empire v7.3 - Error Handling Service
Centralized error handling, logging, and retry management
"""

import traceback
import logging
from typing import Optional, Dict, Any, Callable, Type
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)


# ============================================================================
# Error Classification
# ============================================================================

class ErrorSeverity(str, Enum):
    """Error severity levels"""
    CRITICAL = "critical"  # System failure, requires immediate attention
    ERROR = "error"        # Operation failed, needs investigation
    WARNING = "warning"    # Potential issue, degraded functionality
    INFO = "info"         # Informational, operation recovered


class ErrorCategory(str, Enum):
    """Error categories for classification"""
    NETWORK = "network"              # Network connectivity issues
    SERVICE_UNAVAILABLE = "service_unavailable"  # External service down
    VALIDATION = "validation"        # Data validation errors
    PARSING = "parsing"              # Document parsing failures
    DATABASE = "database"            # Database operation failures
    STORAGE = "storage"              # File storage errors
    TIMEOUT = "timeout"              # Operation timeout
    AUTHENTICATION = "authentication"  # Auth/permission errors
    CONFIGURATION = "configuration"  # Configuration issues
    UNKNOWN = "unknown"              # Unclassified errors


class RetryStrategy(str, Enum):
    """Retry strategy types"""
    NONE = "none"                    # Don't retry
    IMMEDIATE = "immediate"          # Retry immediately
    LINEAR = "linear"                # Linear backoff
    EXPONENTIAL = "exponential"      # Exponential backoff
    CUSTOM = "custom"                # Custom retry logic


# ============================================================================
# Error Data Classes
# ============================================================================

@dataclass
class ErrorContext:
    """Context information for an error"""
    task_id: Optional[str] = None
    task_type: Optional[str] = None
    file_id: Optional[str] = None
    filename: Optional[str] = None
    user_id: Optional[str] = None
    document_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    additional_context: Optional[Dict[str, Any]] = None


@dataclass
class ProcessingLog:
    """Structured processing log entry"""
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    error_type: str
    error_message: str
    stack_trace: Optional[str]
    context: ErrorContext
    recovery_action: Optional[str] = None
    resolution_status: str = "unresolved"  # unresolved, retrying, resolved, failed


# ============================================================================
# Error Classification Helper
# ============================================================================

class ErrorClassifier:
    """Classify errors into categories and determine retry strategies"""

    # Transient errors that should be retried
    TRANSIENT_ERROR_TYPES = {
        "ConnectionError",
        "TimeoutError",
        "Timeout",
        "HTTPError",
        "RequestException",
        "ServiceUnavailable",
        "TooManyRequests",
        "TemporaryFailure",
    }

    # Permanent errors that should not be retried
    PERMANENT_ERROR_TYPES = {
        "ValidationError",
        "ValueError",
        "TypeError",
        "FileNotFoundError",
        "PermissionError",
        "AuthenticationError",
        "ConfigurationError",
    }

    @staticmethod
    def classify_error(exception: Exception) -> tuple[ErrorCategory, RetryStrategy]:
        """
        Classify an error and determine retry strategy

        Args:
            exception: The exception to classify

        Returns:
            Tuple of (ErrorCategory, RetryStrategy)
        """
        error_type = type(exception).__name__
        error_message = str(exception).lower()

        # Timeout errors (check first before network errors)
        if "Timeout" in error_type or "timeout" in error_message:
            return ErrorCategory.TIMEOUT, RetryStrategy.EXPONENTIAL

        # Network errors
        if any(keyword in error_type for keyword in ["Connection", "Network", "HTTP"]):
            return ErrorCategory.NETWORK, RetryStrategy.EXPONENTIAL

        # Service unavailable
        if any(keyword in error_message for keyword in ["503", "service unavailable", "temporarily unavailable"]):
            return ErrorCategory.SERVICE_UNAVAILABLE, RetryStrategy.EXPONENTIAL

        # Validation errors
        if any(keyword in error_type for keyword in ["Validation", "ValueError", "TypeError"]):
            return ErrorCategory.VALIDATION, RetryStrategy.NONE

        # Parsing errors
        if any(keyword in error_type for keyword in ["Parse", "Decode", "Json", "Xml"]):
            return ErrorCategory.PARSING, RetryStrategy.NONE

        # Parsing errors in message
        if any(keyword in error_message for keyword in ["parse", "parsing", "invalid json", "invalid xml"]):
            return ErrorCategory.PARSING, RetryStrategy.NONE

        # Database errors
        if any(keyword in error_type for keyword in ["Database", "SQL", "Connection"]):
            if "lock" in error_message or "deadlock" in error_message:
                return ErrorCategory.DATABASE, RetryStrategy.LINEAR
            return ErrorCategory.DATABASE, RetryStrategy.EXPONENTIAL

        # Storage errors
        if any(keyword in error_type for keyword in ["Storage", "File", "IO"]):
            if "not found" in error_message:
                return ErrorCategory.STORAGE, RetryStrategy.NONE
            return ErrorCategory.STORAGE, RetryStrategy.EXPONENTIAL

        # Auth errors
        if any(keyword in error_type for keyword in ["Auth", "Permission", "Forbidden"]):
            return ErrorCategory.AUTHENTICATION, RetryStrategy.NONE

        # Check if transient
        if error_type in ErrorClassifier.TRANSIENT_ERROR_TYPES:
            return ErrorCategory.UNKNOWN, RetryStrategy.EXPONENTIAL

        # Check if permanent
        if error_type in ErrorClassifier.PERMANENT_ERROR_TYPES:
            return ErrorCategory.UNKNOWN, RetryStrategy.NONE

        # Default to retrying unknown errors with exponential backoff
        return ErrorCategory.UNKNOWN, RetryStrategy.EXPONENTIAL

    @staticmethod
    def is_retryable(exception: Exception) -> bool:
        """Determine if an error should be retried"""
        _, strategy = ErrorClassifier.classify_error(exception)
        return strategy != RetryStrategy.NONE


# ============================================================================
# Error Handler Service
# ============================================================================

class ErrorHandler:
    """Centralized error handling service"""

    def __init__(self, supabase_storage=None):
        """
        Initialize error handler

        Args:
            supabase_storage: Optional Supabase storage service for logging to DB
        """
        self.supabase_storage = supabase_storage
        self._fallback_callbacks = {}

    async def handle_error(
        self,
        exception: Exception,
        context: ErrorContext,
        severity: Optional[ErrorSeverity] = None,
        custom_recovery: Optional[Callable] = None
    ) -> ProcessingLog:
        """
        Handle an error: classify, log, and optionally recover

        Args:
            exception: The exception that occurred
            context: Context information about the error
            severity: Optional manual severity override
            custom_recovery: Optional custom recovery function

        Returns:
            ProcessingLog entry
        """
        # Classify error
        category, retry_strategy = ErrorClassifier.classify_error(exception)

        # Determine severity if not provided
        if severity is None:
            severity = self._determine_severity(exception, category, context.retry_count)

        # Create processing log
        log_entry = ProcessingLog(
            timestamp=datetime.utcnow(),
            severity=severity,
            category=category,
            error_type=type(exception).__name__,
            error_message=str(exception),
            stack_trace=traceback.format_exc(),
            context=context,
            recovery_action=None,
            resolution_status="retrying" if retry_strategy != RetryStrategy.NONE else "failed"
        )

        # Log to Python logger
        self._log_to_python_logger(log_entry)

        # Log to database if available
        if self.supabase_storage:
            await self._log_to_database(log_entry)

        # Attempt recovery if provided
        if custom_recovery:
            try:
                await custom_recovery(exception, context)
                log_entry.recovery_action = "custom_recovery_executed"
                log_entry.resolution_status = "resolved"
            except Exception as recovery_error:
                logger.error(f"Recovery function failed: {recovery_error}")
                log_entry.recovery_action = "custom_recovery_failed"

        return log_entry

    def _determine_severity(self, exception: Exception, category: ErrorCategory, retry_count: int) -> ErrorSeverity:
        """Determine error severity based on type and retry count"""
        # Critical if we've exhausted retries
        if retry_count >= 3:
            return ErrorSeverity.CRITICAL

        # Critical categories
        if category in [ErrorCategory.DATABASE, ErrorCategory.AUTHENTICATION]:
            return ErrorSeverity.ERROR

        # Permanent errors are errors
        if not ErrorClassifier.is_retryable(exception):
            return ErrorSeverity.ERROR

        # Transient errors are warnings
        return ErrorSeverity.WARNING

    def _log_to_python_logger(self, log_entry: ProcessingLog):
        """Log to Python logging system"""
        log_message = (
            f"[{log_entry.severity.value.upper()}] "
            f"{log_entry.category.value} - {log_entry.error_type}: {log_entry.error_message}"
        )

        if log_entry.context.task_type:
            log_message += f" (task: {log_entry.context.task_type})"
        if log_entry.context.filename:
            log_message += f" (file: {log_entry.context.filename})"

        if log_entry.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif log_entry.severity == ErrorSeverity.ERROR:
            logger.error(log_message)
        elif log_entry.severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)

    async def _log_to_database(self, log_entry: ProcessingLog):
        """Log to processing_logs table in database"""
        try:
            await self.supabase_storage.insert_processing_log({
                "timestamp": log_entry.timestamp.isoformat(),
                "severity": log_entry.severity.value,
                "category": log_entry.category.value,
                "error_type": log_entry.error_type,
                "error_message": log_entry.error_message,
                "stack_trace": log_entry.stack_trace,
                "task_id": log_entry.context.task_id,
                "task_type": log_entry.context.task_type,
                "file_id": log_entry.context.file_id,
                "filename": log_entry.context.filename,
                "user_id": log_entry.context.user_id,
                "document_id": log_entry.context.document_id,
                "retry_count": log_entry.context.retry_count,
                "max_retries": log_entry.context.max_retries,
                "recovery_action": log_entry.recovery_action,
                "resolution_status": log_entry.resolution_status,
                "additional_context": log_entry.context.additional_context
            })
        except Exception as e:
            logger.error(f"Failed to log error to database: {e}")

    def register_fallback(self, error_type: Type[Exception], fallback_fn: Callable):
        """
        Register a fallback function for a specific error type

        Args:
            error_type: Exception class to handle
            fallback_fn: Function to call when this error occurs
        """
        self._fallback_callbacks[error_type] = fallback_fn

    async def get_fallback(self, exception: Exception) -> Optional[Callable]:
        """Get registered fallback function for an exception"""
        for error_type, fallback_fn in self._fallback_callbacks.items():
            if isinstance(exception, error_type):
                return fallback_fn
        return None


# ============================================================================
# Decorators for Error Handling
# ============================================================================

def handle_errors(
    fallback_value: Any = None,
    log_errors: bool = True,
    reraise: bool = False
):
    """
    Decorator to handle errors in async functions

    Args:
        fallback_value: Value to return on error
        log_errors: Whether to log errors
        reraise: Whether to reraise the exception after handling

    Example:
        @handle_errors(fallback_value=[], log_errors=True)
        async def fetch_data():
            # ... code that might fail
            return data
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {e}")
                    logger.debug(traceback.format_exc())

                if reraise:
                    raise

                return fallback_value
        return wrapper
    return decorator


def with_fallback(fallback_fn: Callable):
    """
    Decorator to provide a fallback function if primary function fails

    Args:
        fallback_fn: Function to call if primary fails

    Example:
        @with_fallback(lambda *args, **kwargs: simple_processing(*args, **kwargs))
        async def advanced_processing(data):
            # ... complex processing
            return result
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"{func.__name__} failed, using fallback: {e}")
                return await fallback_fn(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================================
# Singleton Instance
# ============================================================================

_error_handler_instance: Optional[ErrorHandler] = None


def get_error_handler(supabase_storage=None) -> ErrorHandler:
    """Get or create singleton ErrorHandler instance"""
    global _error_handler_instance
    if _error_handler_instance is None:
        _error_handler_instance = ErrorHandler(supabase_storage)
    return _error_handler_instance
