"""
Empire v7.3 - Content Prep Agent Celery Tasks

Feature: 007-content-prep-agent
Tasks for content set detection, validation, and ordered processing.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.celery_app import celery_app, PRIORITY_NORMAL, PRIORITY_HIGH

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async code in Celery tasks"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ============================================================================
# Content Set Detection Task
# ============================================================================

@celery_app.task(
    name='app.tasks.content_prep_tasks.detect_content_sets',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    queue='content_prep'
)
def detect_content_sets(
    self,
    b2_folder: str,
    detection_mode: str = "auto",
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Detect content sets in a B2 folder.

    Analyzes files in the specified folder to identify related content sets
    (courses, documentation, book chapters) and standalone files.

    Args:
        b2_folder: B2 folder path to analyze (e.g., "pending/courses/")
        detection_mode: Detection strategy - "auto", "pattern", "metadata", "llm"
        user_id: Optional user ID for access control

    Returns:
        dict: Detection results with content_sets and standalone_files
    """
    from app.services.content_prep_agent import ContentPrepAgent

    logger.info(f"Detecting content sets in {b2_folder} (mode: {detection_mode})")

    try:
        agent = ContentPrepAgent()
        result = run_async(agent.analyze_folder(
            b2_folder=b2_folder,
            detection_mode=detection_mode
        ))

        logger.info(
            f"Detected {len(result.get('content_sets', []))} content sets, "
            f"{len(result.get('standalone_files', []))} standalone files"
        )

        return {
            "status": "success",
            "b2_folder": b2_folder,
            "detection_mode": detection_mode,
            "content_sets": result.get("content_sets", []),
            "standalone_files": result.get("standalone_files", []),
            "analysis_time_ms": result.get("analysis_time_ms", 0),
            "detected_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Content set detection failed: {e}", exc_info=True)
        raise


# ============================================================================
# Content Set Validation Task
# ============================================================================

@celery_app.task(
    name='app.tasks.content_prep_tasks.validate_content_set',
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    queue='content_prep'
)
def validate_content_set(
    self,
    content_set_id: str,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate completeness of a content set.

    Checks for missing files in the sequence (gap detection).

    Args:
        content_set_id: UUID of the content set to validate
        user_id: Optional user ID for access control

    Returns:
        dict: Validation result with is_complete, missing_files, etc.
    """
    from app.services.content_prep_agent import ContentPrepAgent

    logger.info(f"Validating content set: {content_set_id}")

    try:
        agent = ContentPrepAgent()
        result = run_async(agent.validate_completeness(content_set_id))

        return {
            "status": "success",
            "set_id": content_set_id,
            "is_complete": result.get("is_complete", False),
            "missing_files": result.get("missing_files", []),
            "total_files": result.get("total_files", 0),
            "gaps_detected": result.get("gaps_detected", 0),
            "can_proceed": result.get("can_proceed", True),
            "requires_acknowledgment": result.get("requires_acknowledgment", False),
            "validated_at": datetime.utcnow().isoformat()
        }

    except ValueError as e:
        logger.warning(f"Content set not found: {content_set_id}")
        return {
            "status": "error",
            "error": str(e),
            "set_id": content_set_id
        }
    except Exception as e:
        logger.error(f"Content set validation failed: {e}", exc_info=True)
        raise


# ============================================================================
# Manifest Generation Task
# ============================================================================

@celery_app.task(
    name='app.tasks.content_prep_tasks.generate_manifest',
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    queue='content_prep'
)
def generate_manifest(
    self,
    content_set_id: str,
    proceed_incomplete: bool = False,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a processing manifest for a content set.

    Creates an ordered processing queue with file dependencies.

    Args:
        content_set_id: UUID of the content set
        proceed_incomplete: Allow processing even if set is incomplete
        user_id: Optional user ID for access control

    Returns:
        dict: Manifest with ordered_files, dependencies, and context
    """
    from app.services.content_prep_agent import ContentPrepAgent

    logger.info(f"Generating manifest for content set: {content_set_id}")

    try:
        agent = ContentPrepAgent()
        result = run_async(agent.generate_manifest(
            content_set_id=content_set_id,
            proceed_incomplete=proceed_incomplete
        ))

        return {
            "status": "success",
            "manifest_id": result.get("manifest_id"),
            "content_set_id": content_set_id,
            "content_set_name": result.get("content_set_name"),
            "ordered_files": result.get("ordered_files", []),
            "total_files": result.get("total_files", 0),
            "warnings": result.get("warnings", []),
            "estimated_time_seconds": result.get("estimated_time_seconds", 0),
            "context": result.get("context", {}),
            "created_at": result.get("created_at", datetime.utcnow().isoformat())
        }

    except ValueError as e:
        error_msg = str(e)
        if "incomplete" in error_msg.lower():
            return {
                "status": "error",
                "error": error_msg,
                "action_required": "Set proceed_incomplete=true to proceed with incomplete set",
                "content_set_id": content_set_id
            }
        logger.warning(f"Manifest generation failed: {error_msg}")
        return {
            "status": "error",
            "error": error_msg,
            "content_set_id": content_set_id
        }
    except Exception as e:
        logger.error(f"Manifest generation failed: {e}", exc_info=True)
        raise


# ============================================================================
# Content Set Processing Task
# ============================================================================

@celery_app.task(
    name='app.tasks.content_prep_tasks.process_content_set',
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    autoretry_for=(Exception,),
    retry_backoff=True,
    queue='content_prep'
)
def process_content_set(
    self,
    content_set_id: str,
    proceed_incomplete: bool = False,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process an entire content set in order.

    1. Validates the content set
    2. Generates a manifest
    3. Triggers ordered processing for each file

    Args:
        content_set_id: UUID of the content set to process
        proceed_incomplete: Allow processing even if set is incomplete
        user_id: Optional user ID for access control

    Returns:
        dict: Processing result with status and triggered tasks
    """
    from app.services.content_prep_agent import ContentPrepAgent
    from app.tasks.source_processing import process_source

    logger.info(f"Processing content set: {content_set_id}")

    try:
        agent = ContentPrepAgent()

        # Step 1: Validate the content set
        validation = run_async(agent.validate_completeness(content_set_id))

        if not validation.get("is_complete") and not proceed_incomplete:
            return {
                "status": "blocked",
                "error": "Content set is incomplete",
                "missing_files": validation.get("missing_files", []),
                "action_required": "Set proceed_incomplete=true to proceed",
                "content_set_id": content_set_id
            }

        # Step 2: Generate manifest
        manifest = run_async(agent.generate_manifest(
            content_set_id=content_set_id,
            proceed_incomplete=proceed_incomplete
        ))

        # Step 3: Trigger ordered processing
        ordered_files = manifest.get("ordered_files", [])
        triggered_tasks = []
        content_set_context = manifest.get("context", {})

        for file_info in ordered_files:
            # Get the source_id for this file (from B2 path lookup)
            # In production, this would query the database for the source record
            b2_path = file_info.get("b2_path")
            sequence = file_info.get("sequence", 0)

            # Trigger processing with content set context
            # Note: process_source expects source_id, so we need to map B2 path to source
            # For now, we'll store the task info for the caller to handle
            triggered_tasks.append({
                "sequence": sequence,
                "file": file_info.get("file"),
                "b2_path": b2_path,
                "dependencies": file_info.get("dependencies", []),
                "content_set_context": content_set_context
            })

        logger.info(f"Content set {content_set_id} ready for processing: {len(triggered_tasks)} files")

        return {
            "status": "success",
            "content_set_id": content_set_id,
            "manifest_id": manifest.get("manifest_id"),
            "total_files": len(triggered_tasks),
            "files_to_process": triggered_tasks,
            "warnings": manifest.get("warnings", []),
            "content_set_context": content_set_context,
            "processed_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Content set processing failed: {e}", exc_info=True)
        raise


# ============================================================================
# Batch Analysis Task
# ============================================================================

@celery_app.task(
    name='app.tasks.content_prep_tasks.analyze_pending_folders',
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue='content_prep'
)
def analyze_pending_folders(
    self,
    folders: Optional[List[str]] = None,
    detection_mode: str = "auto",
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze multiple B2 folders for content sets.

    If no folders specified, analyzes the default pending folder.

    Args:
        folders: List of B2 folder paths to analyze
        detection_mode: Detection strategy
        user_id: Optional user ID for access control

    Returns:
        dict: Aggregated results from all folders
    """
    folders = folders or ["pending/courses/"]

    logger.info(f"Analyzing {len(folders)} folders for content sets")

    all_content_sets = []
    all_standalone = []
    folder_results = []

    for folder in folders:
        try:
            result = detect_content_sets(
                b2_folder=folder,
                detection_mode=detection_mode,
                user_id=user_id
            )

            if result.get("status") == "success":
                all_content_sets.extend(result.get("content_sets", []))
                all_standalone.extend(result.get("standalone_files", []))
                folder_results.append({
                    "folder": folder,
                    "status": "success",
                    "content_sets_count": len(result.get("content_sets", [])),
                    "standalone_count": len(result.get("standalone_files", []))
                })
            else:
                folder_results.append({
                    "folder": folder,
                    "status": "error",
                    "error": result.get("error")
                })

        except Exception as e:
            logger.error(f"Failed to analyze folder {folder}: {e}")
            folder_results.append({
                "folder": folder,
                "status": "error",
                "error": str(e)
            })

    return {
        "status": "success",
        "folders_analyzed": len(folders),
        "total_content_sets": len(all_content_sets),
        "total_standalone_files": len(all_standalone),
        "folder_results": folder_results,
        "content_sets": all_content_sets,
        "standalone_files": all_standalone,
        "analyzed_at": datetime.utcnow().isoformat()
    }


# ============================================================================
# Clarification Task (Task 129: Chat-Based Ordering Clarification)
# ============================================================================

@celery_app.task(
    name='app.tasks.content_prep_tasks.clarify_ordering_async',
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    queue='content_prep'
)
def clarify_ordering_async(
    self,
    content_set_id: str,
    user_id: str,
    confidence_threshold: float = 0.8,
    timeout_seconds: int = 3600,
) -> Dict[str, Any]:
    """
    Async task to resolve file ordering with user clarification.

    This task handles the long-polling clarification flow in the background,
    allowing the API to return immediately while the agent waits for user response.

    Args:
        content_set_id: UUID of the content set to order
        user_id: User ID for chat communication
        confidence_threshold: Confidence below which to request clarification
        timeout_seconds: How long to wait for user response

    Returns:
        dict: Ordering result with clarification status
    """
    from app.services.content_prep_agent import ContentPrepAgent

    logger.info(
        f"Starting async clarification for content set: {content_set_id} "
        f"(threshold: {confidence_threshold}, timeout: {timeout_seconds}s)"
    )

    try:
        agent = ContentPrepAgent()
        result = run_async(agent.resolve_order_with_clarification(
            content_set_id=content_set_id,
            user_id=user_id,
            confidence_threshold=confidence_threshold,
            timeout_seconds=timeout_seconds,
        ))

        logger.info(
            f"Clarification complete for {content_set_id}: "
            f"confidence={result.get('ordering_confidence')}, "
            f"clarification_requested={result.get('clarification_requested')}"
        )

        return result

    except Exception as e:
        logger.error(f"Clarification task failed for {content_set_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "content_set_id": content_set_id,
        }


# ============================================================================
# Cleanup Task (for 90-day retention) - Task 130
# ============================================================================

@celery_app.task(
    name='app.tasks.content_prep_tasks.cleanup_old_content_sets',
    bind=True,
    max_retries=1,
    queue='content_prep'
)
def cleanup_old_content_sets(
    self,
    retention_days: int = 90
) -> Dict[str, Any]:
    """
    Clean up content sets older than retention period.

    Removes completed content set records after 90 days (configurable).
    Instrumented with Prometheus metrics for monitoring.

    Args:
        retention_days: Number of days to retain completed sets (default 90)

    Returns:
        dict: Cleanup results with count of removed sets
    """
    import time
    from app.core.supabase_client import get_supabase_client
    from datetime import timedelta

    # Import metrics for instrumentation
    from app.services.monitoring_service import (
        RETENTION_CLEANUP_RUNS,
        RETENTION_CLEANUP_DELETED,
        RETENTION_CLEANUP_DURATION,
        CONTENT_SETS_DELETED,
    )

    logger.info(f"Cleaning up content sets older than {retention_days} days")
    start_time = time.time()

    try:
        supabase = get_supabase_client()
        cutoff_date = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()

        # Find completed content sets older than retention period
        result = supabase.table("content_sets").select("id").eq(
            "processing_status", "complete"
        ).lt("completed_at", cutoff_date).execute()

        sets_to_delete = [r["id"] for r in result.data] if result.data else []

        if not sets_to_delete:
            # Record successful run with no deletions
            duration = time.time() - start_time
            RETENTION_CLEANUP_RUNS.labels(status="success").inc()
            RETENTION_CLEANUP_DURATION.observe(duration)

            return {
                "status": "success",
                "message": "No content sets to clean up",
                "deleted_count": 0,
                "retention_days": retention_days,
                "duration_seconds": round(duration, 2)
            }

        # Delete old content sets in batches (cascade will handle related records)
        batch_size = 50
        deleted_count = 0

        for i in range(0, len(sets_to_delete), batch_size):
            batch = sets_to_delete[i:i + batch_size]
            for set_id in batch:
                supabase.table("content_sets").delete().eq("id", set_id).execute()
                deleted_count += 1

            logger.info(f"Deleted batch {i // batch_size + 1}: {len(batch)} content sets")

        # Record metrics
        duration = time.time() - start_time
        RETENTION_CLEANUP_RUNS.labels(status="success").inc()
        RETENTION_CLEANUP_DELETED.inc(deleted_count)
        RETENTION_CLEANUP_DURATION.observe(duration)
        CONTENT_SETS_DELETED.labels(reason="retention_policy").inc(deleted_count)

        logger.info(f"Cleaned up {deleted_count} old content sets in {duration:.2f}s")

        return {
            "status": "success",
            "deleted_count": deleted_count,
            "deleted_ids": sets_to_delete,
            "retention_days": retention_days,
            "cutoff_date": cutoff_date,
            "duration_seconds": round(duration, 2),
            "cleaned_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        # Record failed run
        duration = time.time() - start_time
        RETENTION_CLEANUP_RUNS.labels(status="error").inc()
        RETENTION_CLEANUP_DURATION.observe(duration)

        logger.error(f"Content set cleanup failed: {e}", exc_info=True)
        raise
