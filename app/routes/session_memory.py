"""
Empire v7.3 - Session Memory API Routes
REST API endpoints for session memory and persistence.

Feature: Chat Context Window Management (011)
Task: 207 - Implement Session Memory & Persistence
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog

from app.services.session_memory_service import (
    SessionMemoryService,
    get_session_memory_service,
)
from app.services.context_manager_service import get_context_manager
from app.models.context_models import (
    SessionMemory,
    RetentionType,
    ContextMessage,
)
from app.middleware.auth import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/session-memory", tags=["Session Memory"])


# =============================================================================
# Request/Response Models
# =============================================================================

class SaveMemoryRequest(BaseModel):
    """Request body for saving a session memory."""
    conversation_id: str = Field(..., description="Conversation to save memory for")
    project_id: Optional[str] = Field(None, description="Associated project ID")
    retention_type: str = Field(
        default="project",
        description="Retention policy: project, cko, or indefinite"
    )


class SaveMemoryResponse(BaseModel):
    """Response after saving a memory."""
    success: bool
    memory_id: Optional[str] = None
    summary_preview: Optional[str] = None
    decisions_count: int = 0
    files_count: int = 0
    code_refs_count: int = 0
    error: Optional[str] = None


class MemorySummary(BaseModel):
    """Summary of a memory for list views."""
    id: str
    conversation_id: str
    project_id: Optional[str]
    summary_preview: str
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime


class MemoryListResponse(BaseModel):
    """Response for memory list."""
    success: bool
    memories: List[MemorySummary] = []
    total: int = 0
    error: Optional[str] = None


class MemoryDetailResponse(BaseModel):
    """Response with full memory details."""
    success: bool
    memory: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SearchMemoryRequest(BaseModel):
    """Request for semantic memory search."""
    query: str = Field(..., min_length=3, description="Search query")
    project_id: Optional[str] = Field(None, description="Filter by project")
    limit: int = Field(default=5, ge=1, le=20, description="Max results")


class ResumeSessionResponse(BaseModel):
    """Response for session resume."""
    success: bool
    conversation_id: Optional[str] = None
    memory: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    messages_count: int = 0
    token_count: int = 0
    error: Optional[str] = None


class ResumableSessionSummary(BaseModel):
    """Summary of a resumable session."""
    memory_id: str
    conversation_id: str
    project_id: Optional[str]
    summary_preview: str
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime


class ResumableSessionsResponse(BaseModel):
    """Response with list of resumable sessions."""
    success: bool
    sessions: List[ResumableSessionSummary] = []
    total: int = 0
    error: Optional[str] = None


class UpdateMemoryRequest(BaseModel):
    """Request for updating a memory."""
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    retention_type: Optional[str] = None


class AddNoteRequest(BaseModel):
    """Request for adding a manual memory note."""
    project_id: str = Field(..., min_length=1, description="Project to attach note to")
    content: str = Field(..., min_length=1, max_length=5000, description="Note content")
    tags: Optional[List[str]] = Field(None, description="Optional tags")


# =============================================================================
# Memory Creation Endpoints
# =============================================================================

@router.post("/save", response_model=SaveMemoryResponse)
async def save_session_memory(
    request: SaveMemoryRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Save a session memory for a conversation.

    Creates a persistent summary of the conversation with extracted
    decisions, code references, and file mentions.
    """
    try:
        service = get_session_memory_service()
        context_manager = get_context_manager()

        # Get messages from context
        status_result = await context_manager.get_context_status(
            request.conversation_id, user_id
        )

        if not status_result.success:
            raise HTTPException(status_code=404, detail="Conversation context not found")

        # Get messages
        from app.core.database import get_supabase
        supabase = get_supabase()

        # Get context ID
        ctx_result = supabase.table("conversation_contexts").select(
            "id"
        ).eq("conversation_id", request.conversation_id).eq(
            "user_id", user_id
        ).single().execute()

        if not ctx_result.data:
            raise HTTPException(status_code=404, detail="Context not found")

        context_id = ctx_result.data["id"]

        # Get messages
        msg_result = supabase.table("context_messages").select(
            "*"
        ).eq("context_id", context_id).order(
            "position", desc=False
        ).execute()

        messages = []
        if msg_result.data:
            from app.models.context_models import MessageRole
            for row in msg_result.data:
                messages.append(ContextMessage(
                    id=row["id"],
                    context_id=row["context_id"],
                    role=MessageRole(row["role"]),
                    content=row["content"],
                    token_count=row["token_count"],
                    is_protected=row.get("is_protected", False),
                    position=row["position"],
                    created_at=row.get("created_at", datetime.utcnow())
                ))

        if not messages:
            return SaveMemoryResponse(
                success=False,
                error="No messages found in conversation"
            )

        # Parse retention type
        try:
            retention = RetentionType(request.retention_type)
        except ValueError:
            retention = RetentionType.PROJECT

        # Save memory
        memory_id = await service.save_session_memory(
            conversation_id=request.conversation_id,
            user_id=user_id,
            messages=messages,
            project_id=request.project_id,
            retention_type=retention
        )

        if not memory_id:
            return SaveMemoryResponse(
                success=False,
                error="Failed to save memory"
            )

        # Get the saved memory for response
        memory_result = supabase.table("session_memories").select(
            "summary, key_decisions, files_mentioned, code_preserved"
        ).eq("id", memory_id).single().execute()

        if memory_result.data:
            import json
            data = memory_result.data
            return SaveMemoryResponse(
                success=True,
                memory_id=memory_id,
                summary_preview=data["summary"][:200] + "..." if len(data["summary"]) > 200 else data["summary"],
                decisions_count=len(json.loads(data.get("key_decisions", "[]"))),
                files_count=len(json.loads(data.get("files_mentioned", "[]"))),
                code_refs_count=len(json.loads(data.get("code_preserved", "[]")))
            )

        return SaveMemoryResponse(
            success=True,
            memory_id=memory_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "save_session_memory_failed",
            conversation_id=request.conversation_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to save session memory") from e


@router.post("/note", response_model=SaveMemoryResponse)
async def add_memory_note(
    request: AddNoteRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Create a manual memory note for a project. No LLM summarization.
    """
    try:
        from uuid import uuid4

        normalized_content = request.content.strip()
        if not normalized_content:
            return SaveMemoryResponse(
                success=False,
                error="Note content cannot be blank"
            )

        service = get_session_memory_service()
        memory_id = await service.add_note(
            user_id=user_id,
            conversation_id=f"manual-note-{uuid4()}",
            summary=normalized_content,
            tags=request.tags or [],
            project_id=request.project_id,
            retention_type=RetentionType.INDEFINITE,
        )

        if not memory_id:
            return SaveMemoryResponse(
                success=False,
                error="Failed to save note"
            )

        return SaveMemoryResponse(
            success=True,
            memory_id=memory_id,
            summary_preview=normalized_content[:200] + "..." if len(normalized_content) > 200 else normalized_content
        )

    except Exception as e:
        logger.exception("add_memory_note_failed")
        raise HTTPException(status_code=500, detail="Failed to save note") from e


# =============================================================================
# Memory Retrieval Endpoints
# =============================================================================

@router.post("/search", response_model=MemoryListResponse)
async def search_memories(
    request: SearchMemoryRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Search memories using semantic similarity.

    Returns memories that are semantically similar to the query.
    """
    try:
        service = get_session_memory_service()

        memories = await service.get_relevant_memories(
            user_id=user_id,
            query=request.query,
            project_id=request.project_id,
            limit=request.limit
        )

        return MemoryListResponse(
            success=True,
            memories=[
                MemorySummary(
                    id=m.id,
                    conversation_id=m.conversation_id,
                    project_id=m.project_id,
                    summary_preview=m.summary[:200] + "..." if len(m.summary) > 200 else m.summary,
                    tags=m.tags or [],
                    created_at=m.created_at,
                    updated_at=m.updated_at
                )
                for m in memories
            ],
            total=len(memories)
        )

    except Exception as e:
        logger.error("search_memories_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to search memories") from e


@router.get("/project/{project_id}", response_model=MemoryListResponse)
async def get_project_memories(
    project_id: str,
    limit: int = Query(default=10, ge=1, le=20),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user)
):
    """
    Get all memories for a specific project.
    """
    try:
        service = get_session_memory_service()

        memories, total = await service.get_project_memories(
            user_id=user_id,
            project_id=project_id,
            limit=limit,
            offset=offset,
        )

        return MemoryListResponse(
            success=True,
            memories=[
                MemorySummary(
                    id=m.id,
                    conversation_id=m.conversation_id,
                    project_id=m.project_id,
                    summary_preview=m.summary[:200] + "..." if len(m.summary) > 200 else m.summary,
                    tags=m.tags or [],
                    created_at=m.created_at,
                    updated_at=m.updated_at
                )
                for m in memories
            ],
            total=total,
        )

    except Exception as e:
        logger.error(
            "get_project_memories_failed",
            project_id=project_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve project memories") from e


@router.get("/{memory_id}", response_model=MemoryDetailResponse)
async def get_memory(
    memory_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get a specific memory with full details.
    """
    try:
        from app.core.database import get_supabase
        import json

        supabase = get_supabase()

        result = supabase.table("session_memories").select(
            "*"
        ).eq("id", memory_id).eq("user_id", user_id).single().execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Memory not found")

        row = result.data
        return MemoryDetailResponse(
            success=True,
            memory={
                "id": row["id"],
                "conversation_id": row["conversation_id"],
                "project_id": row.get("project_id"),
                "summary": row["summary"],
                "key_decisions": json.loads(row.get("key_decisions", "[]")),
                "files_mentioned": json.loads(row.get("files_mentioned", "[]")),
                "code_preserved": json.loads(row.get("code_preserved", "[]")),
                "tags": row.get("tags", []),
                "retention_type": row["retention_type"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "expires_at": row.get("expires_at")
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_memory_failed",
            memory_id=memory_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve memory") from e


# =============================================================================
# Session Resume Endpoints
# =============================================================================

@router.get("/resumable", response_model=ResumableSessionsResponse)
async def get_resumable_sessions(
    project_id: Optional[str] = Query(None),
    limit: int = Query(default=10, ge=1, le=50),
    user_id: str = Depends(get_current_user)
):
    """
    Get list of sessions that can be resumed.
    """
    try:
        service = get_session_memory_service()

        sessions = await service.get_resumable_sessions(
            user_id=user_id,
            project_id=project_id,
            limit=limit
        )

        return ResumableSessionsResponse(
            success=True,
            sessions=[
                ResumableSessionSummary(
                    memory_id=s["memory_id"],
                    conversation_id=s["conversation_id"],
                    project_id=s.get("project_id"),
                    summary_preview=s["summary_preview"],
                    tags=s.get("tags", []),
                    created_at=datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(s["updated_at"].replace("Z", "+00:00"))
                )
                for s in sessions
            ],
            total=len(sessions)
        )

    except Exception as e:
        logger.error(
            "get_resumable_sessions_failed",
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to get resumable sessions") from e


@router.post("/resume/{conversation_id}", response_model=ResumeSessionResponse)
async def resume_session(
    conversation_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Resume a previous session.

    Loads the session memory and context for continuing the conversation.
    """
    try:
        service = get_session_memory_service()

        result = await service.resume_session(
            conversation_id=conversation_id,
            user_id=user_id
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Session not found or cannot be resumed"
            )

        return ResumeSessionResponse(
            success=True,
            conversation_id=result["conversation_id"],
            memory=result.get("memory"),
            context=result.get("context"),
            messages_count=len(result.get("messages", [])),
            token_count=result.get("token_count", 0)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "resume_session_failed",
            conversation_id=conversation_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to resume session") from e


# =============================================================================
# Memory Management Endpoints
# =============================================================================

@router.patch("/{memory_id}", response_model=MemoryDetailResponse)
async def update_memory(
    memory_id: str,
    request: UpdateMemoryRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Update a memory's metadata.
    """
    try:
        service = get_session_memory_service()

        updates = {}
        if request.summary is not None:
            updates["summary"] = request.summary
        if request.tags is not None:
            updates["tags"] = request.tags
        if request.retention_type is not None:
            updates["retention_type"] = request.retention_type

        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        success = await service.update_memory(
            memory_id=memory_id,
            user_id=user_id,
            updates=updates
        )

        if not success:
            raise HTTPException(status_code=404, detail="Memory not found or update failed")

        # Return updated memory
        return await get_memory(memory_id, user_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "update_memory_failed",
            memory_id=memory_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to update memory") from e


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Delete a memory.
    """
    try:
        service = get_session_memory_service()

        success = await service.delete_memory(
            memory_id=memory_id,
            user_id=user_id
        )

        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")

        return {"success": True, "deleted_id": memory_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "delete_memory_failed",
            memory_id=memory_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to delete memory") from e


# =============================================================================
# Health Endpoint
# =============================================================================

@router.get("/health")
async def health_check():
    """
    Health check for session memory service.
    """
    try:
        service = get_session_memory_service()

        return {
            "status": "healthy",
            "service": "session-memory",
            "memory_expiration_days": service.memory_expiration_days,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "session-memory",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
