"""
Pydantic models for Content Prep Agent (AGENT-016).

Feature: 007-content-prep-agent
Purpose: API request/response models for content set detection and processing manifests.
"""

from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Request Models
# ============================================================================


class AnalyzeRequest(BaseModel):
    """Request to analyze pending files for content sets."""

    b2_folder: str = Field(..., description="B2 folder path to analyze")
    detection_mode: str = Field(
        default="auto",
        description="Detection mode: auto, pattern, metadata, llm",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "b2_folder": "pending/courses/",
                "detection_mode": "auto",
            }
        }


class ManifestRequest(BaseModel):
    """Request to generate processing manifest for a content set."""

    content_set_id: str = Field(..., description="UUID of the content set")
    proceed_incomplete: bool = Field(
        default=False,
        description="Process even if content set is incomplete (requires acknowledgment)",
    )
    add_context: bool = Field(
        default=True,
        description="Include set context in processing for downstream agents",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content_set_id": "cs-uuid-1234",
                "proceed_incomplete": False,
                "add_context": True,
            }
        }


class ValidateRequest(BaseModel):
    """Request to validate content set completeness."""

    proceed_anyway: bool = Field(
        default=False,
        description="Acknowledge and proceed despite incomplete set",
    )


# ============================================================================
# Response Models - Files
# ============================================================================


class ContentFileResponse(BaseModel):
    """Response model for a single file in a content set."""

    filename: str
    sequence: Optional[int] = None
    b2_path: str
    detection_pattern: Optional[str] = None
    estimated_complexity: str = "medium"
    file_type: Optional[str] = None
    size_bytes: int = 0

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "module-01-introduction.pdf",
                "sequence": 1,
                "b2_path": "pending/courses/module-01-introduction.pdf",
                "detection_pattern": "module",
                "estimated_complexity": "medium",
                "file_type": "pdf",
                "size_bytes": 1024000,
            }
        }


class OrderedFileResponse(BaseModel):
    """Response model for ordered file in manifest."""

    sequence: int
    file: str
    b2_path: str
    dependencies: list[str] = Field(default_factory=list)
    complexity: str = "medium"

    class Config:
        json_schema_extra = {
            "example": {
                "sequence": 1,
                "file": "module-01-introduction.pdf",
                "b2_path": "pending/courses/module-01-introduction.pdf",
                "dependencies": [],
                "complexity": "medium",
            }
        }


# ============================================================================
# Response Models - Content Sets
# ============================================================================


class ContentSetResponse(BaseModel):
    """Response model for a content set."""

    id: str
    name: str
    detection_method: str
    files_count: int
    files: list[ContentFileResponse]
    is_complete: bool
    missing_files: list[str] = Field(default_factory=list)
    processing_status: str = "pending"
    confidence: float = 0.0

    class Config:
        json_schema_extra = {
            "example": {
                "id": "cs-uuid-1234",
                "name": "Python Fundamentals Course",
                "detection_method": "pattern",
                "files_count": 12,
                "files": [],
                "is_complete": False,
                "missing_files": ["module-07-exceptions.pdf"],
                "processing_status": "pending",
                "confidence": 0.95,
            }
        }


class ContentSetSummary(BaseModel):
    """Summary response for a content set (without full file list)."""

    id: str
    name: str
    detection_method: str
    files_count: int
    is_complete: bool
    missing_files: list[str] = Field(default_factory=list)
    processing_status: str
    confidence: float

    class Config:
        json_schema_extra = {
            "example": {
                "id": "cs-uuid-1234",
                "name": "Python Fundamentals Course",
                "detection_method": "pattern",
                "files_count": 12,
                "is_complete": False,
                "missing_files": ["module-07-exceptions.pdf"],
                "processing_status": "pending",
                "confidence": 0.95,
            }
        }


# ============================================================================
# Response Models - Analysis
# ============================================================================


class StandaloneFileResponse(BaseModel):
    """Response model for a standalone file (not part of a set)."""

    filename: str
    path: str
    file_type: Optional[str] = None
    size_bytes: int = 0


class AnalyzeResponse(BaseModel):
    """Response from folder analysis."""

    content_sets: list[ContentSetSummary]
    standalone_files: list[StandaloneFileResponse]
    analysis_time_ms: int = 0

    class Config:
        json_schema_extra = {
            "example": {
                "content_sets": [
                    {
                        "id": "cs-uuid-1234",
                        "name": "Python Fundamentals Course",
                        "detection_method": "pattern",
                        "files_count": 12,
                        "is_complete": False,
                        "missing_files": ["module-07-exceptions.pdf"],
                        "processing_status": "pending",
                        "confidence": 0.95,
                    }
                ],
                "standalone_files": [
                    {"filename": "random-notes.pdf", "path": "pending/random-notes.pdf"}
                ],
                "analysis_time_ms": 150,
            }
        }


# ============================================================================
# Response Models - Manifest
# ============================================================================


class ManifestResponse(BaseModel):
    """Response model for processing manifest."""

    manifest_id: str
    content_set_id: str
    content_set_name: str
    ordered_files: list[OrderedFileResponse]
    total_files: int
    warnings: list[str] = Field(default_factory=list)
    estimated_time_seconds: int
    created_at: datetime
    context: dict = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "manifest_id": "manifest-uuid-5678",
                "content_set_id": "cs-uuid-1234",
                "content_set_name": "Python Fundamentals Course",
                "ordered_files": [],
                "total_files": 12,
                "warnings": ["Missing: module-07-exceptions.pdf"],
                "estimated_time_seconds": 480,
                "created_at": "2026-01-13T12:00:00Z",
                "context": {"set_name": "Python Fundamentals Course", "is_sequential": True},
            }
        }


# ============================================================================
# Response Models - Validation
# ============================================================================


class ValidateResponse(BaseModel):
    """Response from content set validation."""

    set_id: str
    is_complete: bool
    missing_files: list[str] = Field(default_factory=list)
    total_files: int
    gaps_detected: int = 0
    can_proceed: bool = True
    requires_acknowledgment: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "set_id": "cs-uuid-1234",
                "is_complete": False,
                "missing_files": ["#7 (between module-06 and module-08)"],
                "total_files": 11,
                "gaps_detected": 1,
                "can_proceed": True,
                "requires_acknowledgment": True,
            }
        }


# ============================================================================
# Health Check
# ============================================================================


class AgentInfo(BaseModel):
    """Agent identification and status information."""

    agent_id: str = "AGENT-016"
    name: str = "Content Prep Agent"
    version: str = "1.0.0"
    uptime_seconds: int = 0
    llm_available: bool = False


class ProcessingMetrics(BaseModel):
    """Processing metrics for the agent."""

    recent_error_count: int = 0
    pending_content_sets: int = 0
    active_processing_count: int = 0
    total_processed_24h: int = 0


class ConnectivityStatus(BaseModel):
    """Connectivity status for external services."""

    supabase: bool = True
    neo4j: bool = True
    b2_storage: bool = True


class HealthResponse(BaseModel):
    """Comprehensive health check response for Content Prep Agent."""

    status: str = Field(
        default="healthy",
        description="Overall health status: healthy, degraded, or unhealthy"
    )
    agent: AgentInfo = Field(default_factory=AgentInfo)
    metrics: ProcessingMetrics = Field(default_factory=ProcessingMetrics)
    connectivity: ConnectivityStatus = Field(default_factory=ConnectivityStatus)
    capabilities: Dict[str, bool] = Field(
        default_factory=lambda: {
            "content_set_detection": True,
            "ordering_analysis": True,
            "ordering_clarification": True,
            "manifest_generation": True,
            "llm_powered": False,
        }
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "agent": {
                    "agent_id": "AGENT-016",
                    "name": "Content Prep Agent",
                    "version": "1.0.0",
                    "uptime_seconds": 3600,
                    "llm_available": True
                },
                "metrics": {
                    "recent_error_count": 2,
                    "pending_content_sets": 5,
                    "active_processing_count": 1,
                    "total_processed_24h": 15
                },
                "connectivity": {
                    "supabase": True,
                    "neo4j": True,
                    "b2_storage": True
                },
                "capabilities": {
                    "content_set_detection": True,
                    "ordering_analysis": True,
                    "ordering_clarification": True,
                    "manifest_generation": True,
                    "llm_powered": True
                }
            }
        }
    }
