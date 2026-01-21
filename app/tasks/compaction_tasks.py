"""
Empire v7.3 - Context Compaction Tasks
Celery tasks for background context window compaction

Feature: Chat Context Window Management (011)
Task: 203 - Intelligent Context Condensing Engine

Usage:
    # Trigger async compaction
    from app.tasks.compaction_tasks import compact_context
    compact_context.delay(conversation_id="uuid", user_id="uuid")

    # Check progress
    from app.tasks.compaction_tasks import get_compaction_task_status
    status = get_compaction_task_status(task_id)
"""

import time
from datetime import datetime
from typing import Any, Dict, Optional

import structlog
from celery import shared_task
from prometheus_client import Counter, Histogram, Gauge

from app.models.context_models import CompactionTrigger

logger = structlog.get_logger(__name__)

# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

COMPACTION_TASKS_TOTAL = Counter(
    "empire_compaction_tasks_total",
    "Total compaction tasks executed",
    ["status"]  # queued, started, completed, failed
)

COMPACTION_TASK_QUEUE_TIME = Histogram(
    "empire_compaction_task_queue_seconds",
    "Time spent in queue before processing",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

COMPACTION_TASK_DURATION = Histogram(
    "empire_compaction_task_duration_seconds",
    "Total task duration including queue time",
    buckets=[1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0]
)

COMPACTION_TASKS_ACTIVE = Gauge(
    "empire_compaction_tasks_active",
    "Number of compaction tasks currently executing"
)


# =============================================================================
# COMPACTION TASK
# =============================================================================

@shared_task(
    name="empire.context.compact",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=120,  # 2 minutes soft limit
    time_limit=180,  # 3 minutes hard limit
    track_started=True
)
def compact_context(
    self,
    conversation_id: str,
    user_id: str,
    trigger: str = "auto",
    fast: bool = False,
    custom_prompt: Optional[str] = None,
    queued_at: Optional[str] = None
) -> Dict[str, Any]:
    """
    Celery task for background context compaction.

    This task runs the context condensing engine asynchronously,
    allowing the main API to return immediately while compaction
    happens in the background.

    Args:
        conversation_id: Conversation to compact
        user_id: User ID for authorization
        trigger: Trigger type (auto, manual, force)
        fast: Use faster model (Claude Haiku)
        custom_prompt: Custom summarization prompt
        queued_at: ISO timestamp of when task was queued

    Returns:
        Dict with compaction results
    """
    import asyncio
    start_time = time.time()
    task_id = self.request.id

    # Track queue time
    if queued_at:
        try:
            queue_time = datetime.utcnow() - datetime.fromisoformat(queued_at)
            COMPACTION_TASK_QUEUE_TIME.observe(queue_time.total_seconds())
        except Exception:
            pass

    COMPACTION_TASKS_TOTAL.labels(status="started").inc()
    COMPACTION_TASKS_ACTIVE.inc()

    logger.info(
        "Starting compaction task",
        task_id=task_id,
        conversation_id=conversation_id,
        trigger=trigger,
        fast=fast
    )

    try:
        # Import here to avoid circular imports
        from app.services.context_condensing_engine import get_condensing_engine

        engine = get_condensing_engine()

        # Run async compaction in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                engine.compact_conversation(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    trigger=CompactionTrigger(trigger),
                    custom_prompt=custom_prompt,
                    fast=fast
                )
            )
        finally:
            loop.close()

        duration = time.time() - start_time
        COMPACTION_TASK_DURATION.observe(duration)

        if result.success:
            COMPACTION_TASKS_TOTAL.labels(status="completed").inc()
            logger.info(
                "Compaction task completed",
                task_id=task_id,
                conversation_id=conversation_id,
                pre_tokens=result.pre_tokens,
                post_tokens=result.post_tokens,
                reduction_percent=round(result.reduction_percent, 1),
                duration_s=round(duration, 2)
            )

            return {
                "success": True,
                "task_id": task_id,
                "conversation_id": conversation_id,
                "pre_tokens": result.pre_tokens,
                "post_tokens": result.post_tokens,
                "reduction_percent": result.reduction_percent,
                "messages_condensed": result.messages_condensed,
                "duration_ms": result.duration_ms,
                "cost_usd": result.cost_usd,
                "model_used": result.model_used,
                "completed_at": datetime.utcnow().isoformat()
            }
        else:
            COMPACTION_TASKS_TOTAL.labels(status="failed").inc()
            logger.warning(
                "Compaction task failed",
                task_id=task_id,
                conversation_id=conversation_id,
                error=result.error_message
            )

            return {
                "success": False,
                "task_id": task_id,
                "conversation_id": conversation_id,
                "error": result.error_message,
                "completed_at": datetime.utcnow().isoformat()
            }

    except Exception as e:
        COMPACTION_TASKS_TOTAL.labels(status="failed").inc()
        logger.error(
            "Compaction task exception",
            task_id=task_id,
            conversation_id=conversation_id,
            error=str(e)
        )

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "success": False,
            "task_id": task_id,
            "conversation_id": conversation_id,
            "error": str(e),
            "completed_at": datetime.utcnow().isoformat()
        }

    finally:
        COMPACTION_TASKS_ACTIVE.dec()


@shared_task(
    name="empire.context.check_and_compact",
    bind=True,
    max_retries=1
)
def check_and_compact_if_needed(
    self,
    conversation_id: str,
    user_id: str,
    current_tokens: int,
    max_tokens: int,
    threshold_percent: int = 80
) -> Dict[str, Any]:
    """
    Check if compaction is needed and trigger if so.

    This task is typically called after adding a message to check
    if the context window has exceeded the threshold.

    Args:
        conversation_id: Conversation to check
        user_id: User ID
        current_tokens: Current token count
        max_tokens: Maximum tokens
        threshold_percent: Compaction threshold

    Returns:
        Dict indicating if compaction was triggered
    """
    import asyncio

    try:
        from app.services.context_condensing_engine import get_condensing_engine

        engine = get_condensing_engine()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            should_compact = loop.run_until_complete(
                engine.should_compact(
                    conversation_id=conversation_id,
                    current_tokens=current_tokens,
                    max_tokens=max_tokens,
                    threshold_percent=threshold_percent
                )
            )
        finally:
            loop.close()

        if should_compact:
            # Queue compaction task
            task = compact_context.delay(
                conversation_id=conversation_id,
                user_id=user_id,
                trigger="auto",
                fast=True,  # Use fast model for auto compaction
                queued_at=datetime.utcnow().isoformat()
            )

            COMPACTION_TASKS_TOTAL.labels(status="queued").inc()

            logger.info(
                "Auto-compaction triggered",
                conversation_id=conversation_id,
                task_id=task.id,
                current_tokens=current_tokens,
                threshold_percent=threshold_percent
            )

            return {
                "compaction_triggered": True,
                "task_id": task.id,
                "conversation_id": conversation_id
            }

        return {
            "compaction_triggered": False,
            "conversation_id": conversation_id,
            "reason": "Below threshold or in cooldown"
        }

    except Exception as e:
        logger.error(
            "Failed to check compaction",
            conversation_id=conversation_id,
            error=str(e)
        )
        return {
            "compaction_triggered": False,
            "conversation_id": conversation_id,
            "error": str(e)
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_compaction_task_status(task_id: str) -> Dict[str, Any]:
    """
    Get the status of a compaction task.

    Args:
        task_id: Celery task ID

    Returns:
        Dict with task status and result if completed
    """
    from celery.result import AsyncResult
    from app.celery_app import celery_app

    result = AsyncResult(task_id, app=celery_app)

    response = {
        "task_id": task_id,
        "status": result.status,
        "ready": result.ready(),
    }

    if result.ready():
        if result.successful():
            response["result"] = result.get()
        elif result.failed():
            response["error"] = str(result.result)

    return response


def cancel_compaction_task(task_id: str) -> bool:
    """
    Cancel a pending compaction task.

    Args:
        task_id: Celery task ID

    Returns:
        True if task was cancelled
    """
    from celery.result import AsyncResult
    from app.celery_app import celery_app

    try:
        result = AsyncResult(task_id, app=celery_app)
        result.revoke(terminate=True)
        logger.info("Compaction task cancelled", task_id=task_id)
        return True
    except Exception as e:
        logger.error("Failed to cancel task", task_id=task_id, error=str(e))
        return False
