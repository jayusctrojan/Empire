"""
Empire v7.3 - Recovery Tasks
Celery tasks for recovering from failures and maintaining data consistency

These tasks run on startup or periodically to:
1. Recover orphaned documents stuck in "processing"
2. Replay pending WAL entries
3. Clean up stale idempotency keys
4. Verify data consistency between systems

Usage:
    # Run manually
    from app.tasks.recovery_tasks import recover_orphaned_documents
    recover_orphaned_documents.delay()

    # Scheduled via Celery Beat
    # See celery_app.py for schedule configuration
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from celery import shared_task
from prometheus_client import Counter, Histogram

logger = structlog.get_logger(__name__)


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

RECOVERY_TASKS_TOTAL = Counter(
    "empire_recovery_tasks_total",
    "Total recovery tasks executed",
    ["task_type", "result"]
)

RECOVERY_TASK_DURATION = Histogram(
    "empire_recovery_task_duration_seconds",
    "Duration of recovery tasks",
    ["task_type"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

ORPHANED_DOCUMENTS_RECOVERED = Counter(
    "empire_orphaned_documents_recovered_total",
    "Total orphaned documents recovered"
)

WAL_ENTRIES_REPLAYED = Counter(
    "empire_wal_entries_replayed_total",
    "Total WAL entries replayed",
    ["result"]
)


# =============================================================================
# ORPHANED DOCUMENT RECOVERY
# =============================================================================

@shared_task(
    name="empire.recovery.orphaned_documents",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def recover_orphaned_documents(
    self,
    max_age_hours: int = 1,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    Recover documents stuck in "processing" state.

    Documents can get stuck if:
    - Celery worker crashed mid-processing
    - External service timed out
    - Application restarted during processing

    This task resets them to "pending" for retry.

    Args:
        max_age_hours: Only recover documents older than this
        batch_size: Maximum documents to recover per run

    Returns:
        Dict with recovery statistics
    """
    import time
    start_time = time.time()

    try:
        from app.core.connections import get_supabase

        supabase = get_supabase()
        if not supabase:
            logger.warning("Supabase not available for orphaned document recovery")
            RECOVERY_TASKS_TOTAL.labels(task_type="orphaned_documents", result="skipped").inc()
            return {"recovered": 0, "status": "skipped", "reason": "supabase_unavailable"}

        # Calculate cutoff time
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

        # Find orphaned documents
        result = supabase.table("documents_v2").select(
            "id", "title", "status", "updated_at"
        ).eq(
            "status", "processing"
        ).lt(
            "updated_at", cutoff.isoformat()
        ).limit(batch_size).execute()

        orphaned = result.data if result.data else []
        recovered_count = 0
        failed_count = 0

        for doc in orphaned:
            try:
                # Reset to pending
                supabase.table("documents_v2").update({
                    "status": "pending",
                    "updated_at": datetime.utcnow().isoformat(),
                    "processing_error": "Recovered from orphaned state"
                }).eq("id", doc["id"]).execute()

                recovered_count += 1
                ORPHANED_DOCUMENTS_RECOVERED.inc()

                logger.info(
                    "Recovered orphaned document",
                    document_id=doc["id"],
                    title=doc.get("title", "unknown")[:50]
                )

            except Exception as e:
                failed_count += 1
                logger.error(
                    "Failed to recover document",
                    document_id=doc["id"],
                    error=str(e)
                )

        duration = time.time() - start_time
        RECOVERY_TASK_DURATION.labels(task_type="orphaned_documents").observe(duration)
        RECOVERY_TASKS_TOTAL.labels(task_type="orphaned_documents", result="success").inc()

        logger.info(
            "Orphaned document recovery completed",
            found=len(orphaned),
            recovered=recovered_count,
            failed=failed_count,
            duration_seconds=round(duration, 2)
        )

        return {
            "found": len(orphaned),
            "recovered": recovered_count,
            "failed": failed_count,
            "duration_seconds": round(duration, 2),
            "status": "success"
        }

    except Exception as e:
        RECOVERY_TASKS_TOTAL.labels(task_type="orphaned_documents", result="error").inc()
        logger.error("Orphaned document recovery failed", error=str(e))

        # Retry with exponential backoff
        raise self.retry(exc=e)


# =============================================================================
# WAL REPLAY
# =============================================================================

@shared_task(
    name="empire.recovery.wal_replay",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def replay_pending_wal_entries(
    self,
    max_age_hours: int = 24,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Replay pending WAL entries.

    Called on startup and periodically to ensure operations complete.

    Args:
        max_age_hours: Only replay entries younger than this
        limit: Maximum entries to replay per run

    Returns:
        Dict with replay statistics
    """
    import time
    start_time = time.time()

    try:
        from app.services.wal_manager import get_wal_manager

        wal = get_wal_manager()
        if not wal:
            logger.warning("WAL manager not available for replay")
            RECOVERY_TASKS_TOTAL.labels(task_type="wal_replay", result="skipped").inc()
            return {"replayed": 0, "status": "skipped", "reason": "wal_unavailable"}

        # Run async replay
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            stats = loop.run_until_complete(wal.replay_pending())
        finally:
            loop.close()

        duration = time.time() - start_time
        RECOVERY_TASK_DURATION.labels(task_type="wal_replay").observe(duration)
        RECOVERY_TASKS_TOTAL.labels(task_type="wal_replay", result="success").inc()

        # Update metrics
        WAL_ENTRIES_REPLAYED.labels(result="success").inc(stats.get("succeeded", 0))
        WAL_ENTRIES_REPLAYED.labels(result="failure").inc(stats.get("failed", 0))

        logger.info(
            "WAL replay completed",
            **stats,
            duration_seconds=round(duration, 2)
        )

        return {
            **stats,
            "duration_seconds": round(duration, 2),
            "status": "success"
        }

    except Exception as e:
        RECOVERY_TASKS_TOTAL.labels(task_type="wal_replay", result="error").inc()
        logger.error("WAL replay failed", error=str(e))
        raise self.retry(exc=e)


# =============================================================================
# IDEMPOTENCY CLEANUP
# =============================================================================

@shared_task(
    name="empire.recovery.idempotency_cleanup",
    bind=True,
    max_retries=2
)
def cleanup_idempotency_keys(self) -> Dict[str, Any]:
    """
    Clean up expired idempotency keys.

    Runs periodically to prevent table bloat.

    Returns:
        Dict with cleanup statistics
    """
    import time
    start_time = time.time()

    try:
        from app.services.idempotency_manager import get_idempotency_manager

        mgr = get_idempotency_manager()
        if not mgr:
            logger.warning("Idempotency manager not available for cleanup")
            RECOVERY_TASKS_TOTAL.labels(task_type="idempotency_cleanup", result="skipped").inc()
            return {"cleaned": 0, "status": "skipped"}

        # Run async cleanup
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            cleaned = loop.run_until_complete(mgr.cleanup_expired())
        finally:
            loop.close()

        duration = time.time() - start_time
        RECOVERY_TASK_DURATION.labels(task_type="idempotency_cleanup").observe(duration)
        RECOVERY_TASKS_TOTAL.labels(task_type="idempotency_cleanup", result="success").inc()

        logger.info(
            "Idempotency cleanup completed",
            cleaned=cleaned,
            duration_seconds=round(duration, 2)
        )

        return {
            "cleaned": cleaned,
            "duration_seconds": round(duration, 2),
            "status": "success"
        }

    except Exception as e:
        RECOVERY_TASKS_TOTAL.labels(task_type="idempotency_cleanup", result="error").inc()
        logger.error("Idempotency cleanup failed", error=str(e))
        raise self.retry(exc=e)


# =============================================================================
# WAL CLEANUP
# =============================================================================

@shared_task(
    name="empire.recovery.wal_cleanup",
    bind=True,
    max_retries=2
)
def cleanup_wal_entries(self, days: int = 7) -> Dict[str, Any]:
    """
    Clean up old completed/failed WAL entries.

    Args:
        days: Delete entries older than this many days

    Returns:
        Dict with cleanup statistics
    """
    import time
    start_time = time.time()

    try:
        from app.services.wal_manager import get_wal_manager

        wal = get_wal_manager()
        if not wal:
            logger.warning("WAL manager not available for cleanup")
            RECOVERY_TASKS_TOTAL.labels(task_type="wal_cleanup", result="skipped").inc()
            return {"cleaned": 0, "status": "skipped"}

        # Run async cleanup
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            cleaned = loop.run_until_complete(wal.cleanup_old_entries(days))
        finally:
            loop.close()

        duration = time.time() - start_time
        RECOVERY_TASK_DURATION.labels(task_type="wal_cleanup").observe(duration)
        RECOVERY_TASKS_TOTAL.labels(task_type="wal_cleanup", result="success").inc()

        logger.info(
            "WAL cleanup completed",
            cleaned=cleaned,
            duration_seconds=round(duration, 2)
        )

        return {
            "cleaned": cleaned,
            "duration_seconds": round(duration, 2),
            "status": "success"
        }

    except Exception as e:
        RECOVERY_TASKS_TOTAL.labels(task_type="wal_cleanup", result="error").inc()
        logger.error("WAL cleanup failed", error=str(e))
        raise self.retry(exc=e)


# =============================================================================
# DATA CONSISTENCY CHECK
# =============================================================================

@shared_task(
    name="empire.recovery.consistency_check",
    bind=True,
    max_retries=1
)
def check_data_consistency(
    self,
    fix_issues: bool = False
) -> Dict[str, Any]:
    """
    Check data consistency between Supabase and Neo4j.

    Identifies:
    - Documents in Supabase but not in Neo4j
    - Orphaned entities in Neo4j
    - Missing relationships

    Args:
        fix_issues: If True, attempt to fix found issues

    Returns:
        Dict with consistency check results
    """
    import time
    start_time = time.time()

    issues = {
        "missing_in_neo4j": [],
        "orphaned_in_neo4j": [],
        "missing_relationships": []
    }

    try:
        from app.core.connections import get_supabase, get_neo4j_driver

        supabase = get_supabase()
        neo4j = get_neo4j_driver()

        if not supabase or not neo4j:
            logger.warning("Databases not available for consistency check")
            RECOVERY_TASKS_TOTAL.labels(task_type="consistency_check", result="skipped").inc()
            return {"status": "skipped", "issues": issues}

        # Get document IDs from Supabase
        result = supabase.table("documents_v2").select("id").eq("status", "completed").execute()
        supabase_doc_ids = set(doc["id"] for doc in result.data) if result.data else set()

        # Get document IDs from Neo4j
        with neo4j.session() as session:
            neo4j_result = session.run(
                "MATCH (d:Document) RETURN d.id as id"
            )
            neo4j_doc_ids = set(record["id"] for record in neo4j_result)

        # Find discrepancies
        missing_in_neo4j = supabase_doc_ids - neo4j_doc_ids
        orphaned_in_neo4j = neo4j_doc_ids - supabase_doc_ids

        issues["missing_in_neo4j"] = list(missing_in_neo4j)[:100]  # Limit for safety
        issues["orphaned_in_neo4j"] = list(orphaned_in_neo4j)[:100]

        # Log findings
        if missing_in_neo4j:
            logger.warning(
                "Documents missing in Neo4j",
                count=len(missing_in_neo4j),
                sample=list(missing_in_neo4j)[:5]
            )

        if orphaned_in_neo4j:
            logger.warning(
                "Orphaned documents in Neo4j",
                count=len(orphaned_in_neo4j),
                sample=list(orphaned_in_neo4j)[:5]
            )

        # Fix issues if requested
        fixed = {"synced": 0, "deleted": 0}

        if fix_issues and missing_in_neo4j:
            # Queue documents for re-sync
            from app.tasks.graph_sync import sync_document_to_graph

            for doc_id in list(missing_in_neo4j)[:10]:  # Limit batch size
                try:
                    sync_document_to_graph.delay(doc_id)
                    fixed["synced"] += 1
                except Exception as e:
                    logger.error("Failed to queue doc for sync", doc_id=doc_id, error=str(e))

        if fix_issues and orphaned_in_neo4j:
            # Delete orphaned nodes
            with neo4j.session() as session:
                for doc_id in list(orphaned_in_neo4j)[:10]:
                    try:
                        session.run(
                            "MATCH (d:Document {id: $id}) DETACH DELETE d",
                            id=doc_id
                        )
                        fixed["deleted"] += 1
                    except Exception as e:
                        logger.error("Failed to delete orphaned node", doc_id=doc_id, error=str(e))

        duration = time.time() - start_time
        RECOVERY_TASK_DURATION.labels(task_type="consistency_check").observe(duration)
        RECOVERY_TASKS_TOTAL.labels(task_type="consistency_check", result="success").inc()

        return {
            "status": "success",
            "issues": {
                "missing_in_neo4j_count": len(missing_in_neo4j),
                "orphaned_in_neo4j_count": len(orphaned_in_neo4j),
                "samples": issues
            },
            "fixed": fixed if fix_issues else None,
            "duration_seconds": round(duration, 2)
        }

    except Exception as e:
        RECOVERY_TASKS_TOTAL.labels(task_type="consistency_check", result="error").inc()
        logger.error("Consistency check failed", error=str(e))
        raise self.retry(exc=e)


# =============================================================================
# STARTUP RECOVERY
# =============================================================================

@shared_task(name="empire.recovery.startup")
def run_startup_recovery() -> Dict[str, Any]:
    """
    Run all recovery tasks on application startup.

    Called from main.py during lifespan startup.

    Returns:
        Dict with all recovery results
    """
    logger.info("Running startup recovery tasks")

    results = {}

    # 1. Recover orphaned documents
    try:
        results["orphaned_documents"] = recover_orphaned_documents.apply().get(timeout=120)
    except Exception as e:
        results["orphaned_documents"] = {"status": "error", "error": str(e)}
        logger.error("Startup orphaned document recovery failed", error=str(e))

    # 2. Replay pending WAL entries
    try:
        results["wal_replay"] = replay_pending_wal_entries.apply().get(timeout=120)
    except Exception as e:
        results["wal_replay"] = {"status": "error", "error": str(e)}
        logger.error("Startup WAL replay failed", error=str(e))

    logger.info("Startup recovery completed", results=results)

    return results


# =============================================================================
# SCHEDULED TASKS CONFIGURATION
# =============================================================================

# These can be added to Celery Beat schedule in celery_app.py:
#
# CELERYBEAT_SCHEDULE = {
#     'recover-orphaned-documents': {
#         'task': 'empire.recovery.orphaned_documents',
#         'schedule': crontab(minute='*/15'),  # Every 15 minutes
#     },
#     'replay-wal': {
#         'task': 'empire.recovery.wal_replay',
#         'schedule': crontab(minute='*/5'),  # Every 5 minutes
#     },
#     'cleanup-idempotency': {
#         'task': 'empire.recovery.idempotency_cleanup',
#         'schedule': crontab(hour='*/6'),  # Every 6 hours
#     },
#     'cleanup-wal': {
#         'task': 'empire.recovery.wal_cleanup',
#         'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
#     },
#     'consistency-check': {
#         'task': 'empire.recovery.consistency_check',
#         'schedule': crontab(hour=4, minute=0),  # Daily at 4 AM
#     },
# }
