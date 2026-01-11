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

import time
from typing import Dict, Any, Optional, List, Set
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
        config: Optional[ConcurrencyConfig] = None
    ):
        self.supabase = supabase
        self.config = config or ConcurrencyConfig()

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
        Execute a single wave of tasks with concurrency limit.

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
        parallel_count = min(len(wave_tasks), max_concurrent)

        # Split wave into batches if exceeds max_concurrent
        for i in range(0, len(wave_tasks), max_concurrent):
            batch = wave_tasks[i:i + max_concurrent]
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
                        node.status = ExecutionStatus.FAILED
                        node.error = task_result.get("error") if task_result else "Unknown error"
                        failed += 1

            except Exception as e:
                logger.error(f"Batch execution failed: {e}")
                for task_key in batch:
                    node = graph[task_key]
                    node.status = ExecutionStatus.FAILED
                    node.error = str(e)
                    node.completed_at = datetime.utcnow()
                    failed += 1

        return {
            "completed": completed,
            "failed": failed,
            "parallel_count": parallel_count
        }

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
        import asyncio
        await asyncio.sleep(seconds)

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
                job_metrics = monitor.generate_job_metrics(metrics.job_id)

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
