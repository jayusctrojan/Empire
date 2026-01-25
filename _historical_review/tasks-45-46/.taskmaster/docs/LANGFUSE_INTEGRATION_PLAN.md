# Langfuse Integration Plan for Empire v7.3

**Document Version**: 1.0
**Created**: 2025-01-07
**Status**: APPROVED - Implementation starts after Task 26
**Estimated Effort**: 5-7 days (1 developer)
**Estimated Cost**: $3,500 implementation + $0-49/month ongoing

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Integration Timeline](#integration-timeline)
3. [Technical Architecture](#technical-architecture)
4. [Implementation Phases](#implementation-phases)
5. [Code Examples](#code-examples)
6. [Deployment Options](#deployment-options)
7. [Testing & Validation](#testing--validation)
8. [Cost Analysis](#cost-analysis)
9. [Success Metrics](#success-metrics)

---

## Executive Summary

### Why Langfuse?
- **Framework-Agnostic**: Works with Empire's FastAPI + Anthropic + CrewAI stack (no LangChain required)
- **Open Source**: MIT license, self-hostable, no vendor lock-in
- **Low Integration Effort**: Single `@observe()` decorator per function
- **Cost-Effective**: FREE for 50K events/month or $20/month self-hosted vs LangSmith's $100K+/year
- **Comprehensive**: Tracing, prompt management, evaluations, cost tracking in one platform

### Strategic Value
1. **Complements RAGAS**: Quality metrics (RAGAS) + Production tracing (Langfuse)
2. **Enables Cost Optimization**: Real-time visibility into Claude, Mistral, Soniox API costs
3. **Accelerates CrewAI Development**: Multi-agent workflow observability (Tasks 35-40)
4. **Reduces Debugging Time**: 50% faster LLM issue resolution via trace analysis

### Integration Approach
- **Phase 1** (Week 4): Minimal integration during Task 29 (2-3 days)
- **Phase 2** (Week 5-6): Full integration with cost tracking and prompts (3-4 days)
- **Phase 3** (Week 7+): CrewAI multi-agent tracing during Tasks 35-40

---

## Integration Timeline

### Current Project Status
- **Completion**: 46.7% (21/45 tasks done)
- **Active Tasks**: 22-25 (Query Processing, Analytics)
- **Next Critical**: Task 26 (Chat UI) - **DO NOT INTEGRATE YET**
- **Integration Start**: Task 29 (Monitoring & Observability)

### Phased Rollout Schedule

```
Week 1-3 (NOW - Task 26 Complete):
├── Complete Chat UI deployment
├── NO Langfuse integration yet
└── Prepare infrastructure for observability

Week 4 (Task 29 - Minimal Integration):
├── Day 1: Deploy Langfuse (Docker on Render)
├── Day 2: Instrument core RAG pipeline (5-6 key functions)
├── Day 3: Integrate with Grafana dashboards
└── Deliverable: Basic tracing + visualization

Week 5 (Task 30 - Cost Tracking Integration):
├── Day 1: Instrument all Claude API calls
├── Day 2: Add cost tracking for Mistral, Soniox, LangExtract
├── Day 3: Build cost dashboards in Grafana
└── Deliverable: Real-time cost monitoring

Week 6 (Task 29-30 - Prompt Management):
├── Day 1: Centralize query expansion prompts
├── Day 2: Set up prompt versioning
├── Day 3: Implement A/B testing for prompts
└── Deliverable: Managed prompt library

Week 7+ (Tasks 35-40 - CrewAI Tracing):
├── Instrument all 15 CrewAI agents
├── Multi-agent workflow visualization
└── Deliverable: Full agent orchestration observability
```

---

## Technical Architecture

### Empire v7.3 Stack + Langfuse Integration

```
┌─────────────────────────────────────────────────────────────┐
│                    Empire v7.3 Services                      │
├─────────────────────────────────────────────────────────────┤
│  FastAPI (Render)        Celery (Render)      CrewAI (Render)│
│      ↓                        ↓                     ↓         │
│  @observe()              @observe()          @observe()      │
│      ↓                        ↓                     ↓         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Langfuse SDK (Python)                       │   │
│  │  - Automatic trace collection                         │   │
│  │  - Cost tracking                                      │   │
│  │  - Prompt versioning                                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ↓                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │    Langfuse Server (Self-Hosted on Render)           │   │
│  │  - PostgreSQL (Supabase)                             │   │
│  │  - Redis (Upstash)                                   │   │
│  │  - Web UI (Port 3000)                                │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ↓                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          Metrics Export (OpenTelemetry)              │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ↓                                    │
├─────────────────────────────────────────────────────────────┤
│              Existing Observability Stack                    │
├─────────────────────────────────────────────────────────────┤
│  Prometheus (Task 29)    Grafana (Task 29)   RAGAS (Task 45)│
│      ↓                        ↓                     ↓         │
│  Infrastructure       ┌──────────────────┐    RAG Quality   │
│  Metrics              │ Unified Dashboard│    Metrics       │
│                       │  - Infra metrics │                   │
│                       │  - LLM traces    │                   │
│                       │  - RAG quality   │                   │
│                       │  - Cost tracking │                   │
│                       └──────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Query
    ↓
FastAPI Endpoint (@observe)
    ↓
Query Expansion (Claude Haiku) → Langfuse trace + cost
    ↓
Hybrid Search (Supabase) → Langfuse span
    ↓
Reranking (BGE-Reranker-v2) → Langfuse span
    ↓
Response Generation (Claude Sonnet) → Langfuse trace + cost
    ↓
Langfuse Server (aggregates all traces)
    ↓
Grafana Dashboard (real-time visualization)
```

---

## Implementation Phases

### Phase 1: Minimal Integration (Week 4, Task 29)

**Goal**: Get basic tracing working with minimal code changes
**Effort**: 2-3 days
**Impact**: Immediate visibility into RAG pipeline performance

#### Step 1.1: Deploy Langfuse Server (Day 1)

**Option A: Self-Hosted on Render** (Recommended)
```bash
# 1. Create Langfuse service on Render
# Service Type: Web Service
# Docker Image: langfuse/langfuse:latest
# Environment Variables:
NEXTAUTH_SECRET=<from .env>
SALT=<from .env>
DATABASE_URL=<Supabase PostgreSQL connection string>
NEXTAUTH_URL=https://jb-empire-langfuse.onrender.com
TELEMETRY_ENABLED=false

# 2. Configure in .env
LANGFUSE_HOST=https://jb-empire-langfuse.onrender.com
LANGFUSE_PUBLIC_KEY=<generate in Langfuse UI>
LANGFUSE_SECRET_KEY=<generate in Langfuse UI>
```

**Option B: Langfuse Cloud** (Simpler, but less control)
```bash
# Skip deployment, use Langfuse Cloud
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=<from Langfuse dashboard>
LANGFUSE_SECRET_KEY=<from Langfuse dashboard>
```

**Deliverable**: Langfuse dashboard accessible at https://jb-empire-langfuse.onrender.com

---

#### Step 1.2: Install SDK and Instrument Core Functions (Day 2)

**Install Langfuse SDK**:
```bash
pip install langfuse
```

**Add to requirements.txt**:
```txt
langfuse>=2.20.0
```

**Instrument 6 Critical Functions** (from empire-arch.txt):

**File: `app/services/query_processing.py`**
```python
from langfuse.decorators import observe

# Task 19: Query Expansion
@observe()  # <-- Add this decorator
async def expand_query_with_claude_haiku(query: str) -> list[str]:
    """
    Existing function - NO CHANGES TO LOGIC
    Langfuse automatically captures:
    - Input: query
    - Output: expanded queries
    - Latency, tokens, cost
    """
    response = anthropic_client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=150,
        messages=[{
            "role": "user",
            "content": f"Generate 4-5 query variations for: {query}"
        }]
    )
    return response.content[0].text.split('\n')
```

**File: `app/services/hybrid_search.py`**
```python
from langfuse.decorators import observe

# Task 18: Hybrid Search
@observe()  # <-- Add this decorator
async def hybrid_search(
    query: str,
    top_k: int = 20
) -> list[dict]:
    """
    Existing function - NO CHANGES TO LOGIC
    Langfuse captures nested calls:
    - dense_search() span
    - sparse_search() span
    - fuzzy_search() span
    - reciprocal_rank_fusion() span
    """
    # Existing code unchanged
    dense_results = await dense_search(query, top_k)
    sparse_results = await sparse_search(query, top_k)
    fuzzy_results = await fuzzy_search(query, top_k)

    merged = reciprocal_rank_fusion(
        [dense_results, sparse_results, fuzzy_results]
    )
    return merged[:top_k]

# Also instrument nested functions
@observe()
async def dense_search(query: str, top_k: int) -> list[dict]:
    # Existing pgvector similarity search
    pass

@observe()
async def sparse_search(query: str, top_k: int) -> list[dict]:
    # Existing BM25 search
    pass

@observe()
async def fuzzy_search(query: str, top_k: int) -> list[dict]:
    # Existing ILIKE + rapidfuzz search
    pass

@observe()
def reciprocal_rank_fusion(result_lists: list[list[dict]]) -> list[dict]:
    # Existing RRF logic
    pass
```

**File: `app/services/reranking.py`**
```python
from langfuse.decorators import observe

# Task 19: Reranking
@observe()  # <-- Add this decorator
async def rerank_with_bge_reranker(
    query: str,
    candidates: list[dict],
    top_k: int = 10
) -> list[dict]:
    """
    Existing function - NO CHANGES TO LOGIC
    """
    # Existing BGE-Reranker-v2 API call via Ollama
    pass
```

**File: `app/api/routes/search.py`**
```python
from langfuse.decorators import observe

# Task 26: Chat UI endpoint
@observe()  # <-- Add this decorator
@app.post("/api/search")
async def search_endpoint(request: SearchRequest) -> SearchResponse:
    """
    Top-level endpoint - captures full request trace
    Nested @observe() calls create parent-child spans
    """
    # Existing code unchanged
    expanded = await expand_query_with_claude_haiku(request.query)
    results = await hybrid_search(expanded[0])
    reranked = await rerank_with_bge_reranker(request.query, results)

    return SearchResponse(results=reranked)
```

**Total Lines Changed**: ~6 decorators across 6 functions

**Deliverable**: All RAG pipeline calls traced in Langfuse UI

---

#### Step 1.3: Integrate with Grafana (Day 3)

**Export Langfuse metrics to Prometheus**:
```python
# File: app/monitoring/langfuse_exporter.py
from prometheus_client import Counter, Histogram
from langfuse import Langfuse

langfuse = Langfuse()

# Define metrics
llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM requests',
    ['model', 'status']
)

llm_latency_seconds = Histogram(
    'llm_latency_seconds',
    'LLM request latency',
    ['model']
)

llm_cost_usd = Counter(
    'llm_cost_usd',
    'LLM API cost in USD',
    ['model']
)

# Sync Langfuse traces to Prometheus (run every 60s)
async def export_langfuse_metrics():
    # Query Langfuse API for recent traces
    traces = langfuse.get_traces(
        from_timestamp=datetime.now() - timedelta(minutes=1)
    )

    for trace in traces:
        model = trace.metadata.get('model', 'unknown')
        llm_requests_total.labels(model=model, status='success').inc()
        llm_latency_seconds.labels(model=model).observe(trace.latency)
        llm_cost_usd.labels(model=model).inc(trace.cost_usd)
```

**Add to Grafana dashboard** (from Task 29):
```yaml
# File: monitoring/grafana/dashboards/empire-langfuse.json
{
  "dashboard": {
    "title": "Empire LLM Observability",
    "panels": [
      {
        "title": "LLM Request Rate",
        "targets": [
          {
            "expr": "rate(llm_requests_total[5m])",
            "legendFormat": "{{model}}"
          }
        ]
      },
      {
        "title": "LLM Latency (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, llm_latency_seconds)",
            "legendFormat": "{{model}}"
          }
        ]
      },
      {
        "title": "LLM Cost per Hour",
        "targets": [
          {
            "expr": "rate(llm_cost_usd[1h])",
            "legendFormat": "{{model}}"
          }
        ]
      }
    ]
  }
}
```

**Deliverable**: Unified Grafana dashboard showing infrastructure + LLM metrics

---

### Phase 2: Cost Tracking Integration (Week 5, Task 30)

**Goal**: Real-time cost visibility for all LLM API calls
**Effort**: 3-4 days
**Impact**: 10-20% cost reduction via optimization insights

#### Step 2.1: Instrument All Claude API Calls (Day 1)

**Centralize Claude client with cost tracking**:

**File: `app/services/llm_clients/claude_client.py`**
```python
from langfuse.decorators import observe
from langfuse import Langfuse
import anthropic
import os

langfuse = Langfuse()

class ClaudeClient:
    """
    Centralized Claude client with automatic cost tracking
    """
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )

        # Cost per 1M tokens (as of 2025-01-01)
        self.pricing = {
            "claude-3-5-sonnet-20241022": {
                "input": 3.00,   # $3 per 1M input tokens
                "output": 15.00  # $15 per 1M output tokens
            },
            "claude-3-5-haiku-20241022": {
                "input": 1.00,   # $1 per 1M input tokens
                "output": 5.00   # $5 per 1M output tokens
            }
        }

    @observe(as_type="generation")  # Special decorator for LLM calls
    async def create_message(
        self,
        model: str,
        max_tokens: int,
        messages: list[dict],
        **kwargs
    ) -> anthropic.types.Message:
        """
        Wrapper for anthropic.messages.create with automatic cost tracking
        """
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
            **kwargs
        )

        # Calculate cost
        input_cost = (response.usage.input_tokens / 1_000_000) * self.pricing[model]["input"]
        output_cost = (response.usage.output_tokens / 1_000_000) * self.pricing[model]["output"]
        total_cost = input_cost + output_cost

        # Log to Langfuse (automatic via decorator)
        langfuse.score(
            name="cost_usd",
            value=total_cost,
            data_type="numeric"
        )

        return response

# Singleton instance
claude_client = ClaudeClient()
```

**Update all Claude calls to use centralized client**:

**Before**:
```python
# Old code - direct Anthropic API
import anthropic

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-3-5-haiku-20241022",
    max_tokens=150,
    messages=[{"role": "user", "content": query}]
)
```

**After**:
```python
# New code - centralized client with cost tracking
from app.services.llm_clients.claude_client import claude_client

response = await claude_client.create_message(
    model="claude-3-5-haiku-20241022",
    max_tokens=150,
    messages=[{"role": "user", "content": query}]
)
```

**Files to Update**:
1. `app/services/query_processing.py` (query expansion)
2. `app/services/classification.py` (department classification, Task 9)
3. `app/services/document_processing.py` (summarization, extraction)
4. Any other Claude API calls

**Deliverable**: All Claude costs tracked in Langfuse

---

#### Step 2.2: Add Cost Tracking for Other APIs (Day 2)

**Mistral OCR** (Task 10):
```python
from langfuse.decorators import observe

@observe(as_type="generation")
async def mistral_ocr_extract(file_path: str) -> str:
    # Existing Mistral API call
    response = mistral_client.ocr(file_path)

    # Log cost (estimate $0.01 per page)
    langfuse.score(
        name="cost_usd",
        value=response.page_count * 0.01
    )

    return response.text
```

**Soniox Audio Transcription** (Task 11):
```python
from langfuse.decorators import observe

@observe(as_type="generation")
async def soniox_transcribe(audio_path: str) -> dict:
    # Existing Soniox API call
    response = soniox_client.transcribe(audio_path)

    # Log cost ($0.005 per minute)
    duration_minutes = response.duration_seconds / 60
    langfuse.score(
        name="cost_usd",
        value=duration_minutes * 0.005
    )

    return response
```

**LangExtract Entity Extraction** (Task 12):
```python
from langfuse.decorators import observe

@observe(as_type="generation")
async def langextract_entities(text: str) -> dict:
    # Existing LangExtract API call
    response = langextract_client.extract(text)

    # Log cost (estimate based on token count)
    token_count = len(text.split())
    cost = (token_count / 1_000_000) * 2.00  # $2 per 1M tokens
    langfuse.score(
        name="cost_usd",
        value=cost
    )

    return response
```

**Deliverable**: Comprehensive cost tracking for all external APIs

---

#### Step 2.3: Build Cost Dashboards (Day 3)

**Grafana dashboard with cost breakdowns**:

```yaml
# File: monitoring/grafana/dashboards/empire-cost-tracking.json
{
  "dashboard": {
    "title": "Empire API Cost Tracking",
    "panels": [
      {
        "title": "Total Cost per Day",
        "targets": [
          {
            "expr": "sum(increase(llm_cost_usd[1d])) by (model)",
            "legendFormat": "{{model}}"
          }
        ],
        "visualization": "timeseries"
      },
      {
        "title": "Cost per API Provider",
        "targets": [
          {
            "expr": "sum(llm_cost_usd) by (provider)",
            "legendFormat": "{{provider}}"
          }
        ],
        "visualization": "piechart"
      },
      {
        "title": "Cost vs Budget",
        "targets": [
          {
            "expr": "sum(increase(llm_cost_usd[1M])) / 500",  # $500/month budget
            "legendFormat": "% of budget"
          }
        ],
        "thresholds": [
          { "value": 0.8, "color": "yellow" },
          { "value": 1.0, "color": "red" }
        ]
      },
      {
        "title": "Top 10 Expensive Traces",
        "type": "table",
        "datasource": "Langfuse",
        "targets": [
          {
            "query": "SELECT * FROM traces ORDER BY cost_usd DESC LIMIT 10"
          }
        ]
      }
    ]
  }
}
```

**Set up cost alerts** (from Task 29 Alertmanager):
```yaml
# File: monitoring/alert_rules.yml
groups:
  - name: cost_alerts
    rules:
      - alert: HighDailyCost
        expr: sum(increase(llm_cost_usd[1d])) > 50
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Daily LLM cost exceeds $50"

      - alert: BudgetThresholdExceeded
        expr: sum(increase(llm_cost_usd[1M])) > 400  # 80% of $500
        for: 1h
        labels:
          severity: critical
        annotations:
          summary: "Monthly budget at 80% ($400/$500)"
```

**Deliverable**: Real-time cost dashboard with budget alerts

---

### Phase 3: Prompt Management (Week 6, Tasks 29-30)

**Goal**: Centralize and version-control all LLM prompts
**Effort**: 3-4 days
**Impact**: Faster prompt iteration, A/B testing capability

#### Step 3.1: Migrate Prompts to Langfuse (Day 1)

**Query Expansion Prompt** (Task 19):
```python
# BEFORE: Hardcoded prompt
async def expand_query_with_claude_haiku(query: str):
    response = await claude_client.create_message(
        model="claude-3-5-haiku-20241022",
        max_tokens=150,
        messages=[{
            "role": "user",
            "content": f"Generate 4-5 query variations for: {query}"
        }]
    )

# AFTER: Prompt from Langfuse
from langfuse import Langfuse

langfuse = Langfuse()

async def expand_query_with_claude_haiku(query: str):
    # Fetch latest prompt version from Langfuse
    prompt = langfuse.get_prompt("query-expansion")

    response = await claude_client.create_message(
        model=prompt.config["model"],
        max_tokens=prompt.config["max_tokens"],
        messages=[{
            "role": "user",
            "content": prompt.compile(query=query)
        }]
    )
```

**Create prompt in Langfuse UI**:
```
Name: query-expansion
Version: 1.0.0
Model: claude-3-5-haiku-20241022
Max Tokens: 150
Prompt Template:
---
Generate 4-5 query variations for the following search query.
Focus on:
- Synonym expansion
- Related concepts
- Different phrasings
- Technical vs casual language

Query: {{query}}

Return ONLY the query variations, one per line.
---
```

**Department Classification Prompt** (Task 9):
```
Name: department-classification
Version: 1.0.0
Model: claude-3-5-haiku-20241022
Max Tokens: 50
Prompt Template:
---
Classify this document into ONE of these departments:

1. Engineering
2. Sales
3. Marketing
4. HR
5. Finance
6. Legal
7. Operations
8. Product
9. Customer Support
10. Executive

Document title: {{title}}
Document content (first 500 chars): {{content}}

Return ONLY the department name.
---
```

**Deliverable**: 5-10 key prompts managed in Langfuse

---

#### Step 3.2: Set Up Prompt Versioning (Day 2)

**Create prompt versions for A/B testing**:

```python
# Version 1.0.0: Original query expansion
prompt_v1 = langfuse.create_prompt(
    name="query-expansion",
    prompt="Generate 4-5 query variations for: {{query}}",
    config={"model": "claude-3-5-haiku-20241022", "max_tokens": 150}
)

# Version 2.0.0: More detailed instructions
prompt_v2 = langfuse.create_prompt(
    name="query-expansion",
    prompt="""Generate 4-5 query variations with these strategies:
    1. Synonym expansion
    2. Technical/casual phrasing
    3. Related concepts
    4. Question reformulation

    Query: {{query}}

    Return variations one per line.""",
    config={"model": "claude-3-5-haiku-20241022", "max_tokens": 200}
)

# Version 3.0.0: Use Claude Sonnet for better quality
prompt_v3 = langfuse.create_prompt(
    name="query-expansion",
    prompt=prompt_v2.prompt,  # Same prompt
    config={"model": "claude-3-5-sonnet-20241022", "max_tokens": 200}
)
```

**Implement A/B testing**:
```python
import random

async def expand_query_with_claude_haiku(query: str):
    # 50/50 split between v2 (Haiku) and v3 (Sonnet)
    version = "2.0.0" if random.random() < 0.5 else "3.0.0"

    prompt = langfuse.get_prompt("query-expansion", version=version)

    # Langfuse tracks which version was used
    response = await claude_client.create_message(
        model=prompt.config["model"],
        max_tokens=prompt.config["max_tokens"],
        messages=[{
            "role": "user",
            "content": prompt.compile(query=query)
        }]
    )

    return response
```

**Deliverable**: A/B testing framework for prompt optimization

---

#### Step 3.3: Implement Prompt Analytics (Day 3)

**Track prompt performance**:
```python
from langfuse import Langfuse

langfuse = Langfuse()

async def expand_query_with_claude_haiku(query: str):
    prompt = langfuse.get_prompt("query-expansion")

    response = await claude_client.create_message(
        model=prompt.config["model"],
        max_tokens=prompt.config["max_tokens"],
        messages=[{
            "role": "user",
            "content": prompt.compile(query=query)
        }]
    )

    # Track prompt effectiveness
    langfuse.score(
        trace_id=langfuse.get_trace_id(),
        name="query_expansion_quality",
        value=len(response.content[0].text.split('\n')),  # Number of variations
        comment=f"Used prompt version {prompt.version}"
    )

    return response
```

**Analyze in Langfuse UI**:
- Compare average quality score between versions
- Identify which version has lower latency
- Calculate cost difference between Haiku (v2) and Sonnet (v3)

**Deliverable**: Data-driven prompt optimization insights

---

### Phase 4: CrewAI Multi-Agent Tracing (Week 7+, Tasks 35-40)

**Goal**: Full observability for 15 CrewAI agents across 8 workflows
**Effort**: Ongoing during Tasks 35-40
**Impact**: Debug complex multi-agent interactions 10x faster

#### Step 4.1: Instrument CrewAI Agents

**From empire-arch.txt Task 35-40, Empire has 15 agents**:

```python
# File: app/services/crewai/agents.py
from langfuse.decorators import observe
from crewai import Agent, Task, Crew

# Instrument each agent's execution
@observe(name="orchestrator_agent")
async def create_orchestrator_agent():
    return Agent(
        role="Orchestrator",
        goal="Coordinate multi-agent workflows",
        backstory="Expert at task delegation and workflow management",
        verbose=True,
        allow_delegation=True
    )

@observe(name="summarizer_agent")
async def create_summarizer_agent():
    return Agent(
        role="Document Summarizer",
        goal="Create concise, accurate document summaries",
        backstory="Expert at distilling key information",
        verbose=True
    )

# ... repeat for all 15 agents
```

**Instrument crew execution**:
```python
from langfuse.decorators import observe

@observe(name="crewai_workflow")
async def run_document_analysis_workflow(document_id: str):
    """
    Langfuse will create parent trace for entire workflow
    Each agent task becomes a child span
    """
    # Create crew
    crew = Crew(
        agents=[
            orchestrator_agent,
            research_analyst_agent,
            content_strategist_agent,
            fact_checker_agent
        ],
        tasks=[
            research_task,
            strategy_task,
            fact_check_task
        ],
        process="sequential"  # or "hierarchical"
    )

    # Execute workflow
    result = crew.kickoff(inputs={"document_id": document_id})

    # Langfuse captures:
    # - Total workflow duration
    # - Each agent's execution time
    # - Inter-agent messaging
    # - Final output

    return result
```

**Visualize in Langfuse UI**:
```
Trace: Document Analysis Workflow (#12345)
├─ Span: Orchestrator Agent (2.3s)
│  └─ Generation: Task delegation prompt (0.5s)
├─ Span: Research Analyst Agent (15.7s)
│  ├─ Generation: Research planning (1.2s)
│  ├─ Span: Web search (8.3s)
│  └─ Generation: Research synthesis (6.2s)
├─ Span: Content Strategist Agent (8.4s)
│  └─ Generation: Strategy creation (8.4s)
└─ Span: Fact Checker Agent (12.1s)
   ├─ Generation: Fact extraction (3.2s)
   ├─ Span: External verification (7.8s)
   └─ Generation: Verification report (1.1s)

Total Duration: 38.5s
Total Cost: $0.47
Agents Used: 4/15
```

**Deliverable**: Full multi-agent workflow observability

---

## Deployment Options

### Option A: Self-Hosted on Render (Recommended)

**Pros**:
- ✅ Full data control (GDPR/HIPAA compliant)
- ✅ No vendor lock-in
- ✅ Customizable
- ✅ Cost-effective: ~$20/month

**Cons**:
- ⚠️ Requires maintenance
- ⚠️ You manage updates

**Deployment Steps**:

```bash
# 1. Create new Render Web Service
Service Name: empire-langfuse
Docker Image: langfuse/langfuse:latest
Instance Type: Starter ($7/month)
Region: Oregon (same as Empire API)

# 2. Environment Variables (add to Render dashboard)
DATABASE_URL=<Supabase PostgreSQL connection string>
NEXTAUTH_URL=https://empire-langfuse.onrender.com
NEXTAUTH_SECRET=<generate with: openssl rand -base64 32>
SALT=<generate with: openssl rand -base64 32>
TELEMETRY_ENABLED=false
LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES=true

# 3. Connect to existing Supabase PostgreSQL
# Langfuse will auto-create its tables in Supabase

# 4. Access Langfuse UI
# Navigate to: https://empire-langfuse.onrender.com
# Create admin account
# Generate API keys
```

**Cost Breakdown**:
- Render Web Service: $7/month
- Database: $0 (uses existing Supabase)
- Total: **$7/month**

---

### Option B: Langfuse Cloud

**Pros**:
- ✅ Zero maintenance
- ✅ Instant setup (5 minutes)
- ✅ Managed updates

**Cons**:
- ⚠️ Data stored on Langfuse servers
- ⚠️ Vendor lock-in

**Deployment Steps**:

```bash
# 1. Sign up at https://cloud.langfuse.com
# 2. Create project: "Empire v7.3"
# 3. Copy API keys to .env
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

**Cost Breakdown**:
- Free tier: 50,000 events/month (sufficient for Phase 1)
- Hobby tier: $49/month (1M events/month)
- Estimated for Empire: **$0-49/month**

---

### Recommendation: Start with Cloud, Migrate to Self-Hosted

**Phase 1 (Week 4)**: Use Langfuse Cloud
- Zero setup time
- Validate integration quickly
- Free tier sufficient

**Phase 2 (Week 6)**: Migrate to self-hosted
- Once integration is proven
- Better cost economics ($7 vs $49/month)
- Full data control

**Migration is seamless**: Export/import via Langfuse API

---

## Testing & Validation

### Test Plan

#### Phase 1 Tests (Minimal Integration)
```bash
# Test 1: Basic tracing works
curl -X POST https://jb-empire-api.onrender.com/api/search \
  -d '{"query": "California insurance policy"}' \
  -H "Content-Type: application/json"

# Verify in Langfuse UI:
# - Trace appears within 30 seconds
# - All spans present (expansion, search, reranking)
# - Latencies reasonable (<2s total)

# Test 2: Cost tracking works
# Check Langfuse UI for cost data
# Expected: $0.001-0.005 per query

# Test 3: Grafana integration works
# Open Grafana dashboard
# Verify LLM metrics appear alongside infrastructure metrics
```

#### Phase 2 Tests (Cost Tracking)
```bash
# Test 1: All API costs tracked
# Process 10 documents through pipeline
# Verify costs for:
# - Claude (query expansion, classification, summarization)
# - Mistral OCR (scanned PDFs)
# - Soniox (audio transcription)
# - LangExtract (entity extraction)

# Test 2: Cost alerts work
# Artificially trigger high-cost scenario
# Verify Alertmanager sends notification

# Test 3: Budget tracking accurate
# Compare Langfuse costs with actual API bills
# Should match within 5%
```

#### Phase 3 Tests (Prompt Management)
```bash
# Test 1: Prompt versioning works
# Create new prompt version
# Verify old queries use old version
# Verify new queries use new version

# Test 2: A/B testing works
# Enable 50/50 split for query expansion
# Process 100 queries
# Verify ~50 use each version

# Test 3: Prompt analytics accurate
# Compare quality scores between versions
# Statistical significance test (t-test)
```

#### Phase 4 Tests (CrewAI Tracing)
```bash
# Test 1: Multi-agent workflow traced
# Run document analysis workflow
# Verify all 4 agents appear in trace
# Verify spans show correct parent-child relationships

# Test 2: Agent interaction tracking
# Check inter-agent messaging logs
# Verify delegation events captured

# Test 3: Workflow debugging
# Intentionally fail one agent
# Verify error propagation visible in trace
```

---

### Success Metrics

#### Technical Metrics
- **Trace Coverage**: >95% of LLM calls traced
- **Trace Latency Overhead**: <50ms per request
- **Cost Tracking Accuracy**: Within 5% of actual bills
- **Dashboard Update Latency**: <60 seconds

#### Business Metrics
- **Cost Reduction**: 10-20% via optimization insights (6 months)
- **Debugging Speed**: 50% faster LLM issue resolution
- **Prompt Iteration Speed**: 3x faster (via A/B testing)
- **Incident Detection**: <5 minutes (via alerts)

#### Adoption Metrics
- **Team Usage**: 100% of developers using Langfuse UI weekly
- **Prompt Management**: 100% of prompts centralized in Langfuse
- **Dashboard Views**: Daily views of cost/performance dashboards

---

## Cost Analysis

### Implementation Costs

```
Development Time:
├── Phase 1 (Minimal): 2-3 days × $500/day = $1,000-1,500
├── Phase 2 (Cost Tracking): 3-4 days × $500/day = $1,500-2,000
├── Phase 3 (Prompts): 3-4 days × $500/day = $1,500-2,000
└── Phase 4 (CrewAI): Ongoing, already budgeted in Tasks 35-40

Total Implementation: $4,000-5,500 (one-time)
```

### Ongoing Costs

**Option A: Self-Hosted**
```
Render Web Service (Starter): $7/month
Database: $0 (existing Supabase)
Maintenance: ~1 hour/month = $50/month (amortized)

Total: $57/month = $684/year
```

**Option B: Langfuse Cloud**
```
Free tier (50K events): $0/month
Hobby tier (1M events): $49/month
Pro tier (10M events): $199/month

Empire estimate: 100-200K events/month
Total: $49/month = $588/year
```

**Recommended**: Start with Langfuse Cloud ($0), migrate to self-hosted ($7/month) after Phase 1

---

### ROI Analysis

**Cost Savings (6 months)**:
1. **LLM Cost Optimization**: 10-20% reduction via insights
   - Current LLM spend: ~$500/month (Claude, Mistral, Soniox, LangExtract)
   - Savings: $50-100/month × 6 = **$300-600**

2. **Development Time Savings**: Faster debugging/iteration
   - Before: 2 hours/week debugging LLM issues
   - After: 1 hour/week (50% reduction)
   - Savings: 1 hour/week × 26 weeks × $500/day ÷ 8 = **$1,625**

3. **Prevented Custom Development**: Avoid building tracing/prompts from scratch
   - Estimated effort: 3-4 weeks
   - Savings: 20 days × $500 = **$10,000**

**Total Value (6 months)**: $11,925-12,225
**Total Cost (6 months)**: $4,500 implementation + $294 ongoing = $4,794
**Net ROI**: **$7,131-7,431** (148% return)

---

## Next Steps

### Immediate (Week 1-3, NOW)
1. ✅ Complete Tasks 22-26 (Query Processing, Chat UI)
2. ✅ Document finalized in `.taskmaster/docs/LANGFUSE_INTEGRATION_PLAN.md`
3. ⏸️ **DO NOT start Langfuse integration yet**

### Week 4 (Task 29, Start Integration)
1. 🚀 Deploy Langfuse (Option B: Cloud for now)
2. 🚀 Implement Phase 1: Minimal Integration (2-3 days)
3. 🚀 Integrate with Grafana dashboards

### Week 5 (Task 30, Cost Tracking)
1. 🚀 Implement Phase 2: Cost Tracking (3-4 days)
2. 🚀 Set up cost alerts in Alertmanager
3. 🚀 Migrate to self-hosted if desired

### Week 6 (Tasks 29-30, Prompt Management)
1. 🚀 Implement Phase 3: Prompt Management (3-4 days)
2. 🚀 Centralize all prompts in Langfuse
3. 🚀 Set up A/B testing for query expansion

### Week 7+ (Tasks 35-40, CrewAI)
1. 🚀 Implement Phase 4: Multi-Agent Tracing (ongoing)
2. 🚀 Instrument all 15 CrewAI agents
3. 🚀 Build agent performance dashboards

---

## Approval & Sign-off

**Document Status**: ✅ APPROVED
**Implementation Start**: After Task 26 completion
**Estimated Completion**: Week 8 (Phase 1-3 complete)
**Budget Approved**: $5,500 implementation + $49/month ongoing

**Signed**: Jay Bajaj
**Date**: 2025-01-07

---

## Appendix

### A. Langfuse API Reference
- **Documentation**: https://langfuse.com/docs
- **Python SDK**: https://langfuse.com/docs/sdk/python
- **FastAPI Integration**: https://langfuse.com/docs/integrations/fastapi
- **OpenTelemetry**: https://langfuse.com/docs/integrations/opentelemetry

### B. Empire Integration Files
```
Empire Project Structure (Langfuse-related):

app/
├── services/
│   ├── llm_clients/
│   │   ├── claude_client.py          # Centralized Claude client with cost tracking
│   │   ├── mistral_client.py         # Mistral OCR with Langfuse
│   │   ├── soniox_client.py          # Soniox with Langfuse
│   │   └── langextract_client.py     # LangExtract with Langfuse
│   ├── query_processing.py           # @observe decorators added
│   ├── hybrid_search.py              # @observe decorators added
│   ├── reranking.py                  # @observe decorators added
│   └── crewai/
│       ├── agents.py                 # All 15 agents instrumented
│       └── workflows.py              # Crew execution instrumented
├── monitoring/
│   ├── langfuse_exporter.py          # Prometheus metrics exporter
│   └── grafana/
│       └── dashboards/
│           ├── empire-langfuse.json  # LLM observability dashboard
│           └── empire-cost.json      # Cost tracking dashboard
├── api/
│   └── routes/
│       └── search.py                 # @observe on endpoints
└── config/
    └── langfuse.py                   # Langfuse configuration

.env (add these variables):
LANGFUSE_HOST=https://cloud.langfuse.com  # or self-hosted URL
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

monitoring/
├── alert_rules.yml                   # Cost alerts for Alertmanager
└── prometheus.yml                    # Add Langfuse exporter target
```

### C. Comparison: Before vs After Langfuse

**Before (Current State)**:
```
Problem: LLM costs increasing, no visibility
├── Manual cost tracking (Task 30 custom implementation)
├── No trace visibility for debugging
├── Prompts hardcoded in source code
├── No A/B testing capability
└── Multi-agent workflows are black boxes

Result: Slow debugging, unpredictable costs, manual prompt iteration
```

**After (With Langfuse)**:
```
Solution: Complete LLM observability
├── Real-time cost tracking with alerts
├── Full trace visibility (input/output/latency)
├── Centralized prompt management
├── A/B testing for prompt optimization
└── Multi-agent workflow visualization

Result: 10-20% cost savings, 50% faster debugging, 3x faster prompt iteration
```

---

**End of Langfuse Integration Plan**
