"""
Empire v7.3 - Document Analysis Agents (Task 45)
AGENT-009: Senior Research Analyst
AGENT-010: Content Strategist
AGENT-011: Fact Checker

Three specialized agents for comprehensive document analysis workflows:
- AGENT-009: Extract topics, entities, facts, and quality assessment
- AGENT-010: Generate executive summaries, findings, and recommendations
- AGENT-011: Verify claims, assign confidence scores, provide citations

All agents use Claude Sonnet 4.5 with varying temperatures.

Author: Claude Code
Date: 2025-01-26
"""

import os
import re
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import asyncio

import structlog
from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class AgentRole(str, Enum):
    """Document analysis agent roles"""
    RESEARCH_ANALYST = "research_analyst"
    CONTENT_STRATEGIST = "content_strategist"
    FACT_CHECKER = "fact_checker"


class DocumentQuality(str, Enum):
    """Document quality assessment levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    NEEDS_REVIEW = "needs_review"


class VerificationStatus(str, Enum):
    """Fact verification status"""
    VERIFIED = "verified"
    LIKELY_TRUE = "likely_true"
    UNCERTAIN = "uncertain"
    LIKELY_FALSE = "likely_false"
    FALSE = "false"
    UNVERIFIABLE = "unverifiable"


class RecommendationPriority(str, Enum):
    """Recommendation priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


# Agent configurations
AGENT_CONFIGS = {
    AgentRole.RESEARCH_ANALYST: {
        "agent_id": "AGENT-009",
        "name": "Senior Research Analyst",
        "description": "Extracts topics, entities, facts, and assesses document quality",
        "model": "claude-sonnet-4-5-20250514",
        "temperature": 0.1,  # Low temperature for factual extraction
        "max_tokens": 4000
    },
    AgentRole.CONTENT_STRATEGIST: {
        "agent_id": "AGENT-010",
        "name": "Content Strategist",
        "description": "Generates executive summaries, findings, and recommendations",
        "model": "claude-sonnet-4-5-20250514",
        "temperature": 0.3,  # Slightly higher for creative synthesis
        "max_tokens": 3000
    },
    AgentRole.FACT_CHECKER: {
        "agent_id": "AGENT-011",
        "name": "Fact Checker",
        "description": "Verifies claims, assigns confidence scores, provides citations",
        "model": "claude-sonnet-4-5-20250514",
        "temperature": 0.0,  # Zero temperature for strict verification
        "max_tokens": 3000
    }
}


# =============================================================================
# PYDANTIC MODELS - Research Analyst (AGENT-009)
# =============================================================================

class ExtractedTopic(BaseModel):
    """A topic extracted from the document"""
    name: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    description: str = ""
    keywords: List[str] = Field(default_factory=list)


class ExtractedEntity(BaseModel):
    """An entity extracted from the document"""
    name: str
    entity_type: str  # person, organization, location, date, concept, etc.
    mentions: int = 1
    context: str = ""
    importance: float = Field(ge=0.0, le=1.0, default=0.5)


class ExtractedFact(BaseModel):
    """A fact extracted from the document"""
    statement: str
    source_location: str = ""  # Where in document this was found
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    supporting_evidence: str = ""
    related_entities: List[str] = Field(default_factory=list)


class QualityAssessment(BaseModel):
    """Document quality assessment"""
    overall_quality: DocumentQuality
    quality_score: float = Field(ge=0.0, le=1.0)
    clarity_score: float = Field(ge=0.0, le=1.0)
    completeness_score: float = Field(ge=0.0, le=1.0)
    accuracy_indicators: float = Field(ge=0.0, le=1.0)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)


class ResearchAnalysisResult(BaseModel):
    """Complete result from Research Analyst (AGENT-009)"""
    document_id: str = ""
    topics: List[ExtractedTopic] = Field(default_factory=list)
    entities: List[ExtractedEntity] = Field(default_factory=list)
    facts: List[ExtractedFact] = Field(default_factory=list)
    quality_assessment: Optional[QualityAssessment] = None
    word_count: int = 0
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# PYDANTIC MODELS - Content Strategist (AGENT-010)
# =============================================================================

class ExecutiveSummary(BaseModel):
    """Executive summary of the document"""
    title: str = ""
    summary: str
    key_points: List[str] = Field(default_factory=list)
    target_audience: str = ""
    reading_time_minutes: int = 1


class Finding(BaseModel):
    """A key finding from the document"""
    title: str
    description: str
    importance: str = "medium"  # critical, high, medium, low
    supporting_facts: List[str] = Field(default_factory=list)
    implications: str = ""


class Recommendation(BaseModel):
    """A recommendation based on the analysis"""
    title: str
    description: str
    priority: RecommendationPriority = RecommendationPriority.MEDIUM
    rationale: str = ""
    implementation_steps: List[str] = Field(default_factory=list)
    expected_impact: str = ""
    resources_needed: str = ""


class ContentStrategyResult(BaseModel):
    """Complete result from Content Strategist (AGENT-010)"""
    document_id: str = ""
    executive_summary: Optional[ExecutiveSummary] = None
    findings: List[Finding] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# PYDANTIC MODELS - Fact Checker (AGENT-011)
# =============================================================================

class ClaimVerification(BaseModel):
    """Verification result for a single claim"""
    claim: str
    status: VerificationStatus
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_evidence: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    verification_method: str = ""


class FactCheckResult(BaseModel):
    """Complete result from Fact Checker (AGENT-011)"""
    document_id: str = ""
    claims_checked: int = 0
    verified_claims: int = 0
    uncertain_claims: int = 0
    false_claims: int = 0
    verifications: List[ClaimVerification] = Field(default_factory=list)
    overall_credibility_score: float = Field(ge=0.0, le=1.0, default=0.5)
    credibility_assessment: str = ""
    red_flags: List[str] = Field(default_factory=list)
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# PYDANTIC MODELS - Combined Workflow
# =============================================================================

class DocumentAnalysisResult(BaseModel):
    """Combined result from all three agents"""
    document_id: str = ""
    title: str = ""
    research_analysis: Optional[ResearchAnalysisResult] = None
    content_strategy: Optional[ContentStrategyResult] = None
    fact_check: Optional[FactCheckResult] = None
    workflow_completed: bool = False
    total_processing_time_ms: float = 0.0
    agents_used: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


# =============================================================================
# AGENT-009: SENIOR RESEARCH ANALYST
# =============================================================================

class ResearchAnalystAgent:
    """
    AGENT-009: Senior Research Analyst

    Extracts topics, entities, facts, and performs quality assessment
    from documents using Claude Sonnet 4.5 with low temperature.
    """

    AGENT_ID = "AGENT-009"
    AGENT_NAME = "Senior Research Analyst"

    def __init__(self):
        self.config = AGENT_CONFIGS[AgentRole.RESEARCH_ANALYST]
        self.llm = None

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.llm = AsyncAnthropic(api_key=api_key)

        logger.info(f"{self.AGENT_ID} initialized", llm_available=self.llm is not None)

    async def analyze(
        self,
        content: str,
        document_id: str = "",
        extract_topics: bool = True,
        extract_entities: bool = True,
        extract_facts: bool = True,
        assess_quality: bool = True
    ) -> ResearchAnalysisResult:
        """
        Analyze document content and extract structured information.

        Args:
            content: Document content to analyze
            document_id: Optional document identifier
            extract_topics: Whether to extract topics
            extract_entities: Whether to extract entities
            extract_facts: Whether to extract facts
            assess_quality: Whether to assess document quality

        Returns:
            ResearchAnalysisResult with extracted information
        """
        import time
        start_time = time.time()

        result = ResearchAnalysisResult(
            document_id=document_id or hashlib.md5(content.encode()).hexdigest()[:12],
            word_count=len(content.split())
        )

        if not self.llm:
            logger.warning("LLM not available for research analysis")
            result.processing_time_ms = (time.time() - start_time) * 1000
            return result

        try:
            # Build analysis prompt
            analysis_tasks = []
            if extract_topics:
                analysis_tasks.append("TOPICS")
            if extract_entities:
                analysis_tasks.append("ENTITIES")
            if extract_facts:
                analysis_tasks.append("FACTS")
            if assess_quality:
                analysis_tasks.append("QUALITY")

            system_prompt = self._build_system_prompt(analysis_tasks)

            # Truncate content if too long
            content_sample = content[:12000] if len(content) > 12000 else content

            response = await self.llm.messages.create(
                model=self.config["model"],
                max_tokens=self.config["max_tokens"],
                temperature=self.config["temperature"],
                messages=[
                    {"role": "user", "content": f"{system_prompt}\n\nDocument to analyze:\n\n{content_sample}"}
                ]
            )

            response_text = response.content[0].text

            # Parse the structured response
            result = self._parse_analysis_response(response_text, result)

        except Exception as e:
            logger.error("Research analysis failed", error=str(e))
            result.metadata["error"] = str(e)

        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    def _build_system_prompt(self, tasks: List[str]) -> str:
        """Build the system prompt for analysis"""
        prompt = """You are a Senior Research Analyst (AGENT-009) specializing in document analysis.
Your task is to extract structured information from the provided document.

Respond ONLY with valid JSON in the following format:
{"""

        if "TOPICS" in tasks:
            prompt += """
  "topics": [
    {"name": "Topic Name", "relevance_score": 0.9, "description": "Brief description", "keywords": ["kw1", "kw2"]}
  ],"""

        if "ENTITIES" in tasks:
            prompt += """
  "entities": [
    {"name": "Entity Name", "entity_type": "person|organization|location|date|concept", "mentions": 3, "context": "How it appears", "importance": 0.8}
  ],"""

        if "FACTS" in tasks:
            prompt += """
  "facts": [
    {"statement": "The factual statement", "confidence": 0.9, "supporting_evidence": "Evidence from text", "related_entities": ["Entity1"]}
  ],"""

        if "QUALITY" in tasks:
            prompt += """
  "quality": {
    "overall_quality": "excellent|good|fair|poor|needs_review",
    "quality_score": 0.8,
    "clarity_score": 0.9,
    "completeness_score": 0.7,
    "accuracy_indicators": 0.85,
    "strengths": ["Strength 1", "Strength 2"],
    "weaknesses": ["Weakness 1"],
    "improvement_suggestions": ["Suggestion 1"]
  }"""

        prompt += """
}

Guidelines:
- Extract 3-7 main topics with relevance scores
- Identify all significant entities (people, organizations, locations, dates, key concepts)
- Extract 5-15 key factual statements with confidence scores
- Provide honest quality assessment based on clarity, completeness, and accuracy indicators
- Be thorough but concise"""

        return prompt

    def _parse_analysis_response(
        self,
        response_text: str,
        result: ResearchAnalysisResult
    ) -> ResearchAnalysisResult:
        """Parse the LLM response into structured result"""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return result

            data = json.loads(json_match.group())

            # Parse topics
            for topic_data in data.get("topics", []):
                result.topics.append(ExtractedTopic(
                    name=topic_data.get("name", ""),
                    relevance_score=float(topic_data.get("relevance_score", 0.5)),
                    description=topic_data.get("description", ""),
                    keywords=topic_data.get("keywords", [])
                ))

            # Parse entities
            for entity_data in data.get("entities", []):
                result.entities.append(ExtractedEntity(
                    name=entity_data.get("name", ""),
                    entity_type=entity_data.get("entity_type", "concept"),
                    mentions=int(entity_data.get("mentions", 1)),
                    context=entity_data.get("context", ""),
                    importance=float(entity_data.get("importance", 0.5))
                ))

            # Parse facts
            for fact_data in data.get("facts", []):
                result.facts.append(ExtractedFact(
                    statement=fact_data.get("statement", ""),
                    confidence=float(fact_data.get("confidence", 0.8)),
                    supporting_evidence=fact_data.get("supporting_evidence", ""),
                    related_entities=fact_data.get("related_entities", [])
                ))

            # Parse quality assessment
            quality_data = data.get("quality", {})
            if quality_data:
                quality_str = quality_data.get("overall_quality", "fair")
                try:
                    overall_quality = DocumentQuality(quality_str)
                except ValueError:
                    overall_quality = DocumentQuality.FAIR

                result.quality_assessment = QualityAssessment(
                    overall_quality=overall_quality,
                    quality_score=float(quality_data.get("quality_score", 0.5)),
                    clarity_score=float(quality_data.get("clarity_score", 0.5)),
                    completeness_score=float(quality_data.get("completeness_score", 0.5)),
                    accuracy_indicators=float(quality_data.get("accuracy_indicators", 0.5)),
                    strengths=quality_data.get("strengths", []),
                    weaknesses=quality_data.get("weaknesses", []),
                    improvement_suggestions=quality_data.get("improvement_suggestions", [])
                )

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse research analysis JSON", error=str(e))
        except Exception as e:
            logger.error("Error parsing research analysis", error=str(e))

        return result


# =============================================================================
# AGENT-010: CONTENT STRATEGIST
# =============================================================================

class ContentStrategistAgent:
    """
    AGENT-010: Content Strategist

    Generates executive summaries, findings, and recommendations
    from documents using Claude Sonnet 4.5.
    """

    AGENT_ID = "AGENT-010"
    AGENT_NAME = "Content Strategist"

    def __init__(self):
        self.config = AGENT_CONFIGS[AgentRole.CONTENT_STRATEGIST]
        self.llm = None

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.llm = AsyncAnthropic(api_key=api_key)

        logger.info(f"{self.AGENT_ID} initialized", llm_available=self.llm is not None)

    async def strategize(
        self,
        content: str,
        document_id: str = "",
        research_analysis: Optional[ResearchAnalysisResult] = None,
        generate_summary: bool = True,
        generate_findings: bool = True,
        generate_recommendations: bool = True,
        target_audience: str = "business professionals"
    ) -> ContentStrategyResult:
        """
        Generate strategic content from document analysis.

        Args:
            content: Document content
            document_id: Optional document identifier
            research_analysis: Optional prior research analysis to build upon
            generate_summary: Whether to generate executive summary
            generate_findings: Whether to extract key findings
            generate_recommendations: Whether to generate recommendations
            target_audience: Target audience for the content

        Returns:
            ContentStrategyResult with strategic content
        """
        import time
        start_time = time.time()

        result = ContentStrategyResult(
            document_id=document_id or hashlib.md5(content.encode()).hexdigest()[:12]
        )

        if not self.llm:
            logger.warning("LLM not available for content strategy")
            result.processing_time_ms = (time.time() - start_time) * 1000
            return result

        try:
            system_prompt = self._build_system_prompt(
                generate_summary, generate_findings, generate_recommendations,
                target_audience, research_analysis
            )

            # Include research analysis context if available
            context = ""
            if research_analysis:
                context = f"\n\nPrior Research Analysis:\n"
                if research_analysis.topics:
                    context += f"Main Topics: {', '.join(t.name for t in research_analysis.topics[:5])}\n"
                if research_analysis.facts:
                    context += f"Key Facts: {len(research_analysis.facts)} extracted\n"
                if research_analysis.quality_assessment:
                    context += f"Quality: {research_analysis.quality_assessment.overall_quality.value}\n"

            content_sample = content[:10000] if len(content) > 10000 else content

            response = await self.llm.messages.create(
                model=self.config["model"],
                max_tokens=self.config["max_tokens"],
                temperature=self.config["temperature"],
                messages=[
                    {"role": "user", "content": f"{system_prompt}{context}\n\nDocument:\n\n{content_sample}"}
                ]
            )

            response_text = response.content[0].text
            result = self._parse_strategy_response(response_text, result)

        except Exception as e:
            logger.error("Content strategy generation failed", error=str(e))
            result.metadata["error"] = str(e)

        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    def _build_system_prompt(
        self,
        generate_summary: bool,
        generate_findings: bool,
        generate_recommendations: bool,
        target_audience: str,
        research_analysis: Optional[ResearchAnalysisResult]
    ) -> str:
        """Build the system prompt for content strategy"""
        prompt = f"""You are a Content Strategist (AGENT-010) specializing in executive communication.
Your task is to transform document analysis into actionable strategic content for {target_audience}.

Respond ONLY with valid JSON in the following format:
{{"""

        if generate_summary:
            prompt += """
  "executive_summary": {
    "title": "Compelling title",
    "summary": "2-3 paragraph executive summary",
    "key_points": ["Point 1", "Point 2", "Point 3"],
    "target_audience": "Who should read this",
    "reading_time_minutes": 5
  },"""

        if generate_findings:
            prompt += """
  "findings": [
    {
      "title": "Finding title",
      "description": "Detailed description",
      "importance": "critical|high|medium|low",
      "supporting_facts": ["Fact 1", "Fact 2"],
      "implications": "What this means"
    }
  ],"""

        if generate_recommendations:
            prompt += """
  "recommendations": [
    {
      "title": "Recommendation title",
      "description": "What to do",
      "priority": "critical|high|medium|low|optional",
      "rationale": "Why this matters",
      "implementation_steps": ["Step 1", "Step 2"],
      "expected_impact": "Expected outcomes",
      "resources_needed": "Required resources"
    }
  ],
  "action_items": ["Immediate action 1", "Action 2"],
  "next_steps": ["Follow-up step 1", "Step 2"]"""

        prompt += """
}

Guidelines:
- Write for executives who have limited time
- Be specific and actionable
- Prioritize by business impact
- Include measurable outcomes where possible
- Keep summaries concise but comprehensive"""

        return prompt

    def _parse_strategy_response(
        self,
        response_text: str,
        result: ContentStrategyResult
    ) -> ContentStrategyResult:
        """Parse the LLM response into structured result"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return result

            data = json.loads(json_match.group())

            # Parse executive summary
            summary_data = data.get("executive_summary", {})
            if summary_data:
                result.executive_summary = ExecutiveSummary(
                    title=summary_data.get("title", ""),
                    summary=summary_data.get("summary", ""),
                    key_points=summary_data.get("key_points", []),
                    target_audience=summary_data.get("target_audience", ""),
                    reading_time_minutes=int(summary_data.get("reading_time_minutes", 5))
                )

            # Parse findings
            for finding_data in data.get("findings", []):
                result.findings.append(Finding(
                    title=finding_data.get("title", ""),
                    description=finding_data.get("description", ""),
                    importance=finding_data.get("importance", "medium"),
                    supporting_facts=finding_data.get("supporting_facts", []),
                    implications=finding_data.get("implications", "")
                ))

            # Parse recommendations
            for rec_data in data.get("recommendations", []):
                priority_str = rec_data.get("priority", "medium")
                try:
                    priority = RecommendationPriority(priority_str)
                except ValueError:
                    priority = RecommendationPriority.MEDIUM

                result.recommendations.append(Recommendation(
                    title=rec_data.get("title", ""),
                    description=rec_data.get("description", ""),
                    priority=priority,
                    rationale=rec_data.get("rationale", ""),
                    implementation_steps=rec_data.get("implementation_steps", []),
                    expected_impact=rec_data.get("expected_impact", ""),
                    resources_needed=rec_data.get("resources_needed", "")
                ))

            result.action_items = data.get("action_items", [])
            result.next_steps = data.get("next_steps", [])

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse content strategy JSON", error=str(e))
        except Exception as e:
            logger.error("Error parsing content strategy", error=str(e))

        return result


# =============================================================================
# AGENT-011: FACT CHECKER
# =============================================================================

class FactCheckerAgent:
    """
    AGENT-011: Fact Checker

    Verifies claims, assigns confidence scores, and provides citations
    using Claude Sonnet 4.5 with zero temperature for strict verification.
    """

    AGENT_ID = "AGENT-011"
    AGENT_NAME = "Fact Checker"

    def __init__(self):
        self.config = AGENT_CONFIGS[AgentRole.FACT_CHECKER]
        self.llm = None

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.llm = AsyncAnthropic(api_key=api_key)

        logger.info(f"{self.AGENT_ID} initialized", llm_available=self.llm is not None)

    async def verify(
        self,
        content: str,
        document_id: str = "",
        claims_to_verify: Optional[List[str]] = None,
        research_analysis: Optional[ResearchAnalysisResult] = None,
        max_claims: int = 15
    ) -> FactCheckResult:
        """
        Verify claims in the document.

        Args:
            content: Document content
            document_id: Optional document identifier
            claims_to_verify: Specific claims to verify (if None, extracts from content)
            research_analysis: Optional prior research analysis with extracted facts
            max_claims: Maximum number of claims to verify

        Returns:
            FactCheckResult with verification results
        """
        import time
        start_time = time.time()

        result = FactCheckResult(
            document_id=document_id or hashlib.md5(content.encode()).hexdigest()[:12]
        )

        if not self.llm:
            logger.warning("LLM not available for fact checking")
            result.processing_time_ms = (time.time() - start_time) * 1000
            return result

        try:
            # Get claims to verify
            claims = claims_to_verify or []

            # If no specific claims, use facts from research analysis or extract from content
            if not claims and research_analysis and research_analysis.facts:
                claims = [f.statement for f in research_analysis.facts[:max_claims]]

            system_prompt = self._build_system_prompt(claims, max_claims)

            content_sample = content[:10000] if len(content) > 10000 else content

            response = await self.llm.messages.create(
                model=self.config["model"],
                max_tokens=self.config["max_tokens"],
                temperature=self.config["temperature"],
                messages=[
                    {"role": "user", "content": f"{system_prompt}\n\nDocument:\n\n{content_sample}"}
                ]
            )

            response_text = response.content[0].text
            result = self._parse_verification_response(response_text, result)

            # Calculate summary statistics
            result.claims_checked = len(result.verifications)
            result.verified_claims = sum(
                1 for v in result.verifications
                if v.status in [VerificationStatus.VERIFIED, VerificationStatus.LIKELY_TRUE]
            )
            result.uncertain_claims = sum(
                1 for v in result.verifications
                if v.status in [VerificationStatus.UNCERTAIN, VerificationStatus.UNVERIFIABLE]
            )
            result.false_claims = sum(
                1 for v in result.verifications
                if v.status in [VerificationStatus.FALSE, VerificationStatus.LIKELY_FALSE]
            )

            # Calculate overall credibility
            if result.claims_checked > 0:
                credibility_weights = {
                    VerificationStatus.VERIFIED: 1.0,
                    VerificationStatus.LIKELY_TRUE: 0.8,
                    VerificationStatus.UNCERTAIN: 0.5,
                    VerificationStatus.UNVERIFIABLE: 0.5,
                    VerificationStatus.LIKELY_FALSE: 0.2,
                    VerificationStatus.FALSE: 0.0
                }
                total_credibility = sum(
                    credibility_weights.get(v.status, 0.5) * v.confidence
                    for v in result.verifications
                )
                result.overall_credibility_score = total_credibility / result.claims_checked

        except Exception as e:
            logger.error("Fact checking failed", error=str(e))
            result.metadata["error"] = str(e)

        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    def _build_system_prompt(self, claims: List[str], max_claims: int) -> str:
        """Build the system prompt for fact checking"""
        claims_section = ""
        if claims:
            claims_list = "\n".join(f"- {claim}" for claim in claims[:max_claims])
            claims_section = f"\n\nSpecific claims to verify:\n{claims_list}"

        prompt = f"""You are a Fact Checker (AGENT-011) specializing in claim verification.
Your task is to verify factual claims in the document and assess their accuracy.
{claims_section}

Respond ONLY with valid JSON in the following format:
{{
  "verifications": [
    {{
      "claim": "The exact claim being verified",
      "status": "verified|likely_true|uncertain|likely_false|false|unverifiable",
      "confidence": 0.85,
      "reasoning": "Explanation of verification process",
      "supporting_evidence": ["Evidence 1", "Evidence 2"],
      "contradicting_evidence": ["Contradiction 1"],
      "citations": ["Source 1", "Source 2"],
      "verification_method": "How this was verified"
    }}
  ],
  "credibility_assessment": "Overall assessment of document credibility",
  "red_flags": ["Potential issue 1", "Concern 2"]
}}

Verification Guidelines:
- verified: Claim is factually accurate with strong evidence
- likely_true: Claim appears accurate but lacks definitive proof
- uncertain: Cannot determine accuracy with available information
- likely_false: Evidence suggests claim may be inaccurate
- false: Claim is demonstrably incorrect
- unverifiable: Claim cannot be verified (opinion, future prediction, etc.)

Be rigorous and honest. If you cannot verify something, say so.
Check for logical consistency, factual accuracy, and potential biases."""

        return prompt

    def _parse_verification_response(
        self,
        response_text: str,
        result: FactCheckResult
    ) -> FactCheckResult:
        """Parse the LLM response into structured result"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return result

            data = json.loads(json_match.group())

            # Parse verifications
            for ver_data in data.get("verifications", []):
                status_str = ver_data.get("status", "uncertain")
                try:
                    status = VerificationStatus(status_str)
                except ValueError:
                    status = VerificationStatus.UNCERTAIN

                result.verifications.append(ClaimVerification(
                    claim=ver_data.get("claim", ""),
                    status=status,
                    confidence=float(ver_data.get("confidence", 0.5)),
                    reasoning=ver_data.get("reasoning", ""),
                    supporting_evidence=ver_data.get("supporting_evidence", []),
                    contradicting_evidence=ver_data.get("contradicting_evidence", []),
                    citations=ver_data.get("citations", []),
                    verification_method=ver_data.get("verification_method", "")
                ))

            result.credibility_assessment = data.get("credibility_assessment", "")
            result.red_flags = data.get("red_flags", [])

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse fact check JSON", error=str(e))
        except Exception as e:
            logger.error("Error parsing fact check", error=str(e))

        return result


# =============================================================================
# DOCUMENT ANALYSIS WORKFLOW SERVICE
# =============================================================================

class DocumentAnalysisWorkflowService:
    """
    Orchestrates the sequential workflow of all three document analysis agents.

    Workflow:
    1. AGENT-009 (Research Analyst) extracts topics, entities, facts
    2. AGENT-010 (Content Strategist) generates summaries and recommendations
    3. AGENT-011 (Fact Checker) verifies claims and assesses credibility
    """

    def __init__(self):
        self.research_analyst = ResearchAnalystAgent()
        self.content_strategist = ContentStrategistAgent()
        self.fact_checker = FactCheckerAgent()

        # Statistics
        self._stats = {
            "analyses_completed": 0,
            "total_processing_time_ms": 0.0,
            "agents_invoked": {
                "AGENT-009": 0,
                "AGENT-010": 0,
                "AGENT-011": 0
            }
        }

        logger.info("DocumentAnalysisWorkflowService initialized")

    async def analyze_document(
        self,
        content: str,
        title: str = "",
        document_id: str = "",
        run_research: bool = True,
        run_strategy: bool = True,
        run_fact_check: bool = True,
        target_audience: str = "business professionals"
    ) -> DocumentAnalysisResult:
        """
        Run the complete document analysis workflow.

        Args:
            content: Document content to analyze
            title: Document title
            document_id: Optional document identifier
            run_research: Whether to run Research Analyst
            run_strategy: Whether to run Content Strategist
            run_fact_check: Whether to run Fact Checker
            target_audience: Target audience for content strategy

        Returns:
            DocumentAnalysisResult with combined outputs
        """
        import time
        start_time = time.time()

        doc_id = document_id or hashlib.md5(content.encode()).hexdigest()[:12]

        result = DocumentAnalysisResult(
            document_id=doc_id,
            title=title
        )

        research_result = None

        try:
            # Step 1: Research Analysis (AGENT-009)
            if run_research:
                logger.info("Starting research analysis", document_id=doc_id)
                research_result = await self.research_analyst.analyze(
                    content=content,
                    document_id=doc_id
                )
                result.research_analysis = research_result
                result.agents_used.append("AGENT-009")
                self._stats["agents_invoked"]["AGENT-009"] += 1

            # Step 2: Content Strategy (AGENT-010)
            if run_strategy:
                logger.info("Starting content strategy", document_id=doc_id)
                strategy_result = await self.content_strategist.strategize(
                    content=content,
                    document_id=doc_id,
                    research_analysis=research_result,
                    target_audience=target_audience
                )
                result.content_strategy = strategy_result
                result.agents_used.append("AGENT-010")
                self._stats["agents_invoked"]["AGENT-010"] += 1

            # Step 3: Fact Checking (AGENT-011)
            if run_fact_check:
                logger.info("Starting fact check", document_id=doc_id)
                fact_result = await self.fact_checker.verify(
                    content=content,
                    document_id=doc_id,
                    research_analysis=research_result
                )
                result.fact_check = fact_result
                result.agents_used.append("AGENT-011")
                self._stats["agents_invoked"]["AGENT-011"] += 1

            result.workflow_completed = True

        except Exception as e:
            logger.error("Document analysis workflow failed", error=str(e))
            result.errors.append(str(e))

        result.total_processing_time_ms = (time.time() - start_time) * 1000

        # Update statistics
        self._stats["analyses_completed"] += 1
        self._stats["total_processing_time_ms"] += result.total_processing_time_ms

        return result

    async def quick_analysis(
        self,
        content: str,
        document_id: str = ""
    ) -> ResearchAnalysisResult:
        """
        Run only the research analysis for quick insights.

        Args:
            content: Document content
            document_id: Optional document identifier

        Returns:
            ResearchAnalysisResult
        """
        self._stats["agents_invoked"]["AGENT-009"] += 1
        return await self.research_analyst.analyze(content, document_id)

    async def get_summary(
        self,
        content: str,
        target_audience: str = "business professionals"
    ) -> ContentStrategyResult:
        """
        Generate only the executive summary and recommendations.

        Args:
            content: Document content
            target_audience: Target audience

        Returns:
            ContentStrategyResult
        """
        self._stats["agents_invoked"]["AGENT-010"] += 1
        return await self.content_strategist.strategize(
            content=content,
            target_audience=target_audience
        )

    async def verify_claims(
        self,
        content: str,
        claims: Optional[List[str]] = None
    ) -> FactCheckResult:
        """
        Verify specific claims or extract and verify claims from content.

        Args:
            content: Document content
            claims: Optional specific claims to verify

        Returns:
            FactCheckResult
        """
        self._stats["agents_invoked"]["AGENT-011"] += 1
        return await self.fact_checker.verify(
            content=content,
            claims_to_verify=claims
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get workflow statistics"""
        return {
            "total_analyses": self._stats["analyses_completed"],
            "research_analyses": self._stats["agents_invoked"]["AGENT-009"],
            "content_strategies": self._stats["agents_invoked"]["AGENT-010"],
            "fact_checks": self._stats["agents_invoked"]["AGENT-011"],
            "average_processing_time_ms": (
                self._stats["total_processing_time_ms"] / max(1, self._stats["analyses_completed"])
            ),
            "agents": {
                "AGENT-009": {
                    "name": self.research_analyst.AGENT_NAME,
                    "invocations": self._stats["agents_invoked"]["AGENT-009"]
                },
                "AGENT-010": {
                    "name": self.content_strategist.AGENT_NAME,
                    "invocations": self._stats["agents_invoked"]["AGENT-010"]
                },
                "AGENT-011": {
                    "name": self.fact_checker.AGENT_NAME,
                    "invocations": self._stats["agents_invoked"]["AGENT-011"]
                }
            }
        }

    def reset_stats(self) -> None:
        """Reset workflow statistics"""
        self._stats = {
            "analyses_completed": 0,
            "total_processing_time_ms": 0.0,
            "agents_invoked": {
                "AGENT-009": 0,
                "AGENT-010": 0,
                "AGENT-011": 0
            }
        }

    def get_agent_info(self) -> List[Dict[str, Any]]:
        """Get information about all agents"""
        return [
            {
                "agent_id": self.research_analyst.AGENT_ID,
                "name": self.research_analyst.AGENT_NAME,
                "description": AGENT_CONFIGS[AgentRole.RESEARCH_ANALYST]["description"],
                "model": AGENT_CONFIGS[AgentRole.RESEARCH_ANALYST]["model"],
                "temperature": AGENT_CONFIGS[AgentRole.RESEARCH_ANALYST]["temperature"],
                "capabilities": [
                    "topic_extraction",
                    "entity_recognition",
                    "fact_extraction",
                    "quality_assessment"
                ]
            },
            {
                "agent_id": self.content_strategist.AGENT_ID,
                "name": self.content_strategist.AGENT_NAME,
                "description": AGENT_CONFIGS[AgentRole.CONTENT_STRATEGIST]["description"],
                "model": AGENT_CONFIGS[AgentRole.CONTENT_STRATEGIST]["model"],
                "temperature": AGENT_CONFIGS[AgentRole.CONTENT_STRATEGIST]["temperature"],
                "capabilities": [
                    "executive_summary",
                    "key_findings",
                    "recommendations",
                    "action_items"
                ]
            },
            {
                "agent_id": self.fact_checker.AGENT_ID,
                "name": self.fact_checker.AGENT_NAME,
                "description": AGENT_CONFIGS[AgentRole.FACT_CHECKER]["description"],
                "model": AGENT_CONFIGS[AgentRole.FACT_CHECKER]["model"],
                "temperature": AGENT_CONFIGS[AgentRole.FACT_CHECKER]["temperature"],
                "capabilities": [
                    "claim_verification",
                    "credibility_assessment",
                    "evidence_analysis",
                    "red_flag_detection"
                ]
            }
        ]


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_workflow_service: Optional[DocumentAnalysisWorkflowService] = None


def get_document_analysis_workflow_service() -> DocumentAnalysisWorkflowService:
    """Get or create singleton instance of DocumentAnalysisWorkflowService"""
    global _workflow_service
    if _workflow_service is None:
        _workflow_service = DocumentAnalysisWorkflowService()
    return _workflow_service
