"""
Empire v7.3 - Client Error Exceptions (4xx)
Task 154: Standardized Exception Handling Framework

Provides exception classes for client-side errors (HTTP 4xx).
"""

from typing import Optional, Dict, Any, List
from .base import BaseAppException


# =============================================================================
# 400 BAD REQUEST EXCEPTIONS
# =============================================================================

class BadRequestException(BaseAppException):
    """
    Exception for invalid request data (400).

    Raised when the client sends invalid or malformed data.
    """

    def __init__(
        self,
        message: str = "Bad request",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "BAD_REQUEST"
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=400,
            details=details,
            severity="warning",
            retriable=False
        )


class ValidationException(BaseAppException):
    """
    Exception for request validation failures (400).

    Raised when input validation fails. Supports multiple validation errors.
    """

    def __init__(
        self,
        message: str = "Validation failed",
        validation_errors: Optional[List[Dict[str, Any]]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if validation_errors:
            details["validation_errors"] = validation_errors
            details["error_count"] = len(validation_errors)

        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details,
            severity="warning",
            retriable=False
        )
        self.validation_errors = validation_errors or []


class InvalidFormatException(BaseAppException):
    """
    Exception for invalid data format (400).

    Raised when data is in an incorrect format.
    """

    def __init__(
        self,
        message: str = "Invalid format",
        expected_format: Optional[str] = None,
        received_format: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if expected_format:
            details["expected_format"] = expected_format
        if received_format:
            details["received_format"] = received_format

        super().__init__(
            message=message,
            error_code="INVALID_FORMAT",
            status_code=400,
            details=details,
            severity="warning",
            retriable=False
        )


class MissingFieldException(BaseAppException):
    """
    Exception for missing required fields (400).

    Raised when required request fields are missing.
    """

    def __init__(
        self,
        field_name: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        details["field"] = field_name

        super().__init__(
            message=message or f"Missing required field: {field_name}",
            error_code="MISSING_REQUIRED_FIELD",
            status_code=400,
            details=details,
            severity="warning",
            retriable=False
        )


# =============================================================================
# 401 UNAUTHORIZED EXCEPTIONS
# =============================================================================

class UnauthorizedException(BaseAppException):
    """
    Exception for authentication failures (401).

    Raised when authentication is required but not provided or invalid.
    """

    def __init__(
        self,
        message: str = "Authentication required",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "UNAUTHORIZED"
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=401,
            details=details,
            severity="warning",
            retriable=False
        )


class InvalidTokenException(UnauthorizedException):
    """Exception for invalid authentication tokens (401)."""

    def __init__(
        self,
        message: str = "Invalid authentication token",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details,
            error_code="INVALID_TOKEN"
        )


class TokenExpiredException(UnauthorizedException):
    """Exception for expired authentication tokens (401)."""

    def __init__(
        self,
        message: str = "Authentication token has expired",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details,
            error_code="TOKEN_EXPIRED"
        )


class MissingAuthException(UnauthorizedException):
    """Exception for missing authentication (401)."""

    def __init__(
        self,
        message: str = "Authentication header required",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details,
            error_code="MISSING_AUTH_HEADER"
        )


# =============================================================================
# 403 FORBIDDEN EXCEPTIONS
# =============================================================================

class ForbiddenException(BaseAppException):
    """
    Exception for authorization failures (403).

    Raised when the user is authenticated but lacks permission.
    """

    def __init__(
        self,
        message: str = "Access forbidden",
        required_permission: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "FORBIDDEN"
    ):
        details = details or {}
        if required_permission:
            details["required_permission"] = required_permission

        super().__init__(
            message=message,
            error_code=error_code,
            status_code=403,
            details=details,
            severity="warning",
            retriable=False
        )


class InsufficientPermissionsException(ForbiddenException):
    """Exception for insufficient permissions (403)."""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        required_role: Optional[str] = None,
        user_roles: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if required_role:
            details["required_role"] = required_role
        if user_roles:
            details["user_roles"] = user_roles

        super().__init__(
            message=message,
            details=details,
            error_code="INSUFFICIENT_PERMISSIONS"
        )


class AccessDeniedException(ForbiddenException):
    """Exception for access denial to specific resources (403)."""

    def __init__(
        self,
        message: str = "Access denied to this resource",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id

        super().__init__(
            message=message,
            details=details,
            error_code="ACCESS_DENIED"
        )


# =============================================================================
# 404 NOT FOUND EXCEPTIONS
# =============================================================================

class NotFoundException(BaseAppException):
    """
    Exception for resource not found (404).

    Raised when a requested resource does not exist.
    """

    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id

        # Generate specific error code if resource type is provided
        error_code = f"{resource_type.upper()}_NOT_FOUND" if resource_type else "RESOURCE_NOT_FOUND"

        super().__init__(
            message=message,
            error_code=error_code,
            status_code=404,
            details=details,
            severity="warning",
            retriable=False
        )


class DocumentNotFoundException(NotFoundException):
    """Exception for document not found (404)."""

    def __init__(self, document_id: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Document not found: {document_id}",
            resource_type="document",
            resource_id=document_id,
            details=details
        )


class UserNotFoundException(NotFoundException):
    """Exception for user not found (404)."""

    def __init__(self, user_id: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"User not found: {user_id}",
            resource_type="user",
            resource_id=user_id,
            details=details
        )


class ProjectNotFoundException(NotFoundException):
    """Exception for project not found (404)."""

    def __init__(self, project_id: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Project not found: {project_id}",
            resource_type="project",
            resource_id=project_id,
            details=details
        )


# =============================================================================
# 409 CONFLICT EXCEPTIONS
# =============================================================================

class ConflictException(BaseAppException):
    """
    Exception for resource conflicts (409).

    Raised when the request conflicts with the current state.
    """

    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "CONFLICT"
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=409,
            details=details,
            severity="warning",
            retriable=False
        )


class DuplicateResourceException(ConflictException):
    """Exception for duplicate resources (409)."""

    def __init__(
        self,
        message: str = "Resource already exists",
        resource_type: Optional[str] = None,
        identifier: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if resource_type:
            details["resource_type"] = resource_type
        if identifier:
            details["identifier"] = identifier

        super().__init__(
            message=message,
            details=details,
            error_code="DUPLICATE_RESOURCE"
        )


class StateConflictException(ConflictException):
    """Exception for state conflicts (409)."""

    def __init__(
        self,
        message: str = "State conflict",
        current_state: Optional[str] = None,
        expected_state: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if current_state:
            details["current_state"] = current_state
        if expected_state:
            details["expected_state"] = expected_state

        super().__init__(
            message=message,
            details=details,
            error_code="STATE_CONFLICT"
        )


# =============================================================================
# 422 UNPROCESSABLE ENTITY EXCEPTIONS
# =============================================================================

class UnprocessableEntityException(BaseAppException):
    """
    Exception for unprocessable content (422).

    Raised when the request is syntactically correct but semantically wrong.
    """

    def __init__(
        self,
        message: str = "Unprocessable entity",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "UNPROCESSABLE_ENTITY"
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=422,
            details=details,
            severity="warning",
            retriable=False
        )


class BusinessRuleViolationException(UnprocessableEntityException):
    """Exception for business rule violations (422)."""

    def __init__(
        self,
        message: str = "Business rule violation",
        rule: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if rule:
            details["violated_rule"] = rule

        super().__init__(
            message=message,
            details=details,
            error_code="BUSINESS_RULE_VIOLATION"
        )


# =============================================================================
# 429 TOO MANY REQUESTS EXCEPTIONS
# =============================================================================

class RateLimitException(BaseAppException):
    """
    Exception for rate limit exceeded (429).

    Raised when the client has exceeded their rate limit.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        remaining: int = 0,
        reset_seconds: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if limit is not None:
            details["limit"] = limit
        details["remaining"] = remaining
        if reset_seconds is not None:
            details["reset_seconds"] = reset_seconds

        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details,
            severity="warning",
            retriable=True,
            retry_after=reset_seconds or 60
        )


class QuotaExceededException(BaseAppException):
    """
    Exception for quota exceeded (429).

    Raised when a resource quota has been exceeded.
    """

    def __init__(
        self,
        message: str = "Quota exceeded",
        quota_type: Optional[str] = None,
        limit: Optional[int] = None,
        used: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if quota_type:
            details["quota_type"] = quota_type
        if limit is not None:
            details["limit"] = limit
        if used is not None:
            details["used"] = used

        super().__init__(
            message=message,
            error_code="QUOTA_EXCEEDED",
            status_code=429,
            details=details,
            severity="warning",
            retriable=False
        )
