# Architecture Plan: 010-Production Excellence

## Overview

This document outlines the technical architecture for achieving 100/100 production readiness for Empire v7.3. It covers service integrations, observability infrastructure, testing strategy, and migration framework.

---

## 1. Service Integration Architecture

### 1.1 Document Management B2 Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                    Document Management Flow                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌───────────────┐    ┌──────────────┐         │
│  │  Upload  │───▶│ B2Storage     │───▶│  Supabase    │         │
│  │  Request │    │ Service       │    │  Metadata    │         │
│  └──────────┘    └───────────────┘    └──────────────┘         │
│                         │                     │                  │
│                         ▼                     ▼                  │
│               ┌───────────────┐    ┌──────────────────┐        │
│               │ B2 Bucket     │    │ documents table  │        │
│               │ empire-docs/  │    │ - id             │        │
│               │ ├── uploads/  │    │ - b2_file_id     │        │
│               │ ├── processed/│    │ - file_hash      │        │
│               │ └── archived/ │    │ - status         │        │
│               └───────────────┘    └──────────────────┘        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Files to Modify**:
- `app/services/document_management.py`
  - `upload_document()` → Use `B2StorageService.upload_file()`
  - `delete_document()` → Use `B2StorageService.delete_file()`
  - `reprocess_document()` → Use `LlamaIndexService.parse_document()`

**Integration Pattern**:
```python
# document_management.py
from app.services.b2_storage import B2StorageService
from app.services.llama_index_service import get_llama_index_service
from app.services.embedding_service import get_embedding_service

class DocumentManagementService:
    def __init__(self):
        self.b2_service = B2StorageService()
        self.llama_service = get_llama_index_service()
        self.embedding_service = get_embedding_service()

    async def upload_document(self, file_content, filename, metadata):
        # 1. Upload to B2
        b2_result = await self.b2_service.upload_file(
            file_content, filename, folder="uploads"
        )
        # 2. Store metadata in Supabase
        # 3. Trigger processing task
```

### 1.2 Research Tasks Report Generation

```
┌─────────────────────────────────────────────────────────────────┐
│                    Report Generation Pipeline                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌────────────────┐    ┌───────────────┐   │
│  │ Research     │───▶│ ReportExecutor │───▶│ Claude API    │   │
│  │ Artifacts    │    │                │    │ (Generation)  │   │
│  └──────────────┘    └────────────────┘    └───────────────┘   │
│                              │                      │           │
│                              ▼                      ▼           │
│                    ┌────────────────┐    ┌───────────────┐     │
│                    │ B2 Storage     │    │ Supabase      │     │
│                    │ reports/{id}/  │    │ research_     │     │
│                    │ ├── draft.md   │    │ reports table │     │
│                    │ └── final.pdf  │    └───────────────┘     │
│                    └────────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Files to Modify**:
- `app/tasks/research_tasks.py`
  - `generate_report()` → Use `ReportExecutor.execute()`
  - Store reports in B2 under `reports/{project_id}/`

### 1.3 Retrieval Executor Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                    Retrieval Executor Architecture               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                    ┌────────────────────┐                       │
│                    │ RetrievalExecutor  │                       │
│                    └─────────┬──────────┘                       │
│           ┌─────────────────┼─────────────────┐                │
│           ▼                 ▼                 ▼                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ RAG Search  │  │ NLQ Service │  │ Graph Query │            │
│  │ (Hybrid)    │  │ (SQL Gen)   │  │ (Neo4j)     │            │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│         │                │                │                     │
│         ▼                ▼                ▼                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ Supabase    │  │ Supabase    │  │ Neo4j       │            │
│  │ pgvector    │  │ PostgreSQL  │  │ Graph DB    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Services to Integrate**:
- `HybridSearchService` - Already exists
- `NLQService` - Create new or use existing SQL generation
- `Neo4jHTTPClient` - Already exists

---

## 2. Observability Architecture

### 2.1 OpenTelemetry Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                    Distributed Tracing Architecture              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────┐   ┌────────────┐   ┌────────────┐              │
│  │  FastAPI   │──▶│  Celery    │──▶│  External  │              │
│  │  Request   │   │  Task      │   │  Service   │              │
│  └─────┬──────┘   └─────┬──────┘   └─────┬──────┘              │
│        │                │                │                      │
│        └────────────────┴────────────────┘                      │
│                         │                                       │
│                         ▼                                       │
│              ┌─────────────────────┐                           │
│              │  OpenTelemetry      │                           │
│              │  Collector          │                           │
│              └──────────┬──────────┘                           │
│                         │                                       │
│           ┌─────────────┼─────────────┐                        │
│           ▼             ▼             ▼                        │
│    ┌───────────┐ ┌───────────┐ ┌───────────┐                  │
│    │ Jaeger    │ │ Prometheus│ │ Grafana   │                  │
│    │ (Traces)  │ │ (Metrics) │ │ (Viz)     │                  │
│    └───────────┘ └───────────┘ └───────────┘                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**New File**: `app/core/tracing.py`
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def setup_tracing(app, service_name="empire-api"):
    provider = TracerProvider()
    processor = BatchSpanProcessor(OTLPSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Instrument frameworks
    FastAPIInstrumentor.instrument_app(app)
    CeleryInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
```

### 2.2 Health Check Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Health Check Endpoints                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  GET /health              - Basic liveness (always returns 200) │
│  GET /health/ready        - Readiness (checks dependencies)     │
│  GET /health/live         - Liveness (process is running)       │
│  GET /health/dependencies - Detailed dependency status          │
│  GET /health/metrics      - Prometheus metrics export           │
│                                                                  │
│  Dependency Checks:                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ Supabase    │  │ Neo4j       │  │ Redis       │            │
│  │ PostgreSQL  │  │ Graph DB    │  │ Cache       │            │
│  │ ✓ Connected │  │ ✓ Connected │  │ ✓ Connected │            │
│  │ Latency: 5ms│  │ Latency: 8ms│  │ Latency: 2ms│            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ B2 Storage  │  │ Anthropic   │  │ LlamaIndex  │            │
│  │ ✓ Available │  │ ✓ Available │  │ ✓ Available │            │
│  │ Latency: 45ms│ │ Latency: N/A│  │ Latency: 120ms│          │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**New File**: `app/routes/health.py`
```python
@router.get("/health/ready")
async def readiness_check():
    checks = {
        "supabase": await check_supabase(),
        "neo4j": await check_neo4j(),
        "redis": await check_redis(),
        "b2": await check_b2(),
    }
    all_healthy = all(c["healthy"] for c in checks.values())
    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={"ready": all_healthy, "checks": checks}
    )
```

---

## 3. Database Migration Architecture

### 3.1 Alembic Setup

```
Empire/
├── alembic.ini                 # Alembic configuration
├── migrations/
│   ├── env.py                  # Migration environment
│   ├── script.py.mako          # Migration template
│   └── versions/
│       ├── 001_initial_schema.py
│       ├── 002_add_agent_feedback.py
│       └── 003_add_dead_letter_queue.py
```

**Configuration**: `alembic.ini`
```ini
[alembic]
script_location = migrations
sqlalchemy.url = %(SUPABASE_DB_URL)s

[loggers]
keys = root,sqlalchemy,alembic
```

### 3.2 Migration Commands

```bash
# Create new migration
alembic revision --autogenerate -m "Add agent_feedback table"

# Run migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# Show current version
alembic current
```

---

## 4. Testing Architecture

### 4.1 Test Structure

```
tests/
├── unit/
│   ├── services/
│   │   ├── test_document_management.py    # 80%+ coverage target
│   │   ├── test_research_project_service.py
│   │   ├── test_b2_storage.py
│   │   └── test_retrieval_executor.py
│   ├── tasks/
│   │   ├── test_document_processing.py
│   │   ├── test_graph_sync.py
│   │   └── test_research_tasks.py
│   └── core/
│       ├── test_startup_validation.py     # Already exists
│       └── test_service_timeouts.py       # Already exists
├── integration/
│   ├── test_production_readiness.py       # Already exists (26 tests)
│   ├── test_document_pipeline.py          # New
│   ├── test_research_workflow.py          # New
│   └── test_health_endpoints.py           # New
└── e2e/
    ├── test_upload_to_query.py            # New
    └── test_research_project_lifecycle.py # New
```

### 4.2 Coverage Targets

| Module | Current | Target | Priority |
|--------|---------|--------|----------|
| `app/core/` | 50% | 90% | High |
| `app/services/` | 20% | 80% | Critical |
| `app/tasks/` | 0% | 70% | High |
| `app/routes/` | 30% | 70% | Medium |
| `app/middleware/` | 50% | 80% | High |

### 4.3 Test Fixtures

```python
# conftest.py
@pytest.fixture
def mock_b2_service():
    with patch('app.services.b2_storage.B2StorageService') as mock:
        mock.return_value.upload_file.return_value = {
            "file_id": "test-file-id",
            "url": "https://b2.example.com/test.pdf"
        }
        yield mock

@pytest.fixture
def mock_supabase():
    with patch('app.core.supabase_client.get_supabase_client') as mock:
        yield mock

@pytest.fixture
def mock_neo4j():
    with patch('app.services.neo4j_http_client.get_neo4j_http_client') as mock:
        yield mock
```

---

## 5. Authentication Enhancements

### 5.1 WebSocket Authentication Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    WebSocket Authentication                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Client                    Server                               │
│    │                         │                                  │
│    │  ws://api/ws?token=JWT  │                                  │
│    │────────────────────────▶│                                  │
│    │                         │                                  │
│    │                    ┌────┴────┐                             │
│    │                    │ Validate │                            │
│    │                    │   JWT    │                            │
│    │                    └────┬────┘                             │
│    │                         │                                  │
│    │  ◀─ Accept/Reject ──────│                                  │
│    │                         │                                  │
│    │  ◀─ Messages ───────────│  (if accepted)                  │
│    │                         │                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation**:
```python
# app/routes/research_projects.py
@router.websocket("/ws/{project_id}")
async def project_websocket(
    websocket: WebSocket,
    project_id: str,
    token: str = Query(...)
):
    # Validate JWT token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
    except jwt.InvalidTokenError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Check project access
    if not await user_has_project_access(user_id, project_id):
        await websocket.close(code=4003, reason="Access denied")
        return

    await websocket.accept()
    # ... handle messages
```

---

## 6. File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `app/core/tracing.py` | OpenTelemetry setup |
| `app/routes/health.py` | Enhanced health checks |
| `alembic.ini` | Migration configuration |
| `migrations/env.py` | Migration environment |
| `migrations/versions/*.py` | Schema migrations |
| `tests/unit/services/*.py` | Service unit tests |
| `tests/integration/test_*.py` | Integration tests |
| `docs/runbooks/*.md` | Operations documentation |

### Modified Files
| File | Changes |
|------|---------|
| `app/services/document_management.py` | B2 integration |
| `app/tasks/research_tasks.py` | Report generation |
| `app/services/task_executors/retrieval_executor.py` | Service integrations |
| `app/api/upload.py` | B2 verification |
| `app/workflows/langgraph_workflows.py` | Tool calling |
| `app/routes/research_projects.py` | WebSocket auth |
| `app/routes/documents.py` | Admin check |
| `app/services/research_project_service.py` | Celery integration |
| `app/main.py` | Tracing middleware |

---

## 7. Deployment Considerations

### 7.1 Environment Variables (New)
```bash
# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector.example.com:4317
OTEL_SERVICE_NAME=empire-api
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1  # 10% sampling in production

# Health Check Timeouts
HEALTH_CHECK_TIMEOUT_MS=5000
DEPENDENCY_CHECK_TIMEOUT_MS=3000
```

### 7.2 Dependencies (New)
```txt
# requirements.txt additions
opentelemetry-api>=1.20.0
opentelemetry-sdk>=1.20.0
opentelemetry-instrumentation-fastapi>=0.41b0
opentelemetry-instrumentation-celery>=0.41b0
opentelemetry-instrumentation-httpx>=0.41b0
opentelemetry-exporter-otlp>=1.20.0
alembic>=1.13.0
```

---

## 8. Risk Mitigation

| Risk | Mitigation Strategy |
|------|---------------------|
| B2 integration failures | Implement retry with exponential backoff |
| OpenTelemetry overhead | Configure sampling rate, use async export |
| Migration failures | Test on staging, maintain rollback scripts |
| Test coverage gaps | Prioritize critical paths, use coverage gates |

---

## 9. Success Criteria

- [ ] All 25 TODOs resolved
- [ ] Test coverage ≥ 80% on critical services
- [ ] All health check endpoints operational
- [ ] Distributed tracing functional
- [ ] Migration framework in place
- [ ] Runbook documentation complete
- [ ] Production deployment successful

---

**Author**: Claude Code
**Date**: 2026-01-17
**Version**: 1.0
