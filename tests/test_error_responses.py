"""
Tests for Standardized Error Responses (US6 - Task 175).

Tests error models, error codes, and exception handling to ensure
all API errors follow the production-standard format.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock
import uuid

from app.models.errors import (
    # ErrorCode enum (FR-028)
    ErrorCode,
    # StandardError and ErrorResponse models (FR-027)
    StandardError,
    ErrorResponse,
    ERROR_CODE_STATUS_MAP,
    get_status_for_error_code,
    # API Exception classes
    APIError,
    ValidationAPIError,
    AuthenticationAPIError,
    AuthorizationAPIError,
    NotFoundAPIError,
    RateLimitedAPIError,
    ExternalServiceAPIError,
    ServiceUnavailableAPIError,
    InternalAPIError,
    # Helper functions
    create_error_response,
    create_validation_error_response,
    create_external_service_error_response,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_request_id():
    """Fixture for a sample request ID."""
    return "123e4567-e89b-12d3-a456-426614174000"


@pytest.fixture
def mock_request():
    """Fixture for a mock FastAPI request."""
    request = MagicMock()
    request.state.request_id = "test-request-id-123"
    request.url.path = "/api/test"
    request.headers = {"X-Request-ID": "test-request-id-123"}
    return request


# =============================================================================
# Test: ErrorCode Enum (FR-028)
# =============================================================================


class TestErrorCodeEnum:
    """Tests for the ErrorCode enum."""

    def test_validation_error_code(self):
        """Test VALIDATION_ERROR code exists."""
        assert ErrorCode.VALIDATION_ERROR == "VALIDATION_ERROR"

    def test_authentication_error_code(self):
        """Test AUTHENTICATION_ERROR code exists."""
        assert ErrorCode.AUTHENTICATION_ERROR == "AUTHENTICATION_ERROR"

    def test_authorization_error_code(self):
        """Test AUTHORIZATION_ERROR code exists."""
        assert ErrorCode.AUTHORIZATION_ERROR == "AUTHORIZATION_ERROR"

    def test_not_found_code(self):
        """Test NOT_FOUND code exists."""
        assert ErrorCode.NOT_FOUND == "NOT_FOUND"

    def test_rate_limited_code(self):
        """Test RATE_LIMITED code exists."""
        assert ErrorCode.RATE_LIMITED == "RATE_LIMITED"

    def test_external_service_error_code(self):
        """Test EXTERNAL_SERVICE_ERROR code exists."""
        assert ErrorCode.EXTERNAL_SERVICE_ERROR == "EXTERNAL_SERVICE_ERROR"

    def test_service_unavailable_code(self):
        """Test SERVICE_UNAVAILABLE code exists."""
        assert ErrorCode.SERVICE_UNAVAILABLE == "SERVICE_UNAVAILABLE"

    def test_internal_error_code(self):
        """Test INTERNAL_ERROR code exists."""
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_ERROR"

    def test_all_eight_error_codes_defined(self):
        """Test that exactly 8 error codes are defined (FR-028)."""
        assert len(ErrorCode) == 8


# =============================================================================
# Test: HTTP Status Code Mapping
# =============================================================================


class TestErrorCodeStatusMapping:
    """Tests for error code to HTTP status code mapping."""

    def test_validation_error_returns_400(self):
        """Test VALIDATION_ERROR returns 400 Bad Request."""
        assert get_status_for_error_code(ErrorCode.VALIDATION_ERROR) == 400

    def test_authentication_error_returns_401(self):
        """Test AUTHENTICATION_ERROR returns 401 Unauthorized."""
        assert get_status_for_error_code(ErrorCode.AUTHENTICATION_ERROR) == 401

    def test_authorization_error_returns_403(self):
        """Test AUTHORIZATION_ERROR returns 403 Forbidden."""
        assert get_status_for_error_code(ErrorCode.AUTHORIZATION_ERROR) == 403

    def test_not_found_returns_404(self):
        """Test NOT_FOUND returns 404 Not Found."""
        assert get_status_for_error_code(ErrorCode.NOT_FOUND) == 404

    def test_rate_limited_returns_429(self):
        """Test RATE_LIMITED returns 429 Too Many Requests."""
        assert get_status_for_error_code(ErrorCode.RATE_LIMITED) == 429

    def test_external_service_error_returns_502(self):
        """Test EXTERNAL_SERVICE_ERROR returns 502 Bad Gateway."""
        assert get_status_for_error_code(ErrorCode.EXTERNAL_SERVICE_ERROR) == 502

    def test_service_unavailable_returns_503(self):
        """Test SERVICE_UNAVAILABLE returns 503 Service Unavailable."""
        assert get_status_for_error_code(ErrorCode.SERVICE_UNAVAILABLE) == 503

    def test_internal_error_returns_500(self):
        """Test INTERNAL_ERROR returns 500 Internal Server Error."""
        assert get_status_for_error_code(ErrorCode.INTERNAL_ERROR) == 500


# =============================================================================
# Test: StandardError Model (FR-027)
# =============================================================================


class TestStandardErrorModel:
    """Tests for the StandardError model."""

    def test_standard_error_creation(self, sample_request_id):
        """Test StandardError can be created with required fields."""
        error = StandardError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Test error message",
            request_id=sample_request_id,
        )
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert error.message == "Test error message"
        assert error.request_id == sample_request_id

    def test_standard_error_has_timestamp(self):
        """Test StandardError includes timestamp by default."""
        error = StandardError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Test error",
        )
        assert error.timestamp is not None
        assert isinstance(error.timestamp, datetime)

    def test_standard_error_details_optional(self):
        """Test StandardError details field is optional."""
        error = StandardError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Test error",
        )
        assert error.details is None

    def test_standard_error_with_details(self):
        """Test StandardError can include details."""
        error = StandardError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid input",
            details={"field": "email", "reason": "Invalid format"},
        )
        assert error.details["field"] == "email"
        assert error.details["reason"] == "Invalid format"

    def test_standard_error_generates_request_id(self):
        """Test StandardError generates request_id if not provided."""
        error = StandardError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Test error",
        )
        assert error.request_id is not None
        # Should be a valid UUID string
        uuid.UUID(error.request_id)


# =============================================================================
# Test: ErrorResponse Wrapper (FR-027)
# =============================================================================


class TestErrorResponseModel:
    """Tests for the ErrorResponse wrapper model."""

    def test_error_response_wraps_standard_error(self):
        """Test ErrorResponse wraps StandardError in 'error' field."""
        standard_error = StandardError(
            code=ErrorCode.NOT_FOUND,
            message="Resource not found",
        )
        response = ErrorResponse(error=standard_error)
        assert response.error.code == ErrorCode.NOT_FOUND
        assert response.error.message == "Resource not found"

    def test_error_response_json_structure(self):
        """Test ErrorResponse produces correct JSON structure."""
        standard_error = StandardError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid input",
            request_id="test-123",
        )
        response = ErrorResponse(error=standard_error)
        json_dict = response.model_dump()

        assert "error" in json_dict
        assert json_dict["error"]["code"] == "VALIDATION_ERROR"
        assert json_dict["error"]["message"] == "Invalid input"
        assert json_dict["error"]["request_id"] == "test-123"


# =============================================================================
# Test: APIError Base Exception
# =============================================================================


class TestAPIError:
    """Tests for the APIError base exception class."""

    def test_api_error_creation(self):
        """Test APIError can be created."""
        error = APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Something went wrong",
        )
        assert error.code == ErrorCode.INTERNAL_ERROR
        assert error.message == "Something went wrong"
        assert error.status_code == 500

    def test_api_error_with_details(self):
        """Test APIError can include details."""
        error = APIError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid input",
            details={"field": "email"},
        )
        assert error.details["field"] == "email"

    def test_api_error_to_response(self, sample_request_id):
        """Test APIError.to_response produces correct format."""
        error = APIError(
            code=ErrorCode.NOT_FOUND,
            message="Resource not found",
            details={"resource_id": "123"},
        )
        response = error.to_response(sample_request_id)

        assert "error" in response
        assert response["error"]["code"] == "NOT_FOUND"
        assert response["error"]["message"] == "Resource not found"
        assert response["error"]["details"]["resource_id"] == "123"
        assert response["error"]["request_id"] == sample_request_id
        assert "timestamp" in response["error"]

    def test_api_error_inherits_from_exception(self):
        """Test APIError inherits from Exception."""
        error = APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Test error",
        )
        assert isinstance(error, Exception)
        assert str(error) == "Test error"


# =============================================================================
# Test: Specific API Exception Classes
# =============================================================================


class TestValidationAPIError:
    """Tests for ValidationAPIError."""

    def test_validation_error_defaults(self):
        """Test ValidationAPIError default values."""
        error = ValidationAPIError()
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert error.status_code == 400
        assert "Invalid input" in error.message

    def test_validation_error_custom_message(self):
        """Test ValidationAPIError with custom message."""
        error = ValidationAPIError(message="Email format invalid")
        assert error.message == "Email format invalid"

    def test_validation_error_with_details(self):
        """Test ValidationAPIError with field details."""
        error = ValidationAPIError(
            message="Validation failed",
            details={"email": "Invalid format", "name": "Required"},
        )
        assert error.details["email"] == "Invalid format"


class TestAuthenticationAPIError:
    """Tests for AuthenticationAPIError."""

    def test_authentication_error_defaults(self):
        """Test AuthenticationAPIError default values."""
        error = AuthenticationAPIError()
        assert error.code == ErrorCode.AUTHENTICATION_ERROR
        assert error.status_code == 401

    def test_authentication_error_custom_message(self):
        """Test AuthenticationAPIError with custom message."""
        error = AuthenticationAPIError(message="Token expired")
        assert error.message == "Token expired"


class TestAuthorizationAPIError:
    """Tests for AuthorizationAPIError."""

    def test_authorization_error_defaults(self):
        """Test AuthorizationAPIError default values."""
        error = AuthorizationAPIError()
        assert error.code == ErrorCode.AUTHORIZATION_ERROR
        assert error.status_code == 403


class TestNotFoundAPIError:
    """Tests for NotFoundAPIError."""

    def test_not_found_error_defaults(self):
        """Test NotFoundAPIError default values."""
        error = NotFoundAPIError()
        assert error.code == ErrorCode.NOT_FOUND
        assert error.status_code == 404

    def test_not_found_error_with_resource_details(self):
        """Test NotFoundAPIError with resource details."""
        error = NotFoundAPIError(
            message="Document not found",
            details={"document_id": "doc-123"},
        )
        assert error.details["document_id"] == "doc-123"


class TestRateLimitedAPIError:
    """Tests for RateLimitedAPIError."""

    def test_rate_limited_error_defaults(self):
        """Test RateLimitedAPIError default values."""
        error = RateLimitedAPIError()
        assert error.code == ErrorCode.RATE_LIMITED
        assert error.status_code == 429

    def test_rate_limited_error_with_retry_after(self):
        """Test RateLimitedAPIError includes retry_after in details."""
        error = RateLimitedAPIError(retry_after=60)
        assert error.retry_after == 60
        assert error.details["retry_after"] == 60


class TestExternalServiceAPIError:
    """Tests for ExternalServiceAPIError."""

    def test_external_service_error_defaults(self):
        """Test ExternalServiceAPIError default values."""
        error = ExternalServiceAPIError()
        assert error.code == ErrorCode.EXTERNAL_SERVICE_ERROR
        assert error.status_code == 502

    def test_external_service_error_with_service_name(self):
        """Test ExternalServiceAPIError with service name."""
        error = ExternalServiceAPIError(service_name="LlamaIndex")
        assert "LlamaIndex" in error.message
        assert error.details["service"] == "LlamaIndex"


class TestServiceUnavailableAPIError:
    """Tests for ServiceUnavailableAPIError."""

    def test_service_unavailable_error_defaults(self):
        """Test ServiceUnavailableAPIError default values."""
        error = ServiceUnavailableAPIError()
        assert error.code == ErrorCode.SERVICE_UNAVAILABLE
        assert error.status_code == 503


class TestInternalAPIError:
    """Tests for InternalAPIError."""

    def test_internal_error_defaults(self):
        """Test InternalAPIError default values."""
        error = InternalAPIError()
        assert error.code == ErrorCode.INTERNAL_ERROR
        assert error.status_code == 500


# =============================================================================
# Test: Error Response Helper Functions
# =============================================================================


class TestCreateErrorResponse:
    """Tests for create_error_response helper function."""

    def test_create_error_response_basic(self, sample_request_id):
        """Test create_error_response creates correct structure."""
        response = create_error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message="Test error",
            request_id=sample_request_id,
        )

        assert "error" in response
        assert response["error"]["code"] == "VALIDATION_ERROR"
        assert response["error"]["message"] == "Test error"
        assert response["error"]["request_id"] == sample_request_id

    def test_create_error_response_with_details(self):
        """Test create_error_response with details."""
        response = create_error_response(
            code=ErrorCode.NOT_FOUND,
            message="Resource not found",
            details={"resource_type": "document", "id": "123"},
        )

        assert response["error"]["details"]["resource_type"] == "document"
        assert response["error"]["details"]["id"] == "123"

    def test_create_error_response_generates_request_id(self):
        """Test create_error_response generates request_id if not provided."""
        response = create_error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message="Test error",
        )

        assert response["error"]["request_id"] is not None
        # Should be a valid UUID
        uuid.UUID(response["error"]["request_id"])

    def test_create_error_response_includes_timestamp(self):
        """Test create_error_response includes timestamp."""
        response = create_error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message="Test error",
        )

        assert "timestamp" in response["error"]


class TestCreateValidationErrorResponse:
    """Tests for create_validation_error_response helper function."""

    def test_create_validation_error_response_basic(self):
        """Test create_validation_error_response creates correct structure."""
        response = create_validation_error_response(
            message="Validation failed",
        )

        assert response["error"]["code"] == "VALIDATION_ERROR"
        assert response["error"]["message"] == "Validation failed"

    def test_create_validation_error_response_with_fields(self):
        """Test create_validation_error_response with field errors."""
        response = create_validation_error_response(
            message="Validation failed",
            field_errors={"email": "Invalid format", "name": "Required"},
        )

        assert response["error"]["details"]["fields"]["email"] == "Invalid format"
        assert response["error"]["details"]["fields"]["name"] == "Required"


class TestCreateExternalServiceErrorResponse:
    """Tests for create_external_service_error_response helper function."""

    def test_create_external_service_error_response_basic(self):
        """Test create_external_service_error_response creates correct structure."""
        response = create_external_service_error_response(
            service_name="LlamaIndex",
            reason="timeout",
        )

        assert response["error"]["code"] == "EXTERNAL_SERVICE_ERROR"
        assert "LlamaIndex" in response["error"]["message"]
        assert response["error"]["details"]["service"] == "LlamaIndex"
        assert response["error"]["details"]["reason"] == "timeout"

    def test_create_external_service_error_response_with_timeout(self):
        """Test create_external_service_error_response with timeout value."""
        response = create_external_service_error_response(
            service_name="CrewAI",
            reason="timeout",
            timeout_seconds=120.0,
        )

        assert response["error"]["details"]["timeout_seconds"] == 120.0


# =============================================================================
# Test: Error Response Format Compliance (FR-027)
# =============================================================================


class TestErrorResponseFormatCompliance:
    """Tests ensuring error responses comply with FR-027 format requirements."""

    def test_response_has_error_wrapper(self):
        """Test all error responses have 'error' wrapper."""
        error = APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Test",
        )
        response = error.to_response()
        assert "error" in response

    def test_response_has_required_code_field(self):
        """Test error response has required 'code' field."""
        error = ValidationAPIError()
        response = error.to_response()
        assert "code" in response["error"]
        assert response["error"]["code"] == "VALIDATION_ERROR"

    def test_response_has_required_message_field(self):
        """Test error response has required 'message' field."""
        error = ValidationAPIError(message="Test message")
        response = error.to_response()
        assert "message" in response["error"]
        assert response["error"]["message"] == "Test message"

    def test_response_has_required_request_id_field(self):
        """Test error response has required 'request_id' field."""
        error = ValidationAPIError()
        response = error.to_response("test-123")
        assert "request_id" in response["error"]
        assert response["error"]["request_id"] == "test-123"

    def test_response_has_required_timestamp_field(self):
        """Test error response has required 'timestamp' field."""
        error = ValidationAPIError()
        response = error.to_response()
        assert "timestamp" in response["error"]

    def test_timestamp_is_iso_format(self):
        """Test timestamp is in ISO 8601 format."""
        error = ValidationAPIError()
        response = error.to_response()
        timestamp = response["error"]["timestamp"]

        # Should be parseable as ISO format
        assert "T" in timestamp
        # Should include timezone indicator
        assert timestamp.endswith("Z") or "+" in timestamp


# =============================================================================
# Test: Error Code Consistency (FR-028)
# =============================================================================


class TestErrorCodeConsistency:
    """Tests ensuring error codes are used consistently."""

    def test_validation_error_uses_validation_error_code(self):
        """Test validation errors use VALIDATION_ERROR code."""
        error = ValidationAPIError()
        assert error.code == ErrorCode.VALIDATION_ERROR

    def test_auth_error_uses_authentication_error_code(self):
        """Test authentication errors use AUTHENTICATION_ERROR code."""
        error = AuthenticationAPIError()
        assert error.code == ErrorCode.AUTHENTICATION_ERROR

    def test_authz_error_uses_authorization_error_code(self):
        """Test authorization errors use AUTHORIZATION_ERROR code."""
        error = AuthorizationAPIError()
        assert error.code == ErrorCode.AUTHORIZATION_ERROR

    def test_not_found_uses_not_found_code(self):
        """Test not found errors use NOT_FOUND code."""
        error = NotFoundAPIError()
        assert error.code == ErrorCode.NOT_FOUND

    def test_rate_limit_uses_rate_limited_code(self):
        """Test rate limit errors use RATE_LIMITED code."""
        error = RateLimitedAPIError()
        assert error.code == ErrorCode.RATE_LIMITED

    def test_external_service_uses_external_service_error_code(self):
        """Test external service errors use EXTERNAL_SERVICE_ERROR code."""
        error = ExternalServiceAPIError()
        assert error.code == ErrorCode.EXTERNAL_SERVICE_ERROR

    def test_service_unavailable_uses_service_unavailable_code(self):
        """Test service unavailable errors use SERVICE_UNAVAILABLE code."""
        error = ServiceUnavailableAPIError()
        assert error.code == ErrorCode.SERVICE_UNAVAILABLE

    def test_internal_error_uses_internal_error_code(self):
        """Test internal errors use INTERNAL_ERROR code."""
        error = InternalAPIError()
        assert error.code == ErrorCode.INTERNAL_ERROR


# =============================================================================
# Test: Request ID Propagation
# =============================================================================


class TestRequestIdPropagation:
    """Tests for request ID propagation in error responses."""

    def test_request_id_propagated_to_response(self, sample_request_id):
        """Test request ID is propagated to error response."""
        error = ValidationAPIError()
        response = error.to_response(sample_request_id)
        assert response["error"]["request_id"] == sample_request_id

    def test_request_id_generated_if_not_provided(self):
        """Test request ID is generated if not provided."""
        error = ValidationAPIError()
        response = error.to_response()
        assert response["error"]["request_id"] is not None
        # Should be valid UUID
        uuid.UUID(response["error"]["request_id"])

    def test_create_error_response_propagates_request_id(self, sample_request_id):
        """Test create_error_response propagates request ID."""
        response = create_error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message="Test",
            request_id=sample_request_id,
        )
        assert response["error"]["request_id"] == sample_request_id
