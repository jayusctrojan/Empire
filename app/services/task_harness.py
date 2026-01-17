"""
Empire v7.3 - Task Harness Service (Task 94)

Core task execution engine that processes research tasks according to the plan.
Handles task routing, execution, status updates, and completion detection.

Author: Claude Code
Date: 2025-01-10
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from abc import ABC, abstractmethod

import structlog
from supabase import Client

from app.core.supabase_client import get_supabase_client
from app.models.research_project import JobStatus, TaskStatus, TaskType

logger = structlog.get_logger(__name__)


# ==============================================================================
# Task Executor Interface
# ==============================================================================

class TaskExecutor(ABC):
    """Abstract base class for task executors"""

    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the task and return results.

        Args:
            task: Task data from plan_tasks table

        Returns:
            Dict containing:
                - success: bool
                - summary: str (brief result summary)
                - data: Dict (structured result data)
                - artifacts: List[Dict] (artifacts to store)
        """
        pass

    @property
    @abstractmethod
    def supported_types(self) -> List[str]:
        """Return list of task types this executor supports"""
        pass


# ==============================================================================
# Task Harness Service
# ==============================================================================

class TaskHarnessService:
    """
    Core task execution engine for research projects.

    Responsibilities:
    - Get next tasks ready for execution (dependencies satisfied)
    - Route tasks to appropriate executors
    - Update task status and store results
    - Detect job completion
    - Store artifacts from task execution
    """

    def __init__(self, supabase: Client):
        self.supabase = supabase
        self._executors: Dict[str, TaskExecutor] = {}

    def register_executor(self, executor: TaskExecutor) -> None:
        """Register a task executor for specific task types"""
        for task_type in executor.supported_types:
            self._executors[task_type] = executor
            logger.info("Registered executor", task_type=task_type, executor=type(executor).__name__)

    # ==========================================================================
    # Task Selection
    # ==========================================================================

    def get_next_tasks(self, job_id: int, limit: int = 1) -> List[Dict[str, Any]]:
        """
        Get tasks ready for execution (all dependencies satisfied).

        Args:
            job_id: The research job ID
            limit: Maximum number of tasks to return

        Returns:
            List of tasks ready for execution
        """
        # Get all tasks for this job
        result = self.supabase.table("plan_tasks").select("*").eq(
            "job_id", job_id
        ).order("sequence_order").execute()

        tasks = result.data or []

        if not tasks:
            return []

        # Build completed task keys set
        completed_keys = {
            t["task_key"] for t in tasks
            if t["status"] == TaskStatus.COMPLETE.value
        }

        # Find tasks ready for execution
        ready_tasks = []
        for task in tasks:
            if task["status"] != TaskStatus.PENDING.value:
                continue

            # Check if all dependencies are satisfied
            depends_on = task.get("depends_on") or []
            if all(dep in completed_keys for dep in depends_on):
                ready_tasks.append(task)
                if len(ready_tasks) >= limit:
                    break

        logger.info(
            "Found ready tasks",
            job_id=job_id,
            ready_count=len(ready_tasks),
            total_pending=sum(1 for t in tasks if t["status"] == TaskStatus.PENDING.value)
        )

        return ready_tasks

    def get_tasks_by_wave(self, job_id: int) -> List[List[Dict[str, Any]]]:
        """
        Organize all tasks into execution waves for parallel processing.

        Tasks in the same wave have no dependencies on each other.

        Args:
            job_id: The research job ID

        Returns:
            List of waves, each wave is a list of tasks
        """
        result = self.supabase.table("plan_tasks").select("*").eq(
            "job_id", job_id
        ).order("sequence_order").execute()

        tasks = result.data or []
        if not tasks:
            return []

        task_map = {t["task_key"]: t for t in tasks}
        completed: set = set()
        waves: List[List[Dict]] = []

        remaining = {t["task_key"] for t in tasks}

        while remaining:
            wave = []
            for task_key in list(remaining):
                task = task_map[task_key]
                deps = set(task.get("depends_on") or []) & set(task_map.keys())
                if deps.issubset(completed):
                    wave.append(task)

            if not wave:
                # Circular dependency or all remaining have unmet deps
                logger.warning(
                    "Cannot resolve dependencies for remaining tasks",
                    remaining=list(remaining)
                )
                # Add remaining tasks as final wave
                wave = [task_map[k] for k in remaining]

            waves.append(wave)
            completed.update(t["task_key"] for t in wave)
            remaining -= {t["task_key"] for t in wave}

        return waves

    # ==========================================================================
    # Task Execution
    # ==========================================================================

    async def execute_task(self, task_id: int) -> Dict[str, Any]:
        """
        Execute a single task based on its type.

        Args:
            task_id: The plan_tasks record ID

        Returns:
            Dict with execution result
        """
        # Get task details
        result = self.supabase.table("plan_tasks").select("*").eq(
            "id", task_id
        ).single().execute()

        if not result.data:
            raise ValueError(f"Task {task_id} not found")

        task = result.data
        task_type = task["task_type"]

        logger.info(
            "Executing task",
            task_id=task_id,
            task_type=task_type,
            task_key=task["task_key"]
        )

        # Update status to running
        self.update_task_status(task_id, TaskStatus.RUNNING)

        # Record task start in performance monitor
        try:
            from app.services.performance_monitor import get_performance_monitor
            monitor = get_performance_monitor()
            created_at = None
            if task.get("created_at"):
                from datetime import datetime
                created_at = datetime.fromisoformat(
                    task["created_at"].replace("Z", "+00:00")
                )
            monitor.record_task_start(
                task_id=task_id,
                task_type=task_type,
                job_id=task["job_id"],
                created_at=created_at
            )
        except Exception as e:
            logger.debug(f"Performance monitor task start failed: {e}")

        try:
            # Route to appropriate executor
            execution_result = await self.execute_task_by_type(task)

            if execution_result.get("success"):
                # Store artifacts if any
                artifacts = execution_result.get("artifacts", [])
                artifact_count = await self._store_artifacts(task, artifacts)

                # Record quality scores for artifacts
                try:
                    from app.services.performance_monitor import get_performance_monitor
                    monitor = get_performance_monitor()

                    # Record task completion
                    monitor.record_task_complete(
                        task_id=task_id,
                        task_type=task_type,
                        job_id=task["job_id"],
                        success=True
                    )

                    # Record quality gate pass
                    monitor.record_quality_gate_result(
                        job_id=task["job_id"],
                        gate_type=task_type,
                        passed=True,
                        message="Task completed successfully"
                    )
                except Exception as e:
                    logger.debug(f"Performance monitor task complete failed: {e}")

                # Update task as complete
                self.update_task_status(
                    task_id,
                    TaskStatus.COMPLETE,
                    result_data={
                        "summary": execution_result.get("summary", ""),
                        "data": execution_result.get("data", {}),
                        "artifact_count": artifact_count
                    }
                )

                return {
                    "success": True,
                    "task_id": task_id,
                    "task_key": task["task_key"],
                    "summary": execution_result.get("summary"),
                    "artifact_count": artifact_count
                }
            else:
                raise Exception(execution_result.get("error", "Task execution failed"))

        except Exception as e:
            logger.error(
                "Task execution failed",
                task_id=task_id,
                error=str(e)
            )

            # Record failure in performance monitor
            try:
                from app.services.performance_monitor import get_performance_monitor
                monitor = get_performance_monitor()

                monitor.record_task_complete(
                    task_id=task_id,
                    task_type=task_type,
                    job_id=task["job_id"],
                    success=False
                )

                monitor.record_quality_gate_result(
                    job_id=task["job_id"],
                    gate_type=task_type,
                    passed=False,
                    message=str(e)
                )
            except Exception:
                pass

            self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                error_message=str(e)
            )
            return {
                "success": False,
                "task_id": task_id,
                "task_key": task["task_key"],
                "error": str(e)
            }

    async def execute_task_by_type(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route task to appropriate executor based on task_type.

        Args:
            task: Task data from plan_tasks table

        Returns:
            Execution result from the executor
        """
        task_type = task["task_type"]

        # Check for registered executor
        if task_type in self._executors:
            executor = self._executors[task_type]
            return await executor.execute(task)

        # Fallback: use default handling based on task type category
        if task_type.startswith("retrieval_"):
            return await self._execute_retrieval_task(task)
        elif task_type == TaskType.SYNTHESIS.value:
            return await self._execute_synthesis_task(task)
        elif task_type == TaskType.FACT_CHECK.value:
            return await self._execute_fact_check_task(task)
        elif task_type in (TaskType.WRITE_SECTION.value, TaskType.WRITE_REPORT.value):
            return await self._execute_write_task(task)
        elif task_type == TaskType.REVIEW.value:
            return await self._execute_review_task(task)
        else:
            logger.warning(f"No executor for task type: {task_type}")
            return await self._execute_generic_task(task)

    # ==========================================================================
    # Task Handlers - Integrated with Task 95-98 Executors
    # ==========================================================================

    async def _execute_retrieval_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute retrieval task (RAG, NLQ, Graph, API) using RetrievalExecutor.
        Implemented in Task 95.
        """
        from app.services.task_executors.retrieval_executor import RetrievalExecutor

        logger.info("Executing retrieval task", task_type=task["task_type"])
        executor = RetrievalExecutor()
        return await executor.execute(task)

    async def _execute_synthesis_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute synthesis task - combine findings using SynthesisExecutor.
        Implemented in Task 97.
        """
        from app.services.task_executors.synthesis_executor import SynthesisExecutor

        logger.info("Executing synthesis task", task_key=task["task_key"])
        executor = SynthesisExecutor()
        return await executor.execute(task)

    async def _execute_fact_check_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute fact checking task using SynthesisExecutor.
        Implemented in Task 97.
        """
        from app.services.task_executors.synthesis_executor import SynthesisExecutor

        logger.info("Executing fact check task", task_key=task["task_key"])
        executor = SynthesisExecutor()
        return await executor.execute(task)

    async def _execute_write_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute writing task (section or full report) using ReportExecutor.
        Implemented in Task 98.
        """
        from app.services.task_executors.report_executor import ReportExecutor

        logger.info("Executing write task", task_type=task["task_type"])
        executor = ReportExecutor()
        return await executor.execute(task)

    async def _execute_review_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute review/QA task using ReportExecutor.
        Implemented in Task 98.
        """
        from app.services.task_executors.report_executor import ReportExecutor

        logger.info("Executing review task", task_key=task["task_key"])
        executor = ReportExecutor()
        return await executor.execute(task)

    async def _execute_generic_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute generic task with basic handling"""
        logger.info("Executing generic task", task_type=task["task_type"])
        return {
            "success": True,
            "summary": f"Completed: {task['task_title']}",
            "data": {"placeholder": True},
            "artifacts": []
        }

    # ==========================================================================
    # Status Management
    # ==========================================================================

    def update_task_status(
        self,
        task_id: int,
        status: TaskStatus,
        result_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        Update task status in database.

        Args:
            task_id: The plan_tasks record ID
            status: New status
            result_data: Optional result data (for completed tasks)
            error_message: Optional error message (for failed tasks)
        """
        update_data: Dict[str, Any] = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat()
        }

        if status == TaskStatus.RUNNING:
            update_data["started_at"] = datetime.utcnow().isoformat()
        elif status in (TaskStatus.COMPLETE, TaskStatus.FAILED):
            update_data["completed_at"] = datetime.utcnow().isoformat()

        if result_data:
            update_data["result_summary"] = result_data.get("summary", "")
            update_data["result_data"] = result_data.get("data", {})
            update_data["artifacts_count"] = result_data.get("artifact_count", 0)

        if error_message:
            update_data["error_message"] = error_message

        self.supabase.table("plan_tasks").update(update_data).eq("id", task_id).execute()

        logger.info(
            "Task status updated",
            task_id=task_id,
            status=status.value
        )

    def update_job_progress(self, job_id: int) -> Dict[str, Any]:
        """
        Update job progress based on task completion.

        Args:
            job_id: The research job ID

        Returns:
            Dict with progress info
        """
        result = self.supabase.table("plan_tasks").select(
            "id, status"
        ).eq("job_id", job_id).execute()

        tasks = result.data or []
        if not tasks:
            return {"total": 0, "completed": 0, "progress": 0}

        total = len(tasks)
        completed = sum(1 for t in tasks if t["status"] == TaskStatus.COMPLETE.value)
        failed = sum(1 for t in tasks if t["status"] == TaskStatus.FAILED.value)
        progress = (completed / total) * 100

        self.supabase.table("research_jobs").update({
            "completed_tasks": completed,
            "progress_percentage": round(progress, 2),
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", job_id).execute()

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "progress": round(progress, 2)
        }

    # ==========================================================================
    # Job Completion
    # ==========================================================================

    def check_job_completion(self, job_id: int) -> Dict[str, Any]:
        """
        Check if all tasks for a job are complete.

        Args:
            job_id: The research job ID

        Returns:
            Dict with completion status:
                - is_complete: bool
                - all_succeeded: bool
                - failed_count: int
                - pending_count: int
        """
        result = self.supabase.table("plan_tasks").select(
            "id, status"
        ).eq("job_id", job_id).execute()

        tasks = result.data or []

        if not tasks:
            return {
                "is_complete": False,
                "all_succeeded": False,
                "failed_count": 0,
                "pending_count": 0,
                "message": "No tasks found"
            }

        status_counts = {}
        for task in tasks:
            status = task["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

        pending = status_counts.get(TaskStatus.PENDING.value, 0)
        running = status_counts.get(TaskStatus.RUNNING.value, 0)
        completed = status_counts.get(TaskStatus.COMPLETE.value, 0)
        failed = status_counts.get(TaskStatus.FAILED.value, 0)

        # Job is complete if no tasks are pending or running
        is_complete = (pending == 0 and running == 0)
        all_succeeded = (is_complete and failed == 0)

        return {
            "is_complete": is_complete,
            "all_succeeded": all_succeeded,
            "failed_count": failed,
            "pending_count": pending,
            "running_count": running,
            "completed_count": completed,
            "total_count": len(tasks)
        }

    def check_for_blocked_tasks(self, job_id: int) -> List[Dict[str, Any]]:
        """
        Find tasks that are blocked due to failed dependencies.

        Args:
            job_id: The research job ID

        Returns:
            List of blocked tasks with their failed dependency info
        """
        result = self.supabase.table("plan_tasks").select("*").eq(
            "job_id", job_id
        ).execute()

        tasks = result.data or []
        task_map = {t["task_key"]: t for t in tasks}

        # Find failed task keys
        failed_keys = {
            t["task_key"] for t in tasks
            if t["status"] == TaskStatus.FAILED.value
        }

        blocked = []
        for task in tasks:
            if task["status"] != TaskStatus.PENDING.value:
                continue

            depends_on = task.get("depends_on") or []
            failed_deps = [dep for dep in depends_on if dep in failed_keys]

            if failed_deps:
                blocked.append({
                    "task_id": task["id"],
                    "task_key": task["task_key"],
                    "task_title": task["task_title"],
                    "blocked_by": failed_deps
                })

        return blocked

    # ==========================================================================
    # Artifact Storage
    # ==========================================================================

    async def _store_artifacts(
        self,
        task: Dict[str, Any],
        artifacts: List[Dict[str, Any]]
    ) -> int:
        """
        Store artifacts from task execution.

        Args:
            task: The task data
            artifacts: List of artifacts to store

        Returns:
            Number of artifacts stored
        """
        if not artifacts:
            return 0

        stored_count = 0
        for artifact in artifacts:
            try:
                self.supabase.table("research_artifacts").insert({
                    "job_id": task["job_id"],
                    "task_id": task["id"],
                    "artifact_type": artifact.get("type", "raw_output"),
                    "title": artifact.get("title", f"Artifact from {task['task_key']}"),
                    "content": artifact.get("content", ""),
                    "metadata": artifact.get("metadata", {}),
                    "source_reference": artifact.get("source"),
                    "confidence_score": artifact.get("confidence"),
                }).execute()
                stored_count += 1
            except Exception as e:
                logger.error(
                    "Failed to store artifact",
                    task_id=task["id"],
                    error=str(e)
                )

        logger.info(
            "Stored artifacts",
            task_id=task["id"],
            count=stored_count
        )

        return stored_count

    def get_task_artifacts(self, task_id: int) -> List[Dict[str, Any]]:
        """Get all artifacts for a specific task"""
        result = self.supabase.table("research_artifacts").select("*").eq(
            "task_id", task_id
        ).execute()
        return result.data or []

    def get_job_artifacts(
        self,
        job_id: int,
        artifact_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all artifacts for a job, optionally filtered by type"""
        query = self.supabase.table("research_artifacts").select("*").eq(
            "job_id", job_id
        )

        if artifact_type:
            query = query.eq("artifact_type", artifact_type)

        result = query.order("created_at").execute()
        return result.data or []


# ==============================================================================
# Sequential Job Processor
# ==============================================================================

class SequentialJobProcessor:
    """
    Process all tasks for a job in sequential order.

    Useful for simple execution without Celery workers.
    """

    def __init__(self, harness: TaskHarnessService):
        self.harness = harness

    async def process_job(self, job_id: int) -> Dict[str, Any]:
        """
        Process all tasks for a job sequentially.

        Args:
            job_id: The research job ID

        Returns:
            Dict with processing result
        """
        logger.info("Starting sequential job processing", job_id=job_id)

        processed = 0
        failed = 0

        while True:
            # Get next available task
            next_tasks = self.harness.get_next_tasks(job_id, limit=1)

            if not next_tasks:
                # Check if job is complete or blocked
                completion = self.harness.check_job_completion(job_id)

                if completion["is_complete"]:
                    logger.info(
                        "Job processing complete",
                        job_id=job_id,
                        processed=processed,
                        failed=failed
                    )
                    return {
                        "success": completion["all_succeeded"],
                        "job_id": job_id,
                        "processed": processed,
                        "failed": failed,
                        "message": "Job complete"
                    }
                else:
                    # Check for blocked tasks
                    blocked = self.harness.check_for_blocked_tasks(job_id)
                    if blocked:
                        logger.warning(
                            "Job has blocked tasks",
                            job_id=job_id,
                            blocked_count=len(blocked)
                        )
                        return {
                            "success": False,
                            "job_id": job_id,
                            "processed": processed,
                            "failed": failed,
                            "blocked": blocked,
                            "message": "Tasks blocked due to failed dependencies"
                        }
                    else:
                        logger.error(
                            "No tasks available but job not complete",
                            job_id=job_id
                        )
                        return {
                            "success": False,
                            "job_id": job_id,
                            "processed": processed,
                            "failed": failed,
                            "message": "No tasks available but job not complete"
                        }

            # Execute the next task
            task = next_tasks[0]
            result = await self.harness.execute_task(task["id"])

            processed += 1
            if not result.get("success"):
                failed += 1

            # Update job progress
            self.harness.update_job_progress(job_id)


# ==============================================================================
# Service Factory
# ==============================================================================

_harness_instance: Optional[TaskHarnessService] = None


def get_task_harness_service() -> TaskHarnessService:
    """Get or create task harness service singleton with registered executors"""
    global _harness_instance
    if _harness_instance is None:
        supabase = get_supabase_client()
        _harness_instance = TaskHarnessService(supabase)

        # Register available executors
        _register_executors(_harness_instance)

    return _harness_instance


def _register_executors(harness: TaskHarnessService) -> None:
    """Register all available task executors"""
    try:
        from app.services.task_executors.retrieval_executor import get_retrieval_executor
        harness.register_executor(get_retrieval_executor())
        logger.info("Registered RetrievalExecutor")
    except Exception as e:
        logger.warning(f"Could not register RetrievalExecutor: {e}")

    try:
        from app.services.task_executors.synthesis_executor import get_synthesis_executor
        harness.register_executor(get_synthesis_executor())
        logger.info("Registered SynthesisExecutor")
    except Exception as e:
        logger.warning(f"Could not register SynthesisExecutor: {e}")

    try:
        from app.services.task_executors.report_executor import get_report_executor
        harness.register_executor(get_report_executor())
        logger.info("Registered ReportExecutor")
    except Exception as e:
        logger.warning(f"Could not register ReportExecutor: {e}")


def get_sequential_processor() -> SequentialJobProcessor:
    """Get sequential job processor"""
    harness = get_task_harness_service()
    return SequentialJobProcessor(harness)
