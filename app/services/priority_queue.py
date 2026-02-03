"""
Empire v7.3 - Priority Task Queue

Priority queue implementation for task execution ordering.
Uses heapq for efficient priority-based task retrieval.

Features:
- Priority levels 1-10 (10 = highest priority)
- Dynamic priority adjustment
- Priority inheritance from dependencies
- Queue metrics and monitoring

Author: Claude Code
Date: 2025-01-24
"""

import heapq
import threading
from datetime import datetime, timezone
from typing import ClassVar, Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import IntEnum

import structlog
from prometheus_client import Gauge, Counter

logger = structlog.get_logger(__name__)


# ==============================================================================
# Prometheus Metrics
# ==============================================================================

QUEUE_SIZE = Gauge(
    'empire_priority_queue_size',
    'Current size of the priority queue',
    ['queue_name']
)

QUEUE_ENQUEUED = Counter(
    'empire_priority_queue_enqueued_total',
    'Total items enqueued',
    ['queue_name', 'priority']
)

QUEUE_DEQUEUED = Counter(
    'empire_priority_queue_dequeued_total',
    'Total items dequeued',
    ['queue_name']
)


# ==============================================================================
# Priority Levels
# ==============================================================================

class Priority(IntEnum):
    """Task priority levels (higher = more urgent)"""
    LOWEST = 1
    LOW = 3
    NORMAL = 5
    HIGH = 7
    HIGHEST = 9
    CRITICAL = 10


# ==============================================================================
# Queue Item
# ==============================================================================

@dataclass(order=True)
class QueueItem:
    """
    Item in the priority queue.

    Note: Order is determined by (negative priority, timestamp, task_key)
    to ensure higher priority items come first, with FIFO for same priority.
    """
    # Sort key (priority is negated so higher priority comes first in min-heap)
    sort_key: Tuple[int, float, str] = field(compare=True)

    # Actual data
    task_id: int = field(compare=False)
    task_key: str = field(compare=False)
    task_type: str = field(compare=False)
    priority: int = field(compare=False)
    job_id: int = field(compare=False)
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False)
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc), compare=False)
    removed: bool = field(default=False, compare=False)

    @classmethod
    def create(
        cls,
        task_id: int,
        task_key: str,
        task_type: str,
        priority: int = Priority.NORMAL,
        job_id: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "QueueItem":
        """Factory method to create a queue item with proper sort key"""
        now = datetime.now(timezone.utc)
        timestamp = now.timestamp()
        return cls(
            sort_key=(-priority, timestamp, task_key),
            task_id=task_id,
            task_key=task_key,
            task_type=task_type,
            priority=priority,
            job_id=job_id,
            metadata=metadata or {},
            enqueued_at=now
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "task_key": self.task_key,
            "task_type": self.task_type,
            "priority": self.priority,
            "job_id": self.job_id,
            "metadata": self.metadata,
            "enqueued_at": self.enqueued_at.isoformat()
        }


# ==============================================================================
# Priority Queue Implementation
# ==============================================================================

class PriorityTaskQueue:
    """
    Thread-safe priority queue for task execution ordering.

    Uses a min-heap with negated priorities to ensure higher priority
    tasks are retrieved first. Tasks with the same priority are
    processed in FIFO order.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._heap: List[QueueItem] = []
        self._lock = threading.RLock()
        self._task_map: Dict[str, QueueItem] = {}  # task_key -> item for O(1) lookup

    @property
    def size(self) -> int:
        """Current queue size (excluding removed items)"""
        with self._lock:
            return len(self._task_map)

    def is_empty(self) -> bool:
        """Check if queue is empty"""
        with self._lock:
            return len(self._task_map) == 0

    # ==========================================================================
    # Core Operations
    # ==========================================================================

    def push(
        self,
        task_id: int,
        task_key: str,
        task_type: str,
        priority: int = Priority.NORMAL,
        job_id: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a task to the queue.

        Args:
            task_id: Task database ID
            task_key: Unique task key
            task_type: Type of task
            priority: Priority level (1-10, higher = more urgent)
            job_id: Job ID the task belongs to
            metadata: Additional task metadata

        Returns:
            True if task was newly added, False if it already existed (priority updated)
        """
        with self._lock:
            # Check if task already exists
            if task_key in self._task_map:
                logger.warning(
                    "Task already in queue, updating priority",
                    task_key=task_key
                )
                self._update_priority_locked(task_key, priority)
                return False

            item = QueueItem.create(
                task_id=task_id,
                task_key=task_key,
                task_type=task_type,
                priority=priority,
                job_id=job_id,
                metadata=metadata
            )

            heapq.heappush(self._heap, item)
            self._task_map[task_key] = item

            # Update metrics
            QUEUE_SIZE.labels(queue_name=self.name).set(self.size)
            QUEUE_ENQUEUED.labels(queue_name=self.name, priority=str(int(priority))).inc()

            logger.debug(
                "Task enqueued",
                task_key=task_key,
                priority=priority,
                queue_size=self.size
            )
            return True

    def pop(self) -> Optional[QueueItem]:
        """
        Remove and return the highest priority task.

        Returns:
            QueueItem or None if empty
        """
        with self._lock:
            while self._heap:
                item = heapq.heappop(self._heap)

                # Skip if marked as removed
                if item.removed:
                    continue

                # Remove from task map
                del self._task_map[item.task_key]

                # Update metrics
                QUEUE_SIZE.labels(queue_name=self.name).set(self.size)
                QUEUE_DEQUEUED.labels(queue_name=self.name).inc()

                logger.debug(
                    "Task dequeued",
                    task_key=item.task_key,
                    priority=item.priority
                )

                return item

            return None

    def peek(self) -> Optional[QueueItem]:
        """
        View the highest priority task without removing it.

        Returns:
            QueueItem or None if empty
        """
        with self._lock:
            while self._heap and self._heap[0].removed:
                heapq.heappop(self._heap)
            return self._heap[0] if self._heap else None

    def pop_batch(self, count: int) -> List[QueueItem]:
        """
        Remove and return up to `count` highest priority tasks.

        Args:
            count: Maximum number of tasks to pop

        Returns:
            List of QueueItems
        """
        items = []
        for _ in range(count):
            item = self.pop()
            if item is None:
                break
            items.append(item)
        return items

    # ==========================================================================
    # Task Management
    # ==========================================================================

    def remove(self, task_key: str) -> bool:
        """
        Remove a task from the queue (lazy deletion).

        Args:
            task_key: Task key to remove

        Returns:
            True if task was in queue and marked for removal
        """
        with self._lock:
            if task_key in self._task_map:
                self._task_map[task_key].removed = True
                del self._task_map[task_key]
                QUEUE_SIZE.labels(queue_name=self.name).set(self.size)
                logger.debug("Task marked for removal", task_key=task_key)
                return True
            return False

    def _update_priority_locked(self, task_key: str, new_priority: int) -> bool:
        """
        Internal: Update priority while lock is already held.

        Args:
            task_key: Task key to update
            new_priority: New priority level

        Returns:
            True if task was found and updated
        """
        if task_key not in self._task_map:
            return False

        old_item = self._task_map[task_key]

        if old_item.priority == new_priority:
            return True

        # Mark old entry as removed
        old_item.removed = True

        # Create new entry with updated priority
        new_item = QueueItem.create(
            task_id=old_item.task_id,
            task_key=task_key,
            task_type=old_item.task_type,
            priority=new_priority,
            job_id=old_item.job_id,
            metadata=old_item.metadata
        )

        heapq.heappush(self._heap, new_item)
        self._task_map[task_key] = new_item

        logger.debug(
            "Task priority updated",
            task_key=task_key,
            old_priority=old_item.priority,
            new_priority=new_priority
        )

        return True

    def update_priority(self, task_key: str, new_priority: int) -> bool:
        """
        Update the priority of a task in the queue.

        This uses lazy deletion - marks old entry as removed
        and adds a new entry with updated priority.

        Args:
            task_key: Task key to update
            new_priority: New priority level

        Returns:
            True if task was found and updated
        """
        with self._lock:
            return self._update_priority_locked(task_key, new_priority)

    def contains(self, task_key: str) -> bool:
        """Check if a task is in the queue"""
        with self._lock:
            return task_key in self._task_map

    def get(self, task_key: str) -> Optional[QueueItem]:
        """Get a task by key without removing it"""
        with self._lock:
            if task_key in self._task_map:
                return self._task_map[task_key]
            return None

    # ==========================================================================
    # Batch Operations
    # ==========================================================================

    def push_batch(self, items: List[Dict[str, Any]]) -> int:
        """
        Add multiple tasks to the queue.

        Args:
            items: List of dicts with task_id, task_key, task_type, priority, etc.

        Returns:
            Number of tasks actually added (excludes duplicates)
        """
        added = 0
        for item in items:
            # push() returns True if newly added, False if duplicate (atomically checked)
            was_new = self.push(
                task_id=item["task_id"],
                task_key=item["task_key"],
                task_type=item.get("task_type", "unknown"),
                priority=item.get("priority", Priority.NORMAL),
                job_id=item.get("job_id", 0),
                metadata=item.get("metadata")
            )
            if was_new:
                added += 1
        return added

    def clear(self) -> int:
        """
        Clear all tasks from the queue.

        Returns:
            Number of tasks cleared
        """
        with self._lock:
            count = self.size
            self._heap.clear()
            self._task_map.clear()
            QUEUE_SIZE.labels(queue_name=self.name).set(0)
            logger.info("Queue cleared", count=count)
            return count

    def clear_job(self, job_id: int) -> int:
        """
        Remove all tasks for a specific job.

        Args:
            job_id: Job ID to clear

        Returns:
            Number of tasks removed
        """
        with self._lock:
            removed = 0
            for task_key, item in list(self._task_map.items()):
                if item.job_id == job_id:
                    item.removed = True
                    del self._task_map[task_key]
                    removed += 1

            QUEUE_SIZE.labels(queue_name=self.name).set(self.size)
            logger.info("Cleared job tasks", job_id=job_id, count=removed)
            return removed

    # ==========================================================================
    # Query Methods
    # ==========================================================================

    def get_by_priority(self, priority: int) -> List[QueueItem]:
        """Get all tasks with a specific priority"""
        with self._lock:
            return [
                item for item in self._task_map.values()
                if item.priority == priority
            ]

    def get_by_job(self, job_id: int) -> List[QueueItem]:
        """Get all tasks for a specific job"""
        with self._lock:
            return [
                item for item in self._task_map.values()
                if item.job_id == job_id
            ]

    def get_by_type(self, task_type: str) -> List[QueueItem]:
        """Get all tasks of a specific type"""
        with self._lock:
            return [
                item for item in self._task_map.values()
                if item.task_type == task_type
            ]

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        with self._lock:
            active_items = list(self._task_map.values())

            priority_counts = {}
            type_counts = {}
            job_counts = {}

            for item in active_items:
                priority_counts[item.priority] = priority_counts.get(item.priority, 0) + 1
                type_counts[item.task_type] = type_counts.get(item.task_type, 0) + 1
                job_counts[item.job_id] = job_counts.get(item.job_id, 0) + 1

            return {
                "name": self.name,
                "size": len(active_items),
                "heap_size": len(self._heap),
                "removed_count": len(self._heap) - len(active_items),
                "priority_distribution": priority_counts,
                "type_distribution": type_counts,
                "job_distribution": job_counts
            }

    def to_list(self) -> List[Dict[str, Any]]:
        """Get all tasks as a sorted list"""
        with self._lock:
            items = list(self._task_map.values())
            # Sort by priority (highest first) and timestamp
            items.sort(key=lambda x: x.sort_key)
            return [item.to_dict() for item in items]

    # ==========================================================================
    # Maintenance
    # ==========================================================================

    def compact(self) -> int:
        """
        Remove all marked-as-removed entries and rebuild the heap.
        Call this periodically if many removals occur.

        Returns:
            Number of entries removed
        """
        with self._lock:
            old_size = len(self._heap)

            # Filter out removed items
            self._heap = [
                item for item in self._heap
                if not item.removed
            ]

            # Rebuild the heap
            heapq.heapify(self._heap)

            removed_count = old_size - len(self._heap)

            new_size = len(self._heap)
            logger.info(
                "Queue compacted",
                old_size=old_size,
                new_size=new_size,
                removed=removed_count
            )

            return old_size - new_size


# ==============================================================================
# Multi-Queue Manager
# ==============================================================================

class PriorityQueueManager:
    """
    Manages multiple named priority queues.

    Useful for having separate queues for different task types
    or processing stages.
    """

    def __init__(self):
        self._queues: Dict[str, PriorityTaskQueue] = {}
        self._lock = threading.RLock()

    def get_queue(self, name: str) -> PriorityTaskQueue:
        """Get or create a named queue"""
        with self._lock:
            if name not in self._queues:
                self._queues[name] = PriorityTaskQueue(name)
            return self._queues[name]

    def delete_queue(self, name: str) -> bool:
        """Delete a named queue"""
        with self._lock:
            if name in self._queues:
                self._queues[name].clear()
                del self._queues[name]
                return True
            return False

    def list_queues(self) -> List[str]:
        """List all queue names"""
        with self._lock:
            return list(self._queues.keys())

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats for all queues"""
        with self._lock:
            return {
                name: queue.get_stats()
                for name, queue in self._queues.items()
            }

    def total_size(self) -> int:
        """Get total size across all queues"""
        with self._lock:
            return sum(q.size for q in self._queues.values())


# ==============================================================================
# Priority Calculator
# ==============================================================================

class PriorityCalculator:
    """
    Calculate task priority based on various factors.

    Factors considered:
    - Base priority from task type
    - Dependency depth (tasks with many dependents get higher priority)
    - Age (older pending tasks get priority boost)
    - User-specified priority override
    """

    # Base priorities by task type
    TYPE_PRIORITIES: ClassVar[Dict[str, int]] = {
        "retrieval_rag": Priority.NORMAL,
        "retrieval_nlq": Priority.NORMAL,
        "retrieval_graph": Priority.HIGH,
        "retrieval_api": Priority.HIGH,
        "synthesis": Priority.HIGH,
        "fact_check": Priority.NORMAL,
        "write_section": Priority.NORMAL,
        "write_report": Priority.HIGH,
        "review": Priority.HIGH,
    }

    @classmethod
    def calculate(
        cls,
        task_type: str,
        dependent_count: int = 0,
        age_minutes: float = 0,
        user_priority: Optional[int] = None,
        is_critical_path: bool = False
    ) -> int:
        """
        Calculate priority for a task.

        Args:
            task_type: Type of task
            dependent_count: Number of tasks depending on this one
            age_minutes: How long the task has been pending
            user_priority: User-specified priority override
            is_critical_path: Whether task is on critical execution path

        Returns:
            Priority level (1-10)
        """
        if user_priority is not None:
            return max(1, min(10, user_priority))

        # Start with base priority
        base = cls.TYPE_PRIORITIES.get(task_type, Priority.NORMAL)

        # Boost for tasks with dependents (they unblock other work)
        if dependent_count > 5:
            base = min(10, base + 2)
        elif dependent_count > 2:
            base = min(10, base + 1)

        # Boost for aged tasks (prevent starvation)
        if age_minutes > 60:
            base = min(10, base + 2)
        elif age_minutes > 30:
            base = min(10, base + 1)

        # Critical path tasks get maximum priority
        if is_critical_path:
            base = max(base, Priority.HIGHEST)

        return base


# ==============================================================================
# Service Factory
# ==============================================================================

_queue_manager: Optional[PriorityQueueManager] = None
_default_queue: Optional[PriorityTaskQueue] = None
_singleton_lock = threading.Lock()


def get_priority_queue_manager() -> PriorityQueueManager:
    """Get or create the queue manager singleton (thread-safe)"""
    global _queue_manager
    if _queue_manager is None:
        with _singleton_lock:
            if _queue_manager is None:
                _queue_manager = PriorityQueueManager()
    return _queue_manager


def get_priority_queue(name: str = "default") -> PriorityTaskQueue:
    """Get or create a named priority queue"""
    return get_priority_queue_manager().get_queue(name)


def get_default_priority_queue() -> PriorityTaskQueue:
    """Get the default priority queue (thread-safe).

    Uses the same instance as get_priority_queue("default") to ensure
    both accessors return the same queue.
    """
    global _default_queue
    if _default_queue is None:
        with _singleton_lock:
            if _default_queue is None:
                # Use the manager's queue to ensure consistency
                _default_queue = get_priority_queue_manager().get_queue("default")
    return _default_queue
