"""
Empire v7.3 - Research Project Tasks
Celery tasks for the Research Projects (Agent Harness) feature.

Tasks:
- initialize_research_job: Analyze query and create task plan
- execute_research_tasks: Execute planned tasks
- generate_research_report: Generate final report with B2 storage (Task 181)

Author: Claude Code
Date: 2025-01-10
Updated: 2025-01-17 - Task 181: Full report generation with ReportExecutor and B2 storage
"""

import asyncio
import os
import tempfile
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

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
    Generate the final research report from all artifacts (Task 181).

    This task:
    1. Collects all artifacts from completed tasks
    2. Uses ReportExecutor to generate AI-powered report
    3. Generates both markdown and PDF versions
    4. Stores reports in B2 storage
    5. Updates database with report metadata
    6. Sends completion notification

    Args:
        job_id: The research job ID

    Returns:
        Dict with report generation status, URLs, and metadata
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
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Get all artifacts
        artifacts_result = supabase.table("research_artifacts").select("*").eq(
            "job_id", job_id
        ).execute()

        artifacts = artifacts_result.data or []

        # Get completed tasks for context
        tasks_result = supabase.table("plan_tasks").select("*").eq(
            "job_id", job_id
        ).eq("status", TaskStatus.COMPLETE.value).execute()

        completed_tasks = tasks_result.data or []

        # Generate report using ReportExecutor
        report_result = run_async(_generate_report_with_executor(
            job=job,
            artifacts=artifacts,
            tasks=completed_tasks
        ))

        report_content = report_result.get("content", "")
        word_count = report_result.get("word_count", 0)

        # Generate PDF version
        pdf_bytes = _generate_report_pdf(
            title=f"Research Report: {job['query'][:50]}",
            content=report_content,
            job=job
        )

        # Upload to B2 storage
        b2_result = run_async(_upload_reports_to_b2(
            job_id=job_id,
            markdown_content=report_content,
            pdf_bytes=pdf_bytes
        ))

        md_url = b2_result.get("md_url")
        pdf_url = b2_result.get("pdf_url")
        md_path = b2_result.get("md_path")
        pdf_path = b2_result.get("pdf_path")

        # Store report metadata
        report_record = {
            "job_id": job_id,
            "title": f"Research Report: {job['query'][:100]}",
            "description": "Generated report for research query",
            "md_path": md_path,
            "md_url": md_url,
            "pdf_path": pdf_path,
            "pdf_url": pdf_url,
            "word_count": word_count,
            "artifact_count": len(artifacts),
            "task_count": len(completed_tasks),
            "created_at": datetime.utcnow().isoformat()
        }

        # Insert report record
        report_insert = supabase.table("research_reports").insert(
            report_record
        ).execute()

        report_id = report_insert.data[0]["id"] if report_insert.data else None

        # Update job with report
        supabase.table("research_jobs").update({
            "status": JobStatus.COMPLETE.value,
            "report_content": report_content,
            "report_md_url": md_url,
            "report_pdf_url": pdf_url,
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
            report_id=report_id,
            artifact_count=len(artifacts),
            word_count=word_count,
            md_url=md_url,
            pdf_url=pdf_url
        )

        return {
            "success": True,
            "job_id": job_id,
            "report_id": report_id,
            "md_url": md_url,
            "pdf_url": pdf_url,
            "word_count": word_count,
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
    Generate fallback report when ReportExecutor is unavailable.
    """
    return f"""# Research Report

## Query
{job['query']}

## Summary
Research completed with {len(artifacts)} artifacts collected.

## Status
Report generated with fallback method.

---
Generated: {datetime.utcnow().isoformat()}
"""


# ==============================================================================
# Task 181: Report Generation Helpers
# ==============================================================================


async def _generate_report_with_executor(
    job: Dict[str, Any],
    artifacts: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate report content using ReportExecutor (Task 181).

    Uses the ReportExecutor to create an AI-powered comprehensive report
    from job data, artifacts, and task results.

    Args:
        job: Research job record
        artifacts: List of research artifacts
        tasks: List of completed plan tasks

    Returns:
        Dict with content, word_count, and sections
    """
    try:
        from app.services.task_executors.report_executor import get_report_executor

        executor = get_report_executor()

        # Build a synthetic task for the executor
        synthetic_task = {
            "id": 0,
            "job_id": job["id"],
            "task_type": "write_report",
            "task_key": "final_report",
            "query": job["query"],
            "config": {
                "research_type": job.get("config", {}).get("research_type", "general"),
                "focus_areas": job.get("config", {}).get("focus_areas", [])
            }
        }

        # Execute report generation
        result = await executor.execute_write_report(synthetic_task)

        if result.get("success"):
            # Extract content from artifact
            report_artifact = result.get("artifacts", [{}])[0]
            content = report_artifact.get("content", "")

            return {
                "content": content,
                "word_count": result.get("data", {}).get("word_count", len(content.split())),
                "sections": result.get("data", {}).get("sections", []),
                "quality_score": result.get("data", {}).get("quality_score")
            }
        else:
            logger.warning(
                "ReportExecutor returned failure, using fallback",
                error=result.get("error")
            )
            # Fall back to placeholder
            content = _generate_placeholder_report(job, artifacts)
            return {
                "content": content,
                "word_count": len(content.split()),
                "sections": []
            }

    except Exception as e:
        logger.warning(
            "ReportExecutor failed, using fallback",
            error=str(e)
        )
        # Fall back to placeholder
        content = _generate_placeholder_report(job, artifacts)
        return {
            "content": content,
            "word_count": len(content.split()),
            "sections": []
        }


def _generate_report_pdf(
    title: str,
    content: str,
    job: Dict[str, Any]
) -> bytes:
    """
    Generate PDF from markdown report content (Task 181).

    Uses ReportLab to create a professional PDF document.

    Args:
        title: Report title
        content: Markdown content
        job: Job record for metadata

    Returns:
        PDF file as bytes
    """
    try:
        from io import BytesIO
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.colors import HexColor
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, PageBreak
        )

        # Create PDF buffer
        buffer = BytesIO()

        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch
        )

        # Get styles
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=HexColor("#1a365d")
        )

        heading_style = ParagraphStyle(
            'ReportHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=10,
            textColor=HexColor("#2c5282")
        )

        body_style = ParagraphStyle(
            'ReportBody',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=12
        )

        meta_style = ParagraphStyle(
            'ReportMeta',
            parent=styles['Normal'],
            fontSize=10,
            textColor=HexColor("#718096"),
            alignment=TA_CENTER
        )

        # Build story
        story = []

        # Title page
        story.append(Spacer(1, 2 * inch))
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.5 * inch))

        # Metadata
        created_at = job.get("created_at", datetime.utcnow().isoformat())
        story.append(Paragraph(f"Generated: {created_at[:10]}", meta_style))
        story.append(Paragraph("Empire v7.3 Research System", meta_style))
        story.append(PageBreak())

        # Process markdown content
        lines = content.split('\n')
        current_paragraph = []

        for line in lines:
            line = line.strip()

            if not line:
                # Empty line - flush paragraph
                if current_paragraph:
                    text = ' '.join(current_paragraph)
                    story.append(Paragraph(text, body_style))
                    current_paragraph = []
                continue

            if line.startswith('# '):
                # H1 heading
                if current_paragraph:
                    text = ' '.join(current_paragraph)
                    story.append(Paragraph(text, body_style))
                    current_paragraph = []
                story.append(Paragraph(line[2:], title_style))

            elif line.startswith('## '):
                # H2 heading
                if current_paragraph:
                    text = ' '.join(current_paragraph)
                    story.append(Paragraph(text, body_style))
                    current_paragraph = []
                story.append(Paragraph(line[3:], heading_style))

            elif line.startswith('### '):
                # H3 heading
                if current_paragraph:
                    text = ' '.join(current_paragraph)
                    story.append(Paragraph(text, body_style))
                    current_paragraph = []
                h3_style = ParagraphStyle(
                    'H3',
                    parent=heading_style,
                    fontSize=13
                )
                story.append(Paragraph(line[4:], h3_style))

            elif line.startswith('- ') or line.startswith('* '):
                # Bullet point
                if current_paragraph:
                    text = ' '.join(current_paragraph)
                    story.append(Paragraph(text, body_style))
                    current_paragraph = []
                bullet_style = ParagraphStyle(
                    'Bullet',
                    parent=body_style,
                    leftIndent=20,
                    bulletIndent=10
                )
                story.append(Paragraph(f"• {line[2:]}", bullet_style))

            elif line.startswith('---'):
                # Horizontal rule - add spacer
                if current_paragraph:
                    text = ' '.join(current_paragraph)
                    story.append(Paragraph(text, body_style))
                    current_paragraph = []
                story.append(Spacer(1, 0.3 * inch))

            else:
                # Regular text - accumulate
                current_paragraph.append(line)

        # Flush remaining paragraph
        if current_paragraph:
            text = ' '.join(current_paragraph)
            story.append(Paragraph(text, body_style))

        # Footer
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph(
            "Generated by Empire v7.3 Research Report Generator",
            meta_style
        ))

        # Build PDF
        doc.build(story)

        # Get bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(
            "PDF generated",
            size_bytes=len(pdf_bytes)
        )

        return pdf_bytes

    except ImportError as e:
        logger.error(f"ReportLab not available: {e}")
        # Return minimal PDF placeholder
        return b"%PDF-1.4\n%Report generation requires reportlab\n%%EOF"

    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise


async def _upload_reports_to_b2(
    job_id: int,
    markdown_content: str,
    pdf_bytes: bytes
) -> Dict[str, Any]:
    """
    Upload markdown and PDF reports to B2 storage (Task 181).

    Args:
        job_id: Research job ID
        markdown_content: Markdown report content
        pdf_bytes: PDF file bytes

    Returns:
        Dict with md_url, pdf_url, md_path, pdf_path
    """
    try:
        from app.services.b2_storage import get_b2_service
        from io import BytesIO

        b2_service = get_b2_service()

        # Generate filenames with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        md_filename = f"report_{job_id}_{timestamp}.md"
        pdf_filename = f"report_{job_id}_{timestamp}.pdf"

        # B2 paths in reports folder
        md_path = f"reports/{job_id}/{md_filename}"
        pdf_path = f"reports/{job_id}/{pdf_filename}"

        # Upload markdown
        md_buffer = BytesIO(markdown_content.encode('utf-8'))
        md_result = await b2_service.upload_file(
            file_data=md_buffer,
            filename=md_filename,
            folder=f"reports/{job_id}",
            content_type="text/markdown",
            metadata={
                "job_id": str(job_id),
                "report_type": "markdown"
            }
        )

        # Upload PDF
        pdf_buffer = BytesIO(pdf_bytes)
        pdf_result = await b2_service.upload_file(
            file_data=pdf_buffer,
            filename=pdf_filename,
            folder=f"reports/{job_id}",
            content_type="application/pdf",
            metadata={
                "job_id": str(job_id),
                "report_type": "pdf"
            }
        )

        logger.info(
            "Reports uploaded to B2",
            job_id=job_id,
            md_path=md_path,
            pdf_path=pdf_path
        )

        return {
            "md_url": md_result.get("url"),
            "pdf_url": pdf_result.get("url"),
            "md_path": md_path,
            "pdf_path": pdf_path,
            "md_file_id": md_result.get("file_id"),
            "pdf_file_id": pdf_result.get("file_id")
        }

    except Exception as e:
        logger.error(f"B2 upload failed: {e}")
        # Return empty URLs on failure (report still saved in DB)
        return {
            "md_url": None,
            "pdf_url": None,
            "md_path": None,
            "pdf_path": None
        }
