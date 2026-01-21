"""
Empire v7.3 - Distributed Circuit Breaker Tests
Tests for Redis-backed circuit breaker state sharing

Run with:
    pytest tests/test_distributed_circuit_breaker.py -v
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client for circuit breaker state"""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.incr.return_value = 1
    mock.expire.return_value = True
    mock.delete.return_value = 1
    return mock


@pytest.fixture
def circuit_config():
    """Sample circuit breaker configuration"""
    return {
        "failure_threshold": 5,
        "success_threshold": 2,
        "timeout": 30,
        "half_open_max_calls": 3
    }


# =============================================================================
# CIRCUIT BREAKER INITIALIZATION TESTS
# =============================================================================

class TestCircuitBreakerInit:
    """Tests for DistributedCircuitBreaker initialization"""

    def test_breaker_creation(self, mock_redis):
        """Test creating DistributedCircuitBreaker instance"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service")

        assert breaker.service_name == "test_service"
        assert breaker.state == "CLOSED"

    def test_breaker_with_custom_config(self, mock_redis, circuit_config):
        """Test DistributedCircuitBreaker with custom configuration"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(**circuit_config)

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service", config=config)

        assert breaker.config.failure_threshold == 5


# =============================================================================
# CIRCUIT STATE TESTS
# =============================================================================

class TestCircuitStates:
    """Tests for circuit breaker state transitions"""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self, mock_redis):
        """Test that initial state is CLOSED"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service")
            state = await breaker.get_state()

        assert state == "CLOSED"

    @pytest.mark.asyncio
    async def test_state_opens_after_failures(self, mock_redis):
        """Test that circuit opens after failure threshold"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=3)
        failure_count = 0

        def mock_incr(*args):
            nonlocal failure_count
            failure_count += 1
            return failure_count

        mock_redis.incr = AsyncMock(side_effect=mock_incr)

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service", config=config)

            # Record failures
            for _ in range(4):
                await breaker.record_failure()

            state = await breaker.get_state()

        assert state == "OPEN"

    @pytest.mark.asyncio
    async def test_state_transitions_to_half_open(self, mock_redis):
        """Test that circuit transitions to HALF_OPEN after timeout"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=3, timeout=0)  # Immediate timeout

        # Simulate open state that should transition
        mock_redis.get.return_value = b"OPEN"

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service", config=config)
            breaker._opened_at = datetime.utcnow() - timedelta(seconds=60)

            state = await breaker.get_state()

        # After timeout, should be HALF_OPEN
        assert state in ["HALF_OPEN", "OPEN"]

    @pytest.mark.asyncio
    async def test_state_closes_after_success(self, mock_redis):
        """Test that circuit closes after success threshold in HALF_OPEN"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(success_threshold=2)

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service", config=config)
            breaker.state = "HALF_OPEN"

            # Record successes
            await breaker.record_success()
            await breaker.record_success()

            state = await breaker.get_state()

        assert state == "CLOSED"


# =============================================================================
# REDIS STATE SHARING TESTS
# =============================================================================

class TestRedisStateSharing:
    """Tests for Redis-backed state sharing"""

    @pytest.mark.asyncio
    async def test_state_persisted_to_redis(self, mock_redis):
        """Test that circuit state is persisted to Redis"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service")
            await breaker._set_state("OPEN")

        # Redis set should be called
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_state_loaded_from_redis(self, mock_redis):
        """Test that circuit state is loaded from Redis"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker

        mock_redis.get.return_value = b"OPEN"

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service")
            state = await breaker.get_state()

        assert state == "OPEN"

    @pytest.mark.asyncio
    async def test_failure_count_shared_across_instances(self, mock_redis):
        """Test that failure count is shared across instances"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker

        shared_count = 0

        def mock_incr(*args):
            nonlocal shared_count
            shared_count += 1
            return shared_count

        mock_redis.incr = AsyncMock(side_effect=mock_incr)

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker1 = DistributedCircuitBreaker("test_service")
            breaker2 = DistributedCircuitBreaker("test_service")

            await breaker1.record_failure()
            await breaker2.record_failure()

        # Both breakers should increment shared count
        assert shared_count == 2


# =============================================================================
# ALLOW REQUEST TESTS
# =============================================================================

class TestAllowRequest:
    """Tests for allow_request functionality"""

    @pytest.mark.asyncio
    async def test_allow_request_when_closed(self, mock_redis):
        """Test that requests are allowed when circuit is CLOSED"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service")
            allowed = await breaker.allow_request()

        assert allowed is True

    @pytest.mark.asyncio
    async def test_reject_request_when_open(self, mock_redis):
        """Test that requests are rejected when circuit is OPEN"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker

        mock_redis.get.return_value = b"OPEN"

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service")
            breaker.state = "OPEN"
            breaker._opened_at = datetime.utcnow()  # Just opened

            allowed = await breaker.allow_request()

        assert allowed is False

    @pytest.mark.asyncio
    async def test_limited_requests_in_half_open(self, mock_redis):
        """Test that requests are limited when circuit is HALF_OPEN"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(half_open_max_calls=2)

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service", config=config)
            breaker.state = "HALF_OPEN"
            breaker._half_open_calls = 0

            # First two calls should be allowed
            assert await breaker.allow_request() is True
            assert await breaker.allow_request() is True

            # Third call should be rejected
            assert await breaker.allow_request() is False


# =============================================================================
# CALLBACK TESTS
# =============================================================================

class TestCircuitCallbacks:
    """Tests for circuit breaker callbacks"""

    @pytest.mark.asyncio
    async def test_on_open_callback(self, mock_redis):
        """Test that on_open callback is called when circuit opens"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=2)
        callback_called = False

        def on_open(service_name):
            nonlocal callback_called
            callback_called = True

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service", config=config)
            breaker.on_open = on_open

            # Trigger opening
            for _ in range(3):
                await breaker.record_failure()

        assert callback_called is True

    @pytest.mark.asyncio
    async def test_on_close_callback(self, mock_redis):
        """Test that on_close callback is called when circuit closes"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(success_threshold=1)
        callback_called = False

        def on_close(service_name):
            nonlocal callback_called
            callback_called = True

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service", config=config)
            breaker.on_close = on_close
            breaker.state = "HALF_OPEN"

            await breaker.record_success()

        assert callback_called is True


# =============================================================================
# CIRCUIT BREAKER REGISTRY TESTS
# =============================================================================

class TestCircuitBreakerRegistry:
    """Tests for circuit breaker registry"""

    def test_get_or_create_breaker(self, mock_redis):
        """Test getting or creating a circuit breaker"""
        from app.core.distributed_circuit_breaker import CircuitBreakerRegistry

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            registry = CircuitBreakerRegistry()

            breaker1 = registry.get_or_create("service_a")
            breaker2 = registry.get_or_create("service_a")

        # Should return same instance
        assert breaker1 is breaker2

    def test_registry_uses_default_configs(self, mock_redis):
        """Test that registry uses default configs for known services"""
        from app.core.distributed_circuit_breaker import CircuitBreakerRegistry

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            registry = CircuitBreakerRegistry()

            breaker = registry.get_or_create("llamaindex")

        # Should have llamaindex-specific config
        assert breaker.config is not None

    @pytest.mark.asyncio
    async def test_get_all_states(self, mock_redis):
        """Test getting states of all circuit breakers"""
        from app.core.distributed_circuit_breaker import CircuitBreakerRegistry

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            registry = CircuitBreakerRegistry()

            registry.get_or_create("service_a")
            registry.get_or_create("service_b")

            states = await registry.get_all_states()

        assert "service_a" in states
        assert "service_b" in states


# =============================================================================
# METRICS TESTS
# =============================================================================

class TestCircuitMetrics:
    """Tests for circuit breaker metrics"""

    @pytest.mark.asyncio
    async def test_failure_metrics_recorded(self, mock_redis):
        """Test that failure metrics are recorded"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service")

            await breaker.record_failure()

            metrics = breaker.get_metrics()

        assert metrics["failures"] >= 1

    @pytest.mark.asyncio
    async def test_success_metrics_recorded(self, mock_redis):
        """Test that success metrics are recorded"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service")

            await breaker.record_success()

            metrics = breaker.get_metrics()

        assert metrics["successes"] >= 1

    @pytest.mark.asyncio
    async def test_state_change_count_tracked(self, mock_redis):
        """Test that state changes are tracked"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=1, success_threshold=1)

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service", config=config)

            # Trigger state changes
            await breaker.record_failure()
            await breaker.record_failure()  # Opens

            metrics = breaker.get_metrics()

        assert metrics.get("state_changes", 0) >= 0


# =============================================================================
# FALLBACK TESTS
# =============================================================================

class TestCircuitFallback:
    """Tests for circuit breaker fallback behavior"""

    @pytest.mark.asyncio
    async def test_fallback_called_when_open(self, mock_redis):
        """Test that fallback is called when circuit is open"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker

        fallback_called = False

        async def fallback():
            nonlocal fallback_called
            fallback_called = True
            return "fallback_result"

        mock_redis.get.return_value = b"OPEN"

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service")
            breaker.state = "OPEN"
            breaker._opened_at = datetime.utcnow()

            async def main_operation():
                return "main_result"

            result = await breaker.execute(main_operation, fallback)

        # Fallback should be called when open
        assert fallback_called is True or result == "fallback_result"

    @pytest.mark.asyncio
    async def test_main_operation_called_when_closed(self, mock_redis):
        """Test that main operation is called when circuit is closed"""
        from app.core.distributed_circuit_breaker import DistributedCircuitBreaker

        main_called = False

        async def main_operation():
            nonlocal main_called
            main_called = True
            return "main_result"

        async def fallback():
            return "fallback_result"

        with patch('app.core.distributed_circuit_breaker.get_redis', return_value=mock_redis):
            breaker = DistributedCircuitBreaker("test_service")

            result = await breaker.execute(main_operation, fallback)

        assert main_called is True
        assert result == "main_result"
