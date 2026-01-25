"""
Empire v7.3 - Worker Heartbeat Monitoring Service

Monitors Celery worker health and status through heartbeat signals.
Provides real-time visibility into worker availability and load.

Features:
- Worker registration and deregistration
- Heartbeat tracking with configurable thresholds
- Health status monitoring
- Automatic unhealthy worker detection
- Redis-backed state persistence
- Prometheus metrics integration

Author: Claude Code
Date: 2025-01-24
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum

import structlog
from prometheus_client import Gauge, Counter

logger = structlog.get_logger(__name__)


# ==============================================================================
# Prometheus Metrics
# ==============================================================================

WORKER_COUNT = Gauge(
    'empire_worker_count',
    'Number of registered workers',
    ['status']
)

WORKER_HEARTBEATS = Counter(
    'empire_worker_heartbeats_total',
    'Total heartbeats received',
    ['worker_id']
)

WORKER_TASK_COUNT = Gauge(
    'empire_worker_active_tasks',
    'Number of active tasks per worker',
    ['worker_id']
)


# ==============================================================================
# Data Models
# ==============================================================================

class WorkerStatus(str, Enum):
    """Worker health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"  # High load or slow heartbeat
    UNHEALTHY = "unhealthy"  # Missing heartbeats
    OFFLINE = "offline"


@dataclass
class WorkerInfo:
    """Information about a registered worker"""
    worker_id: str
    hostname: str
    status: WorkerStatus = WorkerStatus.HEALTHY

    # Registration
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)

    # Task tracking
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0

    # Resource info
    cpu_usage: float = 0.0
    memory_usage: float = 0.0

    # Queues
    queues: List[str] = field(default_factory=list)

    # Metadata
    celery_version: str = ""
    python_version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "status": self.status.value,
            "registered_at": self.registered_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "active_tasks": self.active_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "queues": self.queues,
            "celery_version": self.celery_version,
            "python_version": self.python_version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerInfo":
        """Create from dictionary"""
        return cls(
            worker_id=data["worker_id"],
            hostname=data["hostname"],
            status=WorkerStatus(data.get("status", "healthy")),
            registered_at=datetime.fromisoformat(data["registered_at"]),
            last_heartbeat=datetime.fromisoformat(data["last_heartbeat"]),
            active_tasks=data.get("active_tasks", 0),
            completed_tasks=data.get("completed_tasks", 0),
            failed_tasks=data.get("failed_tasks", 0),
            cpu_usage=data.get("cpu_usage", 0.0),
            memory_usage=data.get("memory_usage", 0.0),
            queues=data.get("queues", []),
            celery_version=data.get("celery_version", ""),
            python_version=data.get("python_version", "")
        )


@dataclass
class MonitorConfig:
    """Configuration for worker monitoring"""
    # Heartbeat thresholds
    heartbeat_interval: int = 30  # Expected heartbeat interval (seconds)
    degraded_threshold: int = 60  # Mark degraded after N seconds without heartbeat
    unhealthy_threshold: int = 120  # Mark unhealthy after N seconds
    offline_threshold: int = 300  # Mark offline after N seconds

    # Load thresholds
    high_cpu_threshold: float = 80.0
    high_memory_threshold: float = 80.0
    max_tasks_per_worker: int = 10

    # Cleanup
    cleanup_interval: int = 60  # Run cleanup every N seconds
    offline_retention: int = 3600  # Keep offline workers for N seconds


# ==============================================================================
# Worker Monitor Service
# ==============================================================================

class WorkerMonitor:
    """
    Monitor Celery worker health and status.

    Provides:
    - Worker registration and tracking
    - Heartbeat monitoring
    - Health status calculation
    - Unhealthy worker detection
    - Redis-backed persistence
    """

    REDIS_PREFIX = "empire:worker:"

    def __init__(self, config: Optional[MonitorConfig] = None):
        self.config = config or MonitorConfig()
        self._workers: Dict[str, WorkerInfo] = {}
        self._redis = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def initialize(self) -> None:
        """Initialize the worker monitor"""
        await self._connect_redis()
        await self._load_workers_from_redis()
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Worker monitor initialized")

    async def shutdown(self) -> None:
        """Shutdown the worker monitor"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        await self._save_all_workers()
        if self._redis:
            await self._redis.close()
        logger.info("Worker monitor shutdown")

    async def _connect_redis(self) -> None:
        """Connect to Redis"""
        import os
        import redis.asyncio as redis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis = redis.from_url(redis_url, decode_responses=True)

    async def _load_workers_from_redis(self) -> None:
        """Load worker state from Redis"""
        if not self._redis:
            return

        try:
            keys = await self._redis.keys(f"{self.REDIS_PREFIX}*")
            for key in keys:
                data = await self._redis.get(key)
                if data:
                    worker = WorkerInfo.from_dict(json.loads(data))
                    self._workers[worker.worker_id] = worker

            logger.info("Loaded workers from Redis", count=len(self._workers))
        except Exception as e:
            logger.error(f"Failed to load workers from Redis: {e}")

    async def _save_worker(self, worker: WorkerInfo) -> None:
        """Save worker state to Redis"""
        if not self._redis:
            return

        try:
            key = f"{self.REDIS_PREFIX}{worker.worker_id}"
            await self._redis.set(key, json.dumps(worker.to_dict()))
        except Exception as e:
            logger.error(f"Failed to save worker to Redis: {e}")

    async def _save_all_workers(self) -> None:
        """Save all workers to Redis"""
        for worker in self._workers.values():
            await self._save_worker(worker)

    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of stale workers"""
        while self._running:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self._cleanup_offline_workers()
                await self._update_worker_statuses()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    # ==========================================================================
    # Worker Registration
    # ==========================================================================

    async def register_worker(
        self,
        worker_id: str,
        hostname: str,
        queues: Optional[List[str]] = None,
        celery_version: str = "",
        python_version: str = ""
    ) -> WorkerInfo:
        """
        Register a new worker or update existing one.

        Args:
            worker_id: Unique worker identifier
            hostname: Worker hostname
            queues: List of queues the worker consumes from
            celery_version: Celery version string
            python_version: Python version string

        Returns:
            WorkerInfo for the registered worker
        """
        now = datetime.utcnow()

        if worker_id in self._workers:
            worker = self._workers[worker_id]
            worker.last_heartbeat = now
            worker.queues = queues or worker.queues
            worker.status = WorkerStatus.HEALTHY
        else:
            worker = WorkerInfo(
                worker_id=worker_id,
                hostname=hostname,
                registered_at=now,
                last_heartbeat=now,
                queues=queues or [],
                celery_version=celery_version,
                python_version=python_version
            )
            self._workers[worker_id] = worker

            logger.info(
                "Worker registered",
                worker_id=worker_id,
                hostname=hostname
            )

        await self._save_worker(worker)
        self._update_metrics()

        return worker

    async def deregister_worker(self, worker_id: str) -> bool:
        """
        Deregister a worker (graceful shutdown).

        Args:
            worker_id: Worker to deregister

        Returns:
            True if worker was found and removed
        """
        if worker_id in self._workers:
            del self._workers[worker_id]

            if self._redis:
                key = f"{self.REDIS_PREFIX}{worker_id}"
                await self._redis.delete(key)

            logger.info("Worker deregistered", worker_id=worker_id)
            self._update_metrics()
            return True

        return False

    # ==========================================================================
    # Heartbeat Handling
    # ==========================================================================

    async def send_heartbeat(
        self,
        worker_id: str,
        active_tasks: int = 0,
        cpu_usage: float = 0.0,
        memory_usage: float = 0.0
    ) -> bool:
        """
        Process a heartbeat from a worker.

        Args:
            worker_id: Worker sending the heartbeat
            active_tasks: Number of currently active tasks
            cpu_usage: Current CPU usage percentage
            memory_usage: Current memory usage percentage

        Returns:
            True if worker is registered
        """
        if worker_id not in self._workers:
            logger.warning("Heartbeat from unknown worker", worker_id=worker_id)
            return False

        worker = self._workers[worker_id]
        worker.last_heartbeat = datetime.utcnow()
        worker.active_tasks = active_tasks
        worker.cpu_usage = cpu_usage
        worker.memory_usage = memory_usage

        # Update status based on load
        if cpu_usage > self.config.high_cpu_threshold or \
           memory_usage > self.config.high_memory_threshold or \
           active_tasks > self.config.max_tasks_per_worker:
            worker.status = WorkerStatus.DEGRADED
        else:
            worker.status = WorkerStatus.HEALTHY

        await self._save_worker(worker)

        WORKER_HEARTBEATS.labels(worker_id=worker_id).inc()
        WORKER_TASK_COUNT.labels(worker_id=worker_id).set(active_tasks)

        return True

    async def record_task_complete(self, worker_id: str, success: bool = True) -> None:
        """Record task completion for a worker"""
        if worker_id not in self._workers:
            return

        worker = self._workers[worker_id]
        if success:
            worker.completed_tasks += 1
        else:
            worker.failed_tasks += 1

        if worker.active_tasks > 0:
            worker.active_tasks -= 1

        await self._save_worker(worker)

    # ==========================================================================
    # Health Checking
    # ==========================================================================

    async def check_worker_health(self) -> Dict[str, WorkerStatus]:
        """
        Check health of all workers.

        Returns:
            Dict mapping worker_id to status
        """
        await self._update_worker_statuses()
        return {w.worker_id: w.status for w in self._workers.values()}

    async def _update_worker_statuses(self) -> None:
        """Update worker statuses based on heartbeat age"""
        now = datetime.utcnow()

        for worker in self._workers.values():
            if worker.status == WorkerStatus.OFFLINE:
                continue

            elapsed = (now - worker.last_heartbeat).total_seconds()

            if elapsed > self.config.offline_threshold:
                worker.status = WorkerStatus.OFFLINE
            elif elapsed > self.config.unhealthy_threshold:
                worker.status = WorkerStatus.UNHEALTHY
            elif elapsed > self.config.degraded_threshold:
                worker.status = WorkerStatus.DEGRADED

        self._update_metrics()

    async def get_healthy_workers(self) -> List[WorkerInfo]:
        """Get all healthy workers"""
        await self._update_worker_statuses()
        return [w for w in self._workers.values() if w.status == WorkerStatus.HEALTHY]

    async def get_unhealthy_workers(self) -> List[WorkerInfo]:
        """Get all unhealthy workers"""
        await self._update_worker_statuses()
        return [
            w for w in self._workers.values()
            if w.status in (WorkerStatus.UNHEALTHY, WorkerStatus.OFFLINE)
        ]

    async def get_worker(self, worker_id: str) -> Optional[WorkerInfo]:
        """Get a specific worker by ID"""
        return self._workers.get(worker_id)

    async def get_all_workers(self) -> List[WorkerInfo]:
        """Get all registered workers"""
        await self._update_worker_statuses()
        return list(self._workers.values())

    # ==========================================================================
    # Worker Selection
    # ==========================================================================

    async def get_available_worker(
        self,
        queue: Optional[str] = None
    ) -> Optional[WorkerInfo]:
        """
        Get the best available worker for task assignment.

        Prioritizes workers by:
        1. Health status (healthy first)
        2. Load (fewer active tasks)
        3. Resource usage (lower CPU/memory)

        Args:
            queue: Optional queue filter

        Returns:
            Best available worker or None
        """
        await self._update_worker_statuses()

        candidates = [
            w for w in self._workers.values()
            if w.status in (WorkerStatus.HEALTHY, WorkerStatus.DEGRADED)
            and (queue is None or queue in w.queues)
        ]

        if not candidates:
            return None

        # Sort by health, then load, then resources
        candidates.sort(key=lambda w: (
            0 if w.status == WorkerStatus.HEALTHY else 1,
            w.active_tasks,
            w.cpu_usage + w.memory_usage
        ))

        return candidates[0]

    async def get_workers_for_queue(self, queue: str) -> List[WorkerInfo]:
        """Get all healthy workers consuming from a specific queue"""
        await self._update_worker_statuses()
        return [
            w for w in self._workers.values()
            if queue in w.queues and w.status == WorkerStatus.HEALTHY
        ]

    # ==========================================================================
    # Cleanup
    # ==========================================================================

    async def _cleanup_offline_workers(self) -> None:
        """Remove workers that have been offline too long"""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.config.offline_retention)

        to_remove = []
        for worker_id, worker in self._workers.items():
            if worker.status == WorkerStatus.OFFLINE and worker.last_heartbeat < cutoff:
                to_remove.append(worker_id)

        for worker_id in to_remove:
            await self.deregister_worker(worker_id)
            logger.info("Removed stale offline worker", worker_id=worker_id)

    # ==========================================================================
    # Metrics
    # ==========================================================================

    def _update_metrics(self) -> None:
        """Update Prometheus metrics"""
        status_counts = {s: 0 for s in WorkerStatus}

        for worker in self._workers.values():
            status_counts[worker.status] += 1

        for status, count in status_counts.items():
            WORKER_COUNT.labels(status=status.value).set(count)

    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        status_counts = {s.value: 0 for s in WorkerStatus}
        total_active_tasks = 0
        total_completed = 0
        total_failed = 0

        for worker in self._workers.values():
            status_counts[worker.status.value] += 1
            total_active_tasks += worker.active_tasks
            total_completed += worker.completed_tasks
            total_failed += worker.failed_tasks

        return {
            "total_workers": len(self._workers),
            "status_distribution": status_counts,
            "total_active_tasks": total_active_tasks,
            "total_completed_tasks": total_completed,
            "total_failed_tasks": total_failed,
            "workers": [w.to_dict() for w in self._workers.values()]
        }


# ==============================================================================
# Celery Signal Integration
# ==============================================================================

def setup_celery_worker_signals(monitor: WorkerMonitor) -> None:
    """
    Set up Celery signals to automatically report worker events.

    Call this during Celery worker startup.
    """
    from celery.signals import (
        worker_ready,
        worker_shutdown,
        heartbeat_sent,
        task_prerun,
        task_postrun,
        task_failure
    )
    import asyncio

    def run_async(coro):
        """Helper to run async in sync context"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)

    @worker_ready.connect
    def on_worker_ready(sender, **kwargs):
        import socket
        import sys
        import celery

        run_async(monitor.register_worker(
            worker_id=sender.hostname,
            hostname=socket.gethostname(),
            queues=list(sender.app.amqp.queues.keys()),
            celery_version=celery.__version__,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ))

    @worker_shutdown.connect
    def on_worker_shutdown(sender, **kwargs):
        run_async(monitor.deregister_worker(sender.hostname))

    @heartbeat_sent.connect
    def on_heartbeat(sender, **kwargs):
        import psutil

        cpu = psutil.cpu_percent()
        memory = psutil.virtual_memory().percent

        # Count active tasks (approximate)
        active = len(sender.pool._pool) if hasattr(sender, 'pool') else 0

        run_async(monitor.send_heartbeat(
            worker_id=sender.hostname,
            active_tasks=active,
            cpu_usage=cpu,
            memory_usage=memory
        ))

    @task_postrun.connect
    def on_task_complete(sender, task_id, task, retval, state, **kwargs):
        success = state == 'SUCCESS'
        # Get worker hostname from task request
        if hasattr(task, 'request') and task.request.hostname:
            run_async(monitor.record_task_complete(
                task.request.hostname,
                success=success
            ))

    @task_failure.connect
    def on_task_failure(sender, task_id, exception, **kwargs):
        if hasattr(sender, 'request') and sender.request.hostname:
            run_async(monitor.record_task_complete(
                sender.request.hostname,
                success=False
            ))


# ==============================================================================
# Service Factory
# ==============================================================================

_monitor_instance: Optional[WorkerMonitor] = None


async def get_worker_monitor() -> WorkerMonitor:
    """Get or create the worker monitor singleton"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = WorkerMonitor()
        await _monitor_instance.initialize()
    return _monitor_instance


def get_worker_monitor_sync() -> WorkerMonitor:
    """Get or create worker monitor (sync version for signal handlers)"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = WorkerMonitor()
    return _monitor_instance
