"""
Empire v7.3 - Celery Retry Utilities
Utilities for Celery task retry logic with intelligent error handling
"""

from typing import Callable, Tuple, Optional, Type
from functools import wraps
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Retry Configuration
# ============================================================================

# Transient errors that should always be retried
TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    # Add more as needed
)

# Rate limit/throttling errors
RATE_LIMIT_EXCEPTIONS = (
    # TooManyRequestsError, (if available)
)

# Permanent errors that should never be retried
PERMANENT_EXCEPTIONS = (
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
    # Add more as needed
)


# Default retry configurations by error category
DEFAULT_RETRY_CONFIG = {
    "network": {
        "max_retries": 3,
        "countdown": 60,  # Base countdown in seconds
        "backoff": 2,     # Exponential backoff multiplier
    },
    "service_unavailable": {
        "max_retries": 5,
        "countdown": 120,
        "backoff": 2,
    },
    "database": {
        "max_retries": 3,
        "countdown": 30,
        "backoff": 1.5,
    },
    "timeout": {
        "max_retries": 3,
        "countdown": 90,
        "backoff": 2,
    },
    "storage": {
        "max_retries": 3,
        "countdown": 60,
        "backoff": 2,
    },
    "default": {
        "max_retries": 3,
        "countdown": 60,
        "backoff": 2,
    }
}


# ============================================================================
# Retry Helpers
# ============================================================================

def calculate_retry_countdown(
    retry_count: int,
    base_countdown: int = 60,
    backoff: float = 2.0,
    max_countdown: int = 3600
) -> int:
    """
    Calculate exponential backoff countdown

    Args:
        retry_count: Current retry attempt (0-indexed)
        base_countdown: Base delay in seconds
        backoff: Backoff multiplier
        max_countdown: Maximum countdown in seconds

    Returns:
        Countdown in seconds
    """
    countdown = int(base_countdown * (backoff ** retry_count))
    return min(countdown, max_countdown)


def should_retry_error(exc: Exception) -> bool:
    """
    Determine if an error should be retried

    Args:
        exc: The exception to check

    Returns:
        True if error should be retried
    """
    # Never retry permanent errors
    if isinstance(exc, PERMANENT_EXCEPTIONS):
        return False

    # Always retry transient errors
    if isinstance(exc, TRANSIENT_EXCEPTIONS):
        return True

    # Check error message for common transient patterns
    error_message = str(exc).lower()
    transient_patterns = [
        "timeout",
        "connection",
        "temporarily unavailable",
        "service unavailable",
        "502",
        "503",
        "504",
    ]

    return any(pattern in error_message for pattern in transient_patterns)


def get_retry_config(category: str) -> dict:
    """Get retry configuration for a category"""
    return DEFAULT_RETRY_CONFIG.get(category, DEFAULT_RETRY_CONFIG["default"])


# ============================================================================
# Task Decorator for Enhanced Retry
# ============================================================================

def task_with_retry(
    autoretry_for: Tuple[Type[Exception], ...] = TRANSIENT_EXCEPTIONS,
    max_retries: int = 3,
    retry_backoff: int = 60,
    retry_backoff_max: int = 3600,
    retry_jitter: bool = True,
    **task_kwargs
):
    """
    Enhanced Celery task decorator with intelligent retry

    Args:
        autoretry_for: Tuple of exceptions to auto-retry
        max_retries: Maximum number of retries
        retry_backoff: Base backoff time in seconds
        retry_backoff_max: Maximum backoff time
        retry_jitter: Add jitter to backoff
        **task_kwargs: Additional Celery task keyword arguments

    Example:
        from app.celery_app import celery_app
        from app.utils.celery_retry import task_with_retry

        @celery_app.task(**task_with_retry(max_retries=5))
        def my_task():
            # Task code here
            pass
    """
    return {
        "bind": True,
        "autoretry_for": autoretry_for,
        "max_retries": max_retries,
        "retry_backoff": retry_backoff,
        "retry_backoff_max": retry_backoff_max,
        "retry_jitter": retry_jitter,
        **task_kwargs
    }


# ============================================================================
# Manual Retry Helper for Complex Logic
# ============================================================================

class RetryContext:
    """Context manager for manual retry logic"""

    def __init__(
        self,
        task,
        max_retries: int = 3,
        base_countdown: int = 60,
        backoff: float = 2.0
    ):
        """
        Initialize retry context

        Args:
            task: Celery task instance (self from bind=True)
            max_retries: Maximum retry attempts
            base_countdown: Base countdown in seconds
            backoff: Backoff multiplier
        """
        self.task = task
        self.max_retries = max_retries
        self.base_countdown = base_countdown
        self.backoff = backoff
        self.retry_count = getattr(task.request, 'retries', 0)

    def should_retry(self, exc: Exception) -> bool:
        """Check if we should retry"""
        return self.retry_count < self.max_retries and should_retry_error(exc)

    def get_countdown(self) -> int:
        """Get countdown for next retry"""
        return calculate_retry_countdown(
            self.retry_count,
            self.base_countdown,
            self.backoff
        )

    def retry(self, exc: Exception):
        """Retry the task"""
        countdown = self.get_countdown()
        logger.info(
            f"Retrying {self.task.name} (attempt {self.retry_count + 1}/{self.max_retries}) "
            f"in {countdown}s due to: {exc}"
        )
        self.task.retry(exc=exc, countdown=countdown, max_retries=self.max_retries)


# ============================================================================
# Graceful Degradation Decorator
# ============================================================================

def with_graceful_degradation(fallback_fn: Optional[Callable] = None):
    """
    Decorator to enable graceful degradation for task functions

    Args:
        fallback_fn: Optional fallback function to call if primary fails

    Example:
        def simple_processing(file_id, filename):
            return {"status": "partial", "method": "simple"}

        @with_graceful_degradation(fallback_fn=simple_processing)
        def advanced_processing(file_id, filename):
            # Complex processing
            return {"status": "complete", "method": "advanced"}
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"{func.__name__} failed, attempting graceful degradation: {e}")

                if fallback_fn:
                    try:
                        logger.info(f"Using fallback function for {func.__name__}")
                        return fallback_fn(*args, **kwargs)
                    except Exception as fallback_error:
                        logger.error(f"Fallback also failed: {fallback_error}")
                        raise

                # No fallback available, reraise
                raise
        return wrapper
    return decorator
