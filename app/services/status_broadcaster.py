"""
Empire v7.3 - Status Broadcasting Service - Task 12
Unified service for broadcasting Celery task status updates via:
- Redis Pub/Sub (for distributed WebSocket notifications)
- Database persistence (for status history and polling fallback)
- WebSocket notifications (for real-time UI updates)

Uses the standardized TaskStatusMessage schema from app/models/task_status.py
"""

import asyncio
import json
import os
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List
from redis import asyncio as aioredis
import structlog
from prometheus_client import Counter, Histogram

from app.models.task_status import (
    TaskStatusMessage,
    TaskState,
    TaskType,
    ProcessingStage,
    ProgressInfo,
    ErrorInfo,
    TaskStatusHistory,
    TaskStatusHistoryEntry,
    RedisStatusChannel,
    create_started_status,
    create_progress_status,
    create_success_status,
    create_failure_status,
    create_retry_status
)

logger = structlog.get_logger(__name__)

# Prometheus metrics for status broadcasting
STATUS_BROADCASTS = Counter(
    'empire_status_broadcasts_total',
    'Total status broadcasts sent',
    ['status', 'channel_type', 'task_type']
)

STATUS_BROADCAST_ERRORS = Counter(
    'empire_status_broadcast_errors_total',
    'Failed status broadcasts',
    ['error_type', 'channel_type']
)

STATUS_BROADCAST_DURATION = Histogram(
    'empire_status_broadcast_duration_seconds',
    'Duration of status broadcast operations',
    ['operation']
)

DATABASE_STATUS_UPDATES = Counter(
    'empire_database_status_updates_total',
    'Database status update operations',
    ['status', 'operation']
)


class StatusBroadcaster:
    """
    Unified service for broadcasting task status updates.

    Provides:
    - Redis Pub/Sub publishing to multiple channels
    - Database status persistence
    - WebSocket notification integration
    - Standardized message format
    """

    def __init__(self):
        """Initialize the Status Broadcaster"""
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        # Clean URL to remove invalid SSL parameters
        self.redis_url = self.redis_url.split("?")[0] if "?" in self.redis_url else self.redis_url

        self.redis_client: Optional[aioredis.Redis] = None
        self.channels = RedisStatusChannel()
        self._connected = False

        # Supabase client (lazy loaded)
        self._supabase = None

        logger.info(
            "status_broadcaster_initialized",
            redis_url=self.redis_url.split("@")[-1] if "@" in self.redis_url else self.redis_url
        )

    async def connect(self):
        """Connect to Redis for Pub/Sub publishing"""
        if self._connected:
            return

        try:
            self.redis_client = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            self._connected = True
            logger.info("status_broadcaster_redis_connected")
        except Exception as e:
            logger.error("status_broadcaster_redis_connection_failed", error=str(e))
            # Don't raise - allow degraded mode without Redis
            self._connected = False

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False
            logger.info("status_broadcaster_disconnected")

    def _get_supabase(self):
        """Get Supabase client (lazy loaded)"""
        if self._supabase is None:
            try:
                from app.services.supabase_storage import get_supabase_storage
                self._supabase = get_supabase_storage()
            except Exception as e:
                logger.error("supabase_client_initialization_failed", error=str(e))
        return self._supabase

    async def broadcast_status(
        self,
        status_message: TaskStatusMessage,
        persist_to_db: bool = True
    ):
        """
        Broadcast a status message to all relevant channels.

        Args:
            status_message: The TaskStatusMessage to broadcast
            persist_to_db: Whether to persist to database (default True)
        """
        with STATUS_BROADCAST_DURATION.labels(operation="broadcast").time():
            try:
                # Serialize message
                message_dict = status_message.model_dump(mode='json')
                message_json = json.dumps(message_dict, default=str)

                # Publish to Redis channels in parallel
                publish_tasks = []

                # 1. Task-specific channel
                task_channel = self.channels.get_task_channel(status_message.task_id)
                publish_tasks.append(self._publish_to_channel(
                    task_channel, message_json, "task"
                ))

                # 2. Document-specific channel (if document_id present)
                if status_message.document_id:
                    doc_channel = self.channels.get_document_channel(status_message.document_id)
                    publish_tasks.append(self._publish_to_channel(
                        doc_channel, message_json, "document"
                    ))

                # 3. Query-specific channel (if query_id present)
                if status_message.query_id:
                    query_channel = self.channels.get_query_channel(status_message.query_id)
                    publish_tasks.append(self._publish_to_channel(
                        query_channel, message_json, "query"
                    ))

                # 4. User-specific channel (if user_id present)
                if status_message.user_id:
                    user_channel = self.channels.get_user_channel(status_message.user_id)
                    publish_tasks.append(self._publish_to_channel(
                        user_channel, message_json, "user"
                    ))

                # 5. Global channel for monitoring
                publish_tasks.append(self._publish_to_channel(
                    self.channels.global_channel, message_json, "global"
                ))

                # Execute all publishes in parallel
                await asyncio.gather(*publish_tasks, return_exceptions=True)

                # Persist to database
                if persist_to_db:
                    await self._persist_to_database(status_message)

                # Update metrics
                STATUS_BROADCASTS.labels(
                    status=status_message.status.value,
                    channel_type="all",
                    task_type=status_message.task_type.value
                ).inc()

                logger.debug(
                    "status_broadcast_complete",
                    task_id=status_message.task_id,
                    status=status_message.status.value,
                    task_type=status_message.task_type.value
                )

            except Exception as e:
                logger.error(
                    "status_broadcast_failed",
                    task_id=status_message.task_id,
                    error=str(e)
                )
                STATUS_BROADCAST_ERRORS.labels(
                    error_type="broadcast_error",
                    channel_type="all"
                ).inc()

    async def _publish_to_channel(
        self,
        channel: str,
        message_json: str,
        channel_type: str
    ):
        """Publish message to a specific Redis channel"""
        try:
            if not self._connected or not self.redis_client:
                await self.connect()

            if self.redis_client:
                await self.redis_client.publish(channel, message_json)
                logger.debug(
                    "redis_message_published",
                    channel=channel,
                    channel_type=channel_type
                )
        except Exception as e:
            logger.error(
                "redis_publish_failed",
                channel=channel,
                channel_type=channel_type,
                error=str(e)
            )
            STATUS_BROADCAST_ERRORS.labels(
                error_type="redis_publish",
                channel_type=channel_type
            ).inc()

    async def _persist_to_database(self, status_message: TaskStatusMessage):
        """
        Persist status message to database.

        Updates the processing_status JSONB column with history.
        """
        with STATUS_BROADCAST_DURATION.labels(operation="database_persist").time():
            try:
                supabase = self._get_supabase()
                if not supabase:
                    logger.warning("supabase_not_available_for_status_persist")
                    return

                # Check if this is a document-related task
                if status_message.document_id:
                    await self._update_document_status(status_message)

                # Always update the processing_tasks table
                await self._update_processing_task(status_message)

                DATABASE_STATUS_UPDATES.labels(
                    status=status_message.status.value,
                    operation="persist"
                ).inc()

            except Exception as e:
                logger.error(
                    "database_status_persist_failed",
                    task_id=status_message.task_id,
                    error=str(e)
                )
                STATUS_BROADCAST_ERRORS.labels(
                    error_type="database_persist",
                    channel_type="database"
                ).inc()

    async def _update_document_status(self, status_message: TaskStatusMessage):
        """Update document's processing_status in documents table"""
        try:
            supabase = self._get_supabase()
            if not supabase or not status_message.document_id:
                return

            # Build processing status entry
            status_entry = {
                "task_id": status_message.task_id,
                "status": status_message.status.value,
                "message": status_message.status_message,
                "timestamp": status_message.updated_at.isoformat(),
            }

            if status_message.progress:
                status_entry["progress"] = {
                    "current": status_message.progress.current,
                    "total": status_message.progress.total,
                    "percentage": status_message.progress.percentage,
                    "stage": status_message.progress.stage.value if status_message.progress.stage else None
                }

            if status_message.error:
                status_entry["error"] = {
                    "type": status_message.error.error_type,
                    "message": status_message.error.error_message,
                    "retry_count": status_message.error.retry_count
                }

            # Update documents table
            # The processing_status column stores current status and brief history
            result = supabase.client.table("documents").update({
                "processing_status": status_message.status.value,
                "processing_details": status_entry,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", status_message.document_id).execute()

            logger.debug(
                "document_status_updated",
                document_id=status_message.document_id,
                status=status_message.status.value
            )

        except Exception as e:
            logger.error(
                "document_status_update_failed",
                document_id=status_message.document_id,
                error=str(e)
            )

    async def _update_processing_task(self, status_message: TaskStatusMessage):
        """Update or insert into processing_tasks table with full history"""
        try:
            supabase = self._get_supabase()
            if not supabase:
                return

            # Build the full status record
            task_record = {
                "task_id": status_message.task_id,
                "task_name": status_message.task_name,
                "task_type": status_message.task_type.value,
                "status": status_message.status.value,
                "status_message": status_message.status_message,
                "document_id": status_message.document_id,
                "query_id": status_message.query_id,
                "user_id": status_message.user_id,
                "session_id": status_message.session_id,
                "batch_id": status_message.batch_id,
                "worker_id": status_message.worker_id,
                "queue_name": status_message.queue_name,
                "priority": status_message.priority,
                "created_at": status_message.created_at.isoformat(),
                "updated_at": status_message.updated_at.isoformat(),
            }

            # Add optional fields
            if status_message.started_at:
                task_record["started_at"] = status_message.started_at.isoformat()
            if status_message.completed_at:
                task_record["completed_at"] = status_message.completed_at.isoformat()
            if status_message.runtime_seconds:
                task_record["runtime_seconds"] = status_message.runtime_seconds

            # Add progress as JSONB
            if status_message.progress:
                task_record["progress"] = status_message.progress.model_dump(mode='json')

            # Add error as JSONB
            if status_message.error:
                task_record["error"] = status_message.error.model_dump(mode='json')

            # Add result as JSONB
            if status_message.result:
                task_record["result"] = status_message.result

            # Add metadata as JSONB
            if status_message.metadata:
                task_record["metadata"] = status_message.metadata

            # Upsert to processing_tasks table
            result = supabase.client.table("processing_tasks").upsert(
                task_record,
                on_conflict="task_id"
            ).execute()

            logger.debug(
                "processing_task_updated",
                task_id=status_message.task_id,
                status=status_message.status.value
            )

        except Exception as e:
            logger.error(
                "processing_task_update_failed",
                task_id=status_message.task_id,
                error=str(e)
            )

    # Convenience methods for creating and broadcasting status messages

    async def broadcast_started(
        self,
        task_id: str,
        task_name: str,
        task_type: TaskType = TaskType.GENERIC,
        document_id: Optional[str] = None,
        query_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Broadcast task started status"""
        status_message = create_started_status(
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata
        )
        await self.broadcast_status(status_message)
        return status_message

    async def broadcast_progress(
        self,
        task_id: str,
        task_name: str,
        current: int,
        total: int,
        message: str,
        stage: Optional[ProcessingStage] = None,
        task_type: TaskType = TaskType.GENERIC,
        document_id: Optional[str] = None,
        query_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Broadcast task progress update"""
        status_message = create_progress_status(
            task_id=task_id,
            task_name=task_name,
            current=current,
            total=total,
            message=message,
            stage=stage,
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            metadata=metadata
        )
        await self.broadcast_status(status_message)
        return status_message

    async def broadcast_success(
        self,
        task_id: str,
        task_name: str,
        result: Optional[Dict[str, Any]] = None,
        runtime_seconds: Optional[float] = None,
        task_type: TaskType = TaskType.GENERIC,
        document_id: Optional[str] = None,
        query_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Broadcast task success status"""
        status_message = create_success_status(
            task_id=task_id,
            task_name=task_name,
            result=result,
            runtime_seconds=runtime_seconds,
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            metadata=metadata
        )
        await self.broadcast_status(status_message)
        return status_message

    async def broadcast_failure(
        self,
        task_id: str,
        task_name: str,
        error_type: str,
        error_message: str,
        retry_count: int = 0,
        max_retries: int = 3,
        stack_trace: Optional[str] = None,
        runtime_seconds: Optional[float] = None,
        task_type: TaskType = TaskType.GENERIC,
        document_id: Optional[str] = None,
        query_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Broadcast task failure status"""
        status_message = create_failure_status(
            task_id=task_id,
            task_name=task_name,
            error_type=error_type,
            error_message=error_message,
            retry_count=retry_count,
            max_retries=max_retries,
            stack_trace=stack_trace,
            runtime_seconds=runtime_seconds,
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            metadata=metadata
        )
        await self.broadcast_status(status_message)
        return status_message

    async def broadcast_retry(
        self,
        task_id: str,
        task_name: str,
        retry_count: int,
        max_retries: int,
        error_message: str,
        countdown_seconds: int,
        task_type: TaskType = TaskType.GENERIC,
        document_id: Optional[str] = None,
        query_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Broadcast task retry status"""
        status_message = create_retry_status(
            task_id=task_id,
            task_name=task_name,
            retry_count=retry_count,
            max_retries=max_retries,
            error_message=error_message,
            countdown_seconds=countdown_seconds,
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            metadata=metadata
        )
        await self.broadcast_status(status_message)
        return status_message


# Synchronous wrapper for use in Celery signal handlers
class SyncStatusBroadcaster:
    """
    Synchronous wrapper for StatusBroadcaster.
    Used in Celery signal handlers which run in sync context.
    """

    def __init__(self):
        self._async_broadcaster: Optional[StatusBroadcaster] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_broadcaster(self) -> StatusBroadcaster:
        """Get or create the async broadcaster"""
        if self._async_broadcaster is None:
            self._async_broadcaster = StatusBroadcaster()
        return self._async_broadcaster

    def _run_async(self, coro):
        """Run an async coroutine from sync context"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, create a task
                asyncio.create_task(coro)
            else:
                # We're in a sync context, run the coroutine
                loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop, create a new one
            asyncio.run(coro)

    def broadcast_started(
        self,
        task_id: str,
        task_name: str,
        task_type: TaskType = TaskType.GENERIC,
        document_id: Optional[str] = None,
        query_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Broadcast task started status (sync)"""
        broadcaster = self._get_broadcaster()
        self._run_async(broadcaster.broadcast_started(
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata
        ))

    def broadcast_progress(
        self,
        task_id: str,
        task_name: str,
        current: int,
        total: int,
        message: str,
        stage: Optional[ProcessingStage] = None,
        task_type: TaskType = TaskType.GENERIC,
        document_id: Optional[str] = None,
        query_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Broadcast task progress update (sync)"""
        broadcaster = self._get_broadcaster()
        self._run_async(broadcaster.broadcast_progress(
            task_id=task_id,
            task_name=task_name,
            current=current,
            total=total,
            message=message,
            stage=stage,
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            metadata=metadata
        ))

    def broadcast_success(
        self,
        task_id: str,
        task_name: str,
        result: Optional[Dict[str, Any]] = None,
        runtime_seconds: Optional[float] = None,
        task_type: TaskType = TaskType.GENERIC,
        document_id: Optional[str] = None,
        query_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Broadcast task success status (sync)"""
        broadcaster = self._get_broadcaster()
        self._run_async(broadcaster.broadcast_success(
            task_id=task_id,
            task_name=task_name,
            result=result,
            runtime_seconds=runtime_seconds,
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            metadata=metadata
        ))

    def broadcast_failure(
        self,
        task_id: str,
        task_name: str,
        error_type: str,
        error_message: str,
        retry_count: int = 0,
        max_retries: int = 3,
        stack_trace: Optional[str] = None,
        runtime_seconds: Optional[float] = None,
        task_type: TaskType = TaskType.GENERIC,
        document_id: Optional[str] = None,
        query_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Broadcast task failure status (sync)"""
        broadcaster = self._get_broadcaster()
        self._run_async(broadcaster.broadcast_failure(
            task_id=task_id,
            task_name=task_name,
            error_type=error_type,
            error_message=error_message,
            retry_count=retry_count,
            max_retries=max_retries,
            stack_trace=stack_trace,
            runtime_seconds=runtime_seconds,
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            metadata=metadata
        ))

    def broadcast_retry(
        self,
        task_id: str,
        task_name: str,
        retry_count: int,
        max_retries: int,
        error_message: str,
        countdown_seconds: int,
        task_type: TaskType = TaskType.GENERIC,
        document_id: Optional[str] = None,
        query_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Broadcast task retry status (sync)"""
        broadcaster = self._get_broadcaster()
        self._run_async(broadcaster.broadcast_retry(
            task_id=task_id,
            task_name=task_name,
            retry_count=retry_count,
            max_retries=max_retries,
            error_message=error_message,
            countdown_seconds=countdown_seconds,
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            metadata=metadata
        ))


# Global singleton instances
_status_broadcaster: Optional[StatusBroadcaster] = None
_sync_status_broadcaster: Optional[SyncStatusBroadcaster] = None


async def get_status_broadcaster() -> StatusBroadcaster:
    """Get the async StatusBroadcaster singleton"""
    global _status_broadcaster
    if _status_broadcaster is None:
        _status_broadcaster = StatusBroadcaster()
        await _status_broadcaster.connect()
    return _status_broadcaster


def get_sync_status_broadcaster() -> SyncStatusBroadcaster:
    """Get the sync StatusBroadcaster singleton for Celery signal handlers"""
    global _sync_status_broadcaster
    if _sync_status_broadcaster is None:
        _sync_status_broadcaster = SyncStatusBroadcaster()
    return _sync_status_broadcaster


# Helper function to determine task type from task name
def get_task_type_from_name(task_name: str) -> TaskType:
    """
    Determine TaskType from Celery task name.

    Args:
        task_name: Full Celery task name (e.g., 'app.tasks.document_processing.process_document')

    Returns:
        TaskType enum value
    """
    task_name_lower = task_name.lower()

    if 'document' in task_name_lower or 'process' in task_name_lower:
        return TaskType.DOCUMENT_PROCESSING
    elif 'embedding' in task_name_lower:
        return TaskType.EMBEDDING_GENERATION
    elif 'graph' in task_name_lower or 'sync' in task_name_lower:
        return TaskType.GRAPH_SYNC
    elif 'crew' in task_name_lower or 'agent' in task_name_lower:
        return TaskType.CREWAI_WORKFLOW
    elif 'query' in task_name_lower:
        return TaskType.QUERY_PROCESSING
    elif 'batch' in task_name_lower:
        return TaskType.BATCH_OPERATION
    elif 'health' in task_name_lower:
        return TaskType.HEALTH_CHECK
    else:
        return TaskType.GENERIC
