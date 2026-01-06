"""
Empire v7.3 - WebSocket Connection Manager - Task 10.1
Manages WebSocket connections and broadcasts real-time notifications
Enhanced with resource subscriptions, Prometheus metrics, and Redis pub/sub
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
from prometheus_client import Counter, Gauge, Histogram
import structlog

# Use structured logging
logger = structlog.get_logger(__name__)

# Redis Pub/Sub integration - Task 10.3
REDIS_ENABLED = None  # Will be set dynamically

# Prometheus metrics for WebSocket monitoring (Task 10)
WS_CONNECTIONS_TOTAL = Counter(
    'empire_websocket_connections_total',
    'Total WebSocket connections established',
    ['connection_type']
)

WS_ACTIVE_CONNECTIONS = Gauge(
    'empire_websocket_active_connections',
    'Current number of active WebSocket connections',
    ['connection_type']
)

WS_MESSAGES_SENT = Counter(
    'empire_websocket_messages_sent_total',
    'Total WebSocket messages sent',
    ['message_type']
)

WS_MESSAGES_FAILED = Counter(
    'empire_websocket_messages_failed_total',
    'Failed WebSocket message sends',
    ['error_type']
)

WS_MESSAGE_LATENCY = Histogram(
    'empire_websocket_message_latency_seconds',
    'WebSocket message send latency',
    ['message_type'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)


class ConnectionManager:
    """
    WebSocket connection manager for real-time notifications

    Features:
    - Connection pool management
    - Broadcast to all connections
    - Targeted notifications by user/session
    - Resource-based subscriptions (documents, queries) - Task 10
    - Connection lifecycle management
    - Automatic cleanup on disconnect
    - Prometheus metrics integration - Task 10
    - Thread-safe async operations - Task 10
    """

    def __init__(self):
        # Active WebSocket connections
        self.active_connections: Dict[str, WebSocket] = {}

        # Session to connection mapping
        self.session_connections: Dict[str, Set[str]] = {}

        # User to connection mapping (for authenticated users)
        self.user_connections: Dict[str, Set[str]] = {}

        # Resource-based subscriptions - Task 10.1
        # {resource_id: Set[connection_id]}
        self.document_connections: Dict[str, Set[str]] = {}
        self.query_connections: Dict[str, Set[str]] = {}

        # Task 62: Project source subscriptions
        # {source_id: Set[connection_id]}
        self.source_connections: Dict[str, Set[str]] = {}
        # {project_id: Set[connection_id]} - for all sources in a project
        self.project_source_connections: Dict[str, Set[str]] = {}

        # Connection metadata tracking
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}

        # Thread-safe async lock - Task 10.1
        self.lock = asyncio.Lock()

        # Redis Pub/Sub for distributed broadcasting - Task 10.3
        self.redis_pubsub = None
        self.redis_enabled = False
        self._redis_initialized = False

        logger.info("websocket_manager_initialized", features=[
            "session_mapping",
            "user_mapping",
            "resource_subscriptions",
            "metrics",
            "thread_safe",
            "redis_pubsub_ready"
        ])

    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
        query_id: Optional[str] = None,
        source_id: Optional[str] = None,
        project_id: Optional[str] = None,
        connection_type: str = "general"
    ):
        """
        Accept and register a new WebSocket connection

        Args:
            websocket: WebSocket connection
            connection_id: Unique connection identifier
            session_id: Optional session identifier
            user_id: Optional user identifier (for authenticated users)
            document_id: Optional document ID to subscribe to - Task 10.1
            query_id: Optional query ID to subscribe to - Task 10.1
            source_id: Optional source ID to subscribe to - Task 62
            project_id: Optional project ID to subscribe to all sources - Task 62
            connection_type: Connection type for metrics (general, document, query, source)
        """
        try:
            await websocket.accept()

            async with self.lock:
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

                # Register resource subscriptions - Task 10.1
                if document_id:
                    if document_id not in self.document_connections:
                        self.document_connections[document_id] = set()
                    self.document_connections[document_id].add(connection_id)

                if query_id:
                    if query_id not in self.query_connections:
                        self.query_connections[query_id] = set()
                    self.query_connections[query_id].add(connection_id)

                # Register source subscriptions - Task 62
                if source_id:
                    if source_id not in self.source_connections:
                        self.source_connections[source_id] = set()
                    self.source_connections[source_id].add(connection_id)

                if project_id:
                    if project_id not in self.project_source_connections:
                        self.project_source_connections[project_id] = set()
                    self.project_source_connections[project_id].add(connection_id)

                # Store connection metadata
                self.connection_metadata[connection_id] = {
                    "session_id": session_id,
                    "user_id": user_id,
                    "document_id": document_id,
                    "query_id": query_id,
                    "source_id": source_id,
                    "project_id": project_id,
                    "connection_type": connection_type,
                    "connected_at": datetime.utcnow().isoformat()
                }

            # Update Prometheus metrics - Task 10.1
            WS_CONNECTIONS_TOTAL.labels(connection_type=connection_type).inc()
            WS_ACTIVE_CONNECTIONS.labels(connection_type=connection_type).inc()

            logger.info(
                "websocket_connected",
                connection_id=connection_id,
                session_id=session_id,
                user_id=user_id,
                document_id=document_id,
                query_id=query_id,
                source_id=source_id,
                project_id=project_id,
                connection_type=connection_type,
                total_connections=len(self.active_connections)
            )

            # Send connection confirmation
            await self.send_personal_message({
                "type": "connection",
                "status": "connected",
                "connection_id": connection_id,
                "timestamp": datetime.utcnow().isoformat()
            }, connection_id)

        except Exception as e:
            logger.error(
                "websocket_connect_failed",
                connection_id=connection_id,
                error=str(e)
            )
            WS_MESSAGES_FAILED.labels(error_type="connect_error").inc()
            raise

    async def disconnect(
        self,
        connection_id: str
    ):
        """
        Remove and cleanup a WebSocket connection

        Args:
            connection_id: Connection identifier to remove
        """
        async with self.lock:
            # Get metadata before cleanup
            metadata = self.connection_metadata.get(connection_id, {})
            session_id = metadata.get("session_id")
            user_id = metadata.get("user_id")
            document_id = metadata.get("document_id")
            query_id = metadata.get("query_id")
            source_id = metadata.get("source_id")
            project_id = metadata.get("project_id")
            connection_type = metadata.get("connection_type", "general")

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

            # Cleanup resource subscriptions - Task 10.1
            if document_id and document_id in self.document_connections:
                self.document_connections[document_id].discard(connection_id)
                if not self.document_connections[document_id]:
                    del self.document_connections[document_id]

            if query_id and query_id in self.query_connections:
                self.query_connections[query_id].discard(connection_id)
                if not self.query_connections[query_id]:
                    del self.query_connections[query_id]

            # Cleanup source subscriptions - Task 62
            if source_id and source_id in self.source_connections:
                self.source_connections[source_id].discard(connection_id)
                if not self.source_connections[source_id]:
                    del self.source_connections[source_id]

            if project_id and project_id in self.project_source_connections:
                self.project_source_connections[project_id].discard(connection_id)
                if not self.project_source_connections[project_id]:
                    del self.project_source_connections[project_id]

            # Cleanup metadata
            if connection_id in self.connection_metadata:
                del self.connection_metadata[connection_id]

        # Update metrics - Task 10.1
        WS_ACTIVE_CONNECTIONS.labels(connection_type=connection_type).dec()

        logger.info(
            "websocket_disconnected",
            connection_id=connection_id,
            connection_type=connection_type,
            total_connections=len(self.active_connections)
        )

    async def send_personal_message(self, message: dict, connection_id: str):
        """
        Send a message to a specific connection with metrics tracking - Task 10.1

        Args:
            message: Message dictionary to send
            connection_id: Target connection ID
        """
        if connection_id not in self.active_connections:
            logger.warning(
                "connection_not_found",
                connection_id=connection_id,
                message_type=message.get("type")
            )
            WS_MESSAGES_FAILED.labels(error_type="connection_not_found").inc()
            return

        # Track latency - Task 10.1
        import time
        start_time = time.time()

        try:
            websocket = self.active_connections[connection_id]
            await websocket.send_json(message)

            # Record successful send with metrics
            latency = time.time() - start_time
            message_type = message.get("type", "unknown")

            WS_MESSAGE_LATENCY.labels(message_type=message_type).observe(latency)
            WS_MESSAGES_SENT.labels(message_type=message_type).inc()

            logger.debug(
                "message_sent",
                connection_id=connection_id,
                message_type=message_type,
                latency_ms=round(latency * 1000, 2)
            )

        except WebSocketDisconnect:
            logger.info(
                "websocket_disconnected_during_send",
                connection_id=connection_id
            )
            await self.disconnect(connection_id)
            WS_MESSAGES_FAILED.labels(error_type="disconnect").inc()

        except Exception as e:
            logger.error(
                "message_send_failed",
                connection_id=connection_id,
                error=str(e),
                message_type=message.get("type")
            )
            await self.disconnect(connection_id)
            WS_MESSAGES_FAILED.labels(error_type="send_error").inc()

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

    async def broadcast(self, message: dict, exclude: Optional[Set[str]] = None, publish_to_redis: bool = True):
        """
        Broadcast a message to all active connections - Task 10.3 Enhanced

        Args:
            message: Message dictionary to broadcast
            exclude: Optional set of connection IDs to exclude
            publish_to_redis: Whether to publish to Redis for distributed broadcasting
        """
        exclude = exclude or set()
        disconnected = []

        # Publish to Redis first for distributed broadcasting - Task 10.3
        if publish_to_redis and self.redis_enabled:
            message_with_metadata = {
                **message,
                "target_type": "broadcast"
            }
            await self.publish_to_redis(
                channel="empire:websocket:broadcast",
                message=message_with_metadata,
                channel_type="general"
            )

        # Send to local connections
        for connection_id, websocket in self.active_connections.items():
            if connection_id not in exclude:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {connection_id}: {e}")
                    disconnected.append(connection_id)

        # Cleanup disconnected connections
        for connection_id in disconnected:
            await self.disconnect(connection_id)

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

    async def send_to_document(self, message: dict, document_id: str):
        """
        Send a message to all connections subscribed to a document - Task 10.1

        Args:
            message: Message dictionary to send
            document_id: Target document ID
        """
        if document_id not in self.document_connections:
            logger.debug(
                "no_document_subscribers",
                document_id=document_id,
                message_type=message.get("type")
            )
            return

        connection_ids = self.document_connections[document_id].copy()
        for connection_id in connection_ids:
            await self.send_personal_message(message, connection_id)

        logger.info(
            "message_sent_to_document_subscribers",
            document_id=document_id,
            connection_count=len(connection_ids),
            message_type=message.get("type")
        )

    async def send_to_query(self, message: dict, query_id: str):
        """
        Send a message to all connections subscribed to a query - Task 10.1

        Args:
            message: Message dictionary to send
            query_id: Target query ID
        """
        if query_id not in self.query_connections:
            logger.debug(
                "no_query_subscribers",
                query_id=query_id,
                message_type=message.get("type")
            )
            return

        connection_ids = self.query_connections[query_id].copy()
        for connection_id in connection_ids:
            await self.send_personal_message(message, connection_id)

        logger.info(
            "message_sent_to_query_subscribers",
            query_id=query_id,
            connection_count=len(connection_ids),
            message_type=message.get("type")
        )

    async def send_to_source(self, message: dict, source_id: str):
        """
        Send a message to all connections subscribed to a source - Task 62

        Args:
            message: Message dictionary to send
            source_id: Target source ID
        """
        if source_id not in self.source_connections:
            logger.debug(
                "no_source_subscribers",
                source_id=source_id,
                message_type=message.get("type")
            )
            return

        connection_ids = self.source_connections[source_id].copy()
        for connection_id in connection_ids:
            await self.send_personal_message(message, connection_id)

        logger.info(
            "message_sent_to_source_subscribers",
            source_id=source_id,
            connection_count=len(connection_ids),
            message_type=message.get("type")
        )

    async def send_to_project_sources(self, message: dict, project_id: str):
        """
        Send a message to all connections subscribed to a project's sources - Task 62

        Args:
            message: Message dictionary to send
            project_id: Target project ID
        """
        if project_id not in self.project_source_connections:
            logger.debug(
                "no_project_source_subscribers",
                project_id=project_id,
                message_type=message.get("type")
            )
            return

        connection_ids = self.project_source_connections[project_id].copy()
        for connection_id in connection_ids:
            await self.send_personal_message(message, connection_id)

        logger.info(
            "message_sent_to_project_source_subscribers",
            project_id=project_id,
            connection_count=len(connection_ids),
            message_type=message.get("type")
        )

    async def send_source_status(
        self,
        source_id: str,
        project_id: str,
        status: str,
        progress: int,
        message: str,
        metadata: Optional[dict] = None
    ):
        """
        Send a source status update to all relevant subscribers - Task 62

        Sends to:
        - Subscribers of the specific source
        - Subscribers of the project's sources
        - The user who owns the source

        Args:
            source_id: Source ID
            project_id: Project ID
            status: Source status (pending, processing, ready, failed)
            progress: Progress percentage (0-100)
            message: Human-readable status message
            metadata: Optional additional metadata
        """
        notification = {
            "type": "source_status",
            "source_id": source_id,
            "project_id": project_id,
            "status": status,
            "progress": progress,
            "message": message,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }

        # Send to source subscribers
        await self.send_to_source(notification, source_id)

        # Send to project source subscribers
        await self.send_to_project_sources(notification, project_id)

    async def initialize_redis_pubsub(self):
        """
        Initialize Redis Pub/Sub for distributed WebSocket broadcasting - Task 10.3

        Enables message broadcasting across multiple server instances
        """
        if self._redis_initialized:
            logger.debug("redis_pubsub_already_initialized")
            return

        try:
            # Import Redis pub/sub service
            from app.services.redis_pubsub_service import get_redis_pubsub_service

            self.redis_pubsub = await get_redis_pubsub_service()
            self.redis_enabled = True

            # Subscribe to broadcast channel
            await self.redis_pubsub.subscribe_channel(
                "empire:websocket:broadcast",
                self._handle_redis_broadcast
            )

            # Start listening for messages
            await self.redis_pubsub.start_listener()

            self._redis_initialized = True

            logger.info(
                "redis_pubsub_initialized",
                channels=["empire:websocket:broadcast"]
            )

        except ImportError:
            logger.warning(
                "redis_pubsub_not_available",
                message="Redis pub/sub service not found, distributed broadcasting disabled"
            )
            self.redis_enabled = False
        except Exception as e:
            logger.error(
                "redis_pubsub_initialization_failed",
                error=str(e)
            )
            self.redis_enabled = False

    async def _handle_redis_broadcast(self, message: dict):
        """
        Handle incoming broadcast messages from Redis - Task 10.3

        Forwards messages from Redis to local WebSocket connections

        Args:
            message: Message from Redis pub/sub
        """
        try:
            # Extract message metadata
            message_type = message.get("type")
            target_type = message.get("target_type", "broadcast")

            logger.debug(
                "redis_message_received",
                message_type=message_type,
                target_type=target_type
            )

            # Route message based on target type
            if target_type == "document":
                document_id = message.get("document_id")
                if document_id:
                    await self.send_to_document(message, document_id)

            elif target_type == "query":
                query_id = message.get("query_id")
                if query_id:
                    await self.send_to_query(message, query_id)

            elif target_type == "session":
                session_id = message.get("session_id")
                if session_id:
                    await self.send_to_session(message, session_id)

            elif target_type == "user":
                user_id = message.get("user_id")
                if user_id:
                    await self.send_to_user(message, user_id)

            elif target_type == "source":
                source_id = message.get("source_id")
                if source_id:
                    await self.send_to_source(message, source_id)

            elif target_type == "project_sources":
                project_id = message.get("project_id")
                if project_id:
                    await self.send_to_project_sources(message, project_id)

            else:
                # Broadcast to all local connections
                await self.broadcast(message)

        except Exception as e:
            logger.error(
                "redis_message_handling_failed",
                error=str(e),
                message_type=message.get("type")
            )

    async def publish_to_redis(
        self,
        channel: str,
        message: dict,
        channel_type: str = "general"
    ):
        """
        Publish message to Redis for distributed broadcasting - Task 10.3

        Args:
            channel: Redis channel name
            message: Message to publish
            channel_type: Channel type for metrics
        """
        if not self.redis_enabled or not self.redis_pubsub:
            return

        try:
            await self.redis_pubsub.publish_message(
                channel=channel,
                message=message,
                channel_type=channel_type
            )
        except Exception as e:
            logger.error(
                "redis_publish_failed",
                channel=channel,
                error=str(e)
            )

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
            "redis_enabled": self.redis_enabled,
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
