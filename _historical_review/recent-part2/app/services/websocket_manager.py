"""
Empire v7.3 - WebSocket Connection Manager
Manages WebSocket connections and broadcasts real-time notifications
"""

import json
import logging
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    WebSocket connection manager for real-time notifications

    Features:
    - Connection pool management
    - Broadcast to all connections
    - Targeted notifications by user/session
    - Connection lifecycle management
    - Automatic cleanup on disconnect
    """

    def __init__(self):
        # Active WebSocket connections
        self.active_connections: Dict[str, WebSocket] = {}

        # Session to connection mapping
        self.session_connections: Dict[str, Set[str]] = {}

        # User to connection mapping (for authenticated users)
        self.user_connections: Dict[str, Set[str]] = {}

        logger.info("WebSocket ConnectionManager initialized")

    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        Accept and register a new WebSocket connection

        Args:
            websocket: WebSocket connection
            connection_id: Unique connection identifier
            session_id: Optional session identifier
            user_id: Optional user identifier (for authenticated users)
        """
        await websocket.accept()

        # Register connection
        self.active_connections[connection_id] = websocket

        # Register session mapping
        if session_id:
            if session_id not in self.session_connections:
                self.session_connections[session_id] = set()
            self.session_connections[session_id].add(connection_id)

        # Register user mapping (authenticated)
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)

        logger.info(f"WebSocket connected: {connection_id} (session: {session_id}, user: {user_id})")
        logger.info(f"Total active connections: {len(self.active_connections)}")

        # Send connection confirmation
        await self.send_personal_message({
            "type": "connection",
            "status": "connected",
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat()
        }, connection_id)

    def disconnect(
        self,
        connection_id: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        Remove and cleanup a WebSocket connection

        Args:
            connection_id: Connection identifier to remove
            session_id: Optional session identifier
            user_id: Optional user identifier
        """
        # Remove from active connections
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        # Cleanup session mapping
        if session_id and session_id in self.session_connections:
            self.session_connections[session_id].discard(connection_id)
            if not self.session_connections[session_id]:
                del self.session_connections[session_id]

        # Cleanup user mapping
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        logger.info(f"WebSocket disconnected: {connection_id}")
        logger.info(f"Total active connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, connection_id: str):
        """
        Send a message to a specific connection

        Args:
            message: Message dictionary to send
            connection_id: Target connection ID
        """
        if connection_id in self.active_connections:
            try:
                websocket = self.active_connections[connection_id]
                await websocket.send_json(message)
                logger.debug(f"Sent message to connection {connection_id}: {message.get('type')}")
            except Exception as e:
                logger.error(f"Error sending message to {connection_id}: {e}")
                # Connection likely closed, clean up
                self.disconnect(connection_id)
        else:
            logger.warning(f"Connection {connection_id} not found")

    async def send_to_session(self, message: dict, session_id: str):
        """
        Send a message to all connections in a session

        Args:
            message: Message dictionary to send
            session_id: Target session ID
        """
        if session_id in self.session_connections:
            connection_ids = self.session_connections[session_id].copy()
            for connection_id in connection_ids:
                await self.send_personal_message(message, connection_id)
            logger.info(f"Sent message to {len(connection_ids)} connections in session {session_id}")
        else:
            logger.warning(f"Session {session_id} not found")

    async def send_to_user(self, message: dict, user_id: str):
        """
        Send a message to all connections for a user

        Args:
            message: Message dictionary to send
            user_id: Target user ID
        """
        if user_id in self.user_connections:
            connection_ids = self.user_connections[user_id].copy()
            for connection_id in connection_ids:
                await self.send_personal_message(message, connection_id)
            logger.info(f"Sent message to {len(connection_ids)} connections for user {user_id}")
        else:
            logger.warning(f"User {user_id} not found")

    async def broadcast(self, message: dict, exclude: Optional[Set[str]] = None):
        """
        Broadcast a message to all active connections

        Args:
            message: Message dictionary to broadcast
            exclude: Optional set of connection IDs to exclude
        """
        exclude = exclude or set()
        disconnected = []

        for connection_id, websocket in self.active_connections.items():
            if connection_id not in exclude:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {connection_id}: {e}")
                    disconnected.append(connection_id)

        # Cleanup disconnected connections
        for connection_id in disconnected:
            self.disconnect(connection_id)

        recipients = len(self.active_connections) - len(exclude) - len(disconnected)
        logger.info(f"Broadcasted message to {recipients} connections")

    async def send_task_notification(
        self,
        task_id: str,
        task_type: str,
        status: str,
        message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        """
        Send a task-related notification

        Args:
            task_id: Celery task ID
            task_type: Type of task (upload, processing, embedding, etc.)
            status: Task status (pending, processing, completed, failed)
            message: Human-readable message
            session_id: Optional session to notify
            user_id: Optional user to notify
            metadata: Optional additional metadata
        """
        notification = {
            "type": "task_notification",
            "task_id": task_id,
            "task_type": task_type,
            "status": status,
            "message": message,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }

        if session_id:
            await self.send_to_session(notification, session_id)
        elif user_id:
            await self.send_to_user(notification, user_id)
        else:
            # If no specific target, broadcast to all
            await self.broadcast(notification)

    async def send_progress_update(
        self,
        task_id: str,
        progress: int,
        total: int,
        message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        Send a progress update notification

        Args:
            task_id: Celery task ID
            progress: Current progress value
            total: Total value (for percentage calculation)
            message: Progress message
            session_id: Optional session to notify
            user_id: Optional user to notify
        """
        percentage = (progress / total * 100) if total > 0 else 0

        notification = {
            "type": "progress_update",
            "task_id": task_id,
            "progress": progress,
            "total": total,
            "percentage": round(percentage, 2),
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }

        if session_id:
            await self.send_to_session(notification, session_id)
        elif user_id:
            await self.send_to_user(notification, user_id)
        else:
            await self.broadcast(notification)

    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return len(self.active_connections)

    def get_session_count(self) -> int:
        """Get total number of active sessions"""
        return len(self.session_connections)

    def get_user_count(self) -> int:
        """Get total number of connected users"""
        return len(self.user_connections)

    def get_stats(self) -> dict:
        """Get connection statistics"""
        return {
            "active_connections": self.get_connection_count(),
            "active_sessions": self.get_session_count(),
            "connected_users": self.get_user_count(),
            "timestamp": datetime.utcnow().isoformat()
        }


# Global singleton instance
_connection_manager = None


def get_connection_manager() -> ConnectionManager:
    """
    Get singleton instance of ConnectionManager

    Returns:
        ConnectionManager instance
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
