# Technical Implementation Plan: Empire v7.3 Feature Batch

**Branch**: `2-empire-v73-features` | **Date**: 2025-11-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/2-empire-v73-features/spec.md`
**Status**: Technical Planning Phase
**Priority Implementation**: P1 (Sprint 1) → P2 (Sprint 2) → P3 (Sprint 3)

---

## Summary

This technical plan translates 9 user-facing features into concrete implementation steps for Empire v7.3. The features span three priority levels and address core system capabilities: department taxonomy, real-time status updates, multi-modal content ingestion, source attribution, agent orchestration, course management, chat enhancements, and intelligent routing.

**Key Technical Themes**:
1. **Real-time Updates**: WebSocket integration for processing status (Feature 2)
2. **Multi-Modal Ingestion**: URL/link support for YouTube/articles/books (Features 3, 8)
3. **Metadata Extraction**: Source attribution using LangExtract (Feature 4)
4. **Agent Orchestration**: Intelligent routing between CrewAI and Claude Code (Feature 9)
5. **Department Extension**: R&D department addition (Feature 1)
6. **Interactive Features**: Agent chat, course additions, file uploads (Features 5, 6, 7)

---

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- **Backend**: FastAPI 0.104+, Celery 5.3+, Pydantic v2
- **Databases**: Supabase (PostgreSQL 15+, pgvector 0.5+), Neo4j 5.14+, Redis (Upstash)
- **AI/ML**: Anthropic Claude (Sonnet 4.5, Haiku), BGE-M3 (Ollama), LangExtract, LlamaParse
- **Services**: CrewAI (multi-agent), LlamaIndex (document parsing)
- **Frontend**: Gradio 4.x (chat UI)
- **Monitoring**: Prometheus, Grafana, Alertmanager
- **Storage**: Backblaze B2 (S3-compatible)

**Storage**:
- PostgreSQL (Supabase): User data, documents, sessions, department taxonomy
- Neo4j (Mac Studio): Knowledge graphs, entity relationships
- Redis (Upstash): Semantic caching, Celery broker, rate limiting
- Backblaze B2: Document assets, CrewAI outputs

**Testing**:
- pytest 7.4+ (unit, integration, e2e)
- FastAPI TestClient (API endpoints)
- Playwright (frontend flows)
- Locust (load testing)

**Target Platform**:
- **Backend**: Render (web services + Celery workers, Oregon region)
- **Frontend**: Render (Gradio chat UI, Oregon region)
- **Local Services**: Mac Studio M3 Ultra (Neo4j, Ollama embeddings/reranking)

**Performance Goals**:
- **Query Latency**: <500ms P95 for standard queries, <1000ms P99
- **Document Processing**: <5s per document (with caching), <60s for complex PDFs/videos
- **Concurrent Users**: Support 100+ simultaneous chat sessions
- **Cache Hit Rate**: Maintain 60-80% semantic cache hit rate
- **WebSocket Latency**: <100ms for real-time status updates

**Constraints**:
- **Cost Budget**: $350-500/month maximum (cloud services only)
- **Local-First**: Maximize Mac Studio usage (Neo4j, embeddings, reranking)
- **Uptime SLA**: 99.9% availability target
- **Zero-Downtime**: Gradual rollout with feature flags for all features
- **Token Optimization**: Prefer Claude Haiku for expansion, Sonnet for synthesis only

**Scale/Scope**:
- **Document Throughput**: 1000+ documents/day (up from 500 in v7.2)
- **Query Volume**: 5000+ queries/day
- **Department Taxonomy**: 11 departments (10 existing + 1 new R&D)
- **API Endpoints**: ~15 new endpoints across 9 features
- **Database Changes**: ~8 new tables, ~12 schema updates, ~20 new indexes

---

## Constitution Check

*GATE: Must pass before implementation. Constitution: `.specify/constitution.md`*

### ✅ Compliant Decisions

**1. Hybrid Intelligence Architecture**
- ✅ **Feature 1 (R&D Department)**: Uses existing local Neo4j for graph entities
- ✅ **Feature 2 (Loading Status)**: WebSocket updates minimize API polling (cost reduction)
- ✅ **Feature 4 (Source Attribution)**: Uses LangExtract (Gemini-powered) for metadata, stores locally
- ✅ **Feature 9 (Agent Router)**: Routes to local Claude Code for simple tasks, CrewAI for complex workflows

**2. Cost Efficiency & Token Optimization**
- ✅ **Feature 3 (URL Support)**: Caches YouTube transcripts and article content in Redis
- ✅ **Feature 7 (File Uploads)**: Uses Claude Vision API only for images, not every message
- ✅ **Feature 8 (Books)**: Uses LlamaParse free tier (10K pages/month), batch processing via Celery
- ✅ **All Features**: Semantic caching for repeated queries (60-80% hit rate maintained)

**3. Production-Grade Reliability**
- ✅ **Feature 2 (Loading Status)**: Retry logic, graceful degradation if WebSocket fails
- ✅ **All Features**: Prometheus metrics, structured logging with correlation IDs
- ✅ **Feature 9 (Agent Router)**: Fallback mechanisms if routing fails

**4. Technology Stack Mandates**
- ✅ **Language**: Python 3.11+ for all backend code
- ✅ **Framework**: FastAPI with async/await patterns
- ✅ **Task Queue**: Celery with Redis broker (Upstash)
- ✅ **Databases**: Supabase (PostgreSQL + pgvector), Neo4j (Docker), Redis (Upstash)
- ✅ **Storage**: Backblaze B2 for all asset storage
- ✅ **Monitoring**: Prometheus + Grafana + Alertmanager for all new endpoints

**5. API-First Design**
- ✅ **All Features**: OpenAPI/Swagger auto-documentation for new endpoints
- ✅ **Feature 2 (Loading Status)**: WebSocket protocol documented
- ✅ **Feature 7 (File Uploads)**: Multipart/form-data standard compliance

### ⚠️ Minor Deviations (Justified)

**1. New External Dependencies**

| Dependency | Feature | Justification | Cost Impact |
|------------|---------|---------------|-------------|
| YouTube Transcript API | Feature 3 | Free tier (100 requests/day), no alternatives for accurate transcripts | $0 (free tier sufficient) |
| yt-dlp | Feature 3 | Open-source, zero cost, required for YouTube metadata | $0 |
| BeautifulSoup4 + newspaper3k | Feature 3 | Open-source, zero cost, article extraction | $0 |
| PyMuPDF (fitz) | Feature 8 | Open-source, zero cost, better chapter detection than LlamaParse alone | $0 |

**Total Cost Impact**: $0/month (all open-source)

**2. Database Schema Changes**

| Change | Feature | Justification | Risk Level |
|--------|---------|---------------|------------|
| Add `department` enum value 'r_and_d' | Feature 1 | Backward compatible, no data migration needed | LOW |
| Add `processing_status` JSONB column | Feature 2 | Nullable, optional field, no breaking changes | LOW |
| Add `source_metadata` JSONB column | Feature 4 | Nullable, optional field, indexes for fast lookup | LOW |
| Add `content_additions` JSONB array | Feature 6 | Nullable, optional field, audit trail preserved | LOW |

**All schema changes are backward compatible and non-breaking.**

### 🚫 No Constitution Violations

All 9 features comply with Empire v7.2 constitution. No complexity tracking required.

---

## Project Structure

### Documentation (this feature batch)

```text
specs/2-empire-v73-features/
├── spec.md                      # User-facing specification (COMPLETE)
├── technical-plan.md            # This file (IN PROGRESS)
├── checklists/
│   └── requirements.md          # Specification quality checklist (COMPLETE)
├── contracts/                   # API contracts (TO BE CREATED in Phase 1)
│   ├── feature-1-rnd-dept.yaml
│   ├── feature-2-loading-status.yaml
│   ├── feature-3-url-upload.yaml
│   ├── feature-4-source-attribution.yaml
│   ├── feature-5-agent-chat.yaml
│   ├── feature-6-course-addition.yaml
│   ├── feature-7-chat-upload.yaml
│   ├── feature-8-book-processing.yaml
│   └── feature-9-agent-router.yaml
├── data-models/                 # Database schemas (TO BE CREATED in Phase 1)
│   ├── supabase-schemas.sql
│   ├── neo4j-cypher.cypher
│   └── redis-keys.md
├── migrations/                  # Migration scripts (TO BE CREATED in Phase 2)
│   ├── 001_add_rnd_department.sql
│   ├── 002_add_processing_status_column.sql
│   ├── 003_add_source_metadata_column.sql
│   └── ...
└── tasks.md                     # Task breakdown (TO BE CREATED via /speckit.tasks)
```

### Source Code (repository root)

**Structure Decision**: Web application structure (FastAPI backend + Gradio frontend)

```text
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── documents.py          # NEW: Features 1, 3, 7, 8
│   │       │   ├── processing.py         # NEW: Feature 2 (WebSocket)
│   │       │   ├── chat.py              # MODIFIED: Features 4, 5, 7
│   │       │   ├── agents.py            # NEW: Feature 5 (agent chat)
│   │       │   ├── courses.py           # NEW: Feature 6 (course additions)
│   │       │   └── router.py            # NEW: Feature 9 (agent router)
│   │       └── deps.py                  # Shared dependencies
│   ├── core/
│   │   ├── config.py                   # Add new feature flags
│   │   └── constants.py                # Add R&D department constant
│   ├── models/
│   │   ├── database.py                 # MODIFIED: Features 1, 2, 4, 6
│   │   ├── websocket.py                # NEW: Feature 2
│   │   └── agent_router.py             # NEW: Feature 9
│   ├── schemas/
│   │   ├── document.py                 # MODIFIED: Features 1, 3, 7, 8
│   │   ├── processing.py               # NEW: Feature 2
│   │   ├── chat.py                     # MODIFIED: Features 4, 5, 7
│   │   ├── agent.py                    # NEW: Feature 5
│   │   ├── course.py                   # NEW: Feature 6
│   │   └── router.py                   # NEW: Feature 9
│   ├── services/
│   │   ├── youtube_service.py          # NEW: Feature 3
│   │   ├── article_service.py          # NEW: Feature 3
│   │   ├── book_service.py             # NEW: Feature 8
│   │   ├── websocket_manager.py        # NEW: Feature 2
│   │   ├── source_attribution.py       # NEW: Feature 4
│   │   ├── agent_service.py            # NEW: Feature 5
│   │   ├── agent_router_service.py     # NEW: Feature 9
│   │   └── department_service.py       # MODIFIED: Feature 1
│   ├── tasks/
│   │   ├── youtube_tasks.py            # NEW: Feature 3
│   │   ├── article_tasks.py            # NEW: Feature 3
│   │   ├── book_tasks.py               # NEW: Feature 8
│   │   └── processing_tasks.py         # MODIFIED: Feature 2
│   └── utils/
│       ├── url_validator.py            # NEW: Feature 3
│       ├── transcript_extractor.py     # NEW: Feature 3
│       └── chapter_detector.py         # NEW: Feature 8

frontend/
├── app.py                              # MODIFIED: Features 2, 4, 5, 6, 7
├── components/
│   ├── upload_tab.py                   # MODIFIED: Features 3, 7
│   ├── chat_interface.py               # MODIFIED: Features 4, 5, 7
│   ├── agent_selector.py               # NEW: Feature 5
│   ├── course_manager.py               # NEW: Feature 6
│   └── processing_status.py            # NEW: Feature 2
└── utils/
    ├── websocket_client.py             # NEW: Feature 2
    └── file_handler.py                 # NEW: Feature 7

tests/
├── api/
│   ├── test_documents.py               # NEW: Features 1, 3, 7, 8
│   ├── test_processing_websocket.py    # NEW: Feature 2
│   ├── test_chat.py                    # MODIFIED: Features 4, 5, 7
│   ├── test_agents.py                  # NEW: Feature 5
│   ├── test_courses.py                 # NEW: Feature 6
│   └── test_router.py                  # NEW: Feature 9
├── services/
│   ├── test_youtube_service.py         # NEW: Feature 3
│   ├── test_article_service.py         # NEW: Feature 3
│   ├── test_book_service.py            # NEW: Feature 8
│   ├── test_websocket_manager.py       # NEW: Feature 2
│   ├── test_source_attribution.py      # NEW: Feature 4
│   ├── test_agent_service.py           # NEW: Feature 5
│   └── test_agent_router.py            # NEW: Feature 9
└── integration/
    ├── test_youtube_e2e.py             # NEW: Feature 3
    ├── test_book_e2e.py                # NEW: Feature 8
    ├── test_websocket_e2e.py           # NEW: Feature 2
    └── test_agent_routing_e2e.py       # NEW: Feature 9

migrations/
├── 001_add_rnd_department.sql          # Feature 1
├── 002_add_processing_status_column.sql # Feature 2
├── 003_add_source_metadata_column.sql   # Feature 4
├── 004_add_content_additions_column.sql # Feature 6
└── 005_create_agent_feedback_table.sql  # Feature 5

monitoring/
├── alert_rules.yml                     # MODIFIED: Add alerts for new features
└── prometheus.yml                      # MODIFIED: Add new endpoint scraping

docs/
├── api/
│   ├── websocket_protocol.md           # NEW: Feature 2
│   ├── url_upload_api.md               # NEW: Feature 3
│   ├── agent_router_api.md             # NEW: Feature 9
│   └── file_upload_api.md              # NEW: Feature 7
└── guides/
    ├── rnd_department_setup.md         # NEW: Feature 1
    ├── youtube_transcript_guide.md     # NEW: Feature 3
    ├── book_processing_guide.md        # NEW: Feature 8
    └── agent_routing_guide.md          # NEW: Feature 9
```

**File Count Summary**:
- **New Files**: 45+ (services, endpoints, tests, migrations, docs)
- **Modified Files**: 12 (existing endpoints, models, frontend components)
- **Total Changed Files**: ~57

---

## Feature Implementation Plans

### Priority 1 (Sprint 1) - Foundation & UX Critical

#### Feature 1: R&D Department Addition

**Technical Approach**:
- Add `r_and_d` enum value to existing `department` enum type in Supabase
- Update department taxonomy constants in `app/core/constants.py`
- Extend B2 storage folder structure: `documents/{r_and_d}/{doc_id}/`
- Update Neo4j department node patterns

**API Changes**:
- No new endpoints required
- Existing endpoints automatically support new department value

**Database Schema Changes** (`migrations/001_add_rnd_department.sql`):
```sql
-- Add R&D to department enum
ALTER TYPE department_type ADD VALUE IF NOT EXISTS 'r_and_d';

-- Update department_taxonomy table (if exists)
INSERT INTO department_taxonomy (code, name, description)
VALUES ('r_and_d', 'Research & Development', 'Innovation, R&D, technical research');

-- Neo4j: Add department node (via MCP or Cypher migration)
-- CREATE (:Department {code: 'r_and_d', name: 'Research & Development'})
```

**Service Changes**:
- `app/services/department_service.py`: Add R&D classification logic
- `app/services/document_service.py`: Update B2 path generation

**Testing Strategy**:
- Unit: `test_department_service.py` - Verify R&D enum handling
- Integration: `test_document_upload.py` - Upload document with R&D department
- E2E: `test_classification_e2e.py` - Auto-classification to R&D

**Metrics**:
- Counter: `empire_documents_uploaded_total{department="r_and_d"}`
- Gauge: `empire_documents_by_department{department="r_and_d"}`

**Rollout Strategy**: Feature flag `ENABLE_RND_DEPARTMENT=true` (default: true)

---

#### Feature 2: Loading Process Status UI

**Technical Approach**:
- WebSocket endpoint for real-time status updates
- Celery task state tracking with custom states: `PARSING`, `EMBEDDING`, `GRAPH_SYNC`, `INDEXING`
- Redis pub/sub for status broadcasting
- Gradio chat UI with progress bar component

**API Changes**:

**New WebSocket Endpoint**:
```python
# app/api/v1/endpoints/processing.py
@router.websocket("/ws/processing/{task_id}")
async def processing_status_websocket(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time processing status updates.

    Message format:
    {
        "task_id": "abc123",
        "status": "PARSING" | "EMBEDDING" | "GRAPH_SYNC" | "INDEXING" | "COMPLETE",
        "progress": 0.0-1.0,
        "message": "Human-readable status",
        "timestamp": "2025-11-24T10:00:00Z"
    }
    """
    pass
```

**New REST Endpoints**:
```python
# GET /api/v1/processing/{task_id}/status
# Response: Same as WebSocket message
```

**Database Schema Changes** (`migrations/002_add_processing_status_column.sql`):
```sql
-- Add processing_status column to documents_v2 table
ALTER TABLE documents_v2
ADD COLUMN processing_status JSONB DEFAULT '{
    "status": "PENDING",
    "stages": [],
    "current_stage": null,
    "progress": 0.0,
    "started_at": null,
    "completed_at": null
}'::jsonb;

-- Index for fast status lookups
CREATE INDEX idx_documents_processing_status
ON documents_v2 USING GIN (processing_status jsonb_path_ops);

-- Index for filtering by status
CREATE INDEX idx_documents_status_value
ON documents_v2 ((processing_status->>'status'));
```

**Service Changes**:
- `app/services/websocket_manager.py`: Connection pool, broadcasting
- `app/tasks/processing_tasks.py`: Emit status updates at each stage

**Celery Task Updates**:
```python
# app/tasks/processing_tasks.py
@celery_app.task(bind=True)
def process_document(self, doc_id: str):
    # Stage 1: Parsing
    self.update_state(state='PARSING', meta={'progress': 0.2, 'message': 'Parsing document'})
    broadcast_status(doc_id, 'PARSING', 0.2)

    # Stage 2: Embedding
    self.update_state(state='EMBEDDING', meta={'progress': 0.5, 'message': 'Generating embeddings'})
    broadcast_status(doc_id, 'EMBEDDING', 0.5)

    # Stage 3: Graph Sync
    self.update_state(state='GRAPH_SYNC', meta={'progress': 0.8, 'message': 'Syncing to knowledge graph'})
    broadcast_status(doc_id, 'GRAPH_SYNC', 0.8)

    # Stage 4: Indexing
    self.update_state(state='INDEXING', meta={'progress': 0.95, 'message': 'Creating search indexes'})
    broadcast_status(doc_id, 'INDEXING', 0.95)

    # Complete
    self.update_state(state='COMPLETE', meta={'progress': 1.0, 'message': 'Processing complete'})
    broadcast_status(doc_id, 'COMPLETE', 1.0)
```

**Frontend Changes** (`frontend/components/processing_status.py`):
```python
import gradio as gr
import asyncio
import websockets

def create_processing_status_component():
    """
    Returns a Gradio component that displays real-time processing status.

    Components:
    - Progress bar (0-100%)
    - Status text ("Parsing document...")
    - Stage indicator (1/4, 2/4, etc.)
    - Estimated time remaining
    """
    with gr.Column(visible=False, elem_id="processing-status") as status_col:
        progress_bar = gr.Progress(label="Processing Status")
        status_text = gr.Textbox(label="Current Stage", interactive=False)
        stage_indicator = gr.Textbox(label="Stage", interactive=False)

    return status_col, progress_bar, status_text, stage_indicator
```

**Testing Strategy**:
- Unit: `test_websocket_manager.py` - Connection handling, broadcasting
- Integration: `test_processing_websocket.py` - End-to-end WebSocket flow
- E2E: `test_upload_with_status.py` - Upload document, track status via WebSocket
- Load: Simulate 100+ concurrent WebSocket connections

**Metrics**:
- Gauge: `empire_active_websocket_connections{endpoint="processing"}`
- Counter: `empire_processing_status_broadcasts_total{stage="PARSING|EMBEDDING|..."}`
- Histogram: `empire_processing_stage_duration_seconds{stage="..."}`

**Error Handling**:
- WebSocket disconnection: Client reconnects with last known task_id
- Redis pub/sub failure: Fall back to polling REST endpoint
- Task timeout: Send FAILED status with error message

**Rollout Strategy**: Feature flag `ENABLE_WEBSOCKET_STATUS=true` (default: true)

---

#### Feature 4: Source Attribution in Chat UI

**Technical Approach**:
- Use LangExtract (Gemini-powered) to extract metadata: `title`, `author`, `date`, `url`, `page_number`
- Store metadata in `source_metadata` JSONB column
- Return sources with each chat response
- Gradio UI with expandable citations and clickable source links

**API Changes**:

**Modified Chat Endpoint**:
```python
# app/api/v1/endpoints/chat.py
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint with source attribution.

    Response includes:
    {
        "answer": "Insurance in California requires...",
        "sources": [
            {
                "document_id": "doc_123",
                "title": "California Insurance Guide",
                "author": "CA Dept of Insurance",
                "date": "2024-01-01",
                "page_number": 12,
                "url": "https://...",
                "relevance_score": 0.92,
                "excerpt": "Highlighted text from source..."
            }
        ],
        "source_count": 3,
        "has_direct_sources": true
    }
    """
    pass
```

**Database Schema Changes** (`migrations/003_add_source_metadata_column.sql`):
```sql
-- Add source_metadata column to documents_v2 table
ALTER TABLE documents_v2
ADD COLUMN source_metadata JSONB DEFAULT '{
    "title": null,
    "author": null,
    "date": null,
    "url": null,
    "page_numbers": [],
    "extracted_by": "langextract",
    "extraction_confidence": null,
    "extracted_at": null
}'::jsonb;

-- Index for fast metadata lookups
CREATE INDEX idx_documents_source_metadata
ON documents_v2 USING GIN (source_metadata jsonb_path_ops);

-- Index for title search
CREATE INDEX idx_documents_source_title
ON documents_v2 ((source_metadata->>'title'));

-- Index for author search
CREATE INDEX idx_documents_source_author
ON documents_v2 ((source_metadata->>'author'));
```

**Service Changes**:
- `app/services/source_attribution.py`: Extract and format source metadata

**LangExtract Integration**:
```python
# app/services/source_attribution.py
from langextract import LangExtract

langextract_client = LangExtract(api_key=os.getenv("GOOGLE_API_KEY"))

async def extract_source_metadata(document: Document) -> dict:
    """
    Extract source metadata using LangExtract.

    Schema:
    {
        "title": str,
        "author": str,
        "date": str (ISO 8601),
        "url": str,
        "page_numbers": list[int],
        "confidence": float (0.0-1.0)
    }
    """
    metadata = await langextract_client.extract(
        document.content,
        schema={
            "title": "string",
            "author": "string",
            "date": "string",
            "url": "string"
        }
    )
    return metadata
```

**Query Flow with Source Attribution**:
```python
# app/services/query_service.py
async def query_with_sources(query: str) -> ChatResponse:
    # 1. Retrieve relevant documents
    docs = await vector_search(query, top_k=10)

    # 2. Rerank documents
    reranked_docs = await rerank(query, docs)

    # 3. Extract sources from top 3 documents
    sources = [
        {
            "document_id": doc.id,
            **doc.source_metadata,
            "relevance_score": doc.score,
            "excerpt": extract_excerpt(doc.content, query)
        }
        for doc in reranked_docs[:3]
    ]

    # 4. Generate answer with sources injected in prompt
    answer = await claude_generate(
        query,
        context="\n\n".join([doc.content for doc in reranked_docs[:3]]),
        sources=sources
    )

    return ChatResponse(
        answer=answer,
        sources=sources,
        source_count=len(sources),
        has_direct_sources=True
    )
```

**Frontend Changes** (`frontend/components/chat_interface.py`):
```python
def format_sources_component(sources: list[dict]) -> str:
    """
    Format sources as expandable citations.

    Example:
    ---
    **Sources (3):**

    [1] California Insurance Guide (CA Dept of Insurance, 2024)
        Page 12 | Relevance: 92%
        > "Highlighted excerpt from the source..."
        [View Source →](https://...)

    [2] ...
    """
    if not sources:
        return "*No direct sources found. Answer based on general knowledge.*"

    formatted = "**Sources:**\n\n"
    for i, source in enumerate(sources, 1):
        formatted += f"[{i}] **{source['title']}**"
        if source.get('author'):
            formatted += f" ({source['author']}"
            if source.get('date'):
                formatted += f", {source['date']}"
            formatted += ")"
        formatted += "\n"

        if source.get('page_number'):
            formatted += f"    Page {source['page_number']} | "
        formatted += f"Relevance: {int(source['relevance_score']*100)}%\n"

        if source.get('excerpt'):
            formatted += f'    > "{source["excerpt"]}"\n'

        if source.get('url'):
            formatted += f"    [View Source →]({source['url']})\n"

        formatted += "\n"

    return formatted
```

**Testing Strategy**:
- Unit: `test_source_attribution.py` - Metadata extraction, formatting
- Integration: `test_chat_with_sources.py` - Query with sources returned
- E2E: `test_citation_ui.py` - Verify clickable links, expandable citations
- Validation: Manual review of 100 queries to verify source accuracy >95%

**Metrics**:
- Counter: `empire_queries_with_sources_total`
- Histogram: `empire_sources_per_query` (bucket: 0, 1-2, 3-5, >5)
- Counter: `empire_source_extractions_total{success="true|false"}`
- Gauge: `empire_source_extraction_confidence_avg`

**Edge Cases**:
- No sources found: Display message "Answer based on general knowledge"
- Source metadata missing: Display "Source [document_id]" with generic label
- Extraction failure: Log error, continue without metadata

**Rollout Strategy**: Feature flag `ENABLE_SOURCE_ATTRIBUTION=true` (default: true)

---

#### Feature 9: Intelligent Agent Router

**Technical Approach**:
- Decision matrix: Task characteristics → Execution pattern (Skill, Sub-agent, MCP, Slash Command)
- CrewAI vs Claude Code routing: Complexity scoring (0-10)
- Composition rules enforced: Skill → MCP (valid), Skill → Skill (invalid)
- Fallback mechanisms: If routing fails, default to simplest pattern

**API Changes**:

**New Agent Router Endpoint**:
```python
# app/api/v1/endpoints/router.py
@router.post("/route", response_model=AgentRouteResponse)
async def route_task(request: AgentRouteRequest):
    """
    Intelligent routing for agent tasks.

    Request:
    {
        "task_description": "Parse 10 PDFs and extract entities",
        "task_characteristics": {
            "repeatability": "one-off" | "reusable",
            "context_isolation": "shared" | "isolated",
            "parallelization": "sequential" | "concurrent",
            "external_integration": true | false,
            "domain_specialization": "documents" | "code" | "data" | "general",
            "estimated_complexity": 0-10
        }
    }

    Response:
    {
        "primary_pattern": "crewai" | "skill" | "sub-agent" | "slash-command" | "mcp",
        "alternative_pattern": "...",
        "reasoning": "Multi-agent coordination needed (3+ agents), long-running (>30s)",
        "composition": ["skill", "mcp"],  // Valid composition chain
        "estimated_time_seconds": 45,
        "complexity_score": 7.5,
        "fallback_pattern": "skill"
    }
    """
    pass
```

**Decision Matrix** (`app/models/agent_router.py`):
```python
from enum import Enum
from pydantic import BaseModel

class ExecutionPattern(str, Enum):
    SLASH_COMMAND = "slash-command"
    SKILL = "skill"
    SUB_AGENT = "sub-agent"
    MCP = "mcp"
    CREWAI = "crewai"
    CLAUDE_CODE = "claude-code"

class TaskCharacteristics(BaseModel):
    repeatability: str  # "one-off" | "reusable"
    context_isolation: str  # "shared" | "isolated"
    parallelization: str  # "sequential" | "concurrent"
    external_integration: bool
    domain_specialization: str  # "documents" | "code" | "data" | "general"
    estimated_complexity: float  # 0-10

class CompositionRule(BaseModel):
    valid_compositions: list[tuple[ExecutionPattern, ExecutionPattern]]
    invalid_compositions: list[tuple[ExecutionPattern, ExecutionPattern]]

# Valid: Skill → MCP, Skill → Sub-agent, Skill → Slash Command
# Invalid: Sub-agent → Sub-agent, Skill → Skill, Circular dependencies
COMPOSITION_RULES = CompositionRule(
    valid_compositions=[
        (ExecutionPattern.SKILL, ExecutionPattern.MCP),
        (ExecutionPattern.SKILL, ExecutionPattern.SUB_AGENT),
        (ExecutionPattern.SKILL, ExecutionPattern.SLASH_COMMAND),
    ],
    invalid_compositions=[
        (ExecutionPattern.SUB_AGENT, ExecutionPattern.SUB_AGENT),
        (ExecutionPattern.SKILL, ExecutionPattern.SKILL),
    ]
)
```

**Routing Service** (`app/services/agent_router_service.py`):
```python
class AgentRouterService:
    async def route_task(self, task: str, characteristics: TaskCharacteristics) -> AgentRouteResponse:
        """
        Route task to optimal execution pattern.

        Decision factors:
        1. Complexity score (0-10)
        2. Repeatability (one-off vs reusable)
        3. Parallelization needs
        4. External integration requirements
        5. Domain specialization
        """
        complexity_score = await self._calculate_complexity(task, characteristics)

        # CrewAI routing criteria
        if (
            complexity_score >= 7.0  # High complexity
            or characteristics.parallelization == "concurrent"
            or self._requires_multi_agent_coordination(task)
        ):
            return AgentRouteResponse(
                primary_pattern=ExecutionPattern.CREWAI,
                reasoning="High complexity + multi-agent coordination needed",
                complexity_score=complexity_score,
                estimated_time_seconds=await self._estimate_time(complexity_score)
            )

        # Claude Code routing criteria
        if (
            complexity_score < 4.0  # Low-medium complexity
            and characteristics.context_isolation == "shared"
            and not characteristics.external_integration
        ):
            return AgentRouteResponse(
                primary_pattern=ExecutionPattern.CLAUDE_CODE,
                reasoning="Simple task, shared context, no external integration",
                complexity_score=complexity_score,
                estimated_time_seconds=await self._estimate_time(complexity_score)
            )

        # Default to Skill pattern
        return AgentRouteResponse(
            primary_pattern=ExecutionPattern.SKILL,
            reasoning="Default reusable workflow pattern",
            complexity_score=complexity_score,
            estimated_time_seconds=await self._estimate_time(complexity_score)
        )

    async def _calculate_complexity(self, task: str, characteristics: TaskCharacteristics) -> float:
        """
        Calculate complexity score (0-10) using Claude Haiku.

        Factors:
        - Task length and ambiguity
        - Number of steps required
        - External dependencies
        - Error handling complexity
        """
        prompt = f"""
        Rate the complexity of this task on a scale of 0-10.

        Task: {task}
        Characteristics: {characteristics.dict()}

        Factors to consider:
        - Number of steps (1-2 steps = low, 5+ steps = high)
        - Ambiguity level (clear = low, vague = high)
        - External dependencies (none = low, multiple = high)
        - Error handling needs (simple = low, complex = high)

        Return only a single number (0.0-10.0).
        """

        response = await claude_haiku_generate(prompt, max_tokens=10)
        return float(response.strip())
```

**Testing Strategy**:
- Unit: `test_agent_router.py` - Decision matrix, complexity scoring
- Integration: `test_route_to_crewai.py` - Route complex task to CrewAI
- Integration: `test_route_to_claude.py` - Route simple task to Claude Code
- E2E: `test_agent_routing_e2e.py` - End-to-end routing for 100 diverse tasks
- Validation: >90% correct pattern selection on test suite

**Metrics**:
- Counter: `empire_agent_routing_total{pattern="crewai|skill|sub-agent|..."}`
- Histogram: `empire_agent_routing_decision_time_seconds`
- Gauge: `empire_agent_routing_complexity_score{pattern="..."}`
- Counter: `empire_agent_routing_fallback_total{reason="..."}`

**Decision Overhead**:
- Target: <100ms for routing decision
- Use Claude Haiku for complexity scoring (fast, cheap)
- Cache routing decisions for similar tasks (Redis, 1-hour TTL)

**Rollout Strategy**: Feature flag `ENABLE_AGENT_ROUTING=true` (default: true)

---

### Priority 2 (Sprint 2) - Content Expansion

#### Feature 3: URL/Link Support on Upload

**Technical Approach**:
- Detect URL patterns in upload input (YouTube, articles, PDFs)
- YouTube: Extract transcript using `youtube-transcript-api` + `yt-dlp` for metadata
- Articles: Extract content using `newspaper3k` + `BeautifulSoup4`
- PDF URLs: Download and process through existing LlamaParse pipeline
- Cache extracted content in Redis (24-hour TTL)
- Batch processing: Upload multiple URLs at once

**API Changes**:

**New URL Upload Endpoint**:
```python
# app/api/v1/endpoints/documents.py
@router.post("/upload/url", response_model=URLUploadResponse)
async def upload_url(request: URLUploadRequest):
    """
    Upload documents via URLs.

    Request:
    {
        "urls": [
            "https://www.youtube.com/watch?v=abc123",
            "https://example.com/article.html",
            "https://example.com/document.pdf"
        ],
        "department": "it_engineering",
        "auto_classify": true,
        "batch_mode": true
    }

    Response:
    {
        "task_ids": ["task_1", "task_2", "task_3"],
        "processing_count": 3,
        "estimated_time_seconds": 120,
        "websocket_url": "ws://api/ws/processing/batch_abc123"
    }
    """
    pass
```

**Service Changes**:
- `app/services/youtube_service.py`: YouTube transcript extraction
- `app/services/article_service.py`: Article content extraction
- `app/utils/url_validator.py`: URL validation and type detection

**YouTube Transcript Extraction** (`app/services/youtube_service.py`):
```python
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

async def extract_youtube_transcript(url: str) -> dict:
    """
    Extract YouTube video transcript and metadata.

    Returns:
    {
        "video_id": "abc123",
        "title": "Video Title",
        "author": "Channel Name",
        "duration_seconds": 600,
        "upload_date": "2024-01-01",
        "transcript": "Full transcript text...",
        "language": "en",
        "view_count": 1000000
    }
    """
    # Extract video ID
    video_id = extract_video_id(url)

    # Get metadata via yt-dlp (no download)
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        metadata = ydl.extract_info(url, download=False)

    # Get transcript
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    transcript = transcript_list.find_transcript(['en']).fetch()
    full_transcript = " ".join([item['text'] for item in transcript])

    return {
        "video_id": video_id,
        "title": metadata['title'],
        "author": metadata['uploader'],
        "duration_seconds": metadata['duration'],
        "upload_date": metadata['upload_date'],
        "transcript": full_transcript,
        "language": "en",
        "view_count": metadata.get('view_count')
    }
```

**Article Extraction** (`app/services/article_service.py`):
```python
from newspaper import Article
from bs4 import BeautifulSoup
import requests

async def extract_article_content(url: str) -> dict:
    """
    Extract article content and metadata.

    Returns:
    {
        "url": "https://...",
        "title": "Article Title",
        "authors": ["Author 1", "Author 2"],
        "publish_date": "2024-01-01",
        "text": "Full article text...",
        "summary": "Auto-generated summary",
        "top_image": "https://...",
        "keywords": ["keyword1", "keyword2"]
    }
    """
    article = Article(url)
    article.download()
    article.parse()
    article.nlp()  # Auto-generate summary

    return {
        "url": url,
        "title": article.title,
        "authors": article.authors,
        "publish_date": article.publish_date.isoformat() if article.publish_date else None,
        "text": article.text,
        "summary": article.summary,
        "top_image": article.top_image,
        "keywords": article.keywords
    }
```

**URL Validation** (`app/utils/url_validator.py`):
```python
import re
from urllib.parse import urlparse

class URLType(str, Enum):
    YOUTUBE = "youtube"
    ARTICLE = "article"
    PDF = "pdf"
    UNSUPPORTED = "unsupported"

def detect_url_type(url: str) -> URLType:
    """
    Detect URL type for appropriate processing.
    """
    parsed = urlparse(url)

    # YouTube detection
    if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
        return URLType.YOUTUBE

    # PDF detection (by extension)
    if url.lower().endswith('.pdf'):
        return URLType.PDF

    # Article detection (HTML pages)
    if parsed.scheme in ['http', 'https']:
        return URLType.ARTICLE

    return URLType.UNSUPPORTED
```

**Celery Tasks** (`app/tasks/youtube_tasks.py`, `app/tasks/article_tasks.py`):
```python
# app/tasks/youtube_tasks.py
@celery_app.task(bind=True)
def process_youtube_url(self, url: str, department: str):
    """
    Celery task: Process YouTube URL.

    Steps:
    1. Extract transcript and metadata
    2. Generate embeddings (BGE-M3)
    3. Store in Supabase
    4. Sync to Neo4j
    5. Create search indexes
    """
    self.update_state(state='EXTRACTING', meta={'progress': 0.2})
    data = extract_youtube_transcript(url)

    self.update_state(state='EMBEDDING', meta={'progress': 0.5})
    embeddings = generate_embeddings(data['transcript'])

    self.update_state(state='STORING', meta={'progress': 0.8})
    doc_id = store_document(data, embeddings, department)

    self.update_state(state='INDEXING', meta={'progress': 0.95})
    create_search_indexes(doc_id)

    return {"document_id": doc_id, "status": "complete"}
```

**Frontend Changes** (`frontend/components/upload_tab.py`):
```python
def create_url_upload_component():
    """
    Gradio component for URL uploads.

    Features:
    - Text area for multiple URLs (one per line)
    - Auto-detect URL type (YouTube, Article, PDF)
    - Batch processing indicator
    - Progress tracking via WebSocket
    """
    with gr.Tab("URL Upload"):
        url_input = gr.Textbox(
            label="Enter URLs (one per line)",
            placeholder="https://www.youtube.com/watch?v=...\nhttps://example.com/article.html",
            lines=5
        )
        url_type_display = gr.Textbox(label="Detected Types", interactive=False)
        upload_btn = gr.Button("Process URLs")

    return url_input, url_type_display, upload_btn
```

**Caching Strategy** (Redis):
```python
# Cache YouTube transcripts for 24 hours
cache_key = f"youtube:transcript:{video_id}"
cached_transcript = await redis_client.get(cache_key)
if cached_transcript:
    return json.loads(cached_transcript)

# Extract transcript
transcript_data = await extract_youtube_transcript(url)

# Cache result
await redis_client.setex(cache_key, 86400, json.dumps(transcript_data))
```

**Testing Strategy**:
- Unit: `test_youtube_service.py` - Transcript extraction, metadata parsing
- Unit: `test_article_service.py` - Article extraction, BeautifulSoup parsing
- Integration: `test_youtube_e2e.py` - Upload YouTube URL, verify document in Supabase
- Integration: `test_article_e2e.py` - Upload article URL, verify embeddings
- Validation: Test 50 real YouTube videos, 50 real articles (>95% success rate)

**Metrics**:
- Counter: `empire_url_uploads_total{type="youtube|article|pdf"}`
- Histogram: `empire_url_processing_duration_seconds{type="..."}`
- Counter: `empire_url_extraction_errors_total{type="...", reason="..."}`
- Gauge: `empire_url_cache_hit_rate`

**Error Handling**:
- YouTube transcript unavailable: Attempt audio transcription via Soniox
- Article extraction failure: Fall back to raw HTML parsing
- PDF download timeout: Retry with exponential backoff (max 3 attempts)

**Rollout Strategy**: Feature flag `ENABLE_URL_UPLOAD=true` (default: true)

---

#### Feature 7: Chat File/Image Upload

**Technical Approach**:
- Multipart file upload in chat interface
- Support file types: PDF, DOCX, TXT, images (PNG, JPG, WEBP)
- Images: Use Claude Vision API for analysis
- Documents: Process through LlamaParse → embed → query augmentation
- Inline context: Attach file content to current chat message

**API Changes**:

**Modified Chat Endpoint with File Upload**:
```python
# app/api/v1/endpoints/chat.py
@router.post("/chat/upload", response_model=ChatResponse)
async def chat_with_file(
    message: str = Form(...),
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    """
    Chat endpoint with inline file/image upload.

    Supported file types:
    - Images: PNG, JPG, JPEG, WEBP (analyzed via Claude Vision API)
    - Documents: PDF, DOCX, TXT (processed via LlamaParse)
    - Max file size: 10 MB

    Response includes file analysis in context.
    """
    pass
```

**Service Changes**:
- `app/services/vision_service.py`: Claude Vision API integration
- `app/utils/file_handler.py`: File validation, MIME type detection

**Claude Vision Integration** (`app/services/vision_service.py`):
```python
from anthropic import Anthropic
import base64

async def analyze_image_with_claude(image_bytes: bytes, query: str) -> dict:
    """
    Analyze image using Claude Vision API.

    Returns:
    {
        "description": "Image shows a diagram of...",
        "detected_text": "Extracted text from image",
        "objects": ["diagram", "chart", "labels"],
        "analysis": "Contextual analysis based on query"
    }
    """
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Encode image to base64
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')

    response = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_b64
                    }
                },
                {
                    "type": "text",
                    "text": f"Analyze this image in the context of: {query}"
                }
            ]
        }]
    )

    return {
        "description": response.content[0].text,
        "model": "claude-3-5-sonnet-20241022"
    }
```

**File Handler** (`app/utils/file_handler.py`):
```python
from fastapi import UploadFile, HTTPException

ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain"
}

MAX_FILE_SIZE_MB = 10

async def validate_upload_file(file: UploadFile) -> dict:
    """
    Validate uploaded file.

    Returns:
    {
        "file_type": "image" | "document",
        "mime_type": "image/png",
        "size_bytes": 1024000,
        "filename": "example.png"
    }
    """
    # Check MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    # Check file size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {MAX_FILE_SIZE_MB} MB)")

    # Detect file type
    file_type = "image" if file.content_type.startswith("image/") else "document"

    return {
        "file_type": file_type,
        "mime_type": file.content_type,
        "size_bytes": len(file_bytes),
        "filename": file.filename,
        "content": file_bytes
    }
```

**Chat Flow with File Upload**:
```python
# app/services/chat_service.py
async def chat_with_file(message: str, file_data: dict, session_id: str) -> ChatResponse:
    """
    Process chat message with uploaded file.
    """
    # Handle image files
    if file_data['file_type'] == 'image':
        image_analysis = await analyze_image_with_claude(file_data['content'], message)
        context = f"[Image Analysis]: {image_analysis['description']}\n\nUser Question: {message}"

    # Handle document files
    else:
        # Parse document via LlamaParse
        parsed_doc = await llamaparse_service.parse(file_data['content'])

        # Generate embeddings
        embeddings = await generate_embeddings(parsed_doc['text'])

        # Store temporarily (session-scoped)
        temp_doc_id = await store_temp_document(parsed_doc, embeddings, session_id)

        context = f"[Document Content]: {parsed_doc['text'][:2000]}...\n\nUser Question: {message}"

    # Generate response with file context
    response = await query_with_context(context, session_id)

    return response
```

**Frontend Changes** (`frontend/components/chat_interface.py`):
```python
def create_chat_with_upload():
    """
    Gradio chat interface with file upload.

    Features:
    - Drag-and-drop file upload
    - File preview (images shown inline)
    - File type indicator
    - Upload progress bar
    """
    with gr.Column():
        chatbot = gr.Chatbot(label="Chat")

        with gr.Row():
            message_input = gr.Textbox(
                label="Message",
                placeholder="Ask a question or upload a file..."
            )
            file_upload = gr.File(
                label="Upload File",
                file_types=[".png", ".jpg", ".jpeg", ".webp", ".pdf", ".docx", ".txt"]
            )

        send_btn = gr.Button("Send")

    return chatbot, message_input, file_upload, send_btn
```

**Testing Strategy**:
- Unit: `test_vision_service.py` - Claude Vision API integration
- Unit: `test_file_handler.py` - File validation, MIME type detection
- Integration: `test_chat_with_image.py` - Upload image, verify analysis in response
- Integration: `test_chat_with_pdf.py` - Upload PDF, verify document parsing
- E2E: `test_file_upload_ui.py` - Drag-and-drop, file preview, chat flow
- Validation: Test 50 images + 50 documents (>95% successful processing)

**Metrics**:
- Counter: `empire_chat_file_uploads_total{type="image|document"}`
- Histogram: `empire_file_processing_duration_seconds{type="..."}`
- Counter: `empire_vision_api_calls_total{success="true|false"}`
- Histogram: `empire_file_upload_size_bytes{type="..."}`

**Cost Optimization**:
- Use Claude Vision API only for images (not every message)
- Cache image analysis results (Redis, 1-hour TTL)
- Compress images before sending to API (max 1 MB)

**Error Handling**:
- Vision API failure: Return generic message "Unable to analyze image"
- Document parsing failure: Fall back to raw text extraction
- File too large: Return 413 error with clear message

**Rollout Strategy**: Feature flag `ENABLE_CHAT_FILE_UPLOAD=true` (default: true)

---

#### Feature 8: Book Processing

**Technical Approach**:
- Detect book-length PDFs (>100 pages)
- Chapter detection using PyMuPDF (fitz) + regex patterns
- Long-form content handling: Split by chapters, not arbitrary chunks
- OCR fallback using LlamaParse for scanned pages
- Batch processing: Process chapters in parallel via Celery

**API Changes**:

**Modified Document Upload Endpoint**:
```python
# app/api/v1/endpoints/documents.py
@router.post("/upload/book", response_model=BookUploadResponse)
async def upload_book(file: UploadFile = File(...)):
    """
    Upload book-length PDF for chapter-based processing.

    Response:
    {
        "book_id": "book_abc123",
        "title": "Book Title",
        "detected_chapters": 12,
        "total_pages": 300,
        "chapter_titles": ["Chapter 1: Introduction", ...],
        "processing_task_id": "task_xyz",
        "estimated_time_seconds": 600
    }
    """
    pass
```

**Service Changes**:
- `app/services/book_service.py`: Chapter detection, book-specific processing
- `app/utils/chapter_detector.py`: Regex patterns for chapter detection

**Chapter Detection** (`app/utils/chapter_detector.py`):
```python
import fitz  # PyMuPDF
import re

CHAPTER_PATTERNS = [
    r'^Chapter\s+\d+',
    r'^CHAPTER\s+\d+',
    r'^\d+\.\s+[A-Z]',  # "1. INTRODUCTION"
    r'^Part\s+[IVXLCDM]+',  # Roman numerals
]

async def detect_chapters(pdf_bytes: bytes) -> list[dict]:
    """
    Detect chapters in PDF book.

    Returns:
    [
        {
            "chapter_number": 1,
            "title": "Chapter 1: Introduction",
            "start_page": 1,
            "end_page": 15,
            "page_count": 14
        },
        ...
    ]
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    chapters = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()

        # Check for chapter headers
        for pattern in CHAPTER_PATTERNS:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                chapter_title = extract_chapter_title(text, match)
                chapters.append({
                    "chapter_number": len(chapters) + 1,
                    "title": chapter_title,
                    "start_page": page_num + 1,
                    "end_page": None  # Will be set when next chapter found
                })
                break

    # Set end_page for each chapter
    for i in range(len(chapters) - 1):
        chapters[i]['end_page'] = chapters[i+1]['start_page'] - 1

    if chapters:
        chapters[-1]['end_page'] = len(doc)

    # Calculate page counts
    for chapter in chapters:
        chapter['page_count'] = chapter['end_page'] - chapter['start_page'] + 1

    return chapters
```

**Book Processing Service** (`app/services/book_service.py`):
```python
async def process_book(pdf_bytes: bytes, book_metadata: dict) -> dict:
    """
    Process book-length PDF with chapter-based chunking.

    Steps:
    1. Detect chapters
    2. Extract text for each chapter (parallel via Celery)
    3. Generate embeddings per chapter
    4. Store in Supabase with chapter metadata
    5. Sync to Neo4j (book → chapter → entities relationships)
    """
    # Detect chapters
    chapters = await detect_chapters(pdf_bytes)

    if not chapters:
        # Fallback: No chapters detected, treat as regular document
        return await process_regular_document(pdf_bytes, book_metadata)

    # Create book record
    book_id = str(uuid.uuid4())
    await create_book_record(book_id, book_metadata, len(chapters))

    # Process chapters in parallel
    chapter_tasks = []
    for chapter in chapters:
        task = process_chapter.delay(
            book_id=book_id,
            chapter_data=chapter,
            pdf_bytes=pdf_bytes
        )
        chapter_tasks.append(task)

    return {
        "book_id": book_id,
        "chapter_count": len(chapters),
        "chapter_tasks": [task.id for task in chapter_tasks]
    }
```

**Celery Chapter Processing** (`app/tasks/book_tasks.py`):
```python
@celery_app.task(bind=True)
def process_chapter(self, book_id: str, chapter_data: dict, pdf_bytes: bytes):
    """
    Process individual chapter.

    Steps:
    1. Extract chapter text (via PyMuPDF or LlamaParse if OCR needed)
    2. Generate embeddings (BGE-M3)
    3. Store chapter document in Supabase
    4. Link to parent book in Neo4j
    """
    self.update_state(state='EXTRACTING', meta={'progress': 0.2})

    # Extract chapter text
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    chapter_text = ""
    for page_num in range(chapter_data['start_page'] - 1, chapter_data['end_page']):
        page = doc[page_num]
        chapter_text += page.get_text()

    # Check if OCR needed (low text extraction rate)
    if len(chapter_text) < 100:
        # Use LlamaParse for OCR
        chapter_text = await llamaparse_ocr(pdf_bytes, chapter_data)

    self.update_state(state='EMBEDDING', meta={'progress': 0.5})
    embeddings = generate_embeddings(chapter_text)

    self.update_state(state='STORING', meta={'progress': 0.8})
    chapter_doc_id = store_chapter_document(book_id, chapter_data, chapter_text, embeddings)

    self.update_state(state='GRAPH_SYNC', meta={'progress': 0.95})
    sync_chapter_to_neo4j(book_id, chapter_doc_id, chapter_data)

    return {"chapter_id": chapter_doc_id, "status": "complete"}
```

**Database Schema Changes** (`migrations/006_add_book_metadata.sql`):
```sql
-- Add book_metadata JSONB column to documents_v2
ALTER TABLE documents_v2
ADD COLUMN book_metadata JSONB DEFAULT NULL;

-- Index for book queries
CREATE INDEX idx_documents_book_metadata
ON documents_v2 USING GIN (book_metadata jsonb_path_ops);

-- Index for chapter number queries
CREATE INDEX idx_documents_book_chapter
ON documents_v2 ((book_metadata->>'chapter_number'));

-- Example book_metadata structure:
-- {
--   "is_book": true,
--   "book_id": "book_abc123",
--   "book_title": "Book Title",
--   "chapter_number": 1,
--   "chapter_title": "Chapter 1: Introduction",
--   "total_chapters": 12,
--   "start_page": 1,
--   "end_page": 15
-- }
```

**Frontend Changes** (`frontend/components/upload_tab.py`):
```python
def create_book_upload_component():
    """
    Gradio component for book upload.

    Features:
    - Auto-detect book-length PDFs (>100 pages)
    - Display detected chapters
    - Chapter-by-chapter progress tracking
    """
    with gr.Tab("Book Upload"):
        book_upload = gr.File(label="Upload Book PDF", file_types=[".pdf"])
        chapter_display = gr.DataFrame(
            label="Detected Chapters",
            headers=["Chapter #", "Title", "Pages"],
            interactive=False
        )
        process_btn = gr.Button("Process Book")

    return book_upload, chapter_display, process_btn
```

**Testing Strategy**:
- Unit: `test_chapter_detector.py` - Chapter detection patterns
- Integration: `test_book_processing.py` - Upload 300-page book, verify chapters
- E2E: `test_book_query.py` - Query book content, verify chapter sources
- Validation: Test 10 real books (textbooks, novels, technical books) - >90% chapter detection accuracy

**Metrics**:
- Counter: `empire_books_processed_total`
- Histogram: `empire_book_processing_duration_seconds`
- Gauge: `empire_book_chapters_detected_avg`
- Counter: `empire_chapter_processing_errors_total{reason="ocr|extraction|..."}`

**Cost Optimization**:
- Use PyMuPDF (free) for text extraction
- Use LlamaParse OCR only when needed (low text extraction rate)
- Batch chapter embeddings (BGE-M3 local, $0)

**Error Handling**:
- No chapters detected: Process as regular document (fallback)
- OCR failure: Store with partial text, flag for manual review
- Chapter processing timeout: Retry failed chapters individually

**Rollout Strategy**: Feature flag `ENABLE_BOOK_PROCESSING=true` (default: true)

---

### Priority 3 (Sprint 3) - Advanced Features

#### Feature 5: Agent Chat & Improvement

**Technical Approach**:
- Agent selector in chat UI: User chooses which agent to interact with
- Agent types: Document Parser, Entity Extractor, Query Optimizer, Synthesizer
- Feedback collection: Thumbs up/down + text feedback
- Context preservation: Agent-specific chat sessions
- Agent improvement: Feedback stored for future fine-tuning

**API Changes**:

**New Agent Chat Endpoint**:
```python
# app/api/v1/endpoints/agents.py
@router.post("/agents/chat", response_model=AgentChatResponse)
async def agent_chat(request: AgentChatRequest):
    """
    Chat with specific agent.

    Request:
    {
        "agent_id": "document_parser" | "entity_extractor" | "query_optimizer" | "synthesizer",
        "message": "Can you parse this document?",
        "session_id": "session_abc123",
        "context": {...}  // Agent-specific context
    }

    Response:
    {
        "agent_id": "document_parser",
        "response": "I've parsed the document...",
        "actions_taken": ["parsed_pdf", "extracted_text"],
        "confidence": 0.95,
        "feedback_id": "feedback_xyz"  // For subsequent feedback submission
    }
    """
    pass
```

**New Agent Feedback Endpoint**:
```python
@router.post("/agents/feedback", response_model=FeedbackResponse)
async def submit_agent_feedback(request: AgentFeedbackRequest):
    """
    Submit feedback on agent response.

    Request:
    {
        "feedback_id": "feedback_xyz",
        "rating": "positive" | "negative",
        "comment": "The parsing was accurate but missed some tables",
        "suggested_improvement": "Improve table extraction"
    }
    """
    pass
```

**Database Schema Changes** (`migrations/005_create_agent_feedback_table.sql`):
```sql
-- Agent feedback table
CREATE TABLE agent_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feedback_id TEXT UNIQUE NOT NULL,
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    user_message TEXT NOT NULL,
    agent_response TEXT NOT NULL,
    rating TEXT CHECK (rating IN ('positive', 'negative')),
    comment TEXT,
    suggested_improvement TEXT,
    actions_taken JSONB DEFAULT '[]'::jsonb,
    confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    user_id UUID REFERENCES auth.users(id)
);

-- Indexes
CREATE INDEX idx_agent_feedback_agent_id ON agent_feedback(agent_id);
CREATE INDEX idx_agent_feedback_session_id ON agent_feedback(session_id);
CREATE INDEX idx_agent_feedback_rating ON agent_feedback(rating);
CREATE INDEX idx_agent_feedback_created_at ON agent_feedback(created_at);
```

**Agent Service** (`app/services/agent_service.py`):
```python
class AgentType(str, Enum):
    DOCUMENT_PARSER = "document_parser"
    ENTITY_EXTRACTOR = "entity_extractor"
    QUERY_OPTIMIZER = "query_optimizer"
    SYNTHESIZER = "synthesizer"

class AgentService:
    async def chat_with_agent(
        self,
        agent_id: AgentType,
        message: str,
        session_id: str,
        context: dict
    ) -> AgentChatResponse:
        """
        Route message to specific agent.
        """
        if agent_id == AgentType.DOCUMENT_PARSER:
            return await self._document_parser_agent(message, context)
        elif agent_id == AgentType.ENTITY_EXTRACTOR:
            return await self._entity_extractor_agent(message, context)
        elif agent_id == AgentType.QUERY_OPTIMIZER:
            return await self._query_optimizer_agent(message, context)
        elif agent_id == AgentType.SYNTHESIZER:
            return await self._synthesizer_agent(message, context)

    async def _document_parser_agent(self, message: str, context: dict) -> AgentChatResponse:
        """
        Document parser agent.

        Capabilities:
        - Parse documents (PDF, DOCX, images)
        - Extract structured data
        - OCR if needed
        """
        # Delegate to LlamaIndex service
        result = await llamaindex_service.parse(context['document'])

        return AgentChatResponse(
            agent_id=AgentType.DOCUMENT_PARSER,
            response=f"I've parsed the document. Found {len(result['pages'])} pages.",
            actions_taken=["parsed_pdf", "extracted_text"],
            confidence=0.95
        )
```

**Frontend Changes** (`frontend/components/agent_selector.py`):
```python
def create_agent_selector():
    """
    Gradio component for agent selection and chat.

    Features:
    - Dropdown to select agent
    - Agent description and capabilities
    - Agent-specific chat interface
    - Feedback buttons (thumbs up/down)
    - Feedback text area
    """
    with gr.Column():
        agent_dropdown = gr.Dropdown(
            choices=[
                ("Document Parser", "document_parser"),
                ("Entity Extractor", "entity_extractor"),
                ("Query Optimizer", "query_optimizer"),
                ("Synthesizer", "synthesizer")
            ],
            label="Select Agent",
            value="document_parser"
        )

        agent_description = gr.Textbox(
            label="Agent Capabilities",
            interactive=False,
            value="Document Parser: Parse PDFs, DOCX, images..."
        )

        agent_chat = gr.Chatbot(label="Agent Chat")

        with gr.Row():
            thumbs_up_btn = gr.Button("👍")
            thumbs_down_btn = gr.Button("👎")

        feedback_text = gr.Textbox(
            label="Feedback (optional)",
            placeholder="What could be improved?"
        )

    return agent_dropdown, agent_description, agent_chat, thumbs_up_btn, thumbs_down_btn, feedback_text
```

**Testing Strategy**:
- Unit: `test_agent_service.py` - Agent routing, response formatting
- Integration: `test_agent_chat.py` - Chat with each agent type
- E2E: `test_agent_feedback.py` - Submit feedback, verify storage
- Validation: Collect 100+ feedback samples, analyze for improvement opportunities

**Metrics**:
- Counter: `empire_agent_chats_total{agent_id="..."}`
- Counter: `empire_agent_feedback_total{agent_id="...", rating="positive|negative"}`
- Histogram: `empire_agent_response_time_seconds{agent_id="..."}`
- Gauge: `empire_agent_feedback_score_avg{agent_id="..."}`

**Rollout Strategy**: Feature flag `ENABLE_AGENT_CHAT=true` (default: false, manual enable)

---

#### Feature 6: Course Content Addition

**Technical Approach**:
- Detect existing course documents (by title pattern or manual selection)
- Confirmation mechanism: Checkbox "I confirm this adds to course X"
- Audit logging: Record who added what to which course
- Accidental modification prevention: Require explicit confirmation + display course summary

**API Changes**:

**New Course Addition Endpoint**:
```python
# app/api/v1/endpoints/courses.py
@router.post("/courses/{course_id}/add-content", response_model=CourseAdditionResponse)
async def add_content_to_course(
    course_id: str,
    request: CourseAdditionRequest
):
    """
    Add new content to existing course.

    Request:
    {
        "document_id": "doc_abc123",
        "confirmation_checked": true,  // REQUIRED
        "addition_notes": "Adding updated syllabus for 2025"
    }

    Response:
    {
        "course_id": "course_xyz",
        "course_title": "Introduction to AI",
        "new_content_count": 1,
        "total_content_count": 15,
        "audit_log_id": "audit_abc123"
    }
    """
    if not request.confirmation_checked:
        raise HTTPException(400, "Confirmation required to add content to course")

    pass
```

**Database Schema Changes** (`migrations/004_add_content_additions_column.sql`):
```sql
-- Add content_additions JSONB array to courses table (if exists)
-- Or create new courses table if needed

CREATE TABLE IF NOT EXISTS courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    department TEXT REFERENCES department_taxonomy(code),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

-- Add content_additions column
ALTER TABLE courses
ADD COLUMN IF NOT EXISTS content_additions JSONB DEFAULT '[]'::jsonb;

-- Index for fast content lookup
CREATE INDEX idx_courses_content_additions
ON courses USING GIN (content_additions jsonb_path_ops);

-- Course-document relationship table
CREATE TABLE IF NOT EXISTS course_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id TEXT REFERENCES courses(course_id),
    document_id TEXT REFERENCES documents_v2(id),
    added_at TIMESTAMPTZ DEFAULT NOW(),
    added_by UUID REFERENCES auth.users(id),
    addition_notes TEXT,
    is_original_content BOOLEAN DEFAULT FALSE,  -- TRUE if part of original course, FALSE if added later
    UNIQUE(course_id, document_id)
);

-- Indexes
CREATE INDEX idx_course_documents_course_id ON course_documents(course_id);
CREATE INDEX idx_course_documents_document_id ON course_documents(document_id);
CREATE INDEX idx_course_documents_added_at ON course_documents(added_at);
```

**Service Changes**:
- `app/services/course_service.py`: Course detection, content addition logic

**Course Service** (`app/services/course_service.py`):
```python
async def add_content_to_course(
    course_id: str,
    document_id: str,
    user_id: str,
    addition_notes: str
) -> dict:
    """
    Add content to existing course with audit trail.

    Steps:
    1. Verify course exists
    2. Verify document exists
    3. Check if document already in course (prevent duplicates)
    4. Add to course_documents table
    5. Update content_additions JSONB array
    6. Create audit log entry
    """
    # Verify course exists
    course = await get_course(course_id)
    if not course:
        raise ValueError(f"Course {course_id} not found")

    # Verify document exists
    document = await get_document(document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")

    # Check for duplicates
    existing = await check_course_document_exists(course_id, document_id)
    if existing:
        raise ValueError(f"Document {document_id} already in course {course_id}")

    # Add to course_documents table
    await insert_course_document(
        course_id=course_id,
        document_id=document_id,
        added_by=user_id,
        addition_notes=addition_notes,
        is_original_content=False
    )

    # Update content_additions array
    await update_content_additions(course_id, {
        "document_id": document_id,
        "added_at": datetime.now().isoformat(),
        "added_by": user_id,
        "notes": addition_notes
    })

    # Create audit log
    audit_log_id = await create_audit_log(
        event_type="course_content_addition",
        course_id=course_id,
        document_id=document_id,
        user_id=user_id,
        notes=addition_notes
    )

    return {
        "course_id": course_id,
        "document_id": document_id,
        "audit_log_id": audit_log_id
    }
```

**Frontend Changes** (`frontend/components/course_manager.py`):
```python
def create_course_addition_component():
    """
    Gradio component for adding content to courses.

    Features:
    - Course selector dropdown
    - Course summary display (title, description, existing content count)
    - Document selector dropdown
    - Confirmation checkbox (REQUIRED)
    - Addition notes text area
    - Warning message about accidental modifications
    """
    with gr.Column():
        gr.Markdown("### Add Content to Existing Course")
        gr.Markdown("⚠️ **Warning**: Only add content if you're sure it belongs to this course.")

        course_dropdown = gr.Dropdown(
            label="Select Course",
            choices=[]  # Populated dynamically
        )

        course_summary = gr.Textbox(
            label="Course Summary",
            interactive=False,
            lines=3
        )

        document_dropdown = gr.Dropdown(
            label="Select Document to Add",
            choices=[]  # Populated dynamically
        )

        confirmation_checkbox = gr.Checkbox(
            label="I confirm this content belongs to the selected course",
            value=False
        )

        addition_notes = gr.Textbox(
            label="Addition Notes (optional)",
            placeholder="E.g., 'Adding updated syllabus for 2025'"
        )

        add_btn = gr.Button("Add to Course", variant="primary")

    return course_dropdown, course_summary, document_dropdown, confirmation_checkbox, addition_notes, add_btn
```

**Testing Strategy**:
- Unit: `test_course_service.py` - Course detection, content addition
- Integration: `test_course_addition.py` - Add document to course, verify audit log
- E2E: `test_course_ui.py` - UI flow for course addition
- Validation: Test 20 course additions, verify audit trails

**Metrics**:
- Counter: `empire_course_additions_total{course_id="..."}`
- Gauge: `empire_course_content_count{course_id="..."}`
- Counter: `empire_course_addition_errors_total{reason="..."}`

**Audit Logging**:
```sql
-- Example audit log entry
INSERT INTO audit_logs (event_type, event_data, user_id)
VALUES (
    'course_content_addition',
    '{
        "course_id": "course_xyz",
        "course_title": "Introduction to AI",
        "document_id": "doc_abc123",
        "document_title": "Updated Syllabus 2025",
        "addition_notes": "Adding updated syllabus",
        "timestamp": "2025-11-24T10:00:00Z"
    }'::jsonb,
    'user_123'
);
```

**Rollout Strategy**: Feature flag `ENABLE_COURSE_ADDITION=true` (default: false, manual enable)

---

## Implementation Phases

### Phase 0: Foundation (Sprint 0 - Pre-Implementation)
**Duration**: 3-5 days
**Goal**: Set up infrastructure, create migrations, write API contracts

**Tasks**:
1. Create API contracts (OpenAPI specs) for all 9 features
2. Write database migration scripts (7 migrations)
3. Set up feature flags in `app/core/config.py`
4. Update Prometheus alert rules for new endpoints
5. Create monitoring dashboards in Grafana
6. Write integration tests structure (empty test files)

**Deliverables**:
- `specs/2-empire-v73-features/contracts/*.yaml` (9 files)
- `migrations/00*_*.sql` (7 migration files)
- Feature flags configuration
- Grafana dashboard JSON exports
- Test structure (empty test files)

---

### Phase 1: Priority 1 (Sprint 1 - Foundation & UX Critical)
**Duration**: 2 weeks
**Features**: 1 (R&D Department), 2 (Loading Status), 4 (Source Attribution), 9 (Agent Router)

**Week 1: Features 1 & 2**
- Day 1-2: Feature 1 (R&D Department)
  - Run migration `001_add_rnd_department.sql`
  - Update constants and department service
  - Test classification with R&D documents
- Day 3-5: Feature 2 (Loading Status)
  - Implement WebSocket endpoint
  - Add processing status column
  - Update Celery tasks with status broadcasts
  - Create Gradio progress component

**Week 2: Features 4 & 9**
- Day 1-3: Feature 4 (Source Attribution)
  - Integrate LangExtract for metadata extraction
  - Run migration `003_add_source_metadata_column.sql`
  - Update chat endpoint with sources
  - Create Gradio citation component
- Day 4-5: Feature 9 (Agent Router)
  - Implement routing service with decision matrix
  - Add complexity scoring logic
  - Create router endpoint
  - Test routing with 100 diverse tasks

**Testing & Deployment**:
- Integration tests for all P1 features
- E2E tests for WebSocket + source attribution
- Deploy to Render staging environment
- Monitor for 2 days, fix critical bugs
- Deploy to production with feature flags ON

---

### Phase 2: Priority 2 (Sprint 2 - Content Expansion)
**Duration**: 2 weeks
**Features**: 3 (URL Upload), 7 (Chat File Upload), 8 (Book Processing)

**Week 1: Feature 3 (URL Upload)**
- Day 1-2: YouTube transcript extraction
  - Integrate `youtube-transcript-api` + `yt-dlp`
  - Implement caching in Redis
  - Create YouTube service and tasks
- Day 3-4: Article extraction
  - Integrate `newspaper3k` + `BeautifulSoup4`
  - Implement article service and tasks
- Day 5: URL upload endpoint
  - Create `/upload/url` endpoint
  - Add batch processing support
  - Update Gradio upload tab

**Week 2: Features 7 & 8**
- Day 1-2: Feature 7 (Chat File Upload)
  - Implement multipart file upload in chat
  - Integrate Claude Vision API for images
  - Create file handler utility
  - Update Gradio chat interface
- Day 3-5: Feature 8 (Book Processing)
  - Implement chapter detection with PyMuPDF
  - Run migration `006_add_book_metadata.sql`
  - Create book service and parallel chapter tasks
  - Test with 10 real books (300+ pages each)

**Testing & Deployment**:
- Integration tests for URL extraction and book processing
- E2E tests for file upload in chat
- Load test: Upload 50 URLs concurrently
- Deploy to Render staging
- Monitor for 2 days, fix bugs
- Deploy to production

---

### Phase 3: Priority 3 (Sprint 3 - Advanced Features)
**Duration**: 1 week
**Features**: 5 (Agent Chat), 6 (Course Addition)

**Week 1: Features 5 & 6**
- Day 1-2: Feature 5 (Agent Chat)
  - Create agent chat endpoint
  - Run migration `005_create_agent_feedback_table.sql`
  - Implement agent service with 4 agent types
  - Create Gradio agent selector component
- Day 3-4: Feature 6 (Course Addition)
  - Run migration `004_add_content_additions_column.sql`
  - Create course addition endpoint
  - Implement course service with audit logging
  - Create Gradio course manager component
- Day 5: Testing & deployment
  - Integration tests for agent chat and course addition
  - E2E tests for feedback submission
  - Deploy to production

**Final Validation**:
- Regression testing for all 9 features
- Performance testing (1000 req/s load)
- Security audit (OWASP top 10 checks)
- Documentation review
- User acceptance testing (UAT)

---

## Rollout Strategy

### Feature Flag Configuration
```python
# app/core/config.py
class Settings(BaseSettings):
    # Feature flags (all default TRUE for production rollout)
    ENABLE_RND_DEPARTMENT: bool = True  # Feature 1
    ENABLE_WEBSOCKET_STATUS: bool = True  # Feature 2
    ENABLE_URL_UPLOAD: bool = True  # Feature 3
    ENABLE_SOURCE_ATTRIBUTION: bool = True  # Feature 4
    ENABLE_AGENT_CHAT: bool = False  # Feature 5 (manual enable)
    ENABLE_COURSE_ADDITION: bool = False  # Feature 6 (manual enable)
    ENABLE_CHAT_FILE_UPLOAD: bool = True  # Feature 7
    ENABLE_BOOK_PROCESSING: bool = True  # Feature 8
    ENABLE_AGENT_ROUTING: bool = True  # Feature 9
```

### Gradual Rollout Plan
1. **Sprint 1 (P1)**: Deploy with feature flags OFF, enable for internal testing (1 week)
2. **Sprint 2 (P1)**: Enable for 10% of users, monitor metrics (3 days)
3. **Sprint 3 (P1)**: Enable for 50% of users, monitor performance (3 days)
4. **Sprint 4 (P1)**: Enable for 100% of users (P1 features fully rolled out)
5. **Repeat for P2 and P3** features

### Monitoring & Alerts
```yaml
# monitoring/alert_rules.yml additions
- alert: HighWebSocketConnectionFailures
  expr: rate(empire_websocket_connection_errors_total[5m]) > 0.1
  for: 5m
  severity: warning

- alert: URLExtractionFailureRate
  expr: rate(empire_url_extraction_errors_total[5m]) > 0.2
  for: 5m
  severity: warning

- alert: AgentRoutingHighLatency
  expr: histogram_quantile(0.95, empire_agent_routing_decision_time_seconds) > 0.5
  for: 5m
  severity: critical
```

---

## Cost Impact Analysis

### New Service Costs (Monthly)

| Service | Feature | Cost | Justification |
|---------|---------|------|---------------|
| YouTube Transcript API | 3 | $0 | Free tier: 100 requests/day |
| Claude Vision API | 7 | ~$20-40 | 1000 images/month @ $0.02-0.04/image |
| LangExtract (Gemini) | 4 | ~$10-20 | 5000 extractions/month @ $0.002-0.004/request |
| LlamaParse OCR | 8 | $0 | Free tier: 10K pages/month |
| **Total New Costs** | | **$30-60** | Within budget ($350-500/month) |

### Existing Service Impact

| Service | Current Cost | New Cost | Delta |
|---------|--------------|----------|-------|
| Anthropic Claude API | $100-150 | $120-180 | +$20-30 (Vision API) |
| Supabase | $25 | $25 | $0 (storage within quota) |
| Upstash Redis | $0 | $0 | $0 (free tier sufficient) |
| Render (web + workers) | $14 | $14 | $0 (no new services) |

**Total Monthly Cost**: $169-$219 (before) → $219-$299 (after) = **+$50-80/month**
**Well within budget**: $350-500/month

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| WebSocket connection overload (Feature 2) | MEDIUM | HIGH | Rate limiting, connection pooling, load testing |
| YouTube API rate limits (Feature 3) | MEDIUM | MEDIUM | Caching, fallback to audio transcription |
| Book chapter detection failures (Feature 8) | HIGH | MEDIUM | Fallback to regular document processing |
| Agent routing incorrect decisions (Feature 9) | MEDIUM | MEDIUM | Manual override, feedback collection |
| Vision API cost overruns (Feature 7) | LOW | MEDIUM | Image compression, caching, monthly budget alerts |

### Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Database migration failures | LOW | CRITICAL | Test migrations on staging, backup before production |
| Performance degradation | MEDIUM | HIGH | Load testing, monitoring, gradual rollout |
| User confusion with new features | MEDIUM | LOW | Clear documentation, tooltips, progressive disclosure |
| Accidental course modifications (Feature 6) | MEDIUM | MEDIUM | Confirmation checkbox, audit logging, rollback capability |

---

## Success Criteria

### Technical Success Metrics
- [ ] All 9 features pass integration tests (>95% pass rate)
- [ ] P95 query latency remains <500ms (no performance regression)
- [ ] WebSocket connections remain stable under load (100+ concurrent)
- [ ] Agent routing achieves >90% correct pattern selection
- [ ] Source attribution accuracy >95% (manual validation of 100 queries)
- [ ] Book chapter detection accuracy >90% (10 test books)
- [ ] URL extraction success rate >95% (100 test URLs)

### Business Success Metrics
- [ ] Document throughput increases to 1000+/day (from 500/day)
- [ ] Query volume maintains or increases (5000+/day)
- [ ] User satisfaction score >4.5/5 (user surveys)
- [ ] Feature adoption rate >60% within 30 days (P1 features)
- [ ] Zero critical bugs in production (no rollbacks required)

### Cost Success Metrics
- [ ] Total monthly cost remains <$500/month
- [ ] New feature costs <$100/month
- [ ] Cloud services cost delta <$80/month

---

## Next Steps

1. **Review & Approval**: Stakeholder review of this technical plan (2 days)
2. **Task Breakdown**: Generate detailed tasks using `/speckit.tasks` command (1 day)
3. **GitHub Issues**: Create GitHub issues for all tasks with labels and milestones (1 day)
4. **Sprint Planning**: Assign tasks to Sprint 1, 2, 3 with team capacity planning (1 day)
5. **Begin Implementation**: Start Phase 0 (Foundation) immediately after approval

**Timeline**:
- Phase 0 (Foundation): 3-5 days
- Phase 1 (Sprint 1): 2 weeks
- Phase 2 (Sprint 2): 2 weeks
- Phase 3 (Sprint 3): 1 week
- **Total**: ~6 weeks (42 days) for all 9 features

---

**Document Version**: 1.0
**Last Updated**: 2025-11-24
**Status**: Ready for Review
**Next Action**: Generate task breakdown with `/speckit.tasks`
