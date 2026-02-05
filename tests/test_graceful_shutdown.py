"""
Empire v7.3 - Graceful Shutdown Tests
Tests for graceful shutdown coordination

Run with:
    pytest tests/test_graceful_shutdown.py -v
"""

import asyncio
import signal
from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.graceful_shutdown import GracefulShutdown, ShutdownMiddleware, ShutdownConfig, ShutdownReason


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_celery_app():
    """Mock Celery application"""
    mock = MagicMock()
    mock.control.broadcast.return_value = None
    mock.control.inspect.return_value.active.return_value = {}
    mock.control.purge.return_value = 0
    return mock


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    mock = AsyncMock()
    mock.close.return_value = None
    return mock


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j driver"""
    mock = MagicMock()
    mock.close.return_value = None
    return mock


# =============================================================================
# SHUTDOWN COORDINATOR INITIALIZATION TESTS
# =============================================================================

class TestShutdownCoordinatorInit:
    """Tests for GracefulShutdown initialization"""

    def test_coordinator_creation(self):
        """Test creating GracefulShutdown instance"""
        coordinator = GracefulShutdown()

        assert coordinator is not None
        assert coordinator.is_shutting_down is False

    def test_coordinator_with_custom_timeout(self):
        """Test GracefulShutdown with custom timeout"""
        config = ShutdownConfig(
            celery_drain_timeout_seconds=60,
            connection_close_timeout_seconds=15
        )
        coordinator = GracefulShutdown(config=config)

        assert coordinator.config.celery_drain_timeout_seconds == 60


# =============================================================================
# SHUTDOWN SIGNAL TESTS
# =============================================================================

class TestShutdownSignals:
    """Tests for shutdown signal handling"""

    @pytest.mark.asyncio
    async def test_prepare_shutdown_sets_shutting_down_flag(self):
        """Test that prepare_shutdown sets the shutting down flag"""
        coordinator = GracefulShutdown()

        # Simulate preparing for shutdown
        await coordinator.prepare_shutdown(ShutdownReason.SIGTERM)

        assert coordinator.is_shutting_down is True

    @pytest.mark.asyncio
    async def test_multiple_prepare_calls_handled_gracefully(self):
        """Test that multiple prepare calls don't cause issues"""
        coordinator = GracefulShutdown()

        # Multiple prepare calls
        await coordinator.prepare_shutdown(ShutdownReason.SIGTERM)
        await coordinator.prepare_shutdown(ShutdownReason.SIGTERM)  # Should be no-op

        # Should still be shutting down without errors
        assert coordinator.is_shutting_down is True


# =============================================================================
# CELERY SHUTDOWN TESTS
# =============================================================================

class TestCeleryShutdown:
    """Tests for Celery worker shutdown"""

    @pytest.mark.asyncio
    async def test_celery_workers_paused(self, mock_celery_app):
        """Test that Celery workers are paused during shutdown"""
        coordinator = GracefulShutdown(celery_app=mock_celery_app)

        await coordinator.drain_celery_tasks(timeout=5)

        # Pool should be paused
        mock_celery_app.control.broadcast.assert_called()

    @pytest.mark.asyncio
    async def test_celery_tasks_drained(self, mock_celery_app):
        """Test that in-flight Celery tasks are drained"""
        # Simulate active tasks that complete
        call_count = 0

        def mock_active():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {"worker1": [{"id": "task1"}]}
            return {"worker1": []}

        mock_celery_app.control.inspect.return_value.active = mock_active

        coordinator = GracefulShutdown(celery_app=mock_celery_app)

        await coordinator.drain_celery_tasks(timeout=10)

        # Should have waited for tasks
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_celery_purge_on_drain(self, mock_celery_app):
        """Test that tasks queue is purged after draining"""
        # Simulate no active tasks
        mock_celery_app.control.inspect.return_value.active.return_value = {"worker1": []}

        coordinator = GracefulShutdown(celery_app=mock_celery_app)

        await coordinator.drain_celery_tasks(timeout=5)

        # Purge should have been called
        mock_celery_app.control.purge.assert_called()


# =============================================================================
# DATABASE CONNECTION SHUTDOWN TESTS
# =============================================================================

class TestDatabaseShutdown:
    """Tests for database connection shutdown"""

    @pytest.mark.asyncio
    async def test_connection_manager_shutdown(self):
        """Test that connection manager is shut down"""
        mock_connection_manager = AsyncMock()

        coordinator = GracefulShutdown(connection_manager=mock_connection_manager)

        await coordinator.close_connections()

        # Shutdown should be called on connection manager
        mock_connection_manager.shutdown.assert_called()

    @pytest.mark.asyncio
    async def test_redis_connection_closed(self, mock_redis):
        """Test that Redis connection is closed"""
        mock_redis.close = MagicMock()

        coordinator = GracefulShutdown(redis_client=mock_redis)

        await coordinator.close_connections()

        # Redis close should be called
        mock_redis.close.assert_called()

    @pytest.mark.asyncio
    async def test_celery_connections_closed(self, mock_celery_app):
        """Test that Celery connections are closed"""
        coordinator = GracefulShutdown(celery_app=mock_celery_app)

        await coordinator.close_connections()

        # Celery close should be called
        mock_celery_app.close.assert_called()


# =============================================================================
# BACKGROUND TASK SHUTDOWN TESTS
# =============================================================================

class TestBackgroundTaskShutdown:
    """Tests for background task shutdown"""

    @pytest.mark.asyncio
    async def test_background_tasks_cancelled(self):
        """Test that background asyncio tasks are cancelled"""
        coordinator = GracefulShutdown()

        # Create some mock tasks
        async def long_running():
            await asyncio.sleep(100)

        task1 = asyncio.create_task(long_running())
        task2 = asyncio.create_task(long_running())

        coordinator.track_background_task(task1)
        coordinator.track_background_task(task2)

        await coordinator.cancel_background_tasks()

        # Tasks should be cancelled
        assert task1.cancelled() or task1.done()
        assert task2.cancelled() or task2.done()

    @pytest.mark.asyncio
    async def test_background_task_exceptions_handled(self):
        """Test that exceptions in background tasks are handled"""
        coordinator = GracefulShutdown()

        async def failing_task():
            raise Exception("Task error")

        task = asyncio.create_task(failing_task())
        coordinator.track_background_task(task)

        # Wait a bit for task to fail
        await asyncio.sleep(0.1)

        # Should not raise
        await coordinator.cancel_background_tasks()


# =============================================================================
# SHUTDOWN PROGRESS TESTS
# =============================================================================

class TestShutdownProgress:
    """Tests for shutdown progress tracking"""

    @pytest.mark.asyncio
    async def test_progress_tracked_through_phases(self):
        """Test that shutdown progress is tracked through phases"""
        coordinator = GracefulShutdown()

        # Start shutdown
        await coordinator.prepare_shutdown(ShutdownReason.MANUAL)

        # Check progress phase updated
        status = coordinator.get_status()
        assert status["is_shutting_down"] is True

    def test_get_shutdown_status(self):
        """Test getting current shutdown status"""
        coordinator = GracefulShutdown()

        status = coordinator.get_status()

        assert status["is_shutting_down"] is False
        assert status["phase"] == "running"

    @pytest.mark.asyncio
    async def test_status_reflects_shutdown_phase(self):
        """Test that status reflects current shutdown phase"""
        coordinator = GracefulShutdown()

        await coordinator.prepare_shutdown(ShutdownReason.MANUAL)
        status = coordinator.get_status()

        assert status["is_shutting_down"] is True
        assert status["reason"] == "manual"


# =============================================================================
# SHUTDOWN MIDDLEWARE TESTS
# =============================================================================

class TestShutdownMiddleware:
    """Tests for shutdown middleware (ASGI style)"""

    @pytest.mark.asyncio
    async def test_middleware_rejects_during_shutdown(self):
        """Test that middleware rejects new requests during shutdown"""
        coordinator = GracefulShutdown()
        coordinator._is_shutting_down = True

        app = AsyncMock()
        middleware = ShutdownMiddleware(app, coordinator)

        # Create ASGI scope
        scope = {"type": "http", "path": "/api/query"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # Should return 503 - check that send was called with 503 status
        send.assert_called()
        calls = send.call_args_list
        # First call should be response start with 503
        assert calls[0][0][0]["status"] == 503

    @pytest.mark.asyncio
    async def test_middleware_passes_non_http_requests(self):
        """Test that middleware passes through non-HTTP requests"""
        coordinator = GracefulShutdown()
        coordinator._is_shutting_down = True

        app = AsyncMock()
        middleware = ShutdownMiddleware(app, coordinator)

        # Create non-HTTP scope (e.g., websocket)
        scope = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # Should pass through to app
        app.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_tracks_active_requests(self):
        """Test that middleware tracks active requests"""
        coordinator = GracefulShutdown()

        request_started = asyncio.Event()

        async def slow_app(scope, receive, send):
            request_started.set()
            await asyncio.sleep(0.1)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        middleware = ShutdownMiddleware(slow_app, coordinator)

        scope = {"type": "http", "path": "/api/query"}
        receive = AsyncMock()
        send = AsyncMock()

        # Start request
        task = asyncio.create_task(middleware(scope, receive, send))

        await request_started.wait()
        await asyncio.sleep(0.01)

        # Should have active request
        assert len(coordinator._active_requests) > 0

        await task

        # Request should be complete
        assert len(coordinator._active_requests) == 0


# =============================================================================
# FULL SHUTDOWN SEQUENCE TESTS
# =============================================================================

class TestFullShutdownSequence:
    """Tests for full shutdown sequence"""

    @pytest.mark.asyncio
    async def test_full_shutdown_order(self, mock_celery_app, mock_redis):
        """Test that shutdown happens in correct order"""
        shutdown_order = []

        coordinator = GracefulShutdown(
            celery_app=mock_celery_app,
            redis_client=mock_redis
        )

        async def mock_drain_celery(*args, **kwargs):
            shutdown_order.append("celery")
            return True

        async def mock_cancel_tasks(*args, **kwargs):
            shutdown_order.append("tasks")
            return 0

        async def mock_close_connections(*args, **kwargs):
            shutdown_order.append("connections")
            return True

        coordinator.drain_celery_tasks = mock_drain_celery
        coordinator.cancel_background_tasks = mock_cancel_tasks
        coordinator.close_connections = mock_close_connections

        await coordinator.initiate_shutdown()

        # Verify order: Celery drain before connections close
        assert shutdown_order.index("celery") < shutdown_order.index("connections")

    @pytest.mark.asyncio
    async def test_shutdown_completes_phases(self):
        """Test that shutdown completes all phases"""
        coordinator = GracefulShutdown()

        progress = await coordinator.initiate_shutdown()

        # Shutdown should be complete
        assert coordinator.is_shutting_down is True
        assert progress.phase.value == "complete"


# =============================================================================
# TELEMETRY FLUSH TESTS
# =============================================================================

class TestTelemetryFlush:
    """Tests for telemetry flushing during shutdown"""

    @pytest.mark.asyncio
    async def test_data_flush_succeeds(self):
        """Test that data flush completes without error"""
        coordinator = GracefulShutdown()

        # Should not raise
        result = await coordinator.flush_data()

        assert result is True
        assert coordinator.progress.flushed_data is True

    @pytest.mark.asyncio
    async def test_shutdown_hooks_called(self):
        """Test that registered shutdown hooks are called"""
        coordinator = GracefulShutdown()

        hook_called = False

        async def test_hook():
            nonlocal hook_called
            hook_called = True

        coordinator.register_shutdown_hook(test_hook)

        await coordinator.flush_data()

        assert hook_called is True
