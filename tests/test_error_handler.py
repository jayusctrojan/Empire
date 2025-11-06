"""
Tests for Error Handler Service
Tests error classification, logging, and retry logic
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from app.services.error_handler import (
    ErrorHandler,
    ErrorContext,
    ErrorClassifier,
    ErrorSeverity,
    ErrorCategory,
    RetryStrategy,
    ProcessingLog,
    handle_errors,
    with_fallback,
    get_error_handler
)


# ============================================================================
# Test Error Classification
# ============================================================================

class TestErrorClassifier:
    """Test error classification logic"""

    def test_classify_network_error(self):
        """Test classification of network errors"""
        error = ConnectionError("Connection refused")
        category, strategy = ErrorClassifier.classify_error(error)

        assert category == ErrorCategory.NETWORK
        assert strategy == RetryStrategy.EXPONENTIAL

    def test_classify_timeout_error(self):
        """Test classification of timeout errors"""
        error = TimeoutError("Request timeout")
        category, strategy = ErrorClassifier.classify_error(error)

        assert category == ErrorCategory.TIMEOUT
        assert strategy == RetryStrategy.EXPONENTIAL

    def test_classify_validation_error(self):
        """Test classification of validation errors"""
        error = ValueError("Invalid input")
        category, strategy = ErrorClassifier.classify_error(error)

        assert category == ErrorCategory.VALIDATION
        assert strategy == RetryStrategy.NONE

    def test_classify_parsing_error(self):
        """Test classification of parsing errors"""
        error = Exception("ParseError: Invalid JSON")
        category, strategy = ErrorClassifier.classify_error(error)

        assert category == ErrorCategory.PARSING
        assert strategy == RetryStrategy.NONE

    def test_classify_service_unavailable(self):
        """Test classification of service unavailable errors"""
        error = Exception("503 Service Temporarily Unavailable")
        category, strategy = ErrorClassifier.classify_error(error)

        assert category == ErrorCategory.SERVICE_UNAVAILABLE
        assert strategy == RetryStrategy.EXPONENTIAL

    def test_is_retryable_transient_error(self):
        """Test retryability of transient errors"""
        error = ConnectionError("Network issue")
        assert ErrorClassifier.is_retryable(error) is True

    def test_is_retryable_permanent_error(self):
        """Test retryability of permanent errors"""
        error = ValueError("Bad value")
        assert ErrorClassifier.is_retryable(error) is False


# ============================================================================
# Test Error Context
# ============================================================================

class TestErrorContext:
    """Test error context dataclass"""

    def test_error_context_creation(self):
        """Test creating error context"""
        context = ErrorContext(
            task_id="task-123",
            task_type="document_processing",
            file_id="file-456",
            filename="test.pdf",
            retry_count=1,
            max_retries=3
        )

        assert context.task_id == "task-123"
        assert context.task_type == "document_processing"
        assert context.file_id == "file-456"
        assert context.filename == "test.pdf"
        assert context.retry_count == 1
        assert context.max_retries == 3

    def test_error_context_with_additional_data(self):
        """Test error context with additional context"""
        context = ErrorContext(
            task_id="task-123",
            additional_context={"user": "test_user", "attempt": 2}
        )

        assert context.additional_context["user"] == "test_user"
        assert context.additional_context["attempt"] == 2


# ============================================================================
# Test Error Handler
# ============================================================================

class TestErrorHandler:
    """Test error handler service"""

    @pytest.mark.asyncio
    async def test_handle_error_without_storage(self):
        """Test handling error without Supabase storage"""
        handler = ErrorHandler()
        context = ErrorContext(
            task_id="task-123",
            task_type="test_task",
            filename="test.pdf"
        )

        error = ConnectionError("Network failure")
        log_entry = await handler.handle_error(error, context)

        assert isinstance(log_entry, ProcessingLog)
        assert log_entry.error_type == "ConnectionError"
        assert log_entry.error_message == "Network failure"
        assert log_entry.category == ErrorCategory.NETWORK
        assert log_entry.severity in [ErrorSeverity.WARNING, ErrorSeverity.ERROR]
        assert log_entry.context.task_id == "task-123"

    @pytest.mark.asyncio
    async def test_handle_error_with_mock_storage(self):
        """Test handling error with mocked Supabase storage"""
        mock_storage = AsyncMock()
        mock_storage.insert_processing_log = AsyncMock(return_value={"id": "log-123"})

        handler = ErrorHandler(supabase_storage=mock_storage)
        context = ErrorContext(task_id="task-123")

        error = TimeoutError("Operation timeout")
        log_entry = await handler.handle_error(error, context)

        assert log_entry.error_type == "TimeoutError"
        assert log_entry.category == ErrorCategory.TIMEOUT
        mock_storage.insert_processing_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_error_with_custom_recovery(self):
        """Test error handling with custom recovery function"""
        recovery_called = False

        async def custom_recovery(exception, context):
            nonlocal recovery_called
            recovery_called = True

        handler = ErrorHandler()
        context = ErrorContext(task_id="task-123")
        error = ValueError("Test error")

        log_entry = await handler.handle_error(
            error,
            context,
            custom_recovery=custom_recovery
        )

        assert recovery_called is True
        assert log_entry.recovery_action == "custom_recovery_executed"
        assert log_entry.resolution_status == "resolved"

    @pytest.mark.asyncio
    async def test_handle_error_recovery_failure(self):
        """Test error handling when recovery function fails"""
        async def failing_recovery(exception, context):
            raise Exception("Recovery failed")

        handler = ErrorHandler()
        context = ErrorContext(task_id="task-123")
        error = ValueError("Test error")

        log_entry = await handler.handle_error(
            error,
            context,
            custom_recovery=failing_recovery
        )

        assert log_entry.recovery_action == "custom_recovery_failed"

    def test_determine_severity_exhausted_retries(self):
        """Test severity determination when retries exhausted"""
        handler = ErrorHandler()
        error = ConnectionError("Network error")
        severity = handler._determine_severity(error, ErrorCategory.NETWORK, retry_count=3)

        assert severity == ErrorSeverity.CRITICAL

    def test_determine_severity_database_error(self):
        """Test severity determination for database errors"""
        handler = ErrorHandler()
        error = Exception("Database connection failed")
        severity = handler._determine_severity(error, ErrorCategory.DATABASE, retry_count=0)

        assert severity == ErrorSeverity.ERROR

    def test_determine_severity_transient_error(self):
        """Test severity determination for transient errors"""
        handler = ErrorHandler()
        error = ConnectionError("Network error")
        severity = handler._determine_severity(error, ErrorCategory.NETWORK, retry_count=0)

        assert severity == ErrorSeverity.WARNING

    def test_register_fallback(self):
        """Test registering fallback functions"""
        handler = ErrorHandler()

        def my_fallback():
            return "fallback_result"

        handler.register_fallback(ConnectionError, my_fallback)

        assert ConnectionError in handler._fallback_callbacks
        assert handler._fallback_callbacks[ConnectionError] == my_fallback

    @pytest.mark.asyncio
    async def test_get_fallback(self):
        """Test retrieving registered fallback"""
        handler = ErrorHandler()

        def my_fallback():
            return "fallback_result"

        handler.register_fallback(ConnectionError, my_fallback)

        error = ConnectionError("Test")
        fallback = await handler.get_fallback(error)

        assert fallback == my_fallback

    @pytest.mark.asyncio
    async def test_get_fallback_no_match(self):
        """Test retrieving fallback when none registered"""
        handler = ErrorHandler()
        error = ValueError("Test")
        fallback = await handler.get_fallback(error)

        assert fallback is None


# ============================================================================
# Test Decorators
# ============================================================================

class TestDecorators:
    """Test error handling decorators"""

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_success(self):
        """Test handle_errors decorator on successful function"""
        @handle_errors(fallback_value=[], log_errors=True)
        async def successful_function():
            return [1, 2, 3]

        result = await successful_function()
        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_with_error(self):
        """Test handle_errors decorator when function raises error"""
        @handle_errors(fallback_value=[], log_errors=True)
        async def failing_function():
            raise ValueError("Test error")

        result = await failing_function()
        assert result == []

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_reraise(self):
        """Test handle_errors decorator with reraise=True"""
        @handle_errors(fallback_value=None, log_errors=True, reraise=True)
        async def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await failing_function()

    @pytest.mark.asyncio
    async def test_with_fallback_decorator_success(self):
        """Test with_fallback decorator on successful function"""
        async def fallback_function():
            return "fallback"

        @with_fallback(fallback_function)
        async def primary_function():
            return "primary"

        result = await primary_function()
        assert result == "primary"

    @pytest.mark.asyncio
    async def test_with_fallback_decorator_uses_fallback(self):
        """Test with_fallback decorator uses fallback on error"""
        async def fallback_function():
            return "fallback"

        @with_fallback(fallback_function)
        async def failing_function():
            raise ValueError("Primary failed")

        result = await failing_function()
        assert result == "fallback"


# ============================================================================
# Test Singleton
# ============================================================================

class TestSingleton:
    """Test singleton pattern for error handler"""

    def test_get_error_handler_singleton(self):
        """Test get_error_handler returns same instance"""
        handler1 = get_error_handler()
        handler2 = get_error_handler()

        assert handler1 is handler2

    def test_get_error_handler_with_storage(self):
        """Test get_error_handler with storage parameter"""
        mock_storage = Mock()
        handler = get_error_handler(supabase_storage=mock_storage)

        assert isinstance(handler, ErrorHandler)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete error handling flow"""

    @pytest.mark.asyncio
    async def test_full_error_handling_flow(self):
        """Test complete error handling workflow"""
        mock_storage = AsyncMock()
        mock_storage.insert_processing_log = AsyncMock(return_value={"id": "log-123"})

        handler = ErrorHandler(supabase_storage=mock_storage)

        context = ErrorContext(
            task_id="integration-test-123",
            task_type="test_task",
            file_id="file-456",
            filename="test.pdf",
            retry_count=1,
            max_retries=3,
            additional_context={"test": "data"}
        )

        # Simulate a network error
        error = ConnectionError("Network temporarily unavailable")

        log_entry = await handler.handle_error(error, context)

        # Verify classification
        assert log_entry.category == ErrorCategory.NETWORK
        assert log_entry.severity in [ErrorSeverity.WARNING, ErrorSeverity.ERROR]

        # Verify logging to storage
        mock_storage.insert_processing_log.assert_called_once()
        call_args = mock_storage.insert_processing_log.call_args[0][0]
        assert call_args["task_id"] == "integration-test-123"
        assert call_args["error_type"] == "ConnectionError"

    @pytest.mark.asyncio
    async def test_multiple_errors_in_sequence(self):
        """Test handling multiple errors sequentially"""
        handler = ErrorHandler()
        context = ErrorContext(task_id="seq-test")

        errors = [
            ConnectionError("Network error 1"),
            TimeoutError("Timeout error"),
            ValueError("Validation error"),
        ]

        log_entries = []
        for error in errors:
            context.retry_count += 1
            log_entry = await handler.handle_error(error, context)
            log_entries.append(log_entry)

        assert len(log_entries) == 3
        assert log_entries[0].category == ErrorCategory.NETWORK
        assert log_entries[1].category == ErrorCategory.TIMEOUT
        assert log_entries[2].category == ErrorCategory.VALIDATION
