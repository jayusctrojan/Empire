"""
Empire v7.3 - Notifications API
WebSocket endpoints for real-time notifications
"""

import uuid
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from typing import Optional
from datetime import datetime

from app.services.websocket_manager import get_connection_manager
from app.models.notifications import (
    NotificationStats,
    WebSocketMessage,
    TaskNotification,
    TaskStatus
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Get WebSocket connection manager
manager = get_connection_manager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time notifications

    Args:
        websocket: WebSocket connection
        session_id: Optional session identifier (for multi-tab support)
        user_id: Optional user identifier (for authenticated users)

    Example:
        ws://localhost:8000/api/v1/notifications/ws?session_id=abc123

    Message Format (Received):
        {
            "type": "task_notification",
            "task_id": "abc-123",
            "status": "completed",
            "message": "File processing complete",
            ...
        }

    Client Actions (Send):
        {
            "action": "subscribe",
            "data": {"task_id": "abc-123"}
        }
    """
    # Generate unique connection ID
    connection_id = str(uuid.uuid4())

    # Accept connection and register
    await manager.connect(
        websocket,
        connection_id,
        session_id=session_id,
        user_id=user_id
    )

    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_json()

            logger.debug(f"Received message from {connection_id}: {data}")

            # Handle different client actions
            action = data.get("action")

            if action == "ping":
                # Respond to ping with pong
                await manager.send_personal_message({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }, connection_id)

            elif action == "subscribe":
                # Client wants to subscribe to specific events
                # (Future: implement topic-based subscriptions)
                await manager.send_personal_message({
                    "type": "info",
                    "message": "Subscription noted",
                    "data": data.get("data", {})
                }, connection_id)

            elif action == "get_stats":
                # Send connection statistics
                stats = manager.get_stats()
                await manager.send_personal_message({
                    "type": "stats",
                    "data": stats
                }, connection_id)

            else:
                # Unknown action
                await manager.send_personal_message({
                    "type": "error",
                    "message": f"Unknown action: {action}"
                }, connection_id)

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {connection_id}")
        manager.disconnect(connection_id, session_id=session_id, user_id=user_id)

    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}")
        manager.disconnect(connection_id, session_id=session_id, user_id=user_id)


@router.get("/stats", response_model=NotificationStats)
async def get_notification_stats():
    """
    Get WebSocket connection statistics

    Returns:
        NotificationStats: Current connection statistics
    """
    stats = manager.get_stats()
    return NotificationStats(**stats)


@router.post("/broadcast")
async def broadcast_notification(
    message: str,
    notification_type: str = "info"
):
    """
    Broadcast a notification to all connected clients

    Args:
        message: Message to broadcast
        notification_type: Type of notification (info, warning, error, success)

    Returns:
        Broadcast confirmation

    Note: This endpoint should be protected in production (admin-only)
    """
    await manager.broadcast({
        "type": notification_type,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    })

    return {
        "status": "success",
        "message": "Notification broadcasted",
        "recipients": manager.get_connection_count()
    }


@router.post("/send/{session_id}")
async def send_to_session(
    session_id: str,
    message: str,
    notification_type: str = "info"
):
    """
    Send a notification to a specific session

    Args:
        session_id: Target session ID
        message: Message to send
        notification_type: Type of notification

    Returns:
        Send confirmation
    """
    await manager.send_to_session({
        "type": notification_type,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }, session_id)

    return {
        "status": "success",
        "message": f"Notification sent to session {session_id}"
    }


@router.post("/send/user/{user_id}")
async def send_to_user(
    user_id: str,
    message: str,
    notification_type: str = "info"
):
    """
    Send a notification to all connections for a user

    Args:
        user_id: Target user ID
        message: Message to send
        notification_type: Type of notification

    Returns:
        Send confirmation
    """
    await manager.send_to_user({
        "type": notification_type,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }, user_id)

    return {
        "status": "success",
        "message": f"Notification sent to user {user_id}"
    }


@router.post("/task-notification")
async def send_task_notification(
    notification: TaskNotification,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None
):
    """
    Send a task-related notification

    Args:
        notification: Task notification details
        session_id: Optional session to notify
        user_id: Optional user to notify

    Returns:
        Send confirmation

    Example:
        POST /api/v1/notifications/task-notification
        {
            "task_id": "abc-123",
            "task_type": "document_processing",
            "status": "completed",
            "message": "Document processing complete",
            "file_id": "xyz-789",
            "filename": "contract.pdf"
        }
    """
    await manager.send_task_notification(
        task_id=notification.task_id,
        task_type=notification.task_type,
        status=notification.status.value,
        message=notification.message,
        session_id=session_id,
        user_id=user_id,
        metadata={
            "file_id": notification.file_id,
            "filename": notification.filename,
            "error": notification.error
        }
    )

    return {
        "status": "success",
        "message": "Task notification sent"
    }


@router.get("/health")
async def notifications_health():
    """
    Health check for notifications service

    Returns:
        Health status and connection statistics
    """
    stats = manager.get_stats()

    return {
        "status": "healthy",
        "service": "notifications",
        "connections": stats
    }
