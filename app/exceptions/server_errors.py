"""
Empire v7.3 - Server Error Exceptions (5xx)
Task 154: Standardized Exception Handling Framework

Provides exception classes for server-side errors (HTTP 5xx).
"""

from typing import Optional, Dict, Any
from .base import BaseAppException


# =============================================================================
# 500 INTERNAL SERVER ERROR EXCEPTIONS
# =============================================================================

class InternalServerException(BaseAppException):
    """
    Base exception for internal server errors (500).

    Raised when an unexpected server error occurs.
    """

    def __init__(
        self,
        message: str = "Internal server error",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "INTERNAL_SERVER_ERROR"
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=500,
            details=details,
            severity="error",
            retriable=True
        )


class DatabaseException(InternalServerException):
    """
    Exception for database-related errors (500).

    Raised when a database operation fails.
    """

    def __init__(
        self,
        message: str = "Database error",
        database: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if database:
            details["database"] = database
        if operation:
            details["operation"] = operation

        super().__init__(
            message=message,
            details=details,
            error_code="DATABASE_ERROR"
        )


class Neo4jException(DatabaseException):
    """Exception for Neo4j graph database errors (500)."""

    def __init__(
        self,
        message: str = "Neo4j database error",
        operation: Optional[str] = None,
        query: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if query:
            details["query"] = query[:200]  # Truncate long queries

        super().__init__(
            message=message,
            database="neo4j",
            operation=operation,
            details=details
        )
        self.error_code = "NEO4J_ERROR"


class SupabaseException(DatabaseException):
    """Exception for Supabase/PostgreSQL errors (500)."""

    def __init__(
        self,
        message: str = "Supabase database error",
        operation: Optional[str] = None,
        table: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if table:
            details["table"] = table

        super().__init__(
            message=message,
            database="supabase",
            operation=operation,
            details=details
        )
        self.error_code = "SUPABASE_ERROR"


class RedisException(DatabaseException):
    """Exception for Redis errors (500)."""

    def __init__(
        self,
        message: str = "Redis error",
        operation: Optional[str] = None,
        key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if key:
            details["key"] = key

        super().__init__(
            message=message,
            database="redis",
            operation=operation,
            details=details
        )
        self.error_code = "REDIS_ERROR"
        # Redis errors are usually retriable
        self.retriable = True
        self.retry_after = 5


class StorageException(InternalServerException):
    """
    Exception for storage-related errors (500).

    Raised when file storage operations fail.
    """

    def __init__(
        self,
        message: str = "Storage error",
        storage_provider: Optional[str] = None,
        operation: Optional[str] = None,
        file_path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if storage_provider:
            details["storage_provider"] = storage_provider
        if operation:
            details["operation"] = operation
        if file_path:
            details["file_path"] = file_path

        super().__init__(
            message=message,
            details=details,
            error_code=f"{storage_provider.upper()}_STORAGE_ERROR" if storage_provider else "STORAGE_ERROR"
        )


class B2StorageException(StorageException):
    """Exception for Backblaze B2 storage errors (500)."""

    def __init__(
        self,
        message: str = "B2 storage error",
        operation: Optional[str] = None,
        file_path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            storage_provider="b2",
            operation=operation,
            file_path=file_path,
            details=details
        )


class FileUploadException(StorageException):
    """Exception for file upload failures (500)."""

    def __init__(
        self,
        message: str = "File upload failed",
        filename: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if filename:
            details["filename"] = filename

        super().__init__(
            message=message,
            operation="upload",
            details=details
        )
        self.error_code = "FILE_UPLOAD_FAILED"


class FileDownloadException(StorageException):
    """Exception for file download failures (500)."""

    def __init__(
        self,
        message: str = "File download failed",
        file_path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            operation="download",
            file_path=file_path,
            details=details
        )
        self.error_code = "FILE_DOWNLOAD_FAILED"


class ChecksumMismatchException(StorageException):
    """
    Exception for checksum verification failures (500).
    Task 157: B2 Storage Error Handling

    Raised when uploaded/downloaded file checksum doesn't match expected value.
    """

    def __init__(
        self,
        message: str = "Checksum verification failed",
        file_path: Optional[str] = None,
        expected_checksum: Optional[str] = None,
        actual_checksum: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if expected_checksum:
            details["expected_checksum"] = expected_checksum
        if actual_checksum:
            details["actual_checksum"] = actual_checksum

        super().__init__(
            message=message,
            operation="checksum_verification",
            file_path=file_path,
            details=details
        )
        self.error_code = "CHECKSUM_MISMATCH"
        self.retriable = False  # Data integrity issue, don't retry same file


class DeadLetterQueueException(StorageException):
    """
    Exception for dead letter queue operations (500).
    Task 157: B2 Storage Error Handling

    Raised when dead letter queue operations fail.
    """

    def __init__(
        self,
        message: str = "Dead letter queue operation failed",
        operation_type: Optional[str] = None,
        queue_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if operation_type:
            details["dlq_operation"] = operation_type
        if queue_name:
            details["queue_name"] = queue_name

        super().__init__(
            message=message,
            operation="dead_letter_queue",
            details=details
        )
        self.error_code = "DEAD_LETTER_QUEUE_ERROR"


class B2RetryExhaustedException(B2StorageException):
    """
    Exception when all retry attempts for B2 operation are exhausted (500).
    Task 157: B2 Storage Error Handling
    """

    def __init__(
        self,
        message: str = "B2 operation failed after all retry attempts",
        operation: Optional[str] = None,
        file_path: Optional[str] = None,
        retry_count: int = 0,
        last_error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        details["retry_count"] = retry_count
        if last_error:
            details["last_error"] = last_error

        super().__init__(
            message=message,
            operation=operation,
            file_path=file_path,
            details=details
        )
        self.error_code = "B2_RETRY_EXHAUSTED"
        self.retriable = False  # Already exhausted retries


# =============================================================================
# 502 BAD GATEWAY EXCEPTIONS
# =============================================================================

class BadGatewayException(BaseAppException):
    """
    Base exception for upstream/external service errors (502).

    Raised when an external service returns an error.
    """

    def __init__(
        self,
        message: str = "External service error",
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "BAD_GATEWAY"
    ):
        details = details or {}
        if service_name:
            details["service_name"] = service_name

        super().__init__(
            message=message,
            error_code=error_code,
            status_code=502,
            details=details,
            severity="error",
            retriable=True,
            retry_after=30
        )


class ExternalAPIException(BadGatewayException):
    """Exception for external API errors (502)."""

    def __init__(
        self,
        message: str = "External API error",
        service_name: Optional[str] = None,
        api_response: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if api_response:
            details["api_response"] = api_response

        super().__init__(
            message=message,
            service_name=service_name,
            details=details,
            error_code="EXTERNAL_API_ERROR"
        )


class AnthropicAPIException(ExternalAPIException):
    """Exception for Anthropic Claude API errors (502)."""

    def __init__(
        self,
        message: str = "Anthropic API error",
        api_response: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            service_name="anthropic",
            api_response=api_response,
            details=details
        )
        self.error_code = "ANTHROPIC_API_ERROR"


class LlamaParseException(ExternalAPIException):
    """Exception for LlamaParse API errors (502)."""

    def __init__(
        self,
        message: str = "LlamaParse API error",
        api_response: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            service_name="llamaparse",
            api_response=api_response,
            details=details
        )
        self.error_code = "LLAMAPARSE_ERROR"


# =============================================================================
# 503 SERVICE UNAVAILABLE EXCEPTIONS
# =============================================================================

class ServiceUnavailableException(BaseAppException):
    """
    Base exception for service unavailable errors (503).

    Raised when a service is temporarily unavailable.
    """

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        service_name: Optional[str] = None,
        estimated_recovery: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "SERVICE_UNAVAILABLE"
    ):
        details = details or {}
        if service_name:
            details["service_name"] = service_name
        if estimated_recovery:
            details["estimated_recovery_seconds"] = estimated_recovery

        super().__init__(
            message=message,
            error_code=error_code,
            status_code=503,
            details=details,
            severity="warning",
            retriable=True,
            retry_after=estimated_recovery or 60
        )


class MaintenanceModeException(ServiceUnavailableException):
    """Exception for maintenance mode (503)."""

    def __init__(
        self,
        message: str = "Service is under maintenance",
        estimated_recovery: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            estimated_recovery=estimated_recovery,
            details=details,
            error_code="MAINTENANCE_MODE"
        )


class CircuitBreakerOpenException(ServiceUnavailableException):
    """Exception for circuit breaker open state (503)."""

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        service_name: Optional[str] = None,
        reset_time: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            service_name=service_name,
            estimated_recovery=reset_time,
            details=details,
            error_code="CIRCUIT_BREAKER_OPEN"
        )


# =============================================================================
# 504 GATEWAY TIMEOUT EXCEPTIONS
# =============================================================================

class GatewayTimeoutException(BaseAppException):
    """
    Base exception for timeout errors (504).

    Raised when an operation times out.
    """

    def __init__(
        self,
        message: str = "Operation timed out",
        timeout_seconds: Optional[float] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "GATEWAY_TIMEOUT"
    ):
        details = details or {}
        if timeout_seconds is not None:
            details["timeout_seconds"] = timeout_seconds
        if operation:
            details["operation"] = operation

        super().__init__(
            message=message,
            error_code=error_code,
            status_code=504,
            details=details,
            severity="warning",
            retriable=True,
            retry_after=30
        )


class OperationTimeoutException(GatewayTimeoutException):
    """Exception for general operation timeouts (504)."""

    def __init__(
        self,
        message: str = "Operation timed out",
        operation: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            timeout_seconds=timeout_seconds,
            operation=operation,
            details=details,
            error_code="OPERATION_TIMEOUT"
        )
