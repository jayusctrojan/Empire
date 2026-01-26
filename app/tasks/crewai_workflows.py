"""
Empire v7.3 - CrewAI Workflow Tasks
Celery tasks for multi-agent content analysis and asset generation (Milestone 8)
"""

from app.celery_app import celery_app
from app.services.crewai_service import CrewAIService
from app.core.connections import get_supabase
from typing import Dict, Any, List
import structlog

logger = structlog.get_logger(__name__)


@celery_app.task(name='app.tasks.crewai_workflows.execute_crew_async', bind=True)
def execute_crew_async(
    self,
    execution_id: str,
    crew_id: str,
    input_data: Dict[str, Any],
    agent_ids: List[str],
    process_type: str = "sequential",
    memory_enabled: bool = True,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Execute a CrewAI workflow asynchronously via Celery.

    This task is queued immediately and executes the external CrewAI service
    in the background, updating the database when complete.

    Args:
        execution_id: UUID of the execution record (already created)
        crew_id: UUID of the crew to execute
        input_data: Input data for the workflow
        agent_ids: List of agent IDs in the crew
        process_type: Execution process type (sequential/hierarchical)
        memory_enabled: Whether to enable crew memory
        verbose: Whether to enable verbose logging

    Returns:
        Execution result with status and outputs
    """
    import requests
    import os
    from datetime import datetime

    try:
        logger.info(
            "Async crew execution started",
            execution_id=execution_id,
            crew_id=crew_id,
            task_id=self.request.id,
            agent_count=len(agent_ids)
        )

        # Get Supabase client
        supabase = get_supabase()

        # Update execution status to "running"
        supabase.table("crewai_executions").update({
            "status": "running",
            "celery_task_id": self.request.id,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", execution_id).execute()

        # Call external CrewAI service
        crewai_base_url = os.getenv("CREWAI_SERVICE_URL", "https://jb-crewai.onrender.com")

        response = requests.post(
            f"{crewai_base_url}/api/crew/execute",
            json={
                "crew_id": crew_id,
                "agents": agent_ids,
                "input_data": input_data,
                "execution_id": execution_id,
                "process_type": process_type,
                "memory_enabled": memory_enabled,
                "verbose": verbose
            },
            timeout=300  # 5 minute timeout
        )

        if response.status_code == 200:
            # Workflow completed successfully
            workflow_result = response.json()

            # Validate output quality (Task 38.5)
            validation_result = None
            quality_metrics = {}

            try:
                from app.services.crewai_output_validator import get_output_validator

                # Get agent roles for validation
                agent_roles_response = supabase.table("crewai_agents") \
                    .select("role") \
                    .in_("id", agent_ids) \
                    .execute()

                agent_roles = [a["role"] for a in agent_roles_response.data]

                # Validate output
                validator = get_output_validator()
                validation_result = validator.validate_execution_output(
                    workflow_result,
                    agent_roles
                )

                quality_metrics = {
                    "validation": {
                        "is_valid": validation_result.is_valid,
                        "quality_score": validation_result.quality_score,
                        "errors": validation_result.errors,
                        "warnings": validation_result.warnings,
                        "recommendations": validation_result.recommendations,
                        "metrics": validation_result.metrics
                    }
                }

                logger.info(
                    "Output validation completed",
                    execution_id=execution_id,
                    quality_score=validation_result.quality_score,
                    is_valid=validation_result.is_valid,
                    errors_count=len(validation_result.errors),
                    warnings_count=len(validation_result.warnings)
                )

            except Exception as val_error:
                logger.warning("Output validation failed", error=str(val_error))
                quality_metrics = {"validation_error": str(val_error)}

            # Update execution with results and validation
            update_data = {
                "status": "completed",
                "completed_tasks": workflow_result.get("completed_tasks", len(agent_ids)),
                "results": workflow_result.get("results"),
                "execution_time_ms": workflow_result.get("execution_time_ms"),
                "completed_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            # Add quality metrics to metadata if validation succeeded
            if quality_metrics:
                existing_metadata = workflow_result.get("metadata", {})
                existing_metadata.update(quality_metrics)
                update_data["metadata"] = existing_metadata

            supabase.table("crewai_executions").update(update_data).eq("id", execution_id).execute()

            logger.info(
                "Async crew execution completed",
                execution_id=execution_id,
                crew_id=crew_id,
                task_id=self.request.id
            )

            # Send WebSocket notification (imported at function level to avoid circular imports)
            try:
                from app.core.websockets import broadcast_execution_update
                broadcast_execution_update(execution_id, {
                    "status": "completed",
                    "execution_id": execution_id,
                    "results": workflow_result.get("results")
                })
            except Exception as ws_error:
                logger.warning("Failed to send WebSocket notification", error=str(ws_error))

            return {
                "status": "completed",
                "execution_id": execution_id,
                "crew_id": crew_id,
                "results": workflow_result.get("results"),
                "celery_task_id": self.request.id
            }
        else:
            # Workflow failed
            error_msg = f"CrewAI service error: {response.text}"

            supabase.table("crewai_executions").update({
                "status": "failed",
                "error_message": error_msg,
                "completed_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", execution_id).execute()

            logger.error(
                "Async crew execution failed",
                execution_id=execution_id,
                error=error_msg,
                task_id=self.request.id
            )

            raise RuntimeError(error_msg)

    except requests.exceptions.Timeout:
        # Timeout error
        error_msg = "Execution timeout (>5 minutes)"

        supabase.table("crewai_executions").update({
            "status": "failed",
            "error_message": error_msg,
            "completed_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", execution_id).execute()

        logger.error("Crew execution timeout", execution_id=execution_id, task_id=self.request.id)
        raise RuntimeError(error_msg)

    except Exception as e:
        # General error
        error_msg = str(e)

        try:
            supabase = get_supabase()
            supabase.table("crewai_executions").update({
                "status": "failed",
                "error_message": error_msg,
                "completed_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", execution_id).execute()
        except Exception as db_error:
            logger.error("Failed to update execution status", error=str(db_error))

        logger.error(
            "Async crew execution failed",
            execution_id=execution_id,
            crew_id=crew_id,
            task_id=self.request.id,
            error=error_msg
        )

        # Retry with exponential backoff
        self.retry(exc=e, countdown=120, max_retries=2)


@celery_app.task(name='app.tasks.crewai_workflows.analyze_document_multi_agent', bind=True)
def analyze_document_multi_agent(
    self,
    document_id: str,
    analysis_type: str = "comprehensive",
    user_id: str = None
) -> Dict[str, Any]:
    """
    Run multi-agent analysis workflow via CrewAI service.

    Args:
        document_id: Unique document identifier
        analysis_type: Type of analysis (e.g., 'comprehensive', 'technical', 'summary')
        user_id: Optional user ID for tracking

    Returns:
        Analysis result from CrewAI workflow
    """
    try:
        logger.info(
            "Document analysis started",
            document_id=document_id,
            analysis_type=analysis_type,
            task_id=self.request.id
        )

        # Get Supabase client
        supabase = get_supabase()

        # Create CrewAI service
        crewai_service = CrewAIService(supabase=supabase)

        # Find or create analysis crew
        # For now, we'll use the first active crew or create a default one
        crews = crewai_service.get_crews(active_only=True)

        if not crews:
            logger.warning("No active crews found, analysis cannot proceed")
            return {
                "status": "error",
                "message": "No active crews available for analysis",
                "document_id": document_id
            }

        # Use first crew (in production, would select based on analysis_type)
        crew = crews[0]

        # Prepare input data
        input_data = {
            "document_id": document_id,
            "analysis_type": analysis_type,
            "task": f"Perform {analysis_type} analysis on document {document_id}"
        }

        # Execute crew
        result = crewai_service.execute_crew(
            crew_id=crew["id"],
            input_data=input_data,
            document_id=document_id,
            user_id=user_id,
            execution_type="document_analysis"
        )

        logger.info(
            "Document analysis completed",
            document_id=document_id,
            execution_id=result.get("id"),
            task_id=self.request.id
        )

        return {
            "status": "success",
            "document_id": document_id,
            "analysis_type": analysis_type,
            "execution_id": result.get("id"),
            "results": result.get("results"),
            "celery_task_id": self.request.id
        }

    except Exception as e:
        logger.error(
            "Document analysis failed",
            document_id=document_id,
            task_id=self.request.id,
            error=str(e)
        )
        self.retry(exc=e, countdown=120, max_retries=2)


@celery_app.task(name='app.tasks.crewai_workflows.generate_assets', bind=True)
def generate_assets(
    self,
    document_id: str,
    asset_types: List[str],
    user_id: str = None
) -> Dict[str, Any]:
    """
    Generate assets (summaries, flashcards, study guides) using CrewAI agents.

    Args:
        document_id: Unique document identifier
        asset_types: Types of assets to generate (e.g., ['summary', 'flashcards', 'quiz'])
        user_id: Optional user ID for tracking

    Returns:
        Asset generation result
    """
    try:
        logger.info(
            "Asset generation started",
            document_id=document_id,
            asset_types=asset_types,
            task_id=self.request.id
        )

        # Get Supabase client
        supabase = get_supabase()

        # Create CrewAI service
        crewai_service = CrewAIService(supabase=supabase)

        # Find active crews for asset generation
        crews = crewai_service.get_crews(active_only=True)

        if not crews:
            logger.warning("No active crews found for asset generation")
            return {
                "status": "error",
                "message": "No active crews available for asset generation",
                "document_id": document_id
            }

        # Use first crew (in production, would select specialized asset generation crew)
        crew = crews[0]

        # Prepare input data
        input_data = {
            "document_id": document_id,
            "asset_types": asset_types,
            "task": f"Generate {', '.join(asset_types)} for document {document_id}"
        }

        # Execute crew
        result = crewai_service.execute_crew(
            crew_id=crew["id"],
            input_data=input_data,
            document_id=document_id,
            user_id=user_id,
            execution_type="asset_generation"
        )

        logger.info(
            "Asset generation completed",
            document_id=document_id,
            execution_id=result.get("id"),
            task_id=self.request.id
        )

        return {
            "status": "success",
            "document_id": document_id,
            "assets_generated": len(asset_types),
            "execution_id": result.get("id"),
            "results": result.get("results"),
            "celery_task_id": self.request.id
        }

    except Exception as e:
        logger.error(
            "Asset generation failed",
            document_id=document_id,
            task_id=self.request.id,
            error=str(e)
        )
        self.retry(exc=e, countdown=120, max_retries=2)


@celery_app.task(name='app.tasks.crewai_workflows.batch_analyze_documents', bind=True)
def batch_analyze_documents(
    self,
    document_ids: List[str],
    analysis_type: str = "comprehensive",
    user_id: str = None
) -> Dict[str, Any]:
    """
    Batch analyze multiple documents using CrewAI multi-agent workflows.

    Args:
        document_ids: List of document IDs to analyze
        analysis_type: Type of analysis to perform
        user_id: Optional user ID for tracking

    Returns:
        Batch analysis results
    """
    try:
        logger.info(
            "Batch document analysis started",
            document_count=len(document_ids),
            analysis_type=analysis_type,
            task_id=self.request.id
        )

        results = []

        for doc_id in document_ids:
            try:
                # Trigger individual analysis tasks
                task = analyze_document_multi_agent.apply_async(
                    args=[doc_id, analysis_type, user_id]
                )
                results.append({
                    "document_id": doc_id,
                    "celery_task_id": task.id,
                    "status": "queued"
                })
            except Exception as e:
                logger.error("Failed to queue document analysis", document_id=doc_id, error=str(e))
                results.append({
                    "document_id": doc_id,
                    "status": "error",
                    "error": str(e)
                })

        logger.info(
            "Batch document analysis queued",
            total=len(document_ids),
            successful=len([r for r in results if r["status"] == "queued"]),
            task_id=self.request.id
        )

        return {
            "status": "success",
            "total_documents": len(document_ids),
            "queued": len([r for r in results if r["status"] == "queued"]),
            "results": results,
            "celery_task_id": self.request.id
        }

    except Exception as e:
        logger.error("Batch document analysis failed", task_id=self.request.id, error=str(e))
        self.retry(exc=e, countdown=120, max_retries=2)
