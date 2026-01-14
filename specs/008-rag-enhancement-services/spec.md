# Feature Specification: RAG Enhancement Services

**Feature Branch**: `008-rag-enhancement-services`
**Created**: 2025-01-14
**Status**: Draft
**Input**: User description: "Implement 6 RAG enhancement services to improve retrieval quality, answer grounding, query understanding, adaptive retrieval, agent selection, and output validation for the Empire RAG system with 17 AI agents."

## Executive Summary

Empire v7.3 has a robust RAG system with hybrid search (Dense + Sparse + Fuzzy + RRF), 17 AI agents, and knowledge graph integration. However, the system lacks critical infrastructure for **measuring and improving RAG quality**. This specification defines 6 new services that wrap around existing agents to provide:

1. **Retrieval Evaluation** - Measure retrieval quality with RAGAS metrics
2. **Query Intent Analysis** - Classify queries for optimal routing
3. **Answer Grounding Evaluation** - Verify citations and prevent hallucinations
4. **Adaptive Retrieval** - Dynamic parameter tuning based on query type
5. **Agent Selection** - Intelligent task-to-agent routing
6. **Output Validation** - Quality enforcement on agent outputs

These are **infrastructure services**, not new agents. They enhance the existing 17 agents.

## Clarifications

### Session 2025-01-14

- Q: What is the LLM cost strategy for evaluation services? → A: Option B - Batch evaluation for high-volume queries, real-time for high-value queries, with statistical sampling (10% of batch) and Anthropic Batch API 50% discount for cost optimization.

- Q: What happens when quality gate fails (low retrieval quality)? → A: Option B - Retry with expanded retrieval (more chunks, graph expansion), then proceed with visible "low confidence" warning if still below threshold.

## Current Agent Registry (17 Agents)

| ID | Agent Name | Route |
|----|------------|-------|
| AGENT-002 | Content Summarizer | `/api/summarizer` |
| AGENT-003 | Skill Asset Generator | `/api/assets/skill` |
| AGENT-004 | Command Asset Generator | `/api/assets/command` |
| AGENT-005 | Agent Asset Generator | `/api/assets/agent` |
| AGENT-006 | Prompt Asset Generator | `/api/assets/prompt` |
| AGENT-007 | Workflow Asset Generator | `/api/assets/workflow` |
| AGENT-008 | Department Classifier | `/api/classifier` |
| AGENT-009 | Research Analyst | `/api/document-analysis/research` |
| AGENT-010 | Strategy Analyst | `/api/document-analysis/strategy` |
| AGENT-011 | Fact Checker | `/api/document-analysis/fact-check` |
| AGENT-012 | Research Orchestrator | `/api/orchestration/research` |
| AGENT-013 | Analysis Orchestrator | `/api/orchestration/analyze` |
| AGENT-014 | Writing Orchestrator | `/api/orchestration/write` |
| AGENT-015 | Review Orchestrator | `/api/orchestration/review` |
| AGENT-016 | Content Prep Agent | `/api/content-prep` |
| AGENT-017 | Graph Agent | `/api/graph` |

## Problem Statement

### Current Gaps

1. **No Retrieval Quality Measurement**
   - Cannot measure if retrieved chunks are relevant
   - No quality gates to prevent bad retrievals from reaching agents
   - No feedback loop for improvement

2. **No Query Understanding**
   - All queries treated identically regardless of intent
   - Factual queries use same strategy as analytical queries
   - No optimization based on query complexity

3. **Weak Answer Grounding**
   - Citations exist but are not verified
   - No measurement of answer faithfulness to sources
   - Hallucinations can slip through undetected

4. **Static Retrieval Parameters**
   - Fixed weights for hybrid search (Dense: 0.4, Sparse: 0.3, Fuzzy: 0.3)
   - Fixed top_k regardless of query type
   - No learning from feedback

5. **No Intelligent Agent Selection**
   - Manual routing or simple rule-based selection
   - No performance tracking per agent per task type
   - Suboptimal agent assignments

6. **No Output Quality Enforcement**
   - Agent outputs not validated against quality standards
   - No automatic correction for common issues
   - Inconsistent output formats

### Impact

- Users receive answers with unknown quality
- Hallucinations go undetected
- Retrieval performance cannot be optimized
- Agent capabilities are not fully utilized

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retrieval Quality Visibility (Priority: P1)

A system administrator wants to understand RAG performance. They access the `/api/rag/metrics` endpoint and see real-time RAGAS scores: Context Relevance (0.82), Answer Relevance (0.78), Faithfulness (0.91), Coverage (0.75). They can drill down by query type, time period, and agent to identify optimization opportunities.

**Why this priority**: Without measurement, no improvement is possible. This is the foundation for all other enhancements.

**Independent Test**: Can be tested by running queries and checking the metrics dashboard. Delivers immediate visibility into RAG quality.

**Acceptance Scenarios**:

1. **Given** a query is processed, **When** retrieval completes, **Then** RAGAS metrics are calculated and stored
2. **Given** metrics are collected, **When** admin accesses dashboard, **Then** aggregate scores and trends are displayed
3. **Given** a low-quality retrieval (Context Relevance < 0.5), **When** threshold breached, **Then** alert is logged and optional fallback triggered

---

### User Story 2 - Query-Aware Processing (Priority: P1)

A user asks "What is the capital of France?" (factual) vs "Analyze the implications of GDPR on our data retention policy" (analytical). The system recognizes these as different query types and routes them appropriately - factual queries use simple RAG, analytical queries engage the multi-agent orchestration with deeper context retrieval.

**Why this priority**: Query classification enables all downstream optimizations. Must be implemented early.

**Independent Test**: Can be tested by submitting different query types and verifying correct classification and routing.

**Acceptance Scenarios**:

1. **Given** a factual query, **When** classified, **Then** system uses lightweight retrieval with top_k=5
2. **Given** an analytical query, **When** classified, **Then** system uses deep retrieval with top_k=20 and graph expansion
3. **Given** a comparative query, **When** classified, **Then** system retrieves from multiple document sets for comparison

---

### User Story 3 - Hallucination Prevention (Priority: P1)

A user receives an answer that includes claims. The system automatically verifies each claim against the retrieved sources. Claims that cannot be grounded are flagged, and the user sees confidence indicators: "High confidence (3 sources support)" vs "Low confidence (claim not directly supported by sources)".

**Why this priority**: Hallucination prevention is critical for enterprise trust. Must be core functionality.

**Independent Test**: Can be tested by generating answers and verifying grounding scores match actual source support.

**Acceptance Scenarios**:

1. **Given** an answer with claims, **When** grounding check runs, **Then** each claim receives a grounding score (0-1)
2. **Given** a claim with grounding score < 0.3, **When** displayed to user, **Then** claim is flagged as "unverified"
3. **Given** all claims are well-grounded (score > 0.8), **When** displayed, **Then** answer shows "High confidence" badge

---

### User Story 4 - Adaptive Search Optimization (Priority: P2)

Over time, the system learns that legal document queries perform better with higher sparse search weight (0.5 instead of 0.3) and technical queries perform better with more fuzzy matching. The system automatically adjusts parameters based on feedback and measured quality.

**Why this priority**: Adaptive retrieval improves quality over time but requires metrics infrastructure first.

**Independent Test**: Can be tested by simulating feedback and verifying parameter adjustments.

**Acceptance Scenarios**:

1. **Given** query type "legal", **When** retrieval executes, **Then** system uses learned optimal parameters for legal queries
2. **Given** negative feedback on a query, **When** processed, **Then** retrieval parameters are adjusted for similar future queries
3. **Given** no historical data for query type, **When** query executes, **Then** system uses conservative defaults

---

### User Story 5 - Intelligent Agent Assignment (Priority: P2)

A complex task arrives that could be handled by AGENT-009 (Research Analyst) or AGENT-013 (Analysis Orchestrator). The system evaluates past performance: AGENT-013 has 92% success rate on similar tasks while AGENT-009 has 78%. The system routes to AGENT-013 and logs the decision for future learning.

**Why this priority**: Agent selection optimization improves overall system quality but requires baseline metrics.

**Independent Test**: Can be tested by submitting tasks and verifying optimal agent selection based on historical performance.

**Acceptance Scenarios**:

1. **Given** a task matching multiple agent capabilities, **When** routing, **Then** agent with highest historical success rate is selected
2. **Given** a new task type with no history, **When** routing, **Then** system uses capability matching with exploration factor
3. **Given** agent selection decision, **When** task completes, **Then** outcome is recorded for future optimization

---

### User Story 6 - Output Quality Assurance (Priority: P2)

An agent generates a response. Before delivery to user, the output validator checks: format compliance, factual consistency, completeness, and style guidelines. Issues are auto-corrected where possible (formatting), or flagged for review (factual issues).

**Why this priority**: Output validation is the final quality gate before user delivery.

**Independent Test**: Can be tested by generating outputs with known issues and verifying detection/correction.

**Acceptance Scenarios**:

1. **Given** an output with formatting issues, **When** validated, **Then** formatting is auto-corrected
2. **Given** an output missing required sections, **When** validated, **Then** missing sections are flagged
3. **Given** an output with internal contradictions, **When** validated, **Then** contradictions are highlighted for review

---

### Edge Cases

- What happens when RAGAS evaluation times out on a large context?
- How does the system handle ambiguous queries that could be multiple types?
- What happens when all agents have similar performance for a task type?
- How does grounding work when sources are conflicting?
- What happens when output validation fails repeatedly?
- How does adaptive retrieval handle adversarial feedback?

---

## Architecture

### Service Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           User Query                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Query Intent Analyzer Service                            │
│   app/services/query_intent_analyzer.py                                      │
│   - Classify: factual | analytical | comparative | procedural | creative     │
│   - Extract entities, complexity score, expected output format               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Adaptive Retrieval Service                               │
│   app/services/adaptive_retrieval_service.py                                 │
│   - Dynamic weight adjustment (Dense/Sparse/Fuzzy)                           │
│   - Query-type-specific top_k and reranking thresholds                       │
│   - Learning from feedback via reinforcement                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     RAG Query Service (Existing)                             │
│   app/services/rag_query_service.py                                          │
│   - Hybrid search with adaptive parameters                                   │
│   - Graph expansion via AGENT-017                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Retrieval Evaluator Service                              │
│   app/services/retrieval_evaluator.py                                        │
│   - RAGAS metrics: Context Relevance, Answer Relevance, Faithfulness         │
│   - Quality gates with configurable thresholds                               │
│   - Metric storage in Supabase for analytics                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Agent Selector Service                                   │
│   app/services/agent_selector_service.py                                     │
│   - Task-to-agent capability matching                                        │
│   - Historical performance tracking (17 agents)                              │
│   - Exploration vs exploitation balancing                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Agent Execution (17 Existing Agents)                     │
│   AGENT-002 through AGENT-017                                                │
│   - Process task with retrieved context                                      │
│   - Generate response                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Answer Grounding Evaluator Service                       │
│   app/services/answer_grounding_evaluator.py                                 │
│   - Claim extraction from answer                                             │
│   - Source-claim alignment scoring                                           │
│   - Citation quality assessment                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Output Validator Service                                 │
│   app/services/output_validator_service.py                                   │
│   - Format compliance checking                                               │
│   - Completeness validation                                                  │
│   - Auto-correction for fixable issues                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Final Response                                     │
│   - Quality-verified answer                                                  │
│   - Grounding scores and citations                                           │
│   - Confidence indicators                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Diagram

```
                                Query
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │   Query Intent Analyzer │
                    │   - intent_type         │
                    │   - complexity_score    │
                    │   - entities            │
                    └───────────┬─────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
    ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
    │ Simple RAG    │   │ Multi-Agent   │   │ Graph-Enhanced│
    │ (factual)     │   │ (analytical)  │   │ (relational)  │
    └───────┬───────┘   └───────┬───────┘   └───────┬───────┘
            │                   │                   │
            └───────────────────┼───────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │  Adaptive Retrieval     │
                    │  - weights per intent   │
                    │  - top_k per complexity │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │  Retrieval Evaluator    │
                    │  - context_relevance    │
                    │  - passage_quality      │
                    └───────────┬─────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
            (score >= threshold)    (score < threshold)
                    │                       │
                    ▼                       ▼
            Continue to Agent       Expand/Retry Retrieval
                    │
                    ▼
                    ┌─────────────────────────┐
                    │   Agent Selector        │
                    │   - capability match    │
                    │   - performance history │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   Selected Agent        │
                    │   (AGENT-002..017)      │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │  Answer Grounding       │
                    │  - claim extraction     │
                    │  - source alignment     │
                    │  - confidence scores    │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │  Output Validator       │
                    │  - format check         │
                    │  - completeness         │
                    │  - auto-correction      │
                    └───────────┬─────────────┘
                                │
                                ▼
                          Final Response
```

### Database Schema Extensions

```sql
-- New tables for RAG Enhancement Services

-- Table: rag_quality_metrics
CREATE TABLE rag_quality_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL,
    query_text TEXT NOT NULL,
    intent_type VARCHAR(50) NOT NULL,  -- factual, analytical, comparative, procedural, creative

    -- RAGAS Metrics
    context_relevance FLOAT,
    answer_relevance FLOAT,
    faithfulness FLOAT,
    coverage FLOAT,

    -- Retrieval Parameters Used
    retrieval_params JSONB,  -- {dense_weight, sparse_weight, fuzzy_weight, top_k}

    -- Agent Selection
    selected_agent_id VARCHAR(20),
    agent_selection_reason TEXT,

    -- Grounding
    grounding_score FLOAT,
    ungrounded_claims INTEGER DEFAULT 0,

    -- Output Validation
    validation_passed BOOLEAN DEFAULT true,
    validation_issues JSONB,

    -- Feedback
    user_feedback INTEGER,  -- -1, 0, 1
    feedback_text TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processing_time_ms INTEGER
);

-- Indexes for analytics
CREATE INDEX idx_rag_metrics_intent ON rag_quality_metrics(intent_type);
CREATE INDEX idx_rag_metrics_agent ON rag_quality_metrics(selected_agent_id);
CREATE INDEX idx_rag_metrics_created ON rag_quality_metrics(created_at);
CREATE INDEX idx_rag_metrics_quality ON rag_quality_metrics(context_relevance, faithfulness);

-- Table: agent_performance_history
CREATE TABLE agent_performance_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(20) NOT NULL,
    task_type VARCHAR(100) NOT NULL,

    -- Performance Metrics
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    avg_quality_score FLOAT,
    avg_processing_time_ms INTEGER,

    -- Time Window
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_perf_agent ON agent_performance_history(agent_id);
CREATE INDEX idx_agent_perf_task ON agent_performance_history(task_type);

-- Table: retrieval_parameter_configs
CREATE TABLE retrieval_parameter_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_type VARCHAR(50) NOT NULL,
    query_complexity VARCHAR(20) NOT NULL,  -- low, medium, high

    -- Weights
    dense_weight FLOAT DEFAULT 0.4,
    sparse_weight FLOAT DEFAULT 0.3,
    fuzzy_weight FLOAT DEFAULT 0.3,

    -- Retrieval Settings
    top_k INTEGER DEFAULT 10,
    rerank_threshold FLOAT DEFAULT 0.5,
    graph_expansion_depth INTEGER DEFAULT 1,

    -- Learning
    total_queries INTEGER DEFAULT 0,
    avg_quality_score FLOAT,
    last_updated TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(intent_type, query_complexity)
);

-- Table: grounding_results
CREATE TABLE grounding_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL,

    -- Claims
    total_claims INTEGER NOT NULL,
    grounded_claims INTEGER NOT NULL,
    ungrounded_claims INTEGER NOT NULL,

    -- Claim Details
    claim_details JSONB,  -- [{claim, grounding_score, supporting_sources}]

    -- Overall Score
    overall_grounding_score FLOAT NOT NULL,
    confidence_level VARCHAR(20),  -- high, medium, low

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_grounding_query ON grounding_results(query_id);
CREATE INDEX idx_grounding_score ON grounding_results(overall_grounding_score);
```

### Service Specifications

#### 1. Query Intent Analyzer Service

**File**: `app/services/query_intent_analyzer.py`

```python
class QueryIntentAnalyzer:
    """
    Analyzes query intent to optimize downstream processing.

    Intent Types:
    - factual: Simple fact lookup ("What is X?")
    - analytical: Deep analysis ("Analyze the implications of X")
    - comparative: Compare entities ("Compare X and Y")
    - procedural: How-to questions ("How do I X?")
    - creative: Generation tasks ("Write a summary of X")
    """

    async def analyze(self, query: str) -> QueryIntent:
        """
        Returns:
            QueryIntent with:
            - intent_type: str
            - complexity_score: float (0-1)
            - entities: list[str]
            - suggested_retrieval_strategy: str
            - expected_output_format: str
        """
        pass
```

#### 2. Adaptive Retrieval Service

**File**: `app/services/adaptive_retrieval_service.py`

```python
class AdaptiveRetrievalService:
    """
    Dynamically adjusts retrieval parameters based on query characteristics
    and historical performance.
    """

    async def get_retrieval_params(
        self,
        intent: QueryIntent
    ) -> RetrievalParams:
        """
        Returns optimized parameters:
        - dense_weight, sparse_weight, fuzzy_weight
        - top_k
        - rerank_threshold
        - graph_expansion_depth
        """
        pass

    async def record_feedback(
        self,
        query_id: str,
        params_used: RetrievalParams,
        quality_score: float,
        user_feedback: int
    ) -> None:
        """Records feedback for parameter optimization."""
        pass
```

#### 3. Retrieval Evaluator Service

**File**: `app/services/retrieval_evaluator.py`

```python
class RetrievalEvaluator:
    """
    Evaluates retrieval quality using RAGAS metrics.

    Metrics:
    - Context Relevance: Are retrieved chunks relevant to query?
    - Answer Relevance: Is the answer relevant to the query?
    - Faithfulness: Is the answer faithful to the context?
    - Coverage: Does retrieval cover all aspects of query?
    """

    async def evaluate(
        self,
        query: str,
        retrieved_contexts: list[str],
        answer: str
    ) -> RAGASMetrics:
        """
        Returns:
            RAGASMetrics with scores for each metric (0-1)
        """
        pass

    async def check_quality_gate(
        self,
        metrics: RAGASMetrics,
        thresholds: QualityThresholds
    ) -> QualityGateResult:
        """
        Returns pass/fail and recommendations.
        """
        pass
```

#### 4. Agent Selector Service

**File**: `app/services/agent_selector_service.py`

```python
class AgentSelectorService:
    """
    Intelligently routes tasks to optimal agents based on:
    - Task requirements and agent capabilities
    - Historical performance per agent per task type
    - Current agent load and availability
    """

    AGENT_CAPABILITIES = {
        "AGENT-002": ["summarization", "key_points"],
        "AGENT-003": ["skill_generation", "automation"],
        # ... all 17 agents
    }

    async def select_agent(
        self,
        task: Task,
        intent: QueryIntent
    ) -> AgentSelection:
        """
        Returns:
            AgentSelection with:
            - agent_id: str
            - confidence: float
            - reason: str
            - alternatives: list[str]
        """
        pass

    async def record_outcome(
        self,
        agent_id: str,
        task_type: str,
        success: bool,
        quality_score: float
    ) -> None:
        """Records outcome for future optimization."""
        pass
```

#### 5. Answer Grounding Evaluator Service

**File**: `app/services/answer_grounding_evaluator.py`

```python
class AnswerGroundingEvaluator:
    """
    Verifies that answer claims are grounded in source documents.
    Prevents hallucinations from reaching users.
    """

    async def evaluate(
        self,
        answer: str,
        sources: list[Document]
    ) -> GroundingResult:
        """
        Returns:
            GroundingResult with:
            - claims: list[Claim] (each with grounding_score)
            - overall_score: float
            - ungrounded_claims: list[str]
            - confidence_level: str (high/medium/low)
        """
        pass

    async def extract_claims(self, answer: str) -> list[Claim]:
        """Extracts verifiable claims from answer."""
        pass

    async def align_claim_to_sources(
        self,
        claim: Claim,
        sources: list[Document]
    ) -> float:
        """Returns alignment score 0-1."""
        pass
```

#### 6. Output Validator Service

**File**: `app/services/output_validator_service.py`

```python
class OutputValidatorService:
    """
    Validates and optionally corrects agent outputs before delivery.

    Checks:
    - Format compliance (JSON structure, markdown, etc.)
    - Completeness (required sections present)
    - Consistency (no internal contradictions)
    - Style guidelines (tone, length)
    """

    async def validate(
        self,
        output: AgentOutput,
        requirements: OutputRequirements
    ) -> ValidationResult:
        """
        Returns:
            ValidationResult with:
            - passed: bool
            - issues: list[ValidationIssue]
            - corrected_output: Optional[str]
            - corrections_made: list[str]
        """
        pass

    async def auto_correct(
        self,
        output: str,
        issues: list[ValidationIssue]
    ) -> str:
        """Attempts to fix correctable issues."""
        pass
```

---

## Requirements *(mandatory)*

### Functional Requirements

**Retrieval Evaluation**
- **FR-001**: System MUST calculate RAGAS metrics using hybrid evaluation strategy: real-time for high-value queries (complex, user-facing), batch with 10% sampling for high-volume queries, leveraging Anthropic Batch API for cost optimization
- **FR-002**: System MUST store metrics in `rag_quality_metrics` table for analytics
- **FR-003**: System MUST support configurable quality thresholds with default values
- **FR-004**: System MUST retry with expanded retrieval (increased top_k, graph expansion) when quality threshold breached, then proceed with visible "low confidence" warning if still below threshold
- **FR-005**: System MUST expose metrics via `/api/rag/metrics` endpoint
- **FR-005a**: System MUST use Claude 3.5 Haiku for evaluation to optimize cost ($0.0052/eval vs $0.0195 for Sonnet)

**Query Intent Analysis**
- **FR-006**: System MUST classify queries into: factual, analytical, comparative, procedural, creative
- **FR-007**: System MUST extract entities from queries for downstream use
- **FR-008**: System MUST calculate complexity score (0-1) based on query characteristics
- **FR-009**: System MUST suggest optimal retrieval strategy based on intent

**Answer Grounding**
- **FR-010**: System MUST extract claims from generated answers
- **FR-011**: System MUST score each claim's grounding against source documents
- **FR-012**: System MUST calculate overall grounding score for answers
- **FR-013**: System MUST flag ungrounded claims with visual indicators
- **FR-014**: System MUST block answers with grounding score below critical threshold

**Adaptive Retrieval**
- **FR-015**: System MUST maintain retrieval parameter configurations per intent type
- **FR-016**: System MUST adjust parameters based on historical quality scores
- **FR-017**: System MUST support manual override of adaptive parameters
- **FR-018**: System MUST log all parameter decisions for auditability

**Agent Selection**
- **FR-019**: System MUST map task types to agent capabilities
- **FR-020**: System MUST track agent performance per task type
- **FR-021**: System MUST select optimal agent based on performance history
- **FR-022**: System MUST support exploration factor to try underutilized agents
- **FR-023**: System MUST provide selection explanation for transparency

**Output Validation**
- **FR-024**: System MUST validate output format compliance
- **FR-025**: System MUST check for required sections/fields
- **FR-026**: System MUST detect internal contradictions
- **FR-027**: System MUST auto-correct formatting issues
- **FR-028**: System MUST flag uncorrectable issues for human review

### Key Entities

- **RAGASMetrics**: Holds retrieval quality scores (context_relevance, answer_relevance, faithfulness, coverage)
- **QueryIntent**: Represents analyzed query with intent_type, complexity, entities
- **RetrievalParams**: Configuration for hybrid search weights and settings
- **AgentSelection**: Result of agent selection with agent_id, confidence, reason
- **GroundingResult**: Claim-level grounding analysis with scores
- **ValidationResult**: Output validation status with issues and corrections

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: System measures retrieval quality for 100% of queries with RAGAS metrics
- **SC-002**: Query intent classification achieves >90% accuracy on labeled test set
- **SC-003**: Answer grounding detects >85% of hallucinated claims (based on human review)
- **SC-004**: Adaptive retrieval improves average Context Relevance by 15% over 30 days
- **SC-005**: Agent selection improves task success rate by 10% vs random/rule-based selection
- **SC-006**: Output validation catches >95% of format violations
- **SC-007**: End-to-end RAG quality score (composite RAGAS) improves from baseline by 20%
- **SC-008**: Metrics dashboard loads within 2 seconds with 30-day data
- **SC-009**: No single enhancement service adds more than 500ms latency per query
- **SC-010**: System maintains 99% availability for all enhancement services

---

## Assumptions

1. **Existing Infrastructure**: RAG query service, hybrid search, and 17 agents are operational
2. **LLM Availability**: Claude API is available for RAGAS evaluation and claim extraction
3. **Database Capacity**: Supabase can handle additional tables and query volume
4. **Metrics Storage**: 30-day retention is sufficient for trend analysis
5. **Agent Capabilities**: Agent capabilities are well-defined and stable
6. **User Feedback**: Some queries will receive explicit user feedback for learning

---

## Dependencies

1. **RAG Query Service**: `app/services/rag_query_service.py` - Core retrieval functionality
2. **Existing 17 Agents**: All agents must be operational for selection optimization
3. **Supabase**: Database for metrics storage and analytics
4. **Claude API**: For LLM-based evaluation (RAGAS, claim extraction)
5. **Redis**: For caching frequently accessed configurations

---

## Implementation Phases

### Phase 1: Foundation (P1 - Critical)
- Retrieval Evaluator Service
- Query Intent Analyzer Service
- Answer Grounding Evaluator Service
- Database schema for metrics

### Phase 2: Optimization (P2 - Important)
- Adaptive Retrieval Service
- Agent Selector Service
- Output Validator Service
- Performance dashboards

### Phase 3: Analytics (P3 - Enhancement)
- Quality trend dashboards
- A/B testing framework for parameters
- Automated parameter tuning
- Alert system for quality degradation
