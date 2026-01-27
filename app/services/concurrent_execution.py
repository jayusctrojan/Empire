"""
Empire v7.3 - Concurrent Task Execution Engine (Task 96)

Provides concurrent execution of independent research tasks for maximum efficiency.
Uses Celery groups/chords for parallel execution with dependency management.

Features:
- Dependency graph analysis
- Wave-based parallel execution
- Configurable concurrency limits
- Performance metrics and instrumentation
- Dynamic task dispatching

Author: Claude Code
Date: 2025-01-10
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

import structlog
from celery import group, chord
from supabase import Client

from app.core.supabase_client import get_supabase_client
from app.models.research_project import JobStatus, TaskStatus

logger = structlog.get_logger(__name__)


# ==============================================================================
# Dynamic Concurrency Configuration
# ==============================================================================

@dataclass
class DynamicConcurrencyConfig:
    """Configuration for dynamic concurrency adjustment."""
    # Adjustment parameters
    min_concurrency: int = 1
    max_concurrency: int = 10
    adjustment_interval_seconds: float = 5.0

    # Resource thresholds for scaling
    scale_up_cpu_threshold: float = 60.0  # Scale up if CPU below this
    scale_down_cpu_threshold: float = 85.0  # Scale down if CPU above this
    scale_up_memory_threshold: float = 65.0
    scale_down_memory_threshold: float = 90.0

    # Adjustment increments
    scale_up_increment: int = 1
    scale_down_increment: int = 1

    # Cooldown to prevent rapid oscillation
    cooldown_after_adjustment_seconds: float = 10.0

    # Enable/disable
    enabled: bool = True


# ==============================================================================
# Configuration
# ==============================================================================

@dataclass
class ConcurrencyConfig:
    """Configuration for concurrent execution"""
    # Concurrency limits
    max_concurrent_tasks: int = 5
    max_concurrent_per_type: int = 3

    # Timing
    poll_interval: float = 0.5  # seconds between status checks
    task_timeout: int = 300  # 5 minutes per task

    # Quality gates
    max_wave_failures: float = 0.5  # Abort if >50% of wave fails
    abort_on_critical_failure: bool = True

    # Partial Wave Retry Configuration
    enable_partial_retry: bool = True
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 2.0
    retry_backoff_multiplier: float = 1.5  # Exponential backoff

    # Performance
    track_metrics: bool = True


class ExecutionStatus(str, Enum):
    """Execution status for graph nodes"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


# ==============================================================================
# Execution Graph
# ==============================================================================

@dataclass
class ExecutionNode:
    """Node in the execution dependency graph"""
    task_id: int
    task_key: str
    task_type: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @property
    def duration(self) -> Optional[float]:
        """Get execution duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class ExecutionMetrics:
    """Metrics for execution performance"""
    job_id: int
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    skipped_tasks: int = 0

    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_duration: float = 0.0

    # Parallelism
    wave_count: int = 0
    max_parallel: int = 0
    avg_parallel: float = 0.0
    parallelism_ratio: float = 0.0  # actual parallel / max possible

    # Task durations
    task_durations: List[float] = field(default_factory=list)
    idle_time: float = 0.0  # time waiting for tasks

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "job_id": self.job_id,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "skipped_tasks": self.skipped_tasks,
            "total_duration": self.total_duration,
            "wave_count": self.wave_count,
            "max_parallel": self.max_parallel,
            "avg_parallel": round(self.avg_parallel, 2),
            "parallelism_ratio": round(self.parallelism_ratio, 2),
            "avg_task_duration": round(
                sum(self.task_durations) / len(self.task_durations), 2
            ) if self.task_durations else 0,
            "idle_time": round(self.idle_time, 2)
        }


# ==============================================================================
# Dynamic Concurrency Controller
# ==============================================================================

class DynamicConcurrencyController:
    """
    Controls concurrency level dynamically based on system resources.

    Monitors CPU and memory usage and adjusts the number of concurrent
    tasks to maintain optimal performance without overloading the system.
    """

    def __init__(
        self,
        initial_concurrency: int = 5,
        config: Optional[DynamicConcurrencyConfig] = None
    ):
        self._config = config or DynamicConcurrencyConfig()
        self._current_concurrency = min(
            max(initial_concurrency, self._config.min_concurrency),
            self._config.max_concurrency
        )
        self._last_adjustment_time: Optional[datetime] = None
        self._adjustment_history: List[Dict[str, Any]] = []
        self._resource_monitor = None

    async def _get_resource_monitor(self):
        """Lazy load resource monitor."""
        if self._resource_monitor is None:
            try:
                from app.services.resource_monitor import get_resource_monitor
                self._resource_monitor = await get_resource_monitor()
            except ImportError:
                logger.warning("resource_monitor_not_available")
                self._resource_monitor = None
        return self._resource_monitor

    @property
    def current_concurrency(self) -> int:
        """Get current concurrency level."""
        return self._current_concurrency

    def _in_cooldown(self) -> bool:
        """Check if we're in cooldown period after last adjustment."""
        if self._last_adjustment_time is None:
            return False

        elapsed = (datetime.utcnow() - self._last_adjustment_time).total_seconds()
        return elapsed < self._config.cooldown_after_adjustment_seconds

    async def evaluate_and_adjust(self) -> Tuple[int, str]:
        """
        Evaluate current resources and adjust concurrency if needed.

        Returns:
            Tuple of (new_concurrency, reason)
        """
        if not self._config.enabled:
            return self._current_concurrency, "dynamic_adjustment_disabled"

        if self._in_cooldown():
            return self._current_concurrency, "in_cooldown"

        monitor = await self._get_resource_monitor()
        if monitor is None:
            return self._current_concurrency, "no_resource_monitor"

        try:
            usage = await monitor.get_current_usage()
        except Exception as e:
            logger.warning("resource_check_failed", error=str(e))
            return self._current_concurrency, f"resource_check_error: {e}"

        old_concurrency = self._current_concurrency
        reason = "no_change"

        # Check if we should scale down (resources under pressure)
        if (usage.cpu_percent > self._config.scale_down_cpu_threshold or
                usage.memory_percent > self._config.scale_down_memory_threshold):

            if self._current_concurrency > self._config.min_concurrency:
                self._current_concurrency = max(
                    self._config.min_concurrency,
                    self._current_concurrency - self._config.scale_down_increment
                )
                reason = f"scale_down: CPU={usage.cpu_percent:.1f}%, MEM={usage.memory_percent:.1f}%"

        # Check if we should scale up (resources available)
        elif (usage.cpu_percent < self._config.scale_up_cpu_threshold and
              usage.memory_percent < self._config.scale_up_memory_threshold):

            if self._current_concurrency < self._config.max_concurrency:
                self._current_concurrency = min(
                    self._config.max_concurrency,
                    self._current_concurrency + self._config.scale_up_increment
                )
                reason = f"scale_up: CPU={usage.cpu_percent:.1f}%, MEM={usage.memory_percent:.1f}%"

        # Record adjustment if changed
        if self._current_concurrency != old_concurrency:
            self._last_adjustment_time = datetime.utcnow()
            self._adjustment_history.append({
                "timestamp": self._last_adjustment_time.isoformat(),
                "old_concurrency": old_concurrency,
                "new_concurrency": self._current_concurrency,
                "reason": reason,
                "cpu_percent": usage.cpu_percent,
                "memory_percent": usage.memory_percent
            })

            logger.info(
                "concurrency_adjusted",
                old=old_concurrency,
                new=self._current_concurrency,
                reason=reason
            )

            # Keep only last 100 adjustments
            if len(self._adjustment_history) > 100:
                self._adjustment_history.pop(0)

        return self._current_concurrency, reason

    def force_set_concurrency(self, value: int) -> int:
        """Force set concurrency to a specific value (within bounds)."""
        self._current_concurrency = min(
            max(value, self._config.min_concurrency),
            self._config.max_concurrency
        )
        return self._current_concurrency

    def get_adjustment_history(self) -> List[Dict[str, Any]]:
        """Get history of concurrency adjustments."""
        return list(self._adjustment_history)

    def get_stats(self) -> Dict[str, Any]:
        """Get controller statistics."""
        return {
            "current_concurrency": self._current_concurrency,
            "min_concurrency": self._config.min_concurrency,
            "max_concurrency": self._config.max_concurrency,
            "adjustment_count": len(self._adjustment_history),
            "last_adjustment": (
                self._last_adjustment_time.isoformat()
                if self._last_adjustment_time else None
            ),
            "enabled": self._config.enabled
        }


# ==============================================================================
# Concurrent Execution Engine
# ==============================================================================

class ConcurrentExecutionEngine:
    """
    Engine for concurrent task execution with dependency management.

    Provides wave-based parallel execution where tasks in the same wave
    have no dependencies on each other and can run concurrently.
    """

    def __init__(
        self,
        supabase: Client,
        config: Optional[ConcurrencyConfig] = None,
        dynamic_config: Optional[DynamicConcurrencyConfig] = None
    ):
        self.supabase = supabase
        self.config = config or ConcurrencyConfig()
        self.dynamic_config = dynamic_config or DynamicConcurrencyConfig()
        self._concurrency_controller: Optional[DynamicConcurrencyController] = None

    # ==========================================================================
    # Dependency Graph
    # ==========================================================================

    def build_execution_graph(self, job_id: int) -> Dict[str, ExecutionNode]:
        """
        Build a dependency graph for all tasks in the job.

        Args:
            job_id: The research job ID

        Returns:
            Dict mapping task_key to ExecutionNode
        """
        result = self.supabase.table("plan_tasks").select("*").eq(
            "job_id", job_id
        ).order("sequence_order").execute()

        tasks = result.data or []
        graph: Dict[str, ExecutionNode] = {}

        # Build initial nodes
        for task in tasks:
            task_key = task["task_key"]
            graph[task_key] = ExecutionNode(
                task_id=task["id"],
                task_key=task_key,
                task_type=task["task_type"],
                status=ExecutionStatus(task["status"]),
                dependencies=task.get("depends_on") or []
            )

        # Populate dependents (reverse mapping)
        for task_key, node in graph.items():
            for dep in node.dependencies:
                if dep in graph:
                    graph[dep].dependents.append(task_key)

        logger.info(
            "Built execution graph",
            job_id=job_id,
            task_count=len(graph)
        )

        return graph

    def identify_execution_waves(
        self,
        graph: Dict[str, ExecutionNode]
    ) -> List[List[str]]:
        """
        Group tasks into execution waves based on dependencies.

        Tasks in the same wave can be executed concurrently.

        Args:
            graph: The execution graph

        Returns:
            List of waves, each wave is a list of task_keys
        """
        waves: List[List[str]] = []
        remaining = set(graph.keys())
        completed = set()

        while remaining:
            # Find tasks with all dependencies satisfied
            wave = []
            for task_key in list(remaining):
                node = graph[task_key]
                deps = set(node.dependencies) & remaining
                if not deps or deps.issubset(completed):
                    wave.append(task_key)

            if not wave:
                # Circular dependency or invalid graph
                logger.error(
                    "Cannot resolve dependencies",
                    remaining=list(remaining)
                )
                # Add remaining as final wave
                wave = list(remaining)

            waves.append(wave)
            completed.update(wave)
            remaining -= set(wave)

        logger.info(
            "Identified execution waves",
            wave_count=len(waves),
            wave_sizes=[len(w) for w in waves]
        )

        return waves

    def get_ready_tasks(
        self,
        graph: Dict[str, ExecutionNode]
    ) -> List[str]:
        """
        Get all tasks that are ready to execute.

        A task is ready if:
        - Status is PENDING
        - All dependencies are COMPLETE

        Args:
            graph: The execution graph

        Returns:
            List of task_keys ready for execution
        """
        ready = []
        completed_keys = {
            k for k, n in graph.items()
            if n.status == ExecutionStatus.COMPLETE
        }

        for task_key, node in graph.items():
            if node.status != ExecutionStatus.PENDING:
                continue

            deps = set(node.dependencies) & set(graph.keys())
            if deps.issubset(completed_keys):
                ready.append(task_key)

        return ready

    # ==========================================================================
    # Concurrent Execution
    # ==========================================================================

    async def execute_job_concurrent(
        self,
        job_id: int,
        max_concurrent: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute all tasks for a job with maximum concurrency.

        Uses wave-based execution with Celery groups for parallelism.

        Args:
            job_id: The research job ID
            max_concurrent: Override max concurrent tasks

        Returns:
            Dict with execution results and metrics
        """
        max_concurrent = max_concurrent or self.config.max_concurrent_tasks
        metrics = ExecutionMetrics(job_id=job_id)
        metrics.start_time = datetime.utcnow()

        logger.info(
            "Starting concurrent job execution",
            job_id=job_id,
            max_concurrent=max_concurrent
        )

        try:
            # Build graph and waves
            graph = self.build_execution_graph(job_id)
            waves = self.identify_execution_waves(graph)

            metrics.total_tasks = len(graph)
            metrics.wave_count = len(waves)

            # Update job status
            self._update_job_status(job_id, JobStatus.EXECUTING)

            # Execute waves sequentially, tasks within waves in parallel
            parallel_counts = []

            for wave_num, wave_tasks in enumerate(waves, 1):
                logger.info(
                    f"Executing wave {wave_num}/{len(waves)}",
                    job_id=job_id,
                    task_count=len(wave_tasks)
                )

                # Execute wave with concurrency limit
                wave_result = await self._execute_wave(
                    graph=graph,
                    wave_tasks=wave_tasks,
                    max_concurrent=max_concurrent
                )

                parallel_counts.append(wave_result["parallel_count"])

                # Update metrics
                metrics.completed_tasks += wave_result["completed"]
                metrics.failed_tasks += wave_result["failed"]

                # Check quality gate
                if wave_result["failed"] > len(wave_tasks) * self.config.max_wave_failures:
                    logger.error(
                        "Too many failures in wave, aborting",
                        job_id=job_id,
                        wave_num=wave_num,
                        failed=wave_result["failed"]
                    )
                    self._update_job_status(
                        job_id,
                        JobStatus.FAILED,
                        f"Too many task failures in wave {wave_num}"
                    )
                    break

                # Update progress
                self._update_job_progress(job_id, graph)

            # Calculate final metrics
            metrics.end_time = datetime.utcnow()
            metrics.total_duration = (
                metrics.end_time - metrics.start_time
            ).total_seconds()
            metrics.max_parallel = max(parallel_counts) if parallel_counts else 0
            metrics.avg_parallel = (
                sum(parallel_counts) / len(parallel_counts)
                if parallel_counts else 0
            )

            # Calculate parallelism ratio
            sequential_time = sum(metrics.task_durations)
            if sequential_time > 0:
                metrics.parallelism_ratio = sequential_time / metrics.total_duration

            # Store metrics if enabled
            if self.config.track_metrics:
                self._store_metrics(metrics)

            # Determine final status
            if metrics.failed_tasks == 0:
                self._update_job_status(job_id, JobStatus.GENERATING_REPORT)
                success = True
            else:
                if metrics.completed_tasks > 0:
                    self._update_job_status(job_id, JobStatus.GENERATING_REPORT)
                    success = True  # Partial success
                else:
                    self._update_job_status(
                        job_id,
                        JobStatus.FAILED,
                        "All tasks failed"
                    )
                    success = False

            return {
                "success": success,
                "job_id": job_id,
                "metrics": metrics.to_dict(),
                "message": f"Executed {metrics.completed_tasks}/{metrics.total_tasks} tasks"
            }

        except Exception as e:
            logger.error(
                "Concurrent execution failed",
                job_id=job_id,
                error=str(e)
            )
            self._update_job_status(job_id, JobStatus.FAILED, str(e))
            return {
                "success": False,
                "job_id": job_id,
                "error": str(e)
            }

    async def _execute_wave(
        self,
        graph: Dict[str, ExecutionNode],
        wave_tasks: List[str],
        max_concurrent: int
    ) -> Dict[str, Any]:
        """
        Execute a single wave of tasks with concurrency limit and partial retry.

        Args:
            graph: The execution graph
            wave_tasks: List of task_keys in this wave
            max_concurrent: Maximum concurrent tasks

        Returns:
            Dict with wave execution results
        """
        from app.tasks.research_tasks import execute_single_task

        completed = 0
        failed = 0
        retried = 0
        parallel_count = min(len(wave_tasks), max_concurrent)

        # Track retry attempts per task
        retry_counts: Dict[str, int] = {tk: 0 for tk in wave_tasks}
        tasks_to_execute = list(wave_tasks)

        while tasks_to_execute:
            batch_failed_tasks: List[str] = []

            # Split into batches
            for i in range(0, len(tasks_to_execute), max_concurrent):
                batch = tasks_to_execute[i:i + max_concurrent]
                batch_task_ids = [graph[tk].task_id for tk in batch]

                # Mark tasks as queued
                for task_key in batch:
                    graph[task_key].status = ExecutionStatus.QUEUED
                    graph[task_key].started_at = datetime.utcnow()

                # Create Celery group for parallel execution
                task_group = group(
                    execute_single_task.s(task_id)
                    for task_id in batch_task_ids
                )

                # Execute and wait for results
                result = task_group.apply_async()

                try:
                    # Wait for all tasks in batch to complete
                    results = result.get(timeout=self.config.task_timeout * len(batch))

                    # Process results
                    for task_key, task_result in zip(batch, results):
                        node = graph[task_key]
                        node.completed_at = datetime.utcnow()

                        if task_result and task_result.get("success"):
                            node.status = ExecutionStatus.COMPLETE
                            node.result = task_result
                            completed += 1
                        else:
                            # Track failure for potential retry
                            error_msg = task_result.get("error") if task_result else "Unknown error"
                            node.error = error_msg

                            # Check if we should retry
                            if (self.config.enable_partial_retry and
                                    retry_counts[task_key] < self.config.max_retry_attempts and
                                    self._is_retryable_error(error_msg)):
                                batch_failed_tasks.append(task_key)
                                node.status = ExecutionStatus.PENDING  # Reset for retry
                                retry_counts[task_key] += 1
                                retried += 1
                                logger.info(
                                    "task_scheduled_for_retry",
                                    task_key=task_key,
                                    attempt=retry_counts[task_key],
                                    max_attempts=self.config.max_retry_attempts
                                )
                            else:
                                node.status = ExecutionStatus.FAILED
                                failed += 1

                except Exception as e:
                    logger.error(f"Batch execution failed: {e}")
                    for task_key in batch:
                        node = graph[task_key]
                        node.completed_at = datetime.utcnow()

                        # Check if we should retry the whole batch
                        if (self.config.enable_partial_retry and
                                retry_counts[task_key] < self.config.max_retry_attempts):
                            batch_failed_tasks.append(task_key)
                            node.status = ExecutionStatus.PENDING
                            node.error = str(e)
                            retry_counts[task_key] += 1
                            retried += 1
                        else:
                            node.status = ExecutionStatus.FAILED
                            node.error = str(e)
                            failed += 1

            # Prepare retry list with backoff delay
            if batch_failed_tasks and self.config.enable_partial_retry:
                # Calculate backoff delay
                max_retry = max(retry_counts[tk] for tk in batch_failed_tasks)
                delay = self.config.retry_delay_seconds * (
                    self.config.retry_backoff_multiplier ** (max_retry - 1)
                )

                logger.info(
                    "retrying_failed_tasks",
                    count=len(batch_failed_tasks),
                    delay_seconds=delay
                )

                await asyncio.sleep(delay)
                tasks_to_execute = batch_failed_tasks
            else:
                tasks_to_execute = []

        return {
            "completed": completed,
            "failed": failed,
            "retried": retried,
            "parallel_count": parallel_count,
            "retry_counts": {k: v for k, v in retry_counts.items() if v > 0}
        }

    def _is_retryable_error(self, error_message: str) -> bool:
        """
        Determine if an error is retryable.

        Some errors (like validation errors or authorization failures)
        should not be retried as they will fail again.

        Args:
            error_message: The error message to analyze

        Returns:
            True if the error is retryable
        """
        if not error_message:
            return True

        error_lower = error_message.lower()

        # Non-retryable errors
        non_retryable_patterns = [
            "validation error",
            "invalid input",
            "unauthorized",
            "forbidden",
            "not found",
            "permission denied",
            "authentication failed",
            "invalid credentials",
            "schema error",
            "type error",
            "value error"
        ]

        for pattern in non_retryable_patterns:
            if pattern in error_lower:
                return False

        # Retryable errors (default to retryable for unknown errors)
        retryable_patterns = [
            "timeout",
            "connection",
            "temporary",
            "rate limit",
            "too many requests",
            "service unavailable",
            "gateway",
            "network",
            "socket",
            "eof",
            "broken pipe"
        ]

        for pattern in retryable_patterns:
            if pattern in error_lower:
                return True

        # Default to retryable for unknown errors
        return True

    # ==========================================================================
    # Dynamic Dispatch (Alternative to Wave-Based)
    # ==========================================================================

    async def execute_job_dynamic(
        self,
        job_id: int,
        max_concurrent: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute tasks with dynamic dispatch as dependencies are satisfied.

        This approach maximizes parallelism by immediately dispatching
        tasks as soon as their dependencies complete.

        Args:
            job_id: The research job ID
            max_concurrent: Override max concurrent tasks

        Returns:
            Dict with execution results
        """
        from app.tasks.research_tasks import execute_single_task

        max_concurrent = max_concurrent or self.config.max_concurrent_tasks
        metrics = ExecutionMetrics(job_id=job_id)
        metrics.start_time = datetime.utcnow()

        logger.info(
            "Starting dynamic job execution",
            job_id=job_id,
            max_concurrent=max_concurrent
        )

        try:
            graph = self.build_execution_graph(job_id)
            metrics.total_tasks = len(graph)

            self._update_job_status(job_id, JobStatus.EXECUTING)

            running: Set[str] = set()
            pending_results: Dict[str, Any] = {}  # task_key -> AsyncResult

            while True:
                # Get ready tasks
                ready = self.get_ready_tasks(graph)

                # Dispatch tasks up to concurrency limit
                available_slots = max_concurrent - len(running)
                for task_key in ready[:available_slots]:
                    if task_key not in running:
                        node = graph[task_key]
                        node.status = ExecutionStatus.RUNNING
                        node.started_at = datetime.utcnow()

                        # Dispatch task
                        result = execute_single_task.delay(node.task_id)
                        pending_results[task_key] = result
                        running.add(task_key)

                        logger.debug(f"Dispatched task {task_key}")

                # Check for completed tasks
                for task_key in list(running):
                    result = pending_results[task_key]
                    if result.ready():
                        node = graph[task_key]
                        node.completed_at = datetime.utcnow()

                        try:
                            task_result = result.get(timeout=1)
                            if task_result and task_result.get("success"):
                                node.status = ExecutionStatus.COMPLETE
                                node.result = task_result
                                metrics.completed_tasks += 1
                            else:
                                node.status = ExecutionStatus.FAILED
                                node.error = task_result.get("error") if task_result else "Unknown"
                                metrics.failed_tasks += 1
                        except Exception as e:
                            node.status = ExecutionStatus.FAILED
                            node.error = str(e)
                            metrics.failed_tasks += 1

                        running.remove(task_key)
                        del pending_results[task_key]

                        if node.duration:
                            metrics.task_durations.append(node.duration)

                        # Update progress
                        self._update_job_progress(job_id, graph)

                # Check if all done
                pending_count = sum(
                    1 for n in graph.values()
                    if n.status == ExecutionStatus.PENDING
                )
                if not running and pending_count == 0:
                    break

                # Check for stuck state (no running, no ready, but pending exist)
                if not running and not ready and pending_count > 0:
                    logger.error(
                        "Stuck state detected - tasks pending but none ready",
                        pending=pending_count
                    )
                    break

                # Short sleep to prevent CPU spinning
                await self._async_sleep(self.config.poll_interval)

            # Finalize
            metrics.end_time = datetime.utcnow()
            metrics.total_duration = (
                metrics.end_time - metrics.start_time
            ).total_seconds()

            if self.config.track_metrics:
                self._store_metrics(metrics)

            success = metrics.completed_tasks > 0
            self._update_job_status(
                job_id,
                JobStatus.GENERATING_REPORT if success else JobStatus.FAILED
            )

            return {
                "success": success,
                "job_id": job_id,
                "metrics": metrics.to_dict()
            }

        except Exception as e:
            logger.error(f"Dynamic execution failed: {e}")
            self._update_job_status(job_id, JobStatus.FAILED, str(e))
            return {"success": False, "job_id": job_id, "error": str(e)}

    async def _async_sleep(self, seconds: float):
        """Async sleep helper"""
        await asyncio.sleep(seconds)

    # ==========================================================================
    # Adaptive Execution with Dynamic Concurrency
    # ==========================================================================

    def _get_concurrency_controller(
        self,
        initial_concurrency: int
    ) -> DynamicConcurrencyController:
        """Get or create the concurrency controller."""
        if (self._concurrency_controller is None or
                self._concurrency_controller.current_concurrency != initial_concurrency):
            self._concurrency_controller = DynamicConcurrencyController(
                initial_concurrency=initial_concurrency,
                config=self.dynamic_config
            )
        return self._concurrency_controller

    async def execute_job_adaptive(
        self,
        job_id: int,
        initial_concurrency: Optional[int] = None,
        enable_dynamic_adjustment: bool = True
    ) -> Dict[str, Any]:
        """
        Execute tasks with adaptive concurrency that adjusts based on resources.

        This method combines the dynamic dispatch approach with resource-aware
        concurrency adjustment for optimal performance.

        Args:
            job_id: The research job ID
            initial_concurrency: Starting concurrency level
            enable_dynamic_adjustment: Whether to dynamically adjust concurrency

        Returns:
            Dict with execution results and adjustment history
        """
        from app.tasks.research_tasks import execute_single_task

        initial_concurrency = initial_concurrency or self.config.max_concurrent_tasks
        controller = self._get_concurrency_controller(initial_concurrency)

        metrics = ExecutionMetrics(job_id=job_id)
        metrics.start_time = datetime.utcnow()

        logger.info(
            "Starting adaptive job execution",
            job_id=job_id,
            initial_concurrency=initial_concurrency,
            dynamic_adjustment=enable_dynamic_adjustment
        )

        try:
            graph = self.build_execution_graph(job_id)
            metrics.total_tasks = len(graph)

            self._update_job_status(job_id, JobStatus.EXECUTING)

            running: Set[str] = set()
            pending_results: Dict[str, Any] = {}
            concurrency_samples: List[int] = []
            last_adjustment_check = datetime.utcnow()

            while True:
                # Dynamic concurrency adjustment
                current_max = controller.current_concurrency
                if enable_dynamic_adjustment:
                    time_since_check = (
                        datetime.utcnow() - last_adjustment_check
                    ).total_seconds()

                    if time_since_check >= self.dynamic_config.adjustment_interval_seconds:
                        current_max, reason = await controller.evaluate_and_adjust()
                        last_adjustment_check = datetime.utcnow()

                        if "scale" in reason:
                            logger.debug(
                                "concurrency_check",
                                current_max=current_max,
                                reason=reason
                            )

                concurrency_samples.append(current_max)

                # Get ready tasks
                ready = self.get_ready_tasks(graph)

                # Dispatch tasks up to current concurrency limit
                available_slots = current_max - len(running)
                for task_key in ready[:available_slots]:
                    if task_key not in running:
                        node = graph[task_key]
                        node.status = ExecutionStatus.RUNNING
                        node.started_at = datetime.utcnow()

                        result = execute_single_task.delay(node.task_id)
                        pending_results[task_key] = result
                        running.add(task_key)

                        logger.debug(
                            "task_dispatched",
                            task_key=task_key,
                            running_count=len(running),
                            max_concurrent=current_max
                        )

                # Check for completed tasks
                for task_key in list(running):
                    result = pending_results[task_key]
                    if result.ready():
                        node = graph[task_key]
                        node.completed_at = datetime.utcnow()

                        try:
                            task_result = result.get(timeout=1)
                            if task_result and task_result.get("success"):
                                node.status = ExecutionStatus.COMPLETE
                                node.result = task_result
                                metrics.completed_tasks += 1
                            else:
                                node.status = ExecutionStatus.FAILED
                                node.error = (
                                    task_result.get("error")
                                    if task_result else "Unknown"
                                )
                                metrics.failed_tasks += 1
                        except Exception as e:
                            node.status = ExecutionStatus.FAILED
                            node.error = str(e)
                            metrics.failed_tasks += 1

                        running.remove(task_key)
                        del pending_results[task_key]

                        if node.duration:
                            metrics.task_durations.append(node.duration)

                        self._update_job_progress(job_id, graph)

                # Check if all done
                pending_count = sum(
                    1 for n in graph.values()
                    if n.status == ExecutionStatus.PENDING
                )
                if not running and pending_count == 0:
                    break

                # Check for stuck state
                if not running and not ready and pending_count > 0:
                    logger.error(
                        "Stuck state detected",
                        pending=pending_count
                    )
                    break

                await self._async_sleep(self.config.poll_interval)

            # Finalize metrics
            metrics.end_time = datetime.utcnow()
            metrics.total_duration = (
                metrics.end_time - metrics.start_time
            ).total_seconds()

            # Calculate average concurrency from samples
            if concurrency_samples:
                metrics.avg_parallel = sum(concurrency_samples) / len(concurrency_samples)
                metrics.max_parallel = max(concurrency_samples)

            if self.config.track_metrics:
                self._store_metrics(metrics)

            success = metrics.completed_tasks > 0
            self._update_job_status(
                job_id,
                JobStatus.GENERATING_REPORT if success else JobStatus.FAILED
            )

            return {
                "success": success,
                "job_id": job_id,
                "metrics": metrics.to_dict(),
                "concurrency_stats": controller.get_stats(),
                "adjustment_history": controller.get_adjustment_history()
            }

        except Exception as e:
            logger.error("Adaptive execution failed", job_id=job_id, error=str(e))
            self._update_job_status(job_id, JobStatus.FAILED, str(e))
            return {
                "success": False,
                "job_id": job_id,
                "error": str(e),
                "concurrency_stats": controller.get_stats() if controller else None
            }

    # ==========================================================================
    # Status and Progress
    # ==========================================================================

    def _update_job_status(
        self,
        job_id: int,
        status: JobStatus,
        error_message: Optional[str] = None
    ):
        """Update job status in database"""
        update_data = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat()
        }

        if error_message:
            update_data["error_message"] = error_message

        self.supabase.table("research_jobs").update(update_data).eq(
            "id", job_id
        ).execute()

    def _update_job_progress(
        self,
        job_id: int,
        graph: Dict[str, ExecutionNode]
    ):
        """Update job progress based on graph state"""
        total = len(graph)
        completed = sum(
            1 for n in graph.values()
            if n.status == ExecutionStatus.COMPLETE
        )
        progress = (completed / total) * 100 if total > 0 else 0

        # Find current running task
        running_tasks = [
            n.task_key for n in graph.values()
            if n.status == ExecutionStatus.RUNNING
        ]
        current_task = running_tasks[0] if running_tasks else None

        self.supabase.table("research_jobs").update({
            "completed_tasks": completed,
            "progress_percentage": round(progress, 2),
            "current_task_key": current_task,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", job_id).execute()

    def _store_metrics(self, metrics: ExecutionMetrics):
        """Store execution metrics for analysis"""
        try:
            # Store in research_jobs metadata
            self.supabase.table("research_jobs").update({
                "execution_metrics": metrics.to_dict()
            }).eq("id", metrics.job_id).execute()

            # Also record via performance monitor for Prometheus metrics
            try:
                from app.services.performance_monitor import get_performance_monitor
                monitor = get_performance_monitor()

                # Generate comprehensive job metrics
                monitor.generate_job_metrics(metrics.job_id)

                # Check SLA compliance
                monitor.check_sla_compliance(metrics.job_id)

            except Exception as e:
                logger.warning(f"Performance monitor integration failed: {e}")

            logger.info(
                "Stored execution metrics",
                job_id=metrics.job_id,
                duration=metrics.total_duration,
                parallelism=metrics.parallelism_ratio
            )
        except Exception as e:
            logger.warning(f"Failed to store metrics: {e}")


# ==============================================================================
# Service Factory
# ==============================================================================

_engine_instance: Optional[ConcurrentExecutionEngine] = None


def get_concurrent_execution_engine() -> ConcurrentExecutionEngine:
    """Get or create concurrent execution engine singleton"""
    global _engine_instance
    if _engine_instance is None:
        supabase = get_supabase_client()
        _engine_instance = ConcurrentExecutionEngine(supabase)
    return _engine_instance
