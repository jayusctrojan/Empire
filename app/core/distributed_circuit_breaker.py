"""
Empire v7.3 - Distributed Circuit Breaker
Redis-backed circuit breaker for state sharing across instances

The Distributed Circuit Breaker:
1. Shares circuit state across all app instances via Redis
2. Prevents cascading failures when services are unhealthy
3. Provides automatic recovery with half-open state
4. Supports per-service configuration

Usage:
    breaker = DistributedCircuitBreaker(redis_client, "llamaindex")

    @breaker.protect
    async def call_llamaindex():
        return await llamaindex_client.parse(...)

    # Or manual usage
    if breaker.can_execute():
        try:
            result = await some_operation()
            await breaker.record_success()
        except Exception as e:
            await breaker.record_failure(e)
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, Optional, TypeVar, Union

import structlog
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, REGISTRY

logger = structlog.get_logger(__name__)

T = TypeVar('T')


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

def _get_or_create_counter(name: str, description: str, labels: list) -> Counter:
    """Get existing counter or create new one to avoid duplicate registration errors."""
    try:
        return Counter(name, description, labels)
    except ValueError:
        # Metric already exists, retrieve it from registry
        # Use registry lock to prevent race conditions
        with REGISTRY._lock:
            return REGISTRY._names_to_collectors.get(name.replace("_total", ""))


def _get_or_create_gauge(name: str, description: str, labels: list) -> Gauge:
    """Get existing gauge or create new one to avoid duplicate registration errors."""
    try:
        return Gauge(name, description, labels)
    except ValueError:
        # Metric already exists, retrieve it from registry
        # Use registry lock to prevent race conditions
        with REGISTRY._lock:
            return REGISTRY._names_to_collectors.get(name)


CIRCUIT_STATE_CHANGES = _get_or_create_counter(
    "empire_circuit_breaker_state_changes_total",
    "Total circuit breaker state changes",
    ["service", "from_state", "to_state"]
)

CIRCUIT_REJECTIONS = _get_or_create_counter(
    "empire_circuit_breaker_rejections_total",
    "Total requests rejected by circuit breaker",
    ["service"]
)

CIRCUIT_CURRENT_STATE = _get_or_create_gauge(
    "empire_circuit_breaker_state",
    "Current circuit breaker state (0=closed, 1=half_open, 2=open)",
    ["service"]
)

CIRCUIT_FAILURE_COUNT = _get_or_create_gauge(
    "empire_circuit_breaker_failures",
    "Current failure count",
    ["service"]
)


# =============================================================================
# MODELS
# =============================================================================

class CircuitState(str, Enum):
    """States of a circuit breaker"""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Circuit tripped, requests rejected
    HALF_OPEN = "half_open"  # Testing recovery, limited requests allowed


class CircuitBreakerConfig(BaseModel):
    """Configuration for a circuit breaker"""
    service_name: str = Field(..., description="Name of the service")
    failure_threshold: int = Field(default=5, description="Failures before opening circuit")
    success_threshold: int = Field(default=3, description="Successes in half-open before closing")
    timeout_seconds: int = Field(default=60, description="Time circuit stays open before half-open")
    half_open_max_calls: int = Field(default=3, description="Max calls allowed in half-open state")
    excluded_exceptions: list = Field(default_factory=list, description="Exceptions that don't count as failures")


class CircuitBreakerState(BaseModel):
    """Persisted state of a circuit breaker"""
    service_name: str
    state: CircuitState = Field(default=CircuitState.CLOSED)
    failure_count: int = Field(default=0)
    success_count: int = Field(default=0)
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    last_state_change: Optional[float] = None
    half_open_calls: int = Field(default=0)
    consecutive_successes: int = Field(default=0)


# =============================================================================
# DEFAULT SERVICE CONFIGURATIONS
# =============================================================================

DEFAULT_CONFIGS: Dict[str, CircuitBreakerConfig] = {
    "llamaindex": CircuitBreakerConfig(
        service_name="llamaindex",
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=30
    ),
    "crewai": CircuitBreakerConfig(
        service_name="crewai",
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=30
    ),
    "neo4j": CircuitBreakerConfig(
        service_name="neo4j",
        failure_threshold=5,
        success_threshold=3,
        timeout_seconds=60
    ),
    "supabase": CircuitBreakerConfig(
        service_name="supabase",
        failure_threshold=5,
        success_threshold=3,
        timeout_seconds=60
    ),
    "ollama": CircuitBreakerConfig(
        service_name="ollama",
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=30
    ),
    "b2": CircuitBreakerConfig(
        service_name="b2",
        failure_threshold=5,
        success_threshold=3,
        timeout_seconds=60
    ),
    "anthropic": CircuitBreakerConfig(
        service_name="anthropic",
        failure_threshold=5,
        success_threshold=2,
        timeout_seconds=30
    ),
    "arcade": CircuitBreakerConfig(
        service_name="arcade",
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=30
    )
}


# =============================================================================
# DISTRIBUTED CIRCUIT BREAKER
# =============================================================================

class DistributedCircuitBreaker:
    """
    Redis-backed circuit breaker for distributed state sharing.

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Circuit tripped, all requests rejected immediately
    - HALF_OPEN: Testing recovery, limited requests allowed

    Transitions:
    - CLOSED → OPEN: When failure_threshold exceeded
    - OPEN → HALF_OPEN: After timeout_seconds
    - HALF_OPEN → CLOSED: When success_threshold consecutive successes
    - HALF_OPEN → OPEN: On any failure in half-open state
    """

    def __init__(
        self,
        redis_client,
        service_name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize a distributed circuit breaker.

        Args:
            redis_client: Redis client for state storage
            service_name: Name of the service this breaker protects
            config: Optional custom configuration
        """
        self.redis = redis_client
        self.service_name = service_name
        self.config = config or DEFAULT_CONFIGS.get(
            service_name,
            CircuitBreakerConfig(service_name=service_name)
        )

        self._key_prefix = f"circuit_breaker:{service_name}"
        self._state_key = f"{self._key_prefix}:state"
        self._lock_key = f"{self._key_prefix}:lock"

        # Local cache for performance
        self._local_state: Optional[CircuitBreakerState] = None
        self._local_state_time: float = 0
        self._cache_ttl: float = 1.0  # Cache state for 1 second

        # Lock ownership tracking
        self._lock_owner: Optional[str] = None

        logger.debug(
            "Distributed circuit breaker initialized",
            service=service_name,
            failure_threshold=self.config.failure_threshold,
            timeout_seconds=self.config.timeout_seconds
        )

    def _redis_key(self, suffix: str) -> str:
        """Generate Redis key"""
        return f"{self._key_prefix}:{suffix}"

    async def _acquire_lock(self, timeout: float = 5.0) -> bool:
        """Acquire distributed lock for state modifications."""
        try:
            # Generate unique owner ID for safe lock release
            lock_id = str(uuid.uuid4())

            # Use SET NX with expiry for atomic lock acquisition
            result = await asyncio.to_thread(
                self.redis.set,
                self._lock_key,
                lock_id,
                nx=True,
                ex=int(timeout)
            )
            if result:  # Use truthiness check instead of identity
                self._lock_owner = lock_id
                return True
            return False
        except Exception as e:
            logger.warning("Failed to acquire circuit breaker lock", error=str(e))
            return False

    async def _release_lock(self):
        """Release distributed lock only if we own it (using Lua script for atomicity)."""
        if not self._lock_owner:
            return

        try:
            # Lua script to atomically check owner and delete
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            await asyncio.to_thread(
                self.redis.eval,
                lua_script,
                1,
                self._lock_key,
                self._lock_owner
            )
        except Exception as e:
            logger.warning("Failed to release circuit breaker lock", error=str(e))
        finally:
            self._lock_owner = None

    async def _get_state(self, *, force_refresh: bool = False) -> CircuitBreakerState:
        """
        Get current state from Redis with local caching.

        Args:
            force_refresh: If True, bypass local cache and read from Redis.
                          Use this when holding a lock to ensure fresh state.

        Returns:
            Current circuit breaker state
        """
        # Check local cache (skip if force_refresh requested)
        now = time.time()
        if (
            not force_refresh and
            self._local_state is not None and
            now - self._local_state_time < self._cache_ttl
        ):
            return self._local_state

        try:
            # Use asyncio.to_thread to run sync Redis operation in thread pool
            data = await asyncio.to_thread(self.redis.get, self._state_key)

            if data:
                state_dict = json.loads(data)
                state = CircuitBreakerState(**state_dict)
            else:
                # Initialize new state
                state = CircuitBreakerState(service_name=self.service_name)
                await self._save_state(state)

            # Update local cache
            self._local_state = state
            self._local_state_time = now

            return state

        except Exception as e:
            logger.warning(
                "Error reading circuit breaker state",
                service=self.service_name,
                error=str(e)
            )
            # Return default closed state on error
            return CircuitBreakerState(service_name=self.service_name)

    async def _save_state(self, state: CircuitBreakerState):
        """
        Save state to Redis.

        Args:
            state: State to persist
        """
        try:
            # State TTL: Keep for 24 hours even if not updated
            # Use asyncio.to_thread to run sync Redis operation in thread pool
            await asyncio.to_thread(
                self.redis.setex,
                self._state_key,
                86400,  # 24 hours
                state.model_dump_json()
            )

            # Invalidate local cache
            self._local_state = None

            # Update metrics
            state_value = {
                CircuitState.CLOSED: 0,
                CircuitState.HALF_OPEN: 1,
                CircuitState.OPEN: 2
            }.get(state.state, 0)

            CIRCUIT_CURRENT_STATE.labels(service=self.service_name).set(state_value)
            CIRCUIT_FAILURE_COUNT.labels(service=self.service_name).set(state.failure_count)

        except Exception as e:
            logger.error(
                "Error saving circuit breaker state",
                service=self.service_name,
                error=str(e)
            )

    async def _transition_to(self, new_state: CircuitState):
        """
        Transition circuit to new state.

        Args:
            new_state: Target state

        Note: This method is always called from lock-protected paths,
              so we use force_refresh to ensure fresh state from Redis.
        """
        state = await self._get_state(force_refresh=True)
        old_state = state.state

        if old_state == new_state:
            return

        state.state = new_state
        state.last_state_change = time.time()

        if new_state == CircuitState.CLOSED:
            state.failure_count = 0
            state.consecutive_successes = 0
        elif new_state == CircuitState.HALF_OPEN:
            state.half_open_calls = 0
            state.consecutive_successes = 0
        elif new_state == CircuitState.OPEN:
            state.half_open_calls = 0
            state.consecutive_successes = 0

        await self._save_state(state)

        CIRCUIT_STATE_CHANGES.labels(
            service=self.service_name,
            from_state=old_state.value,
            to_state=new_state.value
        ).inc()

        logger.info(
            "Circuit breaker state transition",
            service=self.service_name,
            from_state=old_state.value,
            to_state=new_state.value,
            failure_count=state.failure_count
        )

    async def can_execute(self) -> bool:
        """
        Check if a request can be executed.

        Returns:
            True if request is allowed
        """
        state = await self._get_state()

        if state.state == CircuitState.CLOSED:
            return True

        if state.state == CircuitState.OPEN:
            # Check if timeout has passed
            if state.last_state_change:
                elapsed = time.time() - state.last_state_change
                if elapsed >= self.config.timeout_seconds:
                    # Atomic transition to HALF_OPEN with slot reservation
                    if await self._acquire_lock(timeout=2.0):
                        try:
                            # Re-read state under lock to avoid race
                            state = await self._get_state(force_refresh=True)
                            # Another caller may have already transitioned
                            if state.state == CircuitState.OPEN:
                                state.state = CircuitState.HALF_OPEN
                                state.last_state_change = time.time()
                                state.half_open_calls = 1  # Reserve first slot
                                state.consecutive_successes = 0
                                await self._save_state(state)
                                CIRCUIT_STATE_CHANGES.labels(
                                    service=self.service_name,
                                    from_state=CircuitState.OPEN.value,
                                    to_state=CircuitState.HALF_OPEN.value
                                ).inc()
                                logger.info(
                                    "Circuit breaker state transition",
                                    service=self.service_name,
                                    from_state=CircuitState.OPEN.value,
                                    to_state=CircuitState.HALF_OPEN.value,
                                    failure_count=state.failure_count
                                )
                                return True
                            elif state.state == CircuitState.HALF_OPEN:
                                # Already transitioned, try to get a slot
                                if state.half_open_calls < self.config.half_open_max_calls:
                                    state.half_open_calls += 1
                                    await self._save_state(state)
                                    return True
                        finally:
                            await self._release_lock()

            CIRCUIT_REJECTIONS.labels(service=self.service_name).inc()
            return False

        if state.state == CircuitState.HALF_OPEN:
            # Use distributed lock to atomically reserve half-open slot
            if await self._acquire_lock(timeout=2.0):
                try:
                    # Re-read state under lock to avoid race
                    state = await self._get_state(force_refresh=True)
                    if state.half_open_calls < self.config.half_open_max_calls:
                        state.half_open_calls += 1
                        await self._save_state(state)
                        return True
                finally:
                    await self._release_lock()

            CIRCUIT_REJECTIONS.labels(service=self.service_name).inc()
            return False

        return False

    async def record_success(self):
        """Record a successful call"""
        if not await self._acquire_lock(timeout=2.0):
            logger.warning("Could not acquire lock for record_success", service=self.service_name)
            return

        try:
            state = await self._get_state(force_refresh=True)
            state.last_success_time = time.time()
            state.consecutive_successes += 1

            if state.state == CircuitState.HALF_OPEN:
                state.success_count += 1
                # Note: half_open_calls already incremented in can_execute()

                # Check if we've hit success threshold
                if state.consecutive_successes >= self.config.success_threshold:
                    await self._transition_to(CircuitState.CLOSED)
                    return

            await self._save_state(state)

            logger.debug(
                "Circuit breaker success recorded",
                service=self.service_name,
                state=state.state.value,
                consecutive_successes=state.consecutive_successes
            )
        finally:
            await self._release_lock()

    async def record_failure(self, exception: Optional[Exception] = None):
        """
        Record a failed call.

        Args:
            exception: The exception that occurred (if any)
        """
        # Check if exception should be excluded (use isinstance for subclass support)
        excluded = tuple(self.config.excluded_exceptions)
        if exception and excluded and isinstance(exception, excluded):
            logger.debug(
                "Excluded exception, not counting as failure",
                service=self.service_name,
                exception_type=type(exception).__name__
            )
            return

        if not await self._acquire_lock(timeout=2.0):
            logger.warning("Could not acquire lock for record_failure", service=self.service_name)
            return

        try:
            state = await self._get_state(force_refresh=True)
            state.failure_count += 1
            state.last_failure_time = time.time()
            state.consecutive_successes = 0

            if state.state == CircuitState.HALF_OPEN:
                # Note: half_open_calls already incremented in can_execute()
                # Any failure in half-open immediately opens circuit
                await self._transition_to(CircuitState.OPEN)
                return

            if state.state == CircuitState.CLOSED:
                # Check if we've hit failure threshold
                if state.failure_count >= self.config.failure_threshold:
                    await self._transition_to(CircuitState.OPEN)
                    return

            await self._save_state(state)

            logger.warning(
                "Circuit breaker failure recorded",
                service=self.service_name,
                state=state.state.value,
                failure_count=state.failure_count,
                threshold=self.config.failure_threshold,
                error=str(exception) if exception else None
            )
        finally:
            await self._release_lock()

    async def force_open(self):
        """Force the circuit to open state"""
        if await self._acquire_lock(timeout=2.0):
            try:
                await self._transition_to(CircuitState.OPEN)
            finally:
                await self._release_lock()
        else:
            logger.warning("Could not acquire lock for force_open", service=self.service_name)

    async def force_close(self):
        """Force the circuit to closed state"""
        if await self._acquire_lock(timeout=2.0):
            try:
                await self._transition_to(CircuitState.CLOSED)
            finally:
                await self._release_lock()
        else:
            logger.warning("Could not acquire lock for force_close", service=self.service_name)

    async def reset(self):
        """Reset the circuit breaker to initial state"""
        if await self._acquire_lock(timeout=2.0):
            try:
                state = CircuitBreakerState(service_name=self.service_name)
                await self._save_state(state)
                logger.info("Circuit breaker reset", service=self.service_name)
            finally:
                await self._release_lock()
        else:
            logger.warning("Could not acquire lock for reset", service=self.service_name)

    async def get_status(self) -> Dict[str, Any]:
        """
        Get current circuit breaker status.

        Returns:
            Dictionary with status information
        """
        state = await self._get_state()

        time_in_state = None
        if state.last_state_change:
            time_in_state = time.time() - state.last_state_change

        time_until_half_open = None
        if state.state == CircuitState.OPEN and state.last_state_change:
            remaining = self.config.timeout_seconds - time_in_state
            time_until_half_open = max(0, remaining)

        return {
            "service": self.service_name,
            "state": state.state.value,
            "failure_count": state.failure_count,
            "failure_threshold": self.config.failure_threshold,
            "success_count": state.success_count,
            "success_threshold": self.config.success_threshold,
            "consecutive_successes": state.consecutive_successes,
            "time_in_state_seconds": round(time_in_state, 1) if time_in_state is not None else None,
            "time_until_half_open_seconds": round(time_until_half_open, 1) if time_until_half_open is not None else None,
            "half_open_calls": state.half_open_calls,
            "half_open_max_calls": self.config.half_open_max_calls,
            "last_failure": datetime.fromtimestamp(state.last_failure_time).isoformat() if state.last_failure_time else None,
            "last_success": datetime.fromtimestamp(state.last_success_time).isoformat() if state.last_success_time else None
        }

    def protect(
        self,
        func: Callable[..., Coroutine[Any, Any, T]]
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        """
        Decorator to protect a function with circuit breaker.

        Usage:
            @breaker.protect
            async def call_external_service():
                ...

        Args:
            func: Async function to protect

        Returns:
            Wrapped function with circuit breaker protection
        """
        async def wrapper(*args, **kwargs) -> T:
            if not await self.can_execute():
                raise CircuitBreakerOpenError(
                    service=self.service_name,
                    message=f"Circuit breaker is open for {self.service_name}"
                )

            try:
                result = await func(*args, **kwargs)
                await self.record_success()
                return result
            except Exception as e:
                await self.record_failure(e)
                raise

        return wrapper


# =============================================================================
# EXCEPTIONS
# =============================================================================

class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and request is rejected"""

    def __init__(self, service: str, message: str):
        self.service = service
        super().__init__(message)


# =============================================================================
# CIRCUIT BREAKER REGISTRY
# =============================================================================

class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.

    Provides centralized access to circuit breakers for all services.
    """

    def __init__(self, redis_client):
        """
        Initialize the registry.

        Args:
            redis_client: Redis client for state storage
        """
        self.redis = redis_client
        self._breakers: Dict[str, DistributedCircuitBreaker] = {}

    def get_breaker(
        self,
        service_name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> DistributedCircuitBreaker:
        """
        Get or create a circuit breaker for a service.

        Args:
            service_name: Name of the service
            config: Optional custom configuration

        Returns:
            Circuit breaker instance
        """
        if service_name not in self._breakers:
            self._breakers[service_name] = DistributedCircuitBreaker(
                redis_client=self.redis,
                service_name=service_name,
                config=config
            )
        return self._breakers[service_name]

    async def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all circuit breakers.

        Returns:
            Dictionary of service name to status
        """
        status = {}
        for name, breaker in self._breakers.items():
            status[name] = await breaker.get_status()
        return status

    async def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self._breakers.values():
            await breaker.reset()
        logger.info("All circuit breakers reset")


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_circuit_registry: Optional[CircuitBreakerRegistry] = None


def get_circuit_registry() -> Optional[CircuitBreakerRegistry]:
    """Get the global circuit breaker registry"""
    return _circuit_registry


def initialize_circuit_registry(redis_client) -> CircuitBreakerRegistry:
    """
    Initialize the global circuit breaker registry.

    Args:
        redis_client: Redis client for state storage

    Returns:
        Initialized CircuitBreakerRegistry instance
    """
    global _circuit_registry
    _circuit_registry = CircuitBreakerRegistry(redis_client)

    # Pre-create breakers for known services
    for service_name in DEFAULT_CONFIGS.keys():
        _circuit_registry.get_breaker(service_name)

    logger.info(
        "Circuit breaker registry initialized",
        services=list(DEFAULT_CONFIGS.keys())
    )

    return _circuit_registry


def get_circuit_breaker(service_name: str) -> Optional[DistributedCircuitBreaker]:
    """
    Convenience function to get a circuit breaker.

    Args:
        service_name: Name of the service

    Returns:
        Circuit breaker instance or None if registry not initialized
    """
    registry = get_circuit_registry()
    if registry:
        return registry.get_breaker(service_name)
    return None
