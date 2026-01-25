"""
Empire v7.3 - Answer Grounding Evaluator Service (Task 144)

Verifies answer claims against source documents to prevent hallucinations.
Part of the RAG Enhancement Services (Feature 008).

Features:
- Claim extraction from answers using LLM
- Claim-to-source alignment scoring (0-1)
- Calculation of overall grounding score and confidence level
- Flagging of ungrounded claims
- Blocking of answers below critical grounding threshold

Author: Claude Code
Date: 2025-01-14
"""

import os
import re
import json
import uuid
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

import structlog
from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from app.services.api_resilience import ResilientAnthropicClient, CircuitOpenError

logger = structlog.get_logger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class ConfidenceLevel(str, Enum):
    """Confidence level for grounding"""
    HIGH = "high"      # >= 0.8 grounding score
    MEDIUM = "medium"  # >= 0.5 grounding score
    LOW = "low"        # < 0.5 grounding score


class ClaimStatus(str, Enum):
    """Status of individual claims"""
    GROUNDED = "grounded"          # Claim supported by sources
    PARTIALLY_GROUNDED = "partially_grounded"  # Partially supported
    UNGROUNDED = "ungrounded"      # Not supported by sources
    CONTRADICTED = "contradicted"  # Contradicts sources


# Thresholds
GROUNDING_THRESHOLDS = {
    "high": 0.8,
    "medium": 0.5,
    "critical": 0.3,  # Below this, block the answer
}


# =============================================================================
# DATA MODELS
# =============================================================================

class SupportingSource(BaseModel):
    """A source that supports a claim"""
    source_index: int = Field(..., description="Index of the source context")
    chunk_text: str = Field(..., description="Relevant chunk from source")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="How well this source supports the claim")


class ClaimAnalysis(BaseModel):
    """Analysis of a single claim"""
    claim_text: str = Field(..., description="The extracted claim")
    claim_index: int = Field(..., description="Position in the answer")
    grounding_score: float = Field(..., ge=0.0, le=1.0, description="How well grounded this claim is")
    status: ClaimStatus = Field(..., description="Grounding status")
    supporting_sources: List[SupportingSource] = Field(default_factory=list)
    reasoning: Optional[str] = Field(None, description="Why this score was assigned")


class GroundingResult(BaseModel):
    """Complete grounding analysis result"""
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_claims: int = Field(..., description="Total number of claims extracted")
    grounded_claims: int = Field(..., description="Number of well-grounded claims")
    partially_grounded_claims: int = Field(0, description="Number of partially grounded claims")
    ungrounded_claims: int = Field(..., description="Number of ungrounded claims")
    contradicted_claims: int = Field(0, description="Number of contradicted claims")
    claim_details: List[ClaimAnalysis] = Field(default_factory=list)
    overall_grounding_score: float = Field(..., ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel = Field(...)
    should_block: bool = Field(False, description="Whether to block this answer")
    warning_message: Optional[str] = Field(None, description="Warning for low confidence")


class GroundingRequest(BaseModel):
    """Request for grounding evaluation"""
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    source_contexts: List[str] = Field(..., min_items=1)
    critical_threshold: float = Field(0.3, ge=0.0, le=1.0)


# =============================================================================
# ANSWER GROUNDING EVALUATOR SERVICE
# =============================================================================

class AnswerGroundingEvaluator:
    """
    Verifies answer claims against source documents.

    Pipeline:
    1. Extract claims from the answer
    2. For each claim, search for supporting evidence in sources
    3. Calculate grounding score per claim
    4. Aggregate to overall grounding score
    5. Determine confidence level and blocking decision
    """

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        use_resilient_client: bool = True,
        critical_threshold: float = 0.3,
        supabase_client: Optional[Any] = None,
    ):
        """
        Initialize the Answer Grounding Evaluator.

        Args:
            anthropic_api_key: Anthropic API key
            use_resilient_client: Whether to use circuit breaker pattern
            critical_threshold: Threshold below which to block answers
            supabase_client: Supabase client for storing results
        """
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.use_resilient_client = use_resilient_client
        self.critical_threshold = critical_threshold
        self.supabase = supabase_client

        # Initialize Anthropic client
        if use_resilient_client:
            self.client = ResilientAnthropicClient(api_key=self.api_key)
        else:
            self.client = AsyncAnthropic(api_key=self.api_key)

        # Model for evaluation
        self.model = "claude-haiku-4-5"

        logger.info(
            "AnswerGroundingEvaluator initialized",
            use_resilient_client=use_resilient_client,
            critical_threshold=critical_threshold,
            model=self.model
        )

    async def _extract_claims(self, answer: str) -> List[str]:
        """
        Extract factual claims from the answer.

        Returns a list of distinct claims that can be verified.
        """
        prompt = f"""Extract all factual claims from this answer that can be verified against source documents.

Answer:
"{answer}"

Rules:
1. Break down compound statements into individual claims
2. Include specific facts, numbers, dates, names
3. Include assertions about relationships or causation
4. Exclude opinions, hedged statements ("might be", "could be")
5. Exclude general knowledge that doesn't need sourcing

Respond with JSON only:
{{"claims": ["claim 1", "claim 2", "claim 3", ...]}}

Extract up to 10 key claims."""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                claims = data.get("claims", [])
                # Filter empty claims
                return [c.strip() for c in claims if c.strip()][:10]

        except Exception as e:
            logger.warning("Claim extraction failed", error=str(e))

        # Fallback: split by sentences (basic extraction)
        sentences = re.split(r'[.!?]+', answer)
        claims = [s.strip() for s in sentences if len(s.strip()) > 20]
        return claims[:10]

    async def _evaluate_claim_grounding(
        self,
        claim: str,
        sources: List[str]
    ) -> Tuple[float, ClaimStatus, List[SupportingSource], str]:
        """
        Evaluate how well a claim is grounded in the sources.

        Returns:
            Tuple of (grounding_score, status, supporting_sources, reasoning)
        """
        # Combine sources with indices for reference
        indexed_sources = "\n\n".join([
            f"[Source {i+1}]: {src[:500]}{'...' if len(src) > 500 else ''}"
            for i, src in enumerate(sources[:5])
        ])

        prompt = f"""Evaluate if this claim is supported by the provided sources.

Claim: "{claim}"

Sources:
{indexed_sources}

Evaluate:
1. Is the claim directly stated in any source?
2. Is it implied or can be inferred from sources?
3. Is it contradicted by any source?
4. Is there no relevant information in sources?

Rate grounding from 0.0 to 1.0:
- 1.0: Directly stated in sources with exact match
- 0.8-0.9: Strongly supported with clear evidence
- 0.5-0.7: Partially supported or implied
- 0.2-0.4: Weakly supported, requires inference
- 0.0-0.1: Not supported or contradicted

Respond with JSON only:
{{
    "grounding_score": 0.8,
    "status": "grounded|partially_grounded|ungrounded|contradicted",
    "supporting_sources": [
        {{"source_index": 1, "relevance": 0.9, "relevant_text": "key quote"}}
    ],
    "reasoning": "brief explanation"
}}"""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                grounding_score = float(data.get("grounding_score", 0.5))
                status_str = data.get("status", "ungrounded")
                reasoning = data.get("reasoning", "")

                # Map status
                status_map = {
                    "grounded": ClaimStatus.GROUNDED,
                    "partially_grounded": ClaimStatus.PARTIALLY_GROUNDED,
                    "ungrounded": ClaimStatus.UNGROUNDED,
                    "contradicted": ClaimStatus.CONTRADICTED,
                }
                status = status_map.get(status_str, ClaimStatus.UNGROUNDED)

                # Build supporting sources
                supporting_sources = []
                for src_data in data.get("supporting_sources", []):
                    try:
                        supporting_sources.append(SupportingSource(
                            source_index=int(src_data.get("source_index", 0)) - 1,  # Convert to 0-indexed
                            chunk_text=str(src_data.get("relevant_text", ""))[:200],
                            relevance_score=float(src_data.get("relevance", 0.5))
                        ))
                    except (ValueError, TypeError):
                        continue

                return grounding_score, status, supporting_sources, reasoning

        except Exception as e:
            logger.warning("Claim grounding evaluation failed", error=str(e), claim=claim[:50])

        return 0.5, ClaimStatus.UNGROUNDED, [], "Evaluation failed"

    def _calculate_overall_score(self, claim_analyses: List[ClaimAnalysis]) -> float:
        """
        Calculate overall grounding score from individual claims.

        Uses weighted average where contradicted claims have extra penalty.
        """
        if not claim_analyses:
            return 0.5

        total_weight = 0.0
        weighted_sum = 0.0

        for analysis in claim_analyses:
            # Weight by importance (contradictions are more serious)
            if analysis.status == ClaimStatus.CONTRADICTED:
                weight = 2.0  # Double weight for contradictions
            elif analysis.status == ClaimStatus.GROUNDED:
                weight = 1.0
            else:
                weight = 1.0

            weighted_sum += analysis.grounding_score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.5

        return weighted_sum / total_weight

    def _get_confidence_level(self, score: float) -> ConfidenceLevel:
        """Determine confidence level from score"""
        if score >= GROUNDING_THRESHOLDS["high"]:
            return ConfidenceLevel.HIGH
        elif score >= GROUNDING_THRESHOLDS["medium"]:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _generate_warning(self, result: GroundingResult) -> Optional[str]:
        """Generate warning message for low confidence answers"""
        if result.confidence_level == ConfidenceLevel.HIGH:
            return None

        if result.should_block:
            return "This response has been blocked due to insufficient source support."

        if result.ungrounded_claims > 0 or result.contradicted_claims > 0:
            issues = []
            if result.ungrounded_claims > 0:
                issues.append(f"{result.ungrounded_claims} unverified claim(s)")
            if result.contradicted_claims > 0:
                issues.append(f"{result.contradicted_claims} potentially incorrect claim(s)")

            return f"Low confidence warning: {', '.join(issues)}. Please verify with original sources."

        if result.confidence_level == ConfidenceLevel.MEDIUM:
            return "Moderate confidence: Some claims may not be fully supported by sources."

        return "Low confidence: Limited source support for this response."

    async def evaluate(
        self,
        answer: str,
        source_contexts: List[str],
        query: Optional[str] = None,
        critical_threshold: Optional[float] = None
    ) -> GroundingResult:
        """
        Evaluate answer grounding against sources.

        Args:
            answer: The generated answer to evaluate
            source_contexts: Source documents/chunks
            query: Original query (for context)
            critical_threshold: Override critical threshold

        Returns:
            GroundingResult with detailed analysis
        """
        start_time = datetime.now()
        threshold = critical_threshold or self.critical_threshold

        # Extract claims
        claims = await self._extract_claims(answer)

        if not claims:
            logger.info("No claims extracted from answer")
            return GroundingResult(
                total_claims=0,
                grounded_claims=0,
                ungrounded_claims=0,
                claim_details=[],
                overall_grounding_score=1.0,  # No claims = nothing to verify
                confidence_level=ConfidenceLevel.HIGH,
                should_block=False
            )

        # Evaluate each claim concurrently
        claim_tasks = [
            self._evaluate_claim_grounding(claim, source_contexts)
            for claim in claims
        ]
        claim_results = await asyncio.gather(*claim_tasks)

        # Build claim analyses
        claim_analyses = []
        grounded_count = 0
        partially_grounded_count = 0
        ungrounded_count = 0
        contradicted_count = 0

        for i, (claim, result) in enumerate(zip(claims, claim_results)):
            score, status, sources, reasoning = result

            analysis = ClaimAnalysis(
                claim_text=claim,
                claim_index=i,
                grounding_score=score,
                status=status,
                supporting_sources=sources,
                reasoning=reasoning
            )
            claim_analyses.append(analysis)

            # Count by status
            if status == ClaimStatus.GROUNDED:
                grounded_count += 1
            elif status == ClaimStatus.PARTIALLY_GROUNDED:
                partially_grounded_count += 1
            elif status == ClaimStatus.CONTRADICTED:
                contradicted_count += 1
            else:
                ungrounded_count += 1

        # Calculate overall score
        overall_score = self._calculate_overall_score(claim_analyses)
        confidence_level = self._get_confidence_level(overall_score)

        # Determine if should block
        should_block = overall_score < threshold

        result = GroundingResult(
            total_claims=len(claims),
            grounded_claims=grounded_count,
            partially_grounded_claims=partially_grounded_count,
            ungrounded_claims=ungrounded_count,
            contradicted_claims=contradicted_count,
            claim_details=claim_analyses,
            overall_grounding_score=overall_score,
            confidence_level=confidence_level,
            should_block=should_block
        )

        # Generate warning if needed
        result.warning_message = self._generate_warning(result)

        elapsed = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            "Grounding evaluation complete",
            total_claims=len(claims),
            grounded=grounded_count,
            ungrounded=ungrounded_count,
            overall_score=overall_score,
            confidence=confidence_level.value,
            should_block=should_block,
            elapsed_ms=int(elapsed)
        )

        return result

    async def store_result(
        self,
        query_id: str,
        result: GroundingResult
    ) -> bool:
        """
        Store grounding result in database.

        Args:
            query_id: Query identifier
            result: Grounding result to store

        Returns:
            True if stored successfully
        """
        if not self.supabase:
            logger.warning("Supabase client not configured")
            return False

        try:
            # Convert claim details to JSON-serializable format
            claim_details_json = [
                {
                    "claim": ca.claim_text,
                    "grounding_score": ca.grounding_score,
                    "status": ca.status.value,
                    "supporting_sources": [
                        {"source_index": ss.source_index, "relevance": ss.relevance_score}
                        for ss in ca.supporting_sources
                    ]
                }
                for ca in result.claim_details
            ]

            data = {
                "query_id": query_id,
                "rag_metrics_id": None,  # Link to rag_quality_metrics if available
                "total_claims": result.total_claims,
                "grounded_claims": result.grounded_claims,
                "ungrounded_claims": result.ungrounded_claims,
                "claim_details": json.dumps(claim_details_json),
                "overall_grounding_score": result.overall_grounding_score,
                "confidence_level": result.confidence_level.value,
            }

            self.supabase.table("grounding_results").insert(data).execute()
            logger.debug("Grounding result stored", query_id=query_id)
            return True

        except Exception as e:
            logger.error("Failed to store grounding result", error=str(e))
            return False

    async def quick_check(
        self,
        answer: str,
        source_contexts: List[str]
    ) -> Tuple[float, ConfidenceLevel, bool]:
        """
        Quick grounding check without detailed claim analysis.

        Useful for initial filtering before full evaluation.

        Returns:
            Tuple of (overall_score, confidence_level, should_block)
        """
        # Use a simpler prompt for quick check
        combined_sources = "\n---\n".join(src[:300] for src in source_contexts[:3])

        prompt = f"""Quickly assess: Is this answer well-supported by the sources?

Sources:
{combined_sources[:1500]}

Answer:
{answer[:500]}

Rate overall grounding (0.0-1.0):
- 1.0: All claims directly supported
- 0.5: Mixed support
- 0.0: No support or contradictions

Respond with JSON only:
{{"score": 0.7, "confidence": "high|medium|low"}}"""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                score = float(data.get("score", 0.5))
                confidence_str = data.get("confidence", "medium")
                confidence = ConfidenceLevel(confidence_str) if confidence_str in ["high", "medium", "low"] else ConfidenceLevel.MEDIUM
                should_block = score < self.critical_threshold
                return score, confidence, should_block

        except Exception as e:
            logger.warning("Quick grounding check failed", error=str(e))

        return 0.5, ConfidenceLevel.MEDIUM, False


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_evaluator_instance: Optional[AnswerGroundingEvaluator] = None


def get_grounding_evaluator(supabase_client: Optional[Any] = None) -> AnswerGroundingEvaluator:
    """Get or create singleton AnswerGroundingEvaluator instance"""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = AnswerGroundingEvaluator(supabase_client=supabase_client)
    return _evaluator_instance


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def evaluate_grounding(
    answer: str,
    sources: List[str]
) -> GroundingResult:
    """
    Convenience function to evaluate answer grounding.

    Example:
        result = await evaluate_grounding(
            answer="Python was created in 1991 by Guido van Rossum.",
            sources=["Python is a programming language created by Guido van Rossum in 1991."]
        )
        logger.info("grounding_evaluated", score=result.overall_grounding_score)
    """
    evaluator = get_grounding_evaluator()
    return await evaluator.evaluate(answer, sources)
