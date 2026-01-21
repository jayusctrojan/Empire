"""
Empire v7.3 - Exception Handling Framework Tests
Task 154: Standardized Exception Handling Framework

Comprehensive tests for the exception hierarchy, error handler middleware,
and contextual error logging utilities.
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.requests import Request as StarletteRequest

# Import exceptions
from app.exceptions import (
    # Base
    BaseAppException,
    ConfigurationError,
    InitializationError,
    # 400
    BadRequestException,
    ValidationException,
    InvalidFormatException,
    MissingFieldException,
    # 401
    UnauthorizedException,
    InvalidTokenException,
    TokenExpiredException,
    # 403
    ForbiddenException,
    InsufficientPermissionsException,
    AccessDeniedException,
    # 404
    NotFoundException,
    DocumentNotFoundException,
    UserNotFoundException,
    ProjectNotFoundException,
    # 409
    ConflictException,
    DuplicateResourceException,
    StateConflictException,
    # 422
    UnprocessableEntityException,
    BusinessRuleViolationException,
    # 429
    RateLimitException,
    QuotaExceededException,
    # 500
    InternalServerException,
    DatabaseException,
    Neo4jException,
    SupabaseException,
    RedisException,
    StorageException,
    B2StorageException,
    FileUploadException,
    FileDownloadException,
    # 502
    BadGatewayException,
    ExternalAPIException,
    AnthropicAPIException,
    LlamaParseException,
    # 503
    ServiceUnavailableException,
    MaintenanceModeException,
    CircuitBreakerOpenException,
    # 504
    GatewayTimeoutException,
    OperationTimeoutException,
    # Agent
    AgentException,
    AgentProcessingException,
    AgentTimeoutException,
    AgentUnavailableException,
    AgentCircuitOpenException,
    # LLM
    LLMException,
    LLMTimeoutException,
    LLMRateLimitException,
    LLMContextExceededException,
    # Workflow
    WorkflowException,
    OrchestrationException,
    WorkflowTimeoutException,
    WorkflowStepException,
    # Content
    ContentProcessingException,
    SummarizationException,
    ClassificationException,
    # Graph
    GraphAgentException,
    GraphQueryException,
    GraphTraversalException,
)

# Import error logging utilities
from app.utils.error_logging import (
    ErrorLogger,
    ErrorContext,
    ErrorAggregator,
    log_errors,
)


# =============================================================================
# BASE EXCEPTION TESTS
# =============================================================================

class TestBaseAppException:
    """Tests for BaseAppException."""

    def test_basic_initialization(self):
        """Test basic exception initialization."""
        exc = BaseAppException(
            message="Test error",
            error_code="TEST_ERROR",
            status_code=400
        )

        assert exc.message == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.status_code == 400
        assert exc.retriable is False
        assert exc.severity == "error"
        assert exc.retry_after is None
        assert isinstance(exc.timestamp, datetime)

    def test_full_initialization(self):
        """Test exception with all parameters."""
        details = {"field": "test", "value": 123}
        exc = BaseAppException(
            message="Full test error",
            error_code="FULL_TEST",
            status_code=503,
            details=details,
            severity="critical",
            retriable=True,
            retry_after=30
        )

        assert exc.message == "Full test error"
        assert exc.error_code == "FULL_TEST"
        assert exc.status_code == 503
        assert exc.details == details
        assert exc.severity == "critical"
        assert exc.retriable is True
        assert exc.retry_after == 30

    def test_to_dict(self):
        """Test exception to_dict conversion."""
        exc = BaseAppException(
            message="Test",
            error_code="TEST",
            status_code=400,
            details={"key": "value"},
            retriable=True,
            retry_after=60
        )

        result = exc.to_dict()

        assert result["error_code"] == "TEST"
        assert result["message"] == "Test"
        assert result["status_code"] == 400
        assert result["retriable"] is True
        assert result["details"] == {"key": "value"}
        assert result["retry_after"] == 60
        assert "timestamp" in result

    def test_string_representations(self):
        """Test __str__ and __repr__ methods."""
        exc = BaseAppException(message="Test error", error_code="TEST")

        assert str(exc) == "TEST: Test error"
        assert "BaseAppException" in repr(exc)
        assert "Test error" in repr(exc)


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_basic_error(self):
        """Test basic configuration error."""
        exc = ConfigurationError(message="Missing config")

        assert exc.status_code == 500
        assert exc.error_code == "CONFIGURATION_ERROR"
        assert exc.severity == "critical"
        assert exc.retriable is False

    def test_with_config_key(self):
        """Test configuration error with config key."""
        exc = ConfigurationError(
            message="Invalid config",
            config_key="DATABASE_URL"
        )

        assert exc.details["config_key"] == "DATABASE_URL"


# =============================================================================
# CLIENT ERROR TESTS (4xx)
# =============================================================================

class TestClientErrors:
    """Tests for client error exceptions (4xx)."""

    def test_bad_request(self):
        """Test BadRequestException."""
        exc = BadRequestException(message="Invalid data")

        assert exc.status_code == 400
        assert exc.error_code == "BAD_REQUEST"
        assert exc.retriable is False

    def test_validation_exception(self):
        """Test ValidationException."""
        validation_errors = [
            {"field": "email", "message": "Invalid format", "type": "value_error"},
            {"field": "age", "message": "Must be positive", "type": "value_error"},
        ]
        exc = ValidationException(
            message="Validation failed",
            validation_errors=validation_errors
        )

        assert exc.status_code == 400
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.validation_errors == validation_errors
        assert exc.details["error_count"] == 2

    def test_missing_field(self):
        """Test MissingFieldException."""
        exc = MissingFieldException(field_name="username")

        assert exc.status_code == 400
        assert exc.error_code == "MISSING_REQUIRED_FIELD"
        assert "username" in exc.message
        assert exc.details["field"] == "username"

    def test_unauthorized(self):
        """Test UnauthorizedException."""
        exc = UnauthorizedException(message="Auth required")

        assert exc.status_code == 401
        assert exc.error_code == "UNAUTHORIZED"

    def test_invalid_token(self):
        """Test InvalidTokenException."""
        exc = InvalidTokenException()

        assert exc.status_code == 401
        assert exc.error_code == "INVALID_TOKEN"

    def test_token_expired(self):
        """Test TokenExpiredException."""
        exc = TokenExpiredException()

        assert exc.status_code == 401
        assert exc.error_code == "TOKEN_EXPIRED"

    def test_forbidden(self):
        """Test ForbiddenException."""
        exc = ForbiddenException(
            message="Not allowed",
            required_permission="admin"
        )

        assert exc.status_code == 403
        assert exc.error_code == "FORBIDDEN"
        assert exc.details["required_permission"] == "admin"

    def test_insufficient_permissions(self):
        """Test InsufficientPermissionsException."""
        exc = InsufficientPermissionsException(
            required_role="admin",
            user_roles=["viewer", "editor"]
        )

        assert exc.status_code == 403
        assert exc.error_code == "INSUFFICIENT_PERMISSIONS"
        assert exc.details["required_role"] == "admin"
        assert exc.details["user_roles"] == ["viewer", "editor"]

    def test_not_found(self):
        """Test NotFoundException."""
        exc = NotFoundException(
            message="Not found",
            resource_type="document",
            resource_id="doc-123"
        )

        assert exc.status_code == 404
        assert exc.error_code == "DOCUMENT_NOT_FOUND"
        assert exc.details["resource_type"] == "document"
        assert exc.details["resource_id"] == "doc-123"

    def test_document_not_found(self):
        """Test DocumentNotFoundException."""
        exc = DocumentNotFoundException(document_id="doc-456")

        assert exc.status_code == 404
        assert exc.error_code == "DOCUMENT_NOT_FOUND"
        assert "doc-456" in exc.message

    def test_user_not_found(self):
        """Test UserNotFoundException."""
        exc = UserNotFoundException(user_id="user-789")

        assert exc.status_code == 404
        assert exc.error_code == "USER_NOT_FOUND"

    def test_conflict(self):
        """Test ConflictException."""
        exc = ConflictException(message="Resource conflict")

        assert exc.status_code == 409
        assert exc.error_code == "CONFLICT"

    def test_duplicate_resource(self):
        """Test DuplicateResourceException."""
        exc = DuplicateResourceException(
            resource_type="user",
            identifier="email@test.com"
        )

        assert exc.status_code == 409
        assert exc.error_code == "DUPLICATE_RESOURCE"
        assert exc.details["identifier"] == "email@test.com"

    def test_rate_limit(self):
        """Test RateLimitException."""
        exc = RateLimitException(
            limit=100,
            remaining=0,
            reset_seconds=60
        )

        assert exc.status_code == 429
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"
        assert exc.retriable is True
        assert exc.retry_after == 60
        assert exc.details["limit"] == 100

    def test_quota_exceeded(self):
        """Test QuotaExceededException."""
        exc = QuotaExceededException(
            quota_type="api_calls",
            limit=1000,
            used=1000
        )

        assert exc.status_code == 429
        assert exc.error_code == "QUOTA_EXCEEDED"
        assert exc.details["quota_type"] == "api_calls"


# =============================================================================
# SERVER ERROR TESTS (5xx)
# =============================================================================

class TestServerErrors:
    """Tests for server error exceptions (5xx)."""

    def test_internal_server_error(self):
        """Test InternalServerException."""
        exc = InternalServerException(message="Unexpected error")

        assert exc.status_code == 500
        assert exc.error_code == "INTERNAL_SERVER_ERROR"
        assert exc.retriable is True

    def test_database_exception(self):
        """Test DatabaseException."""
        exc = DatabaseException(
            message="Query failed",
            database="postgres",
            operation="insert"
        )

        assert exc.status_code == 500
        assert exc.error_code == "DATABASE_ERROR"
        assert exc.details["database"] == "postgres"
        assert exc.details["operation"] == "insert"

    def test_neo4j_exception(self):
        """Test Neo4jException."""
        exc = Neo4jException(
            message="Graph query failed",
            operation="traverse",
            query="MATCH (n) RETURN n"
        )

        assert exc.error_code == "NEO4J_ERROR"
        assert exc.details["operation"] == "traverse"

    def test_supabase_exception(self):
        """Test SupabaseException."""
        exc = SupabaseException(
            message="Insert failed",
            table="documents"
        )

        assert exc.error_code == "SUPABASE_ERROR"
        assert exc.details["table"] == "documents"

    def test_redis_exception(self):
        """Test RedisException."""
        exc = RedisException(
            message="Cache error",
            key="user:123"
        )

        assert exc.error_code == "REDIS_ERROR"
        assert exc.retriable is True
        assert exc.retry_after == 5

    def test_storage_exception(self):
        """Test StorageException."""
        exc = StorageException(
            message="Upload failed",
            storage_provider="s3",
            file_path="/uploads/file.pdf"
        )

        assert "S3_STORAGE_ERROR" in exc.error_code
        assert exc.details["file_path"] == "/uploads/file.pdf"

    def test_b2_storage_exception(self):
        """Test B2StorageException."""
        exc = B2StorageException(message="B2 upload failed")

        assert "B2" in exc.error_code

    def test_bad_gateway(self):
        """Test BadGatewayException."""
        exc = BadGatewayException(
            message="Upstream error",
            service_name="external-api"
        )

        assert exc.status_code == 502
        assert exc.error_code == "BAD_GATEWAY"
        assert exc.retriable is True
        assert exc.retry_after == 30

    def test_external_api_exception(self):
        """Test ExternalAPIException."""
        exc = ExternalAPIException(
            service_name="openai",
            api_response={"error": "rate_limit"}
        )

        assert exc.error_code == "EXTERNAL_API_ERROR"
        assert exc.details["api_response"] == {"error": "rate_limit"}

    def test_anthropic_api_exception(self):
        """Test AnthropicAPIException."""
        exc = AnthropicAPIException(message="Claude API error")

        assert exc.error_code == "ANTHROPIC_API_ERROR"

    def test_service_unavailable(self):
        """Test ServiceUnavailableException."""
        exc = ServiceUnavailableException(
            service_name="neo4j",
            estimated_recovery=120
        )

        assert exc.status_code == 503
        assert exc.error_code == "SERVICE_UNAVAILABLE"
        assert exc.retriable is True
        assert exc.retry_after == 120

    def test_circuit_breaker_open(self):
        """Test CircuitBreakerOpenException."""
        exc = CircuitBreakerOpenException(
            service_name="database",
            reset_time=30
        )

        assert exc.error_code == "CIRCUIT_BREAKER_OPEN"
        assert exc.status_code == 503
        assert exc.retry_after == 30

    def test_gateway_timeout(self):
        """Test GatewayTimeoutException."""
        exc = GatewayTimeoutException(
            timeout_seconds=30.0,
            operation="query"
        )

        assert exc.status_code == 504
        assert exc.error_code == "GATEWAY_TIMEOUT"
        assert exc.details["timeout_seconds"] == 30.0


# =============================================================================
# AGENT ERROR TESTS
# =============================================================================

class TestAgentErrors:
    """Tests for agent-specific exceptions."""

    def test_agent_exception_base(self):
        """Test AgentException base class."""
        exc = AgentException(
            message="Agent error",
            agent_id="AGENT-001"
        )

        assert exc.agent_id == "AGENT-001"
        assert exc.details["agent_id"] == "AGENT-001"

    def test_agent_processing_exception(self):
        """Test AgentProcessingException."""
        exc = AgentProcessingException(
            message="Processing failed",
            agent_id="AGENT-002",
            task_type="summarization"
        )

        assert exc.error_code == "AGENT_PROCESSING_ERROR"
        assert exc.agent_id == "AGENT-002"
        assert exc.details["task_type"] == "summarization"

    def test_agent_timeout_exception(self):
        """Test AgentTimeoutException."""
        exc = AgentTimeoutException(
            agent_id="AGENT-003",
            timeout_seconds=60.0
        )

        assert exc.error_code == "AGENT_TIMEOUT"
        assert exc.status_code == 504
        assert exc.retry_after == 30

    def test_agent_unavailable_exception(self):
        """Test AgentUnavailableException."""
        exc = AgentUnavailableException(
            agent_id="AGENT-004",
            reason="maintenance"
        )

        assert exc.error_code == "AGENT_UNAVAILABLE"
        assert exc.status_code == 503
        assert exc.details["unavailable_reason"] == "maintenance"

    def test_agent_circuit_open(self):
        """Test AgentCircuitOpenException."""
        exc = AgentCircuitOpenException(
            agent_id="AGENT-005",
            reset_time=45
        )

        assert exc.error_code == "AGENT_CIRCUIT_OPEN"
        assert exc.retry_after == 45


# =============================================================================
# LLM ERROR TESTS
# =============================================================================

class TestLLMErrors:
    """Tests for LLM-specific exceptions."""

    def test_llm_exception(self):
        """Test LLMException."""
        exc = LLMException(
            message="LLM error",
            agent_id="AGENT-001",
            model="claude-3-5-sonnet"
        )

        assert exc.error_code == "LLM_ERROR"
        assert exc.details["model"] == "claude-3-5-sonnet"

    def test_llm_timeout_exception(self):
        """Test LLMTimeoutException."""
        exc = LLMTimeoutException(
            agent_id="AGENT-001",
            model="claude-3-5-sonnet",
            timeout_seconds=30.0
        )

        assert exc.error_code == "LLM_TIMEOUT"
        assert exc.status_code == 504

    def test_llm_rate_limit_exception(self):
        """Test LLMRateLimitException."""
        exc = LLMRateLimitException(
            agent_id="AGENT-001",
            retry_after=120
        )

        assert exc.error_code == "LLM_RATE_LIMIT"
        assert exc.status_code == 429
        assert exc.retry_after == 120

    def test_llm_context_exceeded(self):
        """Test LLMContextExceededException."""
        exc = LLMContextExceededException(
            agent_id="AGENT-001",
            model="claude-3-5-sonnet",
            context_size=250000,
            max_context=200000
        )

        assert exc.error_code == "LLM_CONTEXT_EXCEEDED"
        assert exc.status_code == 422
        assert exc.retriable is False
        assert exc.details["context_size"] == 250000


# =============================================================================
# WORKFLOW ERROR TESTS
# =============================================================================

class TestWorkflowErrors:
    """Tests for workflow-specific exceptions."""

    def test_workflow_exception(self):
        """Test WorkflowException."""
        exc = WorkflowException(
            message="Workflow failed",
            agent_id="AGENT-001",
            workflow_id="wf-123",
            step="analysis"
        )

        assert exc.error_code == "WORKFLOW_ERROR"
        assert exc.details["workflow_id"] == "wf-123"
        assert exc.details["failed_step"] == "analysis"

    def test_orchestration_exception(self):
        """Test OrchestrationException."""
        exc = OrchestrationException(
            agent_id="AGENT-001",
            workflow_id="wf-456",
            failed_agents=["AGENT-012", "AGENT-013"]
        )

        assert exc.error_code == "ORCHESTRATION_FAILED"
        assert exc.details["failed_agents"] == ["AGENT-012", "AGENT-013"]

    def test_workflow_timeout_exception(self):
        """Test WorkflowTimeoutException."""
        exc = WorkflowTimeoutException(
            agent_id="AGENT-001",
            workflow_id="wf-789",
            timeout_seconds=300.0
        )

        assert exc.error_code == "WORKFLOW_TIMEOUT"
        assert exc.status_code == 504
        assert exc.retry_after == 60

    def test_workflow_step_exception(self):
        """Test WorkflowStepException."""
        exc = WorkflowStepException(
            agent_id="AGENT-001",
            workflow_id="wf-101",
            step="research",
            step_number=2
        )

        assert exc.error_code == "WORKFLOW_STEP_FAILED"
        assert exc.details["step_number"] == 2


# =============================================================================
# ERROR LOGGER TESTS
# =============================================================================

class TestErrorLogger:
    """Tests for ErrorLogger utility."""

    def test_log_error_basic(self):
        """Test basic error logging."""
        exc = ValueError("Test error")

        with patch("app.utils.error_logging.logger") as mock_logger:
            request_id = ErrorLogger.log_error(exc)

            assert request_id is not None
            mock_logger.error.assert_called_once()

    def test_log_error_with_request(self):
        """Test error logging with request context."""
        exc = ValueError("Test error")

        # Create mock request
        mock_request = Mock()
        mock_request.state.request_id = "test-request-id"
        mock_request.state.user_id = "user-123"
        mock_request.url.path = "/api/test"
        mock_request.method = "POST"
        mock_request.client.host = "127.0.0.1"
        mock_request.query_params = {}

        with patch("app.utils.error_logging.logger") as mock_logger:
            request_id = ErrorLogger.log_error(exc, request=mock_request)

            assert request_id == "test-request-id"
            mock_logger.error.assert_called_once()

    def test_log_error_with_base_app_exception(self):
        """Test error logging with BaseAppException."""
        exc = NotFoundException(
            resource_type="document",
            resource_id="doc-123"
        )

        with patch("app.utils.error_logging.logger") as mock_logger:
            request_id = ErrorLogger.log_error(exc)

            assert request_id is not None
            # Verify the error details are included
            call_kwargs = mock_logger.error.call_args[1]
            assert call_kwargs["error_code"] == "DOCUMENT_NOT_FOUND"

    def test_log_warning(self):
        """Test warning logging."""
        with patch("app.utils.error_logging.logger") as mock_logger:
            request_id = ErrorLogger.log_warning(
                "Test warning",
                context={"key": "value"}
            )

            assert request_id is not None
            mock_logger.warning.assert_called_once()

    def test_log_info(self):
        """Test info logging."""
        with patch("app.utils.error_logging.logger") as mock_logger:
            request_id = ErrorLogger.log_info(
                "Test info",
                context={"operation": "test"}
            )

            assert request_id is not None
            mock_logger.info.assert_called_once()


# =============================================================================
# ERROR CONTEXT TESTS
# =============================================================================

class TestErrorContext:
    """Tests for ErrorContext context manager."""

    def test_no_error(self):
        """Test context manager with no error."""
        with ErrorContext() as ctx:
            result = 1 + 1

        assert ctx.error is None
        assert result == 2

    def test_with_error_reraise(self):
        """Test context manager with error and reraise."""
        with patch("app.utils.error_logging.logger"):
            with pytest.raises(ValueError):
                with ErrorContext(reraise=True) as ctx:
                    raise ValueError("Test error")

            assert ctx.error is not None
            assert ctx.request_id is not None

    def test_with_error_suppress(self):
        """Test context manager with error suppression."""
        with patch("app.utils.error_logging.logger"):
            with ErrorContext(reraise=False) as ctx:
                raise ValueError("Suppressed error")

            assert ctx.error is not None
            assert isinstance(ctx.error, ValueError)


# =============================================================================
# ERROR AGGREGATOR TESTS
# =============================================================================

class TestErrorAggregator:
    """Tests for ErrorAggregator."""

    def test_no_errors(self):
        """Test aggregator with no errors."""
        aggregator = ErrorAggregator()

        assert aggregator.has_errors is False
        assert aggregator.error_count == 0

    def test_add_errors(self):
        """Test adding errors to aggregator."""
        aggregator = ErrorAggregator()

        aggregator.add_error(
            ValueError("Error 1"),
            context={"item": 1}
        )
        aggregator.add_error(
            TypeError("Error 2"),
            context={"item": 2}
        )

        assert aggregator.has_errors is True
        assert aggregator.error_count == 2

    def test_log_all(self):
        """Test logging all aggregated errors."""
        aggregator = ErrorAggregator()
        aggregator.add_error(ValueError("Error 1"))
        aggregator.add_error(TypeError("Error 2"))

        with patch("app.utils.error_logging.logger") as mock_logger:
            request_id = aggregator.log_all()

            assert request_id is not None
            mock_logger.error.assert_called_once()

    def test_to_exception(self):
        """Test converting aggregated errors to exception."""
        aggregator = ErrorAggregator()
        aggregator.add_error(ValueError("Error 1"))
        aggregator.add_error(TypeError("Error 2"))

        exc = aggregator.to_exception()

        assert isinstance(exc, InternalServerException)
        assert exc.details["error_count"] == 2

    def test_clear(self):
        """Test clearing aggregated errors."""
        aggregator = ErrorAggregator()
        aggregator.add_error(ValueError("Error 1"))

        assert aggregator.has_errors is True

        aggregator.clear()

        assert aggregator.has_errors is False


# =============================================================================
# LOG ERRORS DECORATOR TESTS
# =============================================================================

class TestLogErrorsDecorator:
    """Tests for log_errors decorator."""

    def test_sync_function_success(self):
        """Test decorator with successful sync function."""
        @log_errors()
        def sync_func():
            return "success"

        result = sync_func()
        assert result == "success"

    def test_sync_function_error(self):
        """Test decorator with failing sync function."""
        @log_errors()
        def sync_func():
            raise ValueError("Test error")

        with patch("app.utils.error_logging.logger"):
            with pytest.raises(ValueError):
                sync_func()

    def test_sync_function_error_no_reraise(self):
        """Test decorator without reraise."""
        @log_errors(reraise=False)
        def sync_func():
            raise ValueError("Test error")

        with patch("app.utils.error_logging.logger"):
            result = sync_func()
            assert result is None

    @pytest.mark.asyncio
    async def test_async_function_success(self):
        """Test decorator with successful async function."""
        @log_errors()
        async def async_func():
            return "success"

        result = await async_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_function_error(self):
        """Test decorator with failing async function."""
        @log_errors()
        async def async_func():
            raise ValueError("Test error")

        with patch("app.utils.error_logging.logger"):
            with pytest.raises(ValueError):
                await async_func()

    def test_decorator_with_context(self):
        """Test decorator with custom context."""
        @log_errors(context={"service": "test_service"})
        def func_with_context():
            raise ValueError("Error with context")

        with patch("app.utils.error_logging.ErrorLogger.log_error") as mock_log:
            with pytest.raises(ValueError):
                func_with_context()

            # Verify context was passed
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["context"]["service"] == "test_service"


# =============================================================================
# EXCEPTION INHERITANCE TESTS
# =============================================================================

class TestExceptionInheritance:
    """Tests for exception class inheritance."""

    def test_all_exceptions_inherit_from_base(self):
        """Test that all exceptions inherit from BaseAppException."""
        exceptions = [
            BadRequestException(),
            ValidationException(),
            UnauthorizedException(),
            ForbiddenException(),
            NotFoundException(),
            ConflictException(),
            RateLimitException(),
            InternalServerException(),
            DatabaseException(),
            BadGatewayException(),
            ServiceUnavailableException(),
            GatewayTimeoutException(),
            AgentException(message="Test", agent_id="AGENT-001"),
            LLMException(message="Test", agent_id="AGENT-001"),
            WorkflowException(message="Test", agent_id="AGENT-001"),
        ]

        for exc in exceptions:
            assert isinstance(exc, BaseAppException), f"{type(exc).__name__} should inherit from BaseAppException"

    def test_agent_exceptions_inherit_from_agent_exception(self):
        """Test that agent-specific exceptions inherit correctly."""
        exceptions = [
            AgentProcessingException(agent_id="AGENT-001"),
            AgentTimeoutException(agent_id="AGENT-001"),
            AgentUnavailableException(agent_id="AGENT-001"),
            LLMException(message="Test", agent_id="AGENT-001"),
            LLMTimeoutException(agent_id="AGENT-001"),
            WorkflowException(message="Test", agent_id="AGENT-001"),
            OrchestrationException(agent_id="AGENT-001"),
        ]

        for exc in exceptions:
            assert isinstance(exc, AgentException), f"{type(exc).__name__} should inherit from AgentException"


# =============================================================================
# STATUS CODE MAPPING TESTS
# =============================================================================

class TestStatusCodeMapping:
    """Tests for correct HTTP status code mapping."""

    def test_400_exceptions(self):
        """Test 400-series status codes."""
        assert BadRequestException().status_code == 400
        assert ValidationException().status_code == 400
        assert MissingFieldException(field_name="test").status_code == 400

    def test_401_exceptions(self):
        """Test 401 status codes."""
        assert UnauthorizedException().status_code == 401
        assert InvalidTokenException().status_code == 401
        assert TokenExpiredException().status_code == 401

    def test_403_exceptions(self):
        """Test 403 status codes."""
        assert ForbiddenException().status_code == 403
        assert InsufficientPermissionsException().status_code == 403
        assert AccessDeniedException().status_code == 403

    def test_404_exceptions(self):
        """Test 404 status codes."""
        assert NotFoundException().status_code == 404
        assert DocumentNotFoundException(document_id="test").status_code == 404
        assert UserNotFoundException(user_id="test").status_code == 404

    def test_409_exceptions(self):
        """Test 409 status codes."""
        assert ConflictException().status_code == 409
        assert DuplicateResourceException().status_code == 409
        assert StateConflictException().status_code == 409

    def test_429_exceptions(self):
        """Test 429 status codes."""
        assert RateLimitException().status_code == 429
        assert QuotaExceededException().status_code == 429
        assert LLMRateLimitException(agent_id="test").status_code == 429

    def test_500_exceptions(self):
        """Test 500 status codes."""
        assert InternalServerException().status_code == 500
        assert DatabaseException().status_code == 500

    def test_502_exceptions(self):
        """Test 502 status codes."""
        assert BadGatewayException().status_code == 502
        assert ExternalAPIException().status_code == 502

    def test_503_exceptions(self):
        """Test 503 status codes."""
        assert ServiceUnavailableException().status_code == 503
        assert CircuitBreakerOpenException().status_code == 503
        assert AgentUnavailableException(agent_id="test").status_code == 503

    def test_504_exceptions(self):
        """Test 504 status codes."""
        assert GatewayTimeoutException().status_code == 504
        assert AgentTimeoutException(agent_id="test").status_code == 504
        assert WorkflowTimeoutException(agent_id="test").status_code == 504
