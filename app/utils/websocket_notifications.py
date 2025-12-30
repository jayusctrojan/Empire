"""
Empire v7.3 - WebSocket Notification Helpers for Celery Tasks - Task 10.4

Helper functions for Celery tasks to send real-time WebSocket notifications.
Handles both local WebSocket broadcasting and distributed Redis Pub/Sub.
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


def send_task_notification(
    task_id: str,
    task_name: str,
    status: str,
    message: str,
    progress: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    document_id: Optional[str] = None,
    query_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Send a WebSocket notification for a Celery task event.

    This function is safe to call from sync Celery task context - it handles
    async/await internally without blocking the task.

    Args:
        task_id: Celery task ID
        task_name: Task name (e.g., "process_adaptive_query")
        status: Task status (started, progress, success, failure)
        message: Human-readable message
        progress: Optional progress percentage (0-100)
        metadata: Optional additional data
        document_id: Optional document ID for document-specific notifications
        query_id: Optional query ID for query-specific notifications
        user_id: Optional user ID for user-specific notifications
        session_id: Optional session ID for session-specific notifications

    Example:
        # In a Celery task
        send_task_notification(
            task_id=self.request.id,
            task_name="process_document",
            status="started",
            message="Document processing started",
            document_id="doc_123"
        )
    """
    try:
        # Build notification payload
        notification = {
            "type": "task_event",
            "task_id": task_id,
            "task_name": task_name,
            "status": status,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if progress is not None:
            notification["progress"] = progress

        if metadata:
            notification["metadata"] = metadata

        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop in current thread (Celery worker context)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Send notification async
        loop.run_until_complete(
            _send_websocket_notification(
                notification=notification,
                document_id=document_id,
                query_id=query_id,
                user_id=user_id,
                session_id=session_id
            )
        )

    except Exception as e:
        # Don't let WebSocket errors break task execution
        logger.error(
            "websocket_notification_failed",
            task_id=task_id,
            task_name=task_name,
            error=str(e)
        )


async def _send_websocket_notification(
    notification: Dict[str, Any],
    document_id: Optional[str] = None,
    query_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Internal async function to send WebSocket notifications.

    Routes notifications to appropriate channels based on resource IDs.
    """
    try:
        # Import here to avoid circular imports
        from app.services.websocket_manager import get_connection_manager

        manager = get_connection_manager()

        # Route to specific channels
        if document_id:
            await manager.send_to_document(notification, document_id)
            logger.debug(
                "websocket_notification_sent_to_document",
                document_id=document_id,
                task_id=notification.get("task_id")
            )

        if query_id:
            await manager.send_to_query(notification, query_id)
            logger.debug(
                "websocket_notification_sent_to_query",
                query_id=query_id,
                task_id=notification.get("task_id")
            )

        if user_id:
            await manager.send_to_user(notification, user_id)
            logger.debug(
                "websocket_notification_sent_to_user",
                user_id=user_id,
                task_id=notification.get("task_id")
            )

        if session_id:
            await manager.send_to_session(notification, session_id)
            logger.debug(
                "websocket_notification_sent_to_session",
                session_id=session_id,
                task_id=notification.get("task_id")
            )

        # If no specific routing, broadcast to all
        if not any([document_id, query_id, user_id, session_id]):
            await manager.broadcast(notification)
            logger.debug(
                "websocket_notification_broadcast",
                task_id=notification.get("task_id")
            )

    except Exception as e:
        logger.error(
            "websocket_notification_send_failed",
            error=str(e),
            notification_type=notification.get("type")
        )


def send_document_processing_update(
    task_id: str,
    document_id: str,
    stage: str,
    status: str,
    message: str,
    progress: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Send WebSocket update for document processing tasks.

    Args:
        task_id: Celery task ID
        document_id: Document being processed
        stage: Processing stage (parsing, embedding, indexing, graph_sync)
        status: Stage status (started, progress, success, failure)
        message: Human-readable message
        progress: Optional progress percentage (0-100)
        metadata: Optional additional data (e.g., chunk count, embedding model)

    Example:
        send_document_processing_update(
            task_id=self.request.id,
            document_id="doc_123",
            stage="embedding",
            status="progress",
            message="Generated embeddings for 50/100 chunks",
            progress=50,
            metadata={"chunks_completed": 50, "total_chunks": 100}
        )
    """
    send_task_notification(
        task_id=task_id,
        task_name="document_processing",
        status=status,
        message=message,
        progress=progress,
        metadata={
            "stage": stage,
            **(metadata or {})
        },
        document_id=document_id
    )


def send_query_processing_update(
    task_id: str,
    query_id: str,
    stage: str,
    status: str,
    message: str,
    progress: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Send WebSocket update for query processing tasks.

    Args:
        task_id: Celery task ID
        query_id: Query being processed
        stage: Processing stage (refining, searching, synthesizing)
        status: Stage status (started, progress, success, failure)
        message: Human-readable message
        progress: Optional progress percentage (0-100)
        metadata: Optional additional data (e.g., iteration count, tool calls)
        user_id: Optional user ID
        session_id: Optional session ID

    Example:
        send_query_processing_update(
            task_id=self.request.id,
            query_id="query_456",
            stage="searching",
            status="progress",
            message="Iteration 2/3: Searching knowledge base",
            progress=66,
            metadata={"iteration": 2, "max_iterations": 3}
        )
    """
    send_task_notification(
        task_id=task_id,
        task_name="query_processing",
        status=status,
        message=message,
        progress=progress,
        metadata={
            "stage": stage,
            **(metadata or {})
        },
        query_id=query_id,
        user_id=user_id,
        session_id=session_id
    )


def send_embedding_generation_update(
    task_id: str,
    document_id: str,
    status: str,
    message: str,
    progress: Optional[int] = None,
    chunks_processed: Optional[int] = None,
    total_chunks: Optional[int] = None,
    model: Optional[str] = None
):
    """
    Send WebSocket update for embedding generation tasks.

    Args:
        task_id: Celery task ID
        document_id: Document being embedded
        status: Task status (started, progress, success, failure)
        message: Human-readable message
        progress: Optional progress percentage (0-100)
        chunks_processed: Optional number of chunks processed
        total_chunks: Optional total number of chunks
        model: Optional embedding model name

    Example:
        send_embedding_generation_update(
            task_id=self.request.id,
            document_id="doc_123",
            status="progress",
            message="Generating embeddings with BGE-M3",
            progress=60,
            chunks_processed=60,
            total_chunks=100,
            model="bge-m3"
        )
    """
    metadata = {}
    if chunks_processed is not None:
        metadata["chunks_processed"] = chunks_processed
    if total_chunks is not None:
        metadata["total_chunks"] = total_chunks
    if model:
        metadata["model"] = model

    send_task_notification(
        task_id=task_id,
        task_name="embedding_generation",
        status=status,
        message=message,
        progress=progress,
        metadata=metadata if metadata else None,
        document_id=document_id
    )


def send_graph_sync_update(
    task_id: str,
    document_id: str,
    status: str,
    message: str,
    progress: Optional[int] = None,
    entities_created: Optional[int] = None,
    relationships_created: Optional[int] = None
):
    """
    Send WebSocket update for graph synchronization tasks.

    Args:
        task_id: Celery task ID
        document_id: Document being synced to graph
        status: Task status (started, progress, success, failure)
        message: Human-readable message
        progress: Optional progress percentage (0-100)
        entities_created: Optional number of entities created
        relationships_created: Optional number of relationships created

    Example:
        send_graph_sync_update(
            task_id=self.request.id,
            document_id="doc_123",
            status="success",
            message="Graph sync completed",
            progress=100,
            entities_created=15,
            relationships_created=23
        )
    """
    metadata = {}
    if entities_created is not None:
        metadata["entities_created"] = entities_created
    if relationships_created is not None:
        metadata["relationships_created"] = relationships_created

    send_task_notification(
        task_id=task_id,
        task_name="graph_sync",
        status=status,
        message=message,
        progress=progress,
        metadata=metadata if metadata else None,
        document_id=document_id
    )
