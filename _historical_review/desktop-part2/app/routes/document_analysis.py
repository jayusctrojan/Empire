"""
Empire v7.3 - Document Analysis Agents API Routes
Task 45: Implement Document Analysis Agents (AGENT-009, AGENT-010, AGENT-011)

Provides REST API endpoints for:
- AGENT-009: Senior Research Analyst - Topic/entity/fact extraction
- AGENT-010: Content Strategist - Executive summaries and recommendations
- AGENT-011: Fact Checker - Claim verification with confidence scores

Sequential workflow: Research Analysis → Content Strategy → Fact Checking
"""

import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel, Field
import structlog

from app.services.document_analysis_agents import (
    get_document_analysis_workflow_service,
    DocumentAnalysisWorkflowService,
    ResearchAnalysisResult,
    ContentStrategyResult,
    FactCheckResult,
    DocumentAnalysisResult
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/document-analysis", tags=["Document Analysis Agents"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class AnalyzeDocumentRequest(BaseModel):
    """Request model for full document analysis workflow"""
    content: str = Field(..., min_length=50, description="Document content to analyze")
    title: Optional[str] = Field(None, description="Document title")
    document_id: Optional[str] = Field(None, description="Optional document ID for tracking")
    run_research: bool = Field(default=True, description="Run AGENT-009 research analysis")
    run_strategy: bool = Field(default=True, description="Run AGENT-010 content strategy")
    run_fact_check: bool = Field(default=True, description="Run AGENT-011 fact checking")


class ResearchAnalysisRequest(BaseModel):
    """Request model for research analysis only (AGENT-009)"""
    content: str = Field(..., min_length=50, description="Document content to analyze")
    document_id: Optional[str] = Field(None, description="Optional document ID")
    extract_topics: bool = Field(default=True)
    extract_entities: bool = Field(default=True)
    extract_facts: bool = Field(default=True)
    assess_quality: bool = Field(default=True)


class ContentStrategyRequest(BaseModel):
    """Request model for content strategy only (AGENT-010)"""
    content: str = Field(..., min_length=50, description="Document content to analyze")
    document_id: Optional[str] = Field(None, description="Optional document ID")
    target_audience: str = Field(default="business professionals", description="Target audience")


class FactCheckRequest(BaseModel):
    """Request model for fact checking only (AGENT-011)"""
    content: str = Field(..., min_length=50, description="Document content to verify")
    document_id: Optional[str] = Field(None, description="Optional document ID")
    claims_to_verify: Optional[List[str]] = Field(None, description="Specific claims to verify")
    max_claims: int = Field(default=15, ge=1, le=50, description="Maximum claims to verify")


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
    total_analyses: int
    research_analyses: int
    content_strategies: int
    fact_checks: int
    average_processing_time_ms: float
    agents: Dict[str, Dict[str, Any]]


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_workflow_service() -> DocumentAnalysisWorkflowService:
    """Dependency for document analysis workflow service"""
    return get_document_analysis_workflow_service()


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/analyze")
async def analyze_document(
    request: AnalyzeDocumentRequest,
    service: DocumentAnalysisWorkflowService = Depends(get_workflow_service)
) -> Dict[str, Any]:
    """
    Run full document analysis workflow.

    Sequential pipeline:
    1. AGENT-009 (Research Analyst): Extract topics, entities, facts, quality
    2. AGENT-010 (Content Strategist): Generate summaries, findings, recommendations
    3. AGENT-011 (Fact Checker): Verify claims with confidence scores

    Each agent can be enabled/disabled via request parameters.
    """
    try:
        logger.info(
            "Document analysis request",
            content_length=len(request.content),
            title=request.title,
            run_research=request.run_research,
            run_strategy=request.run_strategy,
            run_fact_check=request.run_fact_check
        )

        result = await service.analyze_document(
            content=request.content,
            title=request.title or "",
            document_id=request.document_id or "",
            run_research=request.run_research,
            run_strategy=request.run_strategy,
            run_fact_check=request.run_fact_check
        )

        return _convert_analysis_result(result)

    except Exception as e:
        logger.error("Document analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/file")
async def analyze_file(
    file: UploadFile = File(..., description="Document file to analyze"),
    run_research: bool = Form(default=True),
    run_strategy: bool = Form(default=True),
    run_fact_check: bool = Form(default=True),
    service: DocumentAnalysisWorkflowService = Depends(get_workflow_service)
) -> Dict[str, Any]:
    """
    Analyze an uploaded document file.

    Supported file types: .txt, .md, .py, .js, .json, .yaml, .csv
    """
    try:
        # Read file content
        content_bytes = await file.read()

        # Decode text content
        try:
            content = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                content = content_bytes.decode('latin-1')
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Could not decode file content. Please upload a text file."
                )

        if len(content) < 50:
            raise HTTPException(
                status_code=400,
                detail="File content too short. Minimum 50 characters required."
            )

        logger.info(
            "File analysis request",
            filename=file.filename,
            content_length=len(content)
        )

        result = await service.analyze_document(
            content=content,
            title=file.filename or "",
            run_research=run_research,
            run_strategy=run_strategy,
            run_fact_check=run_fact_check
        )

        return _convert_analysis_result(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("File analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research")
async def run_research_analysis(
    request: ResearchAnalysisRequest,
    service: DocumentAnalysisWorkflowService = Depends(get_workflow_service)
) -> Dict[str, Any]:
    """
    Run AGENT-009 (Senior Research Analyst) only.

    Extracts:
    - Topics with relevance scores
    - Named entities with context
    - Key facts with confidence
    - Document quality assessment
    """
    try:
        logger.info(
            "Research analysis request",
            content_length=len(request.content),
            document_id=request.document_id
        )

        result = await service.research_analyst.analyze(
            content=request.content,
            document_id=request.document_id or "",
            extract_topics=request.extract_topics,
            extract_entities=request.extract_entities,
            extract_facts=request.extract_facts,
            assess_quality=request.assess_quality
        )

        return _convert_research_result(result)

    except Exception as e:
        logger.error("Research analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy")
async def run_content_strategy(
    request: ContentStrategyRequest,
    service: DocumentAnalysisWorkflowService = Depends(get_workflow_service)
) -> Dict[str, Any]:
    """
    Run AGENT-010 (Content Strategist) only.

    Generates:
    - Executive summary
    - Key findings with evidence
    - Prioritized recommendations
    - Action items and next steps
    """
    try:
        logger.info(
            "Content strategy request",
            content_length=len(request.content),
            document_id=request.document_id
        )

        result = await service.content_strategist.strategize(
            content=request.content,
            document_id=request.document_id or "",
            target_audience=request.target_audience
        )

        return _convert_strategy_result(result)

    except Exception as e:
        logger.error("Content strategy failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fact-check")
async def run_fact_check(
    request: FactCheckRequest,
    service: DocumentAnalysisWorkflowService = Depends(get_workflow_service)
) -> Dict[str, Any]:
    """
    Run AGENT-011 (Fact Checker) only.

    Verifies:
    - Claims extracted from document
    - Specific claims if provided
    - Assigns verification status and confidence
    - Provides evidence and source references
    """
    try:
        logger.info(
            "Fact check request",
            content_length=len(request.content),
            document_id=request.document_id,
            claims_count=len(request.claims_to_verify) if request.claims_to_verify else 0
        )

        result = await service.fact_checker.verify(
            content=request.content,
            document_id=request.document_id or "",
            claims_to_verify=request.claims_to_verify,
            max_claims=request.max_claims
        )

        return _convert_fact_check_result(result)

    except Exception as e:
        logger.error("Fact check failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents", response_model=List[AgentInfoResponse])
async def get_agents(
    service: DocumentAnalysisWorkflowService = Depends(get_workflow_service)
) -> List[AgentInfoResponse]:
    """Get information about all three document analysis agents"""
    agents = service.get_agent_info()
    return [AgentInfoResponse(**agent) for agent in agents]


@router.get("/agents/{agent_id}", response_model=AgentInfoResponse)
async def get_agent(
    agent_id: str,
    service: DocumentAnalysisWorkflowService = Depends(get_workflow_service)
) -> AgentInfoResponse:
    """Get information about a specific agent"""
    agents = service.get_agent_info()

    for agent in agents:
        if agent["agent_id"] == agent_id:
            return AgentInfoResponse(**agent)

    raise HTTPException(
        status_code=404,
        detail=f"Agent '{agent_id}' not found. Valid agents: AGENT-009, AGENT-010, AGENT-011"
    )


@router.get("/stats", response_model=WorkflowStatsResponse)
async def get_workflow_stats(
    service: DocumentAnalysisWorkflowService = Depends(get_workflow_service)
) -> WorkflowStatsResponse:
    """Get workflow statistics for all agents"""
    stats = service.get_stats()
    return WorkflowStatsResponse(**stats)


@router.post("/stats/reset")
async def reset_workflow_stats(
    service: DocumentAnalysisWorkflowService = Depends(get_workflow_service)
) -> Dict[str, str]:
    """Reset workflow statistics"""
    service.reset_stats()
    return {"message": "Statistics reset successfully"}


@router.get("/health")
async def workflow_health() -> Dict[str, Any]:
    """Health check for Document Analysis Agents"""
    return {
        "status": "healthy",
        "agents": [
            {
                "agent_id": "AGENT-009",
                "name": "Senior Research Analyst",
                "status": "available"
            },
            {
                "agent_id": "AGENT-010",
                "name": "Content Strategist",
                "status": "available"
            },
            {
                "agent_id": "AGENT-011",
                "name": "Fact Checker",
                "status": "available"
            }
        ],
        "capabilities": {
            "full_workflow": True,
            "individual_agents": True,
            "file_upload": True,
            "llm_powered": bool(os.getenv("ANTHROPIC_API_KEY"))
        },
        "workflow": "Research Analysis → Content Strategy → Fact Checking"
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _convert_analysis_result(result: DocumentAnalysisResult) -> Dict[str, Any]:
    """Convert DocumentAnalysisResult to API response"""
    response = {
        "document_id": result.document_id,
        "title": result.title,
        "workflow_completed": result.workflow_completed,
        "agents_run": result.agents_used,
        "total_processing_time_ms": result.total_processing_time_ms,
        "errors": result.errors
    }

    if result.research_analysis:
        response["research_analysis"] = _convert_research_result(result.research_analysis)

    if result.content_strategy:
        response["content_strategy"] = _convert_strategy_result(result.content_strategy)

    if result.fact_check:
        response["fact_check"] = _convert_fact_check_result(result.fact_check)

    return response


def _convert_research_result(result: ResearchAnalysisResult) -> Dict[str, Any]:
    """Convert ResearchAnalysisResult to API response"""
    response = {
        "agent_id": "AGENT-009",
        "agent_name": "Senior Research Analyst",
        "document_id": result.document_id,
        "word_count": result.word_count,
        "processing_time_ms": result.processing_time_ms,
        "topics": [
            {
                "name": t.name,
                "relevance_score": t.relevance_score,
                "keywords": t.keywords,
                "description": t.description
            }
            for t in result.topics
        ],
        "entities": [
            {
                "name": e.name,
                "entity_type": e.entity_type,
                "mentions": e.mentions,
                "context": e.context,
                "importance": e.importance
            }
            for e in result.entities
        ],
        "facts": [
            {
                "statement": f.statement,
                "source_location": f.source_location,
                "confidence": f.confidence,
                "supporting_evidence": f.supporting_evidence,
                "related_entities": f.related_entities
            }
            for f in result.facts
        ]
    }

    if result.quality_assessment:
        qa = result.quality_assessment
        response["quality_assessment"] = {
            "overall_quality": qa.overall_quality.value,
            "quality_score": qa.quality_score,
            "clarity_score": qa.clarity_score,
            "completeness_score": qa.completeness_score,
            "accuracy_indicators": qa.accuracy_indicators,
            "strengths": qa.strengths,
            "weaknesses": qa.weaknesses,
            "improvement_suggestions": qa.improvement_suggestions
        }

    return response


def _convert_strategy_result(result: ContentStrategyResult) -> Dict[str, Any]:
    """Convert ContentStrategyResult to API response"""
    response = {
        "agent_id": "AGENT-010",
        "agent_name": "Content Strategist",
        "document_id": result.document_id,
        "processing_time_ms": result.processing_time_ms,
        "action_items": result.action_items,
        "next_steps": result.next_steps,
        "findings": [
            {
                "title": f.title,
                "description": f.description,
                "importance": f.importance,
                "supporting_facts": f.supporting_facts,
                "implications": f.implications
            }
            for f in result.findings
        ],
        "recommendations": [
            {
                "title": r.title,
                "description": r.description,
                "priority": r.priority.value,
                "rationale": r.rationale,
                "implementation_steps": r.implementation_steps,
                "expected_impact": r.expected_impact,
                "resources_needed": r.resources_needed
            }
            for r in result.recommendations
        ]
    }

    if result.executive_summary:
        es = result.executive_summary
        response["executive_summary"] = {
            "title": es.title,
            "summary": es.summary,
            "key_points": es.key_points,
            "target_audience": es.target_audience,
            "reading_time_minutes": es.reading_time_minutes
        }

    return response


def _convert_fact_check_result(result: FactCheckResult) -> Dict[str, Any]:
    """Convert FactCheckResult to API response"""
    return {
        "agent_id": "AGENT-011",
        "agent_name": "Fact Checker",
        "document_id": result.document_id,
        "claims_checked": result.claims_checked,
        "verified_claims": result.verified_claims,
        "uncertain_claims": result.uncertain_claims,
        "false_claims": result.false_claims,
        "overall_credibility_score": result.overall_credibility_score,
        "credibility_assessment": result.credibility_assessment,
        "red_flags": result.red_flags,
        "processing_time_ms": result.processing_time_ms,
        "verifications": [
            {
                "claim": v.claim,
                "status": v.status.value,
                "confidence": v.confidence,
                "reasoning": v.reasoning,
                "supporting_evidence": v.supporting_evidence,
                "contradicting_evidence": v.contradicting_evidence,
                "citations": v.citations,
                "verification_method": v.verification_method
            }
            for v in result.verifications
        ]
    }
