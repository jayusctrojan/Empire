# Tasks: Production Excellence - 100/100 Readiness

**Input**: Design documents from `/specs/010-production-excellence/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure for production excellence features

- [ ] T001 Install production dependencies (opentelemetry-sdk, alembic, pytest-cov) in requirements.txt
- [ ] T002 [P] Create migrations directory structure in migrations/
- [ ] T003 [P] Create alembic.ini configuration file in migrations/alembic.ini
- [ ] T004 Create Alembic env.py with Supabase connection in migrations/env.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Create database migration for dead_letter_queue table in migrations/versions/001_dead_letter_queue.py
- [ ] T006 [P] Create database migration for agent_feedback table in migrations/versions/002_agent_feedback.py
- [ ] T007 Create OpenTelemetry tracing setup in app/core/tracing.py
- [ ] T008 [P] Create tracing middleware for FastAPI in app/middleware/tracing.py
- [ ] T009 [P] Create base health check models in app/core/health.py
- [ ] T010 Create conftest.py with shared fixtures in tests/conftest.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Complete Service Integration (Priority: P1) 🎯 MVP

**Goal**: All service integrations fully functional with B2 storage, text extraction, and embedding generation

**Independent Test**: Upload document, verify B2 storage, verify text extraction and embedding generation

### Implementation for User Story 1

- [ ] T011 [US1] Implement B2 upload in upload_document() in app/services/document_management.py
- [ ] T012 [US1] Implement B2 deletion in delete_document() in app/services/document_management.py
- [ ] T013 [US1] Implement text re-extraction in reprocess_document() in app/services/document_management.py
- [ ] T014 [US1] Implement embedding regeneration in reprocess_document() in app/services/document_management.py
- [ ] T015 [US1] Implement report generation in generate_report() in app/tasks/research_tasks.py
- [ ] T016 [US1] Connect report generation to B2 storage in app/tasks/research_tasks.py
- [ ] T017 [P] [US1] Integrate NLQ service in retrieval executor in app/services/task_executors/retrieval_executor.py
- [ ] T018 [P] [US1] Integrate Neo4j service for graph retrieval in app/services/task_executors/retrieval_executor.py
- [ ] T019 [US1] Implement B2 verification in upload API in app/api/upload.py
- [ ] T020 [US1] Implement LLM tool binding in LangGraph workflows in app/workflows/langgraph_workflows.py
- [ ] T021 [US1] Create unit tests for document management in tests/unit/test_document_management.py

**Checkpoint**: Document upload/delete/reprocess fully functional with B2

---

## Phase 4: User Story 2 - Reliable Task Processing (Priority: P1)

**Goal**: Background task processing reliable with proper error handling and DLQ

**Independent Test**: Trigger task, verify completion or DLQ capture on failure

### Implementation for User Story 2

- [ ] T022 [US2] Implement project initialization Celery task trigger in app/services/research_project_service.py
- [ ] T023 [US2] Implement task revocation on project cancellation in app/services/research_project_service.py
- [ ] T024 [US2] Implement DLQ database storage in send_to_dead_letter_queue() in app/celery_app.py
- [ ] T025 [US2] Implement DLQ inspection endpoint in app/api/routes/dlq.py
- [ ] T026 [US2] Implement DLQ retry functionality in app/api/routes/dlq.py
- [ ] T027 [US2] Create unit tests for research project service in tests/unit/test_research_project_service.py
- [ ] T028 [US2] Create integration tests for DLQ in tests/integration/test_dlq.py

**Checkpoint**: Task processing reliable with DLQ capture

---

## Phase 5: User Story 3 - System Observability (Priority: P2)

**Goal**: Distributed tracing and comprehensive health checks operational

**Independent Test**: Make API request, verify trace ID in logs and response headers

### Implementation for User Story 3

- [ ] T029 [US3] Implement trace ID generation in tracing middleware in app/middleware/tracing.py
- [ ] T030 [US3] Implement trace context propagation to Celery tasks in app/celery_app.py
- [ ] T031 [US3] Implement trace ID injection in structlog in app/core/tracing.py
- [ ] T032 [US3] Implement liveness probe endpoint (/health/live) in app/routes/health.py
- [ ] T033 [US3] Implement readiness probe endpoint (/health/ready) in app/routes/health.py
- [ ] T034 [US3] Implement deep health check endpoint (/health/deep) in app/routes/health.py
- [ ] T035 [P] [US3] Implement Supabase health check in app/core/health.py
- [ ] T036 [P] [US3] Implement Neo4j health check in app/core/health.py
- [ ] T037 [P] [US3] Implement Redis health check in app/core/health.py
- [ ] T038 [P] [US3] Implement B2 health check in app/core/health.py
- [ ] T039 [US3] Create unit tests for tracing in tests/unit/test_tracing.py
- [ ] T040 [US3] Create integration tests for health endpoints in tests/integration/test_health_endpoints.py

**Checkpoint**: Observability operational with tracing and health checks

---

## Phase 6: User Story 4 - Secure Authentication (Priority: P2)

**Goal**: All access points properly authenticated, WebSocket secured

**Independent Test**: Attempt WebSocket connection without token, verify rejection

### Implementation for User Story 4

- [ ] T041 [US4] Implement JWT validation for WebSocket connections in app/routes/research_projects.py
- [ ] T042 [US4] Implement WebSocket connection rejection without valid token in app/routes/research_projects.py
- [ ] T043 [US4] Implement admin check for approval listings in app/routes/documents.py
- [ ] T044 [US4] Implement non-admin filtering for pending approvals in app/routes/documents.py
- [ ] T045 [US4] Create integration tests for WebSocket auth in tests/integration/test_websocket_auth.py

**Checkpoint**: Authentication secure on all access points

---

## Phase 7: User Story 5 - Test Coverage Confidence (Priority: P2)

**Goal**: 80%+ test coverage overall, 100% on critical paths

**Independent Test**: Run pytest with coverage, verify thresholds met

### Implementation for User Story 5

- [ ] T046 [P] [US5] Create unit tests for document_processing.py in tests/unit/test_document_processing.py
- [ ] T047 [P] [US5] Create unit tests for graph_sync.py in tests/unit/test_graph_sync.py
- [ ] T048 [P] [US5] Create unit tests for celery_app.py in tests/unit/test_celery_app.py
- [ ] T049 [P] [US5] Create integration tests for B2 integration in tests/integration/test_b2_integration.py
- [ ] T050 [P] [US5] Create integration tests for Neo4j integration in tests/integration/test_neo4j_integration.py
- [ ] T051 [US5] Configure pytest-cov for 80% threshold in pyproject.toml
- [ ] T052 [US5] Run full test suite and verify coverage in CI

**Checkpoint**: Test coverage meets production requirements

---

## Phase 8: User Story 6 - Database Schema Management (Priority: P3)

**Goal**: Versioned database migrations with rollback capability

**Independent Test**: Apply migration, verify schema change, rollback, verify reversion

### Implementation for User Story 6

- [ ] T053 [US6] Create initial schema migration from current state in migrations/versions/003_initial_schema.py
- [ ] T054 [US6] Implement migration up/down scripts for all new tables
- [ ] T055 [US6] Create migration test suite in tests/integration/test_migrations.py
- [ ] T056 [US6] Document migration procedures in docs/MIGRATION_GUIDE.md

**Checkpoint**: Migrations operational with rollback capability

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Minor completions and documentation

- [ ] T057 [P] Implement semantic similarity using embeddings in app/services/agent_router_service.py
- [ ] T058 [P] Implement JSON parsing of LLM output in app/services/content_prep_agent.py
- [ ] T059 [P] Integrate cost tracking with notification service in app/services/cost_tracking_service.py
- [ ] T060 [P] Implement classification feedback storage in app/services/classification_service.py
- [ ] T061 [P] Implement asset management feedback storage in app/services/asset_management_service.py
- [ ] T062 Run all 26 production readiness tests and verify pass
- [ ] T063 Verify 0 TODO items remain in codebase
- [ ] T064 Verify production readiness score is 100/100

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - US1 and US2 can proceed in parallel (both P1 priority)
  - US3 and US4 can proceed in parallel (both P2 priority)
  - US5 depends on implementation from US1-4 being complete
  - US6 can proceed independently after Foundational
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational - No dependencies on other stories
- **US2 (P1)**: Can start after Foundational - No dependencies on other stories
- **US3 (P2)**: Can start after Foundational - Integrates with US2 (Celery tracing)
- **US4 (P2)**: Can start after Foundational - No dependencies on other stories
- **US5 (P2)**: Depends on US1-4 implementations for test coverage
- **US6 (P3)**: Can start after Foundational - No dependencies on other stories

### Parallel Opportunities

- T002/T003: Setup tasks can run in parallel
- T005/T006: Migration scripts can run in parallel
- T007/T008/T009: Foundational infrastructure can partially parallelize
- T017/T018: Retrieval executor integrations can run in parallel
- T035/T036/T037/T038: Health check implementations can run in parallel
- T046/T047/T048/T049/T050: Test creation can run in parallel
- T057/T058/T059/T060/T061: Minor completions can run in parallel

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Service Integration)
4. Complete Phase 4: User Story 2 (Task Processing)
5. **STOP and VALIDATE**: Test document flow and task reliability
6. Deploy if production-critical features working

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → Document integration complete → Validate
3. US2 → Task processing reliable → Validate
4. US3 → Observability operational → Validate
5. US4 → Authentication secure → Validate
6. US5 → Test coverage met → Validate
7. US6 → Migrations operational → Validate
8. Polish → 100/100 production readiness achieved

---

## Summary

| Phase | User Story | Task Count | Parallel Tasks |
|-------|------------|------------|----------------|
| 1 | Setup | 4 | 2 |
| 2 | Foundational | 6 | 3 |
| 3 | US1: Service Integration | 11 | 2 |
| 4 | US2: Task Processing | 7 | 0 |
| 5 | US3: Observability | 12 | 4 |
| 6 | US4: Authentication | 5 | 0 |
| 7 | US5: Test Coverage | 7 | 5 |
| 8 | US6: Migrations | 4 | 0 |
| 9 | Polish | 8 | 5 |
| **Total** | | **64** | **21** |
