"""
Empire v7.3 - Task Scheduler Service

Manages scheduled, delayed, and recurring tasks using Celery Beat integration.
Provides API for scheduling tasks at specific times, with cron expressions,
and managing scheduled task lifecycle.

Features:
- One-time scheduled task execution
- Recurring tasks with cron expressions
- Task cancellation and rescheduling
- Schedule persistence in database
- Integration with existing task harness

Author: Claude Code
Date: 2025-01-24
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

import structlog
from supabase import Client
from celery import current_app
from celery.schedules import crontab

from app.core.supabase_client import get_supabase_client
from app.celery_app import celery_app

logger = structlog.get_logger(__name__)


# ==============================================================================
# Data Models
# ==============================================================================

class ScheduleType(str, Enum):
    """Type of schedule"""
    ONE_TIME = "one_time"
    RECURRING = "recurring"
    DELAYED = "delayed"


class ScheduleStatus(str, Enum):
    """Status of a scheduled task"""
    PENDING = "pending"
    ACTIVE = "active"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class ScheduledTask:
    """Represents a scheduled task"""
    schedule_id: str
    task_id: int
    job_id: int
    task_name: str
    schedule_type: ScheduleType
    status: ScheduleStatus = ScheduleStatus.PENDING

    # Timing
    run_at: Optional[datetime] = None
    cron_expression: Optional[str] = None
    delay_seconds: Optional[int] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    run_count: int = 0
    max_runs: Optional[int] = None

    # Task arguments
    task_args: List[Any] = field(default_factory=list)
    task_kwargs: Dict[str, Any] = field(default_factory=dict)

    # Error handling
    last_error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "schedule_id": self.schedule_id,
            "task_id": self.task_id,
            "job_id": self.job_id,
            "task_name": self.task_name,
            "schedule_type": self.schedule_type.value,
            "status": self.status.value,
            "run_at": self.run_at.isoformat() if self.run_at else None,
            "cron_expression": self.cron_expression,
            "delay_seconds": self.delay_seconds,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "run_count": self.run_count,
            "max_runs": self.max_runs,
            "task_args": json.dumps(self.task_args),
            "task_kwargs": json.dumps(self.task_kwargs),
            "last_error": self.last_error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledTask":
        """Create from dictionary"""
        return cls(
            schedule_id=data["schedule_id"],
            task_id=data["task_id"],
            job_id=data["job_id"],
            task_name=data["task_name"],
            schedule_type=ScheduleType(data["schedule_type"]),
            status=ScheduleStatus(data["status"]),
            run_at=datetime.fromisoformat(data["run_at"]) if data.get("run_at") else None,
            cron_expression=data.get("cron_expression"),
            delay_seconds=data.get("delay_seconds"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_run_at=datetime.fromisoformat(data["last_run_at"]) if data.get("last_run_at") else None,
            next_run_at=datetime.fromisoformat(data["next_run_at"]) if data.get("next_run_at") else None,
            run_count=data.get("run_count", 0),
            max_runs=data.get("max_runs"),
            task_args=json.loads(data.get("task_args", "[]")),
            task_kwargs=json.loads(data.get("task_kwargs", "{}")),
            last_error=data.get("last_error"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3)
        )


# ==============================================================================
# Cron Parser
# ==============================================================================

class CronParser:
    """Parse cron expressions into Celery crontab"""

    @staticmethod
    def parse(expression: str) -> crontab:
        """
        Parse a cron expression string into a Celery crontab.

        Standard cron format: minute hour day_of_month month day_of_week

        Examples:
            "0 0 * * *" -> daily at midnight
            "*/15 * * * *" -> every 15 minutes
            "0 9 * * 1-5" -> weekdays at 9am

        Args:
            expression: Cron expression string

        Returns:
            Celery crontab object
        """
        parts = expression.strip().split()

        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression: {expression}. "
                "Expected 5 parts: minute hour day_of_month month day_of_week"
            )

        minute, hour, day_of_month, month, day_of_week = parts

        return crontab(
            minute=minute,
            hour=hour,
            day_of_month=day_of_month,
            month_of_year=month,
            day_of_week=day_of_week
        )

    @staticmethod
    def calculate_next_run(expression: str, from_time: Optional[datetime] = None) -> datetime:
        """
        Calculate the next run time for a cron expression.

        Args:
            expression: Cron expression string
            from_time: Time to calculate from (default: now)

        Returns:
            Next run datetime
        """
        from croniter import croniter

        base_time = from_time or datetime.utcnow()
        cron = croniter(expression, base_time)
        return cron.get_next(datetime)


# ==============================================================================
# Task Scheduler Service
# ==============================================================================

class TaskScheduler:
    """
    Manages scheduled, delayed, and recurring tasks.

    Provides functionality for:
    - One-time scheduled task execution
    - Recurring tasks with cron expressions
    - Delayed task execution
    - Task cancellation and rescheduling
    - Schedule persistence and recovery
    """

    def __init__(self, supabase: Client):
        self.supabase = supabase
        self._celery_task_ids: Dict[str, str] = {}  # schedule_id -> celery_task_id

    # ==========================================================================
    # One-Time Scheduling
    # ==========================================================================

    def schedule_task(
        self,
        task_id: int,
        run_at: datetime,
        task_name: str = "app.tasks.research_tasks.execute_single_task",
        job_id: Optional[int] = None,
        task_args: Optional[List[Any]] = None,
        task_kwargs: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Schedule a task to run at a specific time.

        Args:
            task_id: The plan_tasks record ID
            run_at: When to execute the task
            task_name: Celery task name
            job_id: Optional job ID for grouping
            task_args: Task arguments
            task_kwargs: Task keyword arguments

        Returns:
            Schedule ID
        """
        schedule_id = str(uuid.uuid4())

        # Calculate ETA
        eta = run_at if run_at > datetime.utcnow() else datetime.utcnow() + timedelta(seconds=1)

        # Create scheduled task record
        scheduled = ScheduledTask(
            schedule_id=schedule_id,
            task_id=task_id,
            job_id=job_id or 0,
            task_name=task_name,
            schedule_type=ScheduleType.ONE_TIME,
            status=ScheduleStatus.PENDING,
            run_at=run_at,
            next_run_at=eta,
            task_args=task_args or [task_id],
            task_kwargs=task_kwargs or {}
        )

        # Store in database
        self._store_schedule(scheduled)

        # Schedule with Celery
        task = celery_app.send_task(
            task_name,
            args=scheduled.task_args,
            kwargs=scheduled.task_kwargs,
            eta=eta,
            task_id=f"scheduled_{schedule_id}"
        )

        self._celery_task_ids[schedule_id] = task.id

        logger.info(
            "Scheduled one-time task",
            schedule_id=schedule_id,
            task_id=task_id,
            run_at=run_at.isoformat()
        )

        return schedule_id

    def schedule_delayed(
        self,
        task_id: int,
        delay_seconds: int,
        task_name: str = "app.tasks.research_tasks.execute_single_task",
        job_id: Optional[int] = None,
        task_args: Optional[List[Any]] = None,
        task_kwargs: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Schedule a task to run after a delay.

        Args:
            task_id: The plan_tasks record ID
            delay_seconds: Delay before execution
            task_name: Celery task name
            job_id: Optional job ID
            task_args: Task arguments
            task_kwargs: Task keyword arguments

        Returns:
            Schedule ID
        """
        run_at = datetime.utcnow() + timedelta(seconds=delay_seconds)

        schedule_id = str(uuid.uuid4())

        scheduled = ScheduledTask(
            schedule_id=schedule_id,
            task_id=task_id,
            job_id=job_id or 0,
            task_name=task_name,
            schedule_type=ScheduleType.DELAYED,
            status=ScheduleStatus.PENDING,
            delay_seconds=delay_seconds,
            run_at=run_at,
            next_run_at=run_at,
            task_args=task_args or [task_id],
            task_kwargs=task_kwargs or {}
        )

        self._store_schedule(scheduled)

        task = celery_app.send_task(
            task_name,
            args=scheduled.task_args,
            kwargs=scheduled.task_kwargs,
            countdown=delay_seconds,
            task_id=f"scheduled_{schedule_id}"
        )

        self._celery_task_ids[schedule_id] = task.id

        logger.info(
            "Scheduled delayed task",
            schedule_id=schedule_id,
            task_id=task_id,
            delay_seconds=delay_seconds
        )

        return schedule_id

    # ==========================================================================
    # Recurring Scheduling
    # ==========================================================================

    def schedule_recurring(
        self,
        task_id: int,
        cron_expression: str,
        task_name: str = "app.tasks.research_tasks.execute_single_task",
        job_id: Optional[int] = None,
        task_args: Optional[List[Any]] = None,
        task_kwargs: Optional[Dict[str, Any]] = None,
        max_runs: Optional[int] = None
    ) -> str:
        """
        Schedule a recurring task using cron expression.

        Args:
            task_id: The plan_tasks record ID
            cron_expression: Cron expression (e.g., "0 0 * * *" for daily)
            task_name: Celery task name
            job_id: Optional job ID
            task_args: Task arguments
            task_kwargs: Task keyword arguments
            max_runs: Maximum number of runs (None for unlimited)

        Returns:
            Schedule ID
        """
        schedule_id = str(uuid.uuid4())

        # Validate and calculate next run
        try:
            CronParser.parse(cron_expression)
            next_run = CronParser.calculate_next_run(cron_expression)
        except Exception as e:
            raise ValueError(f"Invalid cron expression: {e}")

        scheduled = ScheduledTask(
            schedule_id=schedule_id,
            task_id=task_id,
            job_id=job_id or 0,
            task_name=task_name,
            schedule_type=ScheduleType.RECURRING,
            status=ScheduleStatus.ACTIVE,
            cron_expression=cron_expression,
            next_run_at=next_run,
            max_runs=max_runs,
            task_args=task_args or [task_id],
            task_kwargs=task_kwargs or {}
        )

        self._store_schedule(scheduled)

        # Register with Celery Beat dynamically
        self._register_beat_schedule(scheduled)

        logger.info(
            "Scheduled recurring task",
            schedule_id=schedule_id,
            task_id=task_id,
            cron_expression=cron_expression,
            next_run=next_run.isoformat()
        )

        return schedule_id

    def _register_beat_schedule(self, scheduled: ScheduledTask) -> None:
        """Register a recurring schedule with Celery Beat"""
        if not scheduled.cron_expression:
            return

        schedule_name = f"scheduled_{scheduled.schedule_id}"
        cron = CronParser.parse(scheduled.cron_expression)

        # Add to beat schedule dynamically
        celery_app.conf.beat_schedule[schedule_name] = {
            'task': scheduled.task_name,
            'schedule': cron,
            'args': scheduled.task_args,
            'kwargs': scheduled.task_kwargs,
            'options': {
                'task_id': schedule_name,
            }
        }

        logger.debug(f"Registered beat schedule: {schedule_name}")

    # ==========================================================================
    # Schedule Management
    # ==========================================================================

    def cancel_scheduled(self, schedule_id: str) -> bool:
        """
        Cancel a scheduled task.

        Args:
            schedule_id: The schedule ID to cancel

        Returns:
            True if cancelled successfully
        """
        try:
            # Update database status
            self.supabase.table("scheduled_tasks").update({
                "status": ScheduleStatus.CANCELLED.value,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("schedule_id", schedule_id).execute()

            # Revoke Celery task
            celery_task_id = self._celery_task_ids.get(schedule_id) or f"scheduled_{schedule_id}"
            current_app.control.revoke(celery_task_id, terminate=True)

            # Remove from beat schedule if recurring
            schedule_name = f"scheduled_{schedule_id}"
            if schedule_name in celery_app.conf.beat_schedule:
                del celery_app.conf.beat_schedule[schedule_name]

            logger.info("Cancelled scheduled task", schedule_id=schedule_id)
            return True

        except Exception as e:
            logger.error(f"Failed to cancel schedule: {e}", schedule_id=schedule_id)
            return False

    def pause_recurring(self, schedule_id: str) -> bool:
        """Pause a recurring schedule"""
        try:
            self.supabase.table("scheduled_tasks").update({
                "status": ScheduleStatus.PAUSED.value,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("schedule_id", schedule_id).execute()

            # Remove from beat schedule
            schedule_name = f"scheduled_{schedule_id}"
            if schedule_name in celery_app.conf.beat_schedule:
                del celery_app.conf.beat_schedule[schedule_name]

            logger.info("Paused recurring schedule", schedule_id=schedule_id)
            return True

        except Exception as e:
            logger.error(f"Failed to pause schedule: {e}")
            return False

    def resume_recurring(self, schedule_id: str) -> bool:
        """Resume a paused recurring schedule"""
        try:
            result = self.supabase.table("scheduled_tasks").select("*").eq(
                "schedule_id", schedule_id
            ).single().execute()

            if not result.data:
                return False

            scheduled = ScheduledTask.from_dict(result.data)

            if scheduled.schedule_type != ScheduleType.RECURRING:
                return False

            # Update status
            self.supabase.table("scheduled_tasks").update({
                "status": ScheduleStatus.ACTIVE.value,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("schedule_id", schedule_id).execute()

            # Re-register with beat
            self._register_beat_schedule(scheduled)

            logger.info("Resumed recurring schedule", schedule_id=schedule_id)
            return True

        except Exception as e:
            logger.error(f"Failed to resume schedule: {e}")
            return False

    def reschedule(
        self,
        schedule_id: str,
        new_run_at: Optional[datetime] = None,
        new_cron: Optional[str] = None
    ) -> bool:
        """
        Reschedule a task to a new time or cron expression.

        Args:
            schedule_id: The schedule to modify
            new_run_at: New run time (for one-time)
            new_cron: New cron expression (for recurring)

        Returns:
            True if rescheduled successfully
        """
        try:
            result = self.supabase.table("scheduled_tasks").select("*").eq(
                "schedule_id", schedule_id
            ).single().execute()

            if not result.data:
                return False

            scheduled = ScheduledTask.from_dict(result.data)

            # Cancel existing
            self.cancel_scheduled(schedule_id)

            # Create new schedule
            if new_run_at and scheduled.schedule_type == ScheduleType.ONE_TIME:
                self.schedule_task(
                    task_id=scheduled.task_id,
                    run_at=new_run_at,
                    task_name=scheduled.task_name,
                    job_id=scheduled.job_id,
                    task_args=scheduled.task_args,
                    task_kwargs=scheduled.task_kwargs
                )
            elif new_cron and scheduled.schedule_type == ScheduleType.RECURRING:
                self.schedule_recurring(
                    task_id=scheduled.task_id,
                    cron_expression=new_cron,
                    task_name=scheduled.task_name,
                    job_id=scheduled.job_id,
                    task_args=scheduled.task_args,
                    task_kwargs=scheduled.task_kwargs,
                    max_runs=scheduled.max_runs
                )

            return True

        except Exception as e:
            logger.error(f"Failed to reschedule: {e}")
            return False

    # ==========================================================================
    # Query Methods
    # ==========================================================================

    def list_scheduled(
        self,
        job_id: Optional[int] = None,
        status: Optional[ScheduleStatus] = None,
        schedule_type: Optional[ScheduleType] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[ScheduledTask]:
        """
        List scheduled tasks with optional filters.

        Args:
            job_id: Filter by job ID
            status: Filter by status
            schedule_type: Filter by schedule type
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of scheduled tasks
        """
        query = self.supabase.table("scheduled_tasks").select("*")

        if job_id is not None:
            query = query.eq("job_id", job_id)
        if status:
            query = query.eq("status", status.value)
        if schedule_type:
            query = query.eq("schedule_type", schedule_type.value)

        query = query.order("created_at", desc=True)
        query = query.range(offset, offset + limit - 1)

        result = query.execute()

        return [ScheduledTask.from_dict(row) for row in (result.data or [])]

    def get_schedule(self, schedule_id: str) -> Optional[ScheduledTask]:
        """Get a specific schedule by ID"""
        result = self.supabase.table("scheduled_tasks").select("*").eq(
            "schedule_id", schedule_id
        ).single().execute()

        if result.data:
            return ScheduledTask.from_dict(result.data)
        return None

    def get_upcoming(
        self,
        job_id: Optional[int] = None,
        hours: int = 24
    ) -> List[ScheduledTask]:
        """Get tasks scheduled to run in the next N hours"""
        cutoff = datetime.utcnow() + timedelta(hours=hours)

        query = self.supabase.table("scheduled_tasks").select("*").lt(
            "next_run_at", cutoff.isoformat()
        ).in_("status", [ScheduleStatus.PENDING.value, ScheduleStatus.ACTIVE.value])

        if job_id is not None:
            query = query.eq("job_id", job_id)

        result = query.order("next_run_at").execute()

        return [ScheduledTask.from_dict(row) for row in (result.data or [])]

    # ==========================================================================
    # Internal Methods
    # ==========================================================================

    def _store_schedule(self, scheduled: ScheduledTask) -> None:
        """Store a scheduled task in the database"""
        self.supabase.table("scheduled_tasks").insert(
            scheduled.to_dict()
        ).execute()

    def update_schedule_run(
        self,
        schedule_id: str,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """
        Update schedule after a run (called by task callback).

        Args:
            schedule_id: The schedule ID
            success: Whether the run was successful
            error: Error message if failed
        """
        try:
            result = self.supabase.table("scheduled_tasks").select("*").eq(
                "schedule_id", schedule_id
            ).single().execute()

            if not result.data:
                return

            scheduled = ScheduledTask.from_dict(result.data)
            now = datetime.utcnow()

            update_data = {
                "last_run_at": now.isoformat(),
                "run_count": scheduled.run_count + 1,
                "updated_at": now.isoformat()
            }

            if not success:
                update_data["last_error"] = error
                update_data["retry_count"] = scheduled.retry_count + 1

            # Handle recurring schedule next run
            if scheduled.schedule_type == ScheduleType.RECURRING:
                if scheduled.cron_expression:
                    next_run = CronParser.calculate_next_run(scheduled.cron_expression, now)
                    update_data["next_run_at"] = next_run.isoformat()

                # Check max runs
                if scheduled.max_runs and scheduled.run_count + 1 >= scheduled.max_runs:
                    update_data["status"] = ScheduleStatus.EXECUTED.value
                    # Remove from beat schedule
                    schedule_name = f"scheduled_{schedule_id}"
                    if schedule_name in celery_app.conf.beat_schedule:
                        del celery_app.conf.beat_schedule[schedule_name]
            else:
                # One-time task is now executed
                update_data["status"] = ScheduleStatus.EXECUTED.value if success else ScheduleStatus.FAILED.value

            self.supabase.table("scheduled_tasks").update(update_data).eq(
                "schedule_id", schedule_id
            ).execute()

        except Exception as e:
            logger.error(f"Failed to update schedule run: {e}")

    def recover_schedules(self) -> int:
        """
        Recover schedules from database on startup.

        Registers all active recurring schedules with Celery Beat
        and reschedules any pending one-time tasks that were missed.

        Returns:
            Number of schedules recovered
        """
        recovered = 0

        # Get all active recurring schedules
        result = self.supabase.table("scheduled_tasks").select("*").eq(
            "status", ScheduleStatus.ACTIVE.value
        ).eq("schedule_type", ScheduleType.RECURRING.value).execute()

        for row in (result.data or []):
            try:
                scheduled = ScheduledTask.from_dict(row)
                self._register_beat_schedule(scheduled)
                recovered += 1
            except Exception as e:
                logger.error(f"Failed to recover schedule: {e}")

        # Get pending one-time tasks that haven't run
        result = self.supabase.table("scheduled_tasks").select("*").eq(
            "status", ScheduleStatus.PENDING.value
        ).in_("schedule_type", [ScheduleType.ONE_TIME.value, ScheduleType.DELAYED.value]).execute()

        now = datetime.utcnow()
        for row in (result.data or []):
            try:
                scheduled = ScheduledTask.from_dict(row)

                # If task should have run, execute immediately
                if scheduled.next_run_at and scheduled.next_run_at <= now:
                    celery_app.send_task(
                        scheduled.task_name,
                        args=scheduled.task_args,
                        kwargs=scheduled.task_kwargs,
                        task_id=f"scheduled_{scheduled.schedule_id}"
                    )
                else:
                    # Re-schedule for future
                    eta = scheduled.next_run_at or (now + timedelta(seconds=60))
                    celery_app.send_task(
                        scheduled.task_name,
                        args=scheduled.task_args,
                        kwargs=scheduled.task_kwargs,
                        eta=eta,
                        task_id=f"scheduled_{scheduled.schedule_id}"
                    )

                recovered += 1
            except Exception as e:
                logger.error(f"Failed to recover one-time schedule: {e}")

        logger.info("Recovered schedules", count=recovered)
        return recovered


# ==============================================================================
# Service Factory
# ==============================================================================

_scheduler_instance: Optional[TaskScheduler] = None


def get_task_scheduler() -> TaskScheduler:
    """Get or create task scheduler singleton.

    On first call, recovers persisted schedules from the database.
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        supabase = get_supabase_client()
        _scheduler_instance = TaskScheduler(supabase)
        # Recover persisted schedules on startup
        try:
            recovered = _scheduler_instance.recover_schedules()
            if recovered > 0:
                logger.info("schedule_recovery_complete", recovered_count=recovered)
        except Exception:
            logger.exception("Failed to recover schedules on startup")
    return _scheduler_instance
