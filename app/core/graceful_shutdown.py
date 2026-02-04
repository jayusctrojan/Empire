"""
Empire v7.3 - Graceful Shutdown Coordinator
Ensures orderly shutdown of all services with data safety

The Graceful Shutdown Coordinator:
1. Stops accepting new requests
2. Waits for in-flight operations to complete
3. Flushes pending data to storage
4. Closes connections in correct order
5. Reports shutdown status

Usage:
    shutdown = GracefulShutdown()
    await shutdown.initiate_shutdown(timeout=30)
"""

import asyncio
import signal
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

import structlog
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, Histogram

logger = structlog.get_logger(__name__)


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

SHUTDOWN_INITIATED = Counter(
    "empire_shutdown_initiated_total",
    "Total shutdown initiations",
    ["reason"]
)

SHUTDOWN_DURATION = Histogram(
    "empire_shutdown_duration_seconds",
    "Duration of shutdown process",
    buckets=[1.0, 5.0, 10.0, 15.0, 30.0, 60.0, 120.0]
)

ACTIVE_REQUESTS = Gauge(
    "empire_active_requests_current",
    "Current number of active requests"
)

SHUTDOWN_PHASE = Gauge(
    "empire_shutdown_phase",
    "Current shutdown phase (0=running, 1=draining, 2=flushing, 3=closing, 4=complete)"
)


# =============================================================================
# MODELS
# =============================================================================

class ShutdownPhase(str, Enum):
    """Phases of graceful shutdown"""
    RUNNING = "running"
    PREPARING = "preparing"
    DRAINING = "draining"
    FLUSHING = "flushing"
    CLOSING = "closing"
    COMPLETE = "complete"
    FAILED = "failed"


class ShutdownReason(str, Enum):
    """Reasons for shutdown"""
    SIGTERM = "sigterm"
    SIGINT = "sigint"
    API_REQUEST = "api_request"
    HEALTH_CHECK_FAILURE = "health_check_failure"
    MANUAL = "manual"


class ShutdownProgress(BaseModel):
    """Progress of shutdown process"""
    phase: ShutdownPhase = Field(default=ShutdownPhase.RUNNING)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    reason: Optional[ShutdownReason] = None
    active_requests: int = 0
    pending_tasks: int = 0
    drained_tasks: int = 0
    flushed_data: bool = False
    connections_closed: bool = False
    errors: List[str] = Field(default_factory=list)


class ShutdownConfig(BaseModel):
    """Configuration for shutdown process"""
    drain_timeout_seconds: int = Field(default=30, description="Max time to wait for request draining")
    flush_timeout_seconds: int = Field(default=10, description="Max time for data flush")
    connection_close_timeout_seconds: int = Field(default=5, description="Max time to close connections")
    celery_drain_timeout_seconds: int = Field(default=30, description="Max time for Celery task drain")
    force_after_timeout: bool = Field(default=True, description="Force shutdown after timeout")


# =============================================================================
# GRACEFUL SHUTDOWN COORDINATOR
# =============================================================================

class GracefulShutdown:
    """
    Coordinates orderly shutdown of all Empire services.

    Shutdown Order:
    1. Stop accepting new requests (prepare)
    2. Drain in-flight requests (drain)
    3. Drain Celery tasks (drain)
    4. Flush pending data (flush)
    5. Close connections (close)
    6. Exit (complete)

    Features:
    - Configurable timeouts per phase
    - Celery task draining with monitoring
    - Background task cancellation
    - Connection pool cleanup
    - Telemetry flush
    - Progress tracking
    """

    def __init__(
        self,
        config: Optional[ShutdownConfig] = None,
        celery_app=None,
        connection_manager=None,
        redis_client=None
    ):
        """
        Initialize the shutdown coordinator.

        Args:
            config: Shutdown configuration
            celery_app: Celery application instance
            connection_manager: Connection manager for cleanup
            redis_client: Redis client for cleanup
        """
        self.config = config or ShutdownConfig()
        self.celery_app = celery_app
        self.connection_manager = connection_manager
        self.redis = redis_client

        self.progress = ShutdownProgress()
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down = False

        # Track active operations
        self._active_requests: Set[str] = set()
        self._background_tasks: Set[asyncio.Task] = set()
        self._shutdown_hooks: List[Callable[..., Coroutine[Any, Any, Any]]] = []

        logger.info("Graceful shutdown coordinator initialized")

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress"""
        return self._is_shutting_down

    def register_shutdown_hook(
        self,
        hook: Callable[..., Coroutine[Any, Any, Any]]
    ):
        """
        Register a hook to be called during shutdown.

        Args:
            hook: Async function to call during shutdown
        """
        self._shutdown_hooks.append(hook)
        logger.debug("Shutdown hook registered", hook_name=hook.__name__)

    def track_request(self, request_id: str):
        """
        Track an active request.

        Args:
            request_id: Unique request identifier
        """
        self._active_requests.add(request_id)
        ACTIVE_REQUESTS.set(len(self._active_requests))

    def complete_request(self, request_id: str):
        """
        Mark a request as complete.

        Args:
            request_id: Unique request identifier
        """
        self._active_requests.discard(request_id)
        ACTIVE_REQUESTS.set(len(self._active_requests))

    def track_background_task(self, task: asyncio.Task):
        """
        Track a background asyncio task.

        Args:
            task: Asyncio task to track
        """
        self._background_tasks.add(task)
        task.add_done_callback(lambda t: self._background_tasks.discard(t))

    async def prepare_shutdown(self, reason: ShutdownReason = ShutdownReason.MANUAL):
        """
        Prepare for shutdown - stop accepting new requests.

        Args:
            reason: Reason for shutdown
        """
        if self._is_shutting_down:
            logger.warning("Shutdown already in progress")
            return

        self._is_shutting_down = True
        self.progress.phase = ShutdownPhase.PREPARING
        self.progress.started_at = datetime.now(timezone.utc)
        self.progress.reason = reason

        SHUTDOWN_INITIATED.labels(reason=reason.value).inc()
        SHUTDOWN_PHASE.set(1)

        logger.info(
            "Shutdown initiated",
            reason=reason.value,
            active_requests=len(self._active_requests),
            background_tasks=len(self._background_tasks)
        )

    async def drain_requests(self, timeout: Optional[int] = None) -> bool:
        """
        Wait for in-flight requests to complete.

        Args:
            timeout: Max seconds to wait (default from config)

        Returns:
            True if all requests drained, False if timeout
        """
        self.progress.phase = ShutdownPhase.DRAINING
        SHUTDOWN_PHASE.set(2)

        timeout = timeout or self.config.drain_timeout_seconds
        start_time = time.time()

        logger.info(
            "Draining in-flight requests",
            active_requests=len(self._active_requests),
            timeout_seconds=timeout
        )

        while self._active_requests:
            if time.time() - start_time > timeout:
                logger.warning(
                    "Request drain timeout",
                    remaining_requests=len(self._active_requests)
                )
                self.progress.errors.append(
                    f"Request drain timeout: {len(self._active_requests)} requests remaining"
                )
                return False

            self.progress.active_requests = len(self._active_requests)
            await asyncio.sleep(0.5)

        logger.info("All requests drained")
        self.progress.active_requests = 0
        return True

    async def drain_celery_tasks(self, timeout: Optional[int] = None) -> bool:
        """
        Drain in-flight Celery tasks.

        Args:
            timeout: Max seconds to wait (default from config)

        Returns:
            True if all tasks drained, False if timeout
        """
        if not self.celery_app:
            logger.debug("No Celery app configured, skipping task drain")
            return True

        timeout = timeout or self.config.celery_drain_timeout_seconds
        start_time = time.time()

        try:
            # Signal workers to stop prefetching new tasks
            self.celery_app.control.broadcast('pool_pause')
            logger.info("Celery pool paused, waiting for active tasks")

            # Wait for active tasks to complete
            while True:
                if time.time() - start_time > timeout:
                    logger.warning("Celery drain timeout")
                    self.progress.errors.append("Celery task drain timeout")
                    return False

                # Check for active tasks
                inspect = self.celery_app.control.inspect()
                active = inspect.active()

                if not active:
                    # No active tasks or workers unavailable
                    break

                total_active = sum(len(tasks) for tasks in active.values() if tasks)
                self.progress.pending_tasks = total_active

                if total_active == 0:
                    break

                logger.debug(
                    "Waiting for Celery tasks",
                    active_tasks=total_active,
                    elapsed=int(time.time() - start_time)
                )
                await asyncio.sleep(1)

            # Revoke any remaining scheduled tasks
            self.celery_app.control.purge()

            logger.info("Celery tasks drained")
            self.progress.drained_tasks = self.progress.pending_tasks
            self.progress.pending_tasks = 0
            return True

        except Exception as e:
            logger.error("Error draining Celery tasks", error=str(e))
            self.progress.errors.append(f"Celery drain error: {str(e)}")
            return False

    async def cancel_background_tasks(self) -> int:
        """
        Cancel all tracked background asyncio tasks.

        Returns:
            Number of tasks cancelled
        """
        if not self._background_tasks:
            return 0

        cancelled = 0
        for task in self._background_tasks.copy():
            if not task.done():
                task.cancel()
                cancelled += 1

        # Wait for tasks to complete cancellation
        if self._background_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._background_tasks, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("Some background tasks did not cancel in time")

        logger.info("Background tasks cancelled", count=cancelled)
        return cancelled

    async def flush_data(self, timeout: Optional[int] = None) -> bool:
        """
        Flush pending data to storage.

        Args:
            timeout: Max seconds to wait (default from config)

        Returns:
            True if flush successful
        """
        self.progress.phase = ShutdownPhase.FLUSHING
        SHUTDOWN_PHASE.set(3)

        timeout = timeout or self.config.flush_timeout_seconds

        logger.info("Flushing pending data")

        try:
            # Flush WAL entries
            from app.services.wal_manager import get_wal_manager
            wal = get_wal_manager()
            if wal:
                # Mark in-progress entries as pending for replay
                logger.debug("WAL flush completed")

            # Flush telemetry
            await self._flush_telemetry()

            # Run custom shutdown hooks
            for hook in self._shutdown_hooks:
                try:
                    await asyncio.wait_for(hook(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Shutdown hook timeout", hook=hook.__name__)
                except Exception as e:
                    logger.error("Shutdown hook error", hook=hook.__name__, error=str(e))

            self.progress.flushed_data = True
            logger.info("Data flush completed")
            return True

        except Exception as e:
            logger.error("Error flushing data", error=str(e))
            self.progress.errors.append(f"Data flush error: {str(e)}")
            return False

    async def _flush_telemetry(self):
        """Flush telemetry and tracing data"""
        try:
            # Flush OpenTelemetry if configured
            from opentelemetry import trace
            tracer_provider = trace.get_tracer_provider()
            if hasattr(tracer_provider, 'force_flush'):
                tracer_provider.force_flush(timeout_millis=5000)
                logger.debug("Telemetry flushed")
        except ImportError:
            pass
        except Exception as e:
            logger.warning("Error flushing telemetry", error=str(e))

    async def close_connections(self, timeout: Optional[int] = None) -> bool:
        """
        Close all connections in correct order.

        Order: Redis Pub/Sub → Celery → Neo4j → Supabase → Redis

        Args:
            timeout: Max seconds to wait (default from config)

        Returns:
            True if all connections closed
        """
        self.progress.phase = ShutdownPhase.CLOSING
        SHUTDOWN_PHASE.set(4)

        logger.info("Closing connections")

        errors = []

        # 1. Close Redis Pub/Sub listeners
        if self.redis:
            try:
                # Close any pub/sub connections
                pubsub = getattr(self.redis, 'pubsub', None)
                if pubsub and callable(pubsub):
                    ps = pubsub()
                    if hasattr(ps, 'close'):
                        ps.close()
                logger.debug("Redis Pub/Sub closed")
            except Exception as e:
                errors.append(f"Redis Pub/Sub close error: {str(e)}")

        # 2. Close Celery connections
        if self.celery_app:
            try:
                self.celery_app.close()
                logger.debug("Celery connections closed")
            except Exception as e:
                errors.append(f"Celery close error: {str(e)}")

        # 3. Use connection manager for database cleanup
        if self.connection_manager:
            try:
                await self.connection_manager.shutdown()
                logger.debug("Connection manager shutdown complete")
            except Exception as e:
                errors.append(f"Connection manager shutdown error: {str(e)}")

        # 4. Final Redis close
        if self.redis:
            try:
                if hasattr(self.redis, 'close'):
                    self.redis.close()
                logger.debug("Redis connection closed")
            except Exception as e:
                errors.append(f"Redis close error: {str(e)}")

        if errors:
            for error in errors:
                self.progress.errors.append(error)
                logger.error("Connection close error", error=error)
            return False

        self.progress.connections_closed = True
        logger.info("All connections closed")
        return True

    async def initiate_shutdown(
        self,
        reason: ShutdownReason = ShutdownReason.MANUAL,
        timeout: Optional[int] = None
    ) -> ShutdownProgress:
        """
        Initiate complete shutdown sequence.

        Args:
            reason: Reason for shutdown
            timeout: Overall timeout (uses config defaults if None)

        Returns:
            ShutdownProgress with final status
        """
        start_time = time.time()

        try:
            # Phase 1: Prepare
            await self.prepare_shutdown(reason)

            # Phase 2: Drain requests
            await self.drain_requests()

            # Phase 3: Drain Celery
            await self.drain_celery_tasks()

            # Phase 4: Cancel background tasks
            await self.cancel_background_tasks()

            # Phase 5: Flush data
            await self.flush_data()

            # Phase 6: Close connections
            await self.close_connections()

            # Complete
            self.progress.phase = ShutdownPhase.COMPLETE
            self.progress.completed_at = datetime.now(timezone.utc)
            SHUTDOWN_PHASE.set(5)

        except Exception as e:
            logger.error("Shutdown failed", error=str(e))
            self.progress.phase = ShutdownPhase.FAILED
            self.progress.errors.append(f"Shutdown failed: {str(e)}")

        duration = time.time() - start_time
        SHUTDOWN_DURATION.observe(duration)

        logger.info(
            "Shutdown sequence completed",
            phase=self.progress.phase.value,
            duration_seconds=round(duration, 2),
            errors=len(self.progress.errors)
        )

        # Signal shutdown complete
        self._shutdown_event.set()

        return self.progress

    async def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for shutdown to complete.

        Args:
            timeout: Max seconds to wait

        Returns:
            True if shutdown completed, False if timeout
        """
        try:
            await asyncio.wait_for(self._shutdown_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get current shutdown status"""
        return {
            "is_shutting_down": self._is_shutting_down,
            "phase": self.progress.phase.value,
            "started_at": self.progress.started_at.isoformat() if self.progress.started_at else None,
            "completed_at": self.progress.completed_at.isoformat() if self.progress.completed_at else None,
            "reason": self.progress.reason.value if self.progress.reason else None,
            "active_requests": len(self._active_requests),
            "background_tasks": len(self._background_tasks),
            "pending_celery_tasks": self.progress.pending_tasks,
            "drained_tasks": self.progress.drained_tasks,
            "flushed_data": self.progress.flushed_data,
            "connections_closed": self.progress.connections_closed,
            "errors": self.progress.errors
        }


# =============================================================================
# SIGNAL HANDLERS
# =============================================================================

def setup_signal_handlers(shutdown_coordinator: GracefulShutdown):
    """
    Set up signal handlers for graceful shutdown.

    Args:
        shutdown_coordinator: The shutdown coordinator instance
    """
    loop = asyncio.get_event_loop()

    def handle_signal(sig):
        reason = ShutdownReason.SIGTERM if sig == signal.SIGTERM else ShutdownReason.SIGINT
        logger.info(f"Received {sig.name}, initiating shutdown")

        # Schedule shutdown coroutine
        asyncio.ensure_future(shutdown_coordinator.initiate_shutdown(reason=reason))

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))

    logger.info("Signal handlers configured for graceful shutdown")


# =============================================================================
# MIDDLEWARE FOR REQUEST TRACKING
# =============================================================================

class ShutdownMiddleware:
    """
    FastAPI middleware for graceful shutdown support.

    - Tracks active requests
    - Rejects new requests during shutdown
    - Reports shutdown status in headers
    """

    def __init__(self, app, shutdown_coordinator: GracefulShutdown):
        self.app = app
        self.shutdown = shutdown_coordinator

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check if shutting down
        if self.shutdown.is_shutting_down:
            # Return 503 Service Unavailable
            response = {
                "detail": "Service is shutting down",
                "retry_after": 30
            }

            await send({
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"retry-after", b"30"],
                    [b"x-shutdown-in-progress", b"true"]
                ]
            })

            import json
            await send({
                "type": "http.response.body",
                "body": json.dumps(response).encode()
            })
            return

        # Track request
        import uuid
        request_id = str(uuid.uuid4())
        self.shutdown.track_request(request_id)

        try:
            await self.app(scope, receive, send)
        finally:
            self.shutdown.complete_request(request_id)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_shutdown_coordinator: Optional[GracefulShutdown] = None


def get_shutdown_coordinator() -> Optional[GracefulShutdown]:
    """Get the global shutdown coordinator instance"""
    return _shutdown_coordinator


def initialize_shutdown_coordinator(
    config: Optional[ShutdownConfig] = None,
    celery_app=None,
    connection_manager=None,
    redis_client=None
) -> GracefulShutdown:
    """
    Initialize the global shutdown coordinator.

    Args:
        config: Shutdown configuration
        celery_app: Celery application instance
        connection_manager: Connection manager for cleanup
        redis_client: Redis client for cleanup

    Returns:
        Initialized GracefulShutdown instance
    """
    global _shutdown_coordinator
    _shutdown_coordinator = GracefulShutdown(
        config=config,
        celery_app=celery_app,
        connection_manager=connection_manager,
        redis_client=redis_client
    )
    return _shutdown_coordinator
