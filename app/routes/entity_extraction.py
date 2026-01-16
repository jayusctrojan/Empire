"""
Empire v7.3 - Entity Extraction API Routes (Task 155)

API endpoints for Claude Haiku-based entity extraction from research tasks.
Provides synchronous and asynchronous extraction capabilities with Neo4j storage.

Author: Claude Code
Date: 2025-01-15
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, status, BackgroundTasks
from pydantic import BaseModel, Field
import structlog

from app.middleware.auth import get_current_user
from app.services.entity_extraction_service import (
    EntityExtractionService,
    EntityExtractionResponse,
    ExtractionResult,
    get_entity_extraction_service,
)
from app.exceptions import (
    EntityExtractionException,
    InvalidExtractionResultException,
    EntityGraphStorageException,
    EntityExtractionTimeoutException,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/entity-extraction", tags=["Entity Extraction"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class EntityExtractionRequest(BaseModel):
    """Request for entity extraction"""
    task_id: str = Field(..., description="Unique identifier for the research task")
    title: str = Field(..., min_length=1, max_length=500, description="Task title")
    description: str = Field("", max_length=2000, description="Task description")
    content: str = Field(..., min_length=10, description="Main content to extract entities from")
    store_in_graph: bool = Field(True, description="Whether to store results in Neo4j")


class AsyncExtractionRequest(BaseModel):
    """Request for async entity extraction"""
    task_id: str = Field(..., description="Unique identifier for the research task")
    title: str = Field(..., min_length=1, max_length=500, description="Task title")
    description: str = Field("", max_length=2000, description="Task description")
    content: str = Field(..., min_length=10, description="Main content to extract entities from")
    store_in_graph: bool = Field(True, description="Whether to store results in Neo4j")
    callback_url: Optional[str] = Field(None, description="Optional URL to callback when complete")


class AsyncExtractionResponse(BaseModel):
    """Response for async extraction request"""
    accepted: bool = Field(..., description="Whether the request was accepted")
    task_id: str = Field(..., description="Task ID for tracking")
    message: str = Field(..., description="Status message")


class ServiceStatsResponse(BaseModel):
    """Service statistics response"""
    extractions_completed: int
    extractions_failed: int
    total_topics_extracted: int
    total_entities_extracted: int
    total_facts_extracted: int
    total_relationships_extracted: int
    service_name: str
    model: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    llm_available: bool
    neo4j_available: bool


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_service() -> EntityExtractionService:
    """Dependency for entity extraction service."""
    return get_entity_extraction_service()


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post(
    "/extract",
    response_model=EntityExtractionResponse,
    summary="Extract entities from content",
    description="Synchronously extract entities, topics, facts, and relationships from research content using Claude Haiku."
)
async def extract_entities(
    request: EntityExtractionRequest,
    user_id: str = Depends(get_current_user),
    service: EntityExtractionService = Depends(get_service),
) -> EntityExtractionResponse:
    """
    Extract entities from research task content.

    This endpoint:
    1. Analyzes the content using Claude Haiku
    2. Extracts topics, entities, facts, and relationships
    3. Optionally stores results in Neo4j graph database
    4. Returns structured extraction results

    - **task_id**: Unique identifier for tracking
    - **title**: Brief title of the content
    - **description**: Optional description/context
    - **content**: Main text content to analyze
    - **store_in_graph**: Whether to persist to Neo4j (default: true)
    """
    logger.info(
        "Entity extraction request received",
        task_id=request.task_id,
        user_id=user_id,
        content_length=len(request.content)
    )

    try:
        response = await service.extract_entities(
            task_id=request.task_id,
            title=request.title,
            description=request.description,
            content=request.content,
            store_in_graph=request.store_in_graph
        )

        return response

    except EntityExtractionTimeoutException as e:
        logger.error("Entity extraction timed out", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(e)
        )
    except InvalidExtractionResultException as e:
        logger.error("Invalid extraction result", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except EntityGraphStorageException as e:
        logger.warning("Graph storage failed but extraction succeeded", error=str(e))
        # Return partial success if extraction worked but storage failed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except EntityExtractionException as e:
        logger.error("Entity extraction failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/extract/async",
    response_model=AsyncExtractionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Async entity extraction",
    description="Asynchronously extract entities. Returns immediately with a task ID for polling."
)
async def extract_entities_async(
    request: AsyncExtractionRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    service: EntityExtractionService = Depends(get_service),
) -> AsyncExtractionResponse:
    """
    Submit an entity extraction request for async processing.

    The extraction will be processed in the background. Use the Celery task
    endpoint for production-grade async processing with status tracking.
    """
    logger.info(
        "Async entity extraction request",
        task_id=request.task_id,
        user_id=user_id
    )

    # Add to background tasks
    async def run_extraction():
        try:
            await service.extract_entities(
                task_id=request.task_id,
                title=request.title,
                description=request.description,
                content=request.content,
                store_in_graph=request.store_in_graph
            )
        except Exception as e:
            logger.error(
                "Background extraction failed",
                task_id=request.task_id,
                error=str(e)
            )

    background_tasks.add_task(run_extraction)

    return AsyncExtractionResponse(
        accepted=True,
        task_id=request.task_id,
        message="Entity extraction queued for processing"
    )


@router.get(
    "/task/{task_id}",
    response_model=ExtractionResult,
    summary="Get extracted entities for a task",
    description="Retrieve previously extracted entities from Neo4j for a given task."
)
async def get_task_entities(
    task_id: str,
    user_id: str = Depends(get_current_user),
    service: EntityExtractionService = Depends(get_service),
) -> ExtractionResult:
    """
    Retrieve previously extracted entities for a research task.

    Returns the entities, topics, facts, and relationships stored in Neo4j.
    """
    logger.info(
        "Get entities request",
        task_id=task_id,
        user_id=user_id
    )

    try:
        result = await service.get_entities_for_task(task_id)
        return result
    except EntityExtractionException as e:
        logger.error("Failed to get entities", task_id=task_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No entities found for task {task_id}"
        )


@router.get(
    "/stats",
    response_model=ServiceStatsResponse,
    summary="Get service statistics",
    description="Get statistics about entity extraction operations."
)
async def get_stats(
    user_id: str = Depends(get_current_user),
    service: EntityExtractionService = Depends(get_service),
) -> ServiceStatsResponse:
    """
    Get extraction service statistics.

    Returns counts of extractions performed, entities extracted, etc.
    """
    stats = service.get_stats()
    return ServiceStatsResponse(**stats)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health status of the entity extraction service."
)
async def health_check(
    service: EntityExtractionService = Depends(get_service),
) -> HealthResponse:
    """
    Check service health status.

    Returns availability status of required dependencies (LLM, Neo4j).
    """
    return HealthResponse(
        status="healthy",
        service="EntityExtractionService",
        llm_available=service.llm is not None,
        neo4j_available=service.neo4j is not None
    )
