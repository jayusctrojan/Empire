"""
Empire v7.3 - AI Studio CKO Conversation API Routes
Task 72: Implement Knowledge Base Chat Service

Endpoints:
- POST /api/studio/cko/sessions - Create a new CKO session
- GET /api/studio/cko/sessions - List user's CKO sessions
- GET /api/studio/cko/sessions/{session_id} - Get session details
- DELETE /api/studio/cko/sessions/{session_id} - Delete a session
- PATCH /api/studio/cko/sessions/{session_id} - Update session title

- POST /api/studio/cko/sessions/{session_id}/messages - Send a message
- GET /api/studio/cko/sessions/{session_id}/messages - Get session messages

- POST /api/studio/cko/messages/{message_id}/rate - Rate a message
- POST /api/studio/cko/messages/{message_id}/clarify - Answer clarification
- POST /api/studio/cko/messages/{message_id}/skip - Skip clarification

- GET /api/studio/cko/clarifications/count - Get pending clarifications count
- GET /api/studio/cko/health - Health check
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import structlog
import json

from app.middleware.auth import get_current_user
from app.services.studio_cko_conversation_service import (
    StudioCKOConversationService,
    CKOConfig,
    CKOSession,
    CKOMessage,
    CKOResponse,
    CKOSource,
    MessageRole,
    ClarificationStatus,
    get_cko_conversation_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/studio/cko", tags=["AI Studio CKO"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a new CKO session"""
    title: Optional[str] = Field(None, max_length=200, description="Optional session title")
    project_id: Optional[str] = Field(None, description="Optional project to link session to")


class SessionResponse(BaseModel):
    """CKO session details"""
    id: str
    userId: str
    title: Optional[str]
    messageCount: int
    pendingClarifications: int
    contextSummary: Optional[str]
    projectId: Optional[str] = None
    createdAt: Optional[str]
    updatedAt: Optional[str]
    lastMessageAt: Optional[str]


class UpdateSessionRequest(BaseModel):
    """Request to update session"""
    title: str = Field(..., min_length=1, max_length=200)


class SourceResponse(BaseModel):
    """A source cited in a CKO response"""
    docId: str
    title: str
    snippet: str
    relevanceScore: float
    pageNumber: Optional[int] = None
    department: Optional[str] = None
    documentType: Optional[str] = None
    chunkIndex: Optional[int] = None


class MessageResponse(BaseModel):
    """CKO message details"""
    id: str
    sessionId: str
    role: str
    content: str
    sources: List[SourceResponse] = []
    actionsPerformed: List[Dict[str, Any]] = []
    isClarification: bool = False
    clarificationType: Optional[str] = None
    clarificationStatus: Optional[str] = None
    clarificationAnswer: Optional[str] = None
    rating: Optional[int] = None
    ratingFeedback: Optional[str] = None
    createdAt: Optional[str] = None


class SendMessageRequest(BaseModel):
    """Request to send a message to CKO"""
    message: str = Field(..., min_length=1, max_length=8000, description="User message")

    # Optional configuration overrides
    enable_query_expansion: bool = Field(True, description="Use query expansion")
    num_query_variations: int = Field(5, ge=1, le=10, description="Number of query variations")
    expansion_strategy: str = Field("balanced", description="Expansion strategy")
    global_kb_limit: int = Field(10, ge=1, le=20, description="Max sources to retrieve")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "What are our company policies on remote work?",
                "enable_query_expansion": True,
                "num_query_variations": 5,
            }
        }


class SendMessageResponse(BaseModel):
    """Response from sending a message"""
    success: bool = True
    message: MessageResponse
    queryTimeMs: float
    sourcesCount: int
    sessionUpdated: bool


class RateMessageRequest(BaseModel):
    """Request to rate a message"""
    rating: int = Field(..., ge=-1, le=1, description="-1 (thumbs down), 0 (neutral), 1 (thumbs up)")
    feedback: Optional[str] = Field(None, max_length=1000, description="Optional feedback text")


class ClarificationAnswerRequest(BaseModel):
    """Request to answer a clarification"""
    answer: str = Field(..., min_length=1, max_length=2000, description="Answer to the clarification")


class ClarificationCountResponse(BaseModel):
    """Pending clarifications count response"""
    count: int
    hasOverdue: bool


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    embeddingModel: str
    llmModel: str
    queryExpansionEnabled: bool


# ============================================================================
# Dependencies
# ============================================================================

def get_service() -> StudioCKOConversationService:
    """Dependency for CKO conversation service"""
    return get_cko_conversation_service()


# ============================================================================
# Search Response Model
# ============================================================================

class SearchResponse(BaseModel):
    """Response from KB search"""
    sources: List[SourceResponse]
    total: int
    query: str


# ============================================================================
# Search Endpoint (must be before /{session_id} routes)
# ============================================================================

@router.get("/search", response_model=SearchResponse)
async def search_kb(
    query: str = Query(..., min_length=1, max_length=2000, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
    user_id: str = Depends(get_current_user),
    service: StudioCKOConversationService = Depends(get_service)
) -> SearchResponse:
    """
    Search the knowledge base directly without creating a session.

    Returns ranked sources matching the query. Uses the same pipeline as
    the CKO chat (query expansion, embeddings, vector search, dedup/rank)
    but skips LLM response generation.
    """
    try:
        logger.info("CKO KB search", user_id=user_id, query=query[:100])

        sources = await service.search(query=query, limit=limit)

        return SearchResponse(
            sources=[
                SourceResponse(
                    docId=s.doc_id,
                    title=s.title,
                    snippet=s.snippet,
                    relevanceScore=s.relevance_score,
                    pageNumber=s.page_number,
                    department=s.department,
                    documentType=s.document_type,
                    chunkIndex=s.chunk_index,
                )
                for s in sources
            ],
            total=len(sources),
            query=query,
        )

    except Exception as e:
        logger.error("CKO search failed", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        ) from e


# ============================================================================
# Session Endpoints
# ============================================================================

@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    user_id: str = Depends(get_current_user),
    service: StudioCKOConversationService = Depends(get_service)
) -> SessionResponse:
    """
    Create a new CKO conversation session.

    The CKO (Chief Knowledge Officer) is an AI persona that helps you
    explore and understand your organization's knowledge base through
    natural conversation.
    """
    try:
        logger.info("Creating CKO session", user_id=user_id)

        # Validate project ownership if project_id is provided
        if request.project_id:
            from app.core.database import get_supabase
            import asyncio as _asyncio

            supabase = get_supabase()
            project_check = await _asyncio.to_thread(
                lambda: supabase.table("projects")
                .select("id")
                .eq("id", request.project_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            if not project_check.data:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Project not found or access denied",
                )

        session = await service.create_session(
            user_id=user_id,
            title=request.title,
            project_id=request.project_id,
        )

        return SessionResponse(**session.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create CKO session", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session"
        ) from e


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    service: StudioCKOConversationService = Depends(get_service)
) -> List[SessionResponse]:
    """
    List all CKO sessions for the current user.

    Sessions are ordered by most recently updated first.
    """
    try:
        sessions = await service.list_sessions(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        return [SessionResponse(**s.to_dict()) for s in sessions]

    except Exception as e:
        logger.error("Failed to list CKO sessions", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
    service: StudioCKOConversationService = Depends(get_service)
) -> SessionResponse:
    """Get a specific CKO session by ID."""
    try:
        session = await service.get_session(session_id, user_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        return SessionResponse(**session.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get CKO session", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session: {str(e)}"
        )


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    user_id: str = Depends(get_current_user),
    service: StudioCKOConversationService = Depends(get_service)
) -> SessionResponse:
    """Update a CKO session (currently supports title update)."""
    try:
        success = await service.update_session_title(
            session_id=session_id,
            user_id=user_id,
            title=request.title
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        session = await service.get_session(session_id, user_id)
        return SessionResponse(**session.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update CKO session", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session: {str(e)}"
        )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
    service: StudioCKOConversationService = Depends(get_service)
):
    """Delete a CKO session and all its messages."""
    try:
        success = await service.delete_session(session_id, user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete CKO session", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )


# ============================================================================
# Message Endpoints
# ============================================================================

@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    user_id: str = Depends(get_current_user),
    service: StudioCKOConversationService = Depends(get_service)
) -> SendMessageResponse:
    """
    Send a message to the CKO and get a response.

    The CKO will:
    1. Search the global knowledge base for relevant information
    2. Generate a comprehensive response with citations
    3. Track sources for reference

    Response includes:
    - CKO's answer with inline citations [1], [2], etc.
    - List of sources used
    - Query performance metrics
    """
    try:
        logger.info(
            "Sending CKO message",
            session_id=session_id,
            message_length=len(request.message)
        )

        # Build config from request
        config = CKOConfig(
            enable_query_expansion=request.enable_query_expansion,
            num_query_variations=request.num_query_variations,
            expansion_strategy=request.expansion_strategy,
            global_kb_limit=request.global_kb_limit,
        )

        response: CKOResponse = await service.send_message(
            session_id=session_id,
            user_id=user_id,
            message=request.message,
            config=config
        )

        # Convert message to response format
        msg = response.message
        sources = [
            SourceResponse(
                docId=s.doc_id,
                title=s.title,
                snippet=s.snippet,
                relevanceScore=s.relevance_score,
                pageNumber=s.page_number,
                department=s.department,
                documentType=s.document_type,
                chunkIndex=s.chunk_index,
            )
            for s in msg.sources
        ]

        return SendMessageResponse(
            success=True,
            message=MessageResponse(
                id=msg.id,
                sessionId=msg.session_id,
                role=msg.role.value,
                content=msg.content,
                sources=sources,
                actionsPerformed=msg.actions_performed,
                isClarification=msg.is_clarification,
                clarificationType=msg.clarification_type,
                clarificationStatus=msg.clarification_status.value if msg.clarification_status else None,
                rating=msg.rating,
                createdAt=msg.created_at.isoformat() if msg.created_at else None,
            ),
            queryTimeMs=response.query_time_ms,
            sourcesCount=response.sources_count,
            sessionUpdated=response.session_updated,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to send CKO message", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )


@router.post("/sessions/{session_id}/messages/stream")
async def stream_message(
    session_id: str,
    request: SendMessageRequest,
    user_id: str = Depends(get_current_user),
    service: StudioCKOConversationService = Depends(get_service)
):
    """
    Stream a CKO response using the multi-model pipeline with Server-Sent Events (SSE).

    Event types:
    - `start`: Session acknowledged, processing started
    - `phase`: Pipeline phase indicator (analyzing, searching, reasoning, formatting)
    - `sources`: Retrieved sources (sent early for UI display)
    - `token`: Response token chunk (streamed from Output Architect or Kimi fallback)
    - `done`: Complete message with metadata including pipeline_mode
    - `error`: Error occurred

    Example SSE stream:
    ```
    event: start
    data: {"session_id": "..."}

    event: phase
    data: {"phase": "analyzing", "label": "Analyzing your question..."}

    event: phase
    data: {"phase": "searching", "label": "Searching knowledge base..."}

    event: sources
    data: {"sources": [...]}

    event: phase
    data: {"phase": "reasoning", "label": "Thinking deeply..."}

    event: phase
    data: {"phase": "formatting", "label": "Formatting response..."}

    event: token
    data: {"content": "Based on"}

    event: done
    data: {"message": {...}, "query_time_ms": 1234, "pipeline_mode": "full"}
    ```
    """
    async def generate():
        try:
            config = CKOConfig(
                enable_query_expansion=request.enable_query_expansion,
                num_query_variations=request.num_query_variations,
                expansion_strategy=request.expansion_strategy,
                global_kb_limit=request.global_kb_limit,
            )

            async for event in service.stream_message(
                session_id=session_id,
                user_id=user_id,
                message=request.message,
                config=config
            ):
                event_type = event.get("type", "unknown")
                yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"

        except Exception as e:
            logger.error("CKO streaming error", session_id=session_id, error=str(e))
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    service: StudioCKOConversationService = Depends(get_service)
) -> List[MessageResponse]:
    """
    Get all messages in a CKO session.

    Messages are returned in chronological order (oldest first).
    """
    try:
        messages = await service.get_messages(
            session_id=session_id,
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        return [
            MessageResponse(
                id=m.id,
                sessionId=m.session_id,
                role=m.role.value,
                content=m.content,
                sources=[
                    SourceResponse(
                        docId=s.doc_id,
                        title=s.title,
                        snippet=s.snippet,
                        relevanceScore=s.relevance_score,
                        pageNumber=s.page_number,
                        department=s.department,
                        documentType=s.document_type,
                        chunkIndex=s.chunk_index,
                    )
                    for s in m.sources
                ],
                actionsPerformed=m.actions_performed,
                isClarification=m.is_clarification,
                clarificationType=m.clarification_type,
                clarificationStatus=m.clarification_status.value if m.clarification_status else None,
                clarificationAnswer=m.clarification_answer,
                rating=m.rating,
                ratingFeedback=m.rating_feedback,
                createdAt=m.created_at.isoformat() if m.created_at else None,
            )
            for m in messages
        ]

    except Exception as e:
        logger.error("Failed to get CKO messages", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get messages: {str(e)}"
        )


# ============================================================================
# Rating & Clarification Endpoints
# ============================================================================

@router.post("/messages/{message_id}/rate", status_code=status.HTTP_200_OK)
async def rate_message(
    message_id: str,
    request: RateMessageRequest,
    user_id: str = Depends(get_current_user),
    service: StudioCKOConversationService = Depends(get_service)
) -> Dict[str, Any]:
    """
    Rate a CKO response.

    Ratings:
    - `-1`: Thumbs down (unhelpful)
    - `0`: Neutral
    - `1`: Thumbs up (helpful)

    Optional feedback text can be provided for more detailed feedback.
    """
    try:
        success = await service.rate_message(
            message_id=message_id,
            user_id=user_id,
            rating=request.rating,
            feedback=request.feedback
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found or access denied"
            )

        return {"success": True, "rating": request.rating}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to rate message", message_id=message_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rate message: {str(e)}"
        )


@router.post("/messages/{message_id}/clarify", response_model=SendMessageResponse)
async def answer_clarification(
    message_id: str,
    request: ClarificationAnswerRequest,
    user_id: str = Depends(get_current_user),
    service: StudioCKOConversationService = Depends(get_service)
) -> SendMessageResponse:
    """
    Answer a clarification question from the CKO.

    When the CKO needs more information, it asks a clarification question.
    Use this endpoint to provide your answer, which will trigger a
    follow-up response.
    """
    try:
        response = await service.answer_clarification(
            message_id=message_id,
            user_id=user_id,
            answer=request.answer
        )

        if not response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clarification not found or already answered"
            )

        # Convert to response format
        msg = response.message
        sources = [
            SourceResponse(
                docId=s.doc_id,
                title=s.title,
                snippet=s.snippet,
                relevanceScore=s.relevance_score,
                pageNumber=s.page_number,
                department=s.department,
            )
            for s in msg.sources
        ]

        return SendMessageResponse(
            success=True,
            message=MessageResponse(
                id=msg.id,
                sessionId=msg.session_id,
                role=msg.role.value,
                content=msg.content,
                sources=sources,
                actionsPerformed=msg.actions_performed,
                createdAt=msg.created_at.isoformat() if msg.created_at else None,
            ),
            queryTimeMs=response.query_time_ms,
            sourcesCount=response.sources_count,
            sessionUpdated=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to answer clarification", message_id=message_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to answer clarification: {str(e)}"
        )


@router.post("/messages/{message_id}/skip", status_code=status.HTTP_200_OK)
async def skip_clarification(
    message_id: str,
    user_id: str = Depends(get_current_user),
    service: StudioCKOConversationService = Depends(get_service)
) -> Dict[str, Any]:
    """
    Skip a clarification question from the CKO.

    Use this when you don't want to answer a clarification question
    and prefer to continue without providing additional context.
    """
    try:
        success = await service.skip_clarification(
            message_id=message_id,
            user_id=user_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clarification not found"
            )

        return {"success": True, "status": "skipped"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to skip clarification", message_id=message_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to skip clarification: {str(e)}"
        )


# ============================================================================
# Clarification Count Endpoint
# ============================================================================

@router.get("/clarifications/count", response_model=ClarificationCountResponse)
async def get_clarifications_count(
    user_id: str = Depends(get_current_user),
    service: StudioCKOConversationService = Depends(get_service)
) -> ClarificationCountResponse:
    """
    Get the count of pending clarifications for the current user.

    Also indicates whether any clarifications are overdue (>24 hours old).
    This is used for the notification badge in the AI Studio sidebar.
    """
    try:
        count, has_overdue = await service.get_pending_clarifications_count(user_id)

        return ClarificationCountResponse(
            count=count,
            hasOverdue=has_overdue
        )

    except Exception as e:
        logger.error("Failed to get clarification count", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get clarification count: {str(e)}"
        )


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check for CKO conversation service."""
    return HealthResponse(
        status="healthy",
        service="studio_cko_conversation",
        embeddingModel="bge-m3",
        llmModel="claude-sonnet-4-5-20250929",
        queryExpansionEnabled=True,
    )
