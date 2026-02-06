"""
Resource-Aware Scheduling Service

Monitors system resources (CPU, memory, I/O) and provides intelligent
scheduling decisions based on current resource availability.

Features:
- Real-time resource monitoring using psutil
- Task resource requirement estimation
- Scheduling decisions based on available capacity
- Resource reservation and release
- Historical resource usage tracking
- Prometheus metrics integration
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import structlog

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = structlog.get_logger(__name__)


class ResourceType(str, Enum):
    """Types of system resources to monitor."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK_IO = "disk_io"
    NETWORK_IO = "network_io"
    GPU = "gpu"


class ResourcePressure(str, Enum):
    """Resource pressure levels."""
    LOW = "low"        # < 50% utilization
    MODERATE = "moderate"  # 50-75% utilization
    HIGH = "high"      # 75-90% utilization
    CRITICAL = "critical"  # > 90% utilization


@dataclass
class ResourceUsage:
    """Current resource usage snapshot."""
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    memory_used_mb: float
    disk_read_bytes_per_sec: float = 0.0
    disk_write_bytes_per_sec: float = 0.0
    network_bytes_sent_per_sec: float = 0.0
    network_bytes_recv_per_sec: float = 0.0
    active_processes: int = 0
    load_average_1m: float = 0.0
    load_average_5m: float = 0.0
    load_average_15m: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def cpu_pressure(self) -> ResourcePressure:
        """Get CPU pressure level."""
        if self.cpu_percent < 50:
            return ResourcePressure.LOW
        elif self.cpu_percent < 75:
            return ResourcePressure.MODERATE
        elif self.cpu_percent < 90:
            return ResourcePressure.HIGH
        return ResourcePressure.CRITICAL

    @property
    def memory_pressure(self) -> ResourcePressure:
        """Get memory pressure level."""
        if self.memory_percent < 50:
            return ResourcePressure.LOW
        elif self.memory_percent < 75:
            return ResourcePressure.MODERATE
        elif self.memory_percent < 90:
            return ResourcePressure.HIGH
        return ResourcePressure.CRITICAL

    @property
    def overall_pressure(self) -> ResourcePressure:
        """Get overall system pressure level."""
        pressures = [self.cpu_pressure, self.memory_pressure]
        pressure_order = [
            ResourcePressure.CRITICAL,
            ResourcePressure.HIGH,
            ResourcePressure.MODERATE,
            ResourcePressure.LOW
        ]

        for pressure in pressure_order:
            if pressure in pressures:
                return pressure

        return ResourcePressure.LOW

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_available_mb": self.memory_available_mb,
            "memory_used_mb": self.memory_used_mb,
            "disk_read_bytes_per_sec": self.disk_read_bytes_per_sec,
            "disk_write_bytes_per_sec": self.disk_write_bytes_per_sec,
            "network_bytes_sent_per_sec": self.network_bytes_sent_per_sec,
            "network_bytes_recv_per_sec": self.network_bytes_recv_per_sec,
            "active_processes": self.active_processes,
            "load_average_1m": self.load_average_1m,
            "load_average_5m": self.load_average_5m,
            "load_average_15m": self.load_average_15m,
            "cpu_pressure": self.cpu_pressure.value,
            "memory_pressure": self.memory_pressure.value,
            "overall_pressure": self.overall_pressure.value,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class TaskResourceRequirements:
    """Resource requirements for a task."""
    task_id: str
    estimated_cpu_percent: float = 10.0  # Expected CPU usage
    estimated_memory_mb: float = 256.0   # Expected memory usage
    estimated_duration_seconds: float = 60.0  # Expected duration
    priority: int = 5  # 1-10, higher = more important
    can_be_throttled: bool = True  # Whether task can run with reduced resources
    requires_gpu: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "estimated_cpu_percent": self.estimated_cpu_percent,
            "estimated_memory_mb": self.estimated_memory_mb,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "priority": self.priority,
            "can_be_throttled": self.can_be_throttled,
            "requires_gpu": self.requires_gpu
        }


@dataclass
class ResourceReservation:
    """A resource reservation for a task."""
    id: UUID
    task_id: str
    cpu_reserved: float
    memory_reserved_mb: float
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    @property
    def is_expired(self) -> bool:
        """Check if reservation has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass
class SchedulingDecision:
    """Decision about whether a task can be scheduled."""
    can_schedule: bool
    reason: str
    recommended_delay_seconds: Optional[float] = None
    throttle_factor: Optional[float] = None  # 0.0-1.0, reduce resources by this factor
    current_usage: Optional[ResourceUsage] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "can_schedule": self.can_schedule,
            "reason": self.reason,
            "recommended_delay_seconds": self.recommended_delay_seconds,
            "throttle_factor": self.throttle_factor,
            "current_usage": self.current_usage.to_dict() if self.current_usage else None
        }


class ResourceMonitor:
    """
    Monitors system resources and provides scheduling decisions.

    Uses psutil for resource monitoring and maintains historical
    data for trend analysis.
    """

    def __init__(
        self,
        cpu_threshold: float = 80.0,
        memory_threshold: float = 85.0,
        sample_interval_seconds: float = 1.0,
        history_size: int = 300  # 5 minutes at 1 sample/second
    ):
        self._cpu_threshold = cpu_threshold
        self._memory_threshold = memory_threshold
        self._sample_interval = sample_interval_seconds
        self._history_size = history_size

        self._usage_history: List[ResourceUsage] = []
        self._reservations: Dict[UUID, ResourceReservation] = {}
        self._last_disk_io: Optional[Tuple[int, int, float]] = None
        self._last_network_io: Optional[Tuple[int, int, float]] = None

        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable[[ResourceUsage], None]] = []
        self._lock = asyncio.Lock()

        if not PSUTIL_AVAILABLE:
            logger.warning("psutil_not_available", message="Resource monitoring will use mock data")

    async def start_monitoring(self) -> None:
        """Start background resource monitoring."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())

        logger.info(
            "resource_monitoring_started",
            cpu_threshold=self._cpu_threshold,
            memory_threshold=self._memory_threshold,
            sample_interval=self._sample_interval
        )

    async def stop_monitoring(self) -> None:
        """Stop background resource monitoring."""
        self._monitoring = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        logger.info("resource_monitoring_stopped")

    async def _monitoring_loop(self) -> None:
        """Background loop for resource monitoring."""
        while self._monitoring:
            try:
                usage = await self.get_current_usage()

                async with self._lock:
                    self._usage_history.append(usage)
                    if len(self._usage_history) > self._history_size:
                        self._usage_history.pop(0)

                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(usage)
                    except Exception as e:
                        logger.error("callback_error", error=str(e))

                # Log if pressure is high
                if usage.overall_pressure in [ResourcePressure.HIGH, ResourcePressure.CRITICAL]:
                    logger.warning(
                        "high_resource_pressure",
                        cpu_percent=usage.cpu_percent,
                        memory_percent=usage.memory_percent,
                        pressure=usage.overall_pressure.value
                    )

                await asyncio.sleep(self._sample_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("monitoring_loop_error", error=str(e))
                await asyncio.sleep(self._sample_interval)

    def add_callback(self, callback: Callable[[ResourceUsage], None]) -> None:
        """Add a callback for resource updates."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[ResourceUsage], None]) -> None:
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def get_current_usage(self) -> ResourceUsage:
        """Get current resource usage."""
        if not PSUTIL_AVAILABLE:
            return self._get_mock_usage()

        return await asyncio.to_thread(self._collect_usage)

    def _collect_usage(self) -> ResourceUsage:
        """Collect resource usage (blocking, run in thread)."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Memory
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available / (1024 * 1024)
        memory_used_mb = memory.used / (1024 * 1024)

        # Disk I/O
        disk_io = psutil.disk_io_counters()
        current_time = time.time()

        disk_read_rate = 0.0
        disk_write_rate = 0.0

        if disk_io and self._last_disk_io:
            last_read, last_write, last_time = self._last_disk_io
            time_delta = current_time - last_time
            if time_delta > 0:
                disk_read_rate = (disk_io.read_bytes - last_read) / time_delta
                disk_write_rate = (disk_io.write_bytes - last_write) / time_delta

        if disk_io:
            self._last_disk_io = (disk_io.read_bytes, disk_io.write_bytes, current_time)

        # Network I/O
        network_io = psutil.net_io_counters()
        network_sent_rate = 0.0
        network_recv_rate = 0.0

        if network_io and self._last_network_io:
            last_sent, last_recv, last_time = self._last_network_io
            time_delta = current_time - last_time
            if time_delta > 0:
                network_sent_rate = (network_io.bytes_sent - last_sent) / time_delta
                network_recv_rate = (network_io.bytes_recv - last_recv) / time_delta

        if network_io:
            self._last_network_io = (network_io.bytes_sent, network_io.bytes_recv, current_time)

        # Load average (Unix only)
        try:
            load_avg = psutil.getloadavg()
        except (AttributeError, OSError):
            load_avg = (0.0, 0.0, 0.0)

        # Process count
        active_processes = len(psutil.pids())

        return ResourceUsage(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_available_mb=memory_available_mb,
            memory_used_mb=memory_used_mb,
            disk_read_bytes_per_sec=disk_read_rate,
            disk_write_bytes_per_sec=disk_write_rate,
            network_bytes_sent_per_sec=network_sent_rate,
            network_bytes_recv_per_sec=network_recv_rate,
            active_processes=active_processes,
            load_average_1m=load_avg[0],
            load_average_5m=load_avg[1],
            load_average_15m=load_avg[2]
        )

    def _get_mock_usage(self) -> ResourceUsage:
        """Get mock usage when psutil is not available."""
        return ResourceUsage(
            cpu_percent=50.0,
            memory_percent=60.0,
            memory_available_mb=8192.0,
            memory_used_mb=12288.0
        )

    async def can_schedule_task(
        self,
        requirements: TaskResourceRequirements
    ) -> SchedulingDecision:
        """Determine if a task can be scheduled given current resources."""
        usage = await self.get_current_usage()

        # Calculate reserved resources
        reserved_cpu = 0.0
        reserved_memory = 0.0

        async with self._lock:
            # Clean up expired reservations
            expired = [rid for rid, res in self._reservations.items() if res.is_expired]
            for rid in expired:
                del self._reservations[rid]

            for reservation in self._reservations.values():
                reserved_cpu += reservation.cpu_reserved
                reserved_memory += reservation.memory_reserved_mb

        # Calculate available resources
        available_cpu = 100.0 - usage.cpu_percent - reserved_cpu
        available_memory = usage.memory_available_mb - reserved_memory

        # Check if we have enough resources
        cpu_needed = requirements.estimated_cpu_percent
        memory_needed = requirements.estimated_memory_mb

        # Check thresholds
        projected_cpu = usage.cpu_percent + reserved_cpu + cpu_needed
        projected_memory = usage.memory_percent + (memory_needed / usage.memory_available_mb * 100)

        # Critical pressure - don't schedule
        if usage.overall_pressure == ResourcePressure.CRITICAL:
            if requirements.priority < 8:  # Only allow high priority tasks
                return SchedulingDecision(
                    can_schedule=False,
                    reason="System under critical resource pressure",
                    recommended_delay_seconds=30.0,
                    current_usage=usage
                )

        # High pressure - throttle or delay
        if usage.overall_pressure == ResourcePressure.HIGH:
            if requirements.can_be_throttled:
                return SchedulingDecision(
                    can_schedule=True,
                    reason="High pressure, task will be throttled",
                    throttle_factor=0.5,
                    current_usage=usage
                )
            elif requirements.priority < 6:
                return SchedulingDecision(
                    can_schedule=False,
                    reason="High pressure, delaying low priority task",
                    recommended_delay_seconds=10.0,
                    current_usage=usage
                )

        # Check specific resources
        if projected_cpu > self._cpu_threshold:
            if requirements.can_be_throttled:
                return SchedulingDecision(
                    can_schedule=True,
                    reason="CPU threshold exceeded, task will be throttled",
                    throttle_factor=0.7,
                    current_usage=usage
                )
            return SchedulingDecision(
                can_schedule=False,
                reason=f"CPU would exceed threshold ({projected_cpu:.1f}% > {self._cpu_threshold}%)",
                recommended_delay_seconds=5.0,
                current_usage=usage
            )

        if projected_memory > self._memory_threshold:
            return SchedulingDecision(
                can_schedule=False,
                reason=f"Memory would exceed threshold ({projected_memory:.1f}% > {self._memory_threshold}%)",
                recommended_delay_seconds=10.0,
                current_usage=usage
            )

        if available_memory < memory_needed:
            return SchedulingDecision(
                can_schedule=False,
                reason=f"Insufficient memory ({available_memory:.0f}MB < {memory_needed:.0f}MB needed)",
                recommended_delay_seconds=15.0,
                current_usage=usage
            )

        # All checks passed
        return SchedulingDecision(
            can_schedule=True,
            reason="Resources available",
            current_usage=usage
        )

    async def reserve_resources(
        self,
        task_id: str,
        cpu_percent: float,
        memory_mb: float,
        duration_seconds: Optional[float] = None
    ) -> UUID:
        """Reserve resources for a task."""
        reservation = ResourceReservation(
            id=uuid4(),
            task_id=task_id,
            cpu_reserved=cpu_percent,
            memory_reserved_mb=memory_mb,
            expires_at=datetime.utcnow() + timedelta(seconds=duration_seconds) if duration_seconds else None
        )

        async with self._lock:
            self._reservations[reservation.id] = reservation

        logger.debug(
            "resources_reserved",
            reservation_id=str(reservation.id),
            task_id=task_id,
            cpu=cpu_percent,
            memory_mb=memory_mb
        )

        return reservation.id

    async def release_resources(self, reservation_id: UUID) -> bool:
        """Release a resource reservation."""
        async with self._lock:
            if reservation_id in self._reservations:
                del self._reservations[reservation_id]
                logger.debug("resources_released", reservation_id=str(reservation_id))
                return True
        return False

    async def get_usage_history(
        self,
        duration_seconds: Optional[float] = None
    ) -> List[ResourceUsage]:
        """Get historical resource usage."""
        async with self._lock:
            if duration_seconds is None:
                return list(self._usage_history)

            cutoff = datetime.utcnow() - timedelta(seconds=duration_seconds)
            return [u for u in self._usage_history if u.timestamp >= cutoff]

    async def get_usage_stats(
        self,
        duration_seconds: float = 60.0
    ) -> Dict[str, Any]:
        """Get usage statistics over a period."""
        history = await self.get_usage_history(duration_seconds)

        if not history:
            return {}

        cpu_values = [u.cpu_percent for u in history]
        memory_values = [u.memory_percent for u in history]

        return {
            "sample_count": len(history),
            "duration_seconds": duration_seconds,
            "cpu": {
                "avg": sum(cpu_values) / len(cpu_values),
                "min": min(cpu_values),
                "max": max(cpu_values)
            },
            "memory": {
                "avg": sum(memory_values) / len(memory_values),
                "min": min(memory_values),
                "max": max(memory_values)
            }
        }

    async def get_recommended_concurrency(
        self,
        task_cpu_estimate: float = 10.0,
        task_memory_estimate_mb: float = 256.0
    ) -> int:
        """Get recommended concurrency level based on current resources."""
        usage = await self.get_current_usage()

        # Calculate available headroom
        cpu_headroom = max(0, self._cpu_threshold - usage.cpu_percent)
        memory_headroom = max(0, self._memory_threshold - usage.memory_percent)

        # Calculate how many tasks we can run
        cpu_concurrency = int(cpu_headroom / task_cpu_estimate) if task_cpu_estimate > 0 else 10
        memory_concurrency = int(
            (usage.memory_available_mb * memory_headroom / 100) / task_memory_estimate_mb
        ) if task_memory_estimate_mb > 0 else 10

        # Take the minimum and ensure at least 1
        recommended = max(1, min(cpu_concurrency, memory_concurrency))

        logger.debug(
            "recommended_concurrency",
            recommended=recommended,
            cpu_headroom=cpu_headroom,
            memory_headroom=memory_headroom
        )

        return recommended


class TaskResourceEstimator:
    """Estimates resource requirements for tasks based on historical data."""

    def __init__(self):
        self._task_history: Dict[str, List[Dict[str, float]]] = {}
        self._default_estimates: Dict[str, TaskResourceRequirements] = {
            "retrieval": TaskResourceRequirements(
                task_id="retrieval",
                estimated_cpu_percent=15.0,
                estimated_memory_mb=512.0,
                estimated_duration_seconds=30.0
            ),
            "synthesis": TaskResourceRequirements(
                task_id="synthesis",
                estimated_cpu_percent=25.0,
                estimated_memory_mb=1024.0,
                estimated_duration_seconds=60.0
            ),
            "report": TaskResourceRequirements(
                task_id="report",
                estimated_cpu_percent=20.0,
                estimated_memory_mb=768.0,
                estimated_duration_seconds=45.0
            ),
            "embedding": TaskResourceRequirements(
                task_id="embedding",
                estimated_cpu_percent=30.0,
                estimated_memory_mb=2048.0,
                estimated_duration_seconds=120.0
            )
        }

    def record_task_resources(
        self,
        task_type: str,
        cpu_percent: float,
        memory_mb: float,
        duration_seconds: float
    ) -> None:
        """Record actual resource usage for a task."""
        if task_type not in self._task_history:
            self._task_history[task_type] = []

        self._task_history[task_type].append({
            "cpu_percent": cpu_percent,
            "memory_mb": memory_mb,
            "duration_seconds": duration_seconds
        })

        # Keep only last 100 samples
        if len(self._task_history[task_type]) > 100:
            self._task_history[task_type].pop(0)

    def estimate_requirements(
        self,
        task_type: str,
        task_id: str,
        priority: int = 5
    ) -> TaskResourceRequirements:
        """Estimate resource requirements for a task type."""
        # Check if we have historical data
        history = self._task_history.get(task_type, [])

        if len(history) >= 5:
            # Use historical average with 20% buffer
            avg_cpu = sum(h["cpu_percent"] for h in history) / len(history) * 1.2
            avg_memory = sum(h["memory_mb"] for h in history) / len(history) * 1.2
            avg_duration = sum(h["duration_seconds"] for h in history) / len(history) * 1.1

            return TaskResourceRequirements(
                task_id=task_id,
                estimated_cpu_percent=avg_cpu,
                estimated_memory_mb=avg_memory,
                estimated_duration_seconds=avg_duration,
                priority=priority
            )

        # Use defaults
        default = self._default_estimates.get(
            task_type,
            TaskResourceRequirements(task_id=task_id, priority=priority)
        )

        return TaskResourceRequirements(
            task_id=task_id,
            estimated_cpu_percent=default.estimated_cpu_percent,
            estimated_memory_mb=default.estimated_memory_mb,
            estimated_duration_seconds=default.estimated_duration_seconds,
            priority=priority
        )


# Global instances
_resource_monitor: Optional[ResourceMonitor] = None
_resource_estimator: Optional[TaskResourceEstimator] = None


async def get_resource_monitor() -> ResourceMonitor:
    """Get the global resource monitor instance."""
    global _resource_monitor

    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
        await _resource_monitor.start_monitoring()

    return _resource_monitor


def get_resource_estimator() -> TaskResourceEstimator:
    """Get the global resource estimator instance."""
    global _resource_estimator

    if _resource_estimator is None:
        _resource_estimator = TaskResourceEstimator()

    return _resource_estimator


async def shutdown_resource_monitor() -> None:
    """Shutdown the resource monitor."""
    global _resource_monitor

    if _resource_monitor:
        await _resource_monitor.stop_monitoring()
        _resource_monitor = None
