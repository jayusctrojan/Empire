"""
Empire v7.3 - Error Handling Tests
Task 135: Implement Standardized Error Response Model and Handling

Comprehensive tests for the standardized error response system:
- Error response models
- Error codes and mappings
- Error handler middleware
- Custom exceptions
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import uuid

from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.models.errors import (
    ErrorType,
    ErrorSeverity,
    AgentErrorResponse,
    ValidationErrorResponse,
    ValidationErrorDetail,
    RateLimitErrorResponse,
    ServiceUnavailableResponse,
    create_agent_error,
    create_validation_error,
)
from app.constants.error_codes import (
    VALIDATION_ERROR,
    INTERNAL_SERVER_ERROR,
    AGENT_PROCESSING_ERROR,
    AGENT_TIMEOUT,
    RATE_LIMIT_EXCEEDED,
    RESOURCE_NOT_FOUND,
    SERVICE_UNAVAILABLE,
    LLM_ERROR,
    get_http_status,
    is_retriable,
    ERROR_CODE_TO_HTTP_STATUS,
    RETRIABLE_ERROR_CODES,
)
from app.middleware.error_handler import (
    ErrorHandlerMiddleware,
    AgentError,
    AgentProcessingError,
    AgentTimeoutError,
    LLMError,
    ServiceUnavailableError,
    ResourceNotFoundError,
    RateLimitError,
    setup_error_handling,
)


# =============================================================================
# ERROR RESPONSE MODEL TESTS
# =============================================================================

class TestAgentErrorResponse:
    """Test AgentErrorResponse Pydantic model"""

    def test_create_basic_error_response(self):
        """Test creating a basic error response"""
        error = AgentErrorResponse(
            error_code="TEST_ERROR",
            error_type=ErrorType.PERMANENT,
            agent_id="AGENT-001",
            message="Test error message"
        )

        assert error.error_code == "TEST_ERROR"
        assert error.error_type == ErrorType.PERMANENT
        assert error.agent_id == "AGENT-001"
        assert error.message == "Test error message"
        assert error.details is None
        assert error.request_id is None
        assert isinstance(error.timestamp, datetime)
        assert error.severity == ErrorSeverity.ERROR
        assert error.retry_after is None

    def test_create_full_error_response(self):
        """Test creating an error response with all fields"""
        error = AgentErrorResponse(
            error_code=AGENT_PROCESSING_ERROR,
            error_type=ErrorType.RETRIABLE,
            agent_id="AGENT-016",
            message="Content processing failed",
            details={"reason": "Invalid format", "file": "test.xyz"},
            request_id="req-abc123",
            severity=ErrorSeverity.ERROR,
            retry_after=30
        )

        assert error.error_code == AGENT_PROCESSING_ERROR
        assert error.error_type == ErrorType.RETRIABLE
        assert error.details == {"reason": "Invalid format", "file": "test.xyz"}
        assert error.request_id == "req-abc123"
        assert error.retry_after == 30

    def test_error_response_serialization(self):
        """Test error response JSON serialization"""
        error = AgentErrorResponse(
            error_code="TEST_ERROR",
            error_type=ErrorType.PERMANENT,
            agent_id="AGENT-003",
            message="Test message"
        )

        json_data = error.model_dump(mode="json")

        assert "error_code" in json_data
        assert "error_type" in json_data
        assert "agent_id" in json_data
        assert "message" in json_data
        assert "timestamp" in json_data


class TestValidationErrorResponse:
    """Test ValidationErrorResponse model"""

    def test_create_validation_error_response(self):
        """Test creating a validation error response"""
        error = ValidationErrorResponse(
            error_code=VALIDATION_ERROR,
            error_type=ErrorType.PERMANENT,
            agent_id="AGENT-003",
            message="Validation failed",
            validation_errors=[
                ValidationErrorDetail(
                    field="name",
                    message="Field required",
                    type="missing",
                    value=None
                )
            ]
        )

        assert error.error_code == VALIDATION_ERROR
        assert len(error.validation_errors) == 1
        assert error.validation_errors[0].field == "name"

    def test_multiple_validation_errors(self):
        """Test validation error with multiple errors"""
        errors = [
            ValidationErrorDetail(field="name", message="Required", type="missing"),
            ValidationErrorDetail(field="email", message="Invalid format", type="format"),
        ]

        error = ValidationErrorResponse(
            error_code=VALIDATION_ERROR,
            error_type=ErrorType.PERMANENT,
            agent_id="AGENT-005",
            message="Multiple validation errors",
            validation_errors=errors
        )

        assert len(error.validation_errors) == 2


class TestRateLimitErrorResponse:
    """Test RateLimitErrorResponse model"""

    def test_create_rate_limit_error(self):
        """Test creating a rate limit error response"""
        reset_time = datetime.utcnow()

        error = RateLimitErrorResponse(
            error_code=RATE_LIMIT_EXCEEDED,
            error_type=ErrorType.RETRIABLE,
            agent_id="AGENT-003",
            message="Rate limit exceeded",
            limit=100,
            remaining=0,
            reset_at=reset_time,
            retry_after=60
        )

        assert error.limit == 100
        assert error.remaining == 0
        assert error.reset_at == reset_time
        assert error.retry_after == 60


class TestFactoryFunctions:
    """Test error factory functions"""

    def test_create_agent_error(self):
        """Test create_agent_error factory function"""
        error = create_agent_error(
            error_code=AGENT_PROCESSING_ERROR,
            agent_id="AGENT-016",
            message="Processing failed",
            details={"step": "validation"}
        )

        assert isinstance(error, AgentErrorResponse)
        assert error.error_code == AGENT_PROCESSING_ERROR
        assert error.agent_id == "AGENT-016"

    def test_create_validation_error_from_pydantic(self):
        """Test create_validation_error factory function"""
        pydantic_errors = [
            {"loc": ["body", "name"], "msg": "field required", "type": "missing", "input": None}
        ]

        error = create_validation_error(
            agent_id="AGENT-003",
            message="Validation failed",
            validation_errors=pydantic_errors
        )

        assert isinstance(error, ValidationErrorResponse)
        assert len(error.validation_errors) == 1
        assert error.validation_errors[0].field == "name"


# =============================================================================
# ERROR CODES TESTS
# =============================================================================

class TestErrorCodes:
    """Test error code constants and functions"""

    def test_get_http_status_known_code(self):
        """Test getting HTTP status for known error codes"""
        assert get_http_status(VALIDATION_ERROR) == 400
        assert get_http_status(RESOURCE_NOT_FOUND) == 404
        assert get_http_status(RATE_LIMIT_EXCEEDED) == 429
        assert get_http_status(INTERNAL_SERVER_ERROR) == 500
        assert get_http_status(SERVICE_UNAVAILABLE) == 503
        assert get_http_status(AGENT_TIMEOUT) == 504

    def test_get_http_status_unknown_code(self):
        """Test getting HTTP status for unknown error code defaults to 500"""
        assert get_http_status("UNKNOWN_ERROR") == 500

    def test_is_retriable_returns_true_for_retriable_codes(self):
        """Test is_retriable returns True for retriable error codes"""
        assert is_retriable(RATE_LIMIT_EXCEEDED) is True
        assert is_retriable(SERVICE_UNAVAILABLE) is True
        assert is_retriable(AGENT_TIMEOUT) is True

    def test_is_retriable_returns_false_for_permanent_codes(self):
        """Test is_retriable returns False for permanent error codes"""
        assert is_retriable(VALIDATION_ERROR) is False
        assert is_retriable(RESOURCE_NOT_FOUND) is False
        assert is_retriable(INTERNAL_SERVER_ERROR) is False


# =============================================================================
# CUSTOM EXCEPTION TESTS
# =============================================================================

class TestCustomExceptions:
    """Test custom exception classes"""

    def test_agent_error_base(self):
        """Test base AgentError exception"""
        error = AgentError(
            error_code=AGENT_PROCESSING_ERROR,
            message="Test error",
            agent_id="AGENT-003"
        )

        assert error.error_code == AGENT_PROCESSING_ERROR
        assert str(error) == "Test error"
        assert error.agent_id == "AGENT-003"
        assert error.error_type == ErrorType.PERMANENT

    def test_agent_processing_error(self):
        """Test AgentProcessingError exception"""
        error = AgentProcessingError(
            message="Content processing failed",
            agent_id="AGENT-016",
            details={"step": "parse"}
        )

        assert error.error_code == AGENT_PROCESSING_ERROR
        assert error.error_type == ErrorType.RETRIABLE
        assert error.details == {"step": "parse"}

    def test_agent_timeout_error(self):
        """Test AgentTimeoutError exception"""
        error = AgentTimeoutError(
            message="Operation timed out",
            agent_id="AGENT-012",
            retry_after=60
        )

        assert error.error_code == AGENT_TIMEOUT
        assert error.retry_after == 60
        assert error.error_type == ErrorType.RETRIABLE

    def test_llm_error(self):
        """Test LLMError exception"""
        error = LLMError(
            message="LLM API call failed",
            agent_id="AGENT-002",
            details={"provider": "anthropic"}
        )

        assert error.error_code == LLM_ERROR
        assert error.details == {"provider": "anthropic"}

    def test_service_unavailable_error(self):
        """Test ServiceUnavailableError exception"""
        error = ServiceUnavailableError(
            message="Neo4j unavailable",
            service_name="neo4j",
            agent_id="AGENT-012",
            retry_after=120
        )

        assert error.error_code == SERVICE_UNAVAILABLE
        assert error.details == {"service_name": "neo4j"}
        assert error.retry_after == 120

    def test_resource_not_found_error(self):
        """Test ResourceNotFoundError exception"""
        error = ResourceNotFoundError(
            resource_type="Document",
            resource_id="doc-123",
            agent_id="AGENT-016"
        )

        assert error.error_code == "DOCUMENT_NOT_FOUND"
        assert "doc-123" in error.message
        assert error.error_type == ErrorType.PERMANENT

    def test_rate_limit_error(self):
        """Test RateLimitError exception"""
        error = RateLimitError(
            message="Too many requests",
            agent_id="AGENT-003",
            retry_after=60,
            limit=100,
            remaining=0
        )

        assert error.error_code == RATE_LIMIT_EXCEEDED
        assert error.retry_after == 60
        assert error.details == {"limit": 100, "remaining": 0}


# =============================================================================
# ERROR HANDLER MIDDLEWARE TESTS
# =============================================================================

class TestErrorHandlerMiddleware:
    """Test ErrorHandlerMiddleware"""

    @pytest.fixture
    def app(self):
        """Create a test FastAPI app with error handling"""
        app = FastAPI()
        setup_error_handling(app)

        router = APIRouter()

        @router.get("/success")
        async def success_route():
            return {"status": "ok"}

        @router.get("/agent-error")
        async def agent_error_route():
            raise AgentProcessingError(
                message="Processing failed",
                agent_id="AGENT-016"
            )

        @router.get("/timeout-error")
        async def timeout_route():
            raise AgentTimeoutError(
                message="Timeout",
                agent_id="AGENT-012",
                retry_after=30
            )

        @router.get("/generic-error")
        async def generic_error_route():
            raise ValueError("Unexpected error")

        @router.post("/validate")
        async def validate_route(data: TestValidationModel):
            return data

        app.include_router(router, prefix="/api/test")

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    def test_success_request(self, client):
        """Test successful request passes through"""
        response = client.get("/api/test/success")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert "X-Request-ID" in response.headers

    def test_agent_error_handled(self, client):
        """Test AgentError is properly handled"""
        response = client.get("/api/test/agent-error")

        assert response.status_code == 500
        data = response.json()

        assert data["error_code"] == AGENT_PROCESSING_ERROR
        assert data["agent_id"] == "AGENT-016"
        assert data["message"] == "Processing failed"
        assert data["error_type"] == "retriable"

    def test_timeout_error_with_retry_after(self, client):
        """Test timeout error includes Retry-After header"""
        response = client.get("/api/test/timeout-error")

        assert response.status_code == 504
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "30"

    def test_generic_error_handled(self, client):
        """Test generic exceptions are caught and wrapped"""
        response = client.get("/api/test/generic-error")

        assert response.status_code == 500
        data = response.json()

        assert data["error_code"] == INTERNAL_SERVER_ERROR
        assert data["message"] == "An unexpected error occurred"
        assert "exception_type" in data["details"]

    def test_request_id_propagated(self, client):
        """Test X-Request-ID header is propagated"""
        request_id = "custom-request-id-123"
        response = client.get(
            "/api/test/success",
            headers={"X-Request-ID": request_id}
        )

        assert response.headers["X-Request-ID"] == request_id


class TestAgentIdExtraction:
    """Test agent ID extraction from URL paths"""

    def test_extract_agent_from_summarizer_path(self):
        """Test extracting agent ID from summarizer path"""
        middleware = ErrorHandlerMiddleware(app=None)
        assert middleware._extract_agent_id("/api/summarizer/summarize") == "AGENT-002"

    def test_extract_agent_from_asset_paths(self):
        """Test extracting agent IDs from asset generator paths"""
        middleware = ErrorHandlerMiddleware(app=None)

        assert middleware._extract_agent_id("/api/assets/skill") == "AGENT-003"
        assert middleware._extract_agent_id("/api/assets/command") == "AGENT-004"
        assert middleware._extract_agent_id("/api/assets/agent") == "AGENT-005"
        assert middleware._extract_agent_id("/api/assets/prompt") == "AGENT-006"
        assert middleware._extract_agent_id("/api/assets/workflow") == "AGENT-007"

    def test_extract_agent_from_classifier_path(self):
        """Test extracting agent ID from classifier path"""
        middleware = ErrorHandlerMiddleware(app=None)
        assert middleware._extract_agent_id("/api/classifier/classify") == "AGENT-008"

    def test_extract_agent_from_analysis_paths(self):
        """Test extracting agent IDs from document analysis paths"""
        middleware = ErrorHandlerMiddleware(app=None)

        assert middleware._extract_agent_id("/api/document-analysis/research") == "AGENT-009"
        assert middleware._extract_agent_id("/api/document-analysis/strategy") == "AGENT-010"
        assert middleware._extract_agent_id("/api/document-analysis/fact-check") == "AGENT-011"

    def test_extract_agent_from_orchestration_paths(self):
        """Test extracting agent IDs from orchestration paths"""
        middleware = ErrorHandlerMiddleware(app=None)

        assert middleware._extract_agent_id("/api/orchestration/research") == "AGENT-012"
        assert middleware._extract_agent_id("/api/orchestration/analyze") == "AGENT-013"
        assert middleware._extract_agent_id("/api/orchestration/write") == "AGENT-014"
        assert middleware._extract_agent_id("/api/orchestration/review") == "AGENT-015"

    def test_extract_agent_from_content_prep_path(self):
        """Test extracting agent ID from content prep path"""
        middleware = ErrorHandlerMiddleware(app=None)
        assert middleware._extract_agent_id("/api/content-prep/process") == "AGENT-016"

    def test_unknown_path_returns_unknown(self):
        """Test unknown paths return 'unknown' agent ID"""
        middleware = ErrorHandlerMiddleware(app=None)
        assert middleware._extract_agent_id("/api/unknown/endpoint") == "unknown"


# =============================================================================
# VALIDATION MODEL FOR TESTS
# =============================================================================

class TestValidationModel(BaseModel):
    """Model for validation testing"""
    name: str = Field(..., min_length=1)
    count: int = Field(..., gt=0)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestErrorHandlingIntegration:
    """Integration tests for error handling system"""

    @pytest.fixture
    def app(self):
        """Create a comprehensive test app"""
        app = FastAPI()
        setup_error_handling(app)

        router = APIRouter()

        @router.post("/assets/skill")
        async def create_skill(data: TestValidationModel):
            return {"name": data.name, "count": data.count}

        @router.get("/orchestration/workflow/{workflow_id}")
        async def get_workflow(workflow_id: str):
            if workflow_id == "not-found":
                raise ResourceNotFoundError(
                    resource_type="Workflow",
                    resource_id=workflow_id,
                    agent_id="AGENT-012"
                )
            return {"id": workflow_id}

        @router.post("/summarizer/summarize")
        async def summarize():
            raise LLMError(
                message="Claude API rate limited",
                agent_id="AGENT-002"
            )

        app.include_router(router, prefix="/api")

        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_validation_error_response_format(self, client):
        """Test validation errors have correct format"""
        response = client.post(
            "/api/assets/skill",
            json={"name": "", "count": -1}
        )

        assert response.status_code == 400
        data = response.json()

        assert data["error_code"] == VALIDATION_ERROR
        assert data["error_type"] == "permanent"
        assert "validation_errors" in data
        assert len(data["validation_errors"]) >= 1

    def test_resource_not_found_response(self, client):
        """Test resource not found error response"""
        response = client.get("/api/orchestration/workflow/not-found")

        assert response.status_code == 404
        data = response.json()

        assert data["error_code"] == "WORKFLOW_NOT_FOUND"
        assert data["agent_id"] == "AGENT-012"
        assert "not-found" in data["message"]

    def test_llm_error_response(self, client):
        """Test LLM error response"""
        response = client.post("/api/summarizer/summarize")

        assert response.status_code == 502  # LLM_ERROR maps to 502
        data = response.json()

        assert data["error_code"] == LLM_ERROR
        assert data["agent_id"] == "AGENT-002"


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
