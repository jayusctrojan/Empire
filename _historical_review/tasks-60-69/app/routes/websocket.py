"""
Empire v7.3 - WebSocket Real-Time Status Endpoints - Task 10.2
Provides WebSocket endpoints for real-time document and query status updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Optional
import structlog
import uuid
from datetime import datetime

from app.services.websocket_manager import get_connection_manager
from app.middleware.auth import get_current_user_optional

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None
):
    """
    WebSocket endpoint for general real-time notifications

    Clients can connect to receive:
    - Task status updates
    - System notifications
    - Broadcast messages

    Args:
        websocket: WebSocket connection
        session_id: Optional session identifier
        user_id: Optional authenticated user identifier
    """
    connection_id = str(uuid.uuid4())
    manager = get_connection_manager()

    try:
        # Connect WebSocket
        await manager.connect(
            websocket=websocket,
            connection_id=connection_id,
            session_id=session_id,
            user_id=user_id,
            connection_type="general"
        )

        logger.info(
            "websocket_notifications_connected",
            connection_id=connection_id,
            session_id=session_id,
            user_id=user_id
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive messages from client (ping/pong, client requests, etc.)
                data = await websocket.receive_json()

                # Handle client ping
                if data.get("type") == "ping":
                    await manager.send_personal_message(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                        connection_id
                    )

                # Handle subscription requests
                elif data.get("type") == "subscribe":
                    resource_type = data.get("resource_type")
                    resource_id = data.get("resource_id")

                    logger.info(
                        "subscription_request",
                        connection_id=connection_id,
                        resource_type=resource_type,
                        resource_id=resource_id
                    )

                    # Note: Subscriptions are handled through dedicated endpoints
                    await manager.send_personal_message(
                        {
                            "type": "subscription_info",
                            "message": "Use /ws/document/{id} or /ws/query/{id} for resource subscriptions"
                        },
                        connection_id
                    )

            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(
            "websocket_notifications_error",
            connection_id=connection_id,
            error=str(e)
        )
    finally:
        # Cleanup connection
        await manager.disconnect(connection_id)
        logger.info(
            "websocket_notifications_disconnected",
            connection_id=connection_id
        )


@router.websocket("/document/{document_id}")
async def websocket_document_status(
    websocket: WebSocket,
    document_id: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None
):
    """
    WebSocket endpoint for document processing status updates

    Clients can connect to receive real-time updates for a specific document:
    - Upload progress
    - Processing stages (parsing, embedding, indexing)
    - Completion status
    - Error notifications

    Args:
        websocket: WebSocket connection
        document_id: Document identifier to subscribe to
        session_id: Optional session identifier
        user_id: Optional authenticated user identifier
    """
    connection_id = str(uuid.uuid4())
    manager = get_connection_manager()

    try:
        # Connect WebSocket with document subscription
        await manager.connect(
            websocket=websocket,
            connection_id=connection_id,
            session_id=session_id,
            user_id=user_id,
            document_id=document_id,
            connection_type="document"
        )

        logger.info(
            "websocket_document_connected",
            connection_id=connection_id,
            document_id=document_id,
            session_id=session_id,
            user_id=user_id
        )

        # Send connection confirmation with subscription details
        await manager.send_personal_message(
            {
                "type": "subscription_confirmed",
                "resource_type": "document",
                "resource_id": document_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            connection_id
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_json()

                # Handle client ping
                if data.get("type") == "ping":
                    await manager.send_personal_message(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                        connection_id
                    )

            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(
            "websocket_document_error",
            connection_id=connection_id,
            document_id=document_id,
            error=str(e)
        )
    finally:
        # Cleanup connection
        await manager.disconnect(connection_id)
        logger.info(
            "websocket_document_disconnected",
            connection_id=connection_id,
            document_id=document_id
        )


@router.websocket("/query/{query_id}")
async def websocket_query_status(
    websocket: WebSocket,
    query_id: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None
):
    """
    WebSocket endpoint for query processing status updates

    Clients can connect to receive real-time updates for a specific query:
    - Query processing stages
    - LangGraph workflow progress
    - CrewAI agent status
    - Search results streaming
    - Completion status

    Args:
        websocket: WebSocket connection
        query_id: Query identifier to subscribe to
        session_id: Optional session identifier
        user_id: Optional authenticated user identifier
    """
    connection_id = str(uuid.uuid4())
    manager = get_connection_manager()

    try:
        # Connect WebSocket with query subscription
        await manager.connect(
            websocket=websocket,
            connection_id=connection_id,
            session_id=session_id,
            user_id=user_id,
            query_id=query_id,
            connection_type="query"
        )

        logger.info(
            "websocket_query_connected",
            connection_id=connection_id,
            query_id=query_id,
            session_id=session_id,
            user_id=user_id
        )

        # Send connection confirmation with subscription details
        await manager.send_personal_message(
            {
                "type": "subscription_confirmed",
                "resource_type": "query",
                "resource_id": query_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            connection_id
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_json()

                # Handle client ping
                if data.get("type") == "ping":
                    await manager.send_personal_message(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                        connection_id
                    )

            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(
            "websocket_query_error",
            connection_id=connection_id,
            query_id=query_id,
            error=str(e)
        )
    finally:
        # Cleanup connection
        await manager.disconnect(connection_id)
        logger.info(
            "websocket_query_disconnected",
            connection_id=connection_id,
            query_id=query_id
        )


@router.websocket("/source/{source_id}")
async def websocket_source_status(
    websocket: WebSocket,
    source_id: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None
):
    """
    WebSocket endpoint for individual source processing status updates - Task 62

    Clients can connect to receive real-time updates for a specific source:
    - Processing progress (0-100%)
    - Processing stages (pending, processing, ready, failed)
    - Error notifications with retry options
    - Estimated time remaining

    Args:
        websocket: WebSocket connection
        source_id: Source identifier to subscribe to
        session_id: Optional session identifier
        user_id: Optional authenticated user identifier
    """
    connection_id = str(uuid.uuid4())
    manager = get_connection_manager()

    try:
        # Connect WebSocket with source subscription
        await manager.connect(
            websocket=websocket,
            connection_id=connection_id,
            session_id=session_id,
            user_id=user_id,
            source_id=source_id,
            connection_type="source"
        )

        logger.info(
            "websocket_source_connected",
            connection_id=connection_id,
            source_id=source_id,
            session_id=session_id,
            user_id=user_id
        )

        # Send connection confirmation with subscription details
        await manager.send_personal_message(
            {
                "type": "subscription_confirmed",
                "resource_type": "source",
                "resource_id": source_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            connection_id
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_json()

                # Handle client ping
                if data.get("type") == "ping":
                    await manager.send_personal_message(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                        connection_id
                    )

            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(
            "websocket_source_error",
            connection_id=connection_id,
            source_id=source_id,
            error=str(e)
        )
    finally:
        # Cleanup connection
        await manager.disconnect(connection_id)
        logger.info(
            "websocket_source_disconnected",
            connection_id=connection_id,
            source_id=source_id
        )


@router.websocket("/project/{project_id}/sources")
async def websocket_project_sources_status(
    websocket: WebSocket,
    project_id: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None
):
    """
    WebSocket endpoint for all sources in a project - Task 62

    Clients can connect to receive real-time updates for all sources in a project:
    - New source added notifications
    - Source processing status changes
    - Source deletion notifications
    - Batch processing progress

    Visual indicators sent:
    - green ● ready
    - blue ◐ processing+%
    - gray ○ pending
    - red ✕ failed+retry

    Args:
        websocket: WebSocket connection
        project_id: Project identifier to subscribe to
        session_id: Optional session identifier
        user_id: Optional authenticated user identifier
    """
    connection_id = str(uuid.uuid4())
    manager = get_connection_manager()

    try:
        # Connect WebSocket with project sources subscription
        await manager.connect(
            websocket=websocket,
            connection_id=connection_id,
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            connection_type="project_sources"
        )

        logger.info(
            "websocket_project_sources_connected",
            connection_id=connection_id,
            project_id=project_id,
            session_id=session_id,
            user_id=user_id
        )

        # Send connection confirmation with subscription details
        await manager.send_personal_message(
            {
                "type": "subscription_confirmed",
                "resource_type": "project_sources",
                "resource_id": project_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            connection_id
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_json()

                # Handle client ping
                if data.get("type") == "ping":
                    await manager.send_personal_message(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                        connection_id
                    )

                # Handle refresh request (full sources sync on reconnect)
                elif data.get("type") == "refresh":
                    await manager.send_personal_message(
                        {
                            "type": "refresh_ack",
                            "message": "Use GET /api/projects/{project_id}/sources for full refresh",
                            "timestamp": datetime.utcnow().isoformat()
                        },
                        connection_id
                    )

            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(
            "websocket_project_sources_error",
            connection_id=connection_id,
            project_id=project_id,
            error=str(e)
        )
    finally:
        # Cleanup connection
        await manager.disconnect(connection_id)
        logger.info(
            "websocket_project_sources_disconnected",
            connection_id=connection_id,
            project_id=project_id
        )


@router.get("/stats")
async def websocket_stats():
    """
    Get WebSocket connection statistics

    Returns:
        Statistics including active connections, sessions, and users
    """
    manager = get_connection_manager()
    return manager.get_stats()
