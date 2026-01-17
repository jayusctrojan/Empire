"""
Empire v7.3 - Agent Feedback Routes
Task 188: Agent Feedback System

API endpoints for managing feedback on AI agent outputs.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
import structlog

from app.services.feedback_service import (
    get_feedback_service,
    FeedbackType,
    AgentId,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])


# =============================================================================
# Pydantic Models
# =============================================================================


class FeedbackCreate(BaseModel):
    """Model for creating feedback"""
    agent_id: str = Field(..., description="Agent identifier")
    feedback_type: str = Field(..., description="Type of feedback")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    input_summary: Optional[str] = Field(None, max_length=500, description="Summary of input")
    output_summary: Optional[str] = Field(None, max_length=500, description="Summary of output")
    feedback_text: Optional[str] = Field(None, description="Free-text feedback")
    task_id: Optional[str] = Field(None, description="Related task ID")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    user_id: Optional[str] = Field(None, description="User providing feedback")

    @validator('feedback_type')
    def validate_feedback_type(cls, v):
        valid_types = [t.value for t in FeedbackType]
        if v not in valid_types:
            # Allow custom types but log warning
            logger.warning("Non-standard feedback type used", feedback_type=v)
        return v


class FeedbackResponse(BaseModel):
    """Model for feedback response"""
    id: str
    agent_id: str
    feedback_type: str
    rating: int
    input_summary: Optional[str]
    output_summary: Optional[str]
    feedback_text: Optional[str]
    task_id: Optional[str]
    metadata: Dict[str, Any]
    created_at: str
    created_by: Optional[str]


class FeedbackStats(BaseModel):
    """Model for feedback statistics"""
    count: int
    average_rating: float
    rating_distribution: Dict[str, int]


class CreateFeedbackResponse(BaseModel):
    """Response model for feedback creation"""
    success: bool
    feedback_id: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "",
    response_model=CreateFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit agent feedback",
    description="Submit feedback for an AI agent's output"
)
async def create_feedback(feedback: FeedbackCreate):
    """
    Submit feedback for an agent's output.

    This endpoint allows users to provide ratings and comments on
    AI agent outputs for quality monitoring and improvement.
    """
    try:
        service = get_feedback_service()
        result = service.store_feedback(
            agent_id=feedback.agent_id,
            feedback_type=feedback.feedback_type,
            rating=feedback.rating,
            input_summary=feedback.input_summary,
            output_summary=feedback.output_summary,
            feedback_text=feedback.feedback_text,
            task_id=feedback.task_id,
            metadata=feedback.metadata,
            user_id=feedback.user_id
        )

        return CreateFeedbackResponse(
            success=result.get("success", False),
            feedback_id=result.get("feedback_id")
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create feedback", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to store feedback")


@router.get(
    "/{feedback_id}",
    response_model=FeedbackResponse,
    summary="Get feedback by ID",
    description="Retrieve a specific feedback record"
)
async def get_feedback(feedback_id: str):
    """Get a specific feedback record by its ID."""
    try:
        service = get_feedback_service()
        feedback = service.get_feedback(feedback_id)

        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        return feedback

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get feedback", error=str(e), feedback_id=feedback_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve feedback")


@router.get(
    "/agent/{agent_id}",
    response_model=List[FeedbackResponse],
    summary="Get agent feedback",
    description="Get all feedback for a specific agent"
)
async def get_agent_feedback(
    agent_id: str,
    feedback_type: Optional[str] = Query(None, description="Filter by feedback type"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Records to skip")
):
    """Get feedback for a specific agent with optional filtering."""
    try:
        service = get_feedback_service()
        feedback_list = service.get_agent_feedback(
            agent_id=agent_id,
            limit=limit,
            offset=offset,
            feedback_type=feedback_type
        )

        return feedback_list

    except Exception as e:
        logger.error("Failed to get agent feedback", error=str(e), agent_id=agent_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve feedback")


@router.get(
    "/type/{feedback_type}",
    response_model=List[FeedbackResponse],
    summary="Get feedback by type",
    description="Get all feedback of a specific type"
)
async def get_feedback_by_type(
    feedback_type: str,
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Records to skip")
):
    """Get feedback filtered by feedback type."""
    try:
        service = get_feedback_service()
        feedback_list = service.get_feedback_by_type(
            feedback_type=feedback_type,
            limit=limit,
            offset=offset
        )

        return feedback_list

    except Exception as e:
        logger.error("Failed to get feedback by type", error=str(e), feedback_type=feedback_type)
        raise HTTPException(status_code=500, detail="Failed to retrieve feedback")


@router.get(
    "/stats",
    response_model=FeedbackStats,
    summary="Get feedback statistics",
    description="Get aggregated feedback statistics"
)
async def get_feedback_stats(
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    feedback_type: Optional[str] = Query(None, description="Filter by feedback type")
):
    """Get aggregated feedback statistics with optional filtering."""
    try:
        service = get_feedback_service()
        stats = service.get_feedback_stats(
            agent_id=agent_id,
            feedback_type=feedback_type
        )

        return stats

    except Exception as e:
        logger.error("Failed to get feedback stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.get(
    "/stats/all-agents",
    response_model=Dict[str, FeedbackStats],
    summary="Get all agent statistics",
    description="Get feedback statistics for all agents"
)
async def get_all_agent_stats():
    """Get feedback statistics for all agents."""
    try:
        service = get_feedback_service()
        stats = service.get_all_agent_stats()

        return stats

    except Exception as e:
        logger.error("Failed to get all agent stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.get(
    "/low-ratings",
    response_model=List[FeedbackResponse],
    summary="Get low-rated feedback",
    description="Get recent feedback with low ratings for review"
)
async def get_low_ratings(
    threshold: int = Query(2, ge=1, le=5, description="Maximum rating to include"),
    limit: int = Query(10, ge=1, le=100, description="Maximum records to return")
):
    """Get recent feedback with low ratings for quality review."""
    try:
        service = get_feedback_service()
        feedback_list = service.get_recent_low_ratings(
            threshold=threshold,
            limit=limit
        )

        return feedback_list

    except Exception as e:
        logger.error("Failed to get low ratings", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve feedback")


@router.get(
    "/agents",
    summary="List available agents",
    description="Get list of known agent identifiers"
)
async def list_agents():
    """List all known agent identifiers that can receive feedback."""
    return {
        "agents": [a.value for a in AgentId],
        "feedback_types": [t.value for t in FeedbackType]
    }


@router.get(
    "/health",
    summary="Feedback service health",
    description="Check if feedback service is healthy"
)
async def health_check():
    """Health check for the feedback service."""
    try:
        service = get_feedback_service()
        # Simple check - just verify we can initialize
        service._get_supabase()

        return {
            "status": "healthy",
            "service": "feedback",
            "message": "Feedback service is operational"
        }

    except Exception as e:
        logger.error("Feedback service health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "feedback",
            "message": str(e)
        }
