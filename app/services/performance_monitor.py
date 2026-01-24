"""
Empire v7.3 - Research Performance Monitor (Task 100)

Comprehensive performance monitoring system to track efficiency metrics
and ensure quality standards for the Agent Harness feature.

Author: Claude Code
Date: 2025-01-10
"""

import functools
import time
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field

import structlog
from prometheus_client import Histogram, Gauge, Counter, Summary

from app.core.supabase_client import get_supabase_client
from app.models.research_project import JobStatus, TaskStatus

logger = structlog.get_logger(__name__)


# ==============================================================================
# Prometheus Metrics
# ==============================================================================

# Task execution metrics
research_task_duration_seconds = Histogram(
    'research_task_duration_seconds',
    'Task execution duration in seconds',
    ['task_type', 'job_id'],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800)
)

research_task_queue_wait_seconds = Histogram(
    'research_task_queue_wait_seconds',
    'Time task spent waiting in queue before execution',
    ['task_type'],
    buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 120)
)

research_concurrent_tasks = Gauge(
    'research_concurrent_tasks',
    'Current number of concurrent tasks executing',
    ['job_id']
)

research_parallelism_ratio = Gauge(
    'research_parallelism_ratio',
    'Ratio of concurrent execution achieved (0-1)',
    ['job_id']
)

research_wave_count = Gauge(
    'research_wave_count',
    'Number of execution waves in a job',
    ['job_id']
)

research_wave_transition_latency_seconds = Histogram(
    'research_wave_transition_latency_seconds',
    'Time between wave completion and next wave start',
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30)
)

# Quality metrics
research_quality_score = Gauge(
    'research_quality_score',
    'Quality score for artifacts (0-1)',
    ['artifact_type', 'job_id']
)

research_quality_gate_failures_total = Counter(
    'research_quality_gate_failures_total',
    'Total number of quality gate failures',
    ['gate_type', 'job_id']
)

research_quality_gate_passes_total = Counter(
    'research_quality_gate_passes_total',
    'Total number of quality gate passes',
    ['gate_type', 'job_id']
)

research_retry_count = Counter(
    'research_retry_count_total',
    'Total number of task retries',
    ['task_type', 'job_id']
)

# Job-level metrics
research_job_duration_seconds = Histogram(
    'research_job_duration_seconds',
    'Total job duration in seconds',
    ['research_type', 'complexity'],
    buckets=(60, 120, 300, 600, 900, 1800, 3600)
)

research_job_task_count = Histogram(
    'research_job_task_count',
    'Number of tasks per job',
    ['research_type'],
    buckets=(5, 10, 15, 20, 30, 50, 100)
)

research_sla_compliance = Gauge(
    'research_sla_compliance',
    'SLA compliance status (1=compliant, 0=not compliant)',
    ['job_id', 'complexity']
)

# Resource utilization
research_artifact_count = Gauge(
    'research_artifact_count',
    'Number of artifacts generated for a job',
    ['artifact_type', 'job_id']
)

research_source_coverage = Gauge(
    'research_source_coverage',
    'Percentage of relevant sources covered',
    ['job_id']
)


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class TaskTiming:
    """Timing data for a task execution."""
    task_id: int
    task_key: str
    task_type: str
    job_id: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    queue_wait_seconds: float = 0.0
    execution_seconds: float = 0.0
    total_seconds: float = 0.0


@dataclass
class JobMetrics:
    """Comprehensive metrics for a research job."""
    job_id: int
    research_type: str
    complexity: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_duration_seconds: float
    average_task_duration: float
    parallelism_ratio: float
    wave_count: int
    quality_gates_passed: int
    quality_gates_failed: int
    artifact_count: int
    sla_compliant: bool
    sla_target_seconds: float
    sla_margin_seconds: float
    metrics_timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QualityGateResult:
    """Result of a quality gate check."""
    gate_type: str
    passed: bool
    score: float
    threshold: float
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ==============================================================================
# SLA Configuration
# ==============================================================================

class SLAConfig:
    """SLA configuration for different job complexities."""

    # SLA targets by complexity (in seconds)
    TARGETS = {
        "simple": 120,       # 2 minutes (1-5 tasks)
        "medium": 300,       # 5 minutes (6-10 tasks)
        "complex": 900,      # 15 minutes (11-20 tasks)
        "very_complex": 1800  # 30 minutes (21+ tasks)
    }

    @classmethod
    def get_complexity(cls, task_count: int) -> str:
        """Determine complexity based on task count."""
        if task_count <= 5:
            return "simple"
        elif task_count <= 10:
            return "medium"
        elif task_count <= 20:
            return "complex"
        else:
            return "very_complex"

    @classmethod
    def get_target(cls, complexity: str) -> int:
        """Get SLA target for a given complexity."""
        return cls.TARGETS.get(complexity, cls.TARGETS["complex"])


# ==============================================================================
# Performance Monitor
# ==============================================================================

class PerformanceMonitor:
    """
    Comprehensive performance monitoring for research jobs.

    Tracks:
    - Task execution times
    - Parallelism efficiency
    - Quality gate results
    - SLA compliance
    - Resource utilization
    """

    def __init__(self):
        self.supabase = get_supabase_client()
        self._task_start_times: Dict[int, float] = {}
        self._wave_start_times: Dict[int, float] = {}
        self._running_tasks_by_job: Dict[int, int] = {}

    # ==========================================================================
    # Task Timing
    # ==========================================================================

    def record_task_start(
        self,
        task_id: int,
        task_type: str,
        job_id: int,
        created_at: Optional[datetime] = None
    ) -> None:
        """
        Record task execution start.

        Args:
            task_id: Task ID
            task_type: Type of task
            job_id: Parent job ID
            created_at: When task was created (for queue wait calculation)
        """
        start_time = time.time()
        self._task_start_times[task_id] = start_time

        # Update running task count
        if job_id not in self._running_tasks_by_job:
            self._running_tasks_by_job[job_id] = 0
        self._running_tasks_by_job[job_id] += 1
        research_concurrent_tasks.labels(job_id=str(job_id)).set(
            self._running_tasks_by_job[job_id]
        )

        # Record queue wait time
        if created_at:
            queue_wait = start_time - created_at.timestamp()
            research_task_queue_wait_seconds.labels(task_type=task_type).observe(queue_wait)

        logger.debug(
            "Task started",
            task_id=task_id,
            task_type=task_type,
            job_id=job_id,
            concurrent_tasks=self._running_tasks_by_job[job_id]
        )

    def record_task_timing(
        self,
        task_id: int,
        start_time: float,
        end_time: float,
        task_type: Optional[str] = None,
        job_id: Optional[int] = None
    ) -> None:
        """
        Record task execution timing.

        Args:
            task_id: Task ID
            start_time: Execution start timestamp
            end_time: Execution end timestamp
            task_type: Type of task (optional, will be fetched if not provided)
            job_id: Parent job ID (optional, will be fetched if not provided)
        """
        duration = end_time - start_time

        # Fetch task details if not provided
        if task_type is None or job_id is None:
            try:
                result = self.supabase.table("plan_tasks").select(
                    "task_type, job_id"
                ).eq("id", task_id).single().execute()
                if result.data:
                    task_type = result.data.get("task_type", "unknown")
                    job_id = result.data.get("job_id", 0)
            except Exception:
                task_type = task_type or "unknown"
                job_id = job_id or 0

        # Record Prometheus metric
        research_task_duration_seconds.labels(
            task_type=task_type,
            job_id=str(job_id)
        ).observe(duration)

        # Update running task count
        if job_id and job_id in self._running_tasks_by_job:
            self._running_tasks_by_job[job_id] -= 1
            research_concurrent_tasks.labels(job_id=str(job_id)).set(
                max(0, self._running_tasks_by_job[job_id])
            )

        # Clean up start time
        self._task_start_times.pop(task_id, None)

        # Store timing in database
        try:
            self.supabase.table("plan_tasks").update({
                "execution_duration_seconds": round(duration, 3)
            }).eq("id", task_id).execute()
        except Exception as e:
            logger.warning(f"Failed to store task timing: {e}")

        logger.debug(
            "Task timing recorded",
            task_id=task_id,
            duration_seconds=round(duration, 2),
            task_type=task_type
        )

    def record_task_complete(
        self,
        task_id: int,
        task_type: str,
        job_id: int,
        success: bool = True
    ) -> float:
        """
        Record task completion and return duration.

        Args:
            task_id: Task ID
            task_type: Type of task
            job_id: Parent job ID
            success: Whether task completed successfully

        Returns:
            Task duration in seconds
        """
        end_time = time.time()
        start_time = self._task_start_times.get(task_id, end_time)
        duration = end_time - start_time

        self.record_task_timing(task_id, start_time, end_time, task_type, job_id)

        return duration

    # ==========================================================================
    # Parallelism Metrics
    # ==========================================================================

    def calculate_parallelism_ratio(self, job_id: int) -> float:
        """
        Calculate the parallelism ratio for a job.

        The ratio indicates how effectively tasks were executed in parallel.
        1.0 = fully sequential, higher = more parallel.

        Args:
            job_id: Research job ID

        Returns:
            Parallelism ratio (theoretical_max_parallel_time / actual_time)
        """
        try:
            # Get all tasks with timing
            result = self.supabase.table("plan_tasks").select(
                "id, started_at, completed_at, execution_duration_seconds"
            ).eq("job_id", job_id).not_.is_("completed_at", "null").execute()

            tasks = result.data or []
            if len(tasks) < 2:
                return 1.0  # Not enough tasks for meaningful parallelism

            # Calculate total task execution time (sum of all durations)
            total_task_time = sum(
                t.get("execution_duration_seconds", 0) or 0
                for t in tasks
            )

            # Get job actual duration
            job_result = self.supabase.table("research_jobs").select(
                "created_at, completed_at"
            ).eq("id", job_id).single().execute()

            if not job_result.data or not job_result.data.get("completed_at"):
                return 1.0

            job = job_result.data
            created = datetime.fromisoformat(job["created_at"].replace("Z", "+00:00"))
            completed = datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
            actual_duration = (completed - created).total_seconds()

            if actual_duration <= 0:
                return 1.0

            # Parallelism ratio: total_task_time / actual_duration
            # Higher is better (more parallelism achieved)
            ratio = total_task_time / actual_duration if actual_duration > 0 else 1.0

            # Update Prometheus gauge
            research_parallelism_ratio.labels(job_id=str(job_id)).set(
                min(ratio, len(tasks))  # Cap at max possible parallelism
            )

            logger.info(
                "Calculated parallelism ratio",
                job_id=job_id,
                ratio=round(ratio, 2),
                total_task_time=round(total_task_time, 2),
                actual_duration=round(actual_duration, 2)
            )

            return ratio

        except Exception as e:
            logger.error(f"Error calculating parallelism ratio: {e}", job_id=job_id)
            return 1.0

    def record_wave_start(self, job_id: int, wave_num: int) -> None:
        """Record the start of an execution wave."""
        self._wave_start_times[(job_id, wave_num)] = time.time()

    def record_wave_complete(
        self,
        job_id: int,
        wave_num: int,
        total_waves: int
    ) -> None:
        """
        Record wave completion and transition latency.

        Args:
            job_id: Job ID
            wave_num: Current wave number (1-indexed)
            total_waves: Total number of waves
        """
        # Record wave count
        research_wave_count.labels(job_id=str(job_id)).set(total_waves)

        # Calculate and record transition latency (if not last wave)
        if wave_num < total_waves:
            start_key = (job_id, wave_num)
            if start_key in self._wave_start_times:
                wave_duration = time.time() - self._wave_start_times[start_key]  # noqa: F841
                # Next wave start latency approximated as immediate
                research_wave_transition_latency_seconds.observe(0.1)
                del self._wave_start_times[start_key]

    # ==========================================================================
    # Quality Metrics
    # ==========================================================================

    def record_quality_score(
        self,
        artifact_id: int,
        score: float,
        artifact_type: Optional[str] = None,
        job_id: Optional[int] = None
    ) -> None:
        """
        Record quality score for an artifact.

        Args:
            artifact_id: Artifact ID
            score: Quality score (0-1)
            artifact_type: Type of artifact
            job_id: Parent job ID
        """
        # Fetch details if not provided
        if artifact_type is None or job_id is None:
            try:
                result = self.supabase.table("research_artifacts").select(
                    "artifact_type, job_id"
                ).eq("id", artifact_id).single().execute()
                if result.data:
                    artifact_type = result.data.get("artifact_type", "unknown")
                    job_id = result.data.get("job_id", 0)
            except Exception:
                artifact_type = artifact_type or "unknown"
                job_id = job_id or 0

        # Record Prometheus metric
        research_quality_score.labels(
            artifact_type=artifact_type,
            job_id=str(job_id)
        ).set(score)

        # Store in database
        try:
            self.supabase.table("research_artifacts").update({
                "confidence_score": score
            }).eq("id", artifact_id).execute()
        except Exception as e:
            logger.warning(f"Failed to store quality score: {e}")

        logger.debug(
            "Quality score recorded",
            artifact_id=artifact_id,
            score=score,
            artifact_type=artifact_type
        )

    def record_quality_gate_result(
        self,
        job_id: int,
        gate_type: str,
        passed: bool,
        score: Optional[float] = None,
        threshold: Optional[float] = None,
        message: Optional[str] = None
    ) -> None:
        """
        Record quality gate result.

        Args:
            job_id: Job ID
            gate_type: Type of quality gate
            passed: Whether gate passed
            score: Actual score (optional)
            threshold: Required threshold (optional)
            message: Additional message (optional)
        """
        if passed:
            research_quality_gate_passes_total.labels(
                gate_type=gate_type,
                job_id=str(job_id)
            ).inc()
        else:
            research_quality_gate_failures_total.labels(
                gate_type=gate_type,
                job_id=str(job_id)
            ).inc()

        logger.info(
            "Quality gate result",
            job_id=job_id,
            gate_type=gate_type,
            passed=passed,
            score=score,
            threshold=threshold
        )

    def record_retry(self, task_type: str, job_id: int) -> None:
        """Record a task retry."""
        research_retry_count.labels(
            task_type=task_type,
            job_id=str(job_id)
        ).inc()

    # ==========================================================================
    # Job Metrics
    # ==========================================================================

    def generate_job_metrics(self, job_id: int) -> JobMetrics:
        """
        Generate comprehensive metrics for a completed job.

        Args:
            job_id: Research job ID

        Returns:
            JobMetrics object with all metrics
        """
        try:
            # Get job details
            job_result = self.supabase.table("research_jobs").select(
                "*"
            ).eq("id", job_id).single().execute()
            job = job_result.data

            # Get task stats
            tasks_result = self.supabase.table("plan_tasks").select(
                "id, status, execution_duration_seconds"
            ).eq("job_id", job_id).execute()
            tasks = tasks_result.data or []

            # Get artifact count
            artifacts_result = self.supabase.table("research_artifacts").select(
                "id", count="exact"
            ).eq("job_id", job_id).execute()
            artifact_count = artifacts_result.count or 0

            # Calculate metrics
            total_tasks = len(tasks)
            completed_tasks = sum(1 for t in tasks if t["status"] == TaskStatus.COMPLETE.value)
            failed_tasks = sum(1 for t in tasks if t["status"] == TaskStatus.FAILED.value)

            # Duration calculation
            created_at = datetime.fromisoformat(job["created_at"].replace("Z", "+00:00"))
            completed_at = (
                datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
                if job.get("completed_at")
                else datetime.utcnow()
            )
            total_duration = (completed_at - created_at).total_seconds()

            # Average task duration
            durations = [
                t.get("execution_duration_seconds", 0) or 0
                for t in tasks
                if t.get("execution_duration_seconds")
            ]
            avg_task_duration = sum(durations) / len(durations) if durations else 0

            # Parallelism
            parallelism_ratio = self.calculate_parallelism_ratio(job_id)

            # Wave count (estimate from task structure)
            wave_count = len(set(
                t.get("sequence_order", 0) // 10 for t in tasks
            )) or 1

            # Complexity and SLA
            complexity = SLAConfig.get_complexity(total_tasks)
            sla_target = SLAConfig.get_target(complexity)
            sla_compliant = total_duration <= sla_target
            sla_margin = sla_target - total_duration

            # Record Prometheus metrics
            research_job_duration_seconds.labels(
                research_type=job.get("research_type", "general"),
                complexity=complexity
            ).observe(total_duration)

            research_job_task_count.labels(
                research_type=job.get("research_type", "general")
            ).observe(total_tasks)

            research_sla_compliance.labels(
                job_id=str(job_id),
                complexity=complexity
            ).set(1 if sla_compliant else 0)

            research_artifact_count.labels(
                artifact_type="all",
                job_id=str(job_id)
            ).set(artifact_count)

            metrics = JobMetrics(
                job_id=job_id,
                research_type=job.get("research_type", "general"),
                complexity=complexity,
                total_tasks=total_tasks,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                total_duration_seconds=total_duration,
                average_task_duration=avg_task_duration,
                parallelism_ratio=parallelism_ratio,
                wave_count=wave_count,
                quality_gates_passed=completed_tasks,  # Simplified
                quality_gates_failed=failed_tasks,
                artifact_count=artifact_count,
                sla_compliant=sla_compliant,
                sla_target_seconds=sla_target,
                sla_margin_seconds=sla_margin
            )

            logger.info(
                "Generated job metrics",
                job_id=job_id,
                duration=round(total_duration, 2),
                parallelism=round(parallelism_ratio, 2),
                sla_compliant=sla_compliant
            )

            return metrics

        except Exception as e:
            logger.error(f"Error generating job metrics: {e}", job_id=job_id)
            raise

    def check_sla_compliance(self, job_id: int) -> Dict[str, Any]:
        """
        Check if job meets SLA targets.

        Args:
            job_id: Research job ID

        Returns:
            Dict with compliance details
        """
        try:
            # Get job details
            job_result = self.supabase.table("research_jobs").select(
                "created_at, completed_at"
            ).eq("id", job_id).single().execute()
            job = job_result.data

            # Get task count for complexity
            tasks_result = self.supabase.table("plan_tasks").select(
                "id", count="exact"
            ).eq("job_id", job_id).execute()
            task_count = tasks_result.count or 0

            # Calculate duration
            created_at = datetime.fromisoformat(job["created_at"].replace("Z", "+00:00"))
            completed_at = (
                datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
                if job.get("completed_at")
                else datetime.utcnow()
            )
            duration = (completed_at - created_at).total_seconds()

            # Determine SLA
            complexity = SLAConfig.get_complexity(task_count)
            sla_target = SLAConfig.get_target(complexity)
            compliant = duration <= sla_target

            # Update Prometheus
            research_sla_compliance.labels(
                job_id=str(job_id),
                complexity=complexity
            ).set(1 if compliant else 0)

            result = {
                "compliant": compliant,
                "duration_seconds": duration,
                "sla_target_seconds": sla_target,
                "complexity": complexity,
                "margin_seconds": sla_target - duration,
                "task_count": task_count
            }

            logger.info("SLA compliance checked", job_id=job_id, **result)

            return result

        except Exception as e:
            logger.error(f"Error checking SLA compliance: {e}", job_id=job_id)
            return {
                "compliant": False,
                "error": str(e)
            }


# ==============================================================================
# Task Instrumentation Decorator
# ==============================================================================

def instrument_task_execution(
    task_type: str,
    job_id_extractor: Optional[Callable] = None
):
    """
    Decorator to instrument task execution with performance metrics.

    Args:
        task_type: Type of task being executed
        job_id_extractor: Optional function to extract job_id from args

    Usage:
        @instrument_task_execution("retrieval_rag")
        async def execute_rag_task(task: dict):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start_time = time.time()  # noqa: F841

            # Extract task info
            task_id = None
            job_id = None

            if args and isinstance(args[0], dict):
                task_id = args[0].get("id")
                job_id = args[0].get("job_id")
            elif job_id_extractor:
                job_id = job_id_extractor(*args, **kwargs)

            # Record start
            if task_id and job_id:
                monitor.record_task_start(task_id, task_type, job_id)

            try:
                result = await func(*args, **kwargs)

                # Record completion
                if task_id and job_id:
                    monitor.record_task_complete(task_id, task_type, job_id, success=True)

                return result

            except Exception as e:  # noqa: F841
                # Record failure
                if task_id and job_id:
                    monitor.record_task_complete(task_id, task_type, job_id, success=False)
                raise

        return wrapper
    return decorator


# ==============================================================================
# Service Factory
# ==============================================================================

_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get singleton instance of PerformanceMonitor."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor
