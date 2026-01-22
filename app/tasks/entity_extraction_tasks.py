"""
Empire v7.3 - Entity Extraction Tasks (Task 155)

Celery tasks for asynchronous entity extraction from research tasks.
Uses Claude Haiku for fast, cost-effective extraction with Neo4j storage.

Author: Claude Code
Date: 2025-01-15
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

import structlog

from app.celery_app import celery_app
from app.core.connections import get_supabase

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
# Task: Extract Entities from Research Task
# ==============================================================================

@celery_app.task(
    name='app.tasks.entity_extraction_tasks.extract_entities_task',
    bind=True,
    max_retries=3,
    default_retry_delay=30
)
def extract_entities_task(
    self,
    task_id: str,
    title: str,
    content: str,
    description: str = "",
    store_in_graph: bool = True
) -> Dict[str, Any]:
    """
    Background task to extract entities from research task content.

    This task:
    1. Uses Claude Haiku for fast entity extraction
    2. Extracts topics, entities, facts, and relationships
    3. Stores results in Neo4j graph database
    4. Updates the task status

    Args:
        task_id: The research task ID
        title: Task title
        content: Main content to extract entities from
        description: Optional task description
        store_in_graph: Whether to store results in Neo4j

    Returns:
        Dict with extraction status and results summary
    """
    try:
        logger.info(
            "Starting entity extraction task",
            task_id=task_id,
            celery_task_id=self.request.id,
            content_length=len(content)
        )

        # Import service here to avoid circular imports
        from app.services.entity_extraction_service import get_entity_extraction_service

        service = get_entity_extraction_service()

        # Run the async extraction in sync context
        result = run_async(
            service.extract_entities(
                task_id=task_id,
                title=title,
                description=description,
                content=content,
                store_in_graph=store_in_graph
            )
        )

        logger.info(
            "Entity extraction task completed",
            task_id=task_id,
            topics_count=len(result.extraction_result.topics),
            entities_count=len(result.extraction_result.entities),
            facts_count=len(result.extraction_result.facts),
            relationships_count=len(result.extraction_result.relationships)
        )

        return {
            "success": True,
            "task_id": task_id,
            "extraction": {
                "topics_count": len(result.extraction_result.topics),
                "entities_count": len(result.extraction_result.entities),
                "facts_count": len(result.extraction_result.facts),
                "relationships_count": len(result.extraction_result.relationships),
                "stored_in_graph": result.graph_storage_success
            },
            "model_used": result.model_used,
            "processing_time_ms": result.processing_time_ms
        }

    except Exception as e:
        logger.error(
            "Entity extraction task failed",
            task_id=task_id,
            error=str(e),
            retry_count=self.request.retries
        )

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "success": False,
            "task_id": task_id,
            "error": str(e)
        }


# ==============================================================================
# Task: Batch Extract Entities
# ==============================================================================

@celery_app.task(
    name='app.tasks.entity_extraction_tasks.batch_extract_entities',
    bind=True,
    max_retries=2
)
def batch_extract_entities(
    self,
    tasks: list[Dict[str, Any]],
    store_in_graph: bool = True
) -> Dict[str, Any]:
    """
    Process multiple entity extraction tasks in batch.

    Args:
        tasks: List of task dicts with task_id, title, content, description
        store_in_graph: Whether to store results in Neo4j

    Returns:
        Dict with batch processing results
    """
    try:
        logger.info(
            "Starting batch entity extraction",
            task_count=len(tasks),
            celery_task_id=self.request.id
        )

        from app.services.entity_extraction_service import get_entity_extraction_service

        service = get_entity_extraction_service()
        results = []
        failed = []

        for task_data in tasks:
            try:
                result = run_async(
                    service.extract_entities(
                        task_id=task_data["task_id"],
                        title=task_data["title"],
                        description=task_data.get("description", ""),
                        content=task_data["content"],
                        store_in_graph=store_in_graph
                    )
                )

                results.append({
                    "task_id": task_data["task_id"],
                    "success": True,
                    "topics_count": len(result.extraction_result.topics),
                    "entities_count": len(result.extraction_result.entities)
                })

            except Exception as e:
                logger.warning(
                    "Single extraction failed in batch",
                    task_id=task_data["task_id"],
                    error=str(e)
                )
                failed.append({
                    "task_id": task_data["task_id"],
                    "error": str(e)
                })

        logger.info(
            "Batch entity extraction completed",
            total=len(tasks),
            succeeded=len(results),
            failed=len(failed)
        )

        return {
            "success": True,
            "total_tasks": len(tasks),
            "succeeded": len(results),
            "failed": len(failed),
            "results": results,
            "failures": failed
        }

    except Exception as e:
        logger.error(
            "Batch entity extraction failed",
            error=str(e)
        )

        return {
            "success": False,
            "error": str(e)
        }


# ==============================================================================
# Task: Extract Entities from Research Job
# ==============================================================================

@celery_app.task(
    name='app.tasks.entity_extraction_tasks.extract_entities_for_job',
    bind=True,
    max_retries=2
)
def extract_entities_for_job(
    self,
    job_id: int
) -> Dict[str, Any]:
    """
    Extract entities from all completed tasks in a research job.

    This task:
    1. Fetches all completed tasks for the job
    2. Extracts entities from each task's artifacts
    3. Stores entities in Neo4j graph

    Args:
        job_id: The research job ID

    Returns:
        Dict with extraction results for the job
    """
    try:
        logger.info(
            "Starting entity extraction for research job",
            job_id=job_id,
            celery_task_id=self.request.id
        )

        supabase = get_supabase()

        # Get all completed tasks for this job
        tasks_result = supabase.table("plan_tasks").select("*").eq(
            "job_id", job_id
        ).eq("status", "complete").execute()

        tasks = tasks_result.data or []

        if not tasks:
            logger.warning("No completed tasks found for job", job_id=job_id)
            return {
                "success": True,
                "job_id": job_id,
                "message": "No completed tasks to extract entities from",
                "tasks_processed": 0
            }

        # Get artifacts for these tasks
        task_ids = [t["id"] for t in tasks]
        artifacts_result = supabase.table("research_artifacts").select("*").in_(
            "task_id", task_ids
        ).execute()

        artifacts = artifacts_result.data or []

        if not artifacts:
            logger.warning("No artifacts found for completed tasks", job_id=job_id)
            return {
                "success": True,
                "job_id": job_id,
                "message": "No artifacts to extract entities from",
                "tasks_processed": 0
            }

        # Extract entities from artifacts
        from app.services.entity_extraction_service import get_entity_extraction_service

        service = get_entity_extraction_service()
        extracted_count = 0
        errors = []

        for artifact in artifacts:
            try:
                # Extract from artifact content
                content = artifact.get("content", "") or artifact.get("summary", "")
                if not content or len(content) < 50:
                    continue

                run_async(
                    service.extract_entities(
                        task_id=f"job-{job_id}-artifact-{artifact['id']}",
                        title=artifact.get("title", f"Artifact {artifact['id']}"),
                        description=f"From research job {job_id}",
                        content=content,
                        store_in_graph=True
                    )
                )
                extracted_count += 1

            except Exception as e:
                errors.append({
                    "artifact_id": artifact["id"],
                    "error": str(e)
                })

        logger.info(
            "Entity extraction for job completed",
            job_id=job_id,
            artifacts_processed=extracted_count,
            errors=len(errors)
        )

        return {
            "success": True,
            "job_id": job_id,
            "artifacts_processed": extracted_count,
            "total_artifacts": len(artifacts),
            "errors": errors if errors else None
        }

    except Exception as e:
        logger.error(
            "Entity extraction for job failed",
            job_id=job_id,
            error=str(e)
        )

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "success": False,
            "job_id": job_id,
            "error": str(e)
        }
