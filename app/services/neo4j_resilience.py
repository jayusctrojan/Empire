"""
Empire v7.3 - Neo4j Graph Sync Resilience Layer
Task 153: Neo4j Graph Sync Error Handling

Implements robust error handling for Neo4j graph synchronization:
- Retry logic with exponential backoff
- Circuit breaker pattern
- Dead letter queue for failed operations
- Monitoring and alerting

Dependencies:
- tenacity: For retry logic
- Redis: For dead letter queue persistence
"""

import asyncio
import json
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar
from functools import wraps
import structlog

from app.services.neo4j_http_client import (
    Neo4jHTTPClient,
    Neo4jConnectionError,
    Neo4jQueryError,
    get_neo4j_http_client,
)

logger = structlog.get_logger(__name__)

# Type variable for generic async functions
T = TypeVar("T")


# ==============================================================================
# Circuit Breaker Implementation
# ==============================================================================


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5        # Failures before opening circuit
    recovery_timeout: float = 60.0    # Seconds to wait before half-open
    success_threshold: int = 3        # Successes to close circuit
    expected_exceptions: tuple = (Neo4jConnectionError, Neo4jQueryError)


@dataclass
class CircuitBreakerState:
    """State tracking for circuit breaker."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_state_change: float = field(default_factory=time.time)


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""
    def __init__(self, message: str = "Circuit breaker is open", recovery_time: float = 0):
        self.recovery_time = recovery_time
        super().__init__(message)


class CircuitBreaker:
    """
    Circuit breaker implementation for Neo4j operations.

    Prevents cascading failures by failing fast when the service is unhealthy.
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for this circuit breaker
            config: Configuration options
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState()
        self._lock = asyncio.Lock()

        logger.info(
            "circuit_breaker_initialized",
            name=name,
            failure_threshold=self.config.failure_threshold,
            recovery_timeout=self.config.recovery_timeout
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state.state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state.state == CircuitState.CLOSED

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function through circuit breaker.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result if successful

        Raises:
            CircuitBreakerOpen: If circuit is open
            Original exception: If function fails
        """
        async with self._lock:
            await self._check_state()

            if self._state.state == CircuitState.OPEN:
                recovery_time = self._get_recovery_time()
                logger.warning(
                    "circuit_breaker_rejected",
                    name=self.name,
                    recovery_in=recovery_time
                )
                raise CircuitBreakerOpen(
                    f"Circuit '{self.name}' is open",
                    recovery_time=recovery_time
                )

        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result

        except self.config.expected_exceptions as e:
            await self._record_failure(e)
            raise

    async def _check_state(self):
        """Check and potentially update circuit state based on time."""
        if self._state.state == CircuitState.OPEN:
            elapsed = time.time() - self._state.last_failure_time
            if elapsed >= self.config.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)

    async def _record_success(self):
        """Record a successful call."""
        async with self._lock:
            if self._state.state == CircuitState.HALF_OPEN:
                self._state.success_count += 1
                if self._state.success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state.state == CircuitState.CLOSED:
                # Reset failure count on success
                self._state.failure_count = 0

    async def _record_failure(self, error: Exception):
        """Record a failed call."""
        async with self._lock:
            self._state.failure_count += 1
            self._state.last_failure_time = time.time()

            logger.warning(
                "circuit_breaker_failure",
                name=self.name,
                failure_count=self._state.failure_count,
                error=str(error)
            )

            if self._state.state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                self._transition_to(CircuitState.OPEN)
            elif self._state.failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state."""
        old_state = self._state.state
        self._state.state = new_state
        self._state.last_state_change = time.time()

        if new_state == CircuitState.CLOSED:
            self._state.failure_count = 0
            self._state.success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._state.success_count = 0

        logger.info(
            "circuit_breaker_state_change",
            name=self.name,
            old_state=old_state.value,
            new_state=new_state.value
        )

    def _get_recovery_time(self) -> float:
        """Get seconds until circuit may recover."""
        if self._state.last_failure_time is None:
            return 0
        elapsed = time.time() - self._state.last_failure_time
        return max(0, self.config.recovery_timeout - elapsed)

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self._state.state.value,
            "failure_count": self._state.failure_count,
            "success_count": self._state.success_count,
            "last_failure_time": self._state.last_failure_time,
            "recovery_time": self._get_recovery_time() if self._state.state == CircuitState.OPEN else 0
        }


# ==============================================================================
# Retry Logic with Exponential Backoff
# ==============================================================================


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_attempts: int = 5
    initial_delay: float = 1.0        # Initial delay in seconds
    max_delay: float = 60.0           # Maximum delay in seconds
    exponential_base: float = 2.0     # Base for exponential backoff
    jitter: bool = True               # Add random jitter to delays
    retryable_exceptions: tuple = (Neo4jConnectionError,)


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    **kwargs
) -> T:
    """
    Execute function with retry logic and exponential backoff.

    Args:
        func: Async function to execute
        *args: Positional arguments
        config: Retry configuration
        **kwargs: Keyword arguments

    Returns:
        Function result if successful

    Raises:
        Last exception if all retries fail
    """
    config = config or RetryConfig()
    last_exception = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func(*args, **kwargs)

        except config.retryable_exceptions as e:
            last_exception = e

            if attempt == config.max_attempts:
                logger.error(
                    "retry_exhausted",
                    attempts=attempt,
                    error=str(e)
                )
                raise

            # Calculate delay with exponential backoff
            delay = min(
                config.initial_delay * (config.exponential_base ** (attempt - 1)),
                config.max_delay
            )

            # Add jitter to prevent thundering herd
            if config.jitter:
                import random
                delay = delay * (0.5 + random.random())

            logger.warning(
                "retry_attempt",
                attempt=attempt,
                max_attempts=config.max_attempts,
                delay=delay,
                error=str(e)
            )

            await asyncio.sleep(delay)

    raise last_exception


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator for adding retry logic to async functions.

    Usage:
        @with_retry(RetryConfig(max_attempts=3))
        async def my_function():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await retry_with_backoff(func, *args, config=config, **kwargs)
        return wrapper
    return decorator


# ==============================================================================
# Dead Letter Queue
# ==============================================================================


@dataclass
class FailedOperation:
    """Represents a failed operation in the dead letter queue."""
    operation_id: str
    operation_type: str
    query: str
    parameters: Dict[str, Any]
    error_message: str
    error_traceback: str
    timestamp: str
    retry_count: int = 0
    last_retry_time: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "query": self.query,
            "parameters": self.parameters,
            "error_message": self.error_message,
            "error_traceback": self.error_traceback,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
            "last_retry_time": self.last_retry_time,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FailedOperation":
        """Create from dictionary."""
        return cls(
            operation_id=data["operation_id"],
            operation_type=data["operation_type"],
            query=data["query"],
            parameters=data["parameters"],
            error_message=data["error_message"],
            error_traceback=data["error_traceback"],
            timestamp=data["timestamp"],
            retry_count=data.get("retry_count", 0),
            last_retry_time=data.get("last_retry_time"),
            metadata=data.get("metadata", {}),
        )


class DeadLetterQueue:
    """
    Dead letter queue for failed Neo4j operations.

    Uses Redis for persistence across restarts.
    """

    QUEUE_KEY = "neo4j:sync:dead_letter_queue"
    MAX_QUEUE_SIZE = 10000
    MAX_RETRY_ATTEMPTS = 5

    def __init__(self, redis_client=None):
        """
        Initialize dead letter queue.

        Args:
            redis_client: Redis client instance (optional, will use default if not provided)
        """
        self._redis = redis_client
        self._local_queue: List[FailedOperation] = []  # Fallback if Redis unavailable
        self._use_local = redis_client is None

        logger.info(
            "dead_letter_queue_initialized",
            storage="local" if self._use_local else "redis"
        )

    async def _get_redis(self):
        """Get Redis client, creating if needed."""
        if self._redis is None:
            try:
                from app.core.redis_client import get_redis_client
                self._redis = await get_redis_client()
                self._use_local = False
            except Exception as e:
                logger.warning("redis_unavailable_using_local", error=str(e))
                self._use_local = True
        return self._redis

    async def add_failed_operation(
        self,
        operation_type: str,
        query: str,
        parameters: Dict[str, Any],
        error: Exception,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a failed operation to the queue.

        Args:
            operation_type: Type of operation (e.g., "entity_sync", "relationship_create")
            query: The Cypher query that failed
            parameters: Query parameters
            error: The exception that occurred
            metadata: Additional context

        Returns:
            Operation ID
        """
        operation = FailedOperation(
            operation_id=str(uuid.uuid4()),
            operation_type=operation_type,
            query=query,
            parameters=parameters,
            error_message=str(error),
            error_traceback=traceback.format_exc(),
            timestamp=datetime.utcnow().isoformat(),
            metadata=metadata or {},
        )

        if self._use_local:
            self._local_queue.append(operation)
            # Trim queue if too large
            if len(self._local_queue) > self.MAX_QUEUE_SIZE:
                self._local_queue = self._local_queue[-self.MAX_QUEUE_SIZE:]
        else:
            try:
                redis = await self._get_redis()
                await redis.lpush(self.QUEUE_KEY, json.dumps(operation.to_dict()))
                await redis.ltrim(self.QUEUE_KEY, 0, self.MAX_QUEUE_SIZE - 1)
            except Exception as e:
                logger.error("dlq_add_failed", error=str(e))
                # Fallback to local
                self._local_queue.append(operation)

        logger.info(
            "dlq_operation_added",
            operation_id=operation.operation_id,
            operation_type=operation_type,
            error=str(error)
        )

        return operation.operation_id

    async def get_failed_operations(
        self,
        limit: int = 100,
        operation_type: Optional[str] = None
    ) -> List[FailedOperation]:
        """
        Retrieve failed operations from the queue.

        Args:
            limit: Maximum number of operations to retrieve
            operation_type: Filter by operation type

        Returns:
            List of failed operations
        """
        if self._use_local:
            operations = self._local_queue[:limit]
        else:
            try:
                redis = await self._get_redis()
                items = await redis.lrange(self.QUEUE_KEY, 0, limit - 1)
                operations = [
                    FailedOperation.from_dict(json.loads(item))
                    for item in items
                ]
            except Exception as e:
                logger.error("dlq_get_failed", error=str(e))
                operations = self._local_queue[:limit]

        # Filter by operation type if specified
        if operation_type:
            operations = [op for op in operations if op.operation_type == operation_type]

        return operations

    async def remove_operation(self, operation_id: str) -> bool:
        """
        Remove an operation from the queue.

        Args:
            operation_id: ID of the operation to remove

        Returns:
            True if removed, False if not found
        """
        if self._use_local:
            for i, op in enumerate(self._local_queue):
                if op.operation_id == operation_id:
                    self._local_queue.pop(i)
                    logger.info("dlq_operation_removed", operation_id=operation_id)
                    return True
            return False

        try:
            redis = await self._get_redis()
            items = await redis.lrange(self.QUEUE_KEY, 0, -1)

            for item in items:
                op = json.loads(item)
                if op.get("operation_id") == operation_id:
                    await redis.lrem(self.QUEUE_KEY, 1, item)
                    logger.info("dlq_operation_removed", operation_id=operation_id)
                    return True

            return False

        except Exception as e:
            logger.error("dlq_remove_failed", error=str(e), operation_id=operation_id)
            return False

    async def update_retry_count(self, operation_id: str) -> bool:
        """
        Increment retry count for an operation.

        Args:
            operation_id: ID of the operation

        Returns:
            True if updated, False if not found or max retries reached
        """
        operations = await self.get_failed_operations(limit=self.MAX_QUEUE_SIZE)

        for op in operations:
            if op.operation_id == operation_id:
                if op.retry_count >= self.MAX_RETRY_ATTEMPTS:
                    logger.warning(
                        "dlq_max_retries_reached",
                        operation_id=operation_id,
                        retry_count=op.retry_count
                    )
                    return False

                # Remove old entry and add updated one
                await self.remove_operation(operation_id)

                op.retry_count += 1
                op.last_retry_time = datetime.utcnow().isoformat()

                if self._use_local:
                    self._local_queue.append(op)
                else:
                    redis = await self._get_redis()
                    await redis.rpush(self.QUEUE_KEY, json.dumps(op.to_dict()))

                return True

        return False

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        if self._use_local:
            count = len(self._local_queue)
        else:
            try:
                redis = await self._get_redis()
                count = await redis.llen(self.QUEUE_KEY)
            except Exception:
                count = len(self._local_queue)

        operations = await self.get_failed_operations(limit=1000)

        # Group by operation type
        by_type: Dict[str, int] = {}
        for op in operations:
            by_type[op.operation_type] = by_type.get(op.operation_type, 0) + 1

        return {
            "total_count": count,
            "by_operation_type": by_type,
            "max_queue_size": self.MAX_QUEUE_SIZE,
            "storage": "local" if self._use_local else "redis",
        }


# ==============================================================================
# Graph Sync Monitor for Alerting
# ==============================================================================


@dataclass
class OperationStats:
    """Statistics for an operation type."""
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0
    last_success_time: Optional[float] = None
    last_failure_time: Optional[float] = None


class GraphSyncMonitor:
    """
    Monitor for Neo4j graph sync operations.

    Tracks success/failure rates and triggers alerts when thresholds are exceeded.
    """

    FAILURE_RATE_THRESHOLD = 0.2  # 20% failure rate triggers alert
    MIN_SAMPLE_SIZE = 10          # Minimum operations before alerting
    ALERT_COOLDOWN = 300          # Seconds between repeated alerts

    def __init__(self, alert_callback: Optional[Callable] = None):
        """
        Initialize monitor.

        Args:
            alert_callback: Async function to call when alert is triggered
        """
        self._stats: Dict[str, OperationStats] = {}
        self._alert_callback = alert_callback
        self._last_alert_time: Dict[str, float] = {}
        self._lock = asyncio.Lock()

        logger.info("graph_sync_monitor_initialized")

    async def record_success(
        self,
        operation_type: str,
        latency_ms: float = 0
    ):
        """
        Record a successful operation.

        Args:
            operation_type: Type of operation
            latency_ms: Operation latency in milliseconds
        """
        async with self._lock:
            if operation_type not in self._stats:
                self._stats[operation_type] = OperationStats()

            stats = self._stats[operation_type]
            stats.success_count += 1
            stats.total_latency_ms += latency_ms
            stats.last_success_time = time.time()

    async def record_failure(
        self,
        operation_type: str,
        error: Exception
    ):
        """
        Record a failed operation.

        Args:
            operation_type: Type of operation
            error: The exception that occurred
        """
        async with self._lock:
            if operation_type not in self._stats:
                self._stats[operation_type] = OperationStats()

            stats = self._stats[operation_type]
            stats.failure_count += 1
            stats.last_failure_time = time.time()

        # Check if alert should be triggered
        await self._check_alert_threshold(operation_type)

    async def _check_alert_threshold(self, operation_type: str):
        """Check if failure rate exceeds threshold and trigger alert."""
        stats = self._stats.get(operation_type)
        if not stats:
            return

        total = stats.success_count + stats.failure_count
        if total < self.MIN_SAMPLE_SIZE:
            return

        failure_rate = stats.failure_count / total

        if failure_rate >= self.FAILURE_RATE_THRESHOLD:
            # Check cooldown
            last_alert = self._last_alert_time.get(operation_type, 0)
            if time.time() - last_alert < self.ALERT_COOLDOWN:
                return

            self._last_alert_time[operation_type] = time.time()

            alert_data = {
                "level": "warning",
                "title": f"High Neo4j sync failure rate for {operation_type}",
                "message": f"Failure rate of {failure_rate:.1%} detected",
                "operation_type": operation_type,
                "stats": {
                    "success_count": stats.success_count,
                    "failure_count": stats.failure_count,
                    "failure_rate": failure_rate,
                },
            }

            logger.warning(
                "graph_sync_alert",
                **alert_data
            )

            if self._alert_callback:
                try:
                    await self._alert_callback(alert_data)
                except Exception as e:
                    logger.error("alert_callback_failed", error=str(e))

    def get_stats(self) -> Dict[str, Any]:
        """Get all operation statistics."""
        result = {}
        for op_type, stats in self._stats.items():
            total = stats.success_count + stats.failure_count
            result[op_type] = {
                "success_count": stats.success_count,
                "failure_count": stats.failure_count,
                "failure_rate": stats.failure_count / total if total > 0 else 0,
                "avg_latency_ms": (
                    stats.total_latency_ms / stats.success_count
                    if stats.success_count > 0 else 0
                ),
                "last_success": stats.last_success_time,
                "last_failure": stats.last_failure_time,
            }
        return result

    def reset_stats(self, operation_type: Optional[str] = None):
        """Reset statistics for one or all operation types."""
        if operation_type:
            if operation_type in self._stats:
                self._stats[operation_type] = OperationStats()
        else:
            self._stats.clear()


# ==============================================================================
# Enhanced Neo4j Client with Resilience
# ==============================================================================


class ResilientNeo4jClient:
    """
    Neo4j client with built-in resilience features.

    Wraps the base Neo4j HTTP client with:
    - Circuit breaker for fail-fast behavior
    - Retry logic with exponential backoff
    - Dead letter queue for failed operations
    - Monitoring and alerting
    """

    def __init__(
        self,
        base_client: Optional[Neo4jHTTPClient] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        dead_letter_queue: Optional[DeadLetterQueue] = None,
        monitor: Optional[GraphSyncMonitor] = None,
    ):
        """
        Initialize resilient client.

        Args:
            base_client: Base Neo4j HTTP client (uses singleton if not provided)
            circuit_breaker_config: Circuit breaker configuration
            retry_config: Retry configuration
            dead_letter_queue: Dead letter queue instance
            monitor: Graph sync monitor instance
        """
        self.base_client = base_client or get_neo4j_http_client()
        self.circuit_breaker = CircuitBreaker(
            name="neo4j_sync",
            config=circuit_breaker_config
        )
        self.retry_config = retry_config or RetryConfig()
        self.dlq = dead_letter_queue or DeadLetterQueue()
        self.monitor = monitor or GraphSyncMonitor()

        logger.info("resilient_neo4j_client_initialized")

    async def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        operation_type: str = "query"
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query with resilience features.

        Args:
            query: Cypher query string
            parameters: Query parameters
            operation_type: Type of operation for monitoring

        Returns:
            Query results

        Raises:
            CircuitBreakerOpen: If circuit is open
            Neo4jConnectionError: If connection fails after retries
            Neo4jQueryError: If query fails
        """
        parameters = parameters or {}
        start_time = time.time()

        try:
            # Execute through circuit breaker with retry
            result = await self.circuit_breaker.call(
                self._execute_with_retry,
                query,
                parameters,
                operation_type
            )

            # Record success
            latency_ms = (time.time() - start_time) * 1000
            await self.monitor.record_success(operation_type, latency_ms)

            return result

        except CircuitBreakerOpen:
            # Don't add to DLQ for circuit breaker - temporary state
            await self.monitor.record_failure(operation_type, CircuitBreakerOpen())
            raise

        except Exception as e:
            # Record failure and add to DLQ
            await self.monitor.record_failure(operation_type, e)
            await self.dlq.add_failed_operation(
                operation_type=operation_type,
                query=query,
                parameters=parameters,
                error=e
            )
            raise

    async def _execute_with_retry(
        self,
        query: str,
        parameters: Dict[str, Any],
        operation_type: str
    ) -> List[Dict[str, Any]]:
        """Execute query with retry logic."""
        return await retry_with_backoff(
            self.base_client.execute_query,
            query,
            parameters,
            config=self.retry_config
        )

    async def execute_batch(
        self,
        queries: List[Dict[str, Any]],
        operation_type: str = "batch"
    ) -> List[List[Dict[str, Any]]]:
        """
        Execute batch queries with resilience features.

        Args:
            queries: List of query dicts
            operation_type: Type of operation for monitoring

        Returns:
            Results for each query
        """
        start_time = time.time()

        try:
            result = await self.circuit_breaker.call(
                self._execute_batch_with_retry,
                queries
            )

            latency_ms = (time.time() - start_time) * 1000
            await self.monitor.record_success(operation_type, latency_ms)

            return result

        except CircuitBreakerOpen:
            await self.monitor.record_failure(operation_type, CircuitBreakerOpen())
            raise

        except Exception as e:
            await self.monitor.record_failure(operation_type, e)
            # Add each query to DLQ
            for query in queries:
                await self.dlq.add_failed_operation(
                    operation_type=operation_type,
                    query=query.get("statement", ""),
                    parameters=query.get("parameters", {}),
                    error=e
                )
            raise

    async def _execute_batch_with_retry(
        self,
        queries: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Execute batch with retry logic."""
        return await retry_with_backoff(
            self.base_client.execute_batch,
            queries,
            config=self.retry_config
        )

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Neo4j health and return comprehensive status.

        Returns:
            Health status including circuit breaker and queue stats
        """
        is_healthy = await self.base_client.health_check()

        return {
            "healthy": is_healthy,
            "circuit_breaker": self.circuit_breaker.get_stats(),
            "dead_letter_queue": await self.dlq.get_queue_stats(),
            "monitor": self.monitor.get_stats(),
        }

    async def close(self):
        """Close the client and release resources."""
        await self.base_client.close()


# ==============================================================================
# Singleton and Dependency Injection
# ==============================================================================


_resilient_client: Optional[ResilientNeo4jClient] = None


def get_resilient_neo4j_client() -> ResilientNeo4jClient:
    """
    Get or create singleton resilient Neo4j client.

    Use for FastAPI dependency injection:

        @app.get("/api/graph/health")
        async def health(client: ResilientNeo4jClient = Depends(get_resilient_neo4j_client)):
            return await client.health_check()
    """
    global _resilient_client
    if _resilient_client is None:
        _resilient_client = ResilientNeo4jClient()
    return _resilient_client


async def close_resilient_neo4j_client():
    """Close the singleton client. Call on application shutdown."""
    global _resilient_client
    if _resilient_client is not None:
        await _resilient_client.close()
        _resilient_client = None
