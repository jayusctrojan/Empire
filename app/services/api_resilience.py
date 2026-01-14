"""
API Resilience Module - Circuit Breaker for Anthropic API Calls.

Task 137: Implement circuit breaker pattern for Anthropic API calls
across all agent services to improve resilience and prevent cascading failures.

Features:
- Circuit breaker with closed/open/half-open states
- Exponential backoff retry (max 3 attempts)
- Prometheus metrics for monitoring
- Configurable thresholds and timeouts
"""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Optional, TypeVar
from functools import wraps

import structlog
from anthropic import AsyncAnthropic, APIError, RateLimitError, APIConnectionError
from prometheus_client import Counter, Gauge, Histogram
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

logger = structlog.get_logger(__name__)

T = TypeVar("T")


# =============================================================================
# Prometheus Metrics for Circuit Breaker
# =============================================================================

CIRCUIT_STATE = Gauge(
    "empire_anthropic_circuit_state",
    "Current state of Anthropic API circuit breaker (0=closed, 1=half-open, 2=open)",
    ["service_name"],
)

CIRCUIT_STATE_CHANGES = Counter(
    "empire_anthropic_circuit_state_changes_total",
    "Number of circuit state transitions",
    ["service_name", "from_state", "to_state"],
)

API_CALLS_TOTAL = Counter(
    "empire_anthropic_api_calls_total",
    "Total Anthropic API calls",
    ["service_name", "status"],
)

API_CALL_DURATION = Histogram(
    "empire_anthropic_api_call_duration_seconds",
    "Duration of Anthropic API calls",
    ["service_name"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

API_RETRIES = Counter(
    "empire_anthropic_api_retries_total",
    "Number of retry attempts for Anthropic API calls",
    ["service_name"],
)

CIRCUIT_REJECTIONS = Counter(
    "empire_anthropic_circuit_rejections_total",
    "Number of calls rejected due to open circuit",
    ["service_name"],
)


# =============================================================================
# Circuit Breaker State
# =============================================================================


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = 0      # Normal operation, requests flow through
    HALF_OPEN = 1   # Testing if service recovered, limited requests
    OPEN = 2        # Service down, rejecting requests immediately


class CircuitOpenError(Exception):
    """Raised when circuit is open and request is rejected."""

    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker for {service_name} is OPEN. "
            f"Retry after {retry_after:.1f} seconds."
        )


# =============================================================================
# Circuit Breaker Implementation
# =============================================================================


class AnthropicCircuitBreaker:
    """
    Circuit breaker for Anthropic API calls with retry logic.

    Implements the circuit breaker pattern:
    - CLOSED: Normal operation, all requests go through
    - OPEN: Service appears down, fail fast without calling API
    - HALF_OPEN: Testing recovery, allow limited requests

    Usage:
        circuit = AnthropicCircuitBreaker("content_summarizer")
        result = await circuit.call(
            client.messages.create,
            model="claude-sonnet-4-5-20250514",
            max_tokens=1000,
            messages=[...]
        )
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        """
        Initialize circuit breaker.

        Args:
            service_name: Name of the service (for metrics/logging)
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open
            half_open_max_calls: Max calls allowed in half-open state
        """
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

        # Initialize metrics
        CIRCUIT_STATE.labels(service_name=service_name).set(CircuitState.CLOSED.value)

        logger.info(
            "Circuit breaker initialized",
            service_name=service_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self._state == CircuitState.HALF_OPEN

    async def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new circuit state."""
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state

        # Update metrics
        CIRCUIT_STATE.labels(service_name=self.service_name).set(new_state.value)
        CIRCUIT_STATE_CHANGES.labels(
            service_name=self.service_name,
            from_state=old_state.name,
            to_state=new_state.name,
        ).inc()

        # Reset counters on state change
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0

        logger.info(
            "Circuit state changed",
            service_name=self.service_name,
            from_state=old_state.name,
            to_state=new_state.name,
            failure_count=self._failure_count,
        )

    async def _check_state(self) -> None:
        """Check and potentially update circuit state based on timeouts."""
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    await self._transition_to(CircuitState.HALF_OPEN)

    async def _record_success(self) -> None:
        """Record a successful API call."""
        async with self._lock:
            self._success_count += 1

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                # After enough successes in half-open, close the circuit
                if self._half_open_calls >= self.half_open_max_calls:
                    await self._transition_to(CircuitState.CLOSED)

            API_CALLS_TOTAL.labels(
                service_name=self.service_name,
                status="success",
            ).inc()

    async def _record_failure(self, error: Exception) -> None:
        """Record a failed API call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            API_CALLS_TOTAL.labels(
                service_name=self.service_name,
                status="failure",
            ).inc()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open immediately opens circuit
                await self._transition_to(CircuitState.OPEN)
                logger.warning(
                    "Circuit opened from half-open due to failure",
                    service_name=self.service_name,
                    error=str(error),
                )
            elif self._state == CircuitState.CLOSED:
                # Check if we've hit the failure threshold
                if self._failure_count >= self.failure_threshold:
                    await self._transition_to(CircuitState.OPEN)
                    logger.error(
                        "Circuit opened due to failure threshold",
                        service_name=self.service_name,
                        failure_count=self._failure_count,
                        threshold=self.failure_threshold,
                        error=str(error),
                    )

    async def call(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute an API call with circuit breaker protection.

        Args:
            func: Async function to call (e.g., client.messages.create)
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result from the API call

        Raises:
            CircuitOpenError: If circuit is open
            Exception: If API call fails after retries
        """
        # Check and update state
        await self._check_state()

        # Reject if circuit is open
        if self._state == CircuitState.OPEN:
            retry_after = self.recovery_timeout
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                retry_after = max(0, self.recovery_timeout - elapsed)

            CIRCUIT_REJECTIONS.labels(service_name=self.service_name).inc()
            raise CircuitOpenError(self.service_name, retry_after)

        # Execute with retry logic
        start_time = time.time()
        try:
            result = await self._execute_with_retry(func, *args, **kwargs)

            # Record success
            duration = time.time() - start_time
            API_CALL_DURATION.labels(service_name=self.service_name).observe(duration)
            await self._record_success()

            return result

        except Exception as e:
            # Record failure
            duration = time.time() - start_time
            API_CALL_DURATION.labels(service_name=self.service_name).observe(duration)
            await self._record_failure(e)
            raise

    async def _execute_with_retry(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute function with exponential backoff retry."""

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
            reraise=True,
        )
        async def _inner():
            return await func(*args, **kwargs)

        attempt = 0
        try:
            # Track retries
            async def _with_retry_tracking():
                nonlocal attempt
                attempt += 1
                if attempt > 1:
                    API_RETRIES.labels(service_name=self.service_name).inc()
                    logger.warning(
                        "Retrying Anthropic API call",
                        service_name=self.service_name,
                        attempt=attempt,
                    )
                return await func(*args, **kwargs)

            @retry(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
                reraise=True,
            )
            async def _retry_wrapper():
                return await _with_retry_tracking()

            return await _retry_wrapper()

        except RetryError as e:
            # Re-raise the underlying exception
            raise e.last_attempt.exception()

    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "service_name": self.service_name,
            "state": self._state.name,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self._last_failure_time,
            "time_until_recovery": (
                max(0, self.recovery_timeout - (time.time() - self._last_failure_time))
                if self._last_failure_time and self._state == CircuitState.OPEN
                else None
            ),
        }


# =============================================================================
# Resilient Anthropic Client Wrapper
# =============================================================================


class ResilientAnthropicClient:
    """
    Wrapper around AsyncAnthropic with built-in circuit breaker.

    Drop-in replacement for AsyncAnthropic that adds resilience.

    Usage:
        client = ResilientAnthropicClient(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            service_name="content_summarizer"
        )

        response = await client.messages.create(
            model="claude-sonnet-4-5-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": "Hello!"}]
        )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        service_name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ):
        """
        Initialize resilient client.

        Args:
            api_key: Anthropic API key
            service_name: Name for metrics/logging
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before testing recovery
        """
        self._client = AsyncAnthropic(api_key=api_key) if api_key else None
        self._circuit = AnthropicCircuitBreaker(
            service_name=service_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
        self._service_name = service_name
        self.messages = _ResilientMessages(self)

    @property
    def circuit_breaker(self) -> AnthropicCircuitBreaker:
        """Access the circuit breaker for status checks."""
        return self._circuit

    @property
    def is_available(self) -> bool:
        """Check if the client is available (has API key and circuit not open)."""
        return self._client is not None and not self._circuit.is_open


class _ResilientMessages:
    """Messages API wrapper with circuit breaker."""

    def __init__(self, client: ResilientAnthropicClient):
        self._client = client

    async def create(self, **kwargs) -> Any:
        """
        Create a message with circuit breaker protection.

        Args:
            **kwargs: Arguments for messages.create()

        Returns:
            API response
        """
        if not self._client._client:
            raise ValueError(
                f"Anthropic client not initialized for {self._client._service_name}"
            )

        return await self._client._circuit.call(
            self._client._client.messages.create,
            **kwargs,
        )


# =============================================================================
# Utility Functions
# =============================================================================


def get_circuit_breaker(service_name: str) -> AnthropicCircuitBreaker:
    """
    Get or create a circuit breaker for a service.

    Uses a global registry to ensure one circuit breaker per service.
    """
    if service_name not in _circuit_registry:
        _circuit_registry[service_name] = AnthropicCircuitBreaker(service_name)
    return _circuit_registry[service_name]


def get_all_circuit_statuses() -> dict:
    """Get status of all registered circuit breakers."""
    return {
        name: cb.get_status()
        for name, cb in _circuit_registry.items()
    }


def reset_circuit(service_name: str) -> bool:
    """
    Manually reset a circuit to closed state.

    Use with caution - only for administrative purposes.
    """
    if service_name in _circuit_registry:
        cb = _circuit_registry[service_name]
        # Force transition to closed
        asyncio.create_task(cb._transition_to(CircuitState.CLOSED))
        logger.warning(
            "Circuit manually reset",
            service_name=service_name,
        )
        return True
    return False


# Global registry of circuit breakers
_circuit_registry: dict[str, AnthropicCircuitBreaker] = {}
