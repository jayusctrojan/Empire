"""
Tests for API Resilience Module - Circuit Breaker for Anthropic API Calls.

Task 137: Test suite for circuit breaker implementation.
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from anthropic import RateLimitError, APIConnectionError, APIError

from app.services.api_resilience import (
    AnthropicCircuitBreaker,
    CircuitState,
    CircuitOpenError,
    ResilientAnthropicClient,
    get_circuit_breaker,
    get_all_circuit_statuses,
    reset_circuit,
    _circuit_registry,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def circuit_breaker():
    """Create a circuit breaker with short timeouts for testing."""
    return AnthropicCircuitBreaker(
        service_name="test_service",
        failure_threshold=3,
        recovery_timeout=1.0,  # Short timeout for tests
        half_open_max_calls=2,
    )


@pytest.fixture
def mock_anthropic_client():
    """Create a mock AsyncAnthropic client."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock()
    return mock


@pytest.fixture(autouse=True)
def clear_circuit_registry():
    """Clear the global circuit registry before each test."""
    _circuit_registry.clear()
    yield
    _circuit_registry.clear()


# =============================================================================
# AnthropicCircuitBreaker Tests
# =============================================================================


class TestCircuitBreakerInitialization:
    """Tests for circuit breaker initialization."""

    def test_initial_state_is_closed(self, circuit_breaker):
        """Circuit breaker should start in closed state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.is_closed is True
        assert circuit_breaker.is_open is False
        assert circuit_breaker.is_half_open is False

    def test_initial_counters_are_zero(self, circuit_breaker):
        """Initial failure and success counts should be zero."""
        status = circuit_breaker.get_status()
        assert status["failure_count"] == 0
        assert status["success_count"] == 0

    def test_service_name_set_correctly(self, circuit_breaker):
        """Service name should be set correctly."""
        assert circuit_breaker.service_name == "test_service"

    def test_thresholds_set_correctly(self, circuit_breaker):
        """Thresholds should be set correctly."""
        status = circuit_breaker.get_status()
        assert status["failure_threshold"] == 3
        assert status["recovery_timeout"] == 1.0


class TestCircuitBreakerStateTransitions:
    """Tests for circuit breaker state transitions."""

    @pytest.mark.asyncio
    async def test_remains_closed_under_threshold(self, circuit_breaker):
        """Circuit should stay closed when failures are under threshold."""
        # Record failures below threshold
        for _ in range(2):
            await circuit_breaker._record_failure(Exception("test error"))

        assert circuit_breaker.is_closed is True
        assert circuit_breaker._failure_count == 2

    @pytest.mark.asyncio
    async def test_opens_when_threshold_reached(self, circuit_breaker):
        """Circuit should open when failure threshold is reached."""
        # Record failures to reach threshold
        for _ in range(3):
            await circuit_breaker._record_failure(Exception("test error"))

        assert circuit_breaker.is_open is True
        assert circuit_breaker._failure_count == 3

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self, circuit_breaker):
        """Circuit should transition to half-open after recovery timeout."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker._record_failure(Exception("test error"))
        assert circuit_breaker.is_open is True

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Check state should trigger transition
        await circuit_breaker._check_state()

        assert circuit_breaker.is_half_open is True

    @pytest.mark.asyncio
    async def test_closes_from_half_open_after_successes(self, circuit_breaker):
        """Circuit should close after enough successes in half-open state."""
        # Transition to half-open
        for _ in range(3):
            await circuit_breaker._record_failure(Exception("test error"))
        await asyncio.sleep(1.1)
        await circuit_breaker._check_state()
        assert circuit_breaker.is_half_open is True

        # Record successful calls
        for _ in range(2):  # half_open_max_calls = 2
            await circuit_breaker._record_success()

        assert circuit_breaker.is_closed is True

    @pytest.mark.asyncio
    async def test_reopens_from_half_open_on_failure(self, circuit_breaker):
        """Circuit should reopen if failure occurs in half-open state."""
        # Transition to half-open
        for _ in range(3):
            await circuit_breaker._record_failure(Exception("test error"))
        await asyncio.sleep(1.1)
        await circuit_breaker._check_state()
        assert circuit_breaker.is_half_open is True

        # Record a failure
        await circuit_breaker._record_failure(Exception("test error"))

        assert circuit_breaker.is_open is True


class TestCircuitBreakerCallExecution:
    """Tests for circuit breaker call execution."""

    @pytest.mark.asyncio
    async def test_successful_call_in_closed_state(self, circuit_breaker):
        """Successful call should work in closed state."""
        async def mock_func():
            return "success"

        result = await circuit_breaker.call(mock_func)
        assert result == "success"
        assert circuit_breaker._success_count == 1

    @pytest.mark.asyncio
    async def test_failed_call_records_failure(self, circuit_breaker):
        """Failed call should record failure."""
        async def mock_func():
            raise Exception("API error")

        with pytest.raises(Exception, match="API error"):
            await circuit_breaker.call(mock_func)

        assert circuit_breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_rejects_call_when_open(self, circuit_breaker):
        """Calls should be rejected when circuit is open."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker._record_failure(Exception("test error"))

        async def mock_func():
            return "success"

        with pytest.raises(CircuitOpenError) as exc_info:
            await circuit_breaker.call(mock_func)

        assert exc_info.value.service_name == "test_service"
        assert exc_info.value.retry_after > 0


class TestCircuitBreakerRetryLogic:
    """Tests for retry logic."""

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit_error(self, circuit_breaker):
        """Should retry on RateLimitError."""
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Create a mock response for RateLimitError
                mock_response = MagicMock()
                mock_response.status_code = 429
                mock_response.headers = {"retry-after": "1"}
                raise RateLimitError(
                    message="Rate limited",
                    response=mock_response,
                    body=None,
                )
            return "success"

        result = await circuit_breaker.call(mock_func)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_connection_error(self, circuit_breaker):
        """Should retry on APIConnectionError."""
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIConnectionError(request=MagicMock())
            return "success"

        result = await circuit_breaker.call(mock_func)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_other_errors(self, circuit_breaker):
        """Should not retry on non-retryable errors."""
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid argument")

        with pytest.raises(ValueError):
            await circuit_breaker.call(mock_func)

        assert call_count == 1


class TestCircuitBreakerStatus:
    """Tests for circuit breaker status reporting."""

    @pytest.mark.asyncio
    async def test_status_includes_all_fields(self, circuit_breaker):
        """Status should include all required fields."""
        status = circuit_breaker.get_status()

        assert "service_name" in status
        assert "state" in status
        assert "failure_count" in status
        assert "success_count" in status
        assert "failure_threshold" in status
        assert "recovery_timeout" in status
        assert "last_failure_time" in status
        assert "time_until_recovery" in status

    @pytest.mark.asyncio
    async def test_time_until_recovery_when_open(self, circuit_breaker):
        """Should calculate time until recovery when circuit is open."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker._record_failure(Exception("test error"))

        status = circuit_breaker.get_status()
        assert status["time_until_recovery"] is not None
        assert status["time_until_recovery"] > 0
        assert status["time_until_recovery"] <= 1.0


# =============================================================================
# ResilientAnthropicClient Tests
# =============================================================================


class TestResilientAnthropicClient:
    """Tests for ResilientAnthropicClient."""

    def test_initialization_with_api_key(self):
        """Client should initialize with API key."""
        with patch("app.services.api_resilience.AsyncAnthropic") as mock_class:
            client = ResilientAnthropicClient(
                api_key="test_key",
                service_name="test_client",
            )
            mock_class.assert_called_once_with(api_key="test_key")
            assert client._service_name == "test_client"

    def test_initialization_without_api_key(self):
        """Client should handle missing API key gracefully."""
        client = ResilientAnthropicClient(
            api_key=None,
            service_name="test_client",
        )
        assert client._client is None
        assert client.is_available is False

    def test_circuit_breaker_accessible(self):
        """Circuit breaker should be accessible."""
        with patch("app.services.api_resilience.AsyncAnthropic"):
            client = ResilientAnthropicClient(
                api_key="test_key",
                service_name="test_client",
            )
            assert client.circuit_breaker is not None
            assert isinstance(client.circuit_breaker, AnthropicCircuitBreaker)

    @pytest.mark.asyncio
    async def test_messages_create_without_client_raises(self):
        """Should raise error if trying to create message without client."""
        client = ResilientAnthropicClient(
            api_key=None,
            service_name="test_client",
        )

        with pytest.raises(ValueError, match="not initialized"):
            await client.messages.create(
                model="claude-sonnet-4-5-20250514",
                max_tokens=100,
                messages=[{"role": "user", "content": "Hello"}],
            )

    @pytest.mark.asyncio
    async def test_messages_create_success(self, mock_anthropic_client):
        """Successful message creation should work."""
        with patch("app.services.api_resilience.AsyncAnthropic", return_value=mock_anthropic_client):
            mock_anthropic_client.messages.create.return_value = {"content": "Hello!"}

            client = ResilientAnthropicClient(
                api_key="test_key",
                service_name="test_client",
            )

            result = await client.messages.create(
                model="claude-sonnet-4-5-20250514",
                max_tokens=100,
                messages=[{"role": "user", "content": "Hello"}],
            )

            assert result == {"content": "Hello!"}
            mock_anthropic_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_available_when_circuit_open(self, mock_anthropic_client):
        """is_available should be False when circuit is open."""
        with patch("app.services.api_resilience.AsyncAnthropic", return_value=mock_anthropic_client):
            client = ResilientAnthropicClient(
                api_key="test_key",
                service_name="test_client",
                failure_threshold=2,
            )

            assert client.is_available is True

            # Force circuit open
            for _ in range(2):
                await client.circuit_breaker._record_failure(Exception("error"))

            assert client.is_available is False


# =============================================================================
# CircuitOpenError Tests
# =============================================================================


class TestCircuitOpenError:
    """Tests for CircuitOpenError exception."""

    def test_error_message(self):
        """Error message should include service name and retry time."""
        error = CircuitOpenError("test_service", 30.5)
        assert "test_service" in str(error)
        assert "30.5" in str(error)
        assert error.service_name == "test_service"
        assert error.retry_after == 30.5


# =============================================================================
# Utility Functions Tests
# =============================================================================


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_get_circuit_breaker_creates_new(self):
        """get_circuit_breaker should create new circuit breaker."""
        cb = get_circuit_breaker("new_service")
        assert cb is not None
        assert cb.service_name == "new_service"
        assert "new_service" in _circuit_registry

    def test_get_circuit_breaker_returns_existing(self):
        """get_circuit_breaker should return existing circuit breaker."""
        cb1 = get_circuit_breaker("existing_service")
        cb2 = get_circuit_breaker("existing_service")
        assert cb1 is cb2

    def test_get_all_circuit_statuses(self):
        """get_all_circuit_statuses should return all statuses."""
        get_circuit_breaker("service_1")
        get_circuit_breaker("service_2")

        statuses = get_all_circuit_statuses()
        assert "service_1" in statuses
        assert "service_2" in statuses
        assert statuses["service_1"]["service_name"] == "service_1"

    @pytest.mark.asyncio
    async def test_reset_circuit_existing(self):
        """reset_circuit should reset existing circuit."""
        cb = get_circuit_breaker("reset_test")

        # Open the circuit
        for _ in range(5):
            await cb._record_failure(Exception("error"))
        assert cb.is_open is True

        # Reset
        result = reset_circuit("reset_test")
        assert result is True

        # Give async task time to run
        await asyncio.sleep(0.1)

        # Should be closed now
        assert cb.is_closed is True

    def test_reset_circuit_nonexistent(self):
        """reset_circuit should return False for nonexistent circuit."""
        result = reset_circuit("nonexistent_service")
        assert result is False


# =============================================================================
# Integration Tests
# =============================================================================


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker behavior."""

    @pytest.mark.asyncio
    async def test_full_circuit_lifecycle(self):
        """Test complete circuit breaker lifecycle."""
        cb = AnthropicCircuitBreaker(
            service_name="lifecycle_test",
            failure_threshold=2,
            recovery_timeout=0.5,
            half_open_max_calls=1,
        )

        # Start closed
        assert cb.is_closed is True

        # Failures open the circuit
        for _ in range(2):
            await cb._record_failure(Exception("error"))
        assert cb.is_open is True

        # Wait for recovery timeout
        await asyncio.sleep(0.6)
        await cb._check_state()
        assert cb.is_half_open is True

        # Success in half-open closes circuit
        await cb._record_success()
        assert cb.is_closed is True

        # Verify counters reset
        status = cb.get_status()
        assert status["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_concurrent_calls_handled_safely(self):
        """Test circuit breaker handles concurrent calls safely."""
        cb = AnthropicCircuitBreaker(
            service_name="concurrent_test",
            failure_threshold=5,
            recovery_timeout=60.0,
        )

        async def record_failure():
            await cb._record_failure(Exception("error"))

        # Record multiple failures concurrently
        await asyncio.gather(*[record_failure() for _ in range(10)])

        # Should have opened and stayed open
        assert cb.is_open is True
        assert cb._failure_count >= 5

    @pytest.mark.asyncio
    async def test_metrics_tracking(self):
        """Test that Prometheus metrics are tracked correctly."""
        # Import metrics
        from app.services.api_resilience import (
            API_CALLS_TOTAL,
            CIRCUIT_STATE,
        )

        cb = AnthropicCircuitBreaker(
            service_name="metrics_test",
            failure_threshold=2,
        )

        # Record some activity
        await cb._record_success()
        await cb._record_failure(Exception("error"))

        # Verify state metric is set (0 = CLOSED)
        assert CIRCUIT_STATE.labels(service_name="metrics_test")._value._value == 0


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_failure_threshold(self):
        """Circuit with zero threshold should open immediately."""
        cb = AnthropicCircuitBreaker(
            service_name="zero_threshold",
            failure_threshold=0,
            recovery_timeout=1.0,
        )

        # Any failure should open
        await cb._record_failure(Exception("error"))
        assert cb.is_open is True

    @pytest.mark.asyncio
    async def test_very_short_recovery_timeout(self):
        """Very short recovery timeout should work correctly."""
        cb = AnthropicCircuitBreaker(
            service_name="short_timeout",
            failure_threshold=1,
            recovery_timeout=0.1,
        )

        # Open circuit
        await cb._record_failure(Exception("error"))
        assert cb.is_open is True

        # Quick recovery
        await asyncio.sleep(0.15)
        await cb._check_state()
        assert cb.is_half_open is True

    @pytest.mark.asyncio
    async def test_state_no_change_on_same_state(self, circuit_breaker):
        """Transitioning to same state should be no-op."""
        initial_state = circuit_breaker.state

        await circuit_breaker._transition_to(initial_state)

        assert circuit_breaker.state == initial_state

    @pytest.mark.asyncio
    async def test_retry_after_calculation_when_open(self, circuit_breaker):
        """retry_after should decrease over time."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker._record_failure(Exception("error"))

        # Get initial retry_after
        await asyncio.sleep(0.3)

        try:
            async def mock_func():
                pass
            await circuit_breaker.call(mock_func)
        except CircuitOpenError as e:
            # Should be less than full recovery timeout
            assert e.retry_after < 1.0
            assert e.retry_after >= 0
