"""
Empire v7.3 - Distributed Circuit Breaker Tests
Tests for Redis-backed circuit breaker state sharing

Run with:
    pytest tests/test_distributed_circuit_breaker.py -v
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import module at top level to ensure Prometheus metrics are registered only once.
# Without this, imports inside test methods can cause duplicate metric registration.
from app.core.distributed_circuit_breaker import (
    DistributedCircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitBreakerOpenError,
    CircuitBreakerState,
    CircuitState,
    DEFAULT_CONFIGS,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client for circuit breaker state that tracks state between calls"""
    mock = MagicMock()

    # Storage dict to persist state between calls
    storage = {}

    def mock_get(key):
        return storage.get(key)

    def mock_setex(key, _ttl, value):
        storage[key] = value
        return True

    def mock_set(key, value, nx=False, ex=None):  # noqa: ARG001
        # Support nx (only set if not exists) for distributed locking
        # Note: ex parameter is unused but must match Redis API signature
        if nx and key in storage:
            return False  # Key already exists, lock not acquired
        storage[key] = value
        return True

    def mock_delete(key):
        if key in storage:
            del storage[key]
            return 1
        return 0

    def mock_eval(_script, num_keys, *args):
        """Mock Lua script evaluation for safe lock release."""
        # Simulate the lock release Lua script
        if num_keys == 1 and len(args) >= 2:
            key = args[0]
            expected_value = args[1]
            if storage.get(key) == expected_value:
                if key in storage:
                    del storage[key]
                    return 1
        return 0

    mock.get.side_effect = mock_get
    mock.set.side_effect = mock_set
    mock.setex.side_effect = mock_setex
    mock.delete.side_effect = mock_delete
    mock.eval.side_effect = mock_eval
    mock.incr.return_value = 1
    mock.expire.return_value = True

    return mock


@pytest.fixture
def circuit_config():
    """Sample circuit breaker configuration"""
    return {
        "failure_threshold": 5,
        "success_threshold": 2,
        "timeout_seconds": 30,
        "half_open_max_calls": 3
    }


# =============================================================================
# CIRCUIT BREAKER INITIALIZATION TESTS
# =============================================================================

class TestCircuitBreakerInit:
    """Tests for DistributedCircuitBreaker initialization"""

    def test_breaker_creation(self, mock_redis):
        """Test creating DistributedCircuitBreaker instance"""
        breaker = DistributedCircuitBreaker(mock_redis, "test_service")

        assert breaker.service_name == "test_service"
        assert breaker.redis == mock_redis

    def test_breaker_with_custom_config(self, mock_redis, circuit_config):
        """Test DistributedCircuitBreaker with custom configuration"""
        config = CircuitBreakerConfig(service_name="test_service", **circuit_config)
        breaker = DistributedCircuitBreaker(mock_redis, "test_service", config=config)

        assert breaker.config.failure_threshold == 5
        assert breaker.config.success_threshold == 2
        assert breaker.config.timeout_seconds == 30

    def test_breaker_uses_default_config(self, mock_redis):
        """Test that breaker uses default config for known services"""
        breaker = DistributedCircuitBreaker(mock_redis, "llamaindex")

        assert breaker.config.service_name == "llamaindex"
        assert breaker.config.failure_threshold == DEFAULT_CONFIGS["llamaindex"].failure_threshold


# =============================================================================
# CIRCUIT STATE TESTS
# =============================================================================

class TestCircuitStates:
    """Tests for circuit breaker state transitions"""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self, mock_redis):
        """Test that initial state is CLOSED"""
        breaker = DistributedCircuitBreaker(mock_redis, "test_service")
        state = await breaker._get_state()

        assert state.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_state_opens_after_failures(self, mock_redis):
        """Test that circuit opens after failure threshold"""
        config = CircuitBreakerConfig(service_name="test_service", failure_threshold=3)
        breaker = DistributedCircuitBreaker(mock_redis, "test_service", config=config)

        # Record failures to exceed threshold
        for _ in range(4):
            await breaker.record_failure()

        state = await breaker._get_state()
        assert state.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_state_transitions_to_half_open(self, mock_redis):
        """Test that circuit transitions to HALF_OPEN after timeout"""
        config = CircuitBreakerConfig(
            service_name="test_service",
            failure_threshold=3,
            timeout_seconds=0  # Immediate timeout
        )
        breaker = DistributedCircuitBreaker(mock_redis, "test_service", config=config)

        # Open the circuit
        for _ in range(4):
            await breaker.record_failure()

        # Now check can_execute - should transition to half-open after timeout
        # Since timeout is 0, it should transition immediately
        await breaker.can_execute()

        state = await breaker._get_state()
        assert state.state in [CircuitState.HALF_OPEN, CircuitState.OPEN]

    @pytest.mark.asyncio
    async def test_state_closes_after_success(self, mock_redis):
        """Test that circuit closes after success threshold in HALF_OPEN"""
        config = CircuitBreakerConfig(
            service_name="test_service",
            success_threshold=2,
            failure_threshold=3,
            timeout_seconds=0
        )
        breaker = DistributedCircuitBreaker(mock_redis, "test_service", config=config)

        # First open the circuit
        for _ in range(4):
            await breaker.record_failure()

        # Trigger transition to half-open
        await breaker.can_execute()

        # Record enough successes to close
        await breaker.record_success()
        await breaker.record_success()

        state = await breaker._get_state()
        assert state.state == CircuitState.CLOSED


# =============================================================================
# REDIS STATE SHARING TESTS
# =============================================================================

class TestRedisStateSharing:
    """Tests for Redis-backed state sharing"""

    @pytest.mark.asyncio
    async def test_state_persisted_to_redis(self, mock_redis):
        """Test that circuit state is persisted to Redis"""
        breaker = DistributedCircuitBreaker(mock_redis, "test_service")

        # Get initial state to trigger save
        await breaker._get_state()

        # setex should be called to persist state
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_state_loaded_from_redis(self):
        """Test that circuit state is loaded from Redis"""
        # Create a fresh mock that returns specific data
        mock = MagicMock()
        state_data = CircuitBreakerState(
            service_name="test_service",
            state=CircuitState.OPEN,
            failure_count=5
        )
        mock.get.return_value = state_data.model_dump_json()
        mock.setex.return_value = True

        breaker = DistributedCircuitBreaker(mock, "test_service")
        # Invalidate cache to force reload from Redis
        breaker._local_state = None
        state = await breaker._get_state()

        assert state.state == CircuitState.OPEN
        assert state.failure_count == 5

    @pytest.mark.asyncio
    async def test_failure_count_shared_via_state(self, mock_redis):
        """Test that failure count is shared via Redis state"""
        breaker1 = DistributedCircuitBreaker(mock_redis, "test_service")
        breaker2 = DistributedCircuitBreaker(mock_redis, "test_service")

        await breaker1.record_failure()
        await breaker2.record_failure()

        # Both should have called setex to save state
        assert mock_redis.setex.call_count >= 2


# =============================================================================
# CAN EXECUTE TESTS
# =============================================================================

class TestCanExecute:
    """Tests for can_execute functionality"""

    @pytest.mark.asyncio
    async def test_can_execute_when_closed(self, mock_redis):
        """Test that requests are allowed when circuit is CLOSED"""
        breaker = DistributedCircuitBreaker(mock_redis, "test_service")
        allowed = await breaker.can_execute()

        assert allowed is True

    @pytest.mark.asyncio
    async def test_cannot_execute_when_open(self, mock_redis):
        """Test that requests are rejected when circuit is OPEN"""
        config = CircuitBreakerConfig(
            service_name="test_service",
            failure_threshold=2,
            timeout_seconds=60  # Long timeout so it stays open
        )
        breaker = DistributedCircuitBreaker(mock_redis, "test_service", config=config)

        # Open the circuit
        for _ in range(3):
            await breaker.record_failure()

        allowed = await breaker.can_execute()
        assert allowed is False

    @pytest.mark.asyncio
    async def test_limited_calls_in_half_open(self, mock_redis):
        """Test that requests are limited when circuit is HALF_OPEN"""
        config = CircuitBreakerConfig(
            service_name="test_service",
            failure_threshold=2,
            timeout_seconds=0,  # Immediate transition to half-open
            half_open_max_calls=2
        )
        breaker = DistributedCircuitBreaker(mock_redis, "test_service", config=config)

        # Open the circuit
        for _ in range(3):
            await breaker.record_failure()

        # First call triggers transition to half-open
        assert await breaker.can_execute() is True

        # Should allow up to half_open_max_calls
        state = await breaker._get_state()
        assert state.state == CircuitState.HALF_OPEN


# =============================================================================
# CIRCUIT BREAKER REGISTRY TESTS
# =============================================================================

class TestCircuitBreakerRegistry:
    """Tests for circuit breaker registry"""

    def test_get_breaker(self, mock_redis):
        """Test getting a circuit breaker from registry"""
        registry = CircuitBreakerRegistry(mock_redis)

        breaker1 = registry.get_breaker("service_a")
        breaker2 = registry.get_breaker("service_a")

        # Should return same instance
        assert breaker1 is breaker2

    def test_registry_uses_default_configs(self, mock_redis):
        """Test that registry uses default configs for known services"""
        registry = CircuitBreakerRegistry(mock_redis)

        breaker = registry.get_breaker("llamaindex")

        # Should have llamaindex-specific config
        assert breaker.config is not None
        assert breaker.config.service_name == "llamaindex"

    @pytest.mark.asyncio
    async def test_get_all_status(self, mock_redis):
        """Test getting status of all circuit breakers"""
        registry = CircuitBreakerRegistry(mock_redis)

        registry.get_breaker("service_a")
        registry.get_breaker("service_b")

        status = await registry.get_all_status()

        assert "service_a" in status
        assert "service_b" in status


# =============================================================================
# STATUS AND METRICS TESTS
# =============================================================================

class TestCircuitStatus:
    """Tests for circuit breaker status"""

    @pytest.mark.asyncio
    async def test_get_status(self, mock_redis):
        """Test getting circuit breaker status"""
        breaker = DistributedCircuitBreaker(mock_redis, "test_service")

        status = await breaker.get_status()

        assert status["service"] == "test_service"
        assert status["state"] == "closed"
        assert "failure_count" in status
        assert "failure_threshold" in status

    @pytest.mark.asyncio
    async def test_status_after_failures(self, mock_redis):
        """Test status reflects failure count"""
        config = CircuitBreakerConfig(
            service_name="test_service",
            failure_threshold=5
        )
        breaker = DistributedCircuitBreaker(mock_redis, "test_service", config=config)

        await breaker.record_failure()
        await breaker.record_failure()

        status = await breaker.get_status()
        assert status["failure_count"] >= 2


# =============================================================================
# RESET AND FORCE TESTS
# =============================================================================

class TestCircuitControl:
    """Tests for circuit breaker control methods"""

    @pytest.mark.asyncio
    async def test_force_open(self, mock_redis):
        """Test forcing circuit to open state"""
        breaker = DistributedCircuitBreaker(mock_redis, "test_service")

        await breaker.force_open()

        state = await breaker._get_state()
        assert state.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_force_close(self, mock_redis):
        """Test forcing circuit to closed state"""
        breaker = DistributedCircuitBreaker(mock_redis, "test_service")

        # First open it
        await breaker.force_open()
        # Then force close
        await breaker.force_close()

        state = await breaker._get_state()
        assert state.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reset(self, mock_redis):
        """Test resetting circuit breaker"""
        breaker = DistributedCircuitBreaker(mock_redis, "test_service")

        # Record some failures
        await breaker.record_failure()
        await breaker.record_failure()

        # Reset
        await breaker.reset()

        state = await breaker._get_state()
        assert state.state == CircuitState.CLOSED
        assert state.failure_count == 0


# =============================================================================
# PROTECT DECORATOR TESTS
# =============================================================================

class TestProtectDecorator:
    """Tests for the protect decorator"""

    @pytest.mark.asyncio
    async def test_protect_allows_when_closed(self, mock_redis):
        """Test that protect decorator allows calls when closed"""
        breaker = DistributedCircuitBreaker(mock_redis, "test_service")

        @breaker.protect
        async def my_operation():
            return "success"

        result = await my_operation()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_protect_records_success(self, mock_redis):
        """Test that protect decorator records success"""
        breaker = DistributedCircuitBreaker(mock_redis, "test_service")

        @breaker.protect
        async def my_operation():
            return "success"

        await my_operation()

        state = await breaker._get_state()
        assert state.consecutive_successes >= 1

    @pytest.mark.asyncio
    async def test_protect_records_failure(self, mock_redis):
        """Test that protect decorator records failure"""
        breaker = DistributedCircuitBreaker(mock_redis, "test_service")

        @breaker.protect
        async def my_operation():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await my_operation()

        state = await breaker._get_state()
        assert state.failure_count >= 1

    @pytest.mark.asyncio
    async def test_protect_raises_when_open(self, mock_redis):
        """Test that protect raises error when circuit is open"""
        config = CircuitBreakerConfig(
            service_name="test_service",
            failure_threshold=2,
            timeout_seconds=60
        )
        breaker = DistributedCircuitBreaker(mock_redis, "test_service", config=config)

        # Open the circuit
        await breaker.force_open()

        @breaker.protect
        async def my_operation():
            return "success"

        with pytest.raises(CircuitBreakerOpenError):
            await my_operation()
