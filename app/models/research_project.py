"""
Empire v7.3 - Research Project Models
Pydantic models for the Research Projects (Agent Harness) feature.
"""

from typing import Optional, List, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


# ==============================================================================
# Enums
# ==============================================================================

class ResearchType(str, Enum):
    """Type of research project"""
    GENERAL = "general"
    COMPLIANCE = "compliance"
    COMPETITIVE = "competitive"
    TECHNICAL = "technical"
    FINANCIAL = "financial"


class JobStatus(str, Enum):
    """Research job lifecycle status"""
    INITIALIZING = "initializing"
    PLANNING = "planning"
    PLANNED = "planned"
    EXECUTING = "executing"
    SYNTHESIZING = "synthesizing"
    GENERATING_REPORT = "generating_report"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Type of research task"""
    RETRIEVAL_RAG = "retrieval_rag"
    RETRIEVAL_NLQ = "retrieval_nlq"
    RETRIEVAL_GRAPH = "retrieval_graph"
    RETRIEVAL_API = "retrieval_api"
    SYNTHESIS = "synthesis"
    FACT_CHECK = "fact_check"
    WRITE_SECTION = "write_section"
    WRITE_REPORT = "write_report"
    REVIEW = "review"


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ArtifactType(str, Enum):
    """Type of research artifact"""
    RETRIEVED_CHUNK = "retrieved_chunk"
    QUERY_RESULT = "query_result"
    GRAPH_PATH = "graph_path"
    API_RESPONSE = "api_response"
    SYNTHESIS_FINDING = "synthesis_finding"
    FACT_CHECK_RESULT = "fact_check_result"
    REPORT_SECTION = "report_section"
    FINAL_REPORT = "final_report"


# ==============================================================================
# Request Models
# ==============================================================================

class CreateResearchProjectRequest(BaseModel):
    """Request to create a new research project"""
    query: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="The research query to investigate"
    )
    context: Optional[str] = Field(
        None,
        max_length=5000,
        description="Additional context or constraints for the research"
    )
    research_type: ResearchType = Field(
        default=ResearchType.GENERAL,
        description="Type of research to conduct"
    )
    notify_email: str = Field(
        ...,
        description="Email address for notifications"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "Analyze all vendor contracts for renewal terms and pricing",
                "context": "Focus on contracts expiring in the next 6 months",
                "research_type": "compliance",
                "notify_email": "user@example.com"
            }
        }
    )


class CreateShareRequest(BaseModel):
    """Request to create a shareable link"""
    expires_in_days: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Number of days until link expires (null = never)"
    )


# ==============================================================================
# Response Models - Tasks
# ==============================================================================

class TaskResponse(BaseModel):
    """Individual task within a research project"""
    id: int
    task_key: str
    task_type: TaskType
    task_title: Optional[str] = None
    task_description: Optional[str] = None
    status: TaskStatus
    sequence_order: int
    depends_on: Optional[List[str]] = None
    result_summary: Optional[str] = None
    artifacts_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    error_message: Optional[str] = None


# ==============================================================================
# Response Models - Artifacts
# ==============================================================================

class ArtifactResponse(BaseModel):
    """Research artifact from task execution"""
    id: int
    artifact_type: ArtifactType
    source: Optional[str] = None
    source_type: Optional[str] = None
    processed_content: Optional[str] = None
    relevance_score: Optional[float] = None
    confidence_score: Optional[float] = None
    created_at: datetime


class FindingsResponse(BaseModel):
    """Partial findings grouped by task type"""
    job_id: int
    status: JobStatus
    progress_percentage: float
    completed_findings: List[dict] = Field(
        default_factory=list,
        description="Findings grouped by completed task"
    )


# ==============================================================================
# Response Models - Shares
# ==============================================================================

class ShareResponse(BaseModel):
    """Shareable link for a research report"""
    id: int
    share_token: str
    share_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    view_count: int = 0
    last_viewed_at: Optional[datetime] = None


class PublicReportResponse(BaseModel):
    """Public report accessed via share token"""
    job_id: int
    query: str
    research_type: ResearchType
    completed_at: Optional[datetime] = None
    summary: Optional[str] = None
    key_findings: Optional[List[dict]] = None
    report_content: Optional[str] = None
    report_url: Optional[str] = None


# ==============================================================================
# Response Models - Projects
# ==============================================================================

class ResearchProjectSummary(BaseModel):
    """Summary view of a research project for listing"""
    id: int
    query: str
    research_type: ResearchType
    status: JobStatus
    progress_percentage: float
    total_tasks: int
    completed_tasks: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class ResearchProjectDetail(BaseModel):
    """Detailed view of a research project"""
    id: int
    query: str
    context: Optional[str] = None
    research_type: ResearchType
    status: JobStatus
    progress_percentage: float
    total_tasks: int
    completed_tasks: int
    current_task_key: Optional[str] = None
    tasks: List[TaskResponse] = Field(default_factory=list)
    summary: Optional[str] = None
    key_findings: Optional[List[dict]] = None
    report_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ProjectStatusResponse(BaseModel):
    """Lightweight status response for polling"""
    id: int
    status: JobStatus
    progress_percentage: float
    total_tasks: int
    completed_tasks: int
    current_task_key: Optional[str] = None
    error_message: Optional[str] = None


class ReportResponse(BaseModel):
    """Final research report"""
    id: int
    status: JobStatus
    summary: Optional[str] = None
    key_findings: Optional[List[dict]] = None
    report_content: Optional[str] = None
    report_url: Optional[str] = None
    completed_at: Optional[datetime] = None


# ==============================================================================
# API Response Wrappers
# ==============================================================================

class CreateProjectResponse(BaseModel):
    """Response after creating a project"""
    success: bool = True
    job_id: int
    status: JobStatus
    estimated_tasks: Optional[int] = None
    message: str = "Research project created successfully"


class ListProjectsResponse(BaseModel):
    """Response for listing projects"""
    success: bool = True
    projects: List[ResearchProjectSummary]
    total: int
    page: int = 1
    page_size: int = 20


class CancelProjectResponse(BaseModel):
    """Response after cancelling a project"""
    success: bool = True
    job_id: int
    status: JobStatus = JobStatus.CANCELLED
    message: str = "Project cancelled successfully"


class CreateShareResponse(BaseModel):
    """Response after creating a share link"""
    success: bool = True
    share: ShareResponse
    message: str = "Share link created successfully"


class ListSharesResponse(BaseModel):
    """Response for listing share links"""
    success: bool = True
    shares: List[ShareResponse]
    total: int


class RevokeShareResponse(BaseModel):
    """Response after revoking a share link"""
    success: bool = True
    share_id: int
    message: str = "Share link revoked successfully"


# ==============================================================================
# WebSocket Models
# ==============================================================================

class WebSocketMessage(BaseModel):
    """WebSocket message for real-time updates"""
    type: str = Field(..., description="Message type: project_status, task_started, task_completed, task_failed, project_complete")
    job_id: int
    data: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
