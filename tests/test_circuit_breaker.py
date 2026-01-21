"""
Tests for Empire v7.3 Circuit Breaker Implementation (Task 159)

Comprehensive tests for:
- CircuitBreaker class
- FallbackRegistry
- ResilientSupabaseClient
- Circuit breaker management API endpoints

Author: Claude Code
Date: 2025-01-15
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from httpx import ConnectError, TimeoutException

from app.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitOpenError,
    FallbackRegistry,
    get_circuit_breaker_sync,
    get_all_circuit_statuses,
    reset_circuit,
    _circuit_registry,
    _fallback_registry,
)
from app.services.supabase_resilience import (
    ResilientSupabaseClient,
    SUPABASE_CONFIG,
    get_resilient_supabase_client,
)
from app.exceptions import ServiceUnavailableException


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def circuit_config():
    """Create a test circuit breaker configuration"""
    return CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        recovery_timeout=1.0,  # Short timeout for testing
        max_retries=2,
        retry_base_delay=0.1,
        retry_max_delay=0.5,
        retry_multiplier=2.0,
        operation_timeout=5.0,
    )


@pytest.fixture
def circuit_breaker(circuit_config):
    """Create a circuit breaker instance for testing"""
    return CircuitBreaker("test_service", circuit_config)


@pytest.fixture
def fallback_registry():
    """Create a clean fallback registry for testing"""
    return FallbackRegistry()


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing"""
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_query = MagicMock()

    # Setup chain
    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_query
    mock_table.insert.return_value = mock_query
    mock_table.update.return_value = mock_query
    mock_table.delete.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.range.return_value = mock_query
    mock_query.execute.return_value = MagicMock(data=[{"id": 1, "name": "test"}])

    return mock_client


# =============================================================================
# CIRCUIT BREAKER CONFIG TESTS
# =============================================================================

class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig dataclass"""

    def test_default_config(self):
        """Test default configuration values"""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.recovery_timeout == 60.0
        assert config.max_retries == 3
        assert config.retry_base_delay == 1.0
        assert config.retry_max_delay == 30.0
        assert config.retry_multiplier == 2.0
        assert config.operation_timeout == 30.0

    def test_custom_config(self, circuit_config):
        """Test custom configuration values"""
        assert circuit_config.failure_threshold == 3
        assert circuit_config.success_threshold == 2
        assert circuit_config.recovery_timeout == 1.0
        assert circuit_config.max_retries == 2

    def test_retryable_exceptions_default(self):
        """Test default retryable exceptions"""
        config = CircuitBreakerConfig()

        assert TimeoutError in config.retryable_exceptions
        assert ConnectionError in config.retryable_exceptions


# =============================================================================
# CIRCUIT BREAKER STATE TESTS
# =============================================================================

class TestCircuitBreakerState:
    """Tests for circuit breaker state management"""

    def test_initial_state_closed(self, circuit_breaker):
        """Test circuit starts in closed state"""
        assert circuit_breaker._state == CircuitState.CLOSED
        assert not circuit_breaker.is_open

    @pytest.mark.asyncio
    async def test_transitions_to_open_after_failures(self, circuit_breaker):
        """Test circuit opens after failure threshold"""
        async def failing_operation():
            raise ConnectionError("Connection refused")

        # Fail enough times to trip the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await circuit_breaker.call(failing_operation, use_fallback=False)

        assert circuit_breaker._state == CircuitState.OPEN
        assert circuit_breaker.is_open

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self, circuit_breaker):
        """Test open circuit rejects new calls"""
        # Force circuit to open state
        circuit_breaker._state = CircuitState.OPEN
        circuit_breaker._last_failure_time = time.time()

        async def operation():
            return "success"

        with pytest.raises(CircuitOpenError):
            await circuit_breaker.call(operation, use_fallback=False)

    @pytest.mark.asyncio
    async def test_half_open_after_recovery_timeout(self, circuit_breaker):
        """Test circuit transitions to half-open after recovery timeout"""
        # Force circuit to open state with old failure time
        circuit_breaker._state = CircuitState.OPEN
        circuit_breaker._last_failure_time = time.time() - 2.0  # Past timeout

        async def successful_operation():
            return "success"

        result = await circuit_breaker.call(successful_operation, use_fallback=False)

        assert result == "success"
        # Should be half-open or closed after success
        assert circuit_breaker._state in [CircuitState.HALF_OPEN, CircuitState.CLOSED]

    @pytest.mark.asyncio
    async def test_closes_after_success_threshold(self, circuit_breaker):
        """Test circuit closes after success threshold in half-open state"""
        circuit_breaker._state = CircuitState.HALF_OPEN
        circuit_breaker._success_count = 0

        async def successful_operation():
            return "success"

        # Need success_threshold successful calls
        for _ in range(2):
            await circuit_breaker.call(successful_operation, use_fallback=False)

        assert circuit_breaker._state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reset_clears_state(self, circuit_breaker):
        """Test reset restores circuit to initial state"""
        # Set some state
        circuit_breaker._state = CircuitState.OPEN
        circuit_breaker._failure_count = 5
        circuit_breaker._success_count = 2

        await circuit_breaker.reset()

        assert circuit_breaker._state == CircuitState.CLOSED
        assert circuit_breaker._failure_count == 0
        assert circuit_breaker._success_count == 0


# =============================================================================
# CIRCUIT BREAKER OPERATION TESTS
# =============================================================================

class TestCircuitBreakerOperations:
    """Tests for circuit breaker call operations"""

    @pytest.mark.asyncio
    async def test_successful_call(self, circuit_breaker):
        """Test successful call passes through"""
        async def operation():
            return {"result": "success"}

        result = await circuit_breaker.call(operation)

        assert result == {"result": "success"}
        assert circuit_breaker._stats["successful_calls"] == 1

    @pytest.mark.asyncio
    async def test_failed_call_increments_failure_count(self, circuit_breaker):
        """Test failed call increments failure counter"""
        async def failing_operation():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_operation, use_fallback=False)

        assert circuit_breaker._failure_count >= 1
        assert circuit_breaker._stats["failed_calls"] == 1

    @pytest.mark.asyncio
    async def test_retries_on_retryable_exception(self, circuit_config, circuit_breaker):
        """Test retries on retryable exceptions"""
        call_count = 0

        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Temporary timeout")
            return "success"

        # Should retry and eventually succeed
        result = await circuit_breaker.call(flaky_operation, use_fallback=False)

        assert result == "success"
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_exception(self, circuit_breaker):
        """Test no retry on non-retryable exceptions"""
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retryable error")

        with pytest.raises(ValueError):
            await circuit_breaker.call(operation, use_fallback=False)

        # Should only be called once (no retries)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_get_status_returns_correct_info(self, circuit_breaker):
        """Test get_status returns comprehensive status"""
        status = circuit_breaker.get_status()

        assert "service_name" in status
        assert "state" in status
        assert "failure_count" in status
        assert "success_count" in status
        assert "is_open" in status
        assert status["service_name"] == "test_service"


# =============================================================================
# FALLBACK REGISTRY TESTS
# =============================================================================

class TestFallbackRegistry:
    """Tests for FallbackRegistry"""

    def test_register_fallback(self, fallback_registry):
        """Test registering a fallback handler"""
        async def fallback_handler():
            return "fallback_result"

        fallback_registry.register("test_service", "operation", fallback_handler)

        handler = fallback_registry.get_fallback("test_service", "operation")
        assert handler == fallback_handler

    def test_register_default_fallback(self, fallback_registry):
        """Test registering a default fallback handler"""
        async def default_handler():
            return "default_result"

        fallback_registry.register_default("test_service", default_handler)

        # Should return default for unknown operation
        handler = fallback_registry.get_fallback("test_service", "unknown_operation")
        assert handler == default_handler

    def test_get_nonexistent_fallback_returns_none(self, fallback_registry):
        """Test getting non-existent fallback returns None"""
        handler = fallback_registry.get_fallback("nonexistent", "operation")
        assert handler is None

    def test_specific_fallback_overrides_default(self, fallback_registry):
        """Test specific fallback takes precedence over default"""
        async def default_handler():
            return "default"

        async def specific_handler():
            return "specific"

        fallback_registry.register_default("test_service", default_handler)
        fallback_registry.register("test_service", "specific_op", specific_handler)

        handler = fallback_registry.get_fallback("test_service", "specific_op")
        assert handler == specific_handler


# =============================================================================
# CIRCUIT BREAKER WITH FALLBACK TESTS
# =============================================================================

class TestCircuitBreakerWithFallback:
    """Tests for circuit breaker fallback behavior"""

    @pytest.mark.asyncio
    async def test_uses_fallback_when_circuit_open(self, circuit_breaker, fallback_registry):
        """Test fallback is used when circuit is open"""
        # Register fallback
        async def fallback():
            return "fallback_result"

        fallback_registry.register("test_service", "default", fallback)
        circuit_breaker.fallback_registry = fallback_registry

        # Force circuit open
        circuit_breaker._state = CircuitState.OPEN
        circuit_breaker._last_failure_time = time.time()

        async def operation():
            return "normal_result"

        result = await circuit_breaker.call(operation, use_fallback=True)

        assert result == "fallback_result"
        assert circuit_breaker._stats["fallback_calls"] == 1

    @pytest.mark.asyncio
    async def test_raises_when_no_fallback_and_circuit_open(self, circuit_breaker):
        """Test raises CircuitOpenError when no fallback available"""
        # Force circuit open
        circuit_breaker._state = CircuitState.OPEN
        circuit_breaker._last_failure_time = time.time()

        async def operation():
            return "result"

        with pytest.raises(CircuitOpenError):
            await circuit_breaker.call(operation, use_fallback=False)


# =============================================================================
# RESILIENT SUPABASE CLIENT TESTS
# =============================================================================

class TestResilientSupabaseClient:
    """Tests for ResilientSupabaseClient"""

    def test_initialization(self):
        """Test client initialization"""
        with patch.dict('os.environ', {
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_SERVICE_KEY': 'test-key'
        }):
            client = ResilientSupabaseClient()

            assert client.supabase_url == 'https://test.supabase.co'
            assert client.supabase_key == 'test-key'
            assert client._client is None  # Lazy initialization

    def test_initialization_without_credentials(self):
        """Test client with missing credentials"""
        with patch.dict('os.environ', {}, clear=True):
            client = ResilientSupabaseClient()
            assert not client.is_available

    def test_circuit_breaker_access(self):
        """Test access to circuit breaker"""
        with patch.dict('os.environ', {
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_SERVICE_KEY': 'test-key'
        }):
            client = ResilientSupabaseClient()

            assert client.circuit_breaker is not None
            assert isinstance(client.circuit_breaker, CircuitBreaker)

    @pytest.mark.asyncio
    async def test_select_operation(self, mock_supabase_client):
        """Test select operation with mocked client"""
        with patch.dict('os.environ', {
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_SERVICE_KEY': 'test-key'
        }):
            client = ResilientSupabaseClient()
            client._client = mock_supabase_client
            client._initialized = True

            # Reset circuit to ensure it's closed
            await client._circuit.reset()

            result = await client.select("test_table", columns="*", limit=10)

            assert result == [{"id": 1, "name": "test"}]
            mock_supabase_client.table.assert_called_with("test_table")

    @pytest.mark.asyncio
    async def test_insert_operation(self, mock_supabase_client):
        """Test insert operation with mocked client"""
        with patch.dict('os.environ', {
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_SERVICE_KEY': 'test-key'
        }):
            client = ResilientSupabaseClient()
            client._client = mock_supabase_client
            client._initialized = True

            await client._circuit.reset()

            data = {"name": "test_item"}
            result = await client.insert("test_table", data)

            assert result == [{"id": 1, "name": "test"}]

    @pytest.mark.asyncio
    async def test_update_operation(self, mock_supabase_client):
        """Test update operation with mocked client"""
        with patch.dict('os.environ', {
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_SERVICE_KEY': 'test-key'
        }):
            client = ResilientSupabaseClient()
            client._client = mock_supabase_client
            client._initialized = True

            await client._circuit.reset()

            result = await client.update(
                "test_table",
                {"name": "updated"},
                {"id": 1}
            )

            assert result == [{"id": 1, "name": "test"}]

    @pytest.mark.asyncio
    async def test_delete_operation(self, mock_supabase_client):
        """Test delete operation with mocked client"""
        with patch.dict('os.environ', {
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_SERVICE_KEY': 'test-key'
        }):
            client = ResilientSupabaseClient()
            client._client = mock_supabase_client
            client._initialized = True

            await client._circuit.reset()

            result = await client.delete("test_table", {"id": 1})

            assert result == [{"id": 1, "name": "test"}]

    def test_get_stats(self):
        """Test get_stats returns comprehensive statistics"""
        with patch.dict('os.environ', {
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_SERVICE_KEY': 'test-key'
        }):
            client = ResilientSupabaseClient()
            stats = client.get_stats()

            assert "operations_total" in stats
            assert "operations_successful" in stats
            assert "operations_failed" in stats
            assert "circuit_status" in stats
            assert "service_name" in stats


# =============================================================================
# CIRCUIT BREAKER REGISTRY TESTS
# =============================================================================

class TestCircuitBreakerRegistry:
    """Tests for global circuit breaker registry functions"""

    def test_get_circuit_breaker_sync_creates_new(self):
        """Test sync creation of circuit breaker"""
        config = CircuitBreakerConfig()

        # Clear registry first
        _circuit_registry.clear()

        cb = get_circuit_breaker_sync("new_test_service", config)

        assert cb is not None
        assert "new_test_service" in _circuit_registry

    def test_get_circuit_breaker_sync_returns_existing(self):
        """Test sync retrieval of existing circuit breaker"""
        config = CircuitBreakerConfig()

        _circuit_registry.clear()

        cb1 = get_circuit_breaker_sync("singleton_service", config)
        cb2 = get_circuit_breaker_sync("singleton_service", config)

        assert cb1 is cb2

    def test_get_all_circuit_statuses(self):
        """Test getting all circuit statuses"""
        _circuit_registry.clear()

        # Create some circuits
        get_circuit_breaker_sync("service_a", CircuitBreakerConfig())
        get_circuit_breaker_sync("service_b", CircuitBreakerConfig())

        statuses = get_all_circuit_statuses()

        assert "service_a" in statuses
        assert "service_b" in statuses

    @pytest.mark.asyncio
    async def test_reset_circuit(self):
        """Test resetting a circuit breaker"""
        _circuit_registry.clear()

        cb = get_circuit_breaker_sync("reset_test_service", CircuitBreakerConfig())
        cb._failure_count = 5
        cb._state = CircuitState.OPEN

        await reset_circuit("reset_test_service")

        assert cb._failure_count == 0
        assert cb._state == CircuitState.CLOSED


# =============================================================================
# CIRCUIT BREAKER API ENDPOINT TESTS
# =============================================================================

class TestCircuitBreakerAPIEndpoints:
    """Tests for circuit breaker management API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_get_all_circuit_states(self, client):
        """Test getting all circuit breaker states"""
        # Ensure at least one circuit exists
        _circuit_registry.clear()
        get_circuit_breaker_sync("api_test_service", CircuitBreakerConfig())

        response = client.get("/api/system/circuit-breakers")

        assert response.status_code == 200
        data = response.json()
        assert "circuits" in data
        assert "total_circuits" in data
        assert "timestamp" in data

    def test_get_single_circuit_state(self, client):
        """Test getting single circuit breaker state"""
        _circuit_registry.clear()
        get_circuit_breaker_sync("single_test_service", CircuitBreakerConfig())

        response = client.get("/api/system/circuit-breakers/single_test_service")

        assert response.status_code == 200
        data = response.json()
        assert data["service_name"] == "single_test_service"
        assert "state" in data
        assert "failure_count" in data

    def test_get_nonexistent_circuit_returns_404(self, client):
        """Test getting non-existent circuit returns 404"""
        response = client.get("/api/system/circuit-breakers/nonexistent_service")

        assert response.status_code == 404

    def test_reset_circuit_endpoint(self, client):
        """Test resetting circuit breaker via API"""
        _circuit_registry.clear()
        cb = get_circuit_breaker_sync("reset_api_service", CircuitBreakerConfig())
        cb._state = CircuitState.OPEN

        response = client.post("/api/system/circuit-breakers/reset_api_service/reset")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["service_name"] == "reset_api_service"

    def test_reset_nonexistent_circuit_returns_404(self, client):
        """Test resetting non-existent circuit returns 404"""
        response = client.post("/api/system/circuit-breakers/nonexistent/reset")

        assert response.status_code == 404

    def test_get_circuit_config(self, client):
        """Test getting circuit breaker configuration"""
        _circuit_registry.clear()
        get_circuit_breaker_sync("config_test_service", CircuitBreakerConfig())

        response = client.get("/api/system/circuit-breakers/config_test_service/config")

        assert response.status_code == 200
        data = response.json()
        assert data["service_name"] == "config_test_service"
        assert "failure_threshold" in data
        assert "recovery_timeout" in data

    def test_get_system_health_summary(self, client):
        """Test getting system health summary"""
        _circuit_registry.clear()

        # Create circuits in different states
        cb1 = get_circuit_breaker_sync("healthy_service", CircuitBreakerConfig())
        cb1._state = CircuitState.CLOSED

        cb2 = get_circuit_breaker_sync("degraded_service", CircuitBreakerConfig())
        cb2._state = CircuitState.HALF_OPEN

        response = client.get("/api/system/circuit-breakers/health/summary")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "healthy_services" in data
        assert "degraded_services" in data
        assert "unhealthy_services" in data

    def test_get_metrics_summary(self, client):
        """Test getting metrics summary"""
        _circuit_registry.clear()
        get_circuit_breaker_sync("metrics_test_service", CircuitBreakerConfig())

        response = client.get("/api/system/circuit-breakers/metrics/summary")

        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "by_service" in data
        assert "total_calls" in data["summary"]


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker system"""

    @pytest.mark.asyncio
    async def test_full_circuit_lifecycle(self, circuit_config):
        """Test full circuit breaker lifecycle: closed -> open -> half-open -> closed"""
        circuit = CircuitBreaker("lifecycle_test", circuit_config)

        # 1. Start closed
        assert circuit._state == CircuitState.CLOSED

        # 2. Fail until open
        async def failing_operation():
            raise ConnectionError("Simulated failure")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await circuit.call(failing_operation, use_fallback=False)

        assert circuit._state == CircuitState.OPEN

        # 3. Wait for recovery timeout
        await asyncio.sleep(1.1)  # Just past recovery timeout

        # 4. Successful calls in half-open
        async def successful_operation():
            return "success"

        # First call transitions to half-open
        result = await circuit.call(successful_operation, use_fallback=False)
        assert result == "success"

        # Second call should close the circuit
        result = await circuit.call(successful_operation, use_fallback=False)
        assert result == "success"

        assert circuit._state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_with_retry_and_fallback(self):
        """Test circuit breaker with retry logic and fallback"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            max_retries=2,
            retry_base_delay=0.05,
            retryable_exceptions=(ConnectionError,),
        )

        registry = FallbackRegistry()
        async def fallback():
            return "fallback_value"

        registry.register_default("retry_fallback_test", fallback)

        circuit = CircuitBreaker("retry_fallback_test", config, fallback_registry=registry)

        call_count = 0

        async def flaky_then_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        # This should retry, then fail, then use fallback
        # Force circuit open first
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await circuit.call(flaky_then_fail, use_fallback=False)

        assert circuit._state == CircuitState.OPEN

        # Now call with fallback
        result = await circuit.call(flaky_then_fail, use_fallback=True)
        assert result == "fallback_value"


# =============================================================================
# SUPABASE CONFIGURATION TESTS
# =============================================================================

class TestSupabaseConfiguration:
    """Tests for Supabase-specific circuit breaker configuration"""

    def test_supabase_config_values(self):
        """Test Supabase circuit breaker configuration"""
        assert SUPABASE_CONFIG.failure_threshold == 5
        assert SUPABASE_CONFIG.success_threshold == 3
        assert SUPABASE_CONFIG.recovery_timeout == 30.0
        assert SUPABASE_CONFIG.max_retries == 3
        assert SUPABASE_CONFIG.operation_timeout == 15.0

    def test_supabase_retryable_exceptions(self):
        """Test Supabase retryable exceptions include HTTP errors"""
        from httpx import HTTPError, ConnectError, TimeoutException

        assert HTTPError in SUPABASE_CONFIG.retryable_exceptions
        assert ConnectError in SUPABASE_CONFIG.retryable_exceptions
        assert TimeoutException in SUPABASE_CONFIG.retryable_exceptions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
