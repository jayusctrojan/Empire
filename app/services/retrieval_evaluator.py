"""
Empire v7.3 - Retrieval Evaluator Service with RAGAS (Task 143)

Evaluates retrieval quality using RAGAS metrics for RAG quality assurance.
Part of the RAG Enhancement Services (Feature 008).

RAGAS Metrics:
- Context Relevance: Are retrieved chunks relevant to the query?
- Answer Relevance: Is the answer relevant to the query?
- Faithfulness: Is the answer faithful to the retrieved context?
- Coverage: Does retrieval cover all aspects of the query?

Evaluation Modes:
- Real-time: For high-value queries using Claude Haiku
- Batch: For high-volume with 10% sampling using Anthropic Batch API

Author: Claude Code
Date: 2025-01-14
"""

import os
import re
import json
import uuid
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import random

import structlog
from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from app.services.api_resilience import ResilientAnthropicClient, CircuitOpenError

logger = structlog.get_logger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class EvaluationMode(str, Enum):
    """Evaluation mode selection"""
    REAL_TIME = "real_time"  # Full evaluation for high-value queries
    BATCH = "batch"  # Sampled evaluation for high-volume
    SKIP = "skip"  # No evaluation (for testing)


class QualityLevel(str, Enum):
    """Quality level classification"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CRITICAL = "critical"


# Default thresholds (can be overridden)
DEFAULT_THRESHOLDS = {
    "context_relevance": 0.6,
    "answer_relevance": 0.6,
    "faithfulness": 0.7,
    "coverage": 0.5,
}

# Batch sampling rate
BATCH_SAMPLE_RATE = 0.10  # 10% of queries evaluated in batch mode


# =============================================================================
# DATA MODELS
# =============================================================================

class RAGASMetrics(BaseModel):
    """RAGAS quality metrics"""
    context_relevance: float = Field(..., ge=0.0, le=1.0, description="Relevance of retrieved context to query")
    answer_relevance: float = Field(..., ge=0.0, le=1.0, description="Relevance of answer to query")
    faithfulness: float = Field(..., ge=0.0, le=1.0, description="Faithfulness of answer to context")
    coverage: float = Field(..., ge=0.0, le=1.0, description="Coverage of query aspects")
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Weighted average score")

    def get_quality_level(self) -> QualityLevel:
        """Determine quality level from overall score"""
        if self.overall_score >= 0.8:
            return QualityLevel.HIGH
        elif self.overall_score >= 0.6:
            return QualityLevel.MEDIUM
        elif self.overall_score >= 0.4:
            return QualityLevel.LOW
        else:
            return QualityLevel.CRITICAL


class QualityThresholds(BaseModel):
    """Configurable quality thresholds"""
    context_relevance: float = Field(0.6, ge=0.0, le=1.0)
    answer_relevance: float = Field(0.6, ge=0.0, le=1.0)
    faithfulness: float = Field(0.7, ge=0.0, le=1.0)
    coverage: float = Field(0.5, ge=0.0, le=1.0)


class QualityGateResult(BaseModel):
    """Result of quality gate check"""
    passed: bool = Field(..., description="Whether quality gate passed")
    metrics: RAGASMetrics = Field(..., description="Evaluated metrics")
    violations: List[str] = Field(default_factory=list, description="Threshold violations")
    quality_level: QualityLevel = Field(..., description="Overall quality classification")
    recommendation: str = Field(..., description="Recommended action")


class EvaluationRequest(BaseModel):
    """Request for retrieval evaluation"""
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str = Field(..., min_length=1)
    retrieved_contexts: List[str] = Field(..., min_items=1)
    answer: str = Field(..., min_length=1)
    intent_type: Optional[str] = Field(None, description="Query intent type")
    agent_id: Optional[str] = Field(None, description="Agent that generated the answer")
    mode: EvaluationMode = Field(EvaluationMode.REAL_TIME)


class StoredMetrics(BaseModel):
    """Metrics stored in database"""
    query_id: str
    query_text: str
    intent_type: str
    context_relevance: float
    answer_relevance: float
    faithfulness: float
    coverage: float
    grounding_score: Optional[float] = None
    selected_agent_id: Optional[str] = None
    processing_time_ms: int
    created_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# RETRIEVAL EVALUATOR SERVICE
# =============================================================================

class RetrievalEvaluator:
    """
    Evaluates retrieval quality using RAGAS metrics.

    Features:
    - Real-time evaluation for high-value queries
    - Batch evaluation with sampling for high-volume
    - Quality gate checking with configurable thresholds
    - Metrics storage for analytics
    - Retry logic for quality gate failures
    """

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        use_resilient_client: bool = True,
        default_thresholds: Optional[QualityThresholds] = None,
        batch_sample_rate: float = BATCH_SAMPLE_RATE,
        supabase_client: Optional[Any] = None,
    ):
        """
        Initialize the Retrieval Evaluator.

        Args:
            anthropic_api_key: Anthropic API key
            use_resilient_client: Whether to use circuit breaker pattern
            default_thresholds: Default quality thresholds
            batch_sample_rate: Sampling rate for batch mode (0-1)
            supabase_client: Supabase client for metrics storage
        """
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.use_resilient_client = use_resilient_client
        self.thresholds = default_thresholds or QualityThresholds()
        self.batch_sample_rate = batch_sample_rate
        self.supabase = supabase_client

        # Initialize Anthropic client
        if use_resilient_client:
            self.client = ResilientAnthropicClient(api_key=self.api_key)
        else:
            self.client = AsyncAnthropic(api_key=self.api_key)

        # Model for evaluation (Haiku for speed/cost)
        self.model = "claude-3-5-haiku-20241022"

        # Metrics buffer for batch storage
        self._metrics_buffer: List[StoredMetrics] = []
        self._buffer_size = 100  # Flush every 100 metrics

        logger.info(
            "RetrievalEvaluator initialized",
            use_resilient_client=use_resilient_client,
            batch_sample_rate=batch_sample_rate,
            model=self.model
        )

    async def _evaluate_context_relevance(
        self,
        query: str,
        contexts: List[str]
    ) -> float:
        """
        Evaluate how relevant the retrieved contexts are to the query.

        Uses LLM to score each context's relevance, then averages.
        """
        if not contexts:
            return 0.0

        prompt = f"""Rate the relevance of each retrieved context to the query.

Query: "{query}"

Retrieved Contexts:
{chr(10).join(f'{i+1}. {ctx[:500]}...' if len(ctx) > 500 else f'{i+1}. {ctx}' for i, ctx in enumerate(contexts[:5]))}

For each context, rate relevance from 0.0 to 1.0:
- 1.0: Directly answers or highly relevant to the query
- 0.7-0.9: Relevant with useful information
- 0.4-0.6: Partially relevant
- 0.1-0.3: Marginally relevant
- 0.0: Not relevant

Respond with JSON only:
{{"scores": [0.8, 0.6, ...], "average": 0.7}}"""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return float(data.get("average", 0.5))

        except Exception as e:
            logger.warning("Context relevance evaluation failed", error=str(e))

        return 0.5  # Default to medium

    async def _evaluate_answer_relevance(
        self,
        query: str,
        answer: str
    ) -> float:
        """
        Evaluate how relevant the answer is to the query.
        """
        prompt = f"""Rate how well the answer addresses the query.

Query: "{query}"

Answer: "{answer[:1000]}{'...' if len(answer) > 1000 else ''}"

Rate the answer relevance from 0.0 to 1.0:
- 1.0: Directly and completely answers the query
- 0.7-0.9: Answers the main question with minor gaps
- 0.4-0.6: Partially answers the query
- 0.1-0.3: Tangentially related but doesn't answer
- 0.0: Does not address the query at all

Respond with JSON only:
{{"relevance": 0.8, "reasoning": "brief explanation"}}"""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return float(data.get("relevance", 0.5))

        except Exception as e:
            logger.warning("Answer relevance evaluation failed", error=str(e))

        return 0.5

    async def _evaluate_faithfulness(
        self,
        answer: str,
        contexts: List[str]
    ) -> float:
        """
        Evaluate if the answer is faithful to (supported by) the retrieved contexts.

        Checks for hallucinations by verifying claims against sources.
        """
        combined_context = "\n---\n".join(contexts[:5])

        prompt = f"""Check if the answer is faithful to the provided contexts.

Contexts:
{combined_context[:2000]}{'...' if len(combined_context) > 2000 else ''}

Answer:
{answer[:1000]}{'...' if len(answer) > 1000 else ''}

Rate faithfulness from 0.0 to 1.0:
- 1.0: All claims in answer are directly supported by contexts
- 0.7-0.9: Most claims supported, minor extrapolations
- 0.4-0.6: Mix of supported and unsupported claims
- 0.1-0.3: Many claims not supported by contexts
- 0.0: Answer contradicts or is unrelated to contexts

Respond with JSON only:
{{"faithfulness": 0.8, "unsupported_claims": 0, "total_claims": 5}}"""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return float(data.get("faithfulness", 0.5))

        except Exception as e:
            logger.warning("Faithfulness evaluation failed", error=str(e))

        return 0.5

    async def _evaluate_coverage(
        self,
        query: str,
        answer: str,
        contexts: List[str]
    ) -> float:
        """
        Evaluate if the retrieval and answer cover all aspects of the query.
        """
        prompt = f"""Evaluate if the answer covers all aspects/requirements of the query.

Query: "{query}"

Answer: "{answer[:1000]}{'...' if len(answer) > 1000 else ''}"

Rate coverage from 0.0 to 1.0:
- 1.0: All aspects of the query are addressed
- 0.7-0.9: Most aspects covered, minor gaps
- 0.4-0.6: Some aspects covered, notable gaps
- 0.1-0.3: Few aspects covered
- 0.0: Query aspects not addressed

Identify what aspects of the query are covered or missing.

Respond with JSON only:
{{"coverage": 0.8, "covered_aspects": ["aspect1", "aspect2"], "missing_aspects": ["aspect3"]}}"""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=250,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return float(data.get("coverage", 0.5))

        except Exception as e:
            logger.warning("Coverage evaluation failed", error=str(e))

        return 0.5

    def _calculate_overall_score(self, metrics: RAGASMetrics) -> float:
        """
        Calculate weighted overall score.

        Weights:
        - Faithfulness: 0.35 (most important - prevents hallucination)
        - Context Relevance: 0.25
        - Answer Relevance: 0.25
        - Coverage: 0.15
        """
        return (
            metrics.faithfulness * 0.35 +
            metrics.context_relevance * 0.25 +
            metrics.answer_relevance * 0.25 +
            metrics.coverage * 0.15
        )

    async def evaluate(
        self,
        query: str,
        retrieved_contexts: List[str],
        answer: str,
        mode: EvaluationMode = EvaluationMode.REAL_TIME
    ) -> RAGASMetrics:
        """
        Evaluate retrieval quality using RAGAS metrics.

        Args:
            query: The user query
            retrieved_contexts: List of retrieved text chunks
            answer: The generated answer
            mode: Evaluation mode (real_time, batch, skip)

        Returns:
            RAGASMetrics with all scores
        """
        start_time = datetime.now()

        if mode == EvaluationMode.SKIP:
            # Return default scores for testing
            return RAGASMetrics(
                context_relevance=0.5,
                answer_relevance=0.5,
                faithfulness=0.5,
                coverage=0.5,
                overall_score=0.5
            )

        if mode == EvaluationMode.BATCH:
            # Sample for batch evaluation
            if random.random() > self.batch_sample_rate:
                # Skip this query (not sampled)
                return RAGASMetrics(
                    context_relevance=-1,  # -1 indicates not evaluated
                    answer_relevance=-1,
                    faithfulness=-1,
                    coverage=-1,
                    overall_score=-1
                )

        # Evaluate all metrics concurrently
        context_relevance, answer_relevance, faithfulness, coverage = await asyncio.gather(
            self._evaluate_context_relevance(query, retrieved_contexts),
            self._evaluate_answer_relevance(query, answer),
            self._evaluate_faithfulness(answer, retrieved_contexts),
            self._evaluate_coverage(query, answer, retrieved_contexts),
        )

        metrics = RAGASMetrics(
            context_relevance=context_relevance,
            answer_relevance=answer_relevance,
            faithfulness=faithfulness,
            coverage=coverage,
            overall_score=0.0  # Will be calculated
        )

        # Calculate overall score
        metrics.overall_score = self._calculate_overall_score(metrics)

        elapsed = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            "RAGAS evaluation complete",
            overall_score=metrics.overall_score,
            context_relevance=metrics.context_relevance,
            faithfulness=metrics.faithfulness,
            elapsed_ms=int(elapsed)
        )

        return metrics

    async def check_quality_gate(
        self,
        metrics: RAGASMetrics,
        thresholds: Optional[QualityThresholds] = None
    ) -> QualityGateResult:
        """
        Check if metrics pass quality thresholds.

        Args:
            metrics: RAGAS metrics to check
            thresholds: Custom thresholds (uses defaults if not provided)

        Returns:
            QualityGateResult with pass/fail and details
        """
        thresholds = thresholds or self.thresholds
        violations = []

        # Check if this was a skipped evaluation
        if metrics.context_relevance < 0:
            return QualityGateResult(
                passed=True,  # Assume passed for non-evaluated
                metrics=metrics,
                violations=[],
                quality_level=QualityLevel.MEDIUM,
                recommendation="Evaluation skipped (batch sampling)"
            )

        # Check each threshold
        if metrics.context_relevance < thresholds.context_relevance:
            violations.append(
                f"Context relevance ({metrics.context_relevance:.2f}) below threshold ({thresholds.context_relevance})"
            )

        if metrics.answer_relevance < thresholds.answer_relevance:
            violations.append(
                f"Answer relevance ({metrics.answer_relevance:.2f}) below threshold ({thresholds.answer_relevance})"
            )

        if metrics.faithfulness < thresholds.faithfulness:
            violations.append(
                f"Faithfulness ({metrics.faithfulness:.2f}) below threshold ({thresholds.faithfulness})"
            )

        if metrics.coverage < thresholds.coverage:
            violations.append(
                f"Coverage ({metrics.coverage:.2f}) below threshold ({thresholds.coverage})"
            )

        passed = len(violations) == 0
        quality_level = metrics.get_quality_level()

        # Determine recommendation
        if passed:
            recommendation = "Quality gate passed. Proceed with response delivery."
        elif quality_level == QualityLevel.CRITICAL:
            recommendation = "Critical quality issues. Retry with expanded retrieval or escalate."
        elif quality_level == QualityLevel.LOW:
            recommendation = "Low quality. Consider retry with different parameters."
        else:
            recommendation = "Some threshold violations. Consider adding low confidence warning."

        return QualityGateResult(
            passed=passed,
            metrics=metrics,
            violations=violations,
            quality_level=quality_level,
            recommendation=recommendation
        )

    async def store_metrics(
        self,
        query_id: str,
        query: str,
        intent_type: str,
        metrics: RAGASMetrics,
        agent_id: Optional[str] = None,
        processing_time_ms: int = 0,
        retrieval_params: Optional[Dict] = None
    ) -> bool:
        """
        Store metrics in the database for analytics.

        Args:
            query_id: Unique query identifier
            query: The query text
            intent_type: Classified intent type
            metrics: RAGAS metrics
            agent_id: Agent that processed the query
            processing_time_ms: Processing time in milliseconds
            retrieval_params: Parameters used for retrieval

        Returns:
            True if stored successfully
        """
        if not self.supabase:
            logger.warning("Supabase client not configured, metrics not stored")
            return False

        try:
            data = {
                "query_id": query_id,
                "query_text": query[:1000],  # Truncate for storage
                "intent_type": intent_type,
                "context_relevance": metrics.context_relevance if metrics.context_relevance >= 0 else None,
                "answer_relevance": metrics.answer_relevance if metrics.answer_relevance >= 0 else None,
                "faithfulness": metrics.faithfulness if metrics.faithfulness >= 0 else None,
                "coverage": metrics.coverage if metrics.coverage >= 0 else None,
                "grounding_score": metrics.overall_score if metrics.overall_score >= 0 else None,
                "selected_agent_id": agent_id,
                "processing_time_ms": processing_time_ms,
                "retrieval_params": json.dumps(retrieval_params) if retrieval_params else None,
            }

            result = self.supabase.table("rag_quality_metrics").insert(data).execute()
            logger.debug("Metrics stored", query_id=query_id)
            return True

        except Exception as e:
            logger.error("Failed to store metrics", error=str(e), query_id=query_id)
            return False

    async def get_aggregate_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        intent_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get aggregate metrics for a time period.

        Args:
            start_date: Start of period (default: 30 days ago)
            end_date: End of period (default: now)
            intent_type: Filter by intent type

        Returns:
            Aggregate metrics dictionary
        """
        if not self.supabase:
            logger.warning("Supabase client not configured")
            return {}

        start_date = start_date or (datetime.now() - timedelta(days=30))
        end_date = end_date or datetime.now()

        try:
            # Use the database function for aggregation
            result = self.supabase.rpc(
                "get_avg_rag_metrics",
                {"p_start_date": start_date.isoformat(), "p_end_date": end_date.isoformat()}
            ).execute()

            if result.data:
                return result.data[0]

        except Exception as e:
            logger.error("Failed to get aggregate metrics", error=str(e))

        return {}

    async def evaluate_and_check(
        self,
        request: EvaluationRequest,
        thresholds: Optional[QualityThresholds] = None
    ) -> Tuple[RAGASMetrics, QualityGateResult]:
        """
        Combined evaluate and quality gate check.

        Args:
            request: Evaluation request
            thresholds: Quality thresholds

        Returns:
            Tuple of (metrics, quality_gate_result)
        """
        start_time = datetime.now()

        metrics = await self.evaluate(
            query=request.query,
            retrieved_contexts=request.retrieved_contexts,
            answer=request.answer,
            mode=request.mode
        )

        gate_result = await self.check_quality_gate(metrics, thresholds)

        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        # Store metrics if we have a database connection
        if self.supabase:
            await self.store_metrics(
                query_id=request.query_id,
                query=request.query,
                intent_type=request.intent_type or "unknown",
                metrics=metrics,
                agent_id=request.agent_id,
                processing_time_ms=elapsed_ms
            )

        return metrics, gate_result


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_evaluator_instance: Optional[RetrievalEvaluator] = None


def get_retrieval_evaluator(supabase_client: Optional[Any] = None) -> RetrievalEvaluator:
    """Get or create singleton RetrievalEvaluator instance"""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = RetrievalEvaluator(supabase_client=supabase_client)
    return _evaluator_instance


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def evaluate_retrieval(
    query: str,
    contexts: List[str],
    answer: str,
    mode: EvaluationMode = EvaluationMode.REAL_TIME
) -> RAGASMetrics:
    """
    Convenience function to evaluate retrieval quality.

    Example:
        metrics = await evaluate_retrieval(
            query="What is RAG?",
            contexts=["RAG stands for..."],
            answer="RAG is a technique..."
        )
        logger.info("retrieval_metrics", faithfulness=metrics.faithfulness)
    """
    evaluator = get_retrieval_evaluator()
    return await evaluator.evaluate(query, contexts, answer, mode)
