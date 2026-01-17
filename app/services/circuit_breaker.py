"""
Empire v7.3 - Universal Circuit Breaker Framework (Task 159)

A comprehensive circuit breaker implementation for all external API services
including configurable thresholds, fallback responses, and monitoring.

Features:
- Generic CircuitBreaker class configurable for any service
- FallbackRegistry for custom fallback handlers
- Prometheus metrics for all circuit operations
- Global registry for circuit management
- Service-specific configuration profiles

Author: Claude Code
Date: 2025-01-15
"""

import asyncio
import time
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)
from dataclasses import dataclass, field
from datetime import datetime

import structlog
from prometheus_client import Counter, Gauge, Histogram
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
    AsyncRetrying,
)
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

T = TypeVar("T")


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

CIRCUIT_STATE_GAUGE = Gauge(
    "empire_circuit_breaker_state",
    "Current state of circuit breaker (0=closed, 1=half-open, 2=open)",
    ["service", "operation"]
)

CIRCUIT_STATE_CHANGES_COUNTER = Counter(
    "empire_circuit_breaker_state_changes_total",
    "Total circuit breaker state transitions",
    ["service", "from_state", "to_state"]
)

CIRCUIT_REQUESTS_COUNTER = Counter(
    "empire_circuit_breaker_requests_total",
    "Total requests through circuit breaker",
    ["service", "operation", "result"]
)

CIRCUIT_RESPONSE_TIME = Histogram(
    "empire_circuit_breaker_response_time_seconds",
    "Response time for requests through circuit breaker",
    ["service", "operation"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

CIRCUIT_REJECTIONS_COUNTER = Counter(
    "empire_circuit_breaker_rejections_total",
    "Number of calls rejected due to open circuit",
    ["service"]
)

CIRCUIT_FALLBACK_COUNTER = Counter(
    "empire_circuit_breaker_fallbacks_total",
    "Number of fallback responses served",
    ["service", "operation"]
)

CIRCUIT_RETRY_COUNTER = Counter(
    "empire_circuit_breaker_retries_total",
    "Number of retry attempts",
    ["service", "operation", "attempt"]
)


# =============================================================================
# CIRCUIT BREAKER STATE
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = 0      # Normal operation, requests flow through
    HALF_OPEN = 1   # Testing if service recovered, limited requests
    OPEN = 2        # Service down, rejecting requests immediately


class CircuitOpenError(Exception):
    """Raised when circuit is open and request is rejected"""

    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker for {service_name} is OPEN. "
            f"Retry after {retry_after:.1f} seconds."
        )


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker instance"""

    # Failure thresholds
    failure_threshold: int = 5          # Failures before opening circuit
    success_threshold: int = 3          # Successes in half-open to close
    recovery_timeout: float = 60.0      # Seconds before trying half-open

    # Retry settings
    max_retries: int = 3
    retry_base_delay: float = 1.0       # Initial retry delay
    retry_max_delay: float = 30.0       # Maximum retry delay
    retry_multiplier: float = 2.0       # Exponential backoff multiplier

    # Timeout settings
    operation_timeout: float = 30.0     # Default operation timeout
    half_open_max_calls: int = 3        # Max calls in half-open state

    # Error classification
    retryable_exceptions: tuple = field(default_factory=lambda: (
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
    ))


# Service-specific default configurations
# Task 174: Production Readiness - Circuit Breaker Configurations (FR-021 to FR-025)
SERVICE_CONFIGS: Dict[str, CircuitBreakerConfig] = {
    "anthropic": CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60.0,
        max_retries=3,
        operation_timeout=120.0,  # LLM calls can be slow
    ),
    # FR-024: Neo4j circuit breaker (3 failures, 30s recovery)
    "neo4j": CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30.0,
        max_retries=3,
        operation_timeout=30.0,
    ),
    "supabase": CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=30.0,
        max_retries=3,
        operation_timeout=15.0,
    ),
    # FR-021: LlamaIndex circuit breaker (5 failures, 30s recovery)
    "llamaindex": CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=30.0,
        max_retries=3,
        operation_timeout=120.0,  # Document parsing can be slow
    ),
    # FR-022: CrewAI circuit breaker (3 failures, 60s recovery)
    "crewai": CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=60.0,
        max_retries=3,
        operation_timeout=180.0,  # Multi-agent workflows can be slow
    ),
    # FR-023: Ollama circuit breaker (5 failures, 15s recovery)
    "ollama": CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=15.0,
        max_retries=3,
        operation_timeout=60.0,  # Local model inference
    ),
    # FR-025: B2 storage circuit breaker (5 failures, 60s recovery)
    "b2": CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60.0,
        max_retries=5,
        operation_timeout=300.0,  # Large file uploads
    ),
    "default": CircuitBreakerConfig(),
}


def get_service_config(service_name: str) -> CircuitBreakerConfig:
    """Get configuration for a service"""
    return SERVICE_CONFIGS.get(service_name, SERVICE_CONFIGS["default"])


# =============================================================================
# FALLBACK REGISTRY
# =============================================================================

class FallbackRegistry:
    """
    Registry for fallback handlers.

    Stores and retrieves fallback functions for service operations
    when the circuit is open or calls fail after retries.

    Usage:
        registry = FallbackRegistry()
        registry.register("neo4j", "query", async_fallback_handler)
        fallback = registry.get_fallback("neo4j", "query")
    """

    def __init__(self):
        self._fallbacks: Dict[str, Dict[str, Callable]] = {}
        self._default_fallbacks: Dict[str, Callable] = {}

    def register(
        self,
        service_name: str,
        operation: str,
        handler: Callable[..., Coroutine[Any, Any, Any]]
    ) -> None:
        """
        Register a fallback handler for a service operation.

        Args:
            service_name: Name of the service
            operation: Name of the operation
            handler: Async function to call as fallback
        """
        if service_name not in self._fallbacks:
            self._fallbacks[service_name] = {}

        self._fallbacks[service_name][operation] = handler
        logger.debug(
            "Fallback registered",
            service=service_name,
            operation=operation
        )

    def register_default(
        self,
        service_name: str,
        handler: Callable[..., Coroutine[Any, Any, Any]]
    ) -> None:
        """
        Register a default fallback handler for a service.

        Used when no operation-specific fallback is registered.

        Args:
            service_name: Name of the service
            handler: Async function to call as fallback
        """
        self._default_fallbacks[service_name] = handler
        logger.debug("Default fallback registered", service=service_name)

    def get_fallback(
        self,
        service_name: str,
        operation: str
    ) -> Optional[Callable[..., Coroutine[Any, Any, Any]]]:
        """
        Get a fallback handler for a service operation.

        Returns operation-specific fallback if registered,
        otherwise returns service default fallback.

        Args:
            service_name: Name of the service
            operation: Name of the operation

        Returns:
            Fallback handler or None if not registered
        """
        # Try operation-specific fallback first
        service_fallbacks = self._fallbacks.get(service_name, {})
        if operation in service_fallbacks:
            return service_fallbacks[operation]

        # Fall back to service default
        return self._default_fallbacks.get(service_name)

    def has_fallback(self, service_name: str, operation: str) -> bool:
        """Check if a fallback is registered for a service operation"""
        return self.get_fallback(service_name, operation) is not None

    def list_fallbacks(self) -> Dict[str, List[str]]:
        """List all registered fallbacks by service"""
        result = {}
        for service, operations in self._fallbacks.items():
            result[service] = list(operations.keys())
        return result


# Global fallback registry
_fallback_registry = FallbackRegistry()


def get_fallback_registry() -> FallbackRegistry:
    """Get the global fallback registry"""
    return _fallback_registry


# =============================================================================
# CIRCUIT BREAKER IMPLEMENTATION
# =============================================================================

class CircuitBreaker(Generic[T]):
    """
    Universal circuit breaker for external API services.

    Implements the circuit breaker pattern with:
    - CLOSED: Normal operation, all requests go through
    - OPEN: Service appears down, fail fast without calling API
    - HALF_OPEN: Testing recovery, allow limited requests

    Features:
    - Configurable thresholds and timeouts
    - Automatic retry with exponential backoff
    - Fallback support via registry
    - Prometheus metrics integration
    - Thread-safe state management

    Usage:
        circuit = CircuitBreaker("neo4j")
        result = await circuit.call(
            db_query_function,
            "MATCH (n) RETURN n",
            operation="query"
        )
    """

    def __init__(
        self,
        service_name: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback_registry: Optional[FallbackRegistry] = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            service_name: Name of the service (for metrics/logging)
            config: Optional custom configuration
            fallback_registry: Optional fallback registry
        """
        self.service_name = service_name
        self.config = config or get_service_config(service_name)
        self.fallback_registry = fallback_registry or _fallback_registry

        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_success_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

        # Statistics
        self._stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "rejected_calls": 0,
            "fallback_calls": 0,
            "retries": 0,
            "state_changes": 0,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Initialize metrics
        CIRCUIT_STATE_GAUGE.labels(
            service=service_name,
            operation="default"
        ).set(CircuitState.CLOSED.value)

        logger.info(
            "Circuit breaker initialized",
            service_name=service_name,
            failure_threshold=self.config.failure_threshold,
            recovery_timeout=self.config.recovery_timeout,
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)"""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)"""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)"""
        return self._state == CircuitState.HALF_OPEN

    async def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new circuit state"""
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state
        self._stats["state_changes"] += 1

        # Update metrics
        CIRCUIT_STATE_GAUGE.labels(
            service=self.service_name,
            operation="default"
        ).set(new_state.value)

        CIRCUIT_STATE_CHANGES_COUNTER.labels(
            service=self.service_name,
            from_state=old_state.name,
            to_state=new_state.name,
        ).inc()

        # Reset counters on state change
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._success_count = 0

        logger.info(
            "Circuit state changed",
            service_name=self.service_name,
            from_state=old_state.name,
            to_state=new_state.name,
            failure_count=self._failure_count,
        )

    async def _check_state(self) -> None:
        """Check and potentially update circuit state based on timeouts"""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.config.recovery_timeout:
                    await self._transition_to(CircuitState.HALF_OPEN)

    async def _record_success(self, operation: str = "default") -> None:
        """Record a successful call"""
        async with self._lock:
            self._success_count += 1
            self._last_success_time = time.time()
            self._stats["successful_calls"] += 1

            CIRCUIT_REQUESTS_COUNTER.labels(
                service=self.service_name,
                operation=operation,
                result="success"
            ).inc()

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._success_count >= self.config.success_threshold:
                    await self._transition_to(CircuitState.CLOSED)

    async def _record_failure(self, error: Exception, operation: str = "default") -> None:
        """Record a failed call"""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            self._stats["failed_calls"] += 1

            CIRCUIT_REQUESTS_COUNTER.labels(
                service=self.service_name,
                operation=operation,
                result="failure"
            ).inc()

            if self._state == CircuitState.HALF_OPEN:
                await self._transition_to(CircuitState.OPEN)
                logger.warning(
                    "Circuit opened from half-open due to failure",
                    service_name=self.service_name,
                    error=str(error),
                )
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    await self._transition_to(CircuitState.OPEN)
                    logger.error(
                        "Circuit opened due to failure threshold",
                        service_name=self.service_name,
                        failure_count=self._failure_count,
                        threshold=self.config.failure_threshold,
                        error=str(error),
                    )

    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        operation: str = "default",
        use_fallback: bool = True,
        **kwargs: Any,
    ) -> T:
        """
        Execute an async function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Positional arguments for the function
            operation: Operation name for metrics and fallback lookup
            use_fallback: Whether to use fallback on failure
            **kwargs: Keyword arguments for the function

        Returns:
            Result from the function or fallback

        Raises:
            CircuitOpenError: If circuit is open and no fallback available
            Exception: If call fails and no fallback available
        """
        self._stats["total_calls"] += 1
        await self._check_state()

        # Handle open circuit
        if self._state == CircuitState.OPEN:
            retry_after = self.config.recovery_timeout
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                retry_after = max(0, self.config.recovery_timeout - elapsed)

            self._stats["rejected_calls"] += 1
            CIRCUIT_REJECTIONS_COUNTER.labels(service=self.service_name).inc()

            # Try fallback
            if use_fallback:
                fallback = self.fallback_registry.get_fallback(
                    self.service_name,
                    operation
                )
                if fallback:
                    logger.info(
                        "Using fallback for open circuit",
                        service=self.service_name,
                        operation=operation
                    )
                    self._stats["fallback_calls"] += 1
                    CIRCUIT_FALLBACK_COUNTER.labels(
                        service=self.service_name,
                        operation=operation
                    ).inc()
                    return await fallback(*args, **kwargs)

            raise CircuitOpenError(self.service_name, retry_after)

        # Execute with retry logic
        start_time = time.time()
        try:
            result = await self._execute_with_retry(
                func,
                *args,
                operation=operation,
                **kwargs
            )

            duration = time.time() - start_time
            CIRCUIT_RESPONSE_TIME.labels(
                service=self.service_name,
                operation=operation
            ).observe(duration)

            await self._record_success(operation)
            return result

        except Exception as e:
            duration = time.time() - start_time
            CIRCUIT_RESPONSE_TIME.labels(
                service=self.service_name,
                operation=operation
            ).observe(duration)

            await self._record_failure(e, operation)

            # Try fallback
            if use_fallback:
                fallback = self.fallback_registry.get_fallback(
                    self.service_name,
                    operation
                )
                if fallback:
                    logger.info(
                        "Using fallback after failure",
                        service=self.service_name,
                        operation=operation,
                        error=str(e)
                    )
                    self._stats["fallback_calls"] += 1
                    CIRCUIT_FALLBACK_COUNTER.labels(
                        service=self.service_name,
                        operation=operation
                    ).inc()
                    return await fallback(*args, **kwargs)

            raise

    async def _execute_with_retry(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        operation: str = "default",
        **kwargs: Any,
    ) -> T:
        """Execute function with exponential backoff retry"""
        attempt = 0

        async def attempt_call():
            nonlocal attempt
            attempt += 1
            if attempt > 1:
                self._stats["retries"] += 1
                CIRCUIT_RETRY_COUNTER.labels(
                    service=self.service_name,
                    operation=operation,
                    attempt=str(attempt)
                ).inc()
                logger.warning(
                    "Retrying call",
                    service=self.service_name,
                    operation=operation,
                    attempt=attempt,
                )
            return await func(*args, **kwargs)

        try:
            async for attempt_state in AsyncRetrying(
                stop=stop_after_attempt(self.config.max_retries),
                wait=wait_exponential(
                    multiplier=self.config.retry_multiplier,
                    min=self.config.retry_base_delay,
                    max=self.config.retry_max_delay
                ),
                retry=retry_if_exception_type(self.config.retryable_exceptions),
                reraise=True,
            ):
                with attempt_state:
                    return await attempt_call()

        except RetryError as e:
            raise e.last_attempt.exception()

    async def reset(self) -> None:
        """Manually reset circuit to closed state"""
        async with self._lock:
            old_state = self._state
            await self._transition_to(CircuitState.CLOSED)
            self._failure_count = 0
            self._success_count = 0
            logger.warning(
                "Circuit manually reset",
                service_name=self.service_name,
                from_state=old_state.name,
            )

    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status"""
        time_until_recovery = None
        if self._last_failure_time and self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            time_until_recovery = max(0, self.config.recovery_timeout - elapsed)

        return {
            "service_name": self.service_name,
            "state": self._state.name,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.config.failure_threshold,
            "success_threshold": self.config.success_threshold,
            "recovery_timeout": self.config.recovery_timeout,
            "last_failure_time": self._last_failure_time,
            "last_success_time": self._last_success_time,
            "time_until_recovery": time_until_recovery,
            "is_open": self._state == CircuitState.OPEN,
            # Flatten stats for API compatibility
            "total_calls": self._stats["total_calls"],
            "total_failures": self._stats["failed_calls"],
            "total_successes": self._stats["successful_calls"],
            "fallback_calls": self._stats["fallback_calls"],
            "rejected_calls": self._stats["rejected_calls"],
            "retries": self._stats["retries"],
            "stats": self._stats,
        }


# =============================================================================
# GLOBAL CIRCUIT REGISTRY
# =============================================================================

_circuit_registry: Dict[str, CircuitBreaker] = {}
_registry_lock = asyncio.Lock()


async def get_circuit_breaker(
    service_name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """
    Get or create a circuit breaker for a service.

    Uses a global registry to ensure one circuit breaker per service.

    Args:
        service_name: Name of the service
        config: Optional custom configuration

    Returns:
        CircuitBreaker instance
    """
    async with _registry_lock:
        if service_name not in _circuit_registry:
            _circuit_registry[service_name] = CircuitBreaker(
                service_name,
                config
            )
        return _circuit_registry[service_name]


def get_circuit_breaker_sync(
    service_name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """
    Synchronous version for use in non-async contexts.

    Note: May create duplicate instances if called concurrently.
    """
    if service_name not in _circuit_registry:
        _circuit_registry[service_name] = CircuitBreaker(
            service_name,
            config
        )
    return _circuit_registry[service_name]


def get_all_circuit_statuses() -> Dict[str, Dict[str, Any]]:
    """Get status of all registered circuit breakers"""
    return {
        name: cb.get_status()
        for name, cb in _circuit_registry.items()
    }


async def reset_circuit(service_name: str) -> bool:
    """
    Manually reset a circuit to closed state.

    Args:
        service_name: Name of the service

    Returns:
        True if circuit was reset, False if not found
    """
    if service_name in _circuit_registry:
        await _circuit_registry[service_name].reset()
        return True
    return False


async def reset_all_circuits() -> int:
    """
    Reset all circuit breakers to closed state.

    Returns:
        Number of circuits reset
    """
    count = 0
    for name, cb in _circuit_registry.items():
        await cb.reset()
        count += 1
    return count


def list_registered_circuits() -> List[str]:
    """List all registered circuit breaker service names"""
    return list(_circuit_registry.keys())
