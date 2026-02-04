"""
Empire v7.3 - Context Window API Routes
REST API endpoints for chat context window status and management.

Feature: Chat Context Window Management (011)
Task: 202 - Context Window Progress Bar UI
Task: 209 - Compact Command & API (rate limiting, history)
"""

from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import asyncio
import json
import time
import structlog

from app.services.context_manager_service import (
    ContextManagerService,
    get_context_manager,
)
from app.services.context_condensing_engine import (
    get_condensing_engine,
)
from app.models.context_models import (
    ContextWindowStatus,
    ContextStatusResponse,
    AddMessageRequest,
    AddMessageResponse,
    ToggleProtectionRequest,
    TriggerCompactionRequest,
    CompactionStatusResponse,
    CompactionResultResponse,
    CompactionResult,
    CompactionTrigger,
    MessageRole,
)
from app.middleware.auth import get_current_user
from app.core.database import get_redis

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/context-window", tags=["Context Window"])


# =============================================================================
# Rate Limiting (Task 209)
# =============================================================================

COMPACTION_COOLDOWN_SECONDS = 30
COMPACTION_RATE_LIMIT_KEY = "compaction:ratelimit:{conversation_id}"


async def check_compaction_rate_limit(conversation_id: str, force: bool = False) -> tuple[bool, int]:
    """
    Check if compaction is rate limited.

    Args:
        conversation_id: Conversation ID
        force: If True, bypass rate limit

    Returns:
        Tuple of (is_allowed, cooldown_remaining_seconds)
    """
    if force:
        return True, 0

    try:
        redis = get_redis()
        key = COMPACTION_RATE_LIMIT_KEY.format(conversation_id=conversation_id)
        last_compaction = redis.get(key)

        if last_compaction:
            last_time = float(last_compaction.decode() if isinstance(last_compaction, bytes) else last_compaction)
            elapsed = time.time() - last_time
            remaining = COMPACTION_COOLDOWN_SECONDS - elapsed

            if remaining > 0:
                return False, int(remaining)

        return True, 0

    except Exception as e:
        logger.warning("rate_limit_check_failed", error=str(e))
        # Allow on error to not block users
        return True, 0


async def update_compaction_rate_limit(conversation_id: str) -> None:
    """Update the rate limit timestamp after successful compaction."""
    try:
        redis = get_redis()
        key = COMPACTION_RATE_LIMIT_KEY.format(conversation_id=conversation_id)
        redis.setex(key, COMPACTION_COOLDOWN_SECONDS + 10, str(time.time()))
    except Exception as e:
        logger.warning("rate_limit_update_failed", error=str(e))


# =============================================================================
# Request/Response Models
# =============================================================================

class ContextWindowStatusResponse(BaseModel):
    """Response model for context window status."""
    conversation_id: str
    current_tokens: int
    max_tokens: int
    reserved_tokens: int = Field(default=10000, description="Tokens reserved for AI response")
    threshold_percent: int
    usage_percent: float
    status: str  # normal, warning, critical
    available_tokens: int
    estimated_messages_remaining: int
    is_compacting: bool
    last_compaction_at: Optional[datetime]
    last_updated: datetime

    class Config:
        from_attributes = True


class CompactionHistoryItem(BaseModel):
    """Single compaction history entry (Task 209)."""
    id: str
    context_id: str
    pre_tokens: int
    post_tokens: int
    reduction_percent: float
    summary_preview: Optional[str] = None
    messages_condensed: int
    model_used: str
    duration_ms: int
    triggered_by: str  # auto, manual, force
    created_at: datetime

    class Config:
        from_attributes = True


class CompactionHistoryResponse(BaseModel):
    """Response for compaction history endpoint (Task 209)."""
    success: bool
    conversation_id: str
    history: List[CompactionHistoryItem] = []
    total_count: int = 0
    has_more: bool = False
    skip: int = 0
    limit: int = 20
    error: Optional[str] = None


class WebSocketConnectionManager:
    """Manages WebSocket connections for real-time context updates."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, conversation_id: str):
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)
        logger.info(
            "websocket_connected",
            conversation_id=conversation_id,
            total_connections=len(self.active_connections[conversation_id])
        )

    def disconnect(self, websocket: WebSocket, conversation_id: str):
        if conversation_id in self.active_connections:
            if websocket in self.active_connections[conversation_id]:
                self.active_connections[conversation_id].remove(websocket)
            if not self.active_connections[conversation_id]:
                del self.active_connections[conversation_id]
        logger.info("websocket_disconnected", conversation_id=conversation_id)

    async def broadcast_status(self, conversation_id: str, status: ContextWindowStatus):
        """Broadcast context status update to all connected clients."""
        if conversation_id not in self.active_connections:
            return

        message = json.dumps({
            "type": "context_status_update",
            "data": {
                "conversation_id": status.conversation_id,
                "current_tokens": status.current_tokens,
                "max_tokens": status.max_tokens,
                "usage_percent": status.usage_percent,
                "status": status.status.value,
                "available_tokens": status.available_tokens,
                "estimated_messages_remaining": status.estimated_messages_remaining,
                "is_compacting": status.is_compacting,
                "last_updated": status.last_updated.isoformat()
            }
        })

        disconnected = []
        for connection in self.active_connections[conversation_id]:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning("websocket_send_failed", error=str(e))
                disconnected.append(connection)

        # Clean up disconnected
        for conn in disconnected:
            self.disconnect(conn, conversation_id)


# Global connection manager
ws_manager = WebSocketConnectionManager()


# =============================================================================
# Static Routes (must come before parameterized routes)
# =============================================================================

@router.get("/thresholds")
async def get_context_thresholds():
    """
    Get the context window threshold configuration.

    Returns the threshold values used for status indicators:
    - Normal: < 70% usage
    - Warning: 70-85% usage
    - Critical: > 85% usage
    """
    return {
        "normal_max_percent": 70,
        "warning_max_percent": 85,
        "critical_min_percent": 85,
        "reserved_buffer_percent": 5,
        "default_max_tokens": 200000
    }


@router.get("/health")
async def health_check():
    """
    Health check for context window service.
    """
    try:
        service = get_context_manager()

        return {
            "status": "healthy",
            "service": "context_window",
            "token_counter_available": service.token_counter is not None,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "context_window",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# =============================================================================
# Context Window Status Endpoints
# =============================================================================

@router.get("/{conversation_id}/status", response_model=ContextWindowStatusResponse)
async def get_context_window_status(
    conversation_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get the current context window status for a conversation.

    Returns real-time token usage, thresholds, and estimated capacity.
    This endpoint powers the context window progress bar UI.
    """
    try:
        service = get_context_manager()
        result = await service.get_context_status(conversation_id, user_id)

        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)

        status = result.status

        # Calculate reserved tokens (5% buffer for AI response)
        reserved_tokens = int(status.max_tokens * 0.05)

        return ContextWindowStatusResponse(
            conversation_id=status.conversation_id,
            current_tokens=status.current_tokens,
            max_tokens=status.max_tokens,
            reserved_tokens=reserved_tokens,
            threshold_percent=status.threshold_percent,
            usage_percent=status.usage_percent,
            status=status.status.value,
            available_tokens=status.available_tokens,
            estimated_messages_remaining=status.estimated_messages_remaining,
            is_compacting=status.is_compacting,
            last_compaction_at=status.last_compaction_at,
            last_updated=status.last_updated
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_context_window_status_failed",
            conversation_id=conversation_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{conversation_id}/message", response_model=AddMessageResponse)
async def add_message_to_context(
    conversation_id: str,
    request: AddMessageRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Add a message to the context window and return updated status.

    Automatically counts tokens and updates the context window state.
    Broadcasts the update to all connected WebSocket clients.
    """
    try:
        service = get_context_manager()
        result = await service.add_message_to_context(
            conversation_id=conversation_id,
            user_id=user_id,
            request=request
        )

        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)

        # Broadcast status update to WebSocket clients
        if result.context_status:
            await ws_manager.broadcast_status(conversation_id, result.context_status)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "add_message_to_context_failed",
            conversation_id=conversation_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{conversation_id}/message/{message_id}/protection")
async def toggle_message_protection(
    conversation_id: str,
    message_id: str,
    request: ToggleProtectionRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Toggle protection status for a message.

    Protected messages are preserved during context compaction.
    """
    try:
        service = get_context_manager()
        success = await service.toggle_message_protection(
            message_id=message_id,
            user_id=user_id,
            is_protected=request.is_protected
        )

        if not success:
            raise HTTPException(
                status_code=404,
                detail="Message not found or not authorized"
            )

        return {
            "success": True,
            "message_id": message_id,
            "is_protected": request.is_protected
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "toggle_message_protection_failed",
            message_id=message_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# WebSocket Endpoint for Real-Time Updates
# =============================================================================

@router.websocket("/{conversation_id}/ws")
async def websocket_context_updates(
    websocket: WebSocket,
    conversation_id: str,
    token: Optional[str] = Query(default=None)
):
    """
    WebSocket endpoint for real-time context window updates.

    Clients receive status updates whenever the context window changes:
    - New messages added
    - Token counts updated
    - Compaction events
    - Status changes (normal → warning → critical)

    Authentication:
    - Pass token as query parameter: ws://host/api/context-window/{id}/ws?token=xxx
    - Token should be a valid JWT or session token
    """
    # Validate authentication token
    user_id = None
    if token:
        try:
            from app.middleware.auth import validate_token
            user_id = await validate_token(token)
        except Exception as e:
            logger.warning(
                "websocket_auth_failed",
                conversation_id=conversation_id,
                error=str(e)
            )
            await websocket.close(code=4001, reason="Invalid authentication token")
            return

    if not user_id:
        logger.warning(
            "websocket_no_auth",
            conversation_id=conversation_id
        )
        await websocket.close(code=4001, reason="Authentication required")
        return

    await ws_manager.connect(websocket, conversation_id)

    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, conversation_id)
    except Exception as e:
        logger.warning(
            "websocket_error",
            conversation_id=conversation_id,
            error=str(e)
        )
        ws_manager.disconnect(websocket, conversation_id)


# =============================================================================
# Compaction Endpoints
# =============================================================================

@router.post("/{conversation_id}/compact", response_model=CompactionResultResponse)
async def trigger_compaction(
    conversation_id: str,
    request: TriggerCompactionRequest = TriggerCompactionRequest(),
    user_id: str = Depends(get_current_user)
):
    """
    Trigger context compaction synchronously.

    Compacts the conversation context by summarizing older messages
    while preserving protected messages and critical information.

    Use `fast=True` for quick compaction using Claude Haiku,
    or `force=True` to compact even below the threshold and bypass rate limiting.

    Rate limited to once every 30 seconds unless force=True.
    """
    try:
        # Check rate limiting (Task 209)
        is_allowed, cooldown_remaining = await check_compaction_rate_limit(
            conversation_id, request.force
        )

        if not is_allowed:
            return CompactionResultResponse(
                success=False,
                error=f"Rate limited. Please wait {cooldown_remaining} seconds before compacting again. Use force=True to bypass."
            )

        engine = get_condensing_engine()

        # Determine trigger type
        trigger = CompactionTrigger.FORCE if request.force else CompactionTrigger.MANUAL

        result = await engine.compact_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            trigger=trigger,
            fast=request.fast
        )

        if not result.success:
            return CompactionResultResponse(
                success=False,
                error=result.error_message
            )

        # Update rate limit timestamp on success
        await update_compaction_rate_limit(conversation_id)

        # Get updated context status
        service = get_context_manager()
        status_result = await service.get_context_status(conversation_id, user_id)

        # Broadcast the update
        if status_result.success:
            await ws_manager.broadcast_status(conversation_id, status_result.status)

        return CompactionResultResponse(
            success=True,
            log={
                "id": str(datetime.now(timezone.utc).timestamp()),
                "context_id": conversation_id,
                "pre_tokens": result.pre_tokens,
                "post_tokens": result.post_tokens,
                "reduction_percent": result.reduction_percent,
                "summary_preview": result.summary_preview,
                "messages_condensed": result.messages_condensed,
                "model_used": result.model_used,
                "duration_ms": result.duration_ms,
                "triggered_by": trigger,
                "created_at": result.created_at
            },
            context_status=status_result.status if status_result.success else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "trigger_compaction_failed",
            conversation_id=conversation_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{conversation_id}/compact/async")
async def trigger_async_compaction(
    conversation_id: str,
    request: TriggerCompactionRequest = TriggerCompactionRequest(),
    user_id: str = Depends(get_current_user)
):
    """
    Trigger context compaction asynchronously via Celery.

    Returns immediately with a task_id that can be used to check progress.
    Use this for long conversations where synchronous compaction might timeout.
    """
    try:
        from app.tasks.compaction_tasks import compact_context

        # Determine trigger type
        trigger = "force" if request.force else "manual"

        # Queue the task
        task = compact_context.delay(
            conversation_id=conversation_id,
            user_id=user_id,
            trigger=trigger,
            fast=request.fast,
            queued_at=datetime.now(timezone.utc).isoformat()
        )

        logger.info(
            "async_compaction_queued",
            conversation_id=conversation_id,
            task_id=task.id
        )

        return {
            "success": True,
            "task_id": task.id,
            "conversation_id": conversation_id,
            "status": "queued",
            "message": "Compaction task queued. Use GET /tasks/{task_id}/progress to check status."
        }

    except Exception as e:
        logger.error(
            "trigger_async_compaction_failed",
            conversation_id=conversation_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/compact/progress", response_model=CompactionStatusResponse)
async def get_compaction_progress(
    conversation_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get the current compaction progress for a conversation.

    Returns the progress percentage, current stage, and whether
    compaction is in progress.
    """
    try:
        engine = get_condensing_engine()
        progress = await engine.get_compaction_progress(conversation_id)

        status = "in_progress" if progress.get("in_progress") else "idle"

        return CompactionStatusResponse(
            success=True,
            status=status,
            progress=progress.get("percent", 0),
            stage=progress.get("stage")
        )

    except Exception as e:
        logger.error(
            "get_compaction_progress_failed",
            conversation_id=conversation_id,
            error=str(e)
        )
        return CompactionStatusResponse(
            success=False,
            status="failed",
            error=str(e)
        )


@router.get("/tasks/{task_id}/progress")
async def get_task_progress(
    task_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get the progress of an async compaction task.

    Returns the task status, progress percentage, and result if completed.
    """
    try:
        from app.tasks.compaction_tasks import get_compaction_task_status

        status = get_compaction_task_status(task_id)

        return {
            "success": True,
            **status
        }

    except Exception as e:
        logger.error(
            "get_task_progress_failed",
            task_id=task_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Cancel a pending compaction task.

    Only works for tasks that haven't started executing yet.
    """
    try:
        from app.tasks.compaction_tasks import cancel_compaction_task

        success = cancel_compaction_task(task_id)

        return {
            "success": success,
            "task_id": task_id,
            "message": "Task cancelled" if success else "Failed to cancel task"
        }

    except Exception as e:
        logger.error(
            "cancel_task_failed",
            task_id=task_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/compact/history", response_model=CompactionHistoryResponse)
async def get_compaction_history(
    conversation_id: str,
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum records to return"),
    user_id: str = Depends(get_current_user)
):
    """
    Get the compaction history for a conversation (Task 209).

    Returns a paginated list of compaction operations that have been
    performed on this conversation, including:
    - Token counts before and after compaction
    - Reduction percentages
    - Trigger types (auto, manual, force)
    - Duration and model used

    Use this to audit compaction behavior and track context efficiency.
    """
    try:
        from app.core.database import get_supabase

        supabase = get_supabase()

        # Query compaction_logs table with pagination
        # Filter by both context_id and user_id for security
        # First get total count
        count_result = supabase.table("compaction_logs") \
            .select("id", count="exact") \
            .eq("context_id", conversation_id) \
            .eq("user_id", user_id) \
            .execute()

        total_count = count_result.count if count_result.count else 0

        # Get paginated history records (scoped to user)
        history_result = supabase.table("compaction_logs") \
            .select("*") \
            .eq("context_id", conversation_id) \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .range(skip, skip + limit - 1) \
            .execute()

        history_items = []
        for row in history_result.data or []:
            history_items.append(CompactionHistoryItem(
                id=str(row.get("id")),
                context_id=row.get("context_id"),
                pre_tokens=row.get("pre_tokens", 0),
                post_tokens=row.get("post_tokens", 0),
                reduction_percent=row.get("reduction_percent", 0.0),
                summary_preview=row.get("summary_preview"),
                messages_condensed=row.get("messages_condensed", 0),
                model_used=row.get("model_used", "unknown"),
                duration_ms=row.get("duration_ms", 0),
                triggered_by=row.get("triggered_by", "unknown"),
                created_at=row.get("created_at")
            ))

        has_more = (skip + len(history_items)) < total_count

        logger.info(
            "compaction_history_retrieved",
            conversation_id=conversation_id,
            total_count=total_count,
            returned_count=len(history_items)
        )

        return CompactionHistoryResponse(
            success=True,
            conversation_id=conversation_id,
            history=history_items,
            total_count=total_count,
            has_more=has_more,
            skip=skip,
            limit=limit
        )

    except Exception as e:
        logger.error(
            "get_compaction_history_failed",
            conversation_id=conversation_id,
            error=str(e)
        )
        return CompactionHistoryResponse(
            success=False,
            conversation_id=conversation_id,
            error=str(e),
            skip=skip,
            limit=limit
        )


# =============================================================================
# Error Recovery Endpoints (Task 210)
# =============================================================================

class RecoveryResponse(BaseModel):
    """Response for recovery operations."""
    success: bool
    message: str
    pre_tokens: Optional[int] = None
    post_tokens: Optional[int] = None
    reduction_percent: Optional[float] = None
    attempts: Optional[int] = None
    error: Optional[str] = None


class RecoveryProgressResponse(BaseModel):
    """Response for recovery progress."""
    in_progress: bool
    percent: int = 0
    stage: str = "Idle"


@router.post("/{conversation_id}/recover", response_model=RecoveryResponse)
async def trigger_recovery(
    conversation_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Trigger manual context recovery for a conversation (Task 210).

    This endpoint allows manual triggering of context recovery when
    the context window is approaching its limit or after an overflow error.

    The recovery process:
    1. Creates a checkpoint for potential rollback
    2. Performs aggressive context reduction
    3. Removes non-essential messages if needed
    4. Returns updated context status

    Use this endpoint after receiving a context overflow error or proactively
    when the context window is nearing its limit.
    """
    try:
        from app.services.context_error_recovery_service import get_error_recovery_service

        recovery_service = get_error_recovery_service()

        # Trigger recovery
        success, message, result = await recovery_service.recover_from_overflow(
            conversation_id=conversation_id,
            user_id=user_id
        )

        if success and result:
            # Broadcast updated status
            service = get_context_manager()
            status_result = await service.get_context_status(conversation_id, user_id)
            if status_result.success:
                await ws_manager.broadcast_status(conversation_id, status_result.status)

            return RecoveryResponse(
                success=True,
                message=message,
                pre_tokens=result.pre_tokens,
                post_tokens=result.post_tokens,
                reduction_percent=result.reduction_percent,
                attempts=1  # Will be enhanced when we track attempts
            )

        return RecoveryResponse(
            success=False,
            message=message,
            error=message if not success else None
        )

    except Exception as e:
        logger.error(
            "trigger_recovery_failed",
            conversation_id=conversation_id,
            error=str(e)
        )
        return RecoveryResponse(
            success=False,
            message="Recovery failed",
            error=str(e)
        )


@router.get("/{conversation_id}/recover/progress", response_model=RecoveryProgressResponse)
async def get_recovery_progress(
    conversation_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get the current recovery progress for a conversation (Task 210).

    Returns the progress of an ongoing recovery operation including:
    - Whether recovery is in progress
    - Progress percentage (0-100)
    - Current stage description
    """
    try:
        from app.services.context_error_recovery_service import get_error_recovery_service

        recovery_service = get_error_recovery_service()
        progress = await recovery_service.get_recovery_progress(conversation_id)

        return RecoveryProgressResponse(
            in_progress=progress.get("in_progress", False),
            percent=progress.get("percent", 0),
            stage=progress.get("stage", "Idle")
        )

    except Exception as e:
        logger.error(
            "get_recovery_progress_failed",
            conversation_id=conversation_id,
            error=str(e)
        )
        return RecoveryProgressResponse(
            in_progress=False,
            percent=0,
            stage="Error"
        )


# =============================================================================
# Broadcast Helper (for external use)
# =============================================================================

async def broadcast_context_update(
    conversation_id: str,
    status: ContextWindowStatus
):
    """
    Broadcast context status update to all WebSocket clients.

    This function can be called from other services when the context
    window state changes.
    """
    await ws_manager.broadcast_status(conversation_id, status)


def get_websocket_manager() -> WebSocketConnectionManager:
    """Get the WebSocket connection manager instance."""
    return ws_manager
