"""
Empire v7.3 - Agent Router Models (Task 17)
Pydantic models for intelligent agent routing between LangGraph, CrewAI, and Simple RAG

Author: Claude Code
Date: 2025-01-25
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from uuid import UUID
from enum import Enum


class AgentType(str, Enum):
    """Supported agent/workflow types for routing."""
    LANGGRAPH = "langgraph"    # Adaptive queries needing refinement, external data
    CREWAI = "crewai"          # Multi-agent document processing workflows
    SIMPLE = "simple"          # Direct RAG pipeline for factual lookups


class QueryCategory(str, Enum):
    """Categories for query classification."""
    DOCUMENT_LOOKUP = "document_lookup"      # Direct factual lookup from docs
    DOCUMENT_ANALYSIS = "document_analysis"  # Multi-doc analysis/comparison
    RESEARCH = "research"                    # Needs external data/web search
    CONVERSATIONAL = "conversational"        # General chat/follow-up
    MULTI_STEP = "multi_step"               # Complex multi-step reasoning
    ENTITY_EXTRACTION = "entity_extraction"  # Extract structured data from docs


class RoutingConfidence(str, Enum):
    """Confidence levels for routing decisions."""
    HIGH = "high"       # >= 0.8
    MEDIUM = "medium"   # 0.5 - 0.8
    LOW = "low"         # < 0.5


# ==================== Request Models ====================

class AgentRouterRequest(BaseModel):
    """Request model for agent routing API."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="User query to route to appropriate agent"
    )
    user_id: Optional[str] = Field(
        None,
        description="User ID for personalized routing"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for context-aware routing"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional context for routing decision"
    )
    force_agent: Optional[AgentType] = Field(
        None,
        description="Force routing to specific agent (bypasses classification)"
    )
    include_reasoning: bool = Field(
        True,
        description="Include detailed reasoning in response"
    )

    @validator('query')
    def query_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty or whitespace only')
        return v.strip()


class BatchRouterRequest(BaseModel):
    """Request for batch routing multiple queries."""
    queries: List[str] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="List of queries to route"
    )
    user_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


# ==================== Response Models ====================

class ClassificationDetail(BaseModel):
    """Detailed classification information."""
    category: QueryCategory = Field(
        description="Classified query category"
    )
    category_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in category classification"
    )
    features_detected: List[str] = Field(
        default_factory=list,
        description="Features detected in the query (e.g., 'multi_document', 'external_data_needed')"
    )
    query_complexity: Literal["simple", "moderate", "complex"] = Field(
        "moderate",
        description="Estimated complexity of the query"
    )


class AgentRouterResponse(BaseModel):
    """Response model for agent routing API."""
    query: str = Field(description="Original query")
    selected_agent: AgentType = Field(description="Selected agent type")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Overall routing confidence score"
    )
    confidence_level: RoutingConfidence = Field(
        description="Categorical confidence level"
    )
    reasoning: Optional[str] = Field(
        None,
        description="Explanation for routing decision"
    )
    classification: Optional[ClassificationDetail] = Field(
        None,
        description="Detailed classification information"
    )
    suggested_tools: List[str] = Field(
        default_factory=list,
        description="Recommended tools for this query"
    )
    estimated_processing_time_ms: Optional[int] = Field(
        None,
        description="Estimated processing time in milliseconds"
    )
    from_cache: bool = Field(
        False,
        description="Whether result was served from cache"
    )
    routing_time_ms: int = Field(
        description="Time taken for routing decision in milliseconds"
    )
    request_id: Optional[str] = Field(
        None,
        description="Unique request identifier for tracking"
    )

    @validator('confidence_level', pre=True, always=True)
    def set_confidence_level(cls, v, values):
        if v is not None:
            return v
        confidence = values.get('confidence', 0.5)
        if confidence >= 0.8:
            return RoutingConfidence.HIGH
        elif confidence >= 0.5:
            return RoutingConfidence.MEDIUM
        return RoutingConfidence.LOW


class BatchRouterResponse(BaseModel):
    """Response for batch routing requests."""
    results: List[AgentRouterResponse]
    total_queries: int
    processing_time_ms: int
    cache_hits: int = 0


# ==================== Cache Models ====================

class RouterCacheEntry(BaseModel):
    """Model for router cache entries (for Redis/Supabase storage)."""
    query_hash: str = Field(description="SHA-256 hash of normalized query")
    query_text: str = Field(description="Original query text")
    selected_agent: AgentType
    confidence: float
    classification: Optional[ClassificationDetail] = None
    reasoning: Optional[str] = None
    suggested_tools: List[str] = Field(default_factory=list)
    hit_count: int = Field(default=1, description="Number of cache hits")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(
        None,
        description="Cache expiration time"
    )
    user_feedback_score: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Aggregated user feedback on routing accuracy"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = self.dict()
        # Convert enums to values
        data['selected_agent'] = self.selected_agent.value
        if self.classification:
            data['classification']['category'] = self.classification.category.value
        # Convert datetimes to ISO strings
        data['created_at'] = self.created_at.isoformat()
        data['last_accessed_at'] = self.last_accessed_at.isoformat()
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RouterCacheEntry":
        """Create from dictionary."""
        # Convert string values back to enums
        if isinstance(data.get('selected_agent'), str):
            data['selected_agent'] = AgentType(data['selected_agent'])
        if data.get('classification') and isinstance(data['classification'].get('category'), str):
            data['classification']['category'] = QueryCategory(data['classification']['category'])
        # Convert ISO strings back to datetimes
        for field in ['created_at', 'last_accessed_at', 'expires_at']:
            if data.get(field) and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
        return cls(**data)


# ==================== Decision History Models ====================

class RoutingDecision(BaseModel):
    """Model for tracking routing decisions (for analytics and learning)."""
    id: Optional[UUID] = None
    query_hash: str
    query_text: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    selected_agent: AgentType
    confidence: float
    classification_category: Optional[QueryCategory] = None
    reasoning: Optional[str] = None

    # Outcome tracking
    was_successful: Optional[bool] = None
    user_feedback: Optional[Literal["positive", "negative", "neutral"]] = None
    actual_processing_time_ms: Optional[int] = None
    fallback_used: bool = Field(default=False, description="Whether fallback agent was used")
    fallback_agent: Optional[AgentType] = None

    # Request metadata
    request_context: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = self.dict()
        # Convert enums
        data['selected_agent'] = self.selected_agent.value
        if self.classification_category:
            data['classification_category'] = self.classification_category.value
        if self.fallback_agent:
            data['fallback_agent'] = self.fallback_agent.value
        # Convert timestamps
        data['created_at'] = self.created_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data


# ==================== Analytics Models ====================

class RoutingMetrics(BaseModel):
    """Aggregated routing metrics for monitoring."""
    time_period: str = Field(description="Time period (e.g., '1h', '24h', '7d')")
    total_requests: int
    cache_hit_rate: float = Field(ge=0.0, le=1.0)
    avg_routing_time_ms: float

    # By agent distribution
    langgraph_count: int = 0
    crewai_count: int = 0
    simple_count: int = 0

    # By confidence level
    high_confidence_count: int = 0
    medium_confidence_count: int = 0
    low_confidence_count: int = 0

    # Success metrics
    success_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    fallback_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    positive_feedback_rate: Optional[float] = Field(None, ge=0.0, le=1.0)


class AgentPerformanceMetrics(BaseModel):
    """Performance metrics for a specific agent type."""
    agent_type: AgentType
    total_requests: int
    avg_processing_time_ms: float
    success_rate: float = Field(ge=0.0, le=1.0)
    avg_confidence: float = Field(ge=0.0, le=1.0)
    positive_feedback_rate: Optional[float] = None


class RoutingAnalyticsResponse(BaseModel):
    """Response for routing analytics endpoint."""
    metrics: RoutingMetrics
    agent_performance: List[AgentPerformanceMetrics]
    top_queries: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Most frequently routed queries"
    )
    recent_fallbacks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Recent routing failures/fallbacks"
    )


# ==================== Feedback Models ====================

class RoutingFeedbackRequest(BaseModel):
    """Request to provide feedback on a routing decision."""
    request_id: str = Field(description="Request ID from routing response")
    feedback: Literal["positive", "negative", "neutral"]
    comment: Optional[str] = Field(None, max_length=1000)
    correct_agent: Optional[AgentType] = Field(
        None,
        description="If negative, what agent should have been used"
    )


class RoutingFeedbackResponse(BaseModel):
    """Response after submitting routing feedback."""
    success: bool
    message: str
    feedback_id: Optional[str] = None
