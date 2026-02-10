"""
Empire v7.3 - AI Studio Feedback API Routes
Task 79: Implement Feedback Collection and Dashboard

Endpoints:
- GET /api/studio/feedback - List all feedback (filterable)
- GET /api/studio/feedback/stats - Get feedback statistics
- GET /api/studio/feedback/impact - Get feedback impact analysis
- GET /api/studio/feedback/summary - Get recent feedback summary
- GET /api/studio/feedback/{feedback_id} - Get feedback details
- POST /api/studio/feedback - Submit new feedback
- GET /api/studio/feedback/health - Health check
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field
import structlog

from app.middleware.auth import get_current_user
from app.services.feedback_service import (
    FeedbackService,
    Feedback,
    FeedbackFilters,
    FeedbackStats,
    FeedbackImpact,
    FeedbackNotFoundError,
    FeedbackSubmitError,
    FeedbackType,
    get_feedback_service,
)
from app.services.weights_service import (
    WeightsService,
    InvalidPresetError,
    WEIGHT_PRESETS,
    get_weights_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/studio/feedback", tags=["AI Studio Feedback"])


# ============================================================================
# Request/Response Models
# ============================================================================

class FeedbackResponse(BaseModel):
    """Feedback details response"""
    id: str
    userId: str
    feedbackType: str
    rating: Optional[int] = None
    sessionId: Optional[str] = None
    messageId: Optional[str] = None
    classificationId: Optional[str] = None
    assetId: Optional[str] = None
    queryText: Optional[str] = None
    responseText: Optional[str] = None
    feedbackText: Optional[str] = None
    improvementSuggestions: Optional[str] = None
    previousValue: Optional[Dict[str, Any]] = None
    newValue: Optional[Dict[str, Any]] = None
    wasRoutingCorrect: Optional[bool] = None
    agentId: Optional[str] = None
    department: Optional[str] = None
    confidenceBefore: Optional[float] = None
    keywordsBefore: List[str] = []
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    @classmethod
    def from_feedback(cls, f: Feedback) -> "FeedbackResponse":
        """Convert Feedback model to response"""
        return cls(
            id=f.id,
            userId=f.user_id,
            feedbackType=f.feedback_type,
            rating=f.rating,
            sessionId=f.session_id,
            messageId=f.message_id,
            classificationId=f.classification_id,
            assetId=f.asset_id,
            queryText=f.query_text,
            responseText=f.response_text,
            feedbackText=f.feedback_text,
            improvementSuggestions=f.improvement_suggestions,
            previousValue=f.previous_value,
            newValue=f.new_value,
            wasRoutingCorrect=f.was_routing_correct,
            agentId=f.agent_id,
            department=f.department,
            confidenceBefore=f.confidence_before,
            keywordsBefore=f.keywords_before or [],
            createdAt=f.created_at.isoformat() if f.created_at else None,
            updatedAt=f.updated_at.isoformat() if f.updated_at else None,
        )


class FeedbackListResponse(BaseModel):
    """Response for listing feedback"""
    feedback: List[FeedbackResponse]
    total: int
    skip: int
    limit: int


class FeedbackSubmitRequest(BaseModel):
    """Request to submit new feedback"""
    feedbackType: str = Field(..., description="Type of feedback")
    rating: Optional[int] = Field(None, ge=-1, le=1, description="Rating: -1, 0, or 1")
    sessionId: Optional[str] = Field(None, description="Related session ID")
    messageId: Optional[str] = Field(None, description="Related message ID")
    classificationId: Optional[str] = Field(None, description="Related classification ID")
    assetId: Optional[str] = Field(None, description="Related asset ID")
    queryText: Optional[str] = Field(None, description="Original query text")
    responseText: Optional[str] = Field(None, description="Response that was rated")
    feedbackText: Optional[str] = Field(None, max_length=2000, description="User's feedback text")
    improvementSuggestions: Optional[str] = Field(None, max_length=2000, description="Suggestions for improvement")
    previousValue: Optional[Dict[str, Any]] = Field(None, description="Value before correction")
    newValue: Optional[Dict[str, Any]] = Field(None, description="Corrected value")
    wasRoutingCorrect: Optional[bool] = Field(None, description="Was the query routed correctly")
    agentId: Optional[str] = Field(None, description="Agent that produced the output")
    department: Optional[str] = Field(None, description="Related department")
    confidenceBefore: Optional[float] = Field(None, ge=0, le=1, description="Confidence before correction")
    keywordsBefore: Optional[List[str]] = Field(None, description="Keywords before correction")

    class Config:
        json_schema_extra = {
            "example": {
                "feedbackType": "kb_chat_rating",
                "rating": 1,
                "messageId": "msg-123",
                "feedbackText": "Very helpful response!",
                "wasRoutingCorrect": True
            }
        }


class FeedbackStatsResponse(BaseModel):
    """Feedback statistics response"""
    total: int
    byType: Dict[str, int]
    byRating: Dict[str, int]
    byDepartment: Dict[str, int]
    avgRating: float
    recentTrend: str


class FeedbackImpactResponse(BaseModel):
    """Feedback impact response"""
    feedbackId: str
    queryText: str
    feedbackType: str
    beforeQuality: float
    afterQuality: float
    improvement: float
    createdAt: str


class FeedbackImpactListResponse(BaseModel):
    """Response for feedback impact list"""
    impact: List[FeedbackImpactResponse]


class FeedbackSummaryResponse(BaseModel):
    """Recent feedback summary response"""
    periodDays: int
    totalFeedback: int
    positiveCount: int
    negativeCount: int
    correctionsCount: int
    mostCommonType: Optional[str]


class WeightsResponse(BaseModel):
    """User weights configuration"""
    userId: str
    preset: str
    departments: Dict[str, float]
    recency: float
    sourceTypes: Dict[str, float]
    confidence: float
    verified: float


class SetDepartmentWeightRequest(BaseModel):
    """Request to set a department weight"""
    department: str = Field(..., min_length=1, max_length=100, description="Department name")
    weight: float = Field(..., ge=0.0, le=5.0, description="Weight multiplier (0.0-5.0)")


class ApplyPresetRequest(BaseModel):
    """Request to apply a weight preset"""
    name: str = Field(..., description="Preset name: balanced, finance-heavy, research-heavy")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str


# ============================================================================
# Dependencies
# ============================================================================

def get_service() -> FeedbackService:
    """Dependency for feedback service"""
    return get_feedback_service()


def get_wt_service() -> WeightsService:
    """Dependency for weights service"""
    return get_weights_service()


# ============================================================================
# List & Stats Endpoints
# ============================================================================

@router.get("", response_model=FeedbackListResponse)
async def list_feedback(
    feedback_type: Optional[str] = Query(None, description="Filter by feedback type"),
    rating: Optional[int] = Query(None, ge=-1, le=1, description="Filter by rating"),
    department: Optional[str] = Query(None, description="Filter by department"),
    search: Optional[str] = Query(None, description="Search in text fields"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records to return"),
    user_id: str = Depends(get_current_user),
    service: FeedbackService = Depends(get_service)
) -> FeedbackListResponse:
    """
    List all feedback for the current user with optional filtering.

    Feedback can be filtered by type, rating, department, and text search.
    """
    try:
        logger.info(
            "Listing feedback",
            user_id=user_id,
            feedback_type=feedback_type,
            rating=rating,
            department=department
        )

        filters = FeedbackFilters(
            feedback_type=feedback_type,
            rating=rating,
            department=department,
            search_query=search
        )

        feedback_list = await service.list_feedback(
            user_id=user_id,
            filters=filters,
            skip=skip,
            limit=limit
        )

        return FeedbackListResponse(
            feedback=[FeedbackResponse.from_feedback(f) for f in feedback_list],
            total=len(feedback_list),
            skip=skip,
            limit=limit
        )

    except Exception as e:
        logger.error("Failed to list feedback", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list feedback: {str(e)}"
        )


@router.get("/stats", response_model=FeedbackStatsResponse)
async def get_feedback_stats(
    user_id: str = Depends(get_current_user),
    service: FeedbackService = Depends(get_service)
) -> FeedbackStatsResponse:
    """
    Get statistics about the user's feedback.

    Returns counts by type, rating, department, average rating, and recent trend.
    """
    try:
        logger.info("Getting feedback stats", user_id=user_id)

        stats = await service.get_feedback_stats(user_id)

        return FeedbackStatsResponse(
            total=stats.total,
            byType=stats.by_type,
            byRating=stats.by_rating,
            byDepartment=stats.by_department,
            avgRating=stats.avg_rating,
            recentTrend=stats.recent_trend
        )

    except Exception as e:
        logger.error("Failed to get feedback stats", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feedback stats: {str(e)}"
        )


@router.get("/impact", response_model=FeedbackImpactListResponse)
async def get_feedback_impact(
    limit: int = Query(10, ge=1, le=50, description="Maximum records to return"),
    user_id: str = Depends(get_current_user),
    service: FeedbackService = Depends(get_service)
) -> FeedbackImpactListResponse:
    """
    Show how feedback has improved responses.

    Returns impact metrics showing quality improvement from corrections.
    """
    try:
        logger.info("Getting feedback impact", user_id=user_id)

        impact_list = await service.get_feedback_impact(user_id, limit)

        return FeedbackImpactListResponse(
            impact=[
                FeedbackImpactResponse(
                    feedbackId=i.feedback_id,
                    queryText=i.query_text,
                    feedbackType=i.feedback_type,
                    beforeQuality=i.before_quality,
                    afterQuality=i.after_quality,
                    improvement=i.improvement,
                    createdAt=i.created_at.isoformat()
                )
                for i in impact_list
            ]
        )

    except Exception as e:
        logger.error("Failed to get feedback impact", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feedback impact: {str(e)}"
        )


@router.get("/summary", response_model=FeedbackSummaryResponse)
async def get_feedback_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days to summarize"),
    user_id: str = Depends(get_current_user),
    service: FeedbackService = Depends(get_service)
) -> FeedbackSummaryResponse:
    """
    Get a summary of recent feedback activity.

    Returns counts and highlights for the specified period.
    """
    try:
        logger.info("Getting feedback summary", user_id=user_id, days=days)

        summary = await service.get_recent_feedback_summary(user_id, days)

        return FeedbackSummaryResponse(
            periodDays=summary["period_days"],
            totalFeedback=summary["total_feedback"],
            positiveCount=summary["positive_count"],
            negativeCount=summary["negative_count"],
            correctionsCount=summary["corrections_count"],
            mostCommonType=summary["most_common_type"]
        )

    except Exception as e:
        logger.error("Failed to get feedback summary", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feedback summary: {str(e)}"
        )


# ============================================================================
# Weights Endpoints (must be before /{feedback_id} to avoid path conflict)
# ============================================================================

def _weights_to_response(data: Dict[str, Any]) -> WeightsResponse:
    """Convert weights dict to response model."""
    return WeightsResponse(
        userId=data["user_id"],
        preset=data.get("preset", "balanced"),
        departments=data.get("departments", {}),
        recency=data.get("recency", 1.0),
        sourceTypes=data.get("source_types", {}),
        confidence=data.get("confidence", 0.5),
        verified=data.get("verified", 1.0),
    )


@router.get("/weights", response_model=WeightsResponse)
async def get_weights(
    user_id: str = Depends(get_current_user),
    service: WeightsService = Depends(get_wt_service)
) -> WeightsResponse:
    """
    Get the current search weight configuration for the user.

    Weights influence how KB search results are ranked — department
    emphasis, recency, source type preferences, etc.
    """
    try:
        data = await service.get_weights(user_id)
        return _weights_to_response(data)
    except Exception as e:
        logger.error("Failed to get weights", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get weights"
        ) from e


@router.put("/weights", response_model=WeightsResponse)
async def set_department_weight(
    request: SetDepartmentWeightRequest,
    user_id: str = Depends(get_current_user),
    service: WeightsService = Depends(get_wt_service)
) -> WeightsResponse:
    """
    Set a department weight.

    Adjusts how strongly results from a specific department are
    ranked in search. A weight > 1.0 boosts the department, < 1.0
    de-emphasizes it.
    """
    try:
        data = await service.set_department_weight(
            user_id=user_id,
            department=request.department,
            weight=request.weight,
        )
        return _weights_to_response(data)
    except Exception as e:
        logger.error("Failed to set weight", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set weight"
        ) from e


@router.post("/weights/preset", response_model=WeightsResponse)
async def apply_weight_preset(
    request: ApplyPresetRequest,
    user_id: str = Depends(get_current_user),
    service: WeightsService = Depends(get_wt_service)
) -> WeightsResponse:
    """
    Apply a named weight preset.

    Available presets:
    - **balanced**: Default equal weighting
    - **finance-heavy**: Boost finance sources (1.5x), reduce research (0.8x)
    - **research-heavy**: Boost research sources (1.5x), reduce finance (0.8x)
    """
    try:
        data = await service.apply_preset(
            user_id=user_id,
            preset_name=request.name,
        )
        return _weights_to_response(data)
    except InvalidPresetError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to apply preset", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to apply preset"
        ) from e


# ============================================================================
# Feedback CRUD Endpoints
# ============================================================================

@router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(
    feedback_id: str,
    user_id: str = Depends(get_current_user),
    service: FeedbackService = Depends(get_service)
) -> FeedbackResponse:
    """Get a specific feedback entry by ID."""
    try:
        logger.info("Getting feedback", feedback_id=feedback_id, user_id=user_id)

        feedback = await service.get_feedback(feedback_id, user_id)
        return FeedbackResponse.from_feedback(feedback)

    except FeedbackNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found"
        )
    except Exception as e:
        logger.error("Failed to get feedback", feedback_id=feedback_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feedback: {str(e)}"
        )


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    request: FeedbackSubmitRequest,
    user_id: str = Depends(get_current_user),
    service: FeedbackService = Depends(get_service)
) -> FeedbackResponse:
    """
    Submit new feedback.

    Can be used to rate KB chat responses, report classification corrections,
    asset reclassifications, or provide general feedback.
    """
    try:
        logger.info(
            "Submitting feedback",
            user_id=user_id,
            feedback_type=request.feedbackType
        )

        feedback = await service.submit_feedback(
            user_id=user_id,
            feedback_type=request.feedbackType,
            rating=request.rating,
            session_id=request.sessionId,
            message_id=request.messageId,
            classification_id=request.classificationId,
            asset_id=request.assetId,
            query_text=request.queryText,
            response_text=request.responseText,
            feedback_text=request.feedbackText,
            improvement_suggestions=request.improvementSuggestions,
            previous_value=request.previousValue,
            new_value=request.newValue,
            was_routing_correct=request.wasRoutingCorrect,
            agent_id=request.agentId,
            department=request.department,
            confidence_before=request.confidenceBefore,
            keywords_before=request.keywordsBefore
        )

        return FeedbackResponse.from_feedback(feedback)

    except FeedbackSubmitError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to submit feedback", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )


# ============================================================================
# Feedback Types Endpoint
# ============================================================================

@router.get("/types/list")
async def list_feedback_types() -> Dict[str, Any]:
    """
    Get list of available feedback types.

    Returns all valid feedback types that can be submitted.
    """
    return {
        "types": [
            {
                "id": FeedbackType.KB_CHAT_RATING.value,
                "label": "KB Chat Rating",
                "description": "Rate a response from the knowledge base chat"
            },
            {
                "id": FeedbackType.CLASSIFICATION_CORRECTION.value,
                "label": "Classification Correction",
                "description": "Correct a misclassified department"
            },
            {
                "id": FeedbackType.ASSET_RECLASSIFICATION.value,
                "label": "Asset Reclassification",
                "description": "Reclassify an asset to a different type"
            },
            {
                "id": FeedbackType.RESPONSE_CORRECTION.value,
                "label": "Response Correction",
                "description": "Correct an inaccurate AI response"
            },
            {
                "id": FeedbackType.GENERAL_FEEDBACK.value,
                "label": "General Feedback",
                "description": "General feedback about the AI Studio"
            }
        ]
    }


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for the feedback service.
    """
    return HealthResponse(
        status="healthy",
        service="AI Studio Feedback Management"
    )
