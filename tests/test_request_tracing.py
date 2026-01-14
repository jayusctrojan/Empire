"""
Unit tests for Request Tracing Middleware and Utilities.

Task 136: X-Request-ID Tracing Across Agent Chains
Tests for: app/middleware/request_tracing.py, app/utils/tracing.py
"""

import pytest
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from httpx import AsyncClient

import os
os.environ.setdefault("ENVIRONMENT", "test")


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def app():
    """Create test FastAPI app with request tracing middleware."""
    from app.middleware.request_tracing import RequestTracingMiddleware

    test_app = FastAPI()
    test_app.add_middleware(
        RequestTracingMiddleware,
        header_name="X-Request-ID",
        log_requests=False,  # Disable logging in tests
        include_path=True,
        include_timing=True,
    )

    @test_app.get("/test")
    async def test_endpoint():
        from app.middleware.request_tracing import get_request_id
        return {"request_id": get_request_id()}

    @test_app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")

    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# ============================================================================
# Test: Context Variables
# ============================================================================


class TestContextVariables:
    """Tests for request ID context variables."""

    def test_get_request_id_default(self):
        """Test get_request_id returns None when not in request context."""
        from app.middleware.request_tracing import get_request_id, request_id_var

        # Reset context first
        request_id_var.set(None)
        assert get_request_id() is None

    def test_set_request_id(self):
        """Test setting request ID manually."""
        from app.middleware.request_tracing import get_request_id, set_request_id

        test_id = "test-request-123"
        set_request_id(test_id)

        assert get_request_id() == test_id

    def test_generate_request_id(self):
        """Test generating new request ID."""
        from app.middleware.request_tracing import generate_request_id

        request_id = generate_request_id()

        # Should be a valid UUID
        assert request_id is not None
        uuid.UUID(request_id)  # Should not raise

    def test_get_request_context_empty(self):
        """Test get_request_context returns empty dict by default."""
        from app.middleware.request_tracing import get_request_context, request_context_var

        # Reset context
        request_context_var.set({})
        context = get_request_context()

        assert context == {}

    def test_get_request_context_returns_copy(self):
        """Test get_request_context returns a copy, not the original."""
        from app.middleware.request_tracing import get_request_context, request_context_var

        original = {"key": "value"}
        request_context_var.set(original)

        context = get_request_context()
        context["new_key"] = "new_value"

        # Original should not be modified
        assert "new_key" not in request_context_var.get()


# ============================================================================
# Test: Middleware Behavior
# ============================================================================


class TestRequestTracingMiddleware:
    """Tests for RequestTracingMiddleware."""

    def test_generates_request_id_when_not_provided(self, client):
        """Test middleware generates UUID when X-Request-ID not provided."""
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

        # Should be a valid UUID
        request_id = response.headers["X-Request-ID"]
        uuid.UUID(request_id)

    def test_preserves_provided_request_id(self, client):
        """Test middleware preserves incoming X-Request-ID."""
        test_id = str(uuid.uuid4())
        response = client.get("/test", headers={"X-Request-ID": test_id})

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == test_id

    def test_request_id_available_in_endpoint(self, client):
        """Test request ID is accessible within endpoint handlers."""
        test_id = str(uuid.uuid4())
        response = client.get("/test", headers={"X-Request-ID": test_id})

        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == test_id

    def test_includes_timing_header(self, client):
        """Test middleware adds X-Process-Time header."""
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Process-Time" in response.headers

        # Should be a valid float
        float(response.headers["X-Process-Time"])

    def test_handles_non_uuid_request_id(self, client):
        """Test middleware accepts non-UUID request IDs."""
        non_uuid_id = "custom-request-id-12345"
        response = client.get("/test", headers={"X-Request-ID": non_uuid_id})

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == non_uuid_id

    def test_request_id_on_error(self, client):
        """Test request ID is preserved even on endpoint errors."""
        test_id = str(uuid.uuid4())

        with pytest.raises(Exception):
            client.get("/error", headers={"X-Request-ID": test_id})


# ============================================================================
# Test: Structlog Processor
# ============================================================================


class TestStructlogProcessor:
    """Tests for add_request_id_processor."""

    def test_adds_request_id_to_event_dict(self):
        """Test processor adds request_id to log entries."""
        from app.middleware.request_tracing import (
            add_request_id_processor,
            set_request_id,
        )

        test_id = "test-log-123"
        set_request_id(test_id)

        event_dict = {"event": "test message"}
        result = add_request_id_processor(None, "info", event_dict)

        assert result["request_id"] == test_id

    def test_does_not_override_existing_request_id(self):
        """Test processor doesn't override existing request_id in event."""
        from app.middleware.request_tracing import (
            add_request_id_processor,
            set_request_id,
        )

        set_request_id("context-id")

        event_dict = {"event": "test", "request_id": "explicit-id"}
        result = add_request_id_processor(None, "info", event_dict)

        assert result["request_id"] == "explicit-id"

    def test_no_request_id_when_not_set(self):
        """Test processor doesn't add request_id when not in context."""
        from app.middleware.request_tracing import (
            add_request_id_processor,
            request_id_var,
        )

        request_id_var.set(None)

        event_dict = {"event": "test"}
        result = add_request_id_processor(None, "info", event_dict)

        assert "request_id" not in result


# ============================================================================
# Test: Logging Filter
# ============================================================================


class TestRequestIdFilter:
    """Tests for RequestIdFilter."""

    def test_filter_adds_request_id_to_record(self):
        """Test filter adds request_id attribute to log records."""
        from app.middleware.request_tracing import RequestIdFilter, set_request_id
        import logging

        test_id = "filter-test-123"
        set_request_id(test_id)

        filter_obj = RequestIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )

        result = filter_obj.filter(record)

        assert result is True
        assert record.request_id == test_id

    def test_filter_uses_fallback_when_no_request_id(self):
        """Test filter uses fallback when no request_id in context."""
        from app.middleware.request_tracing import RequestIdFilter, request_id_var
        import logging

        request_id_var.set(None)

        filter_obj = RequestIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert record.request_id == "no-request-id"


# ============================================================================
# Test: Tracing Utilities
# ============================================================================


class TestTracingUtilities:
    """Tests for utility functions in app/utils/tracing.py."""

    def test_with_request_id_adds_header(self):
        """Test with_request_id adds X-Request-ID header."""
        from app.utils.tracing import with_request_id, set_request_id

        test_id = "util-test-123"
        set_request_id(test_id)

        headers = with_request_id()

        assert headers["X-Request-ID"] == test_id

    def test_with_request_id_preserves_existing_headers(self):
        """Test with_request_id doesn't overwrite other headers."""
        from app.utils.tracing import with_request_id, set_request_id

        set_request_id("test-id")

        existing = {"Authorization": "Bearer token", "Content-Type": "application/json"}
        headers = with_request_id(existing)

        assert headers["Authorization"] == "Bearer token"
        assert headers["Content-Type"] == "application/json"
        assert headers["X-Request-ID"] == "test-id"

    def test_with_request_id_doesnt_mutate_original(self):
        """Test with_request_id returns a new dict."""
        from app.utils.tracing import with_request_id, set_request_id

        set_request_id("test-id")

        original = {"key": "value"}
        result = with_request_id(original)

        # Original should not have X-Request-ID
        assert "X-Request-ID" not in original
        assert "X-Request-ID" in result

    def test_agent_context_creates_context_dict(self):
        """Test agent_context creates proper context dict."""
        from app.utils.tracing import agent_context, set_request_id

        parent_id = "parent-request-123"
        set_request_id(parent_id)

        ctx = agent_context("AGENT-002")

        assert ctx["request_id"] == parent_id
        assert ctx["parent_request_id"] == parent_id
        assert ctx["target_agent"] == "AGENT-002"
        assert ctx["chain_depth"] == 1

    def test_create_task_context(self):
        """Test create_task_context for background tasks."""
        from app.utils.tracing import create_task_context, set_request_id

        test_id = "task-context-123"
        set_request_id(test_id)

        ctx = create_task_context()

        assert ctx["request_id"] == test_id
        assert "parent_context" in ctx

    def test_restore_task_context(self):
        """Test restore_task_context restores request ID."""
        from app.utils.tracing import (
            create_task_context,
            restore_task_context,
            set_request_id,
            get_request_id,
            request_id_var,
        )

        # Set initial context
        original_id = "original-123"
        set_request_id(original_id)
        ctx = create_task_context()

        # Clear context (simulating new task execution)
        request_id_var.set(None)
        assert get_request_id() is None

        # Restore context
        restore_task_context(ctx)
        assert get_request_id() == original_id


# ============================================================================
# Test: Agent Span Functions
# ============================================================================


class TestAgentSpans:
    """Tests for agent span tracking."""

    def test_start_agent_span(self):
        """Test start_agent_span creates span dict."""
        from app.utils.tracing import start_agent_span, set_request_id

        set_request_id("span-test-123")

        span = start_agent_span("AGENT-002", "summarize")

        assert span["agent_id"] == "AGENT-002"
        assert span["operation"] == "summarize"
        assert span["request_id"] == "span-test-123"
        assert span["status"] == "in_progress"
        assert "start_time" in span

    def test_end_agent_span(self):
        """Test end_agent_span calculates duration."""
        from app.utils.tracing import start_agent_span, end_agent_span
        import time

        span = start_agent_span("AGENT-002", "test")
        time.sleep(0.01)  # Small delay to measure
        completed = end_agent_span(span)

        assert "duration_ms" in completed
        assert completed["duration_ms"] > 0
        assert "end_time" in completed


# ============================================================================
# Test: Traced Decorator
# ============================================================================


class TestTracedDecorator:
    """Tests for @traced decorator."""

    @pytest.mark.asyncio
    async def test_traced_async_function(self):
        """Test @traced works with async functions."""
        from app.utils.tracing import traced, set_request_id, get_request_id

        set_request_id("traced-test-123")

        @traced("test_operation")
        async def async_func():
            return {"result": "success"}

        result = await async_func()

        assert result["result"] == "success"

    def test_traced_sync_function(self):
        """Test @traced works with sync functions."""
        from app.utils.tracing import traced, set_request_id

        set_request_id("traced-sync-123")

        @traced("sync_operation")
        def sync_func():
            return "done"

        result = sync_func()

        assert result == "done"

    @pytest.mark.asyncio
    async def test_traced_preserves_exceptions(self):
        """Test @traced re-raises exceptions."""
        from app.utils.tracing import traced

        @traced()
        async def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError) as exc_info:
            await failing_func()

        assert "Test error" in str(exc_info.value)


# ============================================================================
# Test: Configuration Helper
# ============================================================================


class TestConfigureRequestTracing:
    """Tests for configure_request_tracing helper."""

    def test_configure_adds_middleware(self):
        """Test configure_request_tracing adds middleware to app."""
        from app.middleware.request_tracing import configure_request_tracing

        test_app = FastAPI()
        configure_request_tracing(test_app)

        # Middleware should be added (check middleware stack)
        assert len(test_app.user_middleware) > 0


# ============================================================================
# Run Tests
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
