"""
API Routes for Master Orchestrator (AGENT-001).

Feature: Task 133 - Orchestrator API Routes
Endpoints: /api/orchestrator/*

AGENT-001: Master Content Analyzer & Asset Orchestrator
- POST /api/orchestrator/coordinate - Main orchestration endpoint
- POST /api/orchestrator/classify - Department classification only
- POST /api/orchestrator/analyze - Content analysis only
- GET /api/orchestrator/agents - List all registered agents
- GET /api/orchestrator/agents/{agent_id} - Get specific agent info
- GET /api/orchestrator/health - Health check
- GET /api/orchestrator/stats - Statistics
"""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
import structlog

from app.models.orchestrator import (
    OrchestrationRequest,
    OrchestrationResponse,
    ClassificationRequest,
    ClassificationResult,
    AnalyzeContentRequest,
    ContentAnalysisResult,
    AgentInfo,
    AgentRegistryResponse,
    HealthStatus,
    StatsResponse,
    AgentType,
    AgentStatus,
    Department,
    AssetType,
    AssetDecision,
)
from app.services.orchestrator_agent_service import (
    OrchestratorAgentService,
    create_orchestrator_agent,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])


# ============================================================================
# Service Dependencies
# ============================================================================


_orchestrator_service: Optional[OrchestratorAgentService] = None


def get_orchestrator_service() -> OrchestratorAgentService:
    """Get or create the orchestrator service instance."""
    global _orchestrator_service
    if _orchestrator_service is None:
        _orchestrator_service = create_orchestrator_agent()
    return _orchestrator_service


# ============================================================================
# Agent Registry (in-memory for now, could be moved to database)
# ============================================================================


def _get_all_agents() -> List[AgentInfo]:
    """Get information about all registered agents in the system."""
    agents = [
        AgentInfo(
            agent_id="AGENT-001",
            name="Master Content Analyzer & Asset Orchestrator",
            agent_type=AgentType.ORCHESTRATOR,
            status=AgentStatus.AVAILABLE,
            capabilities=[
                "content_classification",
                "asset_type_selection",
                "delegation",
                "summary_determination",
                "pattern_analysis"
            ],
            description="Main orchestrator for content analysis and routing",
            model="claude-sonnet-4-5-20250929",
            version="1.0.0"
        ),
        AgentInfo(
            agent_id="AGENT-002",
            name="Content Summarizer",
            agent_type=AgentType.SUMMARIZER,
            status=AgentStatus.AVAILABLE,
            capabilities=[
                "pdf_summarization",
                "key_points_extraction",
                "executive_summary"
            ],
            description="PDF summary generation with key points",
            model="claude-sonnet-4-5-20250929",
            version="1.0.0"
        ),
        AgentInfo(
            agent_id="AGENT-008",
            name="Department Classifier",
            agent_type=AgentType.CLASSIFIER,
            status=AgentStatus.AVAILABLE,
            capabilities=[
                "department_classification",
                "confidence_scoring",
                "multi_label_support"
            ],
            description="10-department content classification",
            model="claude-sonnet-4-5-20250929",
            version="1.0.0"
        ),
        AgentInfo(
            agent_id="AGENT-009",
            name="Senior Research Analyst",
            agent_type=AgentType.RESEARCH,
            status=AgentStatus.AVAILABLE,
            capabilities=[
                "topic_extraction",
                "entity_extraction",
                "fact_extraction",
                "quality_assessment"
            ],
            description="Document research and analysis",
            model="claude-sonnet-4-5-20250929",
            version="1.0.0"
        ),
        AgentInfo(
            agent_id="AGENT-010",
            name="Content Strategist",
            agent_type=AgentType.ANALYSIS,
            status=AgentStatus.AVAILABLE,
            capabilities=[
                "executive_summary",
                "findings_synthesis",
                "recommendations"
            ],
            description="Strategy and recommendations",
            model="claude-sonnet-4-5-20250929",
            version="1.0.0"
        ),
        AgentInfo(
            agent_id="AGENT-011",
            name="Fact Checker",
            agent_type=AgentType.ANALYSIS,
            status=AgentStatus.AVAILABLE,
            capabilities=[
                "claim_verification",
                "confidence_scoring",
                "citation_provision"
            ],
            description="Fact verification and validation",
            model="claude-sonnet-4-5-20250929",
            version="1.0.0"
        ),
        AgentInfo(
            agent_id="AGENT-012",
            name="Research Agent",
            agent_type=AgentType.RESEARCH,
            status=AgentStatus.AVAILABLE,
            capabilities=[
                "web_search",
                "academic_search",
                "query_expansion",
                "source_credibility"
            ],
            description="Web/academic search and information gathering",
            model="claude-sonnet-4-5-20250929",
            version="1.0.0"
        ),
        AgentInfo(
            agent_id="AGENT-013",
            name="Analysis Agent",
            agent_type=AgentType.ANALYSIS,
            status=AgentStatus.AVAILABLE,
            capabilities=[
                "pattern_detection",
                "statistical_analysis",
                "correlation_finding"
            ],
            description="Pattern detection and statistical analysis",
            model="claude-sonnet-4-5-20250929",
            version="1.0.0"
        ),
        AgentInfo(
            agent_id="AGENT-014",
            name="Writing Agent",
            agent_type=AgentType.WRITING,
            status=AgentStatus.AVAILABLE,
            capabilities=[
                "report_generation",
                "multi_format_output",
                "citation_management"
            ],
            description="Report generation and documentation",
            model="claude-sonnet-4-5-20250929",
            version="1.0.0"
        ),
        AgentInfo(
            agent_id="AGENT-015",
            name="Review Agent",
            agent_type=AgentType.REVIEW,
            status=AgentStatus.AVAILABLE,
            capabilities=[
                "quality_assurance",
                "fact_verification",
                "revision_loop"
            ],
            description="Quality assurance and consistency checking",
            model="claude-sonnet-4-5-20250929",
            version="1.0.0"
        ),
        AgentInfo(
            agent_id="AGENT-016",
            name="Content Prep Agent",
            agent_type=AgentType.CONTENT_PREP,
            status=AgentStatus.AVAILABLE,
            capabilities=[
                "content_set_detection",
                "ordering_analysis",
                "ordering_clarification",
                "manifest_generation"
            ],
            description="Content set detection and file ordering",
            model="claude-sonnet-4-5-20250929",
            version="1.0.0"
        ),
        AgentInfo(
            agent_id="AGENT-017",
            name="Graph Agent",
            agent_type=AgentType.GRAPH,
            status=AgentStatus.AVAILABLE,
            capabilities=[
                "entity_extraction",
                "relationship_mapping",
                "graph_traversal",
                "cypher_generation"
            ],
            description="Knowledge graph operations and queries",
            model="claude-sonnet-4-5-20250929",
            version="1.0.0"
        ),
    ]
    return agents


# ============================================================================
# Main Orchestration Endpoints
# ============================================================================


@router.post("/coordinate", response_model=OrchestrationResponse)
async def coordinate_content(
    request: OrchestrationRequest,
) -> OrchestrationResponse:
    """
    Main orchestration endpoint for AGENT-001.

    Orchestrates content processing:
    1. Analyzes content patterns (code, tables, structure)
    2. Classifies content into one of 12 departments (>96% accuracy)
    3. Selects appropriate asset types (skill/command/agent/prompt/workflow)
    4. Determines if summary is needed
    5. Returns delegation targets and output paths

    **Use Cases:**
    - Document processing pipeline initialization
    - Content routing decisions
    - Asset generation coordination
    """
    try:
        logger.info(
            "Orchestration request received",
            content_length=len(request.content),
            filename=request.filename,
            user_id=request.user_id
        )

        service = get_orchestrator_service()
        result = await service.process_content(
            content=request.content,
            filename=request.filename,
            metadata=request.metadata,
            user_id=request.user_id
        )

        # Convert service result to response model
        return OrchestrationResponse(
            classification=ClassificationResult(
                department=Department(result.classification.department.value),
                confidence=result.classification.confidence,
                reasoning=result.classification.reasoning,
                keywords_matched=result.classification.keywords_matched,
                secondary_department=Department(result.classification.secondary_department.value) if result.classification.secondary_department else None,
                secondary_confidence=result.classification.secondary_confidence
            ),
            asset_decision=AssetDecision(
                asset_types=[AssetType(a.value) for a in result.asset_decision.asset_types],
                primary_type=AssetType(result.asset_decision.primary_type.value),
                reasoning=result.asset_decision.reasoning,
                needs_summary=result.asset_decision.needs_summary,
                summary_reasoning=result.asset_decision.summary_reasoning
            ),
            delegation_targets=result.delegation_targets,
            output_paths=result.output_paths,
            processing_metadata=result.processing_metadata
        )

    except Exception as e:
        logger.error("Orchestration failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/classify", response_model=ClassificationResult)
async def classify_content(
    request: ClassificationRequest,
) -> ClassificationResult:
    """
    Classify content into a department (standalone).

    Uses weighted keyword matching with optional LLM enhancement
    to classify content into one of 12 business departments.

    **Departments:**
    - it-engineering
    - sales-marketing
    - customer-support
    - operations-hr-supply
    - finance-accounting
    - project-management
    - real-estate
    - private-equity-ma
    - consulting
    - personal-continuing-ed
    - research-development
    - _global (cross-department)
    """
    try:
        logger.info(
            "Classification request",
            content_length=len(request.content),
            filename=request.filename,
            force_llm=request.force_llm
        )

        service = get_orchestrator_service()
        result = await service.department_classifier.classify(
            content=request.content,
            filename=request.filename,
            force_llm=request.force_llm
        )

        return ClassificationResult(
            department=Department(result.department.value),
            confidence=result.confidence,
            reasoning=result.reasoning,
            keywords_matched=result.keywords_matched,
            secondary_department=Department(result.secondary_department.value) if result.secondary_department else None,
            secondary_confidence=result.secondary_confidence
        )

    except Exception as e:
        logger.error("Classification failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=ContentAnalysisResult)
async def analyze_content(
    request: AnalyzeContentRequest,
) -> ContentAnalysisResult:
    """
    Analyze content patterns (standalone).

    Detects:
    - Code patterns (Python, JavaScript, etc.)
    - Table structures
    - Structured data (JSON, YAML)
    - Complexity scoring
    - Privacy level (PII detection)
    - Content type (document, code, video metadata)
    """
    try:
        logger.info(
            "Analysis request",
            content_length=len(request.content),
            filename=request.filename
        )

        service = get_orchestrator_service()
        result = service.pattern_analyzer.analyze(
            content=request.content,
            filename=request.filename
        )

        return ContentAnalysisResult(
            word_count=result.word_count,
            char_count=result.char_count,
            has_code=result.has_code,
            has_tables=result.has_tables,
            has_structured_data=result.has_structured_data,
            complexity_score=result.complexity_score,
            privacy_level=result.privacy_level,
            content_type=result.content_type
        )

    except Exception as e:
        logger.error("Analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Agent Registry Endpoints
# ============================================================================


@router.get("/agents", response_model=AgentRegistryResponse)
async def list_agents(
    agent_type: Optional[AgentType] = Query(None, description="Filter by agent type"),
    status: Optional[AgentStatus] = Query(None, description="Filter by status"),
) -> AgentRegistryResponse:
    """
    List all registered agents in the system.

    Optionally filter by agent type or status.
    Returns comprehensive information about each agent's capabilities.
    """
    try:
        all_agents = _get_all_agents()

        # Apply filters
        filtered_agents = all_agents
        if agent_type:
            filtered_agents = [a for a in filtered_agents if a.agent_type == agent_type]
        if status:
            filtered_agents = [a for a in filtered_agents if a.status == status]

        # Calculate summaries
        by_status = {}
        by_type = {}
        for agent in all_agents:
            by_status[agent.status.value] = by_status.get(agent.status.value, 0) + 1
            by_type[agent.agent_type.value] = by_type.get(agent.agent_type.value, 0) + 1

        return AgentRegistryResponse(
            total_agents=len(filtered_agents),
            agents=filtered_agents,
            by_status=by_status,
            by_type=by_type
        )

    except Exception as e:
        logger.error("Failed to list agents", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str) -> AgentInfo:
    """
    Get detailed information about a specific agent.

    Returns agent capabilities, status, model, and description.
    """
    try:
        all_agents = _get_all_agents()

        for agent in all_agents:
            if agent.agent_id == agent_id:
                return agent

        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found. Use GET /api/orchestrator/agents to see all agents."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get agent", agent_id=agent_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Health & Stats Endpoints
# ============================================================================


@router.get("/health", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """
    Health check for Master Orchestrator (AGENT-001).

    Checks:
    - Service availability
    - LLM (Anthropic API) connectivity
    - Capability status
    """
    try:
        # Check Anthropic API availability
        llm_available = bool(os.getenv("ANTHROPIC_API_KEY"))

        # Check dependencies
        dependencies = {
            "anthropic_api": "healthy" if llm_available else "unavailable",
            "keyword_classifier": "healthy",
            "pattern_analyzer": "healthy",
            "asset_decider": "healthy"
        }

        # Determine overall status
        if not llm_available:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return HealthStatus(
            status=overall_status,
            agent_id="AGENT-001",
            agent_name="Master Content Analyzer & Asset Orchestrator",
            version="1.0.0",
            llm_available=llm_available,
            dependencies=dependencies,
            capabilities={
                "department_classification": True,
                "asset_type_selection": True,
                "llm_enhanced_classification": llm_available,
                "content_analysis": True,
                "privacy_detection": True,
                "delegation": True
            }
        )

    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return HealthStatus(
            status="unhealthy",
            agent_id="AGENT-001",
            agent_name="Master Content Analyzer & Asset Orchestrator",
            version="1.0.0",
            llm_available=False,
            dependencies={},
            capabilities={}
        )


@router.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """
    Get processing statistics for AGENT-001.

    Returns:
    - Total content processed
    - Breakdown by department
    - Breakdown by asset type
    - Average confidence scores
    - Summary generation count
    """
    try:
        service = get_orchestrator_service()
        stats = service.get_stats()

        return StatsResponse(
            agent_id=stats.get("agent_id", "AGENT-001"),
            agent_name=stats.get("agent_name", "Master Content Analyzer & Asset Orchestrator"),
            total_processed=stats.get("total_processed", 0),
            by_department=stats.get("by_department", {}),
            by_asset_type=stats.get("by_asset_type", {}),
            average_confidence=stats.get("average_confidence", 0.0),
            summaries_generated=stats.get("summaries_generated", 0),
            average_processing_time_ms=0.0  # Could be calculated from processing_metadata
        )

    except Exception as e:
        logger.error("Failed to get stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stats/reset")
async def reset_stats() -> Dict[str, str]:
    """
    Reset processing statistics for AGENT-001.

    **Note:** This is an admin operation and should be protected
    in production environments.
    """
    try:
        global _orchestrator_service
        # Reset by creating a new service instance
        _orchestrator_service = None
        _orchestrator_service = create_orchestrator_agent()

        logger.info("Statistics reset successfully")
        return {"message": "Statistics reset successfully"}

    except Exception as e:
        logger.error("Failed to reset stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Department Info Endpoint
# ============================================================================


@router.get("/departments")
async def list_departments() -> Dict[str, Any]:
    """
    List all available departments for classification.

    Returns department codes and descriptions.
    """
    departments = {
        "it-engineering": "Software development, infrastructure, DevOps, technical systems",
        "sales-marketing": "Sales processes, marketing campaigns, lead generation, CRM",
        "customer-support": "Customer service, helpdesk, ticketing, issue resolution",
        "operations-hr-supply": "HR, operations, supply chain, logistics, workforce management",
        "finance-accounting": "Financial operations, accounting, budgeting, auditing",
        "project-management": "Project planning, Agile/Scrum, milestones, resource management",
        "real-estate": "Property management, leasing, real estate transactions",
        "private-equity-ma": "Private equity, mergers & acquisitions, valuations, investments",
        "consulting": "Strategic consulting, advisory services, frameworks, recommendations",
        "personal-continuing-ed": "Education, training, professional development, courses",
        "research-development": "R&D, innovation, prototyping, experiments, patents, product development",
        "_global": "General cross-department content"
    }

    return {
        "total_departments": len(departments),
        "departments": departments
    }


# ============================================================================
# Asset Types Info Endpoint
# ============================================================================


@router.get("/asset-types")
async def list_asset_types() -> Dict[str, Any]:
    """
    List all asset types that can be generated.

    Returns asset type codes and descriptions.
    """
    asset_types = {
        "skill": {
            "name": "Skill",
            "description": "Complex reusable automation",
            "format": "YAML",
            "use_case": "Multi-step processes, automated workflows"
        },
        "command": {
            "name": "Command",
            "description": "Quick one-liner actions",
            "format": "Markdown",
            "use_case": "Simple utilities, shortcuts"
        },
        "agent": {
            "name": "Agent",
            "description": "Multi-step role-based tasks",
            "format": "YAML",
            "use_case": "Complex reasoning, decision-making"
        },
        "prompt": {
            "name": "Prompt",
            "description": "Reusable templates (DEFAULT)",
            "format": "Markdown",
            "use_case": "Standard patterns, scaffolds"
        },
        "workflow": {
            "name": "Workflow",
            "description": "Multi-system automation",
            "format": "JSON",
            "use_case": "Integrations, pipelines"
        }
    }

    return {
        "total_asset_types": len(asset_types),
        "default": "prompt",
        "asset_types": asset_types
    }
