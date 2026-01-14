# Implementation Plan: RAG Enhancement Services

**Branch**: `008-rag-enhancement-services` | **Date**: 2025-01-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-rag-enhancement-services/spec.md`

## Summary

Implement 6 infrastructure services to enhance the Empire RAG system's quality measurement, query understanding, and output validation. These services wrap around the existing 17 AI agents to provide:

1. **Retrieval Evaluator** - RAGAS metrics with hybrid batch/real-time evaluation
2. **Query Intent Analyzer** - Query classification for optimal routing
3. **Answer Grounding Evaluator** - Citation verification and hallucination prevention
4. **Adaptive Retrieval** - Dynamic parameter tuning based on query type
5. **Agent Selector** - Intelligent task-to-agent routing with performance tracking
6. **Output Validator** - Quality enforcement with auto-correction

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, Anthropic SDK (Claude 3.5 Haiku), Pydantic v2, structlog, asyncio
**Storage**: Supabase PostgreSQL (new tables: rag_quality_metrics, agent_performance_history, retrieval_parameter_configs, grounding_results)
**Testing**: pytest, pytest-asyncio, pytest-mock
**Target Platform**: Linux server (Render), Mac Studio (local development)
**Project Type**: Backend services (FastAPI)
**Performance Goals**: <500ms additional latency per service, support 10K queries/day
**Constraints**: Use Anthropic Batch API for cost optimization, Claude 3.5 Haiku for evaluations ($0.0052/eval)
**Scale/Scope**: Enhance existing 17 agents, 6 new service files, 4 new database tables

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Library-First | PASS | Each service is self-contained with clear interface |
| Test-First | PASS | Unit tests for each service, integration tests for pipeline |
| Observability | PASS | Metrics stored in PostgreSQL, exposed via /api/rag/metrics |
| Simplicity | PASS | Services wrap existing infrastructure, no new agents |

## Project Structure

### Documentation (this feature)

```text
specs/008-rag-enhancement-services/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
├── research.md          # Research findings
├── data-model.md        # Entity definitions
├── quickstart.md        # Setup and testing guide
├── contracts/           # API endpoint definitions
│   └── rag-metrics-api.yaml
└── tasks.md             # Task breakdown (speckit.tasks output)
```

### Source Code (repository root)

```text
app/
├── services/
│   ├── retrieval_evaluator.py        # NEW: RAGAS metrics evaluation
│   ├── query_intent_analyzer.py      # NEW: Query classification
│   ├── answer_grounding_evaluator.py # NEW: Citation verification
│   ├── adaptive_retrieval_service.py # NEW: Dynamic parameter tuning
│   ├── agent_selector_service.py     # NEW: Intelligent agent routing
│   ├── output_validator_service.py   # NEW: Quality enforcement
│   └── rag_query_service.py          # EXISTING: Enhanced with new services
├── models/
│   └── rag_enhancement.py            # NEW: Pydantic models for all services
├── routes/
│   └── rag_metrics.py                # NEW: /api/rag/metrics endpoints
└── middleware/
    └── rag_enhancement_middleware.py # NEW: Pipeline integration

tests/
├── unit/
│   ├── test_retrieval_evaluator.py
│   ├── test_query_intent_analyzer.py
│   ├── test_answer_grounding_evaluator.py
│   ├── test_adaptive_retrieval_service.py
│   ├── test_agent_selector_service.py
│   └── test_output_validator_service.py
└── integration/
    └── test_rag_enhancement_pipeline.py

migrations/
└── 20250114_rag_enhancement_tables.sql  # NEW: 4 tables
```

**Structure Decision**: Services added to existing `app/services/` directory following Empire v7.3 patterns. Each service is a standalone module with clear interfaces.

## Complexity Tracking

No constitution violations. All services follow existing patterns.

---

## Phase 0: Research

### Technology Decisions

| Decision | Choice | Rationale | Alternatives Rejected |
|----------|--------|-----------|----------------------|
| RAGAS Implementation | Custom with Claude API | More control over evaluation prompts, cost optimization | ragas library (heavier dependency, less flexible) |
| Evaluation Model | Claude 3.5 Haiku | $0.0052/eval, good quality for metrics | Claude 3.5 Sonnet ($0.0195/eval, 3.75x cost) |
| Batch Processing | Anthropic Batch API | 50% cost discount for non-urgent evaluations | Real-time only (higher cost) |
| Query Classification | LLM-based with caching | Accurate intent detection, Redis cache for repeat queries | Rule-based (less accurate), Embedding similarity (slower) |
| Grounding Algorithm | Claim extraction + NLI | Explicit verification, interpretable scores | Embedding similarity only (less precise) |

### Best Practices Research

1. **RAGAS Metrics Implementation**
   - Context Relevance: Use LLM to rate query-context alignment (0-1)
   - Answer Relevance: Check if answer addresses query (0-1)
   - Faithfulness: Verify claims against sources (0-1)
   - Coverage: Check if all query aspects addressed (0-1)

2. **Query Intent Classification**
   - 5 intent types: factual, analytical, comparative, procedural, creative
   - Use few-shot prompting with Claude for classification
   - Cache results in Redis (TTL: 1 hour for identical queries)

3. **Claim Extraction for Grounding**
   - Use LLM to extract atomic claims from answer
   - Score each claim against source chunks using NLI-style prompting
   - Aggregate scores with weighted average

---

## Phase 1: Design

### Data Model

See [data-model.md](./data-model.md) for full entity definitions.

**Core Entities:**

```python
# RAGASMetrics
class RAGASMetrics(BaseModel):
    context_relevance: float  # 0-1
    answer_relevance: float   # 0-1
    faithfulness: float       # 0-1
    coverage: float           # 0-1
    overall_score: float      # weighted average

# QueryIntent
class QueryIntent(BaseModel):
    intent_type: Literal["factual", "analytical", "comparative", "procedural", "creative"]
    complexity_score: float   # 0-1
    entities: list[str]
    suggested_strategy: str

# GroundingResult
class GroundingResult(BaseModel):
    claims: list[Claim]
    grounded_count: int
    ungrounded_count: int
    overall_score: float
    confidence_level: Literal["high", "medium", "low"]

# AgentSelection
class AgentSelection(BaseModel):
    agent_id: str             # AGENT-002 through AGENT-017
    confidence: float
    reason: str
    alternatives: list[str]
```

### API Contracts

**New Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/rag/metrics` | Dashboard metrics (aggregate RAGAS scores) |
| GET | `/api/rag/metrics/{query_id}` | Metrics for specific query |
| POST | `/api/rag/evaluate` | Manual evaluation trigger |
| GET | `/api/rag/agents/performance` | Agent performance leaderboard |
| GET | `/api/rag/config/retrieval` | Current adaptive retrieval params |
| PUT | `/api/rag/config/retrieval` | Override retrieval params |

### Service Interfaces

```python
# 1. Retrieval Evaluator
class RetrievalEvaluator:
    async def evaluate(self, query: str, contexts: list[str], answer: str) -> RAGASMetrics
    async def check_quality_gate(self, metrics: RAGASMetrics) -> QualityGateResult
    async def batch_evaluate(self, evaluations: list[EvaluationRequest]) -> list[RAGASMetrics]

# 2. Query Intent Analyzer
class QueryIntentAnalyzer:
    async def analyze(self, query: str) -> QueryIntent
    async def get_retrieval_strategy(self, intent: QueryIntent) -> RetrievalStrategy

# 3. Answer Grounding Evaluator
class AnswerGroundingEvaluator:
    async def evaluate(self, answer: str, sources: list[Document]) -> GroundingResult
    async def extract_claims(self, answer: str) -> list[Claim]

# 4. Adaptive Retrieval Service
class AdaptiveRetrievalService:
    async def get_params(self, intent: QueryIntent) -> RetrievalParams
    async def record_feedback(self, query_id: str, score: float, feedback: int) -> None
    async def optimize_params(self, intent_type: str) -> None

# 5. Agent Selector Service
class AgentSelectorService:
    async def select(self, task: Task, intent: QueryIntent) -> AgentSelection
    async def record_outcome(self, agent_id: str, task_type: str, success: bool) -> None

# 6. Output Validator Service
class OutputValidatorService:
    async def validate(self, output: str, requirements: OutputRequirements) -> ValidationResult
    async def auto_correct(self, output: str, issues: list[Issue]) -> str
```

### Integration Flow

```python
async def enhanced_rag_pipeline(query: str) -> EnhancedResponse:
    # 1. Analyze query intent
    intent = await query_intent_analyzer.analyze(query)

    # 2. Get adaptive retrieval params
    params = await adaptive_retrieval.get_params(intent)

    # 3. Execute retrieval with params
    contexts = await rag_query_service.retrieve(query, params)

    # 4. Evaluate retrieval quality
    retrieval_metrics = await retrieval_evaluator.evaluate_retrieval(query, contexts)

    # 5. Quality gate check - retry if needed
    if retrieval_metrics.context_relevance < 0.5:
        expanded_params = params.with_expansion()
        contexts = await rag_query_service.retrieve(query, expanded_params)
        retrieval_metrics = await retrieval_evaluator.evaluate_retrieval(query, contexts)

    # 6. Select optimal agent
    selection = await agent_selector.select(task, intent)

    # 7. Execute agent
    agent = get_agent(selection.agent_id)
    raw_answer = await agent.execute(query, contexts)

    # 8. Evaluate answer grounding
    grounding = await grounding_evaluator.evaluate(raw_answer, contexts)

    # 9. Full RAGAS evaluation (batch or real-time based on intent)
    if intent.is_high_value:
        full_metrics = await retrieval_evaluator.evaluate(query, contexts, raw_answer)
    else:
        await retrieval_evaluator.queue_batch_evaluation(query, contexts, raw_answer)
        full_metrics = None

    # 10. Validate and correct output
    validation = await output_validator.validate(raw_answer, intent.output_requirements)
    final_answer = validation.corrected_output or raw_answer

    # 11. Store metrics
    await store_metrics(query, retrieval_metrics, grounding, full_metrics, selection)

    return EnhancedResponse(
        answer=final_answer,
        confidence=grounding.confidence_level,
        metrics=retrieval_metrics,
        agent_used=selection.agent_id,
        warnings=validation.issues if not validation.passed else []
    )
```

---

## Phase 2: Implementation Phases

### Phase 2.1: Foundation (P1 - Critical)
1. Database migrations for 4 new tables
2. Pydantic models for all entities
3. Retrieval Evaluator Service (core RAGAS metrics)
4. Query Intent Analyzer Service
5. Basic API routes for metrics

### Phase 2.2: Quality Assurance (P1 - Critical)
6. Answer Grounding Evaluator Service
7. Quality gate implementation
8. Integration with existing RAG pipeline
9. Unit tests for Phase 1-2 services

### Phase 2.3: Optimization (P2 - Important)
10. Adaptive Retrieval Service
11. Agent Selector Service
12. Performance tracking tables
13. Batch evaluation with Anthropic Batch API

### Phase 2.4: Validation & Polish (P2 - Important)
14. Output Validator Service
15. Metrics dashboard endpoints
16. Integration tests
17. Documentation and quickstart guide

---

## Quickstart

See [quickstart.md](./quickstart.md) for setup and testing instructions.

**Basic Usage:**

```python
from app.services.retrieval_evaluator import RetrievalEvaluator
from app.services.query_intent_analyzer import QueryIntentAnalyzer

# Initialize services
evaluator = RetrievalEvaluator()
intent_analyzer = QueryIntentAnalyzer()

# Analyze query
intent = await intent_analyzer.analyze("What are GDPR requirements?")
# QueryIntent(intent_type="factual", complexity_score=0.3, ...)

# Evaluate retrieval
metrics = await evaluator.evaluate(
    query="What are GDPR requirements?",
    contexts=["GDPR requires...", "Data protection..."],
    answer="GDPR requires organizations to..."
)
# RAGASMetrics(context_relevance=0.85, faithfulness=0.92, ...)
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM cost overrun | Batch API + sampling + Haiku model |
| Latency increase | Async evaluation, caching, <500ms budget per service |
| False positives in grounding | Conservative thresholds, human review for edge cases |
| Agent selector bias | Exploration factor, periodic random selection |

---

## Success Metrics Tracking

| Metric | Target | Measurement |
|--------|--------|-------------|
| RAGAS coverage | 100% queries measured | `rag_quality_metrics` table count |
| Intent accuracy | >90% | Labeled test set evaluation |
| Hallucination detection | >85% | Human review sample |
| Latency overhead | <500ms | P95 latency delta |
| Cost per eval | $0.0052 | Anthropic billing |
