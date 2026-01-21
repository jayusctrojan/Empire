"""
Pydantic models for Master Orchestrator API (AGENT-001).

Feature: Task 133 - Orchestrator API Routes
Endpoints: /api/orchestrator/*

AGENT-001: Master Content Analyzer & Asset Orchestrator
- Analyzes content for department classification (12 departments)
- Selects appropriate asset types (skill/command/agent/prompt/workflow)
- Determines summary requirements
- Delegates to specialized agents
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================


class AgentType(str, Enum):
    """Agent types available in the system."""
    ORCHESTRATOR = "orchestrator"
    CONTENT_PREP = "content_prep"
    SUMMARIZER = "summarizer"
    CLASSIFIER = "classifier"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    WRITING = "writing"
    REVIEW = "review"
    GRAPH = "graph"


class AgentStatus(str, Enum):
    """Agent operational status."""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    DEGRADED = "degraded"


class Department(str, Enum):
    """12 business departments for content classification."""
    IT_ENGINEERING = "it-engineering"
    SALES_MARKETING = "sales-marketing"
    CUSTOMER_SUPPORT = "customer-support"
    OPERATIONS_HR_SUPPLY = "operations-hr-supply"
    FINANCE_ACCOUNTING = "finance-accounting"
    PROJECT_MANAGEMENT = "project-management"
    REAL_ESTATE = "real-estate"
    PRIVATE_EQUITY_MA = "private-equity-ma"
    CONSULTING = "consulting"
    PERSONAL_CONTINUING_ED = "personal-continuing-ed"
    GLOBAL = "_global"
    RESEARCH_DEVELOPMENT = "research-development"


class AssetType(str, Enum):
    """Asset types that can be generated."""
    SKILL = "skill"
    COMMAND = "command"
    AGENT = "agent"
    PROMPT = "prompt"
    WORKFLOW = "workflow"


# ============================================================================
# Request Models
# ============================================================================


class OrchestrationRequest(BaseModel):
    """Request to orchestrate content processing."""
    content: str = Field(
        ...,
        min_length=10,
        description="Content to analyze and process"
    )
    filename: Optional[str] = Field(
        None,
        description="Optional filename for content type hints"
    )
    user_id: Optional[str] = Field(
        None,
        description="User ID for tracking"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional additional metadata"
    )
    force_llm: bool = Field(
        False,
        description="Force LLM classification even for high-confidence keyword matches"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Advanced Sales Pipeline Management Framework...",
                "filename": "sales_pipeline_guide.pdf",
                "user_id": "user-123",
                "metadata": {"source": "upload"},
                "force_llm": False
            }
        }


class ClassificationRequest(BaseModel):
    """Request to classify content into a department."""
    content: str = Field(
        ...,
        min_length=10,
        description="Content to classify"
    )
    filename: Optional[str] = Field(
        None,
        description="Optional filename for hints"
    )
    force_llm: bool = Field(
        False,
        description="Force LLM enhancement even for high-confidence results"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Quarterly financial report with revenue analysis...",
                "filename": "q3_financials.pdf",
                "force_llm": False
            }
        }


class AnalyzeContentRequest(BaseModel):
    """Request to analyze content patterns."""
    content: str = Field(
        ...,
        min_length=10,
        description="Content to analyze"
    )
    filename: Optional[str] = Field(
        None,
        description="Optional filename for type detection"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content": "def calculate_revenue():\n    return sum(sales)",
                "filename": "revenue_calc.py"
            }
        }


class AgentListRequest(BaseModel):
    """Request to filter agent list."""
    agent_type: Optional[AgentType] = Field(
        None,
        description="Filter by agent type"
    )
    status: Optional[AgentStatus] = Field(
        None,
        description="Filter by status"
    )


# ============================================================================
# Response Models - Classification
# ============================================================================


class ClassificationResult(BaseModel):
    """Result of department classification."""
    department: Department
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    keywords_matched: List[str] = Field(default_factory=list)
    secondary_department: Optional[Department] = None
    secondary_confidence: float = 0.0

    class Config:
        json_schema_extra = {
            "example": {
                "department": "sales-marketing",
                "confidence": 0.92,
                "reasoning": "High match with sales keywords",
                "keywords_matched": ["sales", "pipeline", "crm", "lead"],
                "secondary_department": "project-management",
                "secondary_confidence": 0.45
            }
        }


# ============================================================================
# Response Models - Asset Decision
# ============================================================================


class AssetDecision(BaseModel):
    """Decision on which assets to generate."""
    asset_types: List[AssetType]
    primary_type: AssetType
    reasoning: str
    needs_summary: bool = False
    summary_reasoning: str = ""

    class Config:
        json_schema_extra = {
            "example": {
                "asset_types": ["prompt", "skill"],
                "primary_type": "prompt",
                "reasoning": "Content matches template patterns",
                "needs_summary": True,
                "summary_reasoning": "Long document (5000 words)"
            }
        }


# ============================================================================
# Response Models - Content Analysis
# ============================================================================


class ContentAnalysisResult(BaseModel):
    """Content analysis metadata."""
    word_count: int
    char_count: int
    has_code: bool
    has_tables: bool
    has_structured_data: bool
    complexity_score: float = Field(ge=0.0, le=1.0)
    privacy_level: str  # "local_only" or "cloud_eligible"
    content_type: str   # "document", "video", "code", etc.

    class Config:
        json_schema_extra = {
            "example": {
                "word_count": 2500,
                "char_count": 15000,
                "has_code": False,
                "has_tables": True,
                "has_structured_data": False,
                "complexity_score": 0.65,
                "privacy_level": "cloud_eligible",
                "content_type": "document"
            }
        }


# ============================================================================
# Response Models - Orchestration
# ============================================================================


class OrchestrationResponse(BaseModel):
    """Complete orchestration result from AGENT-001."""
    classification: ClassificationResult
    asset_decision: AssetDecision
    delegation_targets: List[str] = Field(default_factory=list)
    output_paths: Dict[str, str] = Field(default_factory=dict)
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "classification": {
                    "department": "sales-marketing",
                    "confidence": 0.92,
                    "reasoning": "High match with sales keywords",
                    "keywords_matched": ["sales", "pipeline"]
                },
                "asset_decision": {
                    "asset_types": ["prompt"],
                    "primary_type": "prompt",
                    "reasoning": "Template content detected",
                    "needs_summary": True,
                    "summary_reasoning": "Long document"
                },
                "delegation_targets": ["Content Summarizer Agent", "Prompt Generator Agent"],
                "output_paths": {
                    "summary": "processed/crewai-summaries/sales-marketing/...",
                    "prompt": "processed/crewai-suggestions/prompts/drafts/..."
                },
                "processing_metadata": {
                    "processing_time_seconds": 1.25,
                    "agent_id": "AGENT-001"
                }
            }
        }


# ============================================================================
# Response Models - Agent Info
# ============================================================================


class AgentInfo(BaseModel):
    """Information about a registered agent."""
    agent_id: str
    name: str
    agent_type: AgentType
    status: AgentStatus
    capabilities: List[str]
    description: Optional[str] = None
    model: Optional[str] = None
    version: str = "1.0.0"

    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "AGENT-001",
                "name": "Master Content Analyzer & Asset Orchestrator",
                "agent_type": "orchestrator",
                "status": "available",
                "capabilities": [
                    "content_classification",
                    "asset_type_selection",
                    "delegation",
                    "summary_determination"
                ],
                "description": "Main orchestrator for content analysis",
                "model": "claude-sonnet-4-5-20250514",
                "version": "1.0.0"
            }
        }


# ============================================================================
# Response Models - Health & Stats
# ============================================================================


class DependencyStatus(BaseModel):
    """Status of a service dependency."""
    name: str
    status: str
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class HealthStatus(BaseModel):
    """Health status for the orchestrator."""
    status: str = Field(
        default="healthy",
        description="Overall health: healthy, degraded, unhealthy"
    )
    agent_id: str = "AGENT-001"
    agent_name: str = "Master Content Analyzer & Asset Orchestrator"
    version: str = "1.0.0"
    llm_available: bool = False
    dependencies: Dict[str, str] = Field(default_factory=dict)
    capabilities: Dict[str, bool] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "agent_id": "AGENT-001",
                "agent_name": "Master Content Analyzer & Asset Orchestrator",
                "version": "1.0.0",
                "llm_available": True,
                "dependencies": {
                    "anthropic_api": "healthy",
                    "supabase": "healthy"
                },
                "capabilities": {
                    "department_classification": True,
                    "asset_type_selection": True,
                    "llm_enhanced_classification": True,
                    "content_analysis": True
                }
            }
        }


class StatsResponse(BaseModel):
    """Statistics for the orchestrator."""
    agent_id: str = "AGENT-001"
    agent_name: str = "Master Content Analyzer & Asset Orchestrator"
    total_processed: int = 0
    by_department: Dict[str, int] = Field(default_factory=dict)
    by_asset_type: Dict[str, int] = Field(default_factory=dict)
    average_confidence: float = 0.0
    summaries_generated: int = 0
    average_processing_time_ms: float = 0.0

    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "AGENT-001",
                "agent_name": "Master Content Analyzer & Asset Orchestrator",
                "total_processed": 150,
                "by_department": {
                    "sales-marketing": 45,
                    "it-engineering": 38,
                    "finance-accounting": 22
                },
                "by_asset_type": {
                    "prompt": 80,
                    "skill": 45,
                    "workflow": 25
                },
                "average_confidence": 0.87,
                "summaries_generated": 95,
                "average_processing_time_ms": 1250.5
            }
        }


# ============================================================================
# Response Models - Agent Registry
# ============================================================================


class AgentRegistryResponse(BaseModel):
    """Response for listing all registered agents."""
    total_agents: int
    agents: List[AgentInfo]
    by_status: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "total_agents": 15,
                "agents": [],
                "by_status": {
                    "available": 14,
                    "busy": 1,
                    "offline": 0
                },
                "by_type": {
                    "orchestrator": 1,
                    "research": 2,
                    "analysis": 2
                }
            }
        }
