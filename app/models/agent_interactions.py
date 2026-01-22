"""
Empire v7.3 - Agent Interaction Models (Task 39)
Pydantic models for inter-agent messaging, events, state sync, and conflict resolution
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from uuid import UUID


# Enums for interaction types
InteractionType = Literal["message", "event", "state_sync", "delegation", "conflict", "response"]
EventType = Literal[
    "task_started", "task_completed", "task_failed", "task_delegated",
    "delegation_accepted", "delegation_rejected", "agent_error", "agent_idle",
    "data_shared", "workflow_started", "workflow_completed"
]
ConflictType = Literal[
    "concurrent_update", "duplicate_assignment", "resource_contention",
    "state_mismatch", "deadline_conflict", "priority_conflict"
]
ResolutionStrategy = Literal["latest_wins", "manual", "merge", "rollback", "escalate"]


class AgentInteractionBase(BaseModel):
    """Base model for agent interactions"""
    execution_id: UUID = Field(description="Execution this interaction belongs to")
    from_agent_id: UUID = Field(description="Source agent ID")
    to_agent_id: Optional[UUID] = Field(None, description="Target agent ID (null for broadcast)")
    interaction_type: InteractionType = Field(description="Type of interaction")
    message: str = Field(description="Interaction message/payload")
    priority: int = Field(default=0, ge=-10, le=10, description="Priority (-10 to 10)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class DirectMessageRequest(AgentInteractionBase):
    """Direct message from one agent to another"""
    interaction_type: Literal["message"] = "message"
    to_agent_id: UUID = Field(description="Target agent ID (required for direct messages)")
    requires_response: bool = Field(default=False, description="Whether a response is expected")
    response_deadline: Optional[datetime] = Field(None, description="Deadline for response")


class BroadcastMessageRequest(AgentInteractionBase):
    """Broadcast message to all agents in a crew"""
    interaction_type: Literal["message"] = "message"
    to_agent_id: Literal[None] = None  # Must be null for broadcast
    requires_response: bool = False  # Broadcasts don't require responses


class EventPublicationRequest(AgentInteractionBase):
    """Event publication for workflow coordination"""
    interaction_type: Literal["event"] = "event"
    event_type: EventType = Field(description="Type of event being published")
    event_data: Dict[str, Any] = Field(default_factory=dict, description="Event payload data")

    @validator("message", always=True)
    def generate_message_from_event(cls, v, values):
        """Auto-generate message if not provided"""
        if not v or v == "":
            event_type = values.get("event_type", "unknown")
            return f"Event: {event_type}"
        return v


class StateSyncRequest(AgentInteractionBase):
    """State synchronization between agents"""
    interaction_type: Literal["state_sync"] = "state_sync"
    state_key: str = Field(description="State key (e.g., task_1_progress)")
    state_value: Dict[str, Any] = Field(description="Current state value")
    state_version: int = Field(default=1, ge=1, description="Version for optimistic locking")
    previous_state: Optional[Dict[str, Any]] = Field(None, description="Previous state for comparison")


class ConflictReportRequest(AgentInteractionBase):
    """Conflict detection and reporting"""
    interaction_type: Literal["conflict"] = "conflict"
    conflict_type: ConflictType = Field(description="Type of conflict detected")
    conflict_detected: Literal[True] = True
    conflict_resolved: bool = Field(default=False)
    resolution_strategy: Optional[ResolutionStrategy] = Field(None, description="Proposed resolution strategy")
    resolution_data: Optional[Dict[str, Any]] = Field(None, description="Resolution details")


class ResponseRequest(AgentInteractionBase):
    """Response to a previous message"""
    interaction_type: Literal["response"] = "response"
    response: str = Field(description="Response content")

    # In responses, 'message' contains the original message being responded to


# Response models

class AgentInteractionResponse(BaseModel):
    """Response model for created interactions"""
    id: UUID
    execution_id: UUID
    from_agent_id: UUID
    to_agent_id: Optional[UUID]
    interaction_type: InteractionType
    message: str
    response: Optional[str] = None

    # Event fields
    event_type: Optional[EventType] = None
    event_data: Optional[Dict[str, Any]] = None

    # State sync fields
    state_key: Optional[str] = None
    state_value: Optional[Dict[str, Any]] = None
    state_version: Optional[int] = None
    previous_state: Optional[Dict[str, Any]] = None

    # Conflict fields
    conflict_detected: bool = False
    conflict_type: Optional[ConflictType] = None
    conflict_resolved: bool = False
    resolution_strategy: Optional[ResolutionStrategy] = None
    resolution_data: Optional[Dict[str, Any]] = None
    resolved_at: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    requires_response: bool = False
    response_deadline: Optional[datetime] = None
    is_broadcast: bool = Field(default=False, description="True if to_agent_id is null")

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None

    @validator("is_broadcast", pre=True, always=True)
    def compute_is_broadcast(cls, v, values):
        """Compute is_broadcast based on to_agent_id being null"""
        # If value is provided explicitly, use it
        if v is not None:
            return v
        # Otherwise, compute based on to_agent_id
        return values.get("to_agent_id") is None

    class Config:
        from_attributes = True


class ConflictResolutionRequest(BaseModel):
    """Request to resolve a conflict"""
    conflict_id: UUID = Field(description="ID of the conflict interaction")
    resolution_strategy: ResolutionStrategy = Field(description="Strategy to resolve the conflict")
    resolution_data: Optional[Dict[str, Any]] = Field(None, description="Additional resolution data")
    resolved_by_agent_id: Optional[UUID] = Field(None, description="Agent that resolved the conflict")


class StateUpdateRequest(BaseModel):
    """Request to update shared state"""
    execution_id: UUID
    agent_id: UUID
    state_key: str
    state_value: Dict[str, Any]
    expected_version: Optional[int] = Field(None, description="Expected version for optimistic locking")


class MessageThreadResponse(BaseModel):
    """Response model for a thread of related messages"""
    thread_id: str
    execution_id: UUID
    participant_agent_ids: List[UUID]
    messages: List[AgentInteractionResponse]
    total_messages: int
    unresolved_conflicts: int
    pending_responses: int


class ConflictSummaryResponse(BaseModel):
    """Summary of unresolved conflicts"""
    execution_id: UUID
    crew_id: UUID
    total_conflicts: int
    unresolved_conflicts: int
    conflict_types: Dict[ConflictType, int]
    oldest_conflict_age_minutes: Optional[float] = None
    conflicts: List[AgentInteractionResponse]


class PendingResponsesResponse(BaseModel):
    """Summary of pending responses"""
    execution_id: UUID
    total_pending: int
    overdue_count: int
    urgent_count: int  # Due within 5 minutes
    pending_responses: List[AgentInteractionResponse]


class BroadcastMessageResponse(BaseModel):
    """Response when broadcasting a message"""
    broadcast_id: UUID
    execution_id: UUID
    from_agent_id: UUID
    message: str
    total_agents: int
    broadcast_at: datetime


# ==================== Analytics Response Models ====================

class PaginationInfo(BaseModel):
    """Pagination metadata"""
    limit: int
    offset: int
    has_more: bool


class InteractionHistoryResponse(BaseModel):
    """Response for interaction history with pagination"""
    total: int
    interactions: List[AgentInteractionResponse]
    pagination: PaginationInfo


class AgentActivityMetrics(BaseModel):
    """Activity metrics for a single agent"""
    agent_id: UUID
    messages_sent: int
    messages_received: int
    events_published: int
    conflicts_detected: int
    last_activity: Optional[datetime] = None


class AgentActivityResponse(BaseModel):
    """Response for agent activity analytics"""
    execution_id: UUID
    time_window: str
    agents: List[AgentActivityMetrics]


class TimelineDataPoint(BaseModel):
    """Single data point in interaction timeline"""
    timestamp: datetime
    messages: int
    events: int
    state_syncs: int
    conflicts: int


class InteractionTimelineResponse(BaseModel):
    """Response for interaction timeline"""
    execution_id: UUID
    granularity: str
    timeline: List[TimelineDataPoint]


class ConflictAnalyticsResponse(BaseModel):
    """Response for conflict analytics"""
    execution_id: UUID
    total_conflicts: int
    resolved_conflicts: int
    unresolved_conflicts: int
    by_type: Dict[str, int]
    resolution_strategies: Dict[str, int]
    avg_resolution_time_minutes: Optional[float] = None


class MessageFlowNode(BaseModel):
    """Node in message flow graph"""
    agent_id: UUID
    name: str
    message_count: int


class MessageFlowEdge(BaseModel):
    """Edge in message flow graph"""
    from_agent: UUID = Field(alias="from")
    to_agent: UUID = Field(alias="to")
    count: int
    avg_latency_ms: Optional[float] = None

    class Config:
        populate_by_name = True


class MessageFlowResponse(BaseModel):
    """Response for message flow graph"""
    execution_id: UUID
    nodes: List[MessageFlowNode]
    edges: List[MessageFlowEdge]
