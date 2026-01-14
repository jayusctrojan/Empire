"""
Empire v7.3 - Multi-Agent Orchestration Agents (Task 46)
AGENT-012: Research Agent (Web/Academic Search)
AGENT-013: Analysis Agent (Pattern Detection, Statistics)
AGENT-014: Writing Agent (Reports, Documentation)
AGENT-015: Review Agent (Quality Assurance, Consistency)

Four specialized agents for complex multi-agent workflows:
- AGENT-012: Web search, academic database access, information gathering
- AGENT-013: Pattern recognition, statistical analysis, data visualization prep
- AGENT-014: Report generation, document formatting, citation management
- AGENT-015: Quality review, fact-checking, consistency validation

Sequential workflow: Research → Analysis → Writing → Review

Author: Claude Code
Date: 2025-01-27
"""

import os
import re
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import asyncio
import time

import structlog
from pydantic import BaseModel, Field

from app.services.api_resilience import ResilientAnthropicClient, CircuitOpenError
from app.services.agent_metrics import (
    AgentMetricsContext,
    AgentID,
    track_agent_request,
    track_agent_error,
    track_llm_call,
    track_quality_score,
    track_workflow,
    track_revision,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class OrchestrationAgentRole(str, Enum):
    """Multi-agent orchestration agent roles"""
    RESEARCH = "research"
    ANALYSIS = "analysis"
    WRITING = "writing"
    REVIEW = "review"


class ResearchSourceType(str, Enum):
    """Types of research sources"""
    WEB = "web"
    ACADEMIC = "academic"
    NEWS = "news"
    INTERNAL = "internal"
    EXPERT = "expert"


class PatternType(str, Enum):
    """Types of patterns detected"""
    TREND = "trend"
    ANOMALY = "anomaly"
    CORRELATION = "correlation"
    CLUSTER = "cluster"
    OUTLIER = "outlier"


class ReportFormat(str, Enum):
    """Supported report formats"""
    MARKDOWN = "markdown"
    HTML = "html"
    TEXT = "text"
    JSON = "json"


class ReviewStatus(str, Enum):
    """Review status outcomes"""
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    MAJOR_ISSUES = "major_issues"
    REJECTED = "rejected"


class IssueType(str, Enum):
    """Types of issues found during review"""
    GRAMMAR = "grammar"
    FACTUAL = "factual"
    CONSISTENCY = "consistency"
    CITATION = "citation"
    FORMATTING = "formatting"
    CLARITY = "clarity"
    COMPLETENESS = "completeness"


class IssueSeverity(str, Enum):
    """Severity levels for issues"""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    SUGGESTION = "suggestion"


# Agent configurations
ORCHESTRATION_AGENT_CONFIGS = {
    OrchestrationAgentRole.RESEARCH: {
        "agent_id": "AGENT-012",
        "name": "Research Agent",
        "description": "Conducts web and academic research, gathers information from multiple sources",
        "model": "claude-sonnet-4-5-20250514",
        "temperature": 0.2,  # Low temperature for factual research
        "max_tokens": 4000
    },
    OrchestrationAgentRole.ANALYSIS: {
        "agent_id": "AGENT-013",
        "name": "Analysis Agent",
        "description": "Detects patterns, performs statistical analysis, identifies insights",
        "model": "claude-sonnet-4-5-20250514",
        "temperature": 0.1,  # Very low for precise analysis
        "max_tokens": 4000
    },
    OrchestrationAgentRole.WRITING: {
        "agent_id": "AGENT-014",
        "name": "Writing Agent",
        "description": "Generates reports, documentation, and structured content",
        "model": "claude-sonnet-4-5-20250514",
        "temperature": 0.4,  # Higher for creative writing
        "max_tokens": 6000
    },
    OrchestrationAgentRole.REVIEW: {
        "agent_id": "AGENT-015",
        "name": "Review Agent",
        "description": "Quality assurance, consistency checking, fact verification",
        "model": "claude-sonnet-4-5-20250514",
        "temperature": 0.0,  # Zero for strict review
        "max_tokens": 4000
    }
}


# =============================================================================
# PYDANTIC MODELS - Research Agent (AGENT-012)
# =============================================================================

class ResearchSource(BaseModel):
    """A research source with metadata"""
    title: str
    url: str = ""
    source_type: ResearchSourceType = ResearchSourceType.WEB
    credibility_score: float = Field(ge=0.0, le=1.0, default=0.7)
    publication_date: str = ""
    authors: List[str] = Field(default_factory=list)
    summary: str = ""


class ResearchFinding(BaseModel):
    """A finding from research"""
    finding: str
    relevance_score: float = Field(ge=0.0, le=1.0, default=0.8)
    sources: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)
    keywords: List[str] = Field(default_factory=list)
    category: str = ""


class ResearchQuery(BaseModel):
    """A research query and its variations"""
    original_query: str
    expanded_queries: List[str] = Field(default_factory=list)
    key_terms: List[str] = Field(default_factory=list)
    search_scope: str = "comprehensive"


class ResearchResult(BaseModel):
    """Complete result from Research Agent (AGENT-012)"""
    task_id: str = ""
    original_query: str = ""
    queries_executed: List[ResearchQuery] = Field(default_factory=list)
    sources: List[ResearchSource] = Field(default_factory=list)
    findings: List[ResearchFinding] = Field(default_factory=list)
    summary: str = ""
    gaps_identified: List[str] = Field(default_factory=list)
    recommended_followup: List[str] = Field(default_factory=list)
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# PYDANTIC MODELS - Analysis Agent (AGENT-013)
# =============================================================================

class DetectedPattern(BaseModel):
    """A pattern detected in data"""
    pattern_type: PatternType = PatternType.TREND
    name: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)
    supporting_data: List[str] = Field(default_factory=list)
    significance: str = ""  # high, medium, low
    visual_recommendation: str = ""  # Chart type recommendation


class StatisticalInsight(BaseModel):
    """A statistical insight from analysis"""
    metric_name: str
    value: str
    interpretation: str
    comparison_baseline: str = ""
    significance_level: str = ""


class DataCorrelation(BaseModel):
    """A correlation between data points"""
    variable_1: str
    variable_2: str
    correlation_type: str  # positive, negative, none
    strength: float = Field(ge=0.0, le=1.0, default=0.5)
    description: str = ""
    implications: str = ""


class AnalysisResult(BaseModel):
    """Complete result from Analysis Agent (AGENT-013)"""
    task_id: str = ""
    patterns: List[DetectedPattern] = Field(default_factory=list)
    statistics: List[StatisticalInsight] = Field(default_factory=list)
    correlations: List[DataCorrelation] = Field(default_factory=list)
    key_insights: List[str] = Field(default_factory=list)
    data_quality_score: float = Field(ge=0.0, le=1.0, default=0.7)
    limitations: List[str] = Field(default_factory=list)
    visualization_specs: List[Dict[str, Any]] = Field(default_factory=list)
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# PYDANTIC MODELS - Writing Agent (AGENT-014)
# =============================================================================

class ReportSection(BaseModel):
    """A section of the report"""
    title: str
    content: str
    section_type: str = "body"  # executive_summary, introduction, body, conclusion, appendix
    order: int = 0
    subsections: List["ReportSection"] = Field(default_factory=list)


class Citation(BaseModel):
    """A citation reference"""
    id: str
    text: str
    source: str
    url: str = ""
    accessed_date: str = ""


class GeneratedReport(BaseModel):
    """A generated report"""
    title: str
    format: ReportFormat = ReportFormat.MARKDOWN
    sections: List[ReportSection] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    word_count: int = 0
    reading_time_minutes: int = 0


class WritingResult(BaseModel):
    """Complete result from Writing Agent (AGENT-014)"""
    task_id: str = ""
    report: Optional[GeneratedReport] = None
    raw_content: str = ""
    format: ReportFormat = ReportFormat.MARKDOWN
    style_guide_compliance: float = Field(ge=0.0, le=1.0, default=0.8)
    terminology_consistency: List[str] = Field(default_factory=list)
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# PYDANTIC MODELS - Review Agent (AGENT-015)
# =============================================================================

class ReviewIssue(BaseModel):
    """An issue found during review"""
    issue_type: IssueType
    severity: IssueSeverity
    location: str = ""  # Section or line reference
    description: str
    suggestion: str = ""
    auto_fixable: bool = False


class FactCheckResult(BaseModel):
    """Result of fact-checking a claim"""
    claim: str
    verified: bool
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    source: str = ""
    notes: str = ""


class ConsistencyCheck(BaseModel):
    """Result of consistency checking"""
    aspect: str  # terminology, formatting, tone, citations
    is_consistent: bool
    inconsistencies: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    """Complete result from Review Agent (AGENT-015)"""
    task_id: str = ""
    status: ReviewStatus = ReviewStatus.NEEDS_REVISION
    overall_quality_score: float = Field(ge=0.0, le=1.0, default=0.7)
    issues: List[ReviewIssue] = Field(default_factory=list)
    fact_checks: List[FactCheckResult] = Field(default_factory=list)
    consistency_checks: List[ConsistencyCheck] = Field(default_factory=list)
    grammar_score: float = Field(ge=0.0, le=1.0, default=0.8)
    clarity_score: float = Field(ge=0.0, le=1.0, default=0.8)
    completeness_score: float = Field(ge=0.0, le=1.0, default=0.8)
    strengths: List[str] = Field(default_factory=list)
    improvement_summary: str = ""
    approved_for_publication: bool = False
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Task 138: Revision loop enhancements
    revision_count: int = 0  # Track number of revisions
    revision_requested: bool = False  # Flag indicating revision needed
    quality_threshold: float = Field(ge=0.0, le=1.0, default=0.75)  # Minimum acceptable quality


# =============================================================================
# PYDANTIC MODELS - Orchestration Workflow
# =============================================================================

class WorkflowTask(BaseModel):
    """A task within the orchestration workflow"""
    task_id: str
    title: str
    description: str
    context: str = ""
    constraints: List[str] = Field(default_factory=list)
    expected_output: str = ""


class OrchestrationResult(BaseModel):
    """Complete result from multi-agent orchestration"""
    workflow_id: str = ""
    task: Optional[WorkflowTask] = None
    research_result: Optional[ResearchResult] = None
    analysis_result: Optional[AnalysisResult] = None
    writing_result: Optional[WritingResult] = None
    review_result: Optional[ReviewResult] = None
    final_output: str = ""
    workflow_completed: bool = False
    agents_used: List[str] = Field(default_factory=list)
    total_processing_time_ms: float = 0.0
    revision_count: int = 0
    errors: List[str] = Field(default_factory=list)
    # Task 138: Revision loop enhancements
    requires_human_review: bool = False  # Flag when max revisions reached without approval
    quality_score_history: List[float] = Field(default_factory=list)  # Track quality improvement
    revision_history: List[Dict[str, Any]] = Field(default_factory=list)  # Store revision details


# =============================================================================
# AGENT-012: RESEARCH AGENT
# =============================================================================

class ResearchAgent:
    """
    AGENT-012: Research Agent

    Conducts web and academic research, gathers information from multiple
    sources, and compiles findings for further analysis.
    """

    AGENT_ID = "AGENT-012"
    AGENT_NAME = "Research Agent"

    def __init__(self):
        self.config = ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.RESEARCH]
        self.llm = None

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.llm = ResilientAnthropicClient(
                api_key=api_key,
                service_name="research_agent",
                failure_threshold=5,
                recovery_timeout=60.0,
            )

        logger.info(f"{self.AGENT_ID} initialized", llm_available=self.llm is not None)

    async def research(
        self,
        query: str,
        task_id: str = "",
        search_types: Optional[List[ResearchSourceType]] = None,
        max_sources: int = 10,
        context: str = ""
    ) -> ResearchResult:
        """
        Conduct research on a given query.

        Args:
            query: The research query or topic
            task_id: Optional task identifier
            search_types: Types of sources to search (defaults to all)
            max_sources: Maximum number of sources to include
            context: Additional context for the research

        Returns:
            ResearchResult with gathered information
        """
        async with AgentMetricsContext(
            AgentID.RESEARCH_AGENT,
            "research",
            model=self.config["model"]
        ) as metrics_ctx:
            start_time = time.time()

            result = ResearchResult(
                task_id=task_id or hashlib.md5(query.encode()).hexdigest()[:12],
                original_query=query
            )

            if not self.llm:
                logger.warning("LLM not available for research")
                result.processing_time_ms = (time.time() - start_time) * 1000
                metrics_ctx.set_failure("llm_unavailable")
                return result

            try:
                search_types = search_types or list(ResearchSourceType)
                system_prompt = self._build_system_prompt(query, search_types, max_sources, context)

                response = await self.llm.messages.create(
                    model=self.config["model"],
                    max_tokens=self.config["max_tokens"],
                    temperature=self.config["temperature"],
                    messages=[
                        {"role": "user", "content": system_prompt}
                    ]
                )

                # Track LLM call metrics
                input_tokens = getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0
                output_tokens = getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0
                metrics_ctx.track_tokens(input_tokens=input_tokens, output_tokens=output_tokens)
                track_llm_call(
                    AgentID.RESEARCH_AGENT,
                    self.config["model"],
                    "success",
                    input_tokens,
                    output_tokens
                )

                response_text = response.content[0].text
                result = self._parse_research_response(response_text, result)
                metrics_ctx.set_success()

            except Exception as e:
                logger.error("Research failed", error=str(e))
                result.metadata["error"] = str(e)
                metrics_ctx.set_failure(type(e).__name__)

            result.processing_time_ms = (time.time() - start_time) * 1000
            return result

    def _build_system_prompt(
        self,
        query: str,
        search_types: List[ResearchSourceType],
        max_sources: int,
        context: str
    ) -> str:
        """Build the system prompt for research"""
        types_str = ", ".join([t.value for t in search_types])
        context_section = f"\n\nAdditional Context:\n{context}" if context else ""

        return f"""You are a Research Agent (AGENT-012) specializing in comprehensive information gathering.
Your task is to conduct thorough research on the following query.

Research Query: {query}

Source Types to Consider: {types_str}
Maximum Sources: {max_sources}
{context_section}

Respond ONLY with valid JSON in the following format:
{{
  "queries": [
    {{
      "original_query": "{query}",
      "expanded_queries": ["Alternative phrasing 1", "Related search 2"],
      "key_terms": ["term1", "term2"],
      "search_scope": "comprehensive"
    }}
  ],
  "sources": [
    {{
      "title": "Source Title",
      "url": "https://example.com/article",
      "source_type": "web|academic|news|internal|expert",
      "credibility_score": 0.85,
      "publication_date": "2024-01-15",
      "authors": ["Author Name"],
      "summary": "Brief summary of source content"
    }}
  ],
  "findings": [
    {{
      "finding": "Key finding or fact discovered",
      "relevance_score": 0.9,
      "sources": ["Source Title 1"],
      "confidence": 0.85,
      "keywords": ["keyword1", "keyword2"],
      "category": "Category name"
    }}
  ],
  "summary": "Overall summary of research findings",
  "gaps_identified": ["Information gap 1", "Gap 2"],
  "recommended_followup": ["Follow-up research topic 1", "Topic 2"]
}}

Research Guidelines:
- Expand the query into multiple search variations
- Prioritize credible, authoritative sources
- Cross-reference findings across multiple sources
- Identify gaps in available information
- Suggest areas for follow-up research
- Rate source credibility based on authority, recency, and corroboration
- Be thorough but focus on the most relevant information"""

    def _parse_research_response(
        self,
        response_text: str,
        result: ResearchResult
    ) -> ResearchResult:
        """Parse the LLM response into structured result"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return result

            data = json.loads(json_match.group())

            # Parse queries
            for query_data in data.get("queries", []):
                result.queries_executed.append(ResearchQuery(
                    original_query=query_data.get("original_query", ""),
                    expanded_queries=query_data.get("expanded_queries", []),
                    key_terms=query_data.get("key_terms", []),
                    search_scope=query_data.get("search_scope", "comprehensive")
                ))

            # Parse sources
            for source_data in data.get("sources", []):
                source_type_str = source_data.get("source_type", "web")
                try:
                    source_type = ResearchSourceType(source_type_str)
                except ValueError:
                    source_type = ResearchSourceType.WEB

                result.sources.append(ResearchSource(
                    title=source_data.get("title", ""),
                    url=source_data.get("url", ""),
                    source_type=source_type,
                    credibility_score=float(source_data.get("credibility_score", 0.7)),
                    publication_date=source_data.get("publication_date", ""),
                    authors=source_data.get("authors", []),
                    summary=source_data.get("summary", "")
                ))

            # Parse findings
            for finding_data in data.get("findings", []):
                result.findings.append(ResearchFinding(
                    finding=finding_data.get("finding", ""),
                    relevance_score=float(finding_data.get("relevance_score", 0.8)),
                    sources=finding_data.get("sources", []),
                    confidence=float(finding_data.get("confidence", 0.7)),
                    keywords=finding_data.get("keywords", []),
                    category=finding_data.get("category", "")
                ))

            result.summary = data.get("summary", "")
            result.gaps_identified = data.get("gaps_identified", [])
            result.recommended_followup = data.get("recommended_followup", [])

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse research JSON", error=str(e))
        except Exception as e:
            logger.error("Error parsing research response", error=str(e))

        return result


# =============================================================================
# AGENT-013: ANALYSIS AGENT
# =============================================================================

class AnalysisAgent:
    """
    AGENT-013: Analysis Agent

    Performs pattern detection, statistical analysis, and identifies
    insights from research data.
    """

    AGENT_ID = "AGENT-013"
    AGENT_NAME = "Analysis Agent"

    def __init__(self):
        self.config = ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.ANALYSIS]
        self.llm = None

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.llm = ResilientAnthropicClient(
                api_key=api_key,
                service_name="analysis_agent",
                failure_threshold=5,
                recovery_timeout=60.0,
            )

        logger.info(f"{self.AGENT_ID} initialized", llm_available=self.llm is not None)

    async def analyze(
        self,
        research_result: Optional[ResearchResult] = None,
        raw_data: str = "",
        task_id: str = "",
        analysis_focus: str = "comprehensive",
        detect_patterns: bool = True,
        compute_statistics: bool = True,
        find_correlations: bool = True
    ) -> AnalysisResult:
        """
        Analyze research findings or raw data.

        Args:
            research_result: Optional prior research result to analyze
            raw_data: Optional raw data to analyze
            task_id: Optional task identifier
            analysis_focus: Focus area for analysis
            detect_patterns: Whether to detect patterns
            compute_statistics: Whether to compute statistics
            find_correlations: Whether to find correlations

        Returns:
            AnalysisResult with patterns, statistics, and insights
        """
        async with AgentMetricsContext(
            AgentID.ANALYSIS_AGENT,
            "analyze",
            model=self.config["model"]
        ) as metrics_ctx:
            start_time = time.time()

            result = AnalysisResult(
                task_id=task_id or hashlib.md5(
                    (research_result.original_query if research_result else raw_data).encode()
                ).hexdigest()[:12]
            )

            if not self.llm:
                logger.warning("LLM not available for analysis")
                result.processing_time_ms = (time.time() - start_time) * 1000
                metrics_ctx.set_failure("llm_unavailable")
                return result

            try:
                # Prepare input data
                input_data = self._prepare_input_data(research_result, raw_data)

                system_prompt = self._build_system_prompt(
                    input_data, analysis_focus, detect_patterns,
                    compute_statistics, find_correlations
                )

                response = await self.llm.messages.create(
                    model=self.config["model"],
                    max_tokens=self.config["max_tokens"],
                    temperature=self.config["temperature"],
                    messages=[
                        {"role": "user", "content": system_prompt}
                    ]
                )

                # Track LLM call metrics
                input_tokens = getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0
                output_tokens = getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0
                metrics_ctx.track_tokens(input_tokens=input_tokens, output_tokens=output_tokens)
                track_llm_call(
                    AgentID.ANALYSIS_AGENT,
                    self.config["model"],
                    "success",
                    input_tokens,
                    output_tokens
                )

                response_text = response.content[0].text
                result = self._parse_analysis_response(response_text, result)

                # Track data quality score
                if result.data_quality_score:
                    track_quality_score(AgentID.ANALYSIS_AGENT, "analyze", result.data_quality_score)

                metrics_ctx.set_success()

            except Exception as e:
                logger.error("Analysis failed", error=str(e))
                result.metadata["error"] = str(e)
                metrics_ctx.set_failure(type(e).__name__)

            result.processing_time_ms = (time.time() - start_time) * 1000
            return result

    def _prepare_input_data(
        self,
        research_result: Optional[ResearchResult],
        raw_data: str
    ) -> str:
        """Prepare input data for analysis"""
        if research_result:
            data_parts = []
            data_parts.append(f"Research Query: {research_result.original_query}")
            data_parts.append(f"Summary: {research_result.summary}")

            if research_result.findings:
                findings_text = "\n".join([
                    f"- {f.finding} (confidence: {f.confidence}, category: {f.category})"
                    for f in research_result.findings
                ])
                data_parts.append(f"Findings:\n{findings_text}")

            if research_result.sources:
                sources_text = "\n".join([
                    f"- {s.title} ({s.source_type.value}, credibility: {s.credibility_score})"
                    for s in research_result.sources
                ])
                data_parts.append(f"Sources:\n{sources_text}")

            return "\n\n".join(data_parts)

        return raw_data

    def _build_system_prompt(
        self,
        input_data: str,
        analysis_focus: str,
        detect_patterns: bool,
        compute_statistics: bool,
        find_correlations: bool
    ) -> str:
        """Build the system prompt for analysis"""
        analysis_tasks = []
        if detect_patterns:
            analysis_tasks.append("pattern detection")
        if compute_statistics:
            analysis_tasks.append("statistical analysis")
        if find_correlations:
            analysis_tasks.append("correlation analysis")

        tasks_str = ", ".join(analysis_tasks) if analysis_tasks else "comprehensive analysis"

        return f"""You are an Analysis Agent (AGENT-013) specializing in data analysis and insight extraction.
Your task is to perform {tasks_str} on the provided data.

Analysis Focus: {analysis_focus}

Input Data:
{input_data[:8000]}

Respond ONLY with valid JSON in the following format:
{{
  "patterns": [
    {{
      "pattern_type": "trend|anomaly|correlation|cluster|outlier",
      "name": "Pattern Name",
      "description": "Detailed pattern description",
      "confidence": 0.85,
      "supporting_data": ["Data point 1", "Data point 2"],
      "significance": "high|medium|low",
      "visual_recommendation": "line_chart|bar_chart|scatter_plot|heatmap"
    }}
  ],
  "statistics": [
    {{
      "metric_name": "Metric Name",
      "value": "Value with units",
      "interpretation": "What this means",
      "comparison_baseline": "Comparison reference",
      "significance_level": "p < 0.05 or similar"
    }}
  ],
  "correlations": [
    {{
      "variable_1": "First variable",
      "variable_2": "Second variable",
      "correlation_type": "positive|negative|none",
      "strength": 0.75,
      "description": "Relationship description",
      "implications": "What this correlation implies"
    }}
  ],
  "key_insights": ["Insight 1", "Insight 2", "Insight 3"],
  "data_quality_score": 0.85,
  "limitations": ["Limitation 1", "Limitation 2"],
  "visualization_specs": [
    {{"type": "chart_type", "data_fields": ["field1", "field2"], "title": "Chart Title"}}
  ]
}}

Analysis Guidelines:
- Identify the most significant patterns in the data
- Calculate relevant descriptive statistics
- Look for correlations and relationships
- Prioritize actionable insights
- Note data quality issues and limitations
- Recommend appropriate visualizations
- Be rigorous and avoid overstating conclusions"""

    def _parse_analysis_response(
        self,
        response_text: str,
        result: AnalysisResult
    ) -> AnalysisResult:
        """Parse the LLM response into structured result"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return result

            data = json.loads(json_match.group())

            # Parse patterns
            for pattern_data in data.get("patterns", []):
                pattern_type_str = pattern_data.get("pattern_type", "trend")
                try:
                    pattern_type = PatternType(pattern_type_str)
                except ValueError:
                    pattern_type = PatternType.TREND

                result.patterns.append(DetectedPattern(
                    pattern_type=pattern_type,
                    name=pattern_data.get("name", ""),
                    description=pattern_data.get("description", ""),
                    confidence=float(pattern_data.get("confidence", 0.7)),
                    supporting_data=pattern_data.get("supporting_data", []),
                    significance=pattern_data.get("significance", "medium"),
                    visual_recommendation=pattern_data.get("visual_recommendation", "")
                ))

            # Parse statistics
            for stat_data in data.get("statistics", []):
                result.statistics.append(StatisticalInsight(
                    metric_name=stat_data.get("metric_name", ""),
                    value=stat_data.get("value", ""),
                    interpretation=stat_data.get("interpretation", ""),
                    comparison_baseline=stat_data.get("comparison_baseline", ""),
                    significance_level=stat_data.get("significance_level", "")
                ))

            # Parse correlations
            for corr_data in data.get("correlations", []):
                result.correlations.append(DataCorrelation(
                    variable_1=corr_data.get("variable_1", ""),
                    variable_2=corr_data.get("variable_2", ""),
                    correlation_type=corr_data.get("correlation_type", "none"),
                    strength=float(corr_data.get("strength", 0.5)),
                    description=corr_data.get("description", ""),
                    implications=corr_data.get("implications", "")
                ))

            result.key_insights = data.get("key_insights", [])
            result.data_quality_score = float(data.get("data_quality_score", 0.7))
            result.limitations = data.get("limitations", [])
            result.visualization_specs = data.get("visualization_specs", [])

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse analysis JSON", error=str(e))
        except Exception as e:
            logger.error("Error parsing analysis response", error=str(e))

        return result


# =============================================================================
# AGENT-014: WRITING AGENT
# =============================================================================

class WritingAgent:
    """
    AGENT-014: Writing Agent

    Generates reports, documentation, and structured content based on
    research and analysis results.
    """

    AGENT_ID = "AGENT-014"
    AGENT_NAME = "Writing Agent"

    def __init__(self):
        self.config = ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.WRITING]
        self.llm = None

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.llm = ResilientAnthropicClient(
                api_key=api_key,
                service_name="writing_agent",
                failure_threshold=5,
                recovery_timeout=60.0,
            )

        logger.info(f"{self.AGENT_ID} initialized", llm_available=self.llm is not None)

    async def write(
        self,
        task: WorkflowTask,
        research_result: Optional[ResearchResult] = None,
        analysis_result: Optional[AnalysisResult] = None,
        task_id: str = "",
        output_format: ReportFormat = ReportFormat.MARKDOWN,
        target_audience: str = "business professionals",
        max_length: int = 3000
    ) -> WritingResult:
        """
        Generate a report or document based on inputs.

        Args:
            task: The workflow task description
            research_result: Optional research findings
            analysis_result: Optional analysis results
            task_id: Optional task identifier
            output_format: Desired output format
            target_audience: Target audience for the content
            max_length: Maximum word count

        Returns:
            WritingResult with generated content
        """
        async with AgentMetricsContext(
            AgentID.WRITING_AGENT,
            "write",
            model=self.config["model"]
        ) as metrics_ctx:
            start_time = time.time()

            result = WritingResult(
                task_id=task_id or hashlib.md5(task.title.encode()).hexdigest()[:12],
                format=output_format
            )

            if not self.llm:
                logger.warning("LLM not available for writing")
                result.processing_time_ms = (time.time() - start_time) * 1000
                metrics_ctx.set_failure("llm_unavailable")
                return result

            try:
                # Prepare context
                context = self._prepare_context(task, research_result, analysis_result)

                system_prompt = self._build_system_prompt(
                    task, context, output_format, target_audience, max_length
                )

                response = await self.llm.messages.create(
                    model=self.config["model"],
                    max_tokens=self.config["max_tokens"],
                    temperature=self.config["temperature"],
                    messages=[
                        {"role": "user", "content": system_prompt}
                    ]
                )

                # Track LLM call metrics
                input_tokens = getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0
                output_tokens = getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0
                metrics_ctx.track_tokens(input_tokens=input_tokens, output_tokens=output_tokens)
                track_llm_call(
                    AgentID.WRITING_AGENT,
                    self.config["model"],
                    "success",
                    input_tokens,
                    output_tokens
                )

                response_text = response.content[0].text
                result = self._parse_writing_response(response_text, result, task.title)

                # Track style compliance score
                if result.style_guide_compliance:
                    track_quality_score(AgentID.WRITING_AGENT, "write", result.style_guide_compliance)

                metrics_ctx.set_success()

            except Exception as e:
                logger.error("Writing failed", error=str(e))
                result.metadata["error"] = str(e)
                metrics_ctx.set_failure(type(e).__name__)

            result.processing_time_ms = (time.time() - start_time) * 1000
            return result

    async def revise_content(
        self,
        original_writing: WritingResult,
        review_feedback: ReviewResult,
        task: WorkflowTask,
        revision_number: int,
        research_result: Optional[ResearchResult] = None,
        analysis_result: Optional[AnalysisResult] = None,
        output_format: ReportFormat = ReportFormat.MARKDOWN,
        target_audience: str = "business professionals"
    ) -> WritingResult:
        """
        Revise content based on review feedback (Task 138).

        This method specifically addresses review feedback to improve
        the quality of the generated content.

        Args:
            original_writing: The original writing result to revise
            review_feedback: Review result with issues and suggestions
            task: The original workflow task
            revision_number: Current revision iteration (1, 2, or 3)
            research_result: Optional research for reference
            analysis_result: Optional analysis for reference
            output_format: Output format
            target_audience: Target audience

        Returns:
            WritingResult with revised content
        """
        async with AgentMetricsContext(
            AgentID.WRITING_AGENT,
            "revise",
            model=self.config["model"]
        ) as metrics_ctx:
            start_time = time.time()

            result = WritingResult(
                task_id=original_writing.task_id,
                format=output_format
            )
            result.metadata["revision_number"] = revision_number
            result.metadata["original_quality_score"] = review_feedback.overall_quality_score

            if not self.llm:
                logger.warning("LLM not available for revision")
                result.processing_time_ms = (time.time() - start_time) * 1000
                metrics_ctx.set_failure("llm_unavailable")
                return result

            try:
                # Format the review feedback for the LLM
                formatted_feedback = self._format_feedback_for_revision(review_feedback)

                # Get original content
                original_content = original_writing.raw_content
                if not original_content and original_writing.report:
                    original_content = "\n\n".join([
                        f"## {s.title}\n{s.content}"
                        for s in original_writing.report.sections
                    ])

                revision_prompt = self._build_revision_prompt(
                    original_content=original_content,
                    formatted_feedback=formatted_feedback,
                    revision_number=revision_number,
                    task=task,
                    output_format=output_format,
                    target_audience=target_audience
                )

                response = await self.llm.messages.create(
                    model=self.config["model"],
                    max_tokens=self.config["max_tokens"],
                    temperature=max(0.3, self.config["temperature"] - 0.1),  # Slightly lower temp for revisions
                    messages=[
                        {"role": "user", "content": revision_prompt}
                    ]
                )

                # Track LLM call metrics
                input_tokens = getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0
                output_tokens = getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0
                metrics_ctx.track_tokens(input_tokens=input_tokens, output_tokens=output_tokens)
                track_llm_call(
                    AgentID.WRITING_AGENT,
                    self.config["model"],
                    "success",
                    input_tokens,
                    output_tokens
                )

                response_text = response.content[0].text
                result = self._parse_writing_response(response_text, result, task.title)

                logger.info(
                    "Content revised",
                    revision_number=revision_number,
                    task_id=original_writing.task_id,
                    original_quality=review_feedback.overall_quality_score
                )
                metrics_ctx.set_success()

            except Exception as e:
                logger.error("Revision failed", error=str(e), revision_number=revision_number)
                result.metadata["error"] = str(e)
                # Fall back to original content on error
                result.raw_content = original_writing.raw_content
                result.report = original_writing.report
                metrics_ctx.set_failure(type(e).__name__)

            result.processing_time_ms = (time.time() - start_time) * 1000
            return result

    def _format_feedback_for_revision(self, review: ReviewResult) -> str:
        """Format review feedback for the revision prompt"""
        feedback_parts = []

        # Overall assessment
        feedback_parts.append(f"Overall Quality Score: {review.overall_quality_score:.2f}")
        feedback_parts.append(f"Grammar Score: {review.grammar_score:.2f}")
        feedback_parts.append(f"Clarity Score: {review.clarity_score:.2f}")
        feedback_parts.append(f"Completeness Score: {review.completeness_score:.2f}")

        # Issues by severity
        if review.issues:
            critical_issues = [i for i in review.issues if i.severity == IssueSeverity.CRITICAL]
            major_issues = [i for i in review.issues if i.severity == IssueSeverity.MAJOR]
            minor_issues = [i for i in review.issues if i.severity == IssueSeverity.MINOR]

            if critical_issues:
                feedback_parts.append("\n**CRITICAL ISSUES (Must Fix):**")
                for issue in critical_issues:
                    feedback_parts.append(f"- [{issue.issue_type.value}] {issue.description}")
                    if issue.suggestion:
                        feedback_parts.append(f"  Suggestion: {issue.suggestion}")

            if major_issues:
                feedback_parts.append("\n**MAJOR ISSUES (Should Fix):**")
                for issue in major_issues:
                    feedback_parts.append(f"- [{issue.issue_type.value}] {issue.description}")
                    if issue.suggestion:
                        feedback_parts.append(f"  Suggestion: {issue.suggestion}")

            if minor_issues:
                feedback_parts.append("\n**MINOR ISSUES (Nice to Fix):**")
                for issue in minor_issues[:5]:  # Limit to top 5 minor issues
                    feedback_parts.append(f"- [{issue.issue_type.value}] {issue.description}")

        # Consistency issues
        inconsistent_checks = [c for c in review.consistency_checks if not c.is_consistent]
        if inconsistent_checks:
            feedback_parts.append("\n**CONSISTENCY ISSUES:**")
            for check in inconsistent_checks:
                feedback_parts.append(f"- {check.aspect}: {', '.join(check.inconsistencies)}")
                if check.recommendations:
                    feedback_parts.append(f"  Recommendations: {', '.join(check.recommendations)}")

        # Improvement summary
        if review.improvement_summary:
            feedback_parts.append(f"\n**IMPROVEMENT SUMMARY:**\n{review.improvement_summary}")

        return "\n".join(feedback_parts)

    def _build_revision_prompt(
        self,
        original_content: str,
        formatted_feedback: str,
        revision_number: int,
        task: WorkflowTask,
        output_format: ReportFormat,
        target_audience: str
    ) -> str:
        """Build the revision prompt"""
        return f"""You are a Writing Agent (AGENT-014) revising content based on review feedback.
This is REVISION #{revision_number}. Focus on addressing all feedback points.

TARGET AUDIENCE: {target_audience}
OUTPUT FORMAT: {output_format.value}

=== ORIGINAL CONTENT ===
{original_content[:10000]}

=== REVIEW FEEDBACK ===
{formatted_feedback}

=== REVISION INSTRUCTIONS ===
1. Address ALL critical issues first - these MUST be fixed
2. Fix all major issues to improve quality
3. Address minor issues where practical
4. Maintain the original purpose and key messages
5. Keep the same overall structure unless feedback specifically requests changes
6. Ensure terminology consistency throughout
7. Verify all cited sources remain accurate

Respond ONLY with valid JSON in the following format:
{{
  "report": {{
    "title": "Report Title",
    "sections": [
      {{
        "title": "Section Title",
        "content": "Revised section content...",
        "section_type": "executive_summary|introduction|body|conclusion",
        "order": 1
      }}
    ],
    "citations": [
      {{"id": "1", "text": "Citation text", "source": "Source name", "url": "https://..."}}
    ]
  }},
  "raw_content": "Complete revised document in {output_format.value} format...",
  "style_guide_compliance": 0.9,
  "terminology_consistency": ["term1", "term2"],
  "changes_made": ["Description of change 1", "Description of change 2"]
}}

Focus on quality improvement. The goal is to reach a quality score of 0.85 or higher."""

    def _prepare_context(
        self,
        task: WorkflowTask,
        research_result: Optional[ResearchResult],
        analysis_result: Optional[AnalysisResult]
    ) -> str:
        """Prepare context from prior agent results"""
        context_parts = []

        context_parts.append(f"Task: {task.title}")
        context_parts.append(f"Description: {task.description}")

        if task.context:
            context_parts.append(f"Additional Context: {task.context}")

        if research_result:
            context_parts.append("\n--- RESEARCH FINDINGS ---")
            context_parts.append(f"Summary: {research_result.summary}")

            if research_result.findings:
                findings = "\n".join([
                    f"• {f.finding}" for f in research_result.findings[:10]
                ])
                context_parts.append(f"Key Findings:\n{findings}")

            if research_result.sources:
                sources = "\n".join([
                    f"• {s.title}" for s in research_result.sources[:5]
                ])
                context_parts.append(f"Key Sources:\n{sources}")

        if analysis_result:
            context_parts.append("\n--- ANALYSIS RESULTS ---")

            if analysis_result.key_insights:
                insights = "\n".join([f"• {i}" for i in analysis_result.key_insights])
                context_parts.append(f"Key Insights:\n{insights}")

            if analysis_result.patterns:
                patterns = "\n".join([
                    f"• {p.name}: {p.description}" for p in analysis_result.patterns[:5]
                ])
                context_parts.append(f"Patterns Detected:\n{patterns}")

            if analysis_result.statistics:
                stats = "\n".join([
                    f"• {s.metric_name}: {s.value}" for s in analysis_result.statistics[:5]
                ])
                context_parts.append(f"Statistical Insights:\n{stats}")

        return "\n\n".join(context_parts)

    def _build_system_prompt(
        self,
        task: WorkflowTask,
        context: str,
        output_format: ReportFormat,
        target_audience: str,
        max_length: int
    ) -> str:
        """Build the system prompt for writing"""
        constraints = "\n".join([f"- {c}" for c in task.constraints]) if task.constraints else "None specified"

        return f"""You are a Writing Agent (AGENT-014) specializing in professional report and documentation generation.
Your task is to create a comprehensive, well-structured document based on the provided research and analysis.

Target Audience: {target_audience}
Output Format: {output_format.value}
Maximum Length: {max_length} words
Constraints:
{constraints}

Expected Output: {task.expected_output if task.expected_output else "A professional report addressing the task"}

{context[:10000]}

Respond ONLY with valid JSON in the following format:
{{
  "report": {{
    "title": "Report Title",
    "sections": [
      {{
        "title": "Executive Summary",
        "content": "Summary content...",
        "section_type": "executive_summary",
        "order": 1
      }},
      {{
        "title": "Introduction",
        "content": "Introduction content...",
        "section_type": "introduction",
        "order": 2
      }},
      {{
        "title": "Main Section Title",
        "content": "Main body content...",
        "section_type": "body",
        "order": 3
      }},
      {{
        "title": "Conclusions",
        "content": "Conclusions and recommendations...",
        "section_type": "conclusion",
        "order": 4
      }}
    ],
    "citations": [
      {{"id": "1", "text": "Citation text", "source": "Source name", "url": "https://..."}}
    ]
  }},
  "raw_content": "The complete document in {output_format.value} format...",
  "style_guide_compliance": 0.9,
  "terminology_consistency": ["term1", "term2"]
}}

Writing Guidelines:
- Write for the specified target audience
- Structure content with clear sections and headings
- Include an executive summary for quick overview
- Support claims with citations from research
- Maintain consistent terminology throughout
- Be concise but comprehensive
- Use appropriate formatting for the output format
- Ensure logical flow between sections"""

    def _parse_writing_response(
        self,
        response_text: str,
        result: WritingResult,
        title: str
    ) -> WritingResult:
        """Parse the LLM response into structured result"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                # If no JSON, treat entire response as raw content
                result.raw_content = response_text
                return result

            data = json.loads(json_match.group())

            # Parse report structure
            report_data = data.get("report", {})
            if report_data:
                sections = []
                for section_data in report_data.get("sections", []):
                    sections.append(ReportSection(
                        title=section_data.get("title", ""),
                        content=section_data.get("content", ""),
                        section_type=section_data.get("section_type", "body"),
                        order=int(section_data.get("order", 0))
                    ))

                citations = []
                for cit_data in report_data.get("citations", []):
                    citations.append(Citation(
                        id=str(cit_data.get("id", "")),
                        text=cit_data.get("text", ""),
                        source=cit_data.get("source", ""),
                        url=cit_data.get("url", "")
                    ))

                # Calculate word count
                total_content = " ".join([s.content for s in sections])
                word_count = len(total_content.split())

                result.report = GeneratedReport(
                    title=report_data.get("title", title),
                    format=result.format,
                    sections=sections,
                    citations=citations,
                    word_count=word_count,
                    reading_time_minutes=max(1, word_count // 200)
                )

            result.raw_content = data.get("raw_content", "")
            result.style_guide_compliance = float(data.get("style_guide_compliance", 0.8))
            result.terminology_consistency = data.get("terminology_consistency", [])

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse writing JSON", error=str(e))
            result.raw_content = response_text
        except Exception as e:
            logger.error("Error parsing writing response", error=str(e))

        return result


# =============================================================================
# AGENT-015: REVIEW AGENT
# =============================================================================

class ReviewAgent:
    """
    AGENT-015: Review Agent

    Performs quality assurance, fact-checking, and consistency validation
    on generated documents.
    """

    AGENT_ID = "AGENT-015"
    AGENT_NAME = "Review Agent"

    def __init__(self):
        self.config = ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.REVIEW]
        self.llm = None

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.llm = ResilientAnthropicClient(
                api_key=api_key,
                service_name="review_agent",
                failure_threshold=5,
                recovery_timeout=60.0,
            )

        logger.info(f"{self.AGENT_ID} initialized", llm_available=self.llm is not None)

    async def review(
        self,
        writing_result: WritingResult,
        research_result: Optional[ResearchResult] = None,
        task_id: str = "",
        check_facts: bool = True,
        check_consistency: bool = True,
        check_grammar: bool = True,
        strict_mode: bool = False
    ) -> ReviewResult:
        """
        Review a document for quality and accuracy.

        Args:
            writing_result: The document to review
            research_result: Original research for fact-checking
            task_id: Optional task identifier
            check_facts: Whether to verify facts
            check_consistency: Whether to check consistency
            check_grammar: Whether to check grammar
            strict_mode: Apply stricter review criteria

        Returns:
            ReviewResult with issues and recommendations
        """
        async with AgentMetricsContext(
            AgentID.REVIEW_AGENT,
            "review",
            model=self.config["model"]
        ) as metrics_ctx:
            start_time = time.time()

            result = ReviewResult(
                task_id=task_id or writing_result.task_id
            )

            if not self.llm:
                logger.warning("LLM not available for review")
                result.processing_time_ms = (time.time() - start_time) * 1000
                metrics_ctx.set_failure("llm_unavailable")
                return result

            try:
                # Prepare content for review
                content = self._prepare_review_content(writing_result, research_result)

                system_prompt = self._build_system_prompt(
                    content, check_facts, check_consistency, check_grammar, strict_mode
                )

                response = await self.llm.messages.create(
                    model=self.config["model"],
                    max_tokens=self.config["max_tokens"],
                    temperature=self.config["temperature"],
                    messages=[
                        {"role": "user", "content": system_prompt}
                    ]
                )

                # Track LLM call metrics
                input_tokens = getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0
                output_tokens = getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0
                metrics_ctx.track_tokens(input_tokens=input_tokens, output_tokens=output_tokens)
                track_llm_call(
                    AgentID.REVIEW_AGENT,
                    self.config["model"],
                    "success",
                    input_tokens,
                    output_tokens
                )

                response_text = response.content[0].text
                result = self._parse_review_response(response_text, result)

                # Determine overall status
                result.status = self._determine_status(result)
                result.approved_for_publication = result.status == ReviewStatus.APPROVED

                # Track quality scores
                if result.overall_quality_score:
                    track_quality_score(AgentID.REVIEW_AGENT, "review", result.overall_quality_score)
                    metrics_ctx.track_quality(result.overall_quality_score)

                metrics_ctx.set_success()

            except Exception as e:
                logger.error("Review failed", error=str(e))
                result.metadata["error"] = str(e)
                metrics_ctx.set_failure(type(e).__name__)

            result.processing_time_ms = (time.time() - start_time) * 1000
            return result

    def _prepare_review_content(
        self,
        writing_result: WritingResult,
        research_result: Optional[ResearchResult]
    ) -> str:
        """Prepare content for review"""
        parts = []

        # Include document content
        if writing_result.report:
            parts.append("=== DOCUMENT TO REVIEW ===")
            parts.append(f"Title: {writing_result.report.title}")
            for section in writing_result.report.sections:
                parts.append(f"\n## {section.title}\n{section.content}")

            if writing_result.report.citations:
                parts.append("\n## Citations")
                for cit in writing_result.report.citations:
                    parts.append(f"[{cit.id}] {cit.text} - {cit.source}")
        elif writing_result.raw_content:
            parts.append("=== DOCUMENT TO REVIEW ===")
            parts.append(writing_result.raw_content)

        # Include research for fact-checking
        if research_result:
            parts.append("\n=== REFERENCE RESEARCH ===")
            if research_result.findings:
                findings = "\n".join([f"• {f.finding}" for f in research_result.findings])
                parts.append(f"Research Findings:\n{findings}")

        return "\n\n".join(parts)

    def _build_system_prompt(
        self,
        content: str,
        check_facts: bool,
        check_consistency: bool,
        check_grammar: bool,
        strict_mode: bool
    ) -> str:
        """Build the system prompt for review"""
        checks = []
        if check_facts:
            checks.append("fact verification")
        if check_consistency:
            checks.append("consistency checking")
        if check_grammar:
            checks.append("grammar and spelling")

        checks_str = ", ".join(checks) if checks else "comprehensive review"
        mode_note = "Apply strict review criteria - flag all potential issues." if strict_mode else "Apply standard review criteria."

        return f"""You are a Review Agent (AGENT-015) specializing in document quality assurance.
Your task is to perform {checks_str} on the provided document.

{mode_note}

{content[:12000]}

Respond ONLY with valid JSON in the following format:
{{
  "overall_quality_score": 0.85,
  "grammar_score": 0.9,
  "clarity_score": 0.85,
  "completeness_score": 0.8,
  "issues": [
    {{
      "issue_type": "grammar|factual|consistency|citation|formatting|clarity|completeness",
      "severity": "critical|major|minor|suggestion",
      "location": "Section name or line reference",
      "description": "Description of the issue",
      "suggestion": "How to fix it",
      "auto_fixable": false
    }}
  ],
  "fact_checks": [
    {{
      "claim": "The claim being verified",
      "verified": true,
      "confidence": 0.9,
      "source": "Source that verifies this",
      "notes": "Additional notes"
    }}
  ],
  "consistency_checks": [
    {{
      "aspect": "terminology|formatting|tone|citations",
      "is_consistent": true,
      "inconsistencies": ["Inconsistency 1"],
      "recommendations": ["Recommendation 1"]
    }}
  ],
  "strengths": ["Strength 1", "Strength 2"],
  "improvement_summary": "Overall summary of needed improvements"
}}

Review Guidelines:
- Be thorough but fair in assessment
- Prioritize issues by severity
- Verify facts against provided research
- Check for terminology consistency
- Assess clarity for target audience
- Note both issues and strengths
- Provide actionable suggestions
- Critical issues must be addressed before publication
- Major issues should be addressed
- Minor issues are recommended fixes
- Suggestions are optional improvements"""

    def _parse_review_response(
        self,
        response_text: str,
        result: ReviewResult
    ) -> ReviewResult:
        """Parse the LLM response into structured result"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return result

            data = json.loads(json_match.group())

            result.overall_quality_score = float(data.get("overall_quality_score", 0.7))
            result.grammar_score = float(data.get("grammar_score", 0.8))
            result.clarity_score = float(data.get("clarity_score", 0.8))
            result.completeness_score = float(data.get("completeness_score", 0.8))

            # Parse issues
            for issue_data in data.get("issues", []):
                issue_type_str = issue_data.get("issue_type", "clarity")
                severity_str = issue_data.get("severity", "minor")

                try:
                    issue_type = IssueType(issue_type_str)
                except ValueError:
                    issue_type = IssueType.CLARITY

                try:
                    severity = IssueSeverity(severity_str)
                except ValueError:
                    severity = IssueSeverity.MINOR

                result.issues.append(ReviewIssue(
                    issue_type=issue_type,
                    severity=severity,
                    location=issue_data.get("location", ""),
                    description=issue_data.get("description", ""),
                    suggestion=issue_data.get("suggestion", ""),
                    auto_fixable=bool(issue_data.get("auto_fixable", False))
                ))

            # Parse fact checks
            for fc_data in data.get("fact_checks", []):
                result.fact_checks.append(FactCheckResult(
                    claim=fc_data.get("claim", ""),
                    verified=bool(fc_data.get("verified", False)),
                    confidence=float(fc_data.get("confidence", 0.5)),
                    source=fc_data.get("source", ""),
                    notes=fc_data.get("notes", "")
                ))

            # Parse consistency checks
            for cc_data in data.get("consistency_checks", []):
                result.consistency_checks.append(ConsistencyCheck(
                    aspect=cc_data.get("aspect", ""),
                    is_consistent=bool(cc_data.get("is_consistent", True)),
                    inconsistencies=cc_data.get("inconsistencies", []),
                    recommendations=cc_data.get("recommendations", [])
                ))

            result.strengths = data.get("strengths", [])
            result.improvement_summary = data.get("improvement_summary", "")

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse review JSON", error=str(e))
        except Exception as e:
            logger.error("Error parsing review response", error=str(e))

        return result

    def _determine_status(self, result: ReviewResult) -> ReviewStatus:
        """Determine overall review status based on issues"""
        critical_count = sum(1 for i in result.issues if i.severity == IssueSeverity.CRITICAL)
        major_count = sum(1 for i in result.issues if i.severity == IssueSeverity.MAJOR)

        if critical_count > 0:
            return ReviewStatus.MAJOR_ISSUES
        elif major_count > 2:
            return ReviewStatus.MAJOR_ISSUES
        elif major_count > 0 or result.overall_quality_score < 0.7:
            return ReviewStatus.NEEDS_REVISION
        elif result.overall_quality_score >= 0.85:
            return ReviewStatus.APPROVED
        else:
            return ReviewStatus.NEEDS_REVISION


# =============================================================================
# MULTI-AGENT ORCHESTRATION SERVICE
# =============================================================================

class MultiAgentOrchestrationService:
    """
    Orchestrates the sequential workflow of all four multi-agent orchestration agents.

    Workflow:
    1. AGENT-012 (Research Agent) gathers information
    2. AGENT-013 (Analysis Agent) analyzes findings
    3. AGENT-014 (Writing Agent) generates report
    4. AGENT-015 (Review Agent) validates quality

    Supports revision loops where Review Agent can send back to Writing Agent.
    """

    # Task 138: Quality threshold for approval
    QUALITY_THRESHOLD = 0.75
    MAX_REVISIONS = 3

    def __init__(self):
        self.research_agent = ResearchAgent()
        self.analysis_agent = AnalysisAgent()
        self.writing_agent = WritingAgent()
        self.review_agent = ReviewAgent()

        # Statistics (Task 138: Enhanced metrics)
        self._stats = {
            "workflows_completed": 0,
            "total_processing_time_ms": 0.0,
            "total_revisions": 0,
            "agents_invoked": {
                "AGENT-012": 0,
                "AGENT-013": 0,
                "AGENT-014": 0,
                "AGENT-015": 0
            },
            # Task 138: Revision-specific metrics
            "successful_first_pass": 0,  # Content approved without revisions
            "successful_after_revision": 0,  # Content approved after 1+ revisions
            "failed_after_max_revisions": 0,  # Content not approved after max revisions
            "total_quality_improvement": 0.0,  # Sum of quality score improvements
            "revision_distribution": {1: 0, 2: 0, 3: 0},  # How many times each revision count occurred
        }

        logger.info("MultiAgentOrchestrationService initialized")

    async def execute_workflow(
        self,
        task: WorkflowTask,
        run_research: bool = True,
        run_analysis: bool = True,
        run_writing: bool = True,
        run_review: bool = True,
        max_revisions: int = 2,
        output_format: ReportFormat = ReportFormat.MARKDOWN,
        target_audience: str = "business professionals"
    ) -> OrchestrationResult:
        """
        Execute the complete multi-agent workflow.

        Args:
            task: The workflow task to execute
            run_research: Whether to run Research Agent
            run_analysis: Whether to run Analysis Agent
            run_writing: Whether to run Writing Agent
            run_review: Whether to run Review Agent
            max_revisions: Maximum revision iterations
            output_format: Desired output format
            target_audience: Target audience for content

        Returns:
            OrchestrationResult with combined outputs
        """
        start_time = time.time()

        workflow_id = hashlib.md5(
            f"{task.task_id}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        result = OrchestrationResult(
            workflow_id=workflow_id,
            task=task
        )

        research_result = None
        analysis_result = None
        writing_result = None

        try:
            # Step 1: Research (AGENT-012)
            if run_research:
                logger.info("Starting research phase", workflow_id=workflow_id)
                research_result = await self.research_agent.research(
                    query=task.description,
                    task_id=task.task_id,
                    context=task.context
                )
                result.research_result = research_result
                result.agents_used.append("AGENT-012")
                self._stats["agents_invoked"]["AGENT-012"] += 1

            # Step 2: Analysis (AGENT-013)
            if run_analysis:
                logger.info("Starting analysis phase", workflow_id=workflow_id)
                analysis_result = await self.analysis_agent.analyze(
                    research_result=research_result,
                    raw_data=task.context if not research_result else "",
                    task_id=task.task_id
                )
                result.analysis_result = analysis_result
                result.agents_used.append("AGENT-013")
                self._stats["agents_invoked"]["AGENT-013"] += 1

            # Step 3: Writing (AGENT-014)
            if run_writing:
                logger.info("Starting writing phase", workflow_id=workflow_id)
                writing_result = await self.writing_agent.write(
                    task=task,
                    research_result=research_result,
                    analysis_result=analysis_result,
                    task_id=task.task_id,
                    output_format=output_format,
                    target_audience=target_audience
                )
                result.writing_result = writing_result
                result.agents_used.append("AGENT-014")
                self._stats["agents_invoked"]["AGENT-014"] += 1

            # Step 4: Review (AGENT-015) with enhanced revision loop (Task 138)
            if run_review and writing_result:
                revision_count = 0
                initial_quality_score = None

                while revision_count <= min(max_revisions, self.MAX_REVISIONS):
                    logger.info(
                        "Starting review phase",
                        workflow_id=workflow_id,
                        revision=revision_count
                    )

                    review_result = await self.review_agent.review(
                        writing_result=writing_result,
                        research_result=research_result,
                        task_id=task.task_id
                    )

                    # Track quality score history
                    result.quality_score_history.append(review_result.overall_quality_score)
                    if initial_quality_score is None:
                        initial_quality_score = review_result.overall_quality_score

                    # Update review result with revision tracking
                    review_result.revision_count = revision_count
                    review_result.quality_threshold = self.QUALITY_THRESHOLD
                    result.review_result = review_result
                    self._stats["agents_invoked"]["AGENT-015"] += 1

                    if "AGENT-015" not in result.agents_used:
                        result.agents_used.append("AGENT-015")

                    # Check if approved based on quality threshold
                    meets_threshold = review_result.overall_quality_score >= self.QUALITY_THRESHOLD
                    review_result.approved_for_publication = meets_threshold and review_result.status == ReviewStatus.APPROVED

                    # Record revision history entry
                    result.revision_history.append({
                        "revision_number": revision_count,
                        "quality_score": review_result.overall_quality_score,
                        "status": review_result.status.value,
                        "issues_count": len(review_result.issues),
                        "critical_issues": sum(1 for i in review_result.issues if i.severity == IssueSeverity.CRITICAL),
                        "approved": review_result.approved_for_publication
                    })

                    # Check if approved or max revisions reached
                    if review_result.approved_for_publication:
                        # Track success metrics
                        if revision_count == 0:
                            self._stats["successful_first_pass"] += 1
                            track_revision(AgentID.REVIEW_AGENT, "approved")
                        else:
                            self._stats["successful_after_revision"] += 1
                            self._stats["revision_distribution"][revision_count] = \
                                self._stats["revision_distribution"].get(revision_count, 0) + 1
                            track_revision(AgentID.REVIEW_AGENT, "approved")
                        break

                    if revision_count >= min(max_revisions, self.MAX_REVISIONS):
                        # Max revisions reached without approval
                        result.requires_human_review = True
                        self._stats["failed_after_max_revisions"] += 1
                        track_revision(AgentID.REVIEW_AGENT, "max_revisions")
                        logger.warning(
                            "Max revisions reached without approval",
                            workflow_id=workflow_id,
                            final_quality=review_result.overall_quality_score,
                            threshold=self.QUALITY_THRESHOLD
                        )
                        break

                    # If needs revision and not at max, use dedicated revise_content method
                    if review_result.status in [ReviewStatus.NEEDS_REVISION, ReviewStatus.MAJOR_ISSUES]:
                        revision_count += 1
                        self._stats["total_revisions"] += 1
                        review_result.revision_requested = True
                        track_revision(AgentID.REVIEW_AGENT, "rejected")

                        logger.info(
                            "Requesting revision",
                            workflow_id=workflow_id,
                            revision=revision_count,
                            current_quality=review_result.overall_quality_score,
                            threshold=self.QUALITY_THRESHOLD
                        )

                        # Use the new revise_content method (Task 138)
                        writing_result = await self.writing_agent.revise_content(
                            original_writing=writing_result,
                            review_feedback=review_result,
                            task=task,
                            revision_number=revision_count,
                            research_result=research_result,
                            analysis_result=analysis_result,
                            output_format=output_format,
                            target_audience=target_audience
                        )
                        result.writing_result = writing_result
                        self._stats["agents_invoked"]["AGENT-014"] += 1

                result.revision_count = revision_count

                # Track quality improvement
                if initial_quality_score is not None and result.quality_score_history:
                    final_quality = result.quality_score_history[-1]
                    quality_improvement = final_quality - initial_quality_score
                    if quality_improvement > 0:
                        self._stats["total_quality_improvement"] += quality_improvement

            # Set final output
            if result.writing_result:
                if result.writing_result.raw_content:
                    result.final_output = result.writing_result.raw_content
                elif result.writing_result.report:
                    sections_content = "\n\n".join([
                        f"# {s.title}\n\n{s.content}"
                        for s in sorted(result.writing_result.report.sections, key=lambda x: x.order)
                    ])
                    result.final_output = f"# {result.writing_result.report.title}\n\n{sections_content}"

            result.workflow_completed = True

        except Exception as e:
            logger.error("Multi-agent workflow failed", error=str(e), workflow_id=workflow_id)
            result.errors.append(str(e))

        result.total_processing_time_ms = (time.time() - start_time) * 1000

        # Update statistics
        self._stats["workflows_completed"] += 1
        self._stats["total_processing_time_ms"] += result.total_processing_time_ms

        # Track workflow metrics in Prometheus
        workflow_status = "success" if result.workflow_completed and not result.errors else "failure"
        track_workflow(
            "multi_agent_orchestration",
            workflow_status,
            result.total_processing_time_ms / 1000.0  # Convert to seconds
        )

        return result

    async def quick_research(
        self,
        query: str,
        context: str = ""
    ) -> ResearchResult:
        """Run only research phase"""
        self._stats["agents_invoked"]["AGENT-012"] += 1
        return await self.research_agent.research(query=query, context=context)

    async def analyze_data(
        self,
        data: str,
        analysis_focus: str = "comprehensive"
    ) -> AnalysisResult:
        """Run only analysis phase on raw data"""
        self._stats["agents_invoked"]["AGENT-013"] += 1
        return await self.analysis_agent.analyze(
            raw_data=data,
            analysis_focus=analysis_focus
        )

    async def generate_report(
        self,
        task: WorkflowTask,
        output_format: ReportFormat = ReportFormat.MARKDOWN
    ) -> WritingResult:
        """Generate report without prior research/analysis"""
        self._stats["agents_invoked"]["AGENT-014"] += 1
        return await self.writing_agent.write(
            task=task,
            output_format=output_format
        )

    async def review_document(
        self,
        writing_result: WritingResult,
        strict_mode: bool = False
    ) -> ReviewResult:
        """Review a document"""
        self._stats["agents_invoked"]["AGENT-015"] += 1
        return await self.review_agent.review(
            writing_result=writing_result,
            strict_mode=strict_mode
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get workflow statistics including Task 138 revision metrics"""
        total_workflows = self._stats["workflows_completed"]
        total_with_review = (
            self._stats["successful_first_pass"]
            + self._stats["successful_after_revision"]
            + self._stats["failed_after_max_revisions"]
        )

        # Calculate revision metrics
        revision_metrics = {
            "successful_first_pass": self._stats["successful_first_pass"],
            "successful_after_revision": self._stats["successful_after_revision"],
            "failed_after_max_revisions": self._stats["failed_after_max_revisions"],
            "total_quality_improvement": round(self._stats["total_quality_improvement"], 4),
            "revision_distribution": self._stats["revision_distribution"],
            # Derived metrics
            "first_pass_success_rate": round(
                self._stats["successful_first_pass"] / max(1, total_with_review), 4
            ),
            "revision_success_rate": round(
                self._stats["successful_after_revision"]
                / max(1, self._stats["successful_after_revision"] + self._stats["failed_after_max_revisions"]),
                4
            ),
            "average_quality_improvement_per_revision": round(
                self._stats["total_quality_improvement"] / max(1, self._stats["total_revisions"]), 4
            ),
            "quality_threshold": self.QUALITY_THRESHOLD,
            "max_revisions_allowed": self.MAX_REVISIONS,
        }

        return {
            "total_workflows": total_workflows,
            "total_revisions": self._stats["total_revisions"],
            "research_invocations": self._stats["agents_invoked"]["AGENT-012"],
            "analysis_invocations": self._stats["agents_invoked"]["AGENT-013"],
            "writing_invocations": self._stats["agents_invoked"]["AGENT-014"],
            "review_invocations": self._stats["agents_invoked"]["AGENT-015"],
            "average_processing_time_ms": (
                self._stats["total_processing_time_ms"] / max(1, total_workflows)
            ),
            # Task 138: Revision loop metrics
            "revision_metrics": revision_metrics,
            "agents": {
                "AGENT-012": {
                    "name": self.research_agent.AGENT_NAME,
                    "invocations": self._stats["agents_invoked"]["AGENT-012"]
                },
                "AGENT-013": {
                    "name": self.analysis_agent.AGENT_NAME,
                    "invocations": self._stats["agents_invoked"]["AGENT-013"]
                },
                "AGENT-014": {
                    "name": self.writing_agent.AGENT_NAME,
                    "invocations": self._stats["agents_invoked"]["AGENT-014"]
                },
                "AGENT-015": {
                    "name": self.review_agent.AGENT_NAME,
                    "invocations": self._stats["agents_invoked"]["AGENT-015"]
                }
            }
        }

    def reset_stats(self) -> None:
        """Reset workflow statistics"""
        self._stats = {
            "workflows_completed": 0,
            "total_processing_time_ms": 0.0,
            "total_revisions": 0,
            "agents_invoked": {
                "AGENT-012": 0,
                "AGENT-013": 0,
                "AGENT-014": 0,
                "AGENT-015": 0
            },
            # Task 138: Revision-specific metrics
            "successful_first_pass": 0,
            "successful_after_revision": 0,
            "failed_after_max_revisions": 0,
            "total_quality_improvement": 0.0,
            "revision_distribution": {1: 0, 2: 0, 3: 0},
        }

    def get_agent_info(self) -> List[Dict[str, Any]]:
        """Get information about all agents"""
        return [
            {
                "agent_id": self.research_agent.AGENT_ID,
                "name": self.research_agent.AGENT_NAME,
                "description": ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.RESEARCH]["description"],
                "model": ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.RESEARCH]["model"],
                "temperature": ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.RESEARCH]["temperature"],
                "capabilities": [
                    "web_search",
                    "academic_search",
                    "information_gathering",
                    "source_credibility_assessment",
                    "query_expansion"
                ]
            },
            {
                "agent_id": self.analysis_agent.AGENT_ID,
                "name": self.analysis_agent.AGENT_NAME,
                "description": ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.ANALYSIS]["description"],
                "model": ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.ANALYSIS]["model"],
                "temperature": ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.ANALYSIS]["temperature"],
                "capabilities": [
                    "pattern_detection",
                    "statistical_analysis",
                    "correlation_analysis",
                    "insight_extraction",
                    "visualization_recommendations"
                ]
            },
            {
                "agent_id": self.writing_agent.AGENT_ID,
                "name": self.writing_agent.AGENT_NAME,
                "description": ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.WRITING]["description"],
                "model": ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.WRITING]["model"],
                "temperature": ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.WRITING]["temperature"],
                "capabilities": [
                    "report_generation",
                    "document_formatting",
                    "citation_management",
                    "style_adaptation",
                    "multi_format_output"
                ]
            },
            {
                "agent_id": self.review_agent.AGENT_ID,
                "name": self.review_agent.AGENT_NAME,
                "description": ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.REVIEW]["description"],
                "model": ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.REVIEW]["model"],
                "temperature": ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.REVIEW]["temperature"],
                "capabilities": [
                    "quality_assurance",
                    "fact_verification",
                    "consistency_checking",
                    "grammar_review",
                    "improvement_suggestions"
                ]
            }
        ]


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_orchestration_service: Optional[MultiAgentOrchestrationService] = None


def get_multi_agent_orchestration_service() -> MultiAgentOrchestrationService:
    """Get or create singleton instance of MultiAgentOrchestrationService"""
    global _orchestration_service
    if _orchestration_service is None:
        _orchestration_service = MultiAgentOrchestrationService()
    return _orchestration_service
