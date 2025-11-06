"""
Empire v7.3 - Notification Models
Pydantic models for WebSocket and email notifications
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class NotificationType(str, Enum):
    """Notification type enum"""
    CONNECTION = "connection"
    TASK = "task_notification"
    PROGRESS = "progress_update"
    ERROR = "error"
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"


class TaskStatus(str, Enum):
    """Task status enum"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"


class BaseNotification(BaseModel):
    """Base notification model"""
    type: NotificationType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ConnectionNotification(BaseNotification):
    """WebSocket connection status notification"""
    type: NotificationType = NotificationType.CONNECTION
    status: str
    connection_id: str


class TaskNotification(BaseNotification):
    """Task-related notification"""
    type: NotificationType = NotificationType.TASK
    task_id: str
    task_type: str  # upload, processing, embedding, graph_sync, etc.
    status: TaskStatus
    message: str
    file_id: Optional[str] = None
    filename: Optional[str] = None
    error: Optional[str] = None


class ProgressNotification(BaseNotification):
    """Progress update notification"""
    type: NotificationType = NotificationType.PROGRESS
    task_id: str
    progress: int
    total: int
    percentage: float
    message: str


class ErrorNotification(BaseNotification):
    """Error notification"""
    type: NotificationType = NotificationType.ERROR
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class SuccessNotification(BaseNotification):
    """Success notification"""
    type: NotificationType = NotificationType.SUCCESS
    message: str
    data: Optional[Dict[str, Any]] = None


class InfoNotification(BaseNotification):
    """Info notification"""
    type: NotificationType = NotificationType.INFO
    message: str


class WarningNotification(BaseNotification):
    """Warning notification"""
    type: NotificationType = NotificationType.WARNING
    message: str


# Response models for API endpoints
class NotificationStats(BaseModel):
    """WebSocket connection statistics"""
    active_connections: int
    active_sessions: int
    connected_users: int
    timestamp: datetime


class WebSocketMessage(BaseModel):
    """Incoming WebSocket message from client"""
    action: str
    data: Optional[Dict[str, Any]] = None


class WebSocketResponse(BaseModel):
    """WebSocket response wrapper"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
