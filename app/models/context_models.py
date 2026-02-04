"""
Empire v7.3 - Context Window Management Models
Pydantic models for chat context window state, messages, and compaction.

Feature: Chat Context Window Management (011)
"""

from datetime import datetime
from typing import Optional, List, Any, Dict, Literal
from pydantic import BaseModel, Field
from enum import Enum


class ContextStatus(str, Enum):
    """Context window usage status"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class CompactionTrigger(str, Enum):
    """How compaction was triggered"""
    AUTO = "auto"
    MANUAL = "manual"
    FORCE = "force"
    ERROR_RECOVERY = "error_recovery"


class MessageRole(str, Enum):
    """Message sender role"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class CheckpointAutoTag(str, Enum):
    """Auto-generated checkpoint tags"""
    CODE = "code"
    DECISION = "decision"
    ERROR_RESOLUTION = "error_resolution"
    MILESTONE = "milestone"


class RetentionType(str, Enum):
    """Session memory retention policy"""
    PROJECT = "project"
    CKO = "cko"
    INDEFINITE = "indefinite"


# ==============================================================================
# Core Models
# ==============================================================================

class ContextWindowStatus(BaseModel):
    """
    Real-time status of a conversation's context window.

    Used for progress bar display and compaction triggering.
    """
    conversation_id: str = Field(..., description="Conversation ID")
    current_tokens: int = Field(..., ge=0, description="Current token count")
    max_tokens: int = Field(default=200000, gt=0, description="Maximum allowed tokens")
    threshold_percent: int = Field(default=80, ge=0, le=100, description="Compaction threshold")
    usage_percent: float = Field(..., ge=0, le=100, description="Current usage percentage")
    status: ContextStatus = Field(..., description="Status: normal, warning, critical")
    available_tokens: int = Field(..., ge=0, description="Tokens available before threshold")
    estimated_messages_remaining: int = Field(
        default=0,
        ge=0,
        description="Estimated messages that can still fit"
    )
    is_compacting: bool = Field(default=False, description="Whether compaction is in progress")
    last_compaction_at: Optional[datetime] = Field(None, description="Last compaction timestamp")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last status update")

    model_config = {
        "from_attributes": True
    }


class ContextMessage(BaseModel):
    """
    A message in the context window with token count and protection status.
    """
    id: str = Field(..., description="Message UUID")
    context_id: str = Field(..., description="Parent context ID")
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    token_count: int = Field(..., ge=0, description="Tokens in this message")
    is_protected: bool = Field(default=False, description="Cannot be summarized")
    position: int = Field(..., ge=0, description="Position in conversation")
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = {
        "from_attributes": True
    }


class ConversationContext(BaseModel):
    """
    Context window state for a conversation.
    """
    id: str = Field(..., description="Context UUID")
    conversation_id: str = Field(..., description="Parent conversation ID")
    user_id: str = Field(..., description="Owner user ID")
    total_tokens: int = Field(default=0, ge=0, description="Current token count")
    max_tokens: int = Field(default=200000, gt=0, description="Maximum tokens")
    threshold_percent: int = Field(default=80, ge=0, le=100, description="Compaction threshold")
    last_compaction_at: Optional[datetime] = Field(None, description="Last compaction time")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = {
        "from_attributes": True
    }


class CompactionLog(BaseModel):
    """
    Record of a compaction event.
    """
    id: str = Field(..., description="Log UUID")
    context_id: str = Field(..., description="Context that was compacted")
    pre_tokens: int = Field(..., ge=0, description="Tokens before compaction")
    post_tokens: int = Field(..., ge=0, description="Tokens after compaction")
    reduction_percent: float = Field(..., ge=0, le=100, description="Percentage reduced")
    summary_preview: Optional[str] = Field(None, max_length=500, description="First 500 chars")
    messages_condensed: int = Field(..., ge=0, description="Messages summarized")
    model_used: str = Field(..., description="AI model used for summarization")
    duration_ms: int = Field(..., ge=0, description="Compaction duration")
    triggered_by: CompactionTrigger = Field(..., description="Trigger type")
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = {
        "from_attributes": True
    }


class CompactionResult(BaseModel):
    """
    Result of a compaction operation (internal use).
    """
    session_id: str = Field(..., description="Conversation/session ID")
    trigger: CompactionTrigger = Field(..., description="How compaction was triggered")
    pre_tokens: int = Field(..., ge=0, description="Tokens before compaction")
    post_tokens: int = Field(..., ge=0, description="Tokens after compaction")
    reduction_percent: float = Field(..., ge=0, le=100, description="Percentage reduced")
    messages_condensed: int = Field(..., ge=0, description="Number of messages condensed")
    summary_preview: str = Field(..., description="Preview of the summary")
    summary_full: Optional[str] = Field(None, description="Full summary content")
    duration_ms: int = Field(..., ge=0, description="Duration in milliseconds")
    cost_usd: float = Field(default=0.0, ge=0, description="Estimated API cost")
    model_used: str = Field(default="claude-3-haiku-20240307", description="Model used")
    success: bool = Field(default=True, description="Whether compaction succeeded")
    error_message: Optional[str] = Field(None, description="Error if failed")
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = {
        "from_attributes": True
    }


class SessionCheckpoint(BaseModel):
    """
    Point-in-time snapshot for crash recovery.
    """
    id: str = Field(..., description="Checkpoint UUID")
    conversation_id: str = Field(..., description="Parent conversation")
    user_id: str = Field(..., description="Owner user ID")
    checkpoint_data: Dict[str, Any] = Field(..., description="Full conversation state")
    token_count: int = Field(..., ge=0, description="Tokens at checkpoint")
    label: Optional[str] = Field(None, description="User-provided label")
    auto_tag: Optional[CheckpointAutoTag] = Field(None, description="Auto-generated tag")
    is_abnormal_close: bool = Field(default=False, description="Crash recovery checkpoint")
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime = Field(..., description="30-day TTL")

    model_config = {
        "from_attributes": True
    }


class SessionMemory(BaseModel):
    """
    Persistent summary for session resume.
    """
    id: str = Field(..., description="Memory UUID")
    conversation_id: str = Field(..., description="Parent conversation")
    user_id: str = Field(..., description="Owner user ID")
    project_id: Optional[str] = Field(None, description="Associated project")
    summary: str = Field(..., description="Conversation summary")
    key_decisions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Array of decisions"
    )
    files_mentioned: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Array of file paths"
    )
    code_preserved: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Important code snippets"
    )
    retention_type: RetentionType = Field(..., description="Retention policy")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = {
        "from_attributes": True
    }


# ==============================================================================
# Request Models
# ==============================================================================

class CreateContextRequest(BaseModel):
    """Request to create a new conversation context"""
    conversation_id: str = Field(..., description="Conversation to create context for")
    max_tokens: int = Field(default=200000, gt=0, description="Maximum tokens")
    threshold_percent: int = Field(default=80, ge=0, le=100, description="Compaction threshold")


class AddMessageRequest(BaseModel):
    """Request to add a message to context"""
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., min_length=1, description="Message content")
    is_protected: bool = Field(default=False, description="Protect from summarization")


class TriggerCompactionRequest(BaseModel):
    """Request to trigger compaction"""
    force: bool = Field(default=False, description="Force compaction even below threshold")
    fast: bool = Field(default=False, description="Use faster Haiku model")


class ToggleProtectionRequest(BaseModel):
    """Request to toggle message protection"""
    is_protected: bool = Field(..., description="New protection status")


class CreateCheckpointRequest(BaseModel):
    """Request to create a manual checkpoint"""
    label: Optional[str] = Field(None, max_length=200, description="Checkpoint label")


class ResumeSessionRequest(BaseModel):
    """Request to resume a session"""
    checkpoint_id: Optional[str] = Field(None, description="Specific checkpoint to resume from")


# ==============================================================================
# Response Models
# ==============================================================================

class ContextStatusResponse(BaseModel):
    """Response with context window status"""
    success: bool
    status: Optional[ContextWindowStatus] = None
    error: Optional[str] = None


class AddMessageResponse(BaseModel):
    """Response after adding a message"""
    success: bool
    message_id: Optional[str] = None
    token_count: int = 0
    context_status: Optional[ContextWindowStatus] = None
    compaction_triggered: bool = False
    error: Optional[str] = None


class CompactionStatusResponse(BaseModel):
    """Response with compaction status"""
    success: bool
    status: Literal["idle", "in_progress", "completed", "failed"]
    progress: int = Field(default=0, ge=0, le=100)
    stage: Optional[str] = None
    result: Optional[CompactionLog] = None
    error: Optional[str] = None


class CompactionResultResponse(BaseModel):
    """Response after compaction completes"""
    success: bool
    log: Optional[CompactionLog] = None
    context_status: Optional[ContextWindowStatus] = None
    error: Optional[str] = None


class CheckpointResponse(BaseModel):
    """Response with checkpoint info"""
    success: bool
    checkpoint: Optional[SessionCheckpoint] = None
    error: Optional[str] = None


class CheckpointListResponse(BaseModel):
    """Response with list of checkpoints"""
    success: bool
    checkpoints: List[SessionCheckpoint] = []
    total: int = 0
    error: Optional[str] = None


class RecoveryCheckResponse(BaseModel):
    """Response for crash recovery check"""
    success: bool
    has_recovery: bool = False
    checkpoint: Optional[SessionCheckpoint] = None
    conversation_title: Optional[str] = None
    error: Optional[str] = None


class SessionListResponse(BaseModel):
    """Response with list of resumable sessions"""
    success: bool
    sessions: List[Dict[str, Any]] = []
    total: int = 0
    error: Optional[str] = None


class SessionResumeResponse(BaseModel):
    """Response after resuming a session"""
    success: bool
    conversation_id: Optional[str] = None
    context_status: Optional[ContextWindowStatus] = None
    messages: List[ContextMessage] = []
    memory: Optional[SessionMemory] = None
    error: Optional[str] = None
