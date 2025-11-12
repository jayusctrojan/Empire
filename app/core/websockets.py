"""
Empire v7.3 - WebSocket Broadcasting Utilities
Helper functions for broadcasting real-time notifications
"""

from app.services.websocket_manager import get_connection_manager
from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


def broadcast_execution_update(
    execution_id: str,
    data: Dict[str, Any],
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Broadcast a crew execution update via WebSocket.

    This is a synchronous wrapper for async WebSocket broadcasting
    that can be safely called from Celery tasks.

    Args:
        execution_id: UUID of the execution
        data: Update data (status, results, etc.)
        user_id: Optional user ID to target
        session_id: Optional session ID to target
    """
    try:
        import asyncio

        manager = get_connection_manager()

        # Create notification message
        message = {
            "type": "crew_execution_update",
            "execution_id": execution_id,
            "data": data,
            **data  # Merge data fields into message
        }

        # Get event loop or create new one for synchronous context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop in current thread (Celery worker)
            # Create a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Send notification based on target
        if user_id:
            loop.run_until_complete(manager.send_to_user(message, user_id))
        elif session_id:
            loop.run_until_complete(manager.send_to_session(message, session_id))
        else:
            # Broadcast to all connections
            loop.run_until_complete(manager.broadcast(message))

        logger.info(
            "Broadcasted execution update",
            execution_id=execution_id,
            status=data.get("status"),
            user_id=user_id,
            session_id=session_id
        )

    except Exception as e:
        logger.error(
            "Failed to broadcast execution update",
            execution_id=execution_id,
            error=str(e),
            exc_info=True
        )
        # Don't raise - WebSocket failures should not break the task


async def async_broadcast_execution_update(
    execution_id: str,
    data: Dict[str, Any],
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Async version of broadcast_execution_update for use in async contexts.

    Args:
        execution_id: UUID of the execution
        data: Update data (status, results, etc.)
        user_id: Optional user ID to target
        session_id: Optional session ID to target
    """
    try:
        manager = get_connection_manager()

        # Create notification message
        message = {
            "type": "crew_execution_update",
            "execution_id": execution_id,
            "data": data,
            **data  # Merge data fields into message
        }

        # Send notification based on target
        if user_id:
            await manager.send_to_user(message, user_id)
        elif session_id:
            await manager.send_to_session(message, session_id)
        else:
            # Broadcast to all connections
            await manager.broadcast(message)

        logger.info(
            "Broadcasted execution update",
            execution_id=execution_id,
            status=data.get("status"),
            user_id=user_id,
            session_id=session_id
        )

    except Exception as e:
        logger.error(
            "Failed to broadcast execution update",
            execution_id=execution_id,
            error=str(e),
            exc_info=True
        )
