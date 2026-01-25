"""
Session Management API Routes - Task 28

Endpoints for managing user sessions: create, retrieve, update, delete, export.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from app.services.session_management_service import (
    SessionManagementService,
    Session
)
from app.core.database import get_supabase, get_redis


router = APIRouter(prefix="/sessions", tags=["Sessions"])


# ==================== Request/Response Models ====================

class CreateSessionRequest(BaseModel):
    """Request model for creating a session"""
    user_id: str = Field(..., description="User identifier")
    title: Optional[str] = Field(None, description="Session title")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Session metadata")


class UpdateSessionActivityRequest(BaseModel):
    """Request model for updating session activity"""
    message_count_delta: int = Field(1, description="Number of messages to add")
    tokens_delta: int = Field(0, description="Number of tokens to add")


class UpdateSessionMetadataRequest(BaseModel):
    """Request model for updating session metadata"""
    metadata: Dict[str, Any] = Field(..., description="New metadata")
    merge: bool = Field(True, description="Merge with existing metadata")


class SessionResponse(BaseModel):
    """Response model for session data"""
    id: str
    user_id: str
    title: Optional[str]
    summary: Optional[str]
    is_active: bool
    message_count: int
    total_tokens: int
    first_message_at: Optional[datetime]
    last_message_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    session_metadata: Dict[str, Any]

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Response model for list of sessions"""
    sessions: List[SessionResponse]
    total: int


class SessionStatsResponse(BaseModel):
    """Response model for session statistics"""
    total_sessions: int
    active_sessions: int
    total_messages: int
    total_tokens: int
    average_messages_per_session: float
    average_tokens_per_session: float


# ==================== Dependency ====================

def get_session_service() -> SessionManagementService:
    """Get SessionManagementService instance"""
    return SessionManagementService(
        supabase_client=get_supabase(),
        redis_client=get_redis()
    )


# ==================== Endpoints ====================

@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    service: SessionManagementService = Depends(get_session_service)
):
    """
    Create a new session.

    Automatically cleans up oldest session if user has reached max limit.
    """
    session = await service.create_session(
        user_id=request.user_id,
        title=request.title,
        metadata=request.metadata
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session"
        )

    return SessionResponse(**session.to_dict())


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    user_id: str,
    service: SessionManagementService = Depends(get_session_service)
):
    """
    Get a specific session by ID.

    Retrieves from Redis cache if available, otherwise from Supabase.
    """
    session = await service.get_session(session_id, user_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    return SessionResponse(**session.to_dict())


@router.get("/user/{user_id}", response_model=SessionListResponse)
async def get_user_sessions(
    user_id: str,
    active_only: bool = False,
    limit: int = 50,
    service: SessionManagementService = Depends(get_session_service)
):
    """
    Get all sessions for a user.

    Can filter to active sessions only and limit results.
    """
    sessions = await service.get_user_sessions(
        user_id=user_id,
        active_only=active_only,
        limit=limit
    )

    return SessionListResponse(
        sessions=[SessionResponse(**s.to_dict()) for s in sessions],
        total=len(sessions)
    )


@router.post("/{session_id}/activity", response_model=SessionResponse)
async def update_session_activity(
    session_id: str,
    user_id: str,
    request: UpdateSessionActivityRequest,
    service: SessionManagementService = Depends(get_session_service)
):
    """
    Update session activity (message count and tokens).

    Also updates last_message_at timestamp and refreshes Redis cache.
    """
    session = await service.update_session_activity(
        session_id=session_id,
        user_id=user_id,
        message_count_delta=request.message_count_delta,
        tokens_delta=request.tokens_delta
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    return SessionResponse(**session.to_dict())


@router.patch("/{session_id}/metadata", response_model=SessionResponse)
async def update_session_metadata(
    session_id: str,
    user_id: str,
    request: UpdateSessionMetadataRequest,
    service: SessionManagementService = Depends(get_session_service)
):
    """
    Update session metadata.

    Can either merge with existing metadata or replace entirely.
    """
    session = await service.update_session_metadata(
        session_id=session_id,
        user_id=user_id,
        metadata=request.metadata,
        merge=request.merge
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    return SessionResponse(**session.to_dict())


@router.post("/{session_id}/deactivate", response_model=Dict[str, str])
async def deactivate_session(
    session_id: str,
    user_id: str,
    service: SessionManagementService = Depends(get_session_service)
):
    """
    Deactivate a session.

    Sets is_active to false and removes from Redis cache.
    """
    success = await service.deactivate_session(session_id, user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found or already deactivated"
        )

    return {"message": f"Session {session_id} deactivated successfully"}


@router.delete("/{session_id}", response_model=Dict[str, str])
async def delete_session(
    session_id: str,
    user_id: str,
    service: SessionManagementService = Depends(get_session_service)
):
    """
    Permanently delete a session.

    Removes from both Supabase and Redis cache.
    """
    success = await service.delete_session(session_id, user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    return {"message": f"Session {session_id} deleted successfully"}


@router.get("/{session_id}/export", response_model=Dict[str, Any])
async def export_session(
    session_id: str,
    user_id: str,
    include_messages: bool = True,
    service: SessionManagementService = Depends(get_session_service)
):
    """
    Export session data as JSON.

    Optionally include messages from the session.
    """
    export_data = await service.export_session(
        session_id=session_id,
        user_id=user_id,
        include_messages=include_messages
    )

    if not export_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    return export_data


@router.get("/user/{user_id}/stats", response_model=SessionStatsResponse)
async def get_session_statistics(
    user_id: str,
    service: SessionManagementService = Depends(get_session_service)
):
    """
    Get session statistics for a user.

    Returns total sessions, active sessions, messages, tokens, and averages.
    """
    stats = await service.get_session_statistics(user_id)

    return SessionStatsResponse(**stats)


@router.post("/cleanup", response_model=Dict[str, Any])
async def cleanup_expired_sessions(
    user_id: Optional[str] = None,
    service: SessionManagementService = Depends(get_session_service)
):
    """
    Clean up expired sessions.

    If user_id provided, only cleans up that user's sessions.
    Otherwise cleans up all expired sessions.
    """
    count = await service.cleanup_expired_sessions(user_id=user_id)

    return {
        "message": "Cleanup completed",
        "sessions_cleaned": count
    }
