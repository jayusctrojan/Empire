"""
Empire v7.3 - Multi-Agent Orchestration API Routes
Task 46: Implement Multi-Agent Orchestration Agents (AGENT-012 to AGENT-015)

Provides REST API endpoints for:
- AGENT-012: Research Agent - Web/academic search and information gathering
- AGENT-013: Analysis Agent - Pattern detection and statistical analysis
- AGENT-014: Writing Agent - Report generation and documentation
- AGENT-015: Review Agent - Quality assurance and consistency checking

Sequential workflow: Research → Analysis → Writing → Review (with revision loop)
"""

import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import structlog

from app.services.multi_agent_orchestration import (
    get_multi_agent_orchestration_service,
    MultiAgentOrchestrationService,
    WorkflowTask,
    ResearchResult,
    AnalysisResult,
    WritingResult,
    ReviewResult,
    OrchestrationResult,
    ReportFormat,
    ResearchSourceType
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/orchestration", tags=["Multi-Agent Orchestration"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class WorkflowRequest(BaseModel):
    """Request model for full orchestration workflow"""
    title: str = Field(..., min_length=3, description="Workflow task title")
    description: str = Field(..., min_length=10, description="Detailed task description")
    context: str = Field(default="", description="Additional context for the task")
    constraints: List[str] = Field(default_factory=list, description="Constraints to follow")
    expected_output: str = Field(default="", description="Expected output description")
    run_research: bool = Field(default=True, description="Run AGENT-012 Research")
    run_analysis: bool = Field(default=True, description="Run AGENT-013 Analysis")
    run_writing: bool = Field(default=True, description="Run AGENT-014 Writing")
    run_review: bool = Field(default=True, description="Run AGENT-015 Review")
    max_revisions: int = Field(default=2, ge=0, le=5, description="Max revision iterations")
    output_format: str = Field(default="markdown", description="Output format: markdown, html, text, json")
    target_audience: str = Field(default="business professionals", description="Target audience")


class ResearchRequest(BaseModel):
    """Request model for research only (AGENT-012)"""
    query: str = Field(..., min_length=5, description="Research query or topic")
    context: str = Field(default="", description="Additional context")
    search_types: Optional[List[str]] = Field(
        default=None,
        description="Source types: web, academic, news, internal, expert"
    )
    max_sources: int = Field(default=10, ge=1, le=50, description="Maximum sources")


class AnalysisRequest(BaseModel):
    """Request model for analysis only (AGENT-013)"""
    data: str = Field(..., min_length=20, description="Data to analyze")
    analysis_focus: str = Field(default="comprehensive", description="Focus area")
    detect_patterns: bool = Field(default=True, description="Detect patterns")
    compute_statistics: bool = Field(default=True, description="Compute statistics")
    find_correlations: bool = Field(default=True, description="Find correlations")


class WritingRequest(BaseModel):
    """Request model for writing only (AGENT-014)"""
    title: str = Field(..., min_length=3, description="Document title")
    description: str = Field(..., min_length=10, description="What to write about")
    context: str = Field(default="", description="Background information")
    constraints: List[str] = Field(default_factory=list, description="Writing constraints")
    output_format: str = Field(default="markdown", description="Output format")
    target_audience: str = Field(default="business professionals", description="Target audience")
    max_length: int = Field(default=3000, ge=100, le=10000, description="Max word count")


class ReviewRequest(BaseModel):
    """Request model for review only (AGENT-015)"""
    content: str = Field(..., min_length=50, description="Document content to review")
    title: str = Field(default="Document Review", description="Document title")
    check_facts: bool = Field(default=True, description="Verify facts")
    check_consistency: bool = Field(default=True, description="Check consistency")
    check_grammar: bool = Field(default=True, description="Check grammar")
    strict_mode: bool = Field(default=False, description="Apply strict criteria")


class AgentInfoResponse(BaseModel):
    """Response model for agent information"""
    agent_id: str
    name: str
    description: str
    model: str
    temperature: float
    capabilities: List[str]


class WorkflowStatsResponse(BaseModel):
    """Response model for workflow statistics"""
    total_workflows: int
    total_revisions: int
    research_invocations: int
    analysis_invocations: int
    writing_invocations: int
    review_invocations: int
    average_processing_time_ms: float
    agents: Dict[str, Dict[str, Any]]


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_orchestration_service() -> MultiAgentOrchestrationService:
    """Dependency for multi-agent orchestration service"""
    return get_multi_agent_orchestration_service()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_report_format(format_str: str) -> ReportFormat:
    """Convert string to ReportFormat enum"""
    format_map = {
        "markdown": ReportFormat.MARKDOWN,
        "html": ReportFormat.HTML,
        "text": ReportFormat.TEXT,
        "json": ReportFormat.JSON
    }
    return format_map.get(format_str.lower(), ReportFormat.MARKDOWN)


def _get_source_types(types: Optional[List[str]]) -> Optional[List[ResearchSourceType]]:
    """Convert string list to ResearchSourceType list"""
    if not types:
        return None

    type_map = {
        "web": ResearchSourceType.WEB,
        "academic": ResearchSourceType.ACADEMIC,
        "news": ResearchSourceType.NEWS,
        "internal": ResearchSourceType.INTERNAL,
        "expert": ResearchSourceType.EXPERT
    }

    return [type_map.get(t.lower(), ResearchSourceType.WEB) for t in types if t.lower() in type_map]


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/workflow")
async def execute_workflow(
    request: WorkflowRequest,
    service: MultiAgentOrchestrationService = Depends(get_orchestration_service)
) -> Dict[str, Any]:
    """
    Execute full multi-agent orchestration workflow.

    Sequential pipeline:
    1. AGENT-012 (Research Agent): Gather information from multiple sources
    2. AGENT-013 (Analysis Agent): Detect patterns and extract insights
    3. AGENT-014 (Writing Agent): Generate comprehensive report
    4. AGENT-015 (Review Agent): Quality check with revision loop

    Each agent can be enabled/disabled via request parameters.
    """
    try:
        logger.info(
            "Orchestration workflow request",
            title=request.title,
            run_research=request.run_research,
            run_analysis=request.run_analysis,
            run_writing=request.run_writing,
            run_review=request.run_review
        )

        task = WorkflowTask(
            task_id="",
            title=request.title,
            description=request.description,
            context=request.context,
            constraints=request.constraints,
            expected_output=request.expected_output
        )

        result = await service.execute_workflow(
            task=task,
            run_research=request.run_research,
            run_analysis=request.run_analysis,
            run_writing=request.run_writing,
            run_review=request.run_review,
            max_revisions=request.max_revisions,
            output_format=_get_report_format(request.output_format),
            target_audience=request.target_audience
        )

        return _convert_orchestration_result(result)

    except Exception as e:
        logger.error("Orchestration workflow failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research")
async def run_research(
    request: ResearchRequest,
    service: MultiAgentOrchestrationService = Depends(get_orchestration_service)
) -> Dict[str, Any]:
    """
    Run AGENT-012 (Research Agent) only.

    Capabilities:
    - Web search and information gathering
    - Academic database access
    - Source credibility assessment
    - Query expansion and reformulation
    """
    try:
        logger.info(
            "Research request",
            query=request.query[:100],
            max_sources=request.max_sources
        )

        result = await service.research_agent.research(
            query=request.query,
            context=request.context,
            search_types=_get_source_types(request.search_types),
            max_sources=request.max_sources
        )

        return _convert_research_result(result)

    except Exception as e:
        logger.error("Research failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def run_analysis(
    request: AnalysisRequest,
    service: MultiAgentOrchestrationService = Depends(get_orchestration_service)
) -> Dict[str, Any]:
    """
    Run AGENT-013 (Analysis Agent) only.

    Capabilities:
    - Pattern detection (trends, anomalies, clusters)
    - Statistical analysis
    - Correlation identification
    - Insight extraction
    - Visualization recommendations
    """
    try:
        logger.info(
            "Analysis request",
            data_length=len(request.data),
            analysis_focus=request.analysis_focus
        )

        result = await service.analysis_agent.analyze(
            raw_data=request.data,
            analysis_focus=request.analysis_focus,
            detect_patterns=request.detect_patterns,
            compute_statistics=request.compute_statistics,
            find_correlations=request.find_correlations
        )

        return _convert_analysis_result(result)

    except Exception as e:
        logger.error("Analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/write")
async def run_writing(
    request: WritingRequest,
    service: MultiAgentOrchestrationService = Depends(get_orchestration_service)
) -> Dict[str, Any]:
    """
    Run AGENT-014 (Writing Agent) only.

    Capabilities:
    - Report generation in multiple formats
    - Section structuring
    - Citation management
    - Style adaptation
    - Terminology consistency
    """
    try:
        logger.info(
            "Writing request",
            title=request.title,
            output_format=request.output_format
        )

        task = WorkflowTask(
            task_id="",
            title=request.title,
            description=request.description,
            context=request.context,
            constraints=request.constraints,
            expected_output=""
        )

        result = await service.writing_agent.write(
            task=task,
            output_format=_get_report_format(request.output_format),
            target_audience=request.target_audience,
            max_length=request.max_length
        )

        return _convert_writing_result(result)

    except Exception as e:
        logger.error("Writing failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review")
async def run_review(
    request: ReviewRequest,
    service: MultiAgentOrchestrationService = Depends(get_orchestration_service)
) -> Dict[str, Any]:
    """
    Run AGENT-015 (Review Agent) only.

    Capabilities:
    - Quality assurance
    - Fact verification
    - Consistency checking
    - Grammar and spelling review
    - Improvement suggestions
    """
    try:
        logger.info(
            "Review request",
            content_length=len(request.content),
            strict_mode=request.strict_mode
        )

        # Create a WritingResult to review
        from app.services.multi_agent_orchestration import WritingResult as WR
        writing_result = WR(
            task_id="direct_review",
            raw_content=request.content
        )

        result = await service.review_agent.review(
            writing_result=writing_result,
            check_facts=request.check_facts,
            check_consistency=request.check_consistency,
            check_grammar=request.check_grammar,
            strict_mode=request.strict_mode
        )

        return _convert_review_result(result)

    except Exception as e:
        logger.error("Review failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents", response_model=List[AgentInfoResponse])
async def get_agents(
    service: MultiAgentOrchestrationService = Depends(get_orchestration_service)
) -> List[AgentInfoResponse]:
    """Get information about all four orchestration agents"""
    agents = service.get_agent_info()
    return [AgentInfoResponse(**agent) for agent in agents]


@router.get("/agents/{agent_id}", response_model=AgentInfoResponse)
async def get_agent(
    agent_id: str,
    service: MultiAgentOrchestrationService = Depends(get_orchestration_service)
) -> AgentInfoResponse:
    """Get information about a specific agent"""
    agents = service.get_agent_info()

    for agent in agents:
        if agent["agent_id"] == agent_id:
            return AgentInfoResponse(**agent)

    raise HTTPException(
        status_code=404,
        detail=f"Agent '{agent_id}' not found. Valid agents: AGENT-012, AGENT-013, AGENT-014, AGENT-015"
    )


@router.get("/stats", response_model=WorkflowStatsResponse)
async def get_workflow_stats(
    service: MultiAgentOrchestrationService = Depends(get_orchestration_service)
) -> WorkflowStatsResponse:
    """Get workflow statistics for all agents"""
    stats = service.get_stats()
    return WorkflowStatsResponse(**stats)


@router.post("/stats/reset")
async def reset_workflow_stats(
    service: MultiAgentOrchestrationService = Depends(get_orchestration_service)
) -> Dict[str, str]:
    """Reset workflow statistics"""
    service.reset_stats()
    return {"message": "Statistics reset successfully"}


@router.get("/health")
async def workflow_health() -> Dict[str, Any]:
    """Health check for Multi-Agent Orchestration"""
    return {
        "status": "healthy",
        "agents": [
            {
                "agent_id": "AGENT-012",
                "name": "Research Agent",
                "status": "available"
            },
            {
                "agent_id": "AGENT-013",
                "name": "Analysis Agent",
                "status": "available"
            },
            {
                "agent_id": "AGENT-014",
                "name": "Writing Agent",
                "status": "available"
            },
            {
                "agent_id": "AGENT-015",
                "name": "Review Agent",
                "status": "available"
            }
        ],
        "capabilities": {
            "full_workflow": True,
            "individual_agents": True,
            "revision_loop": True,
            "llm_powered": bool(os.getenv("ANTHROPIC_API_KEY"))
        },
        "workflow": "Research → Analysis → Writing → Review (with revision loop)"
    }


# =============================================================================
# RESPONSE CONVERTERS
# =============================================================================

def _convert_orchestration_result(result: OrchestrationResult) -> Dict[str, Any]:
    """Convert OrchestrationResult to API response"""
    response = {
        "workflow_id": result.workflow_id,
        "workflow_completed": result.workflow_completed,
        "agents_used": result.agents_used,
        "revision_count": result.revision_count,
        "total_processing_time_ms": result.total_processing_time_ms,
        "errors": result.errors,
        "final_output": result.final_output
    }

    if result.task:
        response["task"] = {
            "task_id": result.task.task_id,
            "title": result.task.title,
            "description": result.task.description
        }

    if result.research_result:
        response["research"] = _convert_research_result(result.research_result)

    if result.analysis_result:
        response["analysis"] = _convert_analysis_result(result.analysis_result)

    if result.writing_result:
        response["writing"] = _convert_writing_result(result.writing_result)

    if result.review_result:
        response["review"] = _convert_review_result(result.review_result)

    return response


def _convert_research_result(result: ResearchResult) -> Dict[str, Any]:
    """Convert ResearchResult to API response"""
    return {
        "agent_id": "AGENT-012",
        "agent_name": "Research Agent",
        "task_id": result.task_id,
        "original_query": result.original_query,
        "processing_time_ms": result.processing_time_ms,
        "summary": result.summary,
        "queries_executed": [
            {
                "original_query": q.original_query,
                "expanded_queries": q.expanded_queries,
                "key_terms": q.key_terms,
                "search_scope": q.search_scope
            }
            for q in result.queries_executed
        ],
        "sources": [
            {
                "title": s.title,
                "url": s.url,
                "source_type": s.source_type.value,
                "credibility_score": s.credibility_score,
                "publication_date": s.publication_date,
                "authors": s.authors,
                "summary": s.summary
            }
            for s in result.sources
        ],
        "findings": [
            {
                "finding": f.finding,
                "relevance_score": f.relevance_score,
                "sources": f.sources,
                "confidence": f.confidence,
                "keywords": f.keywords,
                "category": f.category
            }
            for f in result.findings
        ],
        "gaps_identified": result.gaps_identified,
        "recommended_followup": result.recommended_followup
    }


def _convert_analysis_result(result: AnalysisResult) -> Dict[str, Any]:
    """Convert AnalysisResult to API response"""
    return {
        "agent_id": "AGENT-013",
        "agent_name": "Analysis Agent",
        "task_id": result.task_id,
        "processing_time_ms": result.processing_time_ms,
        "data_quality_score": result.data_quality_score,
        "patterns": [
            {
                "pattern_type": p.pattern_type.value,
                "name": p.name,
                "description": p.description,
                "confidence": p.confidence,
                "supporting_data": p.supporting_data,
                "significance": p.significance,
                "visual_recommendation": p.visual_recommendation
            }
            for p in result.patterns
        ],
        "statistics": [
            {
                "metric_name": s.metric_name,
                "value": s.value,
                "interpretation": s.interpretation,
                "comparison_baseline": s.comparison_baseline,
                "significance_level": s.significance_level
            }
            for s in result.statistics
        ],
        "correlations": [
            {
                "variable_1": c.variable_1,
                "variable_2": c.variable_2,
                "correlation_type": c.correlation_type,
                "strength": c.strength,
                "description": c.description,
                "implications": c.implications
            }
            for c in result.correlations
        ],
        "key_insights": result.key_insights,
        "limitations": result.limitations,
        "visualization_specs": result.visualization_specs
    }


def _convert_writing_result(result: WritingResult) -> Dict[str, Any]:
    """Convert WritingResult to API response"""
    response = {
        "agent_id": "AGENT-014",
        "agent_name": "Writing Agent",
        "task_id": result.task_id,
        "format": result.format.value,
        "processing_time_ms": result.processing_time_ms,
        "style_guide_compliance": result.style_guide_compliance,
        "terminology_consistency": result.terminology_consistency,
        "raw_content": result.raw_content
    }

    if result.report:
        response["report"] = {
            "title": result.report.title,
            "format": result.report.format.value,
            "word_count": result.report.word_count,
            "reading_time_minutes": result.report.reading_time_minutes,
            "sections": [
                {
                    "title": s.title,
                    "content": s.content,
                    "section_type": s.section_type,
                    "order": s.order
                }
                for s in result.report.sections
            ],
            "citations": [
                {
                    "id": c.id,
                    "text": c.text,
                    "source": c.source,
                    "url": c.url
                }
                for c in result.report.citations
            ]
        }

    return response


def _convert_review_result(result: ReviewResult) -> Dict[str, Any]:
    """Convert ReviewResult to API response"""
    return {
        "agent_id": "AGENT-015",
        "agent_name": "Review Agent",
        "task_id": result.task_id,
        "processing_time_ms": result.processing_time_ms,
        "status": result.status.value,
        "approved_for_publication": result.approved_for_publication,
        "overall_quality_score": result.overall_quality_score,
        "grammar_score": result.grammar_score,
        "clarity_score": result.clarity_score,
        "completeness_score": result.completeness_score,
        "issues": [
            {
                "issue_type": i.issue_type.value,
                "severity": i.severity.value,
                "location": i.location,
                "description": i.description,
                "suggestion": i.suggestion,
                "auto_fixable": i.auto_fixable
            }
            for i in result.issues
        ],
        "fact_checks": [
            {
                "claim": f.claim,
                "verified": f.verified,
                "confidence": f.confidence,
                "source": f.source,
                "notes": f.notes
            }
            for f in result.fact_checks
        ],
        "consistency_checks": [
            {
                "aspect": c.aspect,
                "is_consistent": c.is_consistent,
                "inconsistencies": c.inconsistencies,
                "recommendations": c.recommendations
            }
            for c in result.consistency_checks
        ],
        "strengths": result.strengths,
        "improvement_summary": result.improvement_summary
    }
