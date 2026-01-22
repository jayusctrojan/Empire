"""
Empire v7.3 - Task Status Models - Task 12.2
Pydantic models for standardized task status messages used across
Redis Pub/Sub, WebSocket notifications, and database persistence.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from enum import Enum
import uuid


class TaskState(str, Enum):
    """
    Celery-compatible task state values.
    Extended with custom states for better progress tracking.
    """
    # Standard Celery states
    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"

    # Custom extended states for progress tracking
    QUEUED = "queued"
    PROCESSING = "processing"
    PROGRESS = "progress"  # Intermediate progress update
    COMPLETED = "completed"  # Alias for success
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Types of background tasks that can be tracked."""
    DOCUMENT_PROCESSING = "document_processing"
    EMBEDDING_GENERATION = "embedding_generation"
    GRAPH_SYNC = "graph_sync"
    CREWAI_WORKFLOW = "crewai_workflow"
    QUERY_PROCESSING = "query_processing"
    BATCH_OPERATION = "batch_operation"
    HEALTH_CHECK = "health_check"
    GENERIC = "generic"


class ProcessingStage(str, Enum):
    """Processing stages for multi-stage tasks."""
    # Document processing stages
    UPLOADING = "uploading"
    PARSING = "parsing"
    EXTRACTING_METADATA = "extracting_metadata"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    GRAPH_SYNCING = "graph_syncing"

    # Query processing stages
    REFINING = "refining"
    SEARCHING = "searching"
    RERANKING = "reranking"
    SYNTHESIZING = "synthesizing"

    # CrewAI stages
    AGENT_INITIALIZING = "agent_initializing"
    AGENT_EXECUTING = "agent_executing"
    AGENT_DELEGATING = "agent_delegating"

    # Generic stages
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    FINALIZING = "finalizing"
    COMPLETED = "completed"


class ProgressInfo(BaseModel):
    """Detailed progress information for long-running tasks."""
    current: int = Field(0, ge=0, description="Current progress value")
    total: int = Field(100, ge=1, description="Total progress value")
    percentage: float = Field(0.0, ge=0.0, le=100.0, description="Calculated percentage")
    message: str = Field("", description="Human-readable progress message")
    stage: Optional[ProcessingStage] = Field(None, description="Current processing stage")
    stage_index: Optional[int] = Field(None, ge=0, description="Stage index (0-based)")
    total_stages: Optional[int] = Field(None, ge=1, description="Total number of stages")

    @field_validator('percentage', mode='before')
    @classmethod
    def calculate_percentage(cls, v, info):
        """Auto-calculate percentage if not provided."""
        if v == 0.0 and 'current' in info.data and 'total' in info.data:
            total = info.data.get('total', 100)
            if total > 0:
                return round((info.data.get('current', 0) / total) * 100, 2)
        return v

    def model_post_init(self, __context):
        """Calculate percentage after initialization."""
        if self.percentage == 0.0 and self.total > 0:
            self.percentage = round((self.current / self.total) * 100, 2)


class ErrorInfo(BaseModel):
    """Structured error information for failed tasks."""
    error_type: str = Field(..., description="Exception type name")
    error_message: str = Field(..., description="Error message")
    stack_trace: Optional[str] = Field(None, description="Stack trace (truncated)")
    retry_count: int = Field(0, ge=0, description="Number of retries attempted")
    max_retries: int = Field(3, ge=0, description="Maximum retries allowed")
    is_retryable: bool = Field(True, description="Whether error is retryable")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TaskStatusMessage(BaseModel):
    """
    Standardized task status message schema.

    This is the primary schema used for:
    - Redis Pub/Sub broadcasting
    - WebSocket notifications
    - Database status history (JSONB)
    - REST API status responses

    Designed to be consistent across all status communication channels.
    """
    # Identification
    task_id: str = Field(..., description="Celery task ID")
    task_name: str = Field(..., description="Full task name (e.g., app.tasks.document_processing.process_document)")
    task_type: TaskType = Field(TaskType.GENERIC, description="Category of task")

    # Status
    status: TaskState = Field(..., description="Current task state")
    status_message: str = Field("", description="Human-readable status message")

    # Progress tracking
    progress: Optional[ProgressInfo] = Field(None, description="Progress details")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When task was created")
    started_at: Optional[datetime] = Field(None, description="When task started executing")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When status was last updated")
    completed_at: Optional[datetime] = Field(None, description="When task completed (success or failure)")

    # Timing metrics
    runtime_seconds: Optional[float] = Field(None, ge=0, description="Total runtime in seconds")
    estimated_remaining_seconds: Optional[float] = Field(None, ge=0, description="Estimated time remaining")

    # Resource associations
    document_id: Optional[str] = Field(None, description="Associated document ID")
    query_id: Optional[str] = Field(None, description="Associated query ID")
    user_id: Optional[str] = Field(None, description="User who initiated the task")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    batch_id: Optional[str] = Field(None, description="Batch operation ID")

    # Result data (populated on completion)
    result: Optional[Dict[str, Any]] = Field(None, description="Task result data")

    # Error handling
    error: Optional[ErrorInfo] = Field(None, description="Error details if failed")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional task metadata")
    worker_id: Optional[str] = Field(None, description="Celery worker that processed the task")
    queue_name: Optional[str] = Field(None, description="Queue the task was submitted to")
    priority: int = Field(5, ge=0, le=9, description="Task priority (0-9, 9 highest)")

    # Version for schema evolution
    schema_version: str = Field("1.0", description="Schema version for compatibility")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "abc123-def456",
                "task_name": "app.tasks.document_processing.process_document",
                "task_type": "document_processing",
                "status": "processing",
                "status_message": "Extracting metadata from document",
                "progress": {
                    "current": 45,
                    "total": 100,
                    "percentage": 45.0,
                    "message": "Processing page 5 of 11",
                    "stage": "extracting_metadata"
                },
                "created_at": "2025-11-26T10:30:00Z",
                "started_at": "2025-11-26T10:30:01Z",
                "updated_at": "2025-11-26T10:30:45Z",
                "document_id": "doc-789",
                "user_id": "user-123",
                "metadata": {
                    "filename": "report.pdf",
                    "file_size": 1024000
                }
            }
        }


class TaskStatusHistoryEntry(BaseModel):
    """
    Single entry in task status history.
    Stored in processing_status JSONB column.
    """
    status: TaskState
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    progress: Optional[ProgressInfo] = None
    error: Optional[ErrorInfo] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskStatusHistory(BaseModel):
    """
    Complete status history for a task.
    Stored in processing_status JSONB column in database.
    """
    task_id: str
    task_name: str
    task_type: TaskType
    current_status: TaskState
    entries: List[TaskStatusHistoryEntry] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_runtime_seconds: Optional[float] = None
    final_result: Optional[Dict[str, Any]] = None
    final_error: Optional[ErrorInfo] = None

    def add_entry(
        self,
        status: TaskState,
        message: str,
        progress: Optional[ProgressInfo] = None,
        error: Optional[ErrorInfo] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add a new status entry to the history."""
        entry = TaskStatusHistoryEntry(
            status=status,
            message=message,
            progress=progress,
            error=error,
            metadata=metadata or {}
        )
        self.entries.append(entry)
        self.current_status = status

        # Update timestamps
        if status == TaskState.STARTED and not self.started_at:
            self.started_at = entry.timestamp
        elif status in [TaskState.SUCCESS, TaskState.FAILURE, TaskState.COMPLETED, TaskState.CANCELLED]:
            self.completed_at = entry.timestamp
            if self.started_at:
                self.total_runtime_seconds = (entry.timestamp - self.started_at).total_seconds()


class RedisStatusChannel(BaseModel):
    """Configuration for Redis Pub/Sub channels."""
    # Channel naming patterns
    task_channel_pattern: str = Field("empire:task:{task_id}", description="Pattern for task-specific channels")
    document_channel_pattern: str = Field("empire:document:{document_id}", description="Pattern for document channels")
    query_channel_pattern: str = Field("empire:query:{query_id}", description="Pattern for query channels")
    user_channel_pattern: str = Field("empire:user:{user_id}", description="Pattern for user channels")
    global_channel: str = Field("empire:tasks:all", description="Global channel for all task updates")

    def get_task_channel(self, task_id: str) -> str:
        return self.task_channel_pattern.format(task_id=task_id)

    def get_document_channel(self, document_id: str) -> str:
        return self.document_channel_pattern.format(document_id=document_id)

    def get_query_channel(self, query_id: str) -> str:
        return self.query_channel_pattern.format(query_id=query_id)

    def get_user_channel(self, user_id: str) -> str:
        return self.user_channel_pattern.format(user_id=user_id)


# Factory functions for creating status messages
def create_started_status(
    task_id: str,
    task_name: str,
    task_type: TaskType = TaskType.GENERIC,
    document_id: Optional[str] = None,
    query_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> TaskStatusMessage:
    """Create a status message for task start."""
    now = datetime.utcnow()
    return TaskStatusMessage(
        task_id=task_id,
        task_name=task_name,
        task_type=task_type,
        status=TaskState.STARTED,
        status_message=f"Task {task_name.split('.')[-1]} started",
        progress=ProgressInfo(current=0, total=100, message="Starting..."),
        created_at=now,
        started_at=now,
        updated_at=now,
        document_id=document_id,
        query_id=query_id,
        user_id=user_id,
        session_id=session_id,
        metadata=metadata or {}
    )


def create_progress_status(
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
) -> TaskStatusMessage:
    """Create a status message for progress update."""
    return TaskStatusMessage(
        task_id=task_id,
        task_name=task_name,
        task_type=task_type,
        status=TaskState.PROGRESS,
        status_message=message,
        progress=ProgressInfo(
            current=current,
            total=total,
            message=message,
            stage=stage
        ),
        updated_at=datetime.utcnow(),
        document_id=document_id,
        query_id=query_id,
        user_id=user_id,
        metadata=metadata or {}
    )


def create_success_status(
    task_id: str,
    task_name: str,
    result: Optional[Dict[str, Any]] = None,
    runtime_seconds: Optional[float] = None,
    task_type: TaskType = TaskType.GENERIC,
    document_id: Optional[str] = None,
    query_id: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> TaskStatusMessage:
    """Create a status message for successful completion."""
    now = datetime.utcnow()
    return TaskStatusMessage(
        task_id=task_id,
        task_name=task_name,
        task_type=task_type,
        status=TaskState.SUCCESS,
        status_message=f"Task {task_name.split('.')[-1]} completed successfully",
        progress=ProgressInfo(current=100, total=100, percentage=100.0, message="Completed"),
        updated_at=now,
        completed_at=now,
        runtime_seconds=runtime_seconds,
        result=result,
        document_id=document_id,
        query_id=query_id,
        user_id=user_id,
        metadata=metadata or {}
    )


def create_failure_status(
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
) -> TaskStatusMessage:
    """Create a status message for task failure."""
    now = datetime.utcnow()
    return TaskStatusMessage(
        task_id=task_id,
        task_name=task_name,
        task_type=task_type,
        status=TaskState.FAILURE,
        status_message=f"Task failed: {error_message}",
        updated_at=now,
        completed_at=now,
        runtime_seconds=runtime_seconds,
        error=ErrorInfo(
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace[:1000] if stack_trace else None,  # Truncate stack trace
            retry_count=retry_count,
            max_retries=max_retries,
            is_retryable=retry_count < max_retries
        ),
        document_id=document_id,
        query_id=query_id,
        user_id=user_id,
        metadata=metadata or {}
    )


def create_retry_status(
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
) -> TaskStatusMessage:
    """Create a status message for task retry."""
    return TaskStatusMessage(
        task_id=task_id,
        task_name=task_name,
        task_type=task_type,
        status=TaskState.RETRY,
        status_message=f"Retrying ({retry_count + 1}/{max_retries}) in {countdown_seconds}s: {error_message}",
        progress=ProgressInfo(
            current=0,
            total=100,
            message=f"Retry {retry_count + 1} of {max_retries}"
        ),
        updated_at=datetime.utcnow(),
        estimated_remaining_seconds=float(countdown_seconds),
        error=ErrorInfo(
            error_type="RetryError",
            error_message=error_message,
            retry_count=retry_count,
            max_retries=max_retries,
            is_retryable=True
        ),
        document_id=document_id,
        query_id=query_id,
        user_id=user_id,
        metadata={
            **(metadata or {}),
            "countdown_seconds": countdown_seconds
        }
    )
