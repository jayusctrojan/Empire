"""
Empire v7.3 - Progress Emitter Mixin

Provides mid-task progress update capabilities for task executors.
Enables real-time progress tracking during long-running operations.

Features:
- Progress event emission via WebSocket/SSE
- Step-based progress tracking
- Estimated time remaining calculations
- Sub-task progress aggregation
- Prometheus metrics integration
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ProgressStep:
    """Represents a single step in task progress."""
    name: str
    weight: float = 1.0  # Relative weight for progress calculation
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, in_progress, completed, failed, skipped
    message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate step duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class ProgressState:
    """Tracks the overall progress state of a task."""
    task_id: str
    total_steps: int
    current_step: int = 0
    current_step_name: str = ""
    progress_percent: float = 0.0
    steps: List[ProgressStep] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    estimated_remaining_seconds: Optional[float] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for transmission."""
        return {
            "task_id": self.task_id,
            "total_steps": self.total_steps,
            "current_step": self.current_step,
            "current_step_name": self.current_step_name,
            "progress_percent": round(self.progress_percent, 2),
            "started_at": self.started_at.isoformat(),
            "estimated_remaining_seconds": self.estimated_remaining_seconds,
            "message": self.message,
            "metadata": self.metadata,
            "steps": [
                {
                    "name": s.name,
                    "status": s.status,
                    "message": s.message,
                    "duration_seconds": s.duration_seconds
                }
                for s in self.steps
            ]
        }


class ProgressEmitter:
    """
    Mixin class for task executors to emit mid-task progress updates.

    Usage:
        class MyExecutor(TaskExecutor, ProgressEmitter):
            async def execute(self, task):
                self.init_progress(task["id"], steps=["fetch", "process", "store"])

                self.start_step("fetch")
                data = await self.fetch_data()
                self.complete_step("fetch", message="Fetched 100 records")

                self.start_step("process")
                await self.emit_progress(message="Processing records...")
                results = await self.process_data(data)
                self.complete_step("process")

                self.start_step("store")
                await self.store_results(results)
                self.complete_step("store")

                return {"success": True}
    """

    def __init__(self):
        self._progress_state: Optional[ProgressState] = None
        self._progress_callbacks: List[Callable[[ProgressState], None]] = []
        self._broadcaster = None

    def init_progress(
        self,
        task_id: str,
        steps: Optional[List[str]] = None,
        step_weights: Optional[Dict[str, float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize progress tracking for a task.

        Args:
            task_id: Unique identifier for the task
            steps: List of step names in execution order
            step_weights: Optional weights for each step (for progress calculation)
            metadata: Optional metadata to include with progress updates
        """
        steps = steps or ["processing"]
        step_weights = step_weights or {}

        progress_steps = [
            ProgressStep(
                name=name,
                weight=step_weights.get(name, 1.0)
            )
            for name in steps
        ]

        self._progress_state = ProgressState(
            task_id=task_id,
            total_steps=len(progress_steps),
            steps=progress_steps,
            metadata=metadata or {}
        )

        logger.debug(
            "progress_initialized",
            task_id=task_id,
            total_steps=len(progress_steps)
        )

    def start_step(
        self,
        step_name: str,
        message: Optional[str] = None
    ) -> None:
        """
        Mark a step as started.

        Args:
            step_name: Name of the step to start
            message: Optional status message
        """
        if not self._progress_state:
            return

        for i, step in enumerate(self._progress_state.steps):
            if step.name == step_name:
                step.started_at = datetime.utcnow()
                step.status = "in_progress"
                step.message = message

                self._progress_state.current_step = i + 1
                self._progress_state.current_step_name = step_name
                self._update_progress_percent()

                if message:
                    self._progress_state.message = message

                self._notify_progress()
                break

    def complete_step(
        self,
        step_name: str,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark a step as completed.

        Args:
            step_name: Name of the step to complete
            message: Optional completion message
            metadata: Optional metadata for the step
        """
        if not self._progress_state:
            return

        for step in self._progress_state.steps:
            if step.name == step_name:
                step.completed_at = datetime.utcnow()
                step.status = "completed"
                if message:
                    step.message = message
                if metadata:
                    step.metadata.update(metadata)

                self._update_progress_percent()
                self._update_time_estimate()

                if message:
                    self._progress_state.message = message

                self._notify_progress()
                break

    def fail_step(
        self,
        step_name: str,
        error_message: str
    ) -> None:
        """
        Mark a step as failed.

        Args:
            step_name: Name of the step that failed
            error_message: Error message
        """
        if not self._progress_state:
            return

        for step in self._progress_state.steps:
            if step.name == step_name:
                step.completed_at = datetime.utcnow()
                step.status = "failed"
                step.message = error_message

                self._progress_state.message = f"Failed: {error_message}"
                self._notify_progress()
                break

    def skip_step(
        self,
        step_name: str,
        reason: str = "Skipped"
    ) -> None:
        """
        Mark a step as skipped.

        Args:
            step_name: Name of the step to skip
            reason: Reason for skipping
        """
        if not self._progress_state:
            return

        for step in self._progress_state.steps:
            if step.name == step_name:
                step.status = "skipped"
                step.message = reason

                self._update_progress_percent()
                self._notify_progress()
                break

    async def emit_progress(
        self,
        current: Optional[int] = None,
        total: Optional[int] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Emit a progress update during step execution.

        Args:
            current: Current progress value (e.g., items processed)
            total: Total expected value
            message: Status message
            metadata: Additional metadata
        """
        if not self._progress_state:
            return

        if current is not None and total is not None and total > 0:
            # Update sub-step progress
            sub_progress = (current / total) * 100
            self._progress_state.metadata["sub_progress"] = {
                "current": current,
                "total": total,
                "percent": round(sub_progress, 2)
            }

        if message:
            self._progress_state.message = message

        if metadata:
            self._progress_state.metadata.update(metadata)

        await self._broadcast_progress()

    def _update_progress_percent(self) -> None:
        """Calculate overall progress percentage."""
        if not self._progress_state:
            return

        total_weight = sum(s.weight for s in self._progress_state.steps)
        completed_weight = sum(
            s.weight for s in self._progress_state.steps
            if s.status in ("completed", "skipped")
        )

        # Add partial weight for in-progress step
        for step in self._progress_state.steps:
            if step.status == "in_progress":
                # Assume 50% complete for in-progress step
                completed_weight += step.weight * 0.5
                break

        self._progress_state.progress_percent = (
            (completed_weight / total_weight) * 100
            if total_weight > 0 else 0
        )

    def _update_time_estimate(self) -> None:
        """Update estimated remaining time based on completed steps."""
        if not self._progress_state:
            return

        completed_steps = [
            s for s in self._progress_state.steps
            if s.status == "completed" and s.duration_seconds is not None
        ]

        if not completed_steps:
            return

        # Calculate average time per unit weight
        total_duration = sum(s.duration_seconds for s in completed_steps)
        total_weight = sum(s.weight for s in completed_steps)

        if total_weight == 0:
            return

        time_per_weight = total_duration / total_weight

        # Calculate remaining weight
        remaining_weight = sum(
            s.weight for s in self._progress_state.steps
            if s.status in ("pending", "in_progress")
        )

        self._progress_state.estimated_remaining_seconds = (
            time_per_weight * remaining_weight
        )

    def _notify_progress(self) -> None:
        """Notify registered callbacks of progress update."""
        if not self._progress_state:
            return

        for callback in self._progress_callbacks:
            try:
                callback(self._progress_state)
            except Exception as e:
                logger.error("progress_callback_error", error=str(e))

    async def _broadcast_progress(self) -> None:
        """Broadcast progress via WebSocket/SSE."""
        if not self._progress_state:
            return

        try:
            # Lazy load broadcaster
            if self._broadcaster is None:
                try:
                    from app.services.status_broadcaster import get_status_broadcaster
                    self._broadcaster = await get_status_broadcaster()
                except ImportError:
                    self._broadcaster = False  # Mark as unavailable

            if self._broadcaster and self._broadcaster is not False:
                await self._broadcaster.broadcast_progress(
                    task_id=self._progress_state.task_id,
                    current=self._progress_state.current_step,
                    total=self._progress_state.total_steps,
                    message=self._progress_state.message,
                    metadata=self._progress_state.to_dict()
                )
        except Exception as e:
            logger.warning("progress_broadcast_error", error=str(e))

    def add_progress_callback(
        self,
        callback: Callable[[ProgressState], None]
    ) -> None:
        """Add a callback for progress updates."""
        self._progress_callbacks.append(callback)

    def remove_progress_callback(
        self,
        callback: Callable[[ProgressState], None]
    ) -> None:
        """Remove a progress callback."""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)

    def get_progress_state(self) -> Optional[Dict[str, Any]]:
        """Get current progress state as dictionary."""
        if self._progress_state:
            return self._progress_state.to_dict()
        return None


class BatchProgressTracker:
    """
    Tracks progress across multiple tasks in a batch.

    Useful for tracking overall batch progress when processing
    multiple items concurrently.
    """

    def __init__(self, batch_id: str, total_items: int):
        self.batch_id = batch_id
        self.total_items = total_items
        self.completed_items = 0
        self.failed_items = 0
        self.started_at = datetime.utcnow()
        self._item_progress: Dict[str, ProgressState] = {}
        self._lock = asyncio.Lock()

    async def register_item(
        self,
        item_id: str,
        steps: List[str]
    ) -> ProgressEmitter:
        """Register an item for tracking and return its emitter."""
        emitter = ProgressEmitter()
        emitter.init_progress(item_id, steps)

        async with self._lock:
            if emitter._progress_state:
                self._item_progress[item_id] = emitter._progress_state

        return emitter

    async def mark_item_complete(self, item_id: str) -> None:
        """Mark an item as completed."""
        async with self._lock:
            if item_id in self._item_progress:
                self.completed_items += 1

    async def mark_item_failed(self, item_id: str) -> None:
        """Mark an item as failed."""
        async with self._lock:
            if item_id in self._item_progress:
                self.failed_items += 1

    def get_batch_progress(self) -> Dict[str, Any]:
        """Get overall batch progress."""
        processed = self.completed_items + self.failed_items
        progress_percent = (processed / self.total_items * 100) if self.total_items > 0 else 0

        elapsed = (datetime.utcnow() - self.started_at).total_seconds()

        # Estimate remaining time
        if processed > 0 and processed < self.total_items:
            time_per_item = elapsed / processed
            remaining_items = self.total_items - processed
            estimated_remaining = time_per_item * remaining_items
        else:
            estimated_remaining = None

        return {
            "batch_id": self.batch_id,
            "total_items": self.total_items,
            "completed_items": self.completed_items,
            "failed_items": self.failed_items,
            "progress_percent": round(progress_percent, 2),
            "elapsed_seconds": round(elapsed, 2),
            "estimated_remaining_seconds": (
                round(estimated_remaining, 2)
                if estimated_remaining else None
            ),
            "success_rate": (
                round(self.completed_items / processed * 100, 2)
                if processed > 0 else 0
            )
        }
