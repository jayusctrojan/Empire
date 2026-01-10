# Implementation Plan: Research Projects (Agent Harness)

**Branch**: `004-agent-harness` | **Date**: 2025-01-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-agent-harness/spec.md`

## Summary

Implement a long-running autonomous research system that accepts user queries, automatically decomposes them into discrete tasks, executes retrieval and synthesis operations concurrently, and generates comprehensive research reports. The architecture uses a two-stage Agent Harness pattern (Initializer + Task Harness) with wave-based parallel execution via Celery groups/chords.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, Celery, Anthropic SDK, Pydantic v2, structlog
**Storage**: Supabase PostgreSQL (pgvector), Neo4j (knowledge graph), Backblaze B2 (reports), Upstash Redis (cache/broker)
**Testing**: pytest, pytest-asyncio, pytest-celery
**Target Platform**: Linux server (Render)
**Project Type**: Web application (FastAPI backend)
**Performance Goals**: <2min (simple 3-5 tasks), <5min (medium 6-10 tasks), <15min (complex 11-20 tasks)
**Constraints**: >60% parallelism ratio, <100ms wave transition latency, quality gates per phase
**Scale/Scope**: 3 concurrent projects per user, indefinite retention

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Existing Stack | PASS | Uses existing Celery, Supabase, Neo4j, Redis infrastructure |
| API-First | PASS | REST endpoints with WebSocket for real-time updates |
| Data Isolation | PASS | RLS policies enforce per-user data separation |
| Observability | PASS | Prometheus metrics, structured logging with structlog |
| Security | PASS | JWT auth, RLS, signed URLs for reports |

## Project Structure

### Documentation (this feature)

```text
specs/004-agent-harness/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 - Design decisions
├── data-model.md        # Phase 1 - Database schema
├── quickstart.md        # Phase 1 - Getting started guide
├── contracts/           # Phase 1 - API specifications
│   ├── research-projects.yaml  # OpenAPI spec
│   └── websocket.md     # WebSocket protocol
└── tasks.md             # Phase 2 - Implementation tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/
│   │   └── research_project.py      # Pydantic models
│   ├── services/
│   │   ├── research_initializer.py  # AGENT: Task planning
│   │   ├── task_harness.py          # AGENT: Task execution
│   │   ├── concurrent_executor.py   # Wave-based parallelism
│   │   ├── performance_monitor.py   # Metrics collection
│   │   └── task_executors/
│   │       ├── retrieval_executor.py
│   │       ├── synthesis_executor.py
│   │       └── report_executor.py
│   ├── routes/
│   │   └── research_projects.py     # API endpoints
│   └── tasks/
│       └── research_tasks.py        # Celery tasks
└── tests/
    ├── unit/
    │   ├── test_initializer.py
    │   ├── test_harness.py
    │   └── test_executors.py
    ├── integration/
    │   └── test_research_workflow.py
    └── e2e/
        └── test_research_lifecycle.py

migrations/
├── 001_create_research_jobs.sql
├── 002_create_plan_tasks.sql
├── 003_create_research_artifacts.sql
└── 004_create_shared_reports.sql
```

**Structure Decision**: Web application pattern - FastAPI backend with Celery workers. No separate frontend package as this integrates with existing Empire Desktop client.

## Architecture Overview

### High-Level Flow

```
User Query → FastAPI → Initializer Service (Claude) → Task Plan
                              ↓
                    Celery: Wave-based Execution
                              ↓
            ┌─────────────────┼─────────────────┐
            ↓                 ↓                 ↓
       Retrieval         Retrieval         Retrieval
        (RAG)             (NLQ)            (Graph)
            └─────────────────┼─────────────────┘
                              ↓
                         Synthesis
                              ↓
                      Report Generation
                              ↓
                    Email Notification
```

### Key Components

1. **Research Initializer Service** - Claude-powered task planning
2. **Task Harness Service** - Sequential task execution with routing
3. **Concurrent Execution Engine** - Wave-based parallel dispatch
4. **Performance Monitor** - SLA tracking and bottleneck detection
5. **Task Executors** - Retrieval, Synthesis, Report generation

### Database Tables

1. **research_jobs** - Project metadata, status, progress
2. **plan_tasks** - Individual tasks with dependencies
3. **research_artifacts** - Retrieved content, findings, sections
4. **shared_reports** - Public link management (FR-005, FR-005a)

## Implementation Phases

### Phase 1: Core Infrastructure (P1 - Submit Research)
- Database migrations (3 tables + RLS)
- Pydantic models for all entities
- Basic API routes (CRUD operations)
- Celery task scaffolding

### Phase 2: Task Planning (P1 - Submit Research)
- Research Initializer Service
- Claude integration for task decomposition
- Task plan validation and storage
- Status transitions

### Phase 3: Task Execution (P1 - Submit Research)
- Task Harness Service
- Retrieval executors (RAG, NLQ, Graph)
- Synthesis executor
- Report executor

### Phase 4: Concurrent Execution (P2 - Performance)
- Concurrent Execution Engine
- Wave-based parallelism
- Quality gates between waves
- Performance monitoring

### Phase 5: Real-time Updates (P2 - Monitor Progress)
- WebSocket endpoint
- Progress notifications
- Task status streaming

### Phase 6: Report Delivery (P3 - Download Reports)
- Report generation (Markdown/PDF)
- B2 storage integration
- Public shareable links with revocation
- Email notifications

### Phase 7: Project Management (P3 - Manage Projects)
- Cancel project functionality
- Project history view
- Concurrent project limits (3 per user)

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Task Persistence | Supabase PostgreSQL | Consistent with Empire data layer |
| Async Execution | Celery + Redis | Leverages existing worker infrastructure |
| Task Planning | Claude Sonnet 4 | Best balance of capability and cost |
| Real-time Updates | WebSocket | Existing Empire WebSocket infrastructure |
| Report Storage | Backblaze B2 | Existing CrewAI asset storage pattern |
| Concurrent Execution | Celery Groups + Chords | Maximize parallelism without custom orchestration |
| Quality Gates | Per-phase validation | Ensure speed doesn't compromise quality |

## Complexity Tracking

No constitution violations requiring justification.

## Next Steps

1. Run `/speckit.tasks` to generate detailed implementation tasks
2. Review generated tasks for completeness
3. Begin Phase 1 implementation

---

**Document Status**: Ready for task generation
