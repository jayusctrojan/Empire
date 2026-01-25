"""
Empire v7.3 - Notification Dispatcher
Utility for emitting notifications from Celery tasks to WebSocket clients
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.services.websocket_manager import get_connection_manager
from app.services.email_service import get_email_service

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """
    Dispatch notifications from sync Celery tasks to async WebSocket clients and email

    This class bridges the sync world of Celery tasks with the async world
    of FastAPI WebSockets by running async coroutines in the event loop.
    Also sends email notifications for important events and long-running tasks.
    """

    def __init__(self):
        self.manager = get_connection_manager()
        self.email_service = get_email_service()
        self._loop = None
        self._task_start_times: Dict[str, float] = {}  # Track task start times

    def _get_or_create_loop(self):
        """Get existing event loop or create a new one"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop

    def notify_task_started(
        self,
        task_id: str,
        task_type: str,
        filename: Optional[str] = None,
        session_id: Optional[str] = None,
        user_emails: Optional[List[str]] = None
    ):
        """
        Notify that a task has started processing

        Args:
            task_id: Celery task ID
            task_type: Type of task (document_processing, embedding, etc.)
            filename: Optional filename being processed
            session_id: Optional session to notify
            user_emails: Optional list of user emails for notifications
        """
        # Record task start time for long-running detection
        self._task_start_times[task_id] = time.time()

        message = f"Processing started"
        if filename:
            message = f"Processing started: {filename}"

        try:
            loop = self._get_or_create_loop()
            loop.run_until_complete(
                self.manager.send_task_notification(
                    task_id=task_id,
                    task_type=task_type,
                    status="processing",
                    message=message,
                    session_id=session_id,
                    metadata={"filename": filename}
                )
            )
            logger.info(f"Notified task started: {task_id}")
        except Exception as e:
            logger.error(f"Error sending task started notification: {e}")

    def notify_task_progress(
        self,
        task_id: str,
        progress: int,
        total: int,
        message: str = "Processing...",
        session_id: Optional[str] = None
    ):
        """
        Notify about task progress

        Args:
            task_id: Celery task ID
            progress: Current progress value
            total: Total value
            message: Progress message
            session_id: Optional session to notify
        """
        try:
            loop = self._get_or_create_loop()
            loop.run_until_complete(
                self.manager.send_progress_update(
                    task_id=task_id,
                    progress=progress,
                    total=total,
                    message=message,
                    session_id=session_id
                )
            )
            logger.debug(f"Notified task progress: {task_id} ({progress}/{total})")
        except Exception as e:
            logger.error(f"Error sending progress notification: {e}")

    def notify_task_completed(
        self,
        task_id: str,
        task_type: str,
        filename: Optional[str] = None,
        session_id: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        user_emails: Optional[List[str]] = None
    ):
        """
        Notify that a task completed successfully

        Args:
            task_id: Celery task ID
            task_type: Type of task
            filename: Optional filename processed
            session_id: Optional session to notify
            result: Optional task result data
            user_emails: Optional list of user emails for notifications
        """
        # Calculate task duration
        duration = None
        if task_id in self._task_start_times:
            duration = time.time() - self._task_start_times[task_id]
            del self._task_start_times[task_id]  # Clean up

        message = f"Processing completed successfully"
        if filename:
            message = f"Processing completed: {filename}"

        try:
            # Send WebSocket notification
            loop = self._get_or_create_loop()
            loop.run_until_complete(
                self.manager.send_task_notification(
                    task_id=task_id,
                    task_type=task_type,
                    status="completed",
                    message=message,
                    session_id=session_id,
                    metadata={
                        "filename": filename,
                        "result": result,
                        "duration": duration
                    }
                )
            )
            logger.info(f"Notified task completed: {task_id}")

            # Send email notification if emails provided
            if user_emails and duration:
                self.email_service.send_task_notification(
                    to_emails=user_emails,
                    task_id=task_id,
                    task_type=task_type,
                    status="completed",
                    filename=filename,
                    duration=duration
                )
                logger.info(f"Sent email notification to {len(user_emails)} recipients")

        except Exception as e:
            logger.error(f"Error sending task completed notification: {e}")

    def notify_task_failed(
        self,
        task_id: str,
        task_type: str,
        error: str,
        filename: Optional[str] = None,
        session_id: Optional[str] = None,
        user_emails: Optional[List[str]] = None
    ):
        """
        Notify that a task failed

        Args:
            task_id: Celery task ID
            task_type: Type of task
            error: Error message
            filename: Optional filename being processed
            session_id: Optional session to notify
            user_emails: Optional list of user emails for notifications
        """
        # Clean up tracking
        if task_id in self._task_start_times:
            del self._task_start_times[task_id]

        message = f"Processing failed: {error}"
        if filename:
            message = f"Processing failed for {filename}: {error}"

        try:
            # Send WebSocket notification
            loop = self._get_or_create_loop()
            loop.run_until_complete(
                self.manager.send_task_notification(
                    task_id=task_id,
                    task_type=task_type,
                    status="failed",
                    message=message,
                    session_id=session_id,
                    metadata={
                        "filename": filename,
                        "error": error
                    }
                )
            )
            logger.info(f"Notified task failed: {task_id}")

            # Send email notification if emails provided
            if user_emails:
                self.email_service.send_task_notification(
                    to_emails=user_emails,
                    task_id=task_id,
                    task_type=task_type,
                    status="failed",
                    filename=filename,
                    error=error
                )
                logger.info(f"Sent failure email to {len(user_emails)} recipients")

        except Exception as e:
            logger.error(f"Error sending task failed notification: {e}")

    def notify_task_retry(
        self,
        task_id: str,
        task_type: str,
        retry_count: int,
        max_retries: int,
        filename: Optional[str] = None,
        session_id: Optional[str] = None,
        user_emails: Optional[List[str]] = None
    ):
        """
        Notify that a task is being retried

        Args:
            task_id: Celery task ID
            task_type: Type of task
            retry_count: Current retry attempt number
            max_retries: Maximum retry attempts
            filename: Optional filename being processed
            session_id: Optional session to notify
            user_emails: Optional list of user emails for notifications
        """
        message = f"Retrying... (attempt {retry_count + 1}/{max_retries})"
        if filename:
            message = f"Retrying {filename}... (attempt {retry_count + 1}/{max_retries})"

        try:
            # Send WebSocket notification
            loop = self._get_or_create_loop()
            loop.run_until_complete(
                self.manager.send_task_notification(
                    task_id=task_id,
                    task_type=task_type,
                    status="retry",
                    message=message,
                    session_id=session_id,
                    metadata={
                        "filename": filename,
                        "retry_count": retry_count,
                        "max_retries": max_retries
                    }
                )
            )
            logger.info(f"Notified task retry: {task_id} (attempt {retry_count + 1})")

            # Send email notification if emails provided (only on first retry to avoid spam)
            if user_emails and retry_count == 0:
                self.email_service.send_task_notification(
                    to_emails=user_emails,
                    task_id=task_id,
                    task_type=task_type,
                    status="retry",
                    filename=filename
                )
                logger.info(f"Sent retry email to {len(user_emails)} recipients")

        except Exception as e:
            logger.error(f"Error sending task retry notification: {e}")

    def check_long_running_task(
        self,
        task_id: str,
        task_type: str,
        threshold_seconds: float = 300.0,  # 5 minutes default
        filename: Optional[str] = None,
        user_emails: Optional[List[str]] = None,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Check if a task is long-running and send alert if needed

        Args:
            task_id: Celery task ID
            task_type: Type of task
            threshold_seconds: Threshold in seconds to trigger alert
            filename: Optional filename being processed
            user_emails: Optional list of user emails for alert
            session_id: Optional session to notify

        Returns:
            True if task is long-running and alert was sent
        """
        if task_id not in self._task_start_times:
            return False

        elapsed = time.time() - self._task_start_times[task_id]

        if elapsed < threshold_seconds:
            return False

        # Task is long-running
        logger.warning(f"Task {task_id} is long-running: {elapsed:.0f}s elapsed")

        try:
            # Send email alert if emails provided
            if user_emails:
                self.email_service.send_long_running_task_alert(
                    to_emails=user_emails,
                    task_id=task_id,
                    task_type=task_type,
                    filename=filename,
                    elapsed_time=elapsed
                )
                logger.info(f"Sent long-running task alert to {len(user_emails)} recipients")

            # Send WebSocket notification
            loop = self._get_or_create_loop()
            loop.run_until_complete(
                self.manager.send_task_notification(
                    task_id=task_id,
                    task_type=task_type,
                    status="processing",
                    message=f"Task is taking longer than expected ({elapsed/60:.1f} minutes)",
                    session_id=session_id,
                    metadata={
                        "filename": filename,
                        "elapsed_time": elapsed,
                        "long_running": True
                    }
                )
            )

            return True

        except Exception as e:
            logger.error(f"Error sending long-running task alert: {e}")
            return False

    def notify_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ):
        """
        Send a generic alert notification via WebSocket

        Args:
            alert_type: Type of alert (e.g., 'budget_alert', 'system_alert')
            severity: Alert severity ('info', 'warning', 'critical')
            message: Alert message
            metadata: Optional additional metadata
            session_id: Optional session to notify (broadcasts to all if None)
        """
        try:
            loop = self._get_or_create_loop()
            loop.run_until_complete(
                self.manager.broadcast_message({
                    "type": "alert",
                    "alert_type": alert_type,
                    "severity": severity,
                    "message": message,
                    "metadata": metadata or {},
                    "timestamp": datetime.now().isoformat()
                })
            )
            logger.info(f"Broadcast alert: {alert_type} ({severity})")
        except Exception as e:
            logger.error(f"Error sending alert notification: {e}")


# Global singleton instance
_notification_dispatcher = None


def get_notification_dispatcher() -> NotificationDispatcher:
    """
    Get singleton instance of NotificationDispatcher

    Returns:
        NotificationDispatcher instance
    """
    global _notification_dispatcher
    if _notification_dispatcher is None:
        _notification_dispatcher = NotificationDispatcher()
    return _notification_dispatcher
