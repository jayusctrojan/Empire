"""
Enhanced RAG Pipeline - Task 148

Integrates all RAG enhancement services into a unified pipeline:
- Query Intent Analyzer: Classify query intent and complexity
- Adaptive Retrieval Service: Dynamic retrieval parameter adjustment
- Retrieval Evaluator: RAGAS-based retrieval quality assessment
- Agent Selector Service: Intelligent agent routing
- Answer Grounding Evaluator: Verify answer claims against sources
- Output Validator Service: Format and style validation

Pipeline Flow:
1. Analyze query intent and complexity
2. Get adaptive retrieval parameters
3. Execute retrieval with optimized params
4. Evaluate retrieval quality (RAGAS metrics)
5. Select optimal agent for response generation
6. Generate response
7. Evaluate answer grounding
8. Validate output format and style
9. Record metrics for continuous improvement
"""

import os
import time
import structlog
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
from pydantic import BaseModel, Field
from enum import Enum

from app.services.query_intent_analyzer import (
    QueryIntentAnalyzer,
    QueryIntent,
    IntentType,
    QueryComplexity,
    get_query_intent_analyzer
)
from app.services.adaptive_retrieval_service import (
    AdaptiveRetrievalService,
    RetrievalParams,
    get_adaptive_retrieval_service
)
from app.services.retrieval_evaluator import (
    RetrievalEvaluator,
    RAGASMetrics,
    QualityGateResult,
    get_retrieval_evaluator
)
from app.services.agent_selector_service import (
    AgentSelectorService,
    TaskType,
    SelectionResult,
    OutcomeRecord,
    get_agent_selector
)
from app.services.answer_grounding_evaluator import (
    AnswerGroundingEvaluator,
    GroundingResult,
    ConfidenceLevel,
    get_answer_grounding_evaluator
)
from app.services.output_validator_service import (
    OutputValidatorService,
    OutputFormat,
    OutputRequirements,
    ValidationResult,
    get_output_validator
)

logger = structlog.get_logger(__name__)


class PipelineStage(str, Enum):
    """Stages of the enhanced RAG pipeline."""
    INTENT_ANALYSIS = "intent_analysis"
    RETRIEVAL_PARAMS = "retrieval_params"
    RETRIEVAL = "retrieval"
    RETRIEVAL_EVALUATION = "retrieval_evaluation"
    AGENT_SELECTION = "agent_selection"
    RESPONSE_GENERATION = "response_generation"
    GROUNDING_EVALUATION = "grounding_evaluation"
    OUTPUT_VALIDATION = "output_validation"
    METRICS_RECORDING = "metrics_recording"


class PipelineConfig(BaseModel):
    """Configuration for the enhanced RAG pipeline."""
    enable_intent_analysis: bool = True
    enable_adaptive_retrieval: bool = True
    enable_retrieval_evaluation: bool = True
    enable_agent_selection: bool = True
    enable_grounding_evaluation: bool = True
    enable_output_validation: bool = True
    enable_metrics_recording: bool = True

    # Quality thresholds
    min_retrieval_quality: float = 0.5
    min_grounding_score: float = 0.6
    max_ungrounded_claims: int = 2

    # Fallback settings
    enable_fallback_on_low_quality: bool = True
    max_retrieval_retries: int = 2

    # Output settings
    output_format: OutputFormat = OutputFormat.STRUCTURED_ANSWER
    require_citations: bool = True


class StageResult(BaseModel):
    """Result from a pipeline stage."""
    stage: PipelineStage
    success: bool
    duration_ms: float
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class PipelineResult(BaseModel):
    """Complete result from the enhanced RAG pipeline."""
    success: bool
    query: str
    answer: Optional[str] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)

    # Quality metrics
    intent: Optional[QueryIntent] = None
    retrieval_params: Optional[RetrievalParams] = None
    retrieval_metrics: Optional[RAGASMetrics] = None
    grounding_result: Optional[GroundingResult] = None
    validation_result: Optional[ValidationResult] = None

    # Agent info
    selected_agent: Optional[str] = None
    agent_selection_reason: Optional[str] = None

    # Timing
    total_duration_ms: float = 0.0
    stage_results: List[StageResult] = Field(default_factory=list)

    # Flags
    quality_gate_passed: bool = True
    used_fallback: bool = False
    requires_human_review: bool = False
    review_reasons: List[str] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    """Result from retrieval operation."""
    documents: List[Dict[str, Any]]
    scores: List[float]
    retrieval_time_ms: float


class EnhancedRAGPipeline:
    """
    Orchestrates the enhanced RAG pipeline with all quality services.

    The pipeline processes queries through multiple stages:
    1. Intent Analysis - Understand query type and complexity
    2. Retrieval Params - Get optimized retrieval parameters
    3. Retrieval - Execute vector/hybrid search
    4. Retrieval Evaluation - Assess retrieval quality with RAGAS
    5. Agent Selection - Route to optimal agent
    6. Response Generation - Generate answer with selected agent
    7. Grounding Evaluation - Verify claims against sources
    8. Output Validation - Check format and style
    9. Metrics Recording - Store metrics for improvement
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        retrieval_fn: Optional[callable] = None,
        generation_fn: Optional[callable] = None
    ):
        """
        Initialize the enhanced RAG pipeline.

        Args:
            config: Pipeline configuration.
            retrieval_fn: Function to execute retrieval (injected dependency).
            generation_fn: Function to generate responses (injected dependency).
        """
        self.config = config or PipelineConfig()
        self.retrieval_fn = retrieval_fn
        self.generation_fn = generation_fn

        # Initialize services lazily
        self._intent_analyzer: Optional[QueryIntentAnalyzer] = None
        self._adaptive_retrieval: Optional[AdaptiveRetrievalService] = None
        self._retrieval_evaluator: Optional[RetrievalEvaluator] = None
        self._agent_selector: Optional[AgentSelectorService] = None
        self._grounding_evaluator: Optional[AnswerGroundingEvaluator] = None
        self._output_validator: Optional[OutputValidatorService] = None

    @property
    def intent_analyzer(self) -> QueryIntentAnalyzer:
        if self._intent_analyzer is None:
            self._intent_analyzer = get_query_intent_analyzer()
        return self._intent_analyzer

    @property
    def adaptive_retrieval(self) -> AdaptiveRetrievalService:
        if self._adaptive_retrieval is None:
            self._adaptive_retrieval = get_adaptive_retrieval_service()
        return self._adaptive_retrieval

    @property
    def retrieval_evaluator(self) -> RetrievalEvaluator:
        if self._retrieval_evaluator is None:
            self._retrieval_evaluator = get_retrieval_evaluator()
        return self._retrieval_evaluator

    @property
    def agent_selector(self) -> AgentSelectorService:
        if self._agent_selector is None:
            self._agent_selector = get_agent_selector()
        return self._agent_selector

    @property
    def grounding_evaluator(self) -> AnswerGroundingEvaluator:
        if self._grounding_evaluator is None:
            self._grounding_evaluator = get_answer_grounding_evaluator()
        return self._grounding_evaluator

    @property
    def output_validator(self) -> OutputValidatorService:
        if self._output_validator is None:
            self._output_validator = get_output_validator()
        return self._output_validator

    async def execute(
        self,
        query: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> PipelineResult:
        """
        Execute the full enhanced RAG pipeline.

        Args:
            query: User query to process.
            user_id: Optional user identifier.
            session_id: Optional session identifier.
            context: Optional additional context.

        Returns:
            PipelineResult with answer and quality metrics.
        """
        start_time = time.time()
        context = context or {}
        stage_results: List[StageResult] = []

        result = PipelineResult(query=query)

        try:
            # Stage 1: Intent Analysis
            if self.config.enable_intent_analysis:
                stage_result, intent = await self._analyze_intent(query)
                stage_results.append(stage_result)
                if not stage_result.success:
                    raise Exception(f"Intent analysis failed: {stage_result.error}")
                result.intent = intent

            # Stage 2: Get Retrieval Parameters
            if self.config.enable_adaptive_retrieval and result.intent:
                stage_result, params = await self._get_retrieval_params(
                    result.intent.intent_type.value,
                    result.intent.complexity_level.value
                )
                stage_results.append(stage_result)
                if stage_result.success:
                    result.retrieval_params = params

            # Stage 3: Execute Retrieval
            stage_result, retrieval_result = await self._execute_retrieval(
                query,
                result.retrieval_params,
                context
            )
            stage_results.append(stage_result)
            if not stage_result.success:
                raise Exception(f"Retrieval failed: {stage_result.error}")

            result.sources = retrieval_result.documents

            # Stage 4: Evaluate Retrieval Quality
            if self.config.enable_retrieval_evaluation:
                stage_result, metrics = await self._evaluate_retrieval(
                    query,
                    retrieval_result.documents
                )
                stage_results.append(stage_result)
                if stage_result.success:
                    result.retrieval_metrics = metrics

                    # Check quality gate
                    if metrics.overall_score < self.config.min_retrieval_quality:
                        result.quality_gate_passed = False
                        if self.config.enable_fallback_on_low_quality:
                            # Retry with adjusted parameters
                            stage_result, retrieval_result = await self._retry_retrieval(
                                query, result.retrieval_params, context
                            )
                            if stage_result.success:
                                stage_results.append(stage_result)
                                result.sources = retrieval_result.documents
                                result.used_fallback = True

            # Stage 5: Select Agent
            selected_agent = None
            if self.config.enable_agent_selection:
                task_type = self._map_intent_to_task_type(result.intent)
                stage_result, selection = await self._select_agent(task_type)
                stage_results.append(stage_result)
                if stage_result.success:
                    selected_agent = selection
                    result.selected_agent = selection.selected_agent_id
                    result.agent_selection_reason = selection.selection_reason

            # Stage 6: Generate Response
            stage_result, answer = await self._generate_response(
                query,
                result.sources,
                result.intent,
                selected_agent
            )
            stage_results.append(stage_result)
            if not stage_result.success:
                raise Exception(f"Response generation failed: {stage_result.error}")

            result.answer = answer

            # Stage 7: Evaluate Grounding
            if self.config.enable_grounding_evaluation and answer:
                stage_result, grounding = await self._evaluate_grounding(
                    answer,
                    result.sources
                )
                stage_results.append(stage_result)
                if stage_result.success:
                    result.grounding_result = grounding

                    # Check grounding thresholds
                    if grounding.overall_grounding_score < self.config.min_grounding_score:
                        result.requires_human_review = True
                        result.review_reasons.append(
                            f"Low grounding score: {grounding.overall_grounding_score:.2f}"
                        )

                    if grounding.ungrounded_claims > self.config.max_ungrounded_claims:
                        result.requires_human_review = True
                        result.review_reasons.append(
                            f"Too many ungrounded claims: {grounding.ungrounded_claims}"
                        )

            # Stage 8: Validate Output
            if self.config.enable_output_validation and answer:
                requirements = OutputRequirements(
                    format=self.config.output_format,
                    must_include_citations=self.config.require_citations
                )
                stage_result, validation = await self._validate_output(
                    answer,
                    requirements
                )
                stage_results.append(stage_result)
                if stage_result.success:
                    result.validation_result = validation

                    # Use corrected output if available
                    if validation.corrected_output:
                        result.answer = validation.corrected_output

                    if validation.requires_human_review:
                        result.requires_human_review = True
                        result.review_reasons.extend(validation.review_reasons)

            # Stage 9: Record Metrics
            if self.config.enable_metrics_recording:
                stage_result = await self._record_metrics(
                    result, user_id, session_id
                )
                stage_results.append(stage_result)

            result.success = True

        except Exception as e:
            logger.error("enhanced_rag_pipeline_error", error=str(e), query=query[:100])
            result.success = False
            result.review_reasons.append(f"Pipeline error: {str(e)}")

        result.stage_results = stage_results
        result.total_duration_ms = (time.time() - start_time) * 1000

        logger.info(
            "enhanced_rag_pipeline_complete",
            success=result.success,
            total_duration_ms=result.total_duration_ms,
            stages_completed=len(stage_results),
            quality_gate_passed=result.quality_gate_passed,
            requires_human_review=result.requires_human_review
        )

        return result

    async def _analyze_intent(
        self,
        query: str
    ) -> Tuple[StageResult, Optional[QueryIntent]]:
        """Stage 1: Analyze query intent."""
        start_time = time.time()
        try:
            intent = await self.intent_analyzer.analyze(query)
            return StageResult(
                stage=PipelineStage.INTENT_ANALYSIS,
                success=True,
                duration_ms=(time.time() - start_time) * 1000,
                data={
                    "intent_type": intent.intent_type.value,
                    "complexity": intent.complexity_level.value,
                    "confidence": intent.confidence
                }
            ), intent
        except Exception as e:
            return StageResult(
                stage=PipelineStage.INTENT_ANALYSIS,
                success=False,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            ), None

    async def _get_retrieval_params(
        self,
        intent_type: str,
        complexity: str
    ) -> Tuple[StageResult, Optional[RetrievalParams]]:
        """Stage 2: Get adaptive retrieval parameters."""
        start_time = time.time()
        try:
            params = await self.adaptive_retrieval.get_params(
                intent_type=intent_type,
                complexity=complexity
            )
            return StageResult(
                stage=PipelineStage.RETRIEVAL_PARAMS,
                success=True,
                duration_ms=(time.time() - start_time) * 1000,
                data=params.model_dump()
            ), params
        except Exception as e:
            return StageResult(
                stage=PipelineStage.RETRIEVAL_PARAMS,
                success=False,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            ), None

    async def _execute_retrieval(
        self,
        query: str,
        params: Optional[RetrievalParams],
        context: Dict[str, Any]
    ) -> Tuple[StageResult, Optional[RetrievalResult]]:
        """Stage 3: Execute retrieval."""
        start_time = time.time()
        try:
            if self.retrieval_fn:
                # Use injected retrieval function
                docs, scores = await self.retrieval_fn(
                    query=query,
                    params=params,
                    context=context
                )
            else:
                # Fallback: return empty (for testing/demo)
                docs = []
                scores = []
                logger.warning("no_retrieval_function_configured")

            result = RetrievalResult(
                documents=docs,
                scores=scores,
                retrieval_time_ms=(time.time() - start_time) * 1000
            )

            return StageResult(
                stage=PipelineStage.RETRIEVAL,
                success=True,
                duration_ms=result.retrieval_time_ms,
                data={"document_count": len(docs)}
            ), result
        except Exception as e:
            return StageResult(
                stage=PipelineStage.RETRIEVAL,
                success=False,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            ), None

    async def _retry_retrieval(
        self,
        query: str,
        params: Optional[RetrievalParams],
        context: Dict[str, Any]
    ) -> Tuple[StageResult, Optional[RetrievalResult]]:
        """Retry retrieval with adjusted parameters."""
        # Adjust parameters for retry
        if params:
            adjusted_params = RetrievalParams(
                dense_weight=params.dense_weight,
                sparse_weight=params.sparse_weight,
                fuzzy_weight=params.fuzzy_weight,
                top_k=min(params.top_k * 2, 30),  # Increase top_k
                rerank_threshold=max(params.rerank_threshold - 0.1, 0.3),  # Lower threshold
                graph_expansion_depth=params.graph_expansion_depth + 1
            )
        else:
            adjusted_params = None

        return await self._execute_retrieval(query, adjusted_params, context)

    async def _evaluate_retrieval(
        self,
        query: str,
        documents: List[Dict[str, Any]]
    ) -> Tuple[StageResult, Optional[RAGASMetrics]]:
        """Stage 4: Evaluate retrieval quality."""
        start_time = time.time()
        try:
            # Extract document texts for evaluation
            doc_texts = [
                doc.get("content", doc.get("text", ""))
                for doc in documents
            ]

            metrics = await self.retrieval_evaluator.evaluate(
                query=query,
                retrieved_contexts=doc_texts
            )

            return StageResult(
                stage=PipelineStage.RETRIEVAL_EVALUATION,
                success=True,
                duration_ms=(time.time() - start_time) * 1000,
                data={
                    "context_relevance": metrics.context_relevance,
                    "overall_score": metrics.overall_score
                }
            ), metrics
        except Exception as e:
            return StageResult(
                stage=PipelineStage.RETRIEVAL_EVALUATION,
                success=False,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            ), None

    async def _select_agent(
        self,
        task_type: TaskType
    ) -> Tuple[StageResult, Optional[SelectionResult]]:
        """Stage 5: Select optimal agent."""
        start_time = time.time()
        try:
            selection = await self.agent_selector.select_agent(task_type)

            return StageResult(
                stage=PipelineStage.AGENT_SELECTION,
                success=True,
                duration_ms=(time.time() - start_time) * 1000,
                data={
                    "selected_agent": selection.selected_agent_id,
                    "confidence": selection.confidence
                }
            ), selection
        except Exception as e:
            return StageResult(
                stage=PipelineStage.AGENT_SELECTION,
                success=False,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            ), None

    async def _generate_response(
        self,
        query: str,
        sources: List[Dict[str, Any]],
        intent: Optional[QueryIntent],
        agent_selection: Optional[SelectionResult]
    ) -> Tuple[StageResult, Optional[str]]:
        """Stage 6: Generate response."""
        start_time = time.time()
        try:
            if self.generation_fn:
                answer = await self.generation_fn(
                    query=query,
                    sources=sources,
                    intent=intent,
                    agent_id=agent_selection.selected_agent_id if agent_selection else None
                )
            else:
                # Fallback: return placeholder (for testing/demo)
                answer = f"Response to: {query}"
                logger.warning("no_generation_function_configured")

            return StageResult(
                stage=PipelineStage.RESPONSE_GENERATION,
                success=True,
                duration_ms=(time.time() - start_time) * 1000,
                data={"answer_length": len(answer) if answer else 0}
            ), answer
        except Exception as e:
            return StageResult(
                stage=PipelineStage.RESPONSE_GENERATION,
                success=False,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            ), None

    async def _evaluate_grounding(
        self,
        answer: str,
        sources: List[Dict[str, Any]]
    ) -> Tuple[StageResult, Optional[GroundingResult]]:
        """Stage 7: Evaluate answer grounding."""
        start_time = time.time()
        try:
            # Extract source texts
            source_texts = [
                doc.get("content", doc.get("text", ""))
                for doc in sources
            ]

            grounding = await self.grounding_evaluator.evaluate(
                answer=answer,
                source_documents=source_texts
            )

            return StageResult(
                stage=PipelineStage.GROUNDING_EVALUATION,
                success=True,
                duration_ms=(time.time() - start_time) * 1000,
                data={
                    "grounding_score": grounding.overall_grounding_score,
                    "grounded_claims": grounding.grounded_claims,
                    "ungrounded_claims": grounding.ungrounded_claims
                }
            ), grounding
        except Exception as e:
            return StageResult(
                stage=PipelineStage.GROUNDING_EVALUATION,
                success=False,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            ), None

    async def _validate_output(
        self,
        answer: str,
        requirements: OutputRequirements
    ) -> Tuple[StageResult, Optional[ValidationResult]]:
        """Stage 8: Validate output."""
        start_time = time.time()
        try:
            validation = await self.output_validator.validate(
                output=answer,
                requirements=requirements
            )

            return StageResult(
                stage=PipelineStage.OUTPUT_VALIDATION,
                success=True,
                duration_ms=(time.time() - start_time) * 1000,
                data={
                    "is_valid": validation.is_valid,
                    "error_count": validation.error_count,
                    "warning_count": validation.warning_count
                }
            ), validation
        except Exception as e:
            return StageResult(
                stage=PipelineStage.OUTPUT_VALIDATION,
                success=False,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            ), None

    async def _record_metrics(
        self,
        result: PipelineResult,
        user_id: Optional[str],
        session_id: Optional[str]
    ) -> StageResult:
        """Stage 9: Record metrics for continuous improvement."""
        start_time = time.time()
        try:
            # Record to adaptive retrieval service for parameter tuning
            if result.retrieval_metrics and result.intent:
                await self.adaptive_retrieval.record_feedback(
                    intent_type=result.intent.intent_type.value,
                    complexity=result.intent.complexity_level.value,
                    quality_score=result.retrieval_metrics.overall_score,
                    success=result.quality_gate_passed
                )

            # Record agent outcome for selector learning
            if result.selected_agent and result.grounding_result:
                task_type = self._map_intent_to_task_type(result.intent)
                outcome = OutcomeRecord(
                    agent_id=result.selected_agent,
                    task_type=task_type,
                    success=result.success,
                    quality_score=result.grounding_result.overall_grounding_score,
                    latency_ms=result.total_duration_ms
                )
                await self.agent_selector.record_outcome(outcome)

            return StageResult(
                stage=PipelineStage.METRICS_RECORDING,
                success=True,
                duration_ms=(time.time() - start_time) * 1000,
                data={"recorded": True}
            )
        except Exception as e:
            return StageResult(
                stage=PipelineStage.METRICS_RECORDING,
                success=False,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )

    def _map_intent_to_task_type(
        self,
        intent: Optional[QueryIntent]
    ) -> TaskType:
        """Map query intent to agent task type."""
        if not intent:
            return TaskType.ANSWER_GENERATION

        mapping = {
            IntentType.FACTUAL: TaskType.ANSWER_GENERATION,
            IntentType.ANALYTICAL: TaskType.ANALYSIS,
            IntentType.COMPARATIVE: TaskType.ANALYSIS,
            IntentType.PROCEDURAL: TaskType.WRITING,
            IntentType.CREATIVE: TaskType.WRITING,
        }

        return mapping.get(intent.intent_type, TaskType.ANSWER_GENERATION)


# Singleton instance
_pipeline_instance: Optional[EnhancedRAGPipeline] = None


def get_enhanced_rag_pipeline(
    config: Optional[PipelineConfig] = None,
    retrieval_fn: Optional[callable] = None,
    generation_fn: Optional[callable] = None
) -> EnhancedRAGPipeline:
    """Get or create the enhanced RAG pipeline singleton."""
    global _pipeline_instance

    if _pipeline_instance is None:
        _pipeline_instance = EnhancedRAGPipeline(
            config=config,
            retrieval_fn=retrieval_fn,
            generation_fn=generation_fn
        )

    return _pipeline_instance


def create_pipeline(
    config: Optional[PipelineConfig] = None,
    retrieval_fn: Optional[callable] = None,
    generation_fn: Optional[callable] = None
) -> EnhancedRAGPipeline:
    """Create a new pipeline instance (non-singleton)."""
    return EnhancedRAGPipeline(
        config=config,
        retrieval_fn=retrieval_fn,
        generation_fn=generation_fn
    )
