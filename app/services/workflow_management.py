"""
Empire v7.3 - Workflow Management System (Task 158)

Comprehensive workflow management with:
- State Persistence: Checkpoint and resume workflows
- Graceful Shutdown: Signal handling and cleanup
- Cancellation Tokens: Task cancellation support
- Metrics Collection: Prometheus metrics and logging

Author: Claude Code
Date: 2025-01-15
"""

import os
import sys
import json
import time
import signal
import asyncio
import hashlib
import threading
from pathlib import Path
from enum import Enum
from datetime import datetime
from typing import (
    Dict, Any, List, Optional, Callable, TypeVar, Generic,
    Awaitable, Set, Union
)
from dataclasses import dataclass, field, asdict
from contextlib import asynccontextmanager
from functools import wraps

import structlog
from prometheus_client import Counter, Histogram, Gauge, Info

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

logger = structlog.get_logger(__name__)

T = TypeVar("T")


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

WORKFLOW_STARTED = Counter(
    "empire_workflow_started_total",
    "Total workflows started",
    ["workflow_type", "workflow_id"]
)

WORKFLOW_COMPLETED = Counter(
    "empire_workflow_completed_total",
    "Total workflows completed",
    ["workflow_type", "workflow_id", "status"]
)

WORKFLOW_DURATION = Histogram(
    "empire_workflow_duration_seconds",
    "Workflow execution duration",
    ["workflow_type"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
)

WORKFLOW_TASK_DURATION = Histogram(
    "empire_workflow_task_duration_seconds",
    "Individual task duration within workflows",
    ["workflow_type", "task_name"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120]
)

WORKFLOW_ACTIVE = Gauge(
    "empire_workflow_active_count",
    "Number of currently active workflows",
    ["workflow_type"]
)

WORKFLOW_CANCELLED = Counter(
    "empire_workflow_cancelled_total",
    "Total workflows cancelled",
    ["workflow_type", "reason"]
)

WORKFLOW_CHECKPOINTS = Counter(
    "empire_workflow_checkpoints_total",
    "Total workflow checkpoints saved",
    ["workflow_type", "checkpoint_type"]
)

WORKFLOW_RECOVERIES = Counter(
    "empire_workflow_recoveries_total",
    "Total workflow recoveries attempted",
    ["workflow_type", "success"]
)


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class WorkflowStatus(str, Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECOVERING = "recovering"


class CheckpointType(str, Enum):
    """Types of workflow checkpoints"""
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    MILESTONE = "milestone"
    PERIODIC = "periodic"
    SHUTDOWN = "shutdown"


class StorageBackend(str, Enum):
    """Supported storage backends for state persistence"""
    FILE = "file"
    REDIS = "redis"
    MEMORY = "memory"


@dataclass
class WorkflowState:
    """
    Represents the complete state of a workflow for persistence.
    """
    workflow_id: str
    workflow_type: str
    status: WorkflowStatus
    current_task: Optional[str] = None
    completed_tasks: List[str] = field(default_factory=list)
    pending_tasks: List[str] = field(default_factory=list)
    task_results: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    checkpoint_version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowState":
        """Create from dictionary"""
        data = data.copy()
        data["status"] = WorkflowStatus(data["status"])
        return cls(**data)


@dataclass
class TaskMetrics:
    """Metrics for an individual task within a workflow"""
    task_id: str
    task_name: str
    workflow_id: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    status: str = "running"
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# CANCELLATION TOKEN
# =============================================================================

class CancellationToken:
    """
    Token for cooperative task cancellation.

    Allows tasks to be cancelled gracefully by checking the token periodically.
    Supports callbacks for cleanup when cancellation is requested.

    Example:
        ```python
        token = CancellationToken()

        async def long_task(token: CancellationToken):
            for i in range(100):
                if token.is_cancelled():
                    # Cleanup and return
                    return "cancelled"
                await process_item(i)
            return "completed"

        # Later, to cancel:
        token.cancel(reason="User requested cancellation")
        ```
    """

    def __init__(self, parent: Optional["CancellationToken"] = None):
        self._cancelled = False
        self._cancel_reason: Optional[str] = None
        self._cancel_time: Optional[float] = None
        self._callbacks: List[Callable[[], None]] = []
        self._async_callbacks: List[Callable[[], Awaitable[None]]] = []
        self._parent = parent
        self._children: Set["CancellationToken"] = set()
        self._lock = asyncio.Lock()

        if parent:
            parent._register_child(self)

    @property
    def cancelled(self) -> bool:
        """Check if cancellation has been requested"""
        return self._cancelled or (self._parent and self._parent.cancelled)

    @property
    def cancel_reason(self) -> Optional[str]:
        """Get the reason for cancellation"""
        if self._cancelled:
            return self._cancel_reason
        if self._parent and self._parent.cancelled:
            return self._parent.cancel_reason
        return None

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested (alias for cancelled property)"""
        return self.cancelled

    async def cancel(self, reason: str = "Cancellation requested") -> None:
        """
        Request cancellation and execute callbacks.

        Args:
            reason: Reason for cancellation
        """
        async with self._lock:
            if self._cancelled:
                return

            self._cancelled = True
            self._cancel_reason = reason
            self._cancel_time = time.time()

            logger.info(
                "Cancellation requested",
                reason=reason,
                callback_count=len(self._callbacks) + len(self._async_callbacks)
            )

            # Execute sync callbacks
            for callback in self._callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error("Cancellation callback error", error=str(e))

            # Execute async callbacks
            for callback in self._async_callbacks:
                try:
                    await callback()
                except Exception as e:
                    logger.error("Async cancellation callback error", error=str(e))

            # Cancel all child tokens
            for child in self._children:
                await child.cancel(reason=f"Parent cancelled: {reason}")

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register a synchronous callback to execute on cancellation"""
        self._callbacks.append(callback)

    def register_async_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register an asynchronous callback to execute on cancellation"""
        self._async_callbacks.append(callback)

    def _register_child(self, child: "CancellationToken") -> None:
        """Register a child token"""
        self._children.add(child)

    def create_child(self) -> "CancellationToken":
        """Create a child cancellation token linked to this one"""
        return CancellationToken(parent=self)

    def check_cancelled(self) -> None:
        """Raise CancellationError if cancelled"""
        if self.cancelled:
            raise CancellationError(self.cancel_reason or "Operation cancelled")

    def get_status(self) -> Dict[str, Any]:
        """Get cancellation token status"""
        return {
            "cancelled": self._cancelled,
            "reason": self._cancel_reason,
            "cancel_time": self._cancel_time,
            "callback_count": len(self._callbacks) + len(self._async_callbacks),
            "children_count": len(self._children),
            "has_parent": self._parent is not None,
        }


class CancellationError(Exception):
    """Exception raised when an operation is cancelled"""
    pass


# =============================================================================
# WORKFLOW STATE MANAGER
# =============================================================================

class WorkflowStateManager:
    """
    Manages workflow state persistence with multiple storage backends.

    Supports:
    - File-based storage for development/single-instance
    - Redis storage for distributed deployments
    - In-memory storage for testing

    Example:
        ```python
        manager = WorkflowStateManager(backend="redis")

        # Save state
        state = WorkflowState(
            workflow_id="wf-123",
            workflow_type="document_analysis",
            status=WorkflowStatus.RUNNING,
            current_task="extract_entities"
        )
        await manager.save_state(state)

        # Load state
        recovered = await manager.load_state("wf-123")

        # Checkpoint
        await manager.checkpoint(state, CheckpointType.TASK_COMPLETE)
        ```
    """

    def __init__(
        self,
        backend: Union[str, StorageBackend] = StorageBackend.FILE,
        storage_path: str = "./workflow_states",
        redis_url: Optional[str] = None,
        checkpoint_interval: float = 30.0,
        max_checkpoints: int = 10,
    ):
        self.backend = StorageBackend(backend) if isinstance(backend, str) else backend
        self.storage_path = Path(storage_path)
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.checkpoint_interval = checkpoint_interval
        self.max_checkpoints = max_checkpoints

        self._redis: Optional[Any] = None
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

        # Create storage directory for file backend
        if self.backend == StorageBackend.FILE:
            self.storage_path.mkdir(parents=True, exist_ok=True)

        logger.info(
            "WorkflowStateManager initialized",
            backend=self.backend.value,
            storage_path=str(self.storage_path) if self.backend == StorageBackend.FILE else None
        )

    async def initialize(self) -> None:
        """Initialize storage backend connections"""
        if self._initialized:
            return

        if self.backend == StorageBackend.REDIS:
            if aioredis is None:
                raise RuntimeError("redis package not installed for Redis backend")

            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Redis connection established for workflow state")

        self._initialized = True

    async def save_state(self, state: WorkflowState) -> None:
        """
        Save workflow state to storage.

        Args:
            state: WorkflowState to persist
        """
        await self.initialize()

        state.updated_at = datetime.utcnow().isoformat()
        state_dict = state.to_dict()

        try:
            if self.backend == StorageBackend.FILE:
                await self._save_to_file(state.workflow_id, state_dict)
            elif self.backend == StorageBackend.REDIS:
                await self._save_to_redis(state.workflow_id, state_dict)
            else:  # MEMORY
                self._memory_store[state.workflow_id] = state_dict

            logger.debug("Workflow state saved", workflow_id=state.workflow_id)

        except Exception as e:
            logger.error("Failed to save workflow state", workflow_id=state.workflow_id, error=str(e))
            raise

    async def load_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """
        Load workflow state from storage.

        Args:
            workflow_id: ID of workflow to load

        Returns:
            WorkflowState if found, None otherwise
        """
        await self.initialize()

        try:
            if self.backend == StorageBackend.FILE:
                state_dict = await self._load_from_file(workflow_id)
            elif self.backend == StorageBackend.REDIS:
                state_dict = await self._load_from_redis(workflow_id)
            else:  # MEMORY
                state_dict = self._memory_store.get(workflow_id)

            if state_dict:
                return WorkflowState.from_dict(state_dict)
            return None

        except Exception as e:
            logger.error("Failed to load workflow state", workflow_id=workflow_id, error=str(e))
            return None

    async def checkpoint(
        self,
        state: WorkflowState,
        checkpoint_type: CheckpointType,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a checkpoint of the current workflow state.

        Args:
            state: Current workflow state
            checkpoint_type: Type of checkpoint
            metadata: Optional additional metadata

        Returns:
            Checkpoint ID
        """
        checkpoint_id = f"{state.workflow_id}-{checkpoint_type.value}-{int(time.time())}"

        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "checkpoint_type": checkpoint_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "state": state.to_dict(),
            "metadata": metadata or {}
        }

        # Save checkpoint
        if self.backend == StorageBackend.FILE:
            checkpoint_path = self.storage_path / "checkpoints" / f"{checkpoint_id}.json"
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            with open(checkpoint_path, "w") as f:
                json.dump(checkpoint_data, f, indent=2)
        elif self.backend == StorageBackend.REDIS:
            await self._redis.hset(
                f"workflow:checkpoints:{state.workflow_id}",
                checkpoint_id,
                json.dumps(checkpoint_data)
            )
        else:
            if "checkpoints" not in self._memory_store:
                self._memory_store["checkpoints"] = {}
            self._memory_store["checkpoints"][checkpoint_id] = checkpoint_data

        # Update metrics
        WORKFLOW_CHECKPOINTS.labels(
            workflow_type=state.workflow_type,
            checkpoint_type=checkpoint_type.value
        ).inc()

        logger.info(
            "Checkpoint created",
            workflow_id=state.workflow_id,
            checkpoint_id=checkpoint_id,
            checkpoint_type=checkpoint_type.value
        )

        # Cleanup old checkpoints
        await self._cleanup_old_checkpoints(state.workflow_id)

        return checkpoint_id

    async def restore_from_checkpoint(
        self,
        workflow_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[WorkflowState]:
        """
        Restore workflow state from a checkpoint.

        Args:
            workflow_id: Workflow to restore
            checkpoint_id: Specific checkpoint to restore (latest if None)

        Returns:
            Restored WorkflowState or None
        """
        try:
            if checkpoint_id:
                checkpoint_data = await self._get_checkpoint(checkpoint_id)
            else:
                checkpoint_data = await self._get_latest_checkpoint(workflow_id)

            if checkpoint_data:
                state = WorkflowState.from_dict(checkpoint_data["state"])
                state.status = WorkflowStatus.RECOVERING

                WORKFLOW_RECOVERIES.labels(
                    workflow_type=state.workflow_type,
                    success="true"
                ).inc()

                logger.info(
                    "Workflow restored from checkpoint",
                    workflow_id=workflow_id,
                    checkpoint_id=checkpoint_data.get("checkpoint_id")
                )

                return state

            return None

        except Exception as e:
            logger.error("Failed to restore from checkpoint", workflow_id=workflow_id, error=str(e))
            WORKFLOW_RECOVERIES.labels(
                workflow_type="unknown",
                success="false"
            ).inc()
            return None

    async def list_workflows(
        self,
        status: Optional[WorkflowStatus] = None,
        workflow_type: Optional[str] = None
    ) -> List[WorkflowState]:
        """List all workflows, optionally filtered by status or type"""
        await self.initialize()

        workflows = []

        if self.backend == StorageBackend.FILE:
            for state_file in self.storage_path.glob("*.json"):
                if state_file.name.startswith("checkpoint"):
                    continue
                try:
                    with open(state_file) as f:
                        state = WorkflowState.from_dict(json.load(f))
                        if status and state.status != status:
                            continue
                        if workflow_type and state.workflow_type != workflow_type:
                            continue
                        workflows.append(state)
                except Exception:
                    pass
        elif self.backend == StorageBackend.REDIS:
            keys = await self._redis.keys("workflow:state:*")
            for key in keys:
                try:
                    data = await self._redis.get(key)
                    if data:
                        state = WorkflowState.from_dict(json.loads(data))
                        if status and state.status != status:
                            continue
                        if workflow_type and state.workflow_type != workflow_type:
                            continue
                        workflows.append(state)
                except Exception:
                    pass
        else:
            for wf_id, data in self._memory_store.items():
                if wf_id == "checkpoints":
                    continue
                try:
                    state = WorkflowState.from_dict(data)
                    if status and state.status != status:
                        continue
                    if workflow_type and state.workflow_type != workflow_type:
                        continue
                    workflows.append(state)
                except Exception:
                    pass

        return workflows

    async def delete_state(self, workflow_id: str) -> bool:
        """Delete workflow state"""
        await self.initialize()

        try:
            if self.backend == StorageBackend.FILE:
                state_file = self.storage_path / f"{workflow_id}.json"
                if state_file.exists():
                    state_file.unlink()
            elif self.backend == StorageBackend.REDIS:
                await self._redis.delete(f"workflow:state:{workflow_id}")
            else:
                self._memory_store.pop(workflow_id, None)

            return True
        except Exception as e:
            logger.error("Failed to delete workflow state", workflow_id=workflow_id, error=str(e))
            return False

    # Private methods for file storage
    async def _save_to_file(self, workflow_id: str, state_dict: Dict) -> None:
        state_file = self.storage_path / f"{workflow_id}.json"
        with open(state_file, "w") as f:
            json.dump(state_dict, f, indent=2)

    async def _load_from_file(self, workflow_id: str) -> Optional[Dict]:
        state_file = self.storage_path / f"{workflow_id}.json"
        if state_file.exists():
            with open(state_file) as f:
                return json.load(f)
        return None

    # Private methods for Redis storage
    async def _save_to_redis(self, workflow_id: str, state_dict: Dict) -> None:
        await self._redis.set(
            f"workflow:state:{workflow_id}",
            json.dumps(state_dict),
            ex=86400 * 7  # 7 day TTL
        )

    async def _load_from_redis(self, workflow_id: str) -> Optional[Dict]:
        data = await self._redis.get(f"workflow:state:{workflow_id}")
        if data:
            return json.loads(data)
        return None

    async def _get_checkpoint(self, checkpoint_id: str) -> Optional[Dict]:
        if self.backend == StorageBackend.FILE:
            checkpoint_path = self.storage_path / "checkpoints" / f"{checkpoint_id}.json"
            if checkpoint_path.exists():
                with open(checkpoint_path) as f:
                    return json.load(f)
        elif self.backend == StorageBackend.REDIS:
            # Extract workflow_id from checkpoint_id
            workflow_id = checkpoint_id.rsplit("-", 2)[0]
            data = await self._redis.hget(f"workflow:checkpoints:{workflow_id}", checkpoint_id)
            if data:
                return json.loads(data)
        else:
            checkpoints = self._memory_store.get("checkpoints", {})
            return checkpoints.get(checkpoint_id)
        return None

    async def _get_latest_checkpoint(self, workflow_id: str) -> Optional[Dict]:
        if self.backend == StorageBackend.FILE:
            checkpoint_dir = self.storage_path / "checkpoints"
            if not checkpoint_dir.exists():
                return None
            checkpoints = list(checkpoint_dir.glob(f"{workflow_id}-*.json"))
            if checkpoints:
                latest = max(checkpoints, key=lambda p: p.stat().st_mtime)
                with open(latest) as f:
                    return json.load(f)
        elif self.backend == StorageBackend.REDIS:
            all_checkpoints = await self._redis.hgetall(f"workflow:checkpoints:{workflow_id}")
            if all_checkpoints:
                latest_key = max(all_checkpoints.keys())
                return json.loads(all_checkpoints[latest_key])
        else:
            checkpoints = self._memory_store.get("checkpoints", {})
            wf_checkpoints = {k: v for k, v in checkpoints.items() if k.startswith(workflow_id)}
            if wf_checkpoints:
                latest_key = max(wf_checkpoints.keys())
                return wf_checkpoints[latest_key]
        return None

    async def _cleanup_old_checkpoints(self, workflow_id: str) -> None:
        """Remove old checkpoints beyond max_checkpoints limit"""
        try:
            if self.backend == StorageBackend.FILE:
                checkpoint_dir = self.storage_path / "checkpoints"
                if checkpoint_dir.exists():
                    checkpoints = sorted(
                        checkpoint_dir.glob(f"{workflow_id}-*.json"),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True
                    )
                    for old_checkpoint in checkpoints[self.max_checkpoints:]:
                        old_checkpoint.unlink()
            elif self.backend == StorageBackend.REDIS:
                all_checkpoints = await self._redis.hgetall(f"workflow:checkpoints:{workflow_id}")
                if len(all_checkpoints) > self.max_checkpoints:
                    sorted_keys = sorted(all_checkpoints.keys(), reverse=True)
                    for old_key in sorted_keys[self.max_checkpoints:]:
                        await self._redis.hdel(f"workflow:checkpoints:{workflow_id}", old_key)
        except Exception as e:
            logger.warning("Failed to cleanup old checkpoints", workflow_id=workflow_id, error=str(e))


# =============================================================================
# GRACEFUL SHUTDOWN HANDLER
# =============================================================================

class GracefulShutdownHandler:
    """
    Handles graceful shutdown of workflows on SIGTERM/SIGINT signals.

    Ensures:
    - All running workflows are paused
    - State is saved before shutdown
    - Resources are properly cleaned up

    Example:
        ```python
        state_manager = WorkflowStateManager()
        shutdown_handler = GracefulShutdownHandler(state_manager)

        # Register a workflow
        shutdown_handler.register_workflow("wf-123", workflow_state)

        # On shutdown, all registered workflows will be saved
        ```
    """

    def __init__(
        self,
        state_manager: WorkflowStateManager,
        shutdown_timeout: float = 30.0,
    ):
        self.state_manager = state_manager
        self.shutdown_timeout = shutdown_timeout
        self._active_workflows: Dict[str, WorkflowState] = {}
        self._cancellation_tokens: Dict[str, CancellationToken] = {}
        self._cleanup_callbacks: List[Callable[[], Awaitable[None]]] = []
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down = False
        self._original_handlers: Dict[int, Any] = {}

        logger.info("GracefulShutdownHandler initialized", timeout=shutdown_timeout)

    def install_signal_handlers(self) -> None:
        """Install signal handlers for SIGTERM and SIGINT"""
        # Signal handlers can only be installed from the main thread
        if threading.current_thread() is not threading.main_thread():
            logger.warning(
                "Cannot install signal handlers from non-main thread",
                thread_name=threading.current_thread().name
            )
            return

        for sig in (signal.SIGTERM, signal.SIGINT):
            self._original_handlers[sig] = signal.signal(sig, self._signal_handler)

        logger.info("Signal handlers installed", signals=["SIGTERM", "SIGINT"])

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals"""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown")

        # Schedule async shutdown
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.shutdown())
            else:
                loop.run_until_complete(self.shutdown())
        except RuntimeError:
            # No event loop, use synchronous approach
            self._sync_shutdown()

    def _sync_shutdown(self) -> None:
        """Synchronous shutdown fallback"""
        self._is_shutting_down = True
        logger.warning("Performing synchronous shutdown (no event loop)")
        # Best effort - can't do async operations
        sys.exit(0)

    async def shutdown(self) -> None:
        """
        Perform graceful shutdown of all workflows.
        """
        if self._is_shutting_down:
            return

        self._is_shutting_down = True
        self._shutdown_event.set()

        logger.info(
            "Starting graceful shutdown",
            active_workflows=len(self._active_workflows),
            timeout=self.shutdown_timeout
        )

        try:
            # Cancel all cancellation tokens
            for workflow_id, token in self._cancellation_tokens.items():
                await token.cancel(reason="Graceful shutdown")

            # Pause and save all workflows
            for workflow_id, state in self._active_workflows.items():
                try:
                    state.status = WorkflowStatus.PAUSED
                    await self.state_manager.checkpoint(
                        state,
                        CheckpointType.SHUTDOWN,
                        metadata={"shutdown_time": datetime.utcnow().isoformat()}
                    )
                    await self.state_manager.save_state(state)
                    logger.info("Workflow state saved on shutdown", workflow_id=workflow_id)
                except Exception as e:
                    logger.error(
                        "Failed to save workflow on shutdown",
                        workflow_id=workflow_id,
                        error=str(e)
                    )

            # Run cleanup callbacks
            for callback in self._cleanup_callbacks:
                try:
                    await asyncio.wait_for(callback(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Cleanup callback timed out")
                except Exception as e:
                    logger.error("Cleanup callback error", error=str(e))

            logger.info("Graceful shutdown completed")

        except Exception as e:
            logger.error("Error during graceful shutdown", error=str(e))

        # Restore original signal handlers
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)

    def register_workflow(
        self,
        workflow_id: str,
        state: WorkflowState,
        token: Optional[CancellationToken] = None
    ) -> None:
        """Register a workflow for shutdown handling"""
        self._active_workflows[workflow_id] = state
        if token:
            self._cancellation_tokens[workflow_id] = token

    def unregister_workflow(self, workflow_id: str) -> None:
        """Unregister a workflow from shutdown handling"""
        self._active_workflows.pop(workflow_id, None)
        self._cancellation_tokens.pop(workflow_id, None)

    def register_cleanup_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register a cleanup callback to run on shutdown"""
        self._cleanup_callbacks.append(callback)

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress"""
        return self._is_shutting_down

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal"""
        await self._shutdown_event.wait()


# =============================================================================
# WORKFLOW METRICS COLLECTOR
# =============================================================================

class WorkflowMetricsCollector:
    """
    Collects and records metrics for workflow executions.

    Provides:
    - Task-level timing and status metrics
    - Workflow duration tracking
    - Error rate monitoring
    - Prometheus-compatible metrics

    Example:
        ```python
        collector = WorkflowMetricsCollector()

        # Start tracking
        collector.record_workflow_start("wf-123", "document_analysis")
        collector.record_task_start("wf-123", "task-1", "extract_entities")

        # Complete task
        collector.record_task_completion("wf-123", "task-1", success=True)

        # Complete workflow
        collector.record_workflow_completion("wf-123", success=True)

        # Get metrics
        metrics = collector.get_workflow_metrics("wf-123")
        ```
    """

    def __init__(self):
        self._workflow_metrics: Dict[str, Dict[str, Any]] = {}
        self._task_metrics: Dict[str, Dict[str, TaskMetrics]] = {}

        logger.info("WorkflowMetricsCollector initialized")

    def record_workflow_start(
        self,
        workflow_id: str,
        workflow_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record workflow start"""
        self._workflow_metrics[workflow_id] = {
            "workflow_id": workflow_id,
            "workflow_type": workflow_type,
            "start_time": time.time(),
            "status": "running",
            "task_count": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "metadata": metadata or {}
        }
        self._task_metrics[workflow_id] = {}

        # Update Prometheus metrics
        WORKFLOW_STARTED.labels(
            workflow_type=workflow_type,
            workflow_id=workflow_id
        ).inc()
        WORKFLOW_ACTIVE.labels(workflow_type=workflow_type).inc()

        logger.info("Workflow started", workflow_id=workflow_id, workflow_type=workflow_type)

    def record_workflow_completion(
        self,
        workflow_id: str,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """Record workflow completion"""
        if workflow_id not in self._workflow_metrics:
            return

        metrics = self._workflow_metrics[workflow_id]
        metrics["end_time"] = time.time()
        metrics["duration"] = metrics["end_time"] - metrics["start_time"]
        metrics["status"] = "completed" if success else "failed"
        metrics["error"] = error

        # Update Prometheus metrics
        workflow_type = metrics["workflow_type"]
        WORKFLOW_COMPLETED.labels(
            workflow_type=workflow_type,
            workflow_id=workflow_id,
            status=metrics["status"]
        ).inc()
        WORKFLOW_DURATION.labels(workflow_type=workflow_type).observe(metrics["duration"])
        WORKFLOW_ACTIVE.labels(workflow_type=workflow_type).dec()

        logger.info(
            "Workflow completed",
            workflow_id=workflow_id,
            success=success,
            duration=metrics["duration"]
        )

    def record_workflow_cancellation(
        self,
        workflow_id: str,
        reason: str = "unknown"
    ) -> None:
        """Record workflow cancellation"""
        if workflow_id not in self._workflow_metrics:
            return

        metrics = self._workflow_metrics[workflow_id]
        metrics["end_time"] = time.time()
        metrics["duration"] = metrics["end_time"] - metrics["start_time"]
        metrics["status"] = "cancelled"
        metrics["cancellation_reason"] = reason

        workflow_type = metrics["workflow_type"]
        WORKFLOW_CANCELLED.labels(workflow_type=workflow_type, reason=reason).inc()
        WORKFLOW_ACTIVE.labels(workflow_type=workflow_type).dec()

        logger.info("Workflow cancelled", workflow_id=workflow_id, reason=reason)

    def record_task_start(
        self,
        workflow_id: str,
        task_id: str,
        task_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record task start within a workflow"""
        if workflow_id not in self._task_metrics:
            self._task_metrics[workflow_id] = {}

        task_metrics = TaskMetrics(
            task_id=task_id,
            task_name=task_name,
            workflow_id=workflow_id,
            start_time=time.time(),
            metadata=metadata or {}
        )
        self._task_metrics[workflow_id][task_id] = task_metrics

        if workflow_id in self._workflow_metrics:
            self._workflow_metrics[workflow_id]["task_count"] += 1

        logger.debug("Task started", workflow_id=workflow_id, task_id=task_id, task_name=task_name)

    def record_task_completion(
        self,
        workflow_id: str,
        task_id: str,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """Record task completion within a workflow"""
        if workflow_id not in self._task_metrics:
            return
        if task_id not in self._task_metrics[workflow_id]:
            return

        task_metrics = self._task_metrics[workflow_id][task_id]
        task_metrics.end_time = time.time()
        task_metrics.duration = task_metrics.end_time - task_metrics.start_time
        task_metrics.status = "completed" if success else "failed"
        task_metrics.error = error

        # Update workflow metrics
        if workflow_id in self._workflow_metrics:
            if success:
                self._workflow_metrics[workflow_id]["completed_tasks"] += 1
            else:
                self._workflow_metrics[workflow_id]["failed_tasks"] += 1

        # Update Prometheus metrics
        workflow_type = self._workflow_metrics.get(workflow_id, {}).get("workflow_type", "unknown")
        WORKFLOW_TASK_DURATION.labels(
            workflow_type=workflow_type,
            task_name=task_metrics.task_name
        ).observe(task_metrics.duration)

        logger.debug(
            "Task completed",
            workflow_id=workflow_id,
            task_id=task_id,
            success=success,
            duration=task_metrics.duration
        )

    def get_workflow_metrics(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific workflow"""
        if workflow_id not in self._workflow_metrics:
            return None

        metrics = self._workflow_metrics[workflow_id].copy()
        metrics["tasks"] = {
            task_id: {
                "task_id": tm.task_id,
                "task_name": tm.task_name,
                "start_time": tm.start_time,
                "end_time": tm.end_time,
                "duration": tm.duration,
                "status": tm.status,
                "error": tm.error
            }
            for task_id, tm in self._task_metrics.get(workflow_id, {}).items()
        }
        return metrics

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all workflows"""
        total_workflows = len(self._workflow_metrics)
        completed = sum(1 for m in self._workflow_metrics.values() if m.get("status") == "completed")
        failed = sum(1 for m in self._workflow_metrics.values() if m.get("status") == "failed")
        cancelled = sum(1 for m in self._workflow_metrics.values() if m.get("status") == "cancelled")
        running = sum(1 for m in self._workflow_metrics.values() if m.get("status") == "running")

        durations = [m.get("duration", 0) for m in self._workflow_metrics.values() if m.get("duration")]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_workflows": total_workflows,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "running": running,
            "success_rate": completed / total_workflows if total_workflows > 0 else 0,
            "average_duration": avg_duration,
            "total_tasks": sum(m.get("task_count", 0) for m in self._workflow_metrics.values()),
            "completed_tasks": sum(m.get("completed_tasks", 0) for m in self._workflow_metrics.values()),
            "failed_tasks": sum(m.get("failed_tasks", 0) for m in self._workflow_metrics.values()),
        }

    def clear_workflow_metrics(self, workflow_id: str) -> None:
        """Clear metrics for a specific workflow"""
        self._workflow_metrics.pop(workflow_id, None)
        self._task_metrics.pop(workflow_id, None)

    def export_prometheus_format(self) -> str:
        """Export metrics in Prometheus exposition format"""
        # The Prometheus client library handles this via generate_latest()
        from prometheus_client import generate_latest
        return generate_latest().decode("utf-8")


# =============================================================================
# WORKFLOW MANAGER (FACADE)
# =============================================================================

class WorkflowManager:
    """
    Unified facade for workflow management.

    Combines:
    - State persistence
    - Graceful shutdown
    - Cancellation tokens
    - Metrics collection

    Example:
        ```python
        manager = WorkflowManager()
        await manager.initialize()

        # Create workflow
        workflow_id = await manager.create_workflow(
            workflow_type="document_analysis",
            tasks=["parse", "extract", "synthesize"]
        )

        # Get cancellation token
        token = manager.get_cancellation_token(workflow_id)

        # Update progress
        await manager.update_task(workflow_id, "parse", completed=True)

        # Cancel if needed
        await manager.cancel_workflow(workflow_id, reason="User cancelled")
        ```
    """

    def __init__(
        self,
        storage_backend: Union[str, StorageBackend] = StorageBackend.FILE,
        storage_path: str = "./workflow_states",
        redis_url: Optional[str] = None,
        enable_shutdown_handler: bool = True,
    ):
        self.state_manager = WorkflowStateManager(
            backend=storage_backend,
            storage_path=storage_path,
            redis_url=redis_url
        )
        self.metrics_collector = WorkflowMetricsCollector()
        self.shutdown_handler = GracefulShutdownHandler(self.state_manager)

        self._cancellation_tokens: Dict[str, CancellationToken] = {}
        self._enable_shutdown_handler = enable_shutdown_handler
        self._initialized = False

        logger.info("WorkflowManager created", backend=storage_backend)

    async def initialize(self) -> None:
        """Initialize the workflow manager"""
        if self._initialized:
            return

        await self.state_manager.initialize()

        if self._enable_shutdown_handler:
            self.shutdown_handler.install_signal_handlers()

        self._initialized = True
        logger.info("WorkflowManager initialized")

    async def create_workflow(
        self,
        workflow_type: str,
        tasks: List[str],
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new workflow.

        Args:
            workflow_type: Type of workflow
            tasks: List of task names to execute
            context: Optional workflow context
            metadata: Optional metadata

        Returns:
            Workflow ID
        """
        await self.initialize()

        workflow_id = f"wf-{workflow_type}-{int(time.time())}-{hashlib.md5(str(tasks).encode()).hexdigest()[:8]}"

        state = WorkflowState(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            status=WorkflowStatus.PENDING,
            pending_tasks=tasks.copy(),
            context=context or {},
            started_at=datetime.utcnow().isoformat(),
            metadata=metadata or {}
        )

        # Create cancellation token
        token = CancellationToken()
        self._cancellation_tokens[workflow_id] = token

        # Save state
        await self.state_manager.save_state(state)

        # Register with shutdown handler
        self.shutdown_handler.register_workflow(workflow_id, state, token)

        # Record metrics
        self.metrics_collector.record_workflow_start(workflow_id, workflow_type, metadata)

        logger.info("Workflow created", workflow_id=workflow_id, workflow_type=workflow_type, tasks=tasks)

        return workflow_id

    async def start_workflow(self, workflow_id: str) -> WorkflowState:
        """Start a workflow execution"""
        state = await self.state_manager.load_state(workflow_id)
        if not state:
            raise ValueError(f"Workflow {workflow_id} not found")

        state.status = WorkflowStatus.RUNNING
        await self.state_manager.save_state(state)

        return state

    async def start_task(
        self,
        workflow_id: str,
        task_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Start a task within a workflow"""
        state = await self.state_manager.load_state(workflow_id)
        if not state:
            raise ValueError(f"Workflow {workflow_id} not found")

        state.current_task = task_name
        if task_name in state.pending_tasks:
            state.pending_tasks.remove(task_name)

        await self.state_manager.save_state(state)
        await self.state_manager.checkpoint(state, CheckpointType.TASK_START)

        # Record metrics
        task_id = f"{workflow_id}-{task_name}"
        self.metrics_collector.record_task_start(workflow_id, task_id, task_name, metadata)

    async def complete_task(
        self,
        workflow_id: str,
        task_name: str,
        result: Any = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """Complete a task within a workflow"""
        state = await self.state_manager.load_state(workflow_id)
        if not state:
            raise ValueError(f"Workflow {workflow_id} not found")

        state.completed_tasks.append(task_name)
        if result is not None:
            state.task_results[task_name] = result
        if not success and error:
            state.error = error
        state.current_task = None

        await self.state_manager.save_state(state)
        await self.state_manager.checkpoint(state, CheckpointType.TASK_COMPLETE)

        # Record metrics
        task_id = f"{workflow_id}-{task_name}"
        self.metrics_collector.record_task_completion(workflow_id, task_id, success, error)

    async def complete_workflow(
        self,
        workflow_id: str,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """Complete a workflow"""
        state = await self.state_manager.load_state(workflow_id)
        if not state:
            raise ValueError(f"Workflow {workflow_id} not found")

        state.status = WorkflowStatus.COMPLETED if success else WorkflowStatus.FAILED
        state.completed_at = datetime.utcnow().isoformat()
        if error:
            state.error = error

        await self.state_manager.save_state(state)

        # Unregister from shutdown handler
        self.shutdown_handler.unregister_workflow(workflow_id)

        # Record metrics
        self.metrics_collector.record_workflow_completion(workflow_id, success, error)

    async def cancel_workflow(
        self,
        workflow_id: str,
        reason: str = "User cancelled"
    ) -> None:
        """Cancel a workflow"""
        # Cancel via token
        token = self._cancellation_tokens.get(workflow_id)
        if token:
            await token.cancel(reason)

        # Update state
        state = await self.state_manager.load_state(workflow_id)
        if state:
            state.status = WorkflowStatus.CANCELLED
            state.completed_at = datetime.utcnow().isoformat()
            state.error = f"Cancelled: {reason}"
            await self.state_manager.save_state(state)

        # Unregister from shutdown handler
        self.shutdown_handler.unregister_workflow(workflow_id)

        # Record metrics
        self.metrics_collector.record_workflow_cancellation(workflow_id, reason)

    def get_cancellation_token(self, workflow_id: str) -> Optional[CancellationToken]:
        """Get the cancellation token for a workflow"""
        return self._cancellation_tokens.get(workflow_id)

    async def get_workflow_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """Get current workflow state"""
        return await self.state_manager.load_state(workflow_id)

    async def list_workflows(
        self,
        status: Optional[WorkflowStatus] = None,
        workflow_type: Optional[str] = None
    ) -> List[WorkflowState]:
        """List workflows"""
        return await self.state_manager.list_workflows(status, workflow_type)

    async def recover_workflow(self, workflow_id: str) -> Optional[WorkflowState]:
        """Recover a workflow from checkpoint"""
        state = await self.state_manager.restore_from_checkpoint(workflow_id)
        if state:
            state.status = WorkflowStatus.RUNNING
            await self.state_manager.save_state(state)

            # Re-register with shutdown handler
            token = CancellationToken()
            self._cancellation_tokens[workflow_id] = token
            self.shutdown_handler.register_workflow(workflow_id, state, token)

        return state

    def get_metrics(self, workflow_id: Optional[str] = None) -> Dict[str, Any]:
        """Get workflow metrics"""
        if workflow_id:
            return self.metrics_collector.get_workflow_metrics(workflow_id) or {}
        return self.metrics_collector.get_all_metrics()


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_workflow_manager: Optional[WorkflowManager] = None


def get_workflow_manager(
    storage_backend: Union[str, StorageBackend] = StorageBackend.FILE,
    **kwargs
) -> WorkflowManager:
    """Get or create the global WorkflowManager instance"""
    global _workflow_manager
    if _workflow_manager is None:
        _workflow_manager = WorkflowManager(storage_backend=storage_backend, **kwargs)
    return _workflow_manager


async def initialize_workflow_manager(**kwargs) -> WorkflowManager:
    """Initialize and return the workflow manager"""
    manager = get_workflow_manager(**kwargs)
    await manager.initialize()
    return manager
