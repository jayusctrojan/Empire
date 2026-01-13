"""
API Routes for Content Prep Agent (AGENT-016).

Feature: 007-content-prep-agent
Endpoints: /api/content-prep/*
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict

from app.services.content_prep_agent import ContentPrepAgent
from app.services.cko_chat import (
    get_cko_chat_service,
    get_clarification_logger,
    AgentClarificationType,
)
from app.models.content_sets import (
    AnalyzeRequest,
    AnalyzeResponse,
    ManifestRequest,
    ManifestResponse,
    ContentSetResponse,
    ValidateResponse,
    HealthResponse,
)

router = APIRouter(prefix="/api/content-prep", tags=["content-prep"])


# ============================================================================
# Clarification Request/Response Models (Task 129)
# ============================================================================


class ClarificationRequest(BaseModel):
    """Request to initiate ordering clarification."""
    content_set_id: str = Field(..., description="Content set to clarify ordering for")
    user_id: str = Field(..., description="User ID for chat communication")
    confidence_threshold: float = Field(
        0.8, ge=0.0, le=1.0,
        description="Confidence below which to request clarification"
    )
    timeout_seconds: int = Field(
        3600, ge=60, le=86400,
        description="Max wait time for user response (1 min - 24 hours)"
    )


class ClarificationResponse(BaseModel):
    """Response from ordering clarification."""
    status: str
    content_set_id: str
    ordering_confidence: float
    clarification_requested: bool
    clarification_answered: Optional[bool] = None
    clarification_timeout: Optional[bool] = None
    files_reordered: Optional[int] = None
    ordered_files: List[Dict[str, Any]]


class UserClarificationAnswer(BaseModel):
    """User's answer to a clarification request."""
    request_id: str = Field(..., description="Clarification request ID")
    user_id: str = Field(..., description="User ID for verification")
    response: str = Field(..., min_length=1, description="User's response text")


class PendingClarificationResponse(BaseModel):
    """A pending clarification request."""
    id: str
    agent_id: str
    message: str
    clarification_type: str
    context: Dict[str, Any]
    created_at: str
    expires_at: Optional[str]


class ClarificationHistoryResponse(BaseModel):
    """Clarification conversation history entry."""
    id: str
    content_set_id: Optional[str]
    agent_id: str
    question: str
    answer: Optional[str]
    outcome: str
    clarification_type: str
    created_at: str


# ============================================================================
# Analysis Endpoints
# ============================================================================


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_pending_files(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyze pending files in B2 folder and detect content sets.

    Identifies groups of related files (courses, documentation sets, book chapters)
    and determines their correct processing order.

    - **b2_folder**: B2 folder path to analyze (e.g., "pending/courses/")
    - **detection_mode**: Detection strategy - "auto", "pattern", "metadata", or "llm"

    Returns detected content sets and standalone files.
    """
    try:
        agent = ContentPrepAgent()
        result = await agent.analyze_folder(
            b2_folder=request.b2_folder,
            detection_mode=request.detection_mode,
        )
        return AnalyzeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Content Set Endpoints
# ============================================================================


@router.get("/sets", response_model=list[ContentSetResponse])
async def list_content_sets(
    status: Optional[str] = Query(
        None,
        description="Filter by processing status: pending, processing, complete, failed",
    ),
) -> list[ContentSetResponse]:
    """
    List all detected content sets.

    Optionally filter by processing status.
    """
    try:
        agent = ContentPrepAgent()
        sets = await agent.list_sets(status=status)
        return [ContentSetResponse(**s) for s in sets]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sets/{set_id}", response_model=ContentSetResponse)
async def get_content_set(set_id: str) -> ContentSetResponse:
    """
    Get details of a specific content set.

    Includes full file list with sequence numbers and ordering.
    """
    try:
        agent = ContentPrepAgent()
        content_set = await agent.get_set(set_id)
        return ContentSetResponse(**content_set)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Validation Endpoints
# ============================================================================


@router.post("/validate/{set_id}", response_model=ValidateResponse)
async def validate_content_set(set_id: str) -> ValidateResponse:
    """
    Validate completeness of a content set.

    Checks for missing files in the sequence (gap detection).
    Returns whether the set is complete and lists any missing files.

    If the set is incomplete, `requires_acknowledgment` will be True,
    meaning you must set `proceed_incomplete=true` when generating a manifest.
    """
    try:
        agent = ContentPrepAgent()
        result = await agent.validate_completeness(set_id)
        return ValidateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Manifest Endpoints
# ============================================================================


@router.post("/manifest", response_model=ManifestResponse)
async def generate_manifest(request: ManifestRequest) -> ManifestResponse:
    """
    Generate processing manifest for a content set.

    Creates an ordered processing queue with file dependencies.
    If the content set is incomplete, you must set `proceed_incomplete=true`
    to acknowledge and proceed anyway.

    The manifest can be passed to Celery tasks for ordered processing.
    """
    try:
        agent = ContentPrepAgent()
        result = await agent.generate_manifest(
            content_set_id=request.content_set_id,
            proceed_incomplete=request.proceed_incomplete,
        )
        return ManifestResponse(**result)
    except ValueError as e:
        if "incomplete" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": str(e),
                    "action_required": "Set proceed_incomplete=true to proceed with incomplete set",
                },
            )
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Health Check
# ============================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Service health check for Content Prep Agent.

    Returns agent status and version.
    """
    return HealthResponse(
        status="healthy",
        agent="AGENT-016",
        version="1.0.0",
    )


# ============================================================================
# Clarification Endpoints (Task 129: Chat-Based Ordering Clarification)
# ============================================================================


@router.post("/clarify-ordering", response_model=ClarificationResponse)
async def clarify_ordering(request: ClarificationRequest) -> ClarificationResponse:
    """
    Resolve file ordering with user clarification if needed.

    If the ordering confidence for a content set is below the threshold,
    this endpoint will send a clarification request to the user via CKO Chat
    and wait for their response.

    **Flow:**
    1. Calculate ordering confidence for the content set
    2. If confidence >= threshold, return current ordering immediately
    3. If confidence < threshold, send clarification message to user
    4. Wait for user response (up to timeout_seconds)
    5. Parse user response and update ordering
    6. Return final ordering with clarification status

    **Note:** This is a long-polling endpoint. For async processing,
    use the Celery task instead.
    """
    try:
        agent = ContentPrepAgent()
        result = await agent.resolve_order_with_clarification(
            content_set_id=request.content_set_id,
            user_id=request.user_id,
            confidence_threshold=request.confidence_threshold,
            timeout_seconds=request.timeout_seconds,
        )
        return ClarificationResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clarifications/respond")
async def respond_to_clarification(answer: UserClarificationAnswer) -> Dict[str, Any]:
    """
    Submit a user's response to a clarification request.

    Called by the CKO Chat interface when a user responds to an
    agent's clarification question.

    Returns success status and updates the clarification request.
    """
    try:
        chat_service = get_cko_chat_service()
        success = await chat_service.submit_user_response(
            request_id=answer.request_id,
            user_id=answer.user_id,
            response=answer.response,
        )

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Could not submit response. Request may not exist, be already answered, or belong to another user.",
            )

        return {
            "status": "success",
            "message": "Response submitted successfully",
            "request_id": answer.request_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clarifications/pending/{user_id}", response_model=List[PendingClarificationResponse])
async def get_pending_clarifications(
    user_id: str,
    limit: int = Query(10, ge=1, le=50, description="Max requests to return"),
) -> List[PendingClarificationResponse]:
    """
    Get pending clarification requests for a user.

    Returns a list of clarification questions from agents that
    are awaiting the user's response.
    """
    try:
        chat_service = get_cko_chat_service()
        requests = await chat_service.get_pending_requests(
            user_id=user_id,
            limit=limit,
        )

        return [
            PendingClarificationResponse(
                id=r["id"],
                agent_id=r["agent_id"],
                message=r["message"],
                clarification_type=r["clarification_type"],
                context=r.get("context", {}),
                created_at=r["created_at"],
                expires_at=r.get("expires_at"),
            )
            for r in requests
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clarifications/history/{content_set_id}", response_model=List[ClarificationHistoryResponse])
async def get_clarification_history(
    content_set_id: str,
    limit: int = Query(50, ge=1, le=100, description="Max entries to return"),
) -> List[ClarificationHistoryResponse]:
    """
    Get clarification conversation history for a content set.

    Returns the audit trail of all clarification conversations
    that have occurred for this content set.
    """
    try:
        logger = get_clarification_logger()
        history = await logger.get_conversation_history(
            content_set_id=content_set_id,
            limit=limit,
        )

        return [
            ClarificationHistoryResponse(
                id=h["id"],
                content_set_id=h.get("content_set_id"),
                agent_id=h["agent_id"],
                question=h["question"],
                answer=h.get("answer"),
                outcome=h["outcome"],
                clarification_type=h["clarification_type"],
                created_at=h["created_at"],
            )
            for h in history
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clarifications/{request_id}")
async def cancel_clarification(
    request_id: str,
    agent_id: str = Query("AGENT-016", description="Agent ID for verification"),
) -> Dict[str, Any]:
    """
    Cancel a pending clarification request.

    Only the agent that created the request can cancel it.
    """
    try:
        chat_service = get_cko_chat_service()
        success = await chat_service.cancel_request(
            request_id=request_id,
            agent_id=agent_id,
        )

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Could not cancel request. It may not exist, be already answered, or belong to another agent.",
            )

        return {
            "status": "success",
            "message": "Clarification request cancelled",
            "request_id": request_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Admin/Operations Endpoints (Task 130: Retention Policy)
# ============================================================================


class CleanupRequest(BaseModel):
    """Request for manual cleanup."""
    retention_days: int = Field(
        90, ge=1, le=365,
        description="Number of days to retain completed content sets"
    )
    async_mode: bool = Field(
        True,
        description="Run cleanup as background Celery task"
    )


class CleanupResponse(BaseModel):
    """Response from cleanup operation."""
    status: str
    message: str
    task_id: Optional[str] = None
    deleted_count: Optional[int] = None
    retention_days: int
    cutoff_date: Optional[str] = None


@router.post("/admin/cleanup", response_model=CleanupResponse)
async def trigger_cleanup(request: CleanupRequest) -> CleanupResponse:
    """
    Manually trigger content set cleanup.

    By default, runs asynchronously as a Celery task.
    Set async_mode=false to run synchronously (not recommended for production).

    **Note:** This is an admin endpoint. Ensure proper authentication
    is applied in production.
    """
    from app.tasks.content_prep_tasks import cleanup_old_content_sets
    from datetime import timedelta

    try:
        if request.async_mode:
            # Run as Celery task
            task = cleanup_old_content_sets.apply_async(
                kwargs={"retention_days": request.retention_days}
            )
            return CleanupResponse(
                status="accepted",
                message=f"Cleanup task queued with {request.retention_days}-day retention",
                task_id=task.id,
                retention_days=request.retention_days,
            )
        else:
            # Run synchronously (blocking)
            from datetime import datetime
            result = cleanup_old_content_sets(retention_days=request.retention_days)
            return CleanupResponse(
                status=result.get("status", "success"),
                message=result.get("message", f"Deleted {result.get('deleted_count', 0)} content sets"),
                deleted_count=result.get("deleted_count", 0),
                retention_days=request.retention_days,
                cutoff_date=result.get("cutoff_date"),
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/cleanup/status/{task_id}")
async def get_cleanup_status(task_id: str) -> Dict[str, Any]:
    """
    Get status of a cleanup task.

    Returns task state and result if completed.
    """
    from celery.result import AsyncResult
    from app.celery_app import celery_app

    try:
        result = AsyncResult(task_id, app=celery_app)
        response = {
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready(),
        }

        if result.ready():
            if result.successful():
                response["result"] = result.result
            else:
                response["error"] = str(result.result) if result.result else "Unknown error"

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
