"""
Empire v7.3 - B2 Storage Maintenance Tasks (Task 157)

Celery tasks for B2 storage maintenance operations:
- Dead letter queue processing
- Storage metrics collection
- Orphaned file recovery

Author: Claude Code
Date: 2025-01-15
"""

import asyncio
from typing import Dict, Any
from datetime import datetime

import structlog

from app.celery_app import celery_app

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
# Task: Process B2 Dead Letter Queue
# ==============================================================================

@celery_app.task(
    name='app.tasks.b2_maintenance_tasks.process_b2_dead_letter_queue',
    bind=True,
    max_retries=2,
    default_retry_delay=60
)
def process_b2_dead_letter_queue(
    self,
    batch_size: int = 10,
    max_retry_count: int = 10
) -> Dict[str, Any]:
    """
    Process entries in the B2 dead letter queue.

    This task:
    1. Retrieves failed operations from the DLQ
    2. Attempts to retry operations that haven't exceeded max retries
    3. Marks operations as permanent failures if max retries exceeded
    4. Reports results

    Args:
        batch_size: Number of entries to process per run
        max_retry_count: Maximum retries before permanent failure

    Returns:
        Dict with processing results
    """
    try:
        logger.info(
            "Starting B2 DLQ processing task",
            task_id=self.request.id,
            batch_size=batch_size
        )

        from app.services.b2_resilient_storage import get_resilient_b2_service

        service = get_resilient_b2_service()

        result = run_async(
            service.process_dead_letter_queue(
                batch_size=batch_size,
                max_retry_count=max_retry_count
            )
        )

        logger.info(
            "B2 DLQ processing completed",
            processed=result.get("processed", 0),
            succeeded=result.get("succeeded", 0),
            failed=result.get("failed", 0)
        )

        return {
            "success": True,
            "task_id": self.request.id,
            "timestamp": datetime.utcnow().isoformat(),
            **result
        }

    except Exception as e:
        logger.error(
            "B2 DLQ processing failed",
            error=str(e),
            task_id=self.request.id
        )

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "success": False,
            "task_id": self.request.id,
            "error": str(e)
        }


# ==============================================================================
# Task: Update B2 Storage Metrics
# ==============================================================================

@celery_app.task(
    name='app.tasks.b2_maintenance_tasks.update_b2_storage_metrics',
    bind=True,
    max_retries=2
)
def update_b2_storage_metrics(self) -> Dict[str, Any]:
    """
    Update B2 storage metrics for Prometheus.

    This task:
    1. Calculates total storage usage
    2. Updates Prometheus gauges
    3. Reports DLQ size

    Returns:
        Dict with current metrics
    """
    try:
        logger.info(
            "Starting B2 metrics update",
            task_id=self.request.id
        )

        from app.services.b2_resilient_storage import get_resilient_b2_service

        service = get_resilient_b2_service()

        result = run_async(service.update_storage_metrics())

        logger.info(
            "B2 metrics updated",
            storage_mb=result.get("total_storage_mb"),
            file_count=result.get("file_count")
        )

        return {
            "success": True,
            "task_id": self.request.id,
            **result
        }

    except Exception as e:
        logger.error(
            "B2 metrics update failed",
            error=str(e),
            task_id=self.request.id
        )

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "success": False,
            "error": str(e)
        }


# ==============================================================================
# Task: Recover B2 Orphaned Files
# ==============================================================================

@celery_app.task(
    name='app.tasks.b2_maintenance_tasks.recover_b2_orphaned_files',
    bind=True,
    max_retries=1
)
def recover_b2_orphaned_files(
    self,
    timeout_hours: int = 4,
    force_fail: bool = True
) -> Dict[str, Any]:
    """
    Detect and recover orphaned files in B2 PROCESSING folder.

    This task:
    1. Scans for files stuck in PROCESSING for too long
    2. Moves them to FAILED for manual inspection
    3. Reports recovery results

    Args:
        timeout_hours: Hours after which a file is considered orphaned
        force_fail: Move to FAILED (True) or try to restart processing (False)

    Returns:
        Dict with recovery results
    """
    try:
        logger.info(
            "Starting B2 orphan recovery",
            task_id=self.request.id,
            timeout_hours=timeout_hours
        )

        from datetime import timedelta
        from app.services.b2_workflow import get_workflow_manager

        workflow_manager = get_workflow_manager()

        result = run_async(
            workflow_manager.recover_all_orphaned_files(
                timeout=timedelta(hours=timeout_hours),
                force_fail=force_fail
            )
        )

        logger.info(
            "B2 orphan recovery completed",
            orphaned_count=result.get("orphaned_count", 0),
            recovered=len(result.get("recovered", [])),
            failed=len(result.get("failed", []))
        )

        return {
            "success": True,
            "task_id": self.request.id,
            "timestamp": datetime.utcnow().isoformat(),
            **result
        }

    except Exception as e:
        logger.error(
            "B2 orphan recovery failed",
            error=str(e),
            task_id=self.request.id
        )

        return {
            "success": False,
            "error": str(e)
        }


# ==============================================================================
# Task: Full B2 Maintenance (Combined)
# ==============================================================================

@celery_app.task(
    name='app.tasks.b2_maintenance_tasks.b2_full_maintenance',
    bind=True,
    max_retries=1
)
def b2_full_maintenance(self) -> Dict[str, Any]:
    """
    Run full B2 maintenance: DLQ processing + metrics update + orphan recovery.

    This is designed to be scheduled periodically (e.g., every 15 minutes).

    Returns:
        Dict with combined maintenance results
    """
    try:
        logger.info(
            "Starting full B2 maintenance",
            task_id=self.request.id
        )

        results = {
            "success": True,
            "task_id": self.request.id,
            "timestamp": datetime.utcnow().isoformat(),
            "dlq_processing": None,
            "metrics_update": None,
            "orphan_recovery": None
        }

        # Process DLQ
        try:
            dlq_result = process_b2_dead_letter_queue.apply(
                kwargs={"batch_size": 20, "max_retry_count": 10}
            ).get(timeout=120)
            results["dlq_processing"] = dlq_result
        except Exception as e:
            logger.warning("DLQ processing failed in maintenance", error=str(e))
            results["dlq_processing"] = {"error": str(e)}

        # Update metrics
        try:
            metrics_result = update_b2_storage_metrics.apply().get(timeout=60)
            results["metrics_update"] = metrics_result
        except Exception as e:
            logger.warning("Metrics update failed in maintenance", error=str(e))
            results["metrics_update"] = {"error": str(e)}

        # Recover orphans
        try:
            orphan_result = recover_b2_orphaned_files.apply(
                kwargs={"timeout_hours": 4, "force_fail": True}
            ).get(timeout=120)
            results["orphan_recovery"] = orphan_result
        except Exception as e:
            logger.warning("Orphan recovery failed in maintenance", error=str(e))
            results["orphan_recovery"] = {"error": str(e)}

        logger.info("Full B2 maintenance completed", results=results)

        return results

    except Exception as e:
        logger.error(
            "Full B2 maintenance failed",
            error=str(e),
            task_id=self.request.id
        )

        return {
            "success": False,
            "error": str(e)
        }


# ==============================================================================
# Celery Beat Schedule (for periodic tasks)
# ==============================================================================

# Add to celeryconfig.py or celery_app.py beat_schedule:
# beat_schedule = {
#     'b2-maintenance-every-15-minutes': {
#         'task': 'app.tasks.b2_maintenance_tasks.b2_full_maintenance',
#         'schedule': crontab(minute='*/15'),
#     },
#     'b2-metrics-every-5-minutes': {
#         'task': 'app.tasks.b2_maintenance_tasks.update_b2_storage_metrics',
#         'schedule': crontab(minute='*/5'),
#     },
# }
