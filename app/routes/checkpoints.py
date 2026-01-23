"""
Empire v7.3 - Checkpoint API Routes
REST API endpoints for session checkpoints and crash recovery.

Feature: Chat Context Window Management (011)
Task: 206 - Implement Automatic Checkpoint System
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog

from app.services.checkpoint_service import (
    CheckpointService,
    get_checkpoint_service,
)
from app.services.context_manager_service import get_context_manager
from app.models.context_models import (
    SessionCheckpoint,
    CheckpointResponse,
    CheckpointListResponse,
    RecoveryCheckResponse,
    CreateCheckpointRequest,
    ContextMessage,
)
from app.middleware.auth import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/checkpoints", tags=["Checkpoints"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateCheckpointRequestBody(BaseModel):
    """Request body for creating a checkpoint."""
    label: Optional[str] = Field(None, max_length=200, description="User-provided label")
    trigger: str = Field(default="manual", description="Trigger type: manual, auto, pre_compaction")


class CheckpointSummary(BaseModel):
    """Summary of a checkpoint for list views."""
    id: str
    conversation_id: str
    label: Optional[str]
    auto_tag: Optional[str]
    token_count: int
    is_abnormal_close: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CheckpointListResponseBody(BaseModel):
    """Response for checkpoint list."""
    success: bool
    checkpoints: List[CheckpointSummary] = []
    total: int = 0
    error: Optional[str] = None


class CheckpointDetailResponse(BaseModel):
    """Response for single checkpoint with full data."""
    success: bool
    checkpoint: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class RecoveryCheckResponseBody(BaseModel):
    """Response for recovery check."""
    success: bool
    has_recovery: bool = False
    checkpoint_id: Optional[str] = None
    conversation_id: Optional[str] = None
    conversation_title: Optional[str] = None
    created_at: Optional[datetime] = None
    token_count: Optional[int] = None
    error: Optional[str] = None


class RestoreCheckpointResponse(BaseModel):
    """Response after restoring from checkpoint."""
    success: bool
    conversation_id: Optional[str] = None
    messages_count: int = 0
    token_count: int = 0
    restored_from: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Static Routes (must come before parameterized routes)
# =============================================================================

@router.get("/health")
async def health_check():
    """
    Health check for checkpoint service.
    """
    try:
        service = get_checkpoint_service()

        return {
            "status": "healthy",
            "service": "checkpoints",
            "max_checkpoints_per_session": service._max_checkpoints,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "checkpoints",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/recovery/check", response_model=RecoveryCheckResponseBody)
async def check_recovery(
    user_id: str = Depends(get_current_user)
):
    """
    Check if there are any sessions requiring recovery.

    Returns information about the most recent abnormal close checkpoint.
    """
    try:
        service = get_checkpoint_service()

        result = await service.check_for_recovery(user_id)

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)

        if not result.has_recovery:
            return RecoveryCheckResponseBody(
                success=True,
                has_recovery=False
            )

        checkpoint = result.checkpoint

        return RecoveryCheckResponseBody(
            success=True,
            has_recovery=True,
            checkpoint_id=checkpoint.id if checkpoint else None,
            conversation_id=checkpoint.conversation_id if checkpoint else None,
            conversation_title=result.conversation_title,
            created_at=checkpoint.created_at if checkpoint else None,
            token_count=checkpoint.token_count if checkpoint else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "check_recovery_failed",
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recovery/{checkpoint_id}/restore", response_model=RestoreCheckpointResponse)
async def restore_from_recovery(
    checkpoint_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Restore from a recovery checkpoint and clear the recovery flag.
    """
    try:
        service = get_checkpoint_service()

        # Restore the checkpoint
        restored_data = await service.restore_checkpoint(checkpoint_id, user_id)

        if not restored_data:
            raise HTTPException(status_code=500, detail="Failed to restore checkpoint")

        # Clear the abnormal close flag
        await service.clear_recovery_checkpoint(checkpoint_id, user_id)

        return RestoreCheckpointResponse(
            success=True,
            conversation_id=restored_data["conversation_id"],
            messages_count=len(restored_data["messages"]),
            token_count=restored_data["token_count"],
            restored_from=checkpoint_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "restore_recovery_failed",
            checkpoint_id=checkpoint_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recovery/{checkpoint_id}/dismiss")
async def dismiss_recovery(
    checkpoint_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Dismiss a recovery checkpoint without restoring.

    This clears the abnormal close flag so it won't appear again.
    """
    try:
        service = get_checkpoint_service()

        success = await service.clear_recovery_checkpoint(checkpoint_id, user_id)

        if not success:
            raise HTTPException(status_code=404, detail="Recovery checkpoint not found")

        return {"success": True, "dismissed": checkpoint_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "dismiss_recovery_failed",
            checkpoint_id=checkpoint_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Checkpoint Management Endpoints (parameterized routes)
# =============================================================================

@router.post("/{conversation_id}", response_model=CheckpointDetailResponse)
async def create_checkpoint(
    conversation_id: str,
    request: CreateCheckpointRequestBody,
    user_id: str = Depends(get_current_user)
):
    """
    Create a manual checkpoint for a conversation.

    This endpoint is used for the /save-progress or /checkpoint commands.
    It saves the current conversation state for later recovery.
    """
    try:
        service = get_checkpoint_service()
        context_manager = get_context_manager()

        # Get current context status
        status_result = await context_manager.get_context_status(conversation_id, user_id)

        if not status_result.success:
            raise HTTPException(status_code=404, detail="Conversation context not found")

        # Get messages from context (we need to query them)
        from app.core.database import get_supabase
        supabase = get_supabase()

        # First get context ID
        ctx_result = supabase.table("conversation_contexts").select(
            "id"
        ).eq("conversation_id", conversation_id).eq(
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
            for row in msg_result.data:
                messages.append(ContextMessage(
                    id=row["id"],
                    context_id=row["context_id"],
                    role=row["role"],
                    content=row["content"],
                    token_count=row["token_count"],
                    is_protected=row.get("is_protected", False),
                    position=row["position"],
                    created_at=row.get("created_at", datetime.utcnow())
                ))

        # Create the checkpoint
        result = await service.create_checkpoint(
            conversation_id=conversation_id,
            user_id=user_id,
            messages=messages,
            token_count=status_result.status.current_tokens if status_result.status else 0,
            trigger=request.trigger,
            label=request.label,
        )

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)

        return CheckpointDetailResponse(
            success=True,
            checkpoint={
                "id": result.checkpoint.id,
                "conversation_id": result.checkpoint.conversation_id,
                "label": result.checkpoint.label,
                "auto_tag": result.checkpoint.auto_tag.value if result.checkpoint.auto_tag else None,
                "token_count": result.checkpoint.token_count,
                "created_at": result.checkpoint.created_at.isoformat(),
            } if result.checkpoint else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "create_checkpoint_endpoint_failed",
            conversation_id=conversation_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}", response_model=CheckpointListResponseBody)
async def list_checkpoints(
    conversation_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user)
):
    """
    List all checkpoints for a conversation.

    Returns checkpoints in reverse chronological order (newest first).
    """
    try:
        service = get_checkpoint_service()

        result = await service.get_checkpoints(
            conversation_id=conversation_id,
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)

        checkpoints = [
            CheckpointSummary(
                id=cp.id,
                conversation_id=cp.conversation_id,
                label=cp.label,
                auto_tag=cp.auto_tag.value if cp.auto_tag else None,
                token_count=cp.token_count,
                is_abnormal_close=cp.is_abnormal_close,
                created_at=cp.created_at
            )
            for cp in result.checkpoints
        ]

        return CheckpointListResponseBody(
            success=True,
            checkpoints=checkpoints,
            total=result.total
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "list_checkpoints_failed",
            conversation_id=conversation_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/{checkpoint_id}", response_model=CheckpointDetailResponse)
async def get_checkpoint(
    conversation_id: str,
    checkpoint_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get a specific checkpoint with full data.

    Returns the complete checkpoint including message snapshot.
    """
    try:
        service = get_checkpoint_service()

        result = await service.get_checkpoint(
            checkpoint_id=checkpoint_id,
            user_id=user_id
        )

        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)

        if not result.checkpoint:
            raise HTTPException(status_code=404, detail="Checkpoint not found")

        # Verify conversation_id matches
        if result.checkpoint.conversation_id != conversation_id:
            raise HTTPException(status_code=404, detail="Checkpoint not found")

        checkpoint = result.checkpoint

        return CheckpointDetailResponse(
            success=True,
            checkpoint={
                "id": checkpoint.id,
                "conversation_id": checkpoint.conversation_id,
                "label": checkpoint.label,
                "auto_tag": checkpoint.auto_tag.value if checkpoint.auto_tag else None,
                "token_count": checkpoint.token_count,
                "is_abnormal_close": checkpoint.is_abnormal_close,
                "created_at": checkpoint.created_at.isoformat(),
                "expires_at": checkpoint.expires_at.isoformat(),
                "checkpoint_data": checkpoint.checkpoint_data,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_checkpoint_failed",
            checkpoint_id=checkpoint_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conversation_id}/{checkpoint_id}")
async def delete_checkpoint(
    conversation_id: str,
    checkpoint_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Delete a specific checkpoint.
    """
    try:
        from app.core.database import get_supabase
        supabase = get_supabase()

        # Delete checkpoint (with user_id verification)
        result = supabase.table("session_checkpoints").delete().eq(
            "id", checkpoint_id
        ).eq(
            "conversation_id", conversation_id
        ).eq(
            "user_id", user_id
        ).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Checkpoint not found")

        return {"success": True, "deleted_id": checkpoint_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "delete_checkpoint_failed",
            checkpoint_id=checkpoint_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Checkpoint Restoration Endpoints
# =============================================================================

@router.post("/{conversation_id}/{checkpoint_id}/restore", response_model=RestoreCheckpointResponse)
async def restore_from_checkpoint(
    conversation_id: str,
    checkpoint_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Restore a conversation from a checkpoint.

    This replaces the current conversation state with the checkpoint's state.
    """
    try:
        service = get_checkpoint_service()

        # Verify checkpoint belongs to conversation
        check_result = await service.get_checkpoint(checkpoint_id, user_id)
        if not check_result.success or not check_result.checkpoint:
            raise HTTPException(status_code=404, detail="Checkpoint not found")

        if check_result.checkpoint.conversation_id != conversation_id:
            raise HTTPException(status_code=404, detail="Checkpoint not found")

        # Restore the checkpoint
        restored_data = await service.restore_checkpoint(checkpoint_id, user_id)

        if not restored_data:
            raise HTTPException(status_code=500, detail="Failed to restore checkpoint")

        return RestoreCheckpointResponse(
            success=True,
            conversation_id=restored_data["conversation_id"],
            messages_count=len(restored_data["messages"]),
            token_count=restored_data["token_count"],
            restored_from=checkpoint_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "restore_checkpoint_failed",
            checkpoint_id=checkpoint_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))
