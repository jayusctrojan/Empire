"""
Empire v7.3 - Research Project Tasks
Celery tasks for the Research Projects (Agent Harness) feature.

Tasks:
- initialize_research_job: Analyze query and create task plan
- execute_research_tasks: Execute planned tasks
- generate_research_report: Generate final report

Author: Claude Code
Date: 2025-01-10
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

import structlog
from celery import group, chord

from app.celery_app import celery_app
from app.core.connections import get_supabase
from app.models.research_project import JobStatus, TaskStatus

logger = structlog.get_logger(__name__)


def run_async(coro):
    """Helper to run async code in sync Celery tasks"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ==============================================================================
# Task: Initialize Research Job
# ==============================================================================

@celery_app.task(
    name='app.tasks.research_tasks.initialize_research_job',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def initialize_research_job(self, job_id: int) -> Dict[str, Any]:
    """
    Initialize a research job by analyzing the query and creating a task plan.

    This task:
    1. Fetches the job details
    2. Uses Claude to analyze the query
    3. Creates a structured task plan
    4. Stores tasks in the database
    5. Triggers task execution

    Args:
        job_id: The research job ID to initialize

    Returns:
        Dict with initialization status and task count
    """
    try:
        logger.info(
            "Initializing research job",
            job_id=job_id,
            task_id=self.request.id
        )

        # Import here to avoid circular imports
        from app.services.research_initializer import get_research_initializer_service

        # Get service and run async initialization
        service = get_research_initializer_service()
        success = run_async(service.initialize_job(job_id))

        if success:
            # Get task count for response
            supabase = get_supabase()
            result = supabase.table("plan_tasks").select(
                "id", count="exact"
            ).eq("job_id", job_id).execute()

            task_count = result.count if result.count else 0

            logger.info(
                "Research job initialized successfully",
                job_id=job_id,
                task_count=task_count
            )

            # Send project started notification
            try:
                from app.services.research_notification_service import (
                    get_research_notification_service
                )
                notification_service = get_research_notification_service()
                notification_service.send_project_started(job_id)
            except Exception as e:
                logger.warning(f"Failed to send start notification: {e}")

            # Trigger task execution
            execute_research_tasks.delay(job_id)

            return {
                "success": True,
                "job_id": job_id,
                "task_count": task_count,
                "message": "Job initialized, task execution started"
            }
        else:
            return {
                "success": False,
                "job_id": job_id,
                "message": "Failed to initialize job"
            }

    except Exception as e:
        logger.error(
            "Error initializing research job",
            job_id=job_id,
            error=str(e)
        )

        # Mark job as failed
        try:
            supabase = get_supabase()
            supabase.table("research_jobs").update({
                "status": JobStatus.FAILED.value,
                "error_message": f"Initialization failed: {str(e)}",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", job_id).execute()
        except Exception:
            pass

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "success": False,
            "job_id": job_id,
            "error": str(e)
        }


# ==============================================================================
# Task: Execute Research Tasks
# ==============================================================================

@celery_app.task(
    name='app.tasks.research_tasks.execute_research_tasks',
    bind=True,
    max_retries=2
)
def execute_research_tasks(self, job_id: int) -> Dict[str, Any]:
    """
    Execute all planned tasks for a research job.

    This task orchestrates the execution using wave-based parallelism:
    1. Organizes tasks into waves based on dependencies
    2. Executes each wave in parallel using Celery groups
    3. Validates quality gates between waves
    4. Updates progress as tasks complete

    Args:
        job_id: The research job ID

    Returns:
        Dict with execution status
    """
    try:
        logger.info(
            "Starting task execution",
            job_id=job_id,
            task_id=self.request.id
        )

        supabase = get_supabase()

        # Update job status to executing
        supabase.table("research_jobs").update({
            "status": JobStatus.EXECUTING.value,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", job_id).execute()

        # Get all tasks for this job
        tasks_result = supabase.table("plan_tasks").select("*").eq(
            "job_id", job_id
        ).order("sequence_order").execute()

        tasks = tasks_result.data or []

        if not tasks:
            logger.warning("No tasks found for job", job_id=job_id)
            return {"success": False, "job_id": job_id, "message": "No tasks found"}

        # Build execution waves
        waves = _build_execution_waves(tasks)

        logger.info(
            "Execution waves built",
            job_id=job_id,
            wave_count=len(waves),
            total_tasks=len(tasks)
        )

        # Execute waves sequentially, tasks within waves in parallel
        for wave_num, wave_task_ids in enumerate(waves, 1):
            logger.info(
                f"Executing wave {wave_num}/{len(waves)}",
                job_id=job_id,
                task_count=len(wave_task_ids)
            )

            # Create Celery group for parallel execution
            wave_tasks = group(
                execute_single_task.s(task_id)
                for task_id in wave_task_ids
            )

            # Execute wave and wait for completion
            result = wave_tasks.apply_async()
            result.get()  # Wait for all tasks in wave to complete

            # Update job progress
            _update_job_progress(supabase, job_id)

            # Check for failures in this wave
            failed_count = _count_failed_tasks(supabase, job_id, wave_task_ids)
            if failed_count > len(wave_task_ids) // 2:
                logger.error(
                    "Too many failures in wave, aborting",
                    job_id=job_id,
                    wave_num=wave_num,
                    failed=failed_count
                )
                supabase.table("research_jobs").update({
                    "status": JobStatus.FAILED.value,
                    "error_message": f"Too many task failures in wave {wave_num}",
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", job_id).execute()
                return {"success": False, "job_id": job_id, "message": "Too many failures"}

        # All waves complete - trigger report generation
        logger.info("All tasks complete, generating report", job_id=job_id)

        supabase.table("research_jobs").update({
            "status": JobStatus.GENERATING_REPORT.value,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", job_id).execute()

        generate_research_report.delay(job_id)

        return {
            "success": True,
            "job_id": job_id,
            "message": "Task execution complete, report generation started"
        }

    except Exception as e:
        logger.error(
            "Error executing research tasks",
            job_id=job_id,
            error=str(e)
        )

        try:
            supabase = get_supabase()
            supabase.table("research_jobs").update({
                "status": JobStatus.FAILED.value,
                "error_message": f"Execution failed: {str(e)}",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", job_id).execute()
        except Exception:
            pass

        # Send failure notification
        try:
            from app.services.research_notification_service import (
                get_research_notification_service
            )
            notification_service = get_research_notification_service()
            notification_service.send_project_failed(
                job_id=job_id,
                error=str(e),
                failed_task="execute_research_tasks"
            )
        except Exception:
            pass

        return {"success": False, "job_id": job_id, "error": str(e)}


# ==============================================================================
# Task: Execute Research Tasks (Concurrent Engine)
# ==============================================================================

@celery_app.task(
    name='app.tasks.research_tasks.execute_research_tasks_concurrent',
    bind=True,
    max_retries=2
)
def execute_research_tasks_concurrent(
    self,
    job_id: int,
    max_concurrent: int = 5,
    use_dynamic: bool = False
) -> Dict[str, Any]:
    """
    Execute research tasks using the Concurrent Execution Engine.

    Provides advanced features over basic wave execution:
    - Configurable concurrency limits
    - Performance metrics tracking
    - Dynamic dispatch option for maximum parallelism

    Args:
        job_id: The research job ID
        max_concurrent: Maximum concurrent tasks (default: 5)
        use_dynamic: Use dynamic dispatch instead of wave-based

    Returns:
        Dict with execution status and metrics
    """
    try:
        logger.info(
            "Starting concurrent task execution",
            job_id=job_id,
            max_concurrent=max_concurrent,
            use_dynamic=use_dynamic,
            task_id=self.request.id
        )

        from app.services.concurrent_execution import get_concurrent_execution_engine

        engine = get_concurrent_execution_engine()

        if use_dynamic:
            result = run_async(engine.execute_job_dynamic(job_id, max_concurrent))
        else:
            result = run_async(engine.execute_job_concurrent(job_id, max_concurrent))

        if result.get("success"):
            # Trigger report generation
            generate_research_report.delay(job_id)

            logger.info(
                "Concurrent execution complete",
                job_id=job_id,
                metrics=result.get("metrics")
            )

        return result

    except Exception as e:
        logger.error(
            "Error in concurrent execution",
            job_id=job_id,
            error=str(e)
        )

        try:
            supabase = get_supabase()
            supabase.table("research_jobs").update({
                "status": JobStatus.FAILED.value,
                "error_message": f"Concurrent execution failed: {str(e)}",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", job_id).execute()
        except Exception:
            pass

        return {"success": False, "job_id": job_id, "error": str(e)}


# ==============================================================================
# Task: Execute Single Task
# ==============================================================================

@celery_app.task(
    name='app.tasks.research_tasks.execute_single_task',
    bind=True,
    max_retries=2,
    default_retry_delay=30
)
def execute_single_task(self, task_id: int) -> Dict[str, Any]:
    """
    Execute a single research task using the Task Harness Service.

    This task:
    1. Delegates to TaskHarnessService for execution
    2. Handles retries and error reporting
    3. Integrates with Celery for background processing

    Args:
        task_id: The plan_tasks record ID

    Returns:
        Dict with execution result
    """
    try:
        from app.services.task_harness import get_task_harness_service

        harness = get_task_harness_service()
        supabase = get_supabase()

        # Get task details for logging and job update
        task_result = supabase.table("plan_tasks").select("*").eq(
            "id", task_id
        ).single().execute()

        if not task_result.data:
            return {"success": False, "task_id": task_id, "error": "Task not found"}

        task = task_result.data
        job_id = task["job_id"]

        logger.info(
            "Executing task via Task Harness",
            task_id=task_id,
            task_type=task["task_type"],
            task_key=task["task_key"]
        )

        # Update job's current task
        supabase.table("research_jobs").update({
            "current_task_key": task["task_key"],
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", job_id).execute()

        # Execute task using Task Harness Service
        result = run_async(harness.execute_task(task_id))

        if result.get("success"):
            logger.info(
                "Task completed successfully",
                task_id=task_id,
                task_key=task["task_key"]
            )
        else:
            raise Exception(result.get("error", "Task execution failed"))

        return result

    except Exception as e:
        logger.error(
            "Error executing task",
            task_id=task_id,
            error=str(e)
        )

        # Task Harness handles status update on failure, but ensure it's set
        try:
            supabase = get_supabase()
            supabase.table("plan_tasks").update({
                "status": TaskStatus.FAILED.value,
                "error_message": str(e),
                "completed_at": datetime.utcnow().isoformat()
            }).eq("id", task_id).execute()
        except Exception:
            pass

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {"success": False, "task_id": task_id, "error": str(e)}


# ==============================================================================
# Task: Generate Research Report
# ==============================================================================

@celery_app.task(
    name='app.tasks.research_tasks.generate_research_report',
    bind=True,
    max_retries=2
)
def generate_research_report(self, job_id: int) -> Dict[str, Any]:
    """
    Generate the final research report from all artifacts.

    This task:
    1. Collects all artifacts from completed tasks
    2. Synthesizes findings into a structured report
    3. Generates executive summary and key findings
    4. Stores report and sends notification

    Args:
        job_id: The research job ID

    Returns:
        Dict with report generation status
    """
    try:
        logger.info(
            "Generating research report",
            job_id=job_id,
            task_id=self.request.id
        )

        supabase = get_supabase()

        # Get job details
        job_result = supabase.table("research_jobs").select("*").eq(
            "id", job_id
        ).single().execute()

        job = job_result.data

        # Get all artifacts
        artifacts_result = supabase.table("research_artifacts").select("*").eq(
            "job_id", job_id
        ).execute()

        artifacts = artifacts_result.data or []

        # TODO: Implement actual report generation in Task 98
        # For now, create a placeholder report
        report_content = _generate_placeholder_report(job, artifacts)

        # Update job with report
        supabase.table("research_jobs").update({
            "status": JobStatus.COMPLETE.value,
            "report_content": report_content,
            "completed_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "progress_percentage": 100.0
        }).eq("id", job_id).execute()

        # Send project completed notification
        try:
            from app.services.research_notification_service import (
                get_research_notification_service
            )
            notification_service = get_research_notification_service()
            notification_service.send_project_completed(job_id)
        except Exception as e:
            logger.warning(f"Failed to send completion notification: {e}")

        logger.info(
            "Research report generated successfully",
            job_id=job_id,
            artifact_count=len(artifacts)
        )

        return {
            "success": True,
            "job_id": job_id,
            "message": "Report generated successfully"
        }

    except Exception as e:
        logger.error(
            "Error generating report",
            job_id=job_id,
            error=str(e)
        )

        try:
            supabase = get_supabase()
            supabase.table("research_jobs").update({
                "status": JobStatus.FAILED.value,
                "error_message": f"Report generation failed: {str(e)}",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", job_id).execute()
        except Exception:
            pass

        # Send failure notification
        try:
            from app.services.research_notification_service import (
                get_research_notification_service
            )
            notification_service = get_research_notification_service()
            notification_service.send_project_failed(
                job_id=job_id,
                error=str(e),
                failed_task="generate_research_report"
            )
        except Exception:
            pass

        return {"success": False, "job_id": job_id, "error": str(e)}


# ==============================================================================
# Helper Functions
# ==============================================================================

def _build_execution_waves(tasks: list) -> list:
    """Organize tasks into waves based on dependencies"""
    task_map = {t["id"]: t for t in tasks}
    key_to_id = {t["task_key"]: t["id"] for t in tasks}
    completed = set()
    waves = []

    remaining = set(task_map.keys())

    while remaining:
        wave = []
        for task_id in remaining:
            task = task_map[task_id]
            deps = task.get("depends_on") or []
            dep_ids = {key_to_id.get(d) for d in deps if d in key_to_id}
            if dep_ids.issubset(completed):
                wave.append(task_id)

        if not wave:
            # No progress - just add remaining (may have invalid deps)
            wave = list(remaining)
            logger.warning("Could not resolve dependencies, executing remaining tasks")

        waves.append(wave)
        completed.update(wave)
        remaining -= set(wave)

    return waves


def _update_job_progress(supabase, job_id: int):
    """Update job progress percentage and send milestone notifications"""
    result = supabase.table("plan_tasks").select(
        "id, status"
    ).eq("job_id", job_id).execute()

    tasks = result.data or []
    if not tasks:
        return

    completed = sum(1 for t in tasks if t["status"] == TaskStatus.COMPLETE.value)
    progress = (completed / len(tasks)) * 100

    supabase.table("research_jobs").update({
        "completed_tasks": completed,
        "progress_percentage": round(progress, 2),
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", job_id).execute()

    # Send progress milestone notifications (25%, 50%, 75%)
    try:
        from app.services.research_notification_service import (
            get_research_notification_service
        )
        notification_service = get_research_notification_service()
        notification_service.send_progress_update(job_id, progress)
    except Exception as e:
        logger.warning(f"Failed to send progress notification: {e}")


def _count_failed_tasks(supabase, job_id: int, task_ids: list) -> int:
    """Count failed tasks in a wave"""
    result = supabase.table("plan_tasks").select(
        "id"
    ).eq("job_id", job_id).in_("id", task_ids).eq(
        "status", TaskStatus.FAILED.value
    ).execute()

    return len(result.data) if result.data else 0


def _execute_task_by_type(task: dict) -> dict:
    """
    Route task to appropriate executor using the Task Harness Service.

    This function bridges the sync Celery task with the async Task Harness.
    """
    from app.services.task_harness import get_task_harness_service

    harness = get_task_harness_service()

    # Run async executor in sync context
    result = run_async(harness.execute_task_by_type(task))

    return result


def _generate_placeholder_report(job: dict, artifacts: list) -> str:
    """
    Generate placeholder report.
    TODO: Replace with actual report generation in Task 98
    """
    return f"""# Research Report

## Query
{job['query']}

## Summary
Research completed with {len(artifacts)} artifacts collected.

## Status
Report generation placeholder - full implementation in Task 98.

---
Generated: {datetime.utcnow().isoformat()}
"""
