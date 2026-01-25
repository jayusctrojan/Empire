"""
Empire v7.3 - Department Classifier Agent API Routes
Task 44: Implement Department Classifier Agent (AGENT-008)

Provides REST API endpoints for 10-department classification with confidence scores.
"""

import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends, UploadFile, File, Form
from pydantic import BaseModel, Field
import structlog

from app.services.department_classifier_agent import (
    get_department_classifier_service,
    DepartmentClassifierAgentService,
    Department,
    ClassificationResult,
    BatchClassificationResult,
    KeywordExtractionResult
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/classifier", tags=["Department Classifier"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ClassifyContentRequest(BaseModel):
    """Request model for content classification"""
    content: str = Field(..., min_length=10, description="Content to classify")
    filename: Optional[str] = Field(None, description="Optional filename for context")
    include_all_scores: bool = Field(
        default=False,
        description="Include detailed scores for all departments"
    )


class ClassifyContentResponse(BaseModel):
    """Response model for content classification"""
    department: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    keywords_matched: List[str] = []
    secondary_department: Optional[str] = None
    secondary_confidence: float = 0.0
    llm_enhanced: bool = False
    processing_time_ms: float = 0.0
    all_scores: Optional[List[Dict[str, Any]]] = None


class BatchClassifyRequest(BaseModel):
    """Request model for batch classification"""
    items: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of items with 'content' and optional 'filename'"
    )
    concurrency: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of concurrent classifications"
    )


class BatchClassifyResponse(BaseModel):
    """Response model for batch classification"""
    results: List[ClassifyContentResponse]
    total_processed: int
    average_confidence: float
    processing_time_ms: float


class ExtractKeywordsRequest(BaseModel):
    """Request model for keyword extraction"""
    content: str = Field(..., min_length=10, description="Content to analyze")


class ExtractKeywordsResponse(BaseModel):
    """Response model for keyword extraction"""
    all_keywords: List[str]
    department_keywords: Dict[str, List[str]]
    keyword_counts: Dict[str, int]
    total_keywords_found: int


class DepartmentInfoResponse(BaseModel):
    """Response model for department information"""
    code: str
    description: str
    primary_keywords: List[str]
    secondary_keywords: List[str]
    tertiary_keywords: List[str]
    total_keywords: int


class ClassifierStatsResponse(BaseModel):
    """Response model for classifier statistics"""
    agent_id: str
    agent_name: str
    classifications_total: int
    classifications_by_department: Dict[str, int]
    llm_enhanced_count: int
    average_confidence: float
    high_confidence_count: int
    low_confidence_count: int


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_classifier_service() -> DepartmentClassifierAgentService:
    """Dependency for department classifier service"""
    return get_department_classifier_service()


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/classify", response_model=ClassifyContentResponse)
async def classify_content(
    request: ClassifyContentRequest,
    classifier: DepartmentClassifierAgentService = Depends(get_classifier_service)
) -> ClassifyContentResponse:
    """
    Classify content into one of 10 departments.

    Departments:
    - it-engineering: Software, APIs, DevOps, infrastructure
    - sales-marketing: Sales, campaigns, CRM, lead generation
    - customer-support: Help desk, tickets, customer service
    - operations-hr-supply: HR, logistics, procurement, workforce
    - finance-accounting: Financial reporting, budgeting, auditing
    - project-management: Project planning, Agile, milestones
    - real-estate: Property, leases, mortgages
    - private-equity-ma: M&A, valuations, due diligence
    - consulting: Strategy, advisory, frameworks
    - personal-continuing-ed: Education, courses, certifications

    Returns department code and confidence score (0-1).
    """
    try:
        logger.info(
            "Classification request",
            content_length=len(request.content),
            filename=request.filename
        )

        result = await classifier.classify_content(
            content=request.content,
            filename=request.filename,
            include_all_scores=request.include_all_scores
        )

        response = ClassifyContentResponse(
            department=result.department.value,
            confidence=result.confidence,
            reasoning=result.reasoning,
            keywords_matched=result.keywords_matched,
            secondary_department=result.secondary_department.value if result.secondary_department else None,
            secondary_confidence=result.secondary_confidence,
            llm_enhanced=result.llm_enhanced,
            processing_time_ms=result.processing_time_ms
        )

        if request.include_all_scores and result.all_scores:
            response.all_scores = [
                {
                    "department": s.department.value,
                    "raw_score": s.raw_score,
                    "normalized_score": s.normalized_score,
                    "primary_matches": s.primary_matches,
                    "secondary_matches": s.secondary_matches,
                    "tertiary_matches": s.tertiary_matches,
                    "keyword_matches": s.keyword_matches[:10]
                }
                for s in result.all_scores
            ]

        return response

    except Exception as e:
        logger.error("Classification failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/classify/file", response_model=ClassifyContentResponse)
async def classify_file(
    file: UploadFile = File(..., description="File to classify"),
    include_all_scores: bool = Form(default=False),
    classifier: DepartmentClassifierAgentService = Depends(get_classifier_service)
) -> ClassifyContentResponse:
    """
    Classify an uploaded file into one of 10 departments.

    Supported file types: .txt, .md, .py, .js, .json, .yaml, .csv
    """
    try:
        # Read file content
        content_bytes = await file.read()

        # Decode text content
        try:
            content = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                content = content_bytes.decode('latin-1')
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Could not decode file content. Please upload a text file."
                )

        logger.info(
            "File classification request",
            filename=file.filename,
            content_length=len(content)
        )

        result = await classifier.classify_content(
            content=content,
            filename=file.filename,
            include_all_scores=include_all_scores
        )

        response = ClassifyContentResponse(
            department=result.department.value,
            confidence=result.confidence,
            reasoning=result.reasoning,
            keywords_matched=result.keywords_matched,
            secondary_department=result.secondary_department.value if result.secondary_department else None,
            secondary_confidence=result.secondary_confidence,
            llm_enhanced=result.llm_enhanced,
            processing_time_ms=result.processing_time_ms
        )

        if include_all_scores and result.all_scores:
            response.all_scores = [
                {
                    "department": s.department.value,
                    "raw_score": s.raw_score,
                    "normalized_score": s.normalized_score,
                    "primary_matches": s.primary_matches,
                    "secondary_matches": s.secondary_matches,
                    "tertiary_matches": s.tertiary_matches,
                    "keyword_matches": s.keyword_matches[:10]
                }
                for s in result.all_scores
            ]

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("File classification failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/classify/batch", response_model=BatchClassifyResponse)
async def classify_batch(
    request: BatchClassifyRequest,
    classifier: DepartmentClassifierAgentService = Depends(get_classifier_service)
) -> BatchClassifyResponse:
    """
    Classify multiple items in batch.

    Each item should have:
    - content: Text content to classify (required)
    - filename: Optional filename for context

    Returns results for all items with average confidence.
    """
    try:
        logger.info(
            "Batch classification request",
            items_count=len(request.items),
            concurrency=request.concurrency
        )

        # Validate items
        for i, item in enumerate(request.items):
            if "content" not in item:
                raise HTTPException(
                    status_code=400,
                    detail=f"Item {i} missing required 'content' field"
                )

        result = await classifier.classify_batch(
            items=request.items,
            concurrency=request.concurrency
        )

        return BatchClassifyResponse(
            results=[
                ClassifyContentResponse(
                    department=r.department.value,
                    confidence=r.confidence,
                    reasoning=r.reasoning,
                    keywords_matched=r.keywords_matched,
                    secondary_department=r.secondary_department.value if r.secondary_department else None,
                    secondary_confidence=r.secondary_confidence,
                    llm_enhanced=r.llm_enhanced,
                    processing_time_ms=r.processing_time_ms
                )
                for r in result.results
            ],
            total_processed=result.total_processed,
            average_confidence=result.average_confidence,
            processing_time_ms=result.processing_time_ms
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Batch classification failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/keywords/extract", response_model=ExtractKeywordsResponse)
async def extract_keywords(
    request: ExtractKeywordsRequest,
    classifier: DepartmentClassifierAgentService = Depends(get_classifier_service)
) -> ExtractKeywordsResponse:
    """
    Extract department-relevant keywords from content.

    Returns keywords found along with their department associations.
    """
    try:
        logger.info(
            "Keyword extraction request",
            content_length=len(request.content)
        )

        result = classifier.extract_keywords(request.content)

        return ExtractKeywordsResponse(
            all_keywords=result.all_keywords,
            department_keywords=result.department_keywords,
            keyword_counts=result.keyword_counts,
            total_keywords_found=result.total_keywords_found
        )

    except Exception as e:
        logger.error("Keyword extraction failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/departments", response_model=List[DepartmentInfoResponse])
async def get_departments(
    classifier: DepartmentClassifierAgentService = Depends(get_classifier_service)
) -> List[DepartmentInfoResponse]:
    """Get list of all 10 departments with their keywords"""
    departments = classifier.get_all_departments()
    return [
        DepartmentInfoResponse(**dept)
        for dept in departments
    ]


@router.get("/departments/{department_code}", response_model=DepartmentInfoResponse)
async def get_department(
    department_code: str,
    classifier: DepartmentClassifierAgentService = Depends(get_classifier_service)
) -> DepartmentInfoResponse:
    """Get detailed information about a specific department"""
    try:
        # Find matching department
        dept = None
        for d in Department:
            if d.value == department_code:
                dept = d
                break

        if not dept:
            raise HTTPException(
                status_code=404,
                detail=f"Department '{department_code}' not found"
            )

        info = classifier.get_department_info(dept)
        return DepartmentInfoResponse(**info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get department failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=ClassifierStatsResponse)
async def get_classifier_stats(
    classifier: DepartmentClassifierAgentService = Depends(get_classifier_service)
) -> ClassifierStatsResponse:
    """Get classification statistics for AGENT-008"""
    stats = classifier.get_stats()
    return ClassifierStatsResponse(**stats)


@router.post("/stats/reset")
async def reset_classifier_stats(
    classifier: DepartmentClassifierAgentService = Depends(get_classifier_service)
) -> Dict[str, str]:
    """Reset classification statistics"""
    classifier.reset_stats()
    return {"message": "Statistics reset successfully"}


@router.get("/health")
async def classifier_health() -> Dict[str, Any]:
    """Health check for Department Classifier Agent"""
    return {
        "status": "healthy",
        "agent_id": "AGENT-008",
        "agent_name": "Department Classifier Agent",
        "capabilities": {
            "content_classification": True,
            "file_classification": True,
            "batch_classification": True,
            "keyword_extraction": True,
            "llm_enhancement": bool(os.getenv("ANTHROPIC_API_KEY"))
        },
        "departments_count": 10
    }
