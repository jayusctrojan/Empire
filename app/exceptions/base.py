"""
Empire v7.3 - Base Exception Classes
Task 154: Standardized Exception Handling Framework

Provides the base exception class that all application exceptions inherit from.
"""

from typing import Optional, Dict, Any
from datetime import datetime


class BaseAppException(Exception):
    """
    Base exception class for all application exceptions.

    This class provides a standardized structure for exceptions including:
    - Human-readable message
    - Machine-readable error code
    - HTTP status code mapping
    - Additional details/context
    - Severity level for logging
    - Retry information for retriable errors

    All custom exceptions should inherit from this class.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "error",
        retriable: bool = False,
        retry_after: Optional[int] = None,
    ):
        """
        Initialize the base exception.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code (e.g., "VALIDATION_ERROR")
            status_code: HTTP status code to return
            details: Additional context about the error
            severity: Logging severity level (debug, info, warning, error, critical)
            retriable: Whether the client should retry the request
            retry_after: Suggested seconds to wait before retry (for retriable errors)
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.severity = severity
        self.retriable = retriable
        self.retry_after = retry_after
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to a dictionary for JSON serialization.

        Returns:
            Dictionary representation of the exception
        """
        result = {
            "error_code": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "retriable": self.retriable,
            "timestamp": self.timestamp.isoformat(),
        }

        if self.details:
            result["details"] = self.details

        if self.retry_after is not None:
            result["retry_after"] = self.retry_after

        return result

    def __str__(self) -> str:
        """String representation of the exception."""
        return f"{self.error_code}: {self.message}"

    def __repr__(self) -> str:
        """Debug representation of the exception."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}, "
            f"status_code={self.status_code}, "
            f"details={self.details!r})"
        )


class ConfigurationError(BaseAppException):
    """
    Exception for configuration-related errors.

    Raised when the application is misconfigured or required
    configuration values are missing.
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if config_key:
            details["config_key"] = config_key

        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            status_code=500,
            details=details,
            severity="critical",
            retriable=False,
        )


class InitializationError(BaseAppException):
    """
    Exception for initialization failures.

    Raised when a component fails to initialize properly.
    """

    def __init__(
        self,
        message: str,
        component: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if component:
            details["component"] = component

        super().__init__(
            message=message,
            error_code="INITIALIZATION_ERROR",
            status_code=500,
            details=details,
            severity="critical",
            retriable=False,
        )
