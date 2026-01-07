"""
Empire v7.3 - AI Studio Classification Management API Routes
Task 78: Implement Department Classification Management

Endpoints:
- GET /api/studio/classifications - List all classifications (filterable)
- GET /api/studio/classifications/stats - Get classification statistics
- GET /api/studio/classifications/{classification_id} - Get classification details
- PATCH /api/studio/classifications/{classification_id} - Correct classification
- GET /api/studio/classifications/health - Health check
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field
import structlog

from app.middleware.auth import get_current_user
from app.services.classification_service import (
    ClassificationService,
    Classification,
    ClassificationFilters,
    ClassificationNotFoundError,
    ClassificationUpdateError,
    get_classification_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/studio/classifications", tags=["AI Studio Classifications"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ClassificationResponse(BaseModel):
    """Classification details response"""
    id: str
    userId: str
    documentId: Optional[str] = None
    contentHash: Optional[str] = None
    filename: Optional[str] = None
    contentPreview: Optional[str] = None
    department: str
    confidence: float
    reasoning: Optional[str] = None
    keywordsMatched: List[str] = []
    secondaryDepartment: Optional[str] = None
    secondaryConfidence: Optional[float] = None
    userCorrectedDepartment: Optional[str] = None
    correctionReason: Optional[str] = None
    correctedAt: Optional[str] = None
    createdAt: Optional[str] = None

    @classmethod
    def from_classification(cls, c: Classification) -> "ClassificationResponse":
        """Convert Classification model to response"""
        return cls(
            id=c.id,
            userId=c.user_id,
            documentId=c.document_id,
            contentHash=c.content_hash,
            filename=c.filename,
            contentPreview=c.content_preview,
            department=c.department,
            confidence=c.confidence,
            reasoning=c.reasoning,
            keywordsMatched=c.keywords_matched or [],
            secondaryDepartment=c.secondary_department,
            secondaryConfidence=c.secondary_confidence,
            userCorrectedDepartment=c.user_corrected_department,
            correctionReason=c.correction_reason,
            correctedAt=c.corrected_at.isoformat() if c.corrected_at else None,
            createdAt=c.created_at.isoformat() if c.created_at else None,
        )


class ClassificationListResponse(BaseModel):
    """Response for listing classifications"""
    classifications: List[ClassificationResponse]
    total: int
    skip: int
    limit: int


class ClassificationCorrectionRequest(BaseModel):
    """Request to correct a classification"""
    newDepartment: str = Field(..., min_length=1, max_length=100, description="Corrected department")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for correction")

    class Config:
        json_schema_extra = {
            "example": {
                "newDepartment": "sales-marketing",
                "reason": "Content is about sales strategies, not IT"
            }
        }


class ClassificationStatsResponse(BaseModel):
    """Classification statistics response"""
    total: int
    byDepartment: dict
    byConfidence: dict
    correctedCount: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str


# ============================================================================
# Dependencies
# ============================================================================

def get_service() -> ClassificationService:
    """Dependency for classification service"""
    return get_classification_service()


# ============================================================================
# List & Stats Endpoints
# ============================================================================

@router.get("", response_model=ClassificationListResponse)
async def list_classifications(
    department: Optional[str] = Query(None, description="Filter by department"),
    confidence_min: Optional[float] = Query(None, ge=0, le=1, description="Minimum confidence"),
    corrected: Optional[bool] = Query(None, description="Filter by correction status"),
    search: Optional[str] = Query(None, description="Search in filename and content"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records to return"),
    user_id: str = Depends(get_current_user),
    service: ClassificationService = Depends(get_service)
) -> ClassificationListResponse:
    """
    List all classifications for the current user with optional filtering.

    Classifications can be filtered by department, minimum confidence level,
    correction status, and a text search query.
    """
    try:
        logger.info(
            "Listing classifications",
            user_id=user_id,
            department=department,
            confidence_min=confidence_min,
            corrected=corrected
        )

        filters = ClassificationFilters(
            department=department,
            confidence_min=confidence_min,
            corrected=corrected,
            search_query=search
        )

        classifications = await service.list_classifications(
            user_id=user_id,
            filters=filters,
            skip=skip,
            limit=limit
        )

        return ClassificationListResponse(
            classifications=[ClassificationResponse.from_classification(c) for c in classifications],
            total=len(classifications),
            skip=skip,
            limit=limit
        )

    except Exception as e:
        logger.error("Failed to list classifications", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list classifications: {str(e)}"
        )


@router.get("/stats", response_model=ClassificationStatsResponse)
async def get_classification_stats(
    user_id: str = Depends(get_current_user),
    service: ClassificationService = Depends(get_service)
) -> ClassificationStatsResponse:
    """
    Get statistics about the user's classifications.

    Returns counts by department, confidence level, and correction status.
    """
    try:
        logger.info("Getting classification stats", user_id=user_id)

        stats = await service.get_classification_stats(user_id)

        return ClassificationStatsResponse(
            total=stats["total"],
            byDepartment=stats["by_department"],
            byConfidence=stats["by_confidence"],
            correctedCount=stats["corrected_count"]
        )

    except Exception as e:
        logger.error("Failed to get classification stats", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get classification stats: {str(e)}"
        )


# ============================================================================
# Classification CRUD Endpoints
# ============================================================================

@router.get("/{classification_id}", response_model=ClassificationResponse)
async def get_classification(
    classification_id: str,
    user_id: str = Depends(get_current_user),
    service: ClassificationService = Depends(get_service)
) -> ClassificationResponse:
    """Get a specific classification by ID."""
    try:
        logger.info("Getting classification", classification_id=classification_id, user_id=user_id)

        classification = await service.get_classification(classification_id, user_id)
        return ClassificationResponse.from_classification(classification)

    except ClassificationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classification not found"
        )
    except Exception as e:
        logger.error("Failed to get classification", classification_id=classification_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get classification: {str(e)}"
        )


@router.patch("/{classification_id}", response_model=ClassificationResponse)
async def correct_classification(
    classification_id: str,
    request: ClassificationCorrectionRequest,
    user_id: str = Depends(get_current_user),
    service: ClassificationService = Depends(get_service)
) -> ClassificationResponse:
    """
    Correct a misclassified content.

    Changes the department classification and logs feedback for model improvement.
    """
    try:
        logger.info(
            "Correcting classification",
            classification_id=classification_id,
            user_id=user_id,
            new_department=request.newDepartment
        )

        updated = await service.correct_classification(
            classification_id=classification_id,
            user_id=user_id,
            new_department=request.newDepartment,
            reason=request.reason
        )

        return ClassificationResponse.from_classification(updated)

    except ClassificationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classification not found"
        )
    except ClassificationUpdateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to correct classification", classification_id=classification_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to correct classification: {str(e)}"
        )


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for the classification service.
    """
    return HealthResponse(
        status="healthy",
        service="AI Studio Classification Management"
    )
