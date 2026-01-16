"""
Empire v7.3 - Neo4j Dead Letter Queue Processor
Task 153: Neo4j Graph Sync Error Handling

Background Celery task for processing failed Neo4j operations
from the dead letter queue.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List
import structlog

from celery import shared_task

logger = structlog.get_logger(__name__)


@shared_task(
    name="neo4j.process_dead_letter_queue",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def process_dead_letter_queue(self, limit: int = 50) -> Dict[str, Any]:
    """
    Process failed operations from the Neo4j dead letter queue.

    This task runs periodically to retry failed operations.
    Operations that continue to fail after max retries remain in the queue
    for manual inspection.

    Args:
        limit: Maximum number of operations to process in one run

    Returns:
        Summary of processed operations
    """
    return asyncio.get_event_loop().run_until_complete(
        _process_dlq_async(limit)
    )


async def _process_dlq_async(limit: int) -> Dict[str, Any]:
    """Async implementation of DLQ processing."""
    from app.services.neo4j_resilience import (
        DeadLetterQueue,
        ResilientNeo4jClient,
        CircuitBreakerOpen,
    )
    from app.services.neo4j_http_client import Neo4jHTTPClient

    dlq = DeadLetterQueue()
    base_client = Neo4jHTTPClient()

    results = {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped_max_retries": 0,
        "skipped_circuit_open": 0,
        "operations": [],
    }

    try:
        # Get failed operations
        operations = await dlq.get_failed_operations(limit=limit)

        logger.info(
            "dlq_processing_started",
            operation_count=len(operations)
        )

        for op in operations:
            results["processed"] += 1

            # Skip if max retries exceeded
            if op.retry_count >= dlq.MAX_RETRY_ATTEMPTS:
                results["skipped_max_retries"] += 1
                results["operations"].append({
                    "operation_id": op.operation_id,
                    "status": "skipped_max_retries",
                    "retry_count": op.retry_count,
                })
                continue

            try:
                # Attempt to re-execute the query
                await base_client.execute_query(op.query, op.parameters)

                # Success - remove from queue
                await dlq.remove_operation(op.operation_id)
                results["succeeded"] += 1

                results["operations"].append({
                    "operation_id": op.operation_id,
                    "status": "succeeded",
                    "operation_type": op.operation_type,
                })

                logger.info(
                    "dlq_operation_succeeded",
                    operation_id=op.operation_id,
                    operation_type=op.operation_type
                )

            except CircuitBreakerOpen:
                # Circuit is open, skip remaining operations
                results["skipped_circuit_open"] += 1
                results["operations"].append({
                    "operation_id": op.operation_id,
                    "status": "skipped_circuit_open",
                })

                logger.warning(
                    "dlq_circuit_open_skipping",
                    remaining=len(operations) - results["processed"]
                )
                break

            except Exception as e:
                # Still failing - update retry count
                results["failed"] += 1
                await dlq.update_retry_count(op.operation_id)

                results["operations"].append({
                    "operation_id": op.operation_id,
                    "status": "failed",
                    "error": str(e),
                    "retry_count": op.retry_count + 1,
                })

                logger.warning(
                    "dlq_operation_failed",
                    operation_id=op.operation_id,
                    error=str(e),
                    retry_count=op.retry_count + 1
                )

        logger.info(
            "dlq_processing_completed",
            **{k: v for k, v in results.items() if k != "operations"}
        )

        return results

    except Exception as e:
        logger.error("dlq_processing_error", error=str(e))
        raise

    finally:
        await base_client.close()


@shared_task(
    name="neo4j.cleanup_old_dlq_entries",
    bind=True,
)
def cleanup_old_dlq_entries(self, max_age_days: int = 7) -> Dict[str, Any]:
    """
    Clean up old entries from the dead letter queue.

    Removes operations that have exceeded max retries and are older
    than the specified age.

    Args:
        max_age_days: Remove entries older than this many days

    Returns:
        Summary of cleanup operation
    """
    return asyncio.get_event_loop().run_until_complete(
        _cleanup_dlq_async(max_age_days)
    )


async def _cleanup_dlq_async(max_age_days: int) -> Dict[str, Any]:
    """Async implementation of DLQ cleanup."""
    from app.services.neo4j_resilience import DeadLetterQueue

    dlq = DeadLetterQueue()
    cutoff = datetime.utcnow().timestamp() - (max_age_days * 24 * 60 * 60)

    removed = 0
    preserved = 0

    try:
        operations = await dlq.get_failed_operations(limit=10000)

        for op in operations:
            op_time = datetime.fromisoformat(op.timestamp).timestamp()

            if op_time < cutoff and op.retry_count >= dlq.MAX_RETRY_ATTEMPTS:
                await dlq.remove_operation(op.operation_id)
                removed += 1
            else:
                preserved += 1

        logger.info(
            "dlq_cleanup_completed",
            removed=removed,
            preserved=preserved,
            max_age_days=max_age_days
        )

        return {
            "removed": removed,
            "preserved": preserved,
            "max_age_days": max_age_days,
        }

    except Exception as e:
        logger.error("dlq_cleanup_error", error=str(e))
        raise


@shared_task(name="neo4j.get_dlq_stats")
def get_dlq_stats() -> Dict[str, Any]:
    """
    Get current dead letter queue statistics.

    Returns:
        Queue statistics
    """
    return asyncio.get_event_loop().run_until_complete(_get_stats_async())


async def _get_stats_async() -> Dict[str, Any]:
    """Async implementation of stats retrieval."""
    from app.services.neo4j_resilience import DeadLetterQueue

    dlq = DeadLetterQueue()
    return await dlq.get_queue_stats()
