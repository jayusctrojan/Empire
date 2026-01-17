"""
Empire v7.3 - Circuit Breaker Tests (Task 174 - Production Readiness US5)

Tests for circuit breaker pattern implementation per spec requirements:
- FR-021: LlamaIndex circuit breaker (5 failures, 30s recovery)
- FR-022: CrewAI circuit breaker (3 failures, 60s recovery)
- FR-023: Ollama circuit breaker (5 failures, 15s recovery)
- FR-024: Neo4j circuit breaker (3 failures, 30s recovery)
- FR-025: B2 storage circuit breaker (5 failures, 60s recovery)
- FR-026: Expose states via /api/system/circuit-breakers endpoint

Author: Claude Code
Date: 2025-01-16
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient


# =============================================================================
# CIRCUIT BREAKER SERVICE TESTS
# =============================================================================


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration."""

    def test_default_config_values(self):
        """Test default configuration values."""
        from app.services.circuit_breaker import CircuitBreakerConfig

        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.recovery_timeout == 60.0
        assert config.max_retries == 3
        assert config.retry_base_delay == 1.0
        assert config.retry_max_delay == 30.0
        assert config.retry_multiplier == 2.0
        assert config.operation_timeout == 30.0
        assert config.half_open_max_calls == 3

    def test_custom_config_values(self):
        """Test custom configuration values."""
        from app.services.circuit_breaker import CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=5,
            recovery_timeout=120.0,
            max_retries=5,
        )
        assert config.failure_threshold == 10
        assert config.success_threshold == 5
        assert config.recovery_timeout == 120.0
        assert config.max_retries == 5


class TestServiceConfigs:
    """Test service-specific configurations per FR-021 to FR-025."""

    def test_service_configs_exist(self):
        """Test that SERVICE_CONFIGS dictionary exists and has required services."""
        from app.services.circuit_breaker import SERVICE_CONFIGS

        required_services = [
            "llamaindex",
            "crewai",
            "ollama",
            "neo4j",
            "b2",
            "default",
        ]
        for service in required_services:
            assert service in SERVICE_CONFIGS, f"Missing config for {service}"

    def test_fr021_llamaindex_config(self):
        """FR-021: LlamaIndex circuit breaker (5 failures, 30s recovery)."""
        from app.services.circuit_breaker import SERVICE_CONFIGS

        config = SERVICE_CONFIGS["llamaindex"]
        assert config.failure_threshold == 5, "LlamaIndex should have 5 failure threshold"
        assert config.recovery_timeout == 30.0, "LlamaIndex should have 30s recovery timeout"

    def test_fr022_crewai_config(self):
        """FR-022: CrewAI circuit breaker (3 failures, 60s recovery)."""
        from app.services.circuit_breaker import SERVICE_CONFIGS

        config = SERVICE_CONFIGS["crewai"]
        assert config.failure_threshold == 3, "CrewAI should have 3 failure threshold"
        assert config.recovery_timeout == 60.0, "CrewAI should have 60s recovery timeout"

    def test_fr023_ollama_config(self):
        """FR-023: Ollama circuit breaker (5 failures, 15s recovery)."""
        from app.services.circuit_breaker import SERVICE_CONFIGS

        config = SERVICE_CONFIGS["ollama"]
        assert config.failure_threshold == 5, "Ollama should have 5 failure threshold"
        assert config.recovery_timeout == 15.0, "Ollama should have 15s recovery timeout"

    def test_fr024_neo4j_config(self):
        """FR-024: Neo4j circuit breaker (3 failures, 30s recovery)."""
        from app.services.circuit_breaker import SERVICE_CONFIGS

        config = SERVICE_CONFIGS["neo4j"]
        assert config.failure_threshold == 3, "Neo4j should have 3 failure threshold"
        assert config.recovery_timeout == 30.0, "Neo4j should have 30s recovery timeout"

    def test_fr025_b2_config(self):
        """FR-025: B2 storage circuit breaker (5 failures, 60s recovery)."""
        from app.services.circuit_breaker import SERVICE_CONFIGS

        config = SERVICE_CONFIGS["b2"]
        assert config.failure_threshold == 5, "B2 should have 5 failure threshold"
        assert config.recovery_timeout == 60.0, "B2 should have 60s recovery timeout"

    def test_get_service_config_returns_correct_config(self):
        """Test get_service_config returns correct configuration."""
        from app.services.circuit_breaker import get_service_config, SERVICE_CONFIGS

        for service_name in SERVICE_CONFIGS:
            config = get_service_config(service_name)
            assert config == SERVICE_CONFIGS[service_name]

    def test_get_service_config_returns_default_for_unknown(self):
        """Test get_service_config returns default for unknown service."""
        from app.services.circuit_breaker import get_service_config, SERVICE_CONFIGS

        config = get_service_config("unknown_service")
        assert config == SERVICE_CONFIGS["default"]


class TestCircuitState:
    """Test circuit breaker state enum."""

    def test_circuit_states_exist(self):
        """Test that all circuit states are defined."""
        from app.services.circuit_breaker import CircuitState

        assert CircuitState.CLOSED.value == 0
        assert CircuitState.HALF_OPEN.value == 1
        assert CircuitState.OPEN.value == 2


class TestCircuitOpenError:
    """Test CircuitOpenError exception."""

    def test_circuit_open_error_attributes(self):
        """Test CircuitOpenError has correct attributes."""
        from app.services.circuit_breaker import CircuitOpenError

        error = CircuitOpenError("test_service", 30.0)
        assert error.service_name == "test_service"
        assert error.retry_after == 30.0
        assert "test_service" in str(error)
        assert "30.0" in str(error)


class TestCircuitBreaker:
    """Test CircuitBreaker class."""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes with correct state."""
        from app.services.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test_service")
        assert cb.service_name == "test_service"
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed is True
        assert cb.is_open is False
        assert cb.is_half_open is False

    def test_circuit_breaker_with_custom_config(self):
        """Test circuit breaker with custom configuration."""
        from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=45.0,
        )
        cb = CircuitBreaker("test_service", config=config)
        assert cb.config.failure_threshold == 10
        assert cb.config.recovery_timeout == 45.0

    def test_circuit_breaker_uses_service_config(self):
        """Test circuit breaker uses SERVICE_CONFIGS for known services."""
        from app.services.circuit_breaker import CircuitBreaker, SERVICE_CONFIGS

        cb = CircuitBreaker("llamaindex")
        assert cb.config == SERVICE_CONFIGS["llamaindex"]

    @pytest.mark.asyncio
    async def test_successful_call_keeps_circuit_closed(self):
        """Test that successful calls keep the circuit closed."""
        from app.services.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test_service")

        async def success_func():
            return "success"

        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failures_open_circuit(self):
        """Test that failures open the circuit after threshold."""
        from app.services.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitState,
        )

        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
            max_retries=1,  # Disable retries for faster test
        )
        cb = CircuitBreaker("test_service", config=config)

        async def failing_func():
            raise ConnectionError("Connection failed")

        # Trigger failures up to threshold
        for i in range(3):
            try:
                await cb.call(failing_func, use_fallback=False)
            except ConnectionError:
                pass

        # Circuit should be open after threshold failures
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_requests(self):
        """Test that open circuit rejects requests immediately."""
        from app.services.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitState,
            CircuitOpenError,
        )

        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=60.0,
            max_retries=1,
        )
        cb = CircuitBreaker("test_service", config=config)

        async def failing_func():
            raise ConnectionError("Connection failed")

        # Open the circuit
        for i in range(2):
            try:
                await cb.call(failing_func, use_fallback=False)
            except ConnectionError:
                pass

        assert cb.state == CircuitState.OPEN

        # Next call should be rejected immediately
        with pytest.raises(CircuitOpenError) as exc_info:
            await cb.call(failing_func, use_fallback=False)

        assert exc_info.value.service_name == "test_service"

    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open(self):
        """Test circuit transitions to half-open after recovery timeout."""
        from app.services.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitState,
        )

        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,  # Very short for testing
            max_retries=1,
        )
        cb = CircuitBreaker("test_service", config=config)

        async def failing_func():
            raise ConnectionError("Connection failed")

        # Open the circuit
        for i in range(2):
            try:
                await cb.call(failing_func, use_fallback=False)
            except ConnectionError:
                pass

        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Check state - should transition on next call attempt
        await cb._check_state()
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self):
        """Test successful calls in half-open state close the circuit."""
        from app.services.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitState,
        )

        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            recovery_timeout=0.1,
            max_retries=1,
        )
        cb = CircuitBreaker("test_service", config=config)

        call_count = 0

        async def sometimes_failing_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Connection failed")
            return "success"

        # Open the circuit
        for i in range(2):
            try:
                await cb.call(sometimes_failing_func, use_fallback=False)
            except ConnectionError:
                pass

        # Wait for recovery and check state
        await asyncio.sleep(0.15)
        await cb._check_state()
        assert cb.state == CircuitState.HALF_OPEN

        # Successful calls should close the circuit
        for i in range(2):
            await cb.call(sometimes_failing_func, use_fallback=False)

        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_manual_reset(self):
        """Test manual circuit reset."""
        from app.services.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitState,
        )

        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=60.0,
            max_retries=1,
        )
        cb = CircuitBreaker("test_service", config=config)

        async def failing_func():
            raise ConnectionError("Connection failed")

        # Open the circuit
        for i in range(2):
            try:
                await cb.call(failing_func, use_fallback=False)
            except ConnectionError:
                pass

        assert cb.state == CircuitState.OPEN

        # Manual reset
        await cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_get_status_returns_correct_data(self):
        """Test get_status returns expected data structure."""
        from app.services.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test_service")
        status = cb.get_status()

        assert status["service_name"] == "test_service"
        assert status["state"] == "CLOSED"
        assert "failure_count" in status
        assert "success_count" in status
        assert "failure_threshold" in status
        assert "recovery_timeout" in status
        assert "is_open" in status
        assert "total_calls" in status
        assert "total_failures" in status
        assert "total_successes" in status


class TestFallbackRegistry:
    """Test FallbackRegistry class."""

    def test_fallback_registry_initialization(self):
        """Test fallback registry initializes empty."""
        from app.services.circuit_breaker import FallbackRegistry

        registry = FallbackRegistry()
        assert registry.list_fallbacks() == {}

    @pytest.mark.asyncio
    async def test_register_and_get_fallback(self):
        """Test registering and retrieving fallback handlers."""
        from app.services.circuit_breaker import FallbackRegistry

        registry = FallbackRegistry()

        async def fallback_handler(*args, **kwargs):
            return "fallback_result"

        registry.register("test_service", "query", fallback_handler)
        retrieved = registry.get_fallback("test_service", "query")

        assert retrieved == fallback_handler
        result = await retrieved()
        assert result == "fallback_result"

    def test_register_default_fallback(self):
        """Test registering default fallback handler."""
        from app.services.circuit_breaker import FallbackRegistry

        registry = FallbackRegistry()

        async def default_handler(*args, **kwargs):
            return "default_result"

        registry.register_default("test_service", default_handler)
        retrieved = registry.get_fallback("test_service", "unknown_operation")

        assert retrieved == default_handler

    def test_has_fallback(self):
        """Test has_fallback check."""
        from app.services.circuit_breaker import FallbackRegistry

        registry = FallbackRegistry()

        async def handler():
            pass

        assert registry.has_fallback("test_service", "op") is False
        registry.register("test_service", "op", handler)
        assert registry.has_fallback("test_service", "op") is True

    def test_list_fallbacks(self):
        """Test listing registered fallbacks."""
        from app.services.circuit_breaker import FallbackRegistry

        registry = FallbackRegistry()

        async def handler():
            pass

        registry.register("service1", "op1", handler)
        registry.register("service1", "op2", handler)
        registry.register("service2", "op1", handler)

        fallbacks = registry.list_fallbacks()
        assert "service1" in fallbacks
        assert "service2" in fallbacks
        assert "op1" in fallbacks["service1"]
        assert "op2" in fallbacks["service1"]


class TestGlobalRegistry:
    """Test global circuit breaker registry functions."""

    @pytest.mark.asyncio
    async def test_get_circuit_breaker_creates_new(self):
        """Test get_circuit_breaker creates new circuit if not exists."""
        from app.services.circuit_breaker import (
            get_circuit_breaker,
            _circuit_registry,
        )

        # Clean up any existing test circuit
        if "test_global_new" in _circuit_registry:
            del _circuit_registry["test_global_new"]

        cb = await get_circuit_breaker("test_global_new")
        assert cb.service_name == "test_global_new"
        assert "test_global_new" in _circuit_registry

        # Cleanup
        del _circuit_registry["test_global_new"]

    @pytest.mark.asyncio
    async def test_get_circuit_breaker_returns_existing(self):
        """Test get_circuit_breaker returns existing circuit."""
        from app.services.circuit_breaker import (
            get_circuit_breaker,
            _circuit_registry,
        )

        # Clean up any existing test circuit
        if "test_global_existing" in _circuit_registry:
            del _circuit_registry["test_global_existing"]

        cb1 = await get_circuit_breaker("test_global_existing")
        cb2 = await get_circuit_breaker("test_global_existing")
        assert cb1 is cb2

        # Cleanup
        del _circuit_registry["test_global_existing"]

    def test_get_circuit_breaker_sync(self):
        """Test synchronous circuit breaker retrieval."""
        from app.services.circuit_breaker import (
            get_circuit_breaker_sync,
            _circuit_registry,
        )

        # Clean up any existing test circuit
        if "test_sync" in _circuit_registry:
            del _circuit_registry["test_sync"]

        cb = get_circuit_breaker_sync("test_sync")
        assert cb.service_name == "test_sync"

        # Cleanup
        del _circuit_registry["test_sync"]

    def test_get_all_circuit_statuses(self):
        """Test getting all circuit statuses."""
        from app.services.circuit_breaker import (
            get_all_circuit_statuses,
            get_circuit_breaker_sync,
            _circuit_registry,
        )

        # Create some test circuits
        get_circuit_breaker_sync("test_status_1")
        get_circuit_breaker_sync("test_status_2")

        statuses = get_all_circuit_statuses()
        assert "test_status_1" in statuses
        assert "test_status_2" in statuses

        # Cleanup
        del _circuit_registry["test_status_1"]
        del _circuit_registry["test_status_2"]

    def test_list_registered_circuits(self):
        """Test listing registered circuits."""
        from app.services.circuit_breaker import (
            list_registered_circuits,
            get_circuit_breaker_sync,
            _circuit_registry,
        )

        # Create test circuit
        get_circuit_breaker_sync("test_list")

        circuits = list_registered_circuits()
        assert "test_list" in circuits

        # Cleanup
        del _circuit_registry["test_list"]

    @pytest.mark.asyncio
    async def test_reset_circuit(self):
        """Test resetting a specific circuit."""
        from app.services.circuit_breaker import (
            reset_circuit,
            get_circuit_breaker,
            _circuit_registry,
            CircuitState,
        )

        cb = await get_circuit_breaker("test_reset")

        # Manually set to open state for testing
        cb._state = CircuitState.OPEN

        result = await reset_circuit("test_reset")
        assert result is True
        assert cb.state == CircuitState.CLOSED

        # Cleanup
        del _circuit_registry["test_reset"]

    @pytest.mark.asyncio
    async def test_reset_circuit_not_found(self):
        """Test resetting non-existent circuit returns False."""
        from app.services.circuit_breaker import reset_circuit

        result = await reset_circuit("nonexistent_circuit")
        assert result is False

    @pytest.mark.asyncio
    async def test_reset_all_circuits(self):
        """Test resetting all circuits."""
        from app.services.circuit_breaker import (
            reset_all_circuits,
            get_circuit_breaker,
            _circuit_registry,
            CircuitState,
        )

        cb1 = await get_circuit_breaker("test_reset_all_1")
        cb2 = await get_circuit_breaker("test_reset_all_2")

        # Set to open
        cb1._state = CircuitState.OPEN
        cb2._state = CircuitState.OPEN

        count = await reset_all_circuits()
        assert count >= 2

        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED

        # Cleanup
        del _circuit_registry["test_reset_all_1"]
        del _circuit_registry["test_reset_all_2"]


# =============================================================================
# API ENDPOINT TESTS (FR-026)
# =============================================================================


class TestCircuitBreakerAPI:
    """Test circuit breaker API endpoints (FR-026)."""

    @pytest.fixture
    def client(self):
        """Create test client with circuit breaker routes."""
        from app.routes.circuit_breakers import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_get_circuit_states_endpoint(self, client):
        """FR-026: Test /api/system/circuit-breakers endpoint returns states."""
        response = client.get("/api/system/circuit-breakers")
        assert response.status_code == 200

        data = response.json()
        assert "circuits" in data
        assert "total_circuits" in data
        assert "open_circuits" in data
        assert "timestamp" in data

    def test_get_circuit_states_response_format(self, client):
        """Test circuit states response matches expected format."""
        from app.services.circuit_breaker import get_circuit_breaker_sync, _circuit_registry

        # Create a test circuit
        get_circuit_breaker_sync("api_test_service")

        response = client.get("/api/system/circuit-breakers")
        assert response.status_code == 200

        data = response.json()
        if "api_test_service" in data["circuits"]:
            circuit = data["circuits"]["api_test_service"]
            assert "service_name" in circuit
            assert "state" in circuit
            assert "failure_count" in circuit
            assert "is_open" in circuit

        # Cleanup
        if "api_test_service" in _circuit_registry:
            del _circuit_registry["api_test_service"]

    def test_get_single_circuit_state(self, client):
        """Test getting single circuit breaker state."""
        from app.services.circuit_breaker import get_circuit_breaker_sync, _circuit_registry

        # Create test circuit
        get_circuit_breaker_sync("single_test")

        response = client.get("/api/system/circuit-breakers/single_test")
        assert response.status_code == 200

        data = response.json()
        assert data["service_name"] == "single_test"
        assert data["state"] == "CLOSED"

        # Cleanup
        del _circuit_registry["single_test"]

    def test_get_single_circuit_not_found(self, client):
        """Test 404 when circuit breaker not found."""
        response = client.get("/api/system/circuit-breakers/nonexistent_service")
        assert response.status_code == 404

    def test_reset_circuit_endpoint(self, client):
        """Test POST /api/system/circuit-breakers/{name}/reset endpoint."""
        from app.services.circuit_breaker import (
            get_circuit_breaker_sync,
            _circuit_registry,
            CircuitState,
        )

        # Create and open a circuit
        cb = get_circuit_breaker_sync("reset_test")
        cb._state = CircuitState.OPEN

        response = client.post("/api/system/circuit-breakers/reset_test/reset")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["previous_state"] == "OPEN"
        assert data["new_state"] == "CLOSED"

        # Cleanup
        del _circuit_registry["reset_test"]

    def test_reset_circuit_not_found(self, client):
        """Test 404 when resetting non-existent circuit."""
        response = client.post("/api/system/circuit-breakers/nonexistent/reset")
        assert response.status_code == 404

    def test_get_circuit_config(self, client):
        """Test GET /api/system/circuit-breakers/{name}/config endpoint."""
        from app.services.circuit_breaker import get_circuit_breaker_sync, _circuit_registry

        # Create test circuit
        get_circuit_breaker_sync("config_test")

        response = client.get("/api/system/circuit-breakers/config_test/config")
        assert response.status_code == 200

        data = response.json()
        assert data["service_name"] == "config_test"
        assert "failure_threshold" in data
        assert "recovery_timeout" in data
        assert "max_retries" in data

        # Cleanup
        del _circuit_registry["config_test"]

    def test_get_circuit_config_not_found(self, client):
        """Test 404 when getting config for non-existent circuit."""
        response = client.get("/api/system/circuit-breakers/nonexistent/config")
        assert response.status_code == 404

    def test_system_health_summary(self, client):
        """Test GET /api/system/circuit-breakers/health/summary endpoint."""
        response = client.get("/api/system/circuit-breakers/health/summary")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "healthy_services" in data
        assert "degraded_services" in data
        assert "unhealthy_services" in data
        assert "total_services" in data
        assert "timestamp" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_metrics_summary(self, client):
        """Test GET /api/system/circuit-breakers/metrics/summary endpoint."""
        response = client.get("/api/system/circuit-breakers/metrics/summary")
        assert response.status_code == 200

        data = response.json()
        assert "summary" in data
        assert "by_service" in data
        assert "timestamp" in data
        assert "total_calls" in data["summary"]
        assert "overall_success_rate_percent" in data["summary"]


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker with services."""

    @pytest.mark.asyncio
    async def test_llamaindex_circuit_opens_after_5_failures(self):
        """Test LlamaIndex circuit opens after 5 failures (FR-021)."""
        from app.services.circuit_breaker import (
            CircuitBreaker,
            SERVICE_CONFIGS,
            CircuitState,
        )

        # Use LlamaIndex config with disabled retries for test speed
        config = SERVICE_CONFIGS["llamaindex"]
        config_with_no_retry = type(config)(
            failure_threshold=config.failure_threshold,
            recovery_timeout=config.recovery_timeout,
            max_retries=1,
        )

        cb = CircuitBreaker("llamaindex_test", config=config_with_no_retry)

        async def failing_llamaindex_call():
            raise ConnectionError("LlamaIndex service unavailable")

        # 5 failures should open the circuit
        for i in range(5):
            try:
                await cb.call(failing_llamaindex_call, use_fallback=False)
            except ConnectionError:
                pass

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_crewai_circuit_opens_after_3_failures(self):
        """Test CrewAI circuit opens after 3 failures (FR-022)."""
        from app.services.circuit_breaker import (
            CircuitBreaker,
            SERVICE_CONFIGS,
            CircuitState,
        )

        config = SERVICE_CONFIGS["crewai"]
        config_with_no_retry = type(config)(
            failure_threshold=config.failure_threshold,
            recovery_timeout=config.recovery_timeout,
            max_retries=1,
        )

        cb = CircuitBreaker("crewai_test", config=config_with_no_retry)

        async def failing_crewai_call():
            raise ConnectionError("CrewAI service unavailable")

        # 3 failures should open the circuit
        for i in range(3):
            try:
                await cb.call(failing_crewai_call, use_fallback=False)
            except ConnectionError:
                pass

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_neo4j_circuit_opens_after_3_failures(self):
        """Test Neo4j circuit opens after 3 failures (FR-024)."""
        from app.services.circuit_breaker import (
            CircuitBreaker,
            SERVICE_CONFIGS,
            CircuitState,
        )

        config = SERVICE_CONFIGS["neo4j"]
        config_with_no_retry = type(config)(
            failure_threshold=config.failure_threshold,
            recovery_timeout=config.recovery_timeout,
            max_retries=1,
        )

        cb = CircuitBreaker("neo4j_test", config=config_with_no_retry)

        async def failing_neo4j_call():
            raise ConnectionError("Neo4j service unavailable")

        # 3 failures should open the circuit
        for i in range(3):
            try:
                await cb.call(failing_neo4j_call, use_fallback=False)
            except ConnectionError:
                pass

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_ollama_recovery_timeout_15s(self):
        """Test Ollama has 15s recovery timeout (FR-023)."""
        from app.services.circuit_breaker import SERVICE_CONFIGS

        config = SERVICE_CONFIGS["ollama"]
        assert config.recovery_timeout == 15.0

    @pytest.mark.asyncio
    async def test_b2_recovery_timeout_60s(self):
        """Test B2 has 60s recovery timeout (FR-025)."""
        from app.services.circuit_breaker import SERVICE_CONFIGS

        config = SERVICE_CONFIGS["b2"]
        assert config.recovery_timeout == 60.0


# =============================================================================
# PROMETHEUS METRICS TESTS
# =============================================================================


class TestCircuitBreakerMetrics:
    """Test Prometheus metrics integration."""

    def test_metrics_are_defined(self):
        """Test that Prometheus metrics are defined."""
        from app.services.circuit_breaker import (
            CIRCUIT_STATE_GAUGE,
            CIRCUIT_STATE_CHANGES_COUNTER,
            CIRCUIT_REQUESTS_COUNTER,
            CIRCUIT_RESPONSE_TIME,
            CIRCUIT_REJECTIONS_COUNTER,
            CIRCUIT_FALLBACK_COUNTER,
            CIRCUIT_RETRY_COUNTER,
        )

        # These should not raise - just checking they exist
        assert CIRCUIT_STATE_GAUGE is not None
        assert CIRCUIT_STATE_CHANGES_COUNTER is not None
        assert CIRCUIT_REQUESTS_COUNTER is not None
        assert CIRCUIT_RESPONSE_TIME is not None
        assert CIRCUIT_REJECTIONS_COUNTER is not None
        assert CIRCUIT_FALLBACK_COUNTER is not None
        assert CIRCUIT_RETRY_COUNTER is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
