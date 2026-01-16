"""
Empire v7.3 - WebSocket Real-Time Status Endpoints - Task 10.2 + Task 152
Provides WebSocket endpoints for real-time document and query status updates.
Enhanced with JWT authentication, token refresh, and heartbeat functionality.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Optional
import structlog
import uuid
import json
from datetime import datetime

from app.services.websocket_manager import get_connection_manager
from app.middleware.auth import get_current_user_optional
from app.middleware.websocket_auth import (
    websocket_auth_middleware,
    WebSocketAuthMiddleware,
    WebSocketConnectionMonitor,
    handle_websocket_message,
    create_token_refresh_message,
    create_timeout_warning_message,
)

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


# ==================== Authenticated WebSocket Endpoints (Task 152) ====================


@router.websocket("/authenticated")
async def websocket_authenticated(
    websocket: WebSocket,
    token: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Authenticated WebSocket endpoint with JWT validation, heartbeat, and token refresh.

    Task 152: WebSocket Authentication with JWT Validation

    Features:
    - JWT token validation during handshake (via query param or subprotocol)
    - Automatic heartbeat monitoring
    - Token refresh notifications before expiration
    - Connection timeout detection
    - Graceful degradation for anonymous users

    Authentication:
    - Pass token via query parameter: /ws/authenticated?token=<jwt>
    - Or via subprotocol header: Bearer.<jwt>

    Client Messages:
    - {"event": "heartbeat"} or {"type": "ping"} - Keep connection alive
    - {"event": "refresh_token", "token": "<new_jwt>"} - Refresh authentication

    Server Messages:
    - {"event": "pong", "timestamp": ...} - Heartbeat response
    - {"event": "token_refresh_needed", "expires_in_seconds": ...} - Token expiring
    - {"event": "timeout_warning", "seconds_remaining": ...} - Connection timeout warning
    - {"event": "authenticated", "user_id": ..., "role": ...} - Authentication success

    Args:
        websocket: WebSocket connection
        token: Optional JWT token (query parameter)
        session_id: Optional session identifier
    """
    connection_id = str(uuid.uuid4())
    manager = get_connection_manager()
    monitor = None

    try:
        # Authenticate the WebSocket connection (Task 152)
        auth_context = await websocket_auth_middleware(
            websocket,
            require_auth=False,  # Allow anonymous, but track authenticated users
            allow_anonymous=True
        )

        if auth_context is None:
            # Authentication failed and connection was closed
            return

        # Accept the connection
        await websocket.accept()

        # Register with connection manager
        await manager.connect(
            websocket=websocket,
            connection_id=connection_id,
            session_id=session_id,
            user_id=auth_context.user_id,
            connection_type="authenticated"
        )

        logger.info(
            "websocket_authenticated_connected",
            connection_id=connection_id,
            user_id=auth_context.user_id,
            role=auth_context.role,
            is_authenticated=auth_context.is_authenticated
        )

        # Send authentication confirmation
        await websocket.send_json({
            "event": "authenticated",
            "user_id": auth_context.user_id,
            "role": auth_context.role,
            "is_authenticated": auth_context.is_authenticated,
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Set up connection monitor with callbacks
        async def on_timeout():
            """Handle connection timeout."""
            try:
                await websocket.send_json({
                    "event": "connection_timeout",
                    "message": "Connection closed due to inactivity"
                })
                await websocket.close(code=1000, reason="Connection timeout")
            except Exception:
                pass

        async def on_token_refresh_needed():
            """Notify client that token refresh is needed."""
            try:
                if auth_context.token_exp:
                    message = create_token_refresh_message(auth_context.token_exp)
                    await websocket.send_json(message)
            except Exception as e:
                logger.warning("token_refresh_notification_failed", error=str(e))

        # Start connection monitor (Task 152)
        monitor = WebSocketConnectionMonitor(
            websocket=websocket,
            auth_context=auth_context,
            heartbeat_interval=30,
            connection_timeout=120,
            on_timeout=on_timeout,
            on_token_refresh_needed=on_token_refresh_needed
        )
        await monitor.start()

        # Main message loop
        while True:
            try:
                data = await websocket.receive_json()

                # Handle built-in messages (heartbeat, token refresh)
                response = await handle_websocket_message(
                    websocket, data, auth_context, monitor
                )

                if response:
                    await websocket.send_json(response)
                    continue

                # Handle custom messages
                event_type = data.get("event") or data.get("type")

                if event_type == "subscribe":
                    # Handle subscription requests
                    resource_type = data.get("resource_type")
                    resource_id = data.get("resource_id")

                    await websocket.send_json({
                        "event": "subscription_info",
                        "message": f"Use /ws/{resource_type}/{{id}} for resource subscriptions",
                        "resource_type": resource_type,
                        "resource_id": resource_id
                    })

                elif event_type == "echo":
                    # Echo back for testing
                    await websocket.send_json({
                        "event": "echo",
                        "data": data.get("data"),
                        "timestamp": datetime.utcnow().isoformat()
                    })

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_json({
                    "event": "error",
                    "message": "Invalid JSON format"
                })

    except Exception as e:
        logger.error(
            "websocket_authenticated_error",
            connection_id=connection_id,
            error=str(e)
        )
    finally:
        # Cleanup
        if monitor:
            await monitor.stop()

        await manager.disconnect(connection_id)
        logger.info(
            "websocket_authenticated_disconnected",
            connection_id=connection_id
        )


@router.websocket("/secure/{resource_type}/{resource_id}")
async def websocket_secure_resource(
    websocket: WebSocket,
    resource_type: str,
    resource_id: str,
    token: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Secure WebSocket endpoint requiring authentication for resource access.

    Task 152: WebSocket Authentication with JWT Validation

    This endpoint REQUIRES authentication. Unauthenticated connections
    will be rejected with a policy violation close code.

    Supports resource types: document, query, source, project

    Args:
        websocket: WebSocket connection
        resource_type: Type of resource (document, query, source, project)
        resource_id: ID of the resource
        token: JWT token (query parameter)
        session_id: Optional session identifier
    """
    connection_id = str(uuid.uuid4())
    manager = get_connection_manager()
    monitor = None

    # Validate resource type
    valid_resource_types = {"document", "query", "source", "project"}
    if resource_type not in valid_resource_types:
        await websocket.close(
            code=4000,
            reason=f"Invalid resource type. Must be one of: {valid_resource_types}"
        )
        return

    try:
        # Authenticate - REQUIRED for secure endpoints
        auth_context = await websocket_auth_middleware(
            websocket,
            require_auth=True,
            allow_anonymous=False
        )

        if auth_context is None:
            # Authentication failed, connection was closed
            return

        # Accept and register connection
        await websocket.accept()

        # Build connection kwargs based on resource type
        connect_kwargs = {
            "websocket": websocket,
            "connection_id": connection_id,
            "session_id": session_id,
            "user_id": auth_context.user_id,
            "connection_type": f"secure_{resource_type}"
        }

        # Add resource-specific subscription
        if resource_type == "document":
            connect_kwargs["document_id"] = resource_id
        elif resource_type == "query":
            connect_kwargs["query_id"] = resource_id
        elif resource_type == "source":
            connect_kwargs["source_id"] = resource_id
        elif resource_type == "project":
            connect_kwargs["project_id"] = resource_id

        await manager.connect(**connect_kwargs)

        logger.info(
            "websocket_secure_connected",
            connection_id=connection_id,
            user_id=auth_context.user_id,
            role=auth_context.role,
            resource_type=resource_type,
            resource_id=resource_id
        )

        # Send subscription confirmation
        await websocket.send_json({
            "event": "subscription_confirmed",
            "resource_type": resource_type,
            "resource_id": resource_id,
            "user_id": auth_context.user_id,
            "role": auth_context.role,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Set up connection monitor
        async def on_timeout():
            try:
                await websocket.send_json({
                    "event": "connection_timeout",
                    "message": "Connection closed due to inactivity"
                })
                await websocket.close(code=1000)
            except Exception:
                pass

        async def on_token_refresh_needed():
            try:
                if auth_context.token_exp:
                    await websocket.send_json(
                        create_token_refresh_message(auth_context.token_exp)
                    )
            except Exception:
                pass

        monitor = WebSocketConnectionMonitor(
            websocket=websocket,
            auth_context=auth_context,
            heartbeat_interval=30,
            connection_timeout=120,
            on_timeout=on_timeout,
            on_token_refresh_needed=on_token_refresh_needed
        )
        await monitor.start()

        # Message loop
        while True:
            try:
                data = await websocket.receive_json()

                # Handle built-in messages
                response = await handle_websocket_message(
                    websocket, data, auth_context, monitor
                )

                if response:
                    await websocket.send_json(response)

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_json({
                    "event": "error",
                    "message": "Invalid JSON format"
                })

    except Exception as e:
        logger.error(
            "websocket_secure_error",
            connection_id=connection_id,
            resource_type=resource_type,
            resource_id=resource_id,
            error=str(e)
        )
    finally:
        if monitor:
            await monitor.stop()
        await manager.disconnect(connection_id)
        logger.info(
            "websocket_secure_disconnected",
            connection_id=connection_id,
            resource_type=resource_type,
            resource_id=resource_id
        )
