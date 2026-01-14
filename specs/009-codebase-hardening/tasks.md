# Tasks: Codebase Hardening & Completion

**Input**: Design documents from `/specs/009-codebase-hardening/`
**Prerequisites**: plan.md, spec.md
**TaskMaster Integration**: Tasks 151-161 in v7_3_features tag

**Organization**: Tasks are organized by security priority and functional area.

## Format: `[ID] [P?] [Phase] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Phase]**: Which phase this task belongs to (SEC, CORE, INFRA, QUAL)
- Include exact file paths in descriptions

---

## Phase 1: Security Critical (MUST complete first)

**Purpose**: Address critical security gaps before other work

### Implementation

- [ ] T151 [SEC] Implement RLS Database Context Middleware in app/middleware/rls_context.py
  - Complete TODO implementation for session variable setting
  - Add SET app.current_user_id, app.current_role, app.request_id
  - Add error handling (reject with 503 on failure)
  - Add structlog logging for RLS operations
  - Create unit tests for RLS context

- [ ] T152 [P] [SEC] Implement WebSocket JWT Authentication in app/middleware/websocket_auth.py
  - Create WebSocketAuthenticator class
  - Implement JWT token validation in handshake
  - Add connection limit tracking per user (max 5)
  - Track connections in Redis
  - Define close codes: 4001 (invalid token), 4002 (limit exceeded), 4003 (unauthorized), 4004 (expired)
  - Add tests for all auth scenarios

- [ ] T153 [P] [SEC] Create Exception Hierarchy in app/core/exceptions.py
  - Create EmpireBaseException with error_code, details, cause, timestamp
  - Create hierarchy: DatabaseException, ExternalServiceException, ValidationException, AuthException
  - Define error codes (DB: 1xxx, External: 2xxx, Validation: 3xxx, Auth: 4xxx, Internal: 5xxx)
  - Add to_dict() method for API responses
  - Create unit tests for serialization

- [ ] T154 [SEC] Create Error Handling Decorator in app/core/exceptions.py
  - Create @handle_exceptions decorator with logger, default_error_code, reraise params
  - Wrap bare exceptions with EmpireBaseException
  - Log with structlog including error_type, request_id
  - Apply to 48+ bare exception locations

**Checkpoint**: Security-critical gaps addressed. Proceed to Core Functionality.

---

## Phase 2: Core Functionality (Primary Features)

**Purpose**: Complete core features that are partially implemented

### Neo4j Graph Sync (T153)

- [ ] T155 [CORE] Complete Neo4j Graph Sync in app/tasks/graph_sync.py
  - Implement sync_document() to create Document nodes
  - Implement extract_entities() using Claude Haiku with structured output
  - Implement create_relationships() for MENTIONS edges with confidence scores
  - Implement delete_document_graph() for cleanup with orphan detection
  - Define entity types: Person, Organization, Location, Date, Event, Product, Policy, Contract
  - Add Cypher templates for MERGE and CREATE operations
  - Add integration tests with Neo4j

### Research Task Completion (T155)

- [ ] T156 [P] [CORE] Complete Research Report Generator in app/tasks/research_tasks.py
  - Implement generate_report() to produce actual content
  - Define report types: EXECUTIVE_SUMMARY, DETAILED_ANALYSIS, RESEARCH_BRIEF, COMPARISON
  - Create ResearchReport model with sections, citations, methodology, confidence_score
  - Replace placeholder text with Claude-generated analysis
  - Add B2 storage for generated reports
  - Add Neo4j storage for report metadata
  - Create tests for report generation

### LlamaIndex Integration (T156)

- [ ] T157 [P] [CORE] Complete LlamaIndex Integration in app/tasks/document_processing.py
  - Complete process_document() for PDF, DOCX, TXT, MD, PPTX, XLSX
  - Implement extract_metadata() for title, author, date, keywords
  - Implement chunk_document() with strategy selection
  - Create ProcessedDocument model with chunks, metadata, processing_time
  - Wire up to source_processing Celery task
  - Add tests for each file type

**Checkpoint**: Core functionality complete. Proceed to Infrastructure.

---

## Phase 3: Infrastructure (Resilience & Storage)

**Purpose**: Add infrastructure for reliability and storage

### B2 Storage (T157)

- [ ] T158 [INFRA] Complete B2 Storage Service in app/services/b2_storage.py
  - Implement upload_file() with retry logic
  - Implement download_file() with streaming
  - Implement delete_file() with confirmation
  - Implement get_presigned_url() for secure access
  - Implement upload_multipart() for large files (100MB chunks)
  - Create UploadResult model with b2_path, file_id, content_hash
  - Add tests with mocked B2 client

### CrewAI Workflows (T158)

- [ ] T159 [P] [INFRA] Complete CrewAI Workflow Orchestrator in app/tasks/crewai_workflows.py
  - Implement execute_workflow() for complete crew execution
  - Implement handle_agent_failure() with recovery strategies (RETRY, SKIP, FALLBACK, ABORT)
  - Implement aggregate_results() to combine agent outputs
  - Define workflow types: RESEARCH, DOCUMENT_ANALYSIS, CONTENT_REVIEW, REPORT_GENERATION
  - Add execution templates for each workflow type
  - Add tests for workflow execution and failure recovery

### Circuit Breaker (T159)

- [ ] T160 [P] [INFRA] Implement Circuit Breaker Pattern in app/core/circuit_breaker.py
  - Create CircuitBreaker class with failure_threshold, recovery_timeout, half_open_max_calls
  - Implement call() method with fallback support
  - Implement state transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
  - Add Prometheus metrics: circuit_breaker_state, failures_total, successes_total, fallbacks_total
  - Configure for services: Arcade (5 failures, 30s), CrewAI (3 failures, 60s), LlamaIndex, Ollama, Neo4j
  - Add tests for all state transitions

**Checkpoint**: Infrastructure hardened. Proceed to Quality.

---

## Phase 4: Quality (Refactoring & Testing)

**Purpose**: Improve code quality and test coverage

### Large File Refactoring (T160)

- [ ] T161 [QUAL] Refactor multi_agent_orchestration.py (2,224 lines) to app/services/orchestration/
  - Create coordinator.py - Main orchestration logic
  - Create state_machine.py - Workflow state management
  - Create agents/ directory with base.py, research.py, analysis.py, writing.py, review.py
  - Create utils/ directory with prompts.py, formatters.py
  - Add backward-compatible imports with deprecation warnings

- [ ] T162 [P] [QUAL] Refactor content_summarizer_agent.py (1,508 lines) to app/services/summarizer/
  - Create agent.py - Core summarizer
  - Create extractors.py - Key point extraction
  - Create formatters.py - Output formatting
  - Create templates.py - Summary templates
  - Add backward-compatible imports

- [ ] T163 [P] [QUAL] Refactor document_analysis_agents.py (1,285 lines) to app/services/analysis/
  - Create base.py - Base analysis class
  - Create research_analyst.py - AGENT-009
  - Create content_strategist.py - AGENT-010
  - Create fact_checker.py - AGENT-011
  - Add backward-compatible imports

- [ ] T164 [P] [QUAL] Refactor chunking_service.py (1,475 lines) to app/services/chunking/
  - Create service.py - Main service interface
  - Create strategies/ directory with base.py, sentence.py, markdown.py, semantic.py
  - Create validators.py - Chunk validation
  - Add backward-compatible imports

### Test Coverage Improvement (T161)

- [ ] T165 [QUAL] Create Unit Tests for New Services in tests/unit/services/
  - test_adaptive_retrieval_service.py
  - test_agent_selector_service.py
  - test_answer_grounding_evaluator.py
  - test_quality_gate_service.py
  - test_circuit_breaker.py
  - test_exceptions.py
  - test_rls_context.py
  - test_websocket_auth.py

- [ ] T166 [P] [QUAL] Create Integration Tests in tests/integration/
  - neo4j/test_graph_sync.py, test_entity_extraction.py, test_relationship_queries.py
  - b2/test_upload.py, test_download.py, test_multipart.py
  - crewai/test_workflow_execution.py, test_agent_failure_recovery.py
  - supabase/test_rls_enforcement.py

- [ ] T167 [P] [QUAL] Create E2E Tests in tests/e2e/
  - test_document_flow.py (Upload -> Process -> Query)
  - test_research_flow.py (Create -> Execute -> Report)
  - test_auth_flow.py (Register -> Login -> API Access)

- [ ] T168 [P] [QUAL] Create Security Tests in tests/security/
  - test_auth_bypass.py
  - test_rls_isolation.py
  - test_input_validation.py
  - test_rate_limiting.py

**Checkpoint**: Code quality improved, test coverage at 75%.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Security)**: No dependencies - start immediately
- **Phase 2 (Core)**: Depends on T153 (Exception Hierarchy) for proper error handling
- **Phase 3 (Infra)**: Depends on T159 (Circuit Breaker) before T158/T157 for resilience
- **Phase 4 (Quality)**: Depends on Phases 1-3 for code to test

### Within Phases

| Task | Depends On | Can Parallel With |
|------|------------|-------------------|
| T151 | None | T152, T153 |
| T152 | None | T151, T153 |
| T153 | None | T151, T152 |
| T154 | T153 | None |
| T155 | T153, T154 | T156, T157 |
| T156 | T153, T154 | T155, T157 |
| T157 | T153, T154 | T155, T156 |
| T158 | T153 | T159, T160 |
| T159 | T153 | T158, T160 |
| T160 | T153 | T158, T159 |
| T161-T164 | All Core complete | Each other |
| T165-T168 | All Core complete | Each other |

---

## Parallel Execution Example

```bash
# Phase 1: Launch all security tasks
Task: "T151 - RLS Context Middleware"
Task: "T152 - WebSocket Authentication" [P]
Task: "T153 - Exception Hierarchy" [P]
# Then: T154 after T153 completes

# Phase 2: Launch core tasks after Phase 1
Task: "T155 - Neo4j Graph Sync"
Task: "T156 - Research Report Generator" [P]
Task: "T157 - LlamaIndex Integration" [P]

# Phase 3: Launch infrastructure tasks
Task: "T158 - B2 Storage"
Task: "T159 - CrewAI Workflows" [P]
Task: "T160 - Circuit Breaker" [P]

# Phase 4: Launch quality tasks
Task: "T161-T164 - Refactoring" [P between files]
Task: "T165-T168 - Testing" [P between test types]
```

---

## Implementation Strategy

### Sequential Approach (Solo Developer)

1. Phase 1: T151 -> T152 -> T153 -> T154 (Security first)
2. Phase 2: T155 -> T156 -> T157 (Core features)
3. Phase 3: T160 -> T158 -> T159 (Circuit breaker first)
4. Phase 4: T161 -> T165 (Refactor then test)

### Parallel Approach (Team)

1. Developer A: T151, T155, T158, T161-T162
2. Developer B: T152, T156, T159, T163-T164
3. Developer C: T153-T154, T157, T160, T165-T168

---

## TaskMaster Mapping

| speckit Task | TaskMaster ID | Status |
|--------------|---------------|--------|
| T151 | 151 | pending |
| T152 | 152 | pending |
| T153 | 153 | pending |
| T154 | 154 | pending |
| T155 | 155 | pending |
| T156 | 156 | pending |
| T157 | 157 | pending |
| T158 | 158 | pending |
| T159 | 159 | pending |
| T160 | 160 | pending |
| T161-T168 | 161 (combined) | pending |

---

## Notes

- All tasks use structured exception handling from T153
- Circuit breaker (T160) protects external service calls in T155, T156, T157
- Test coverage target: 45% -> 75% (30% increase)
- Backward compatibility maintained for 2 release cycles with deprecation warnings
- File refactoring preserves all existing functionality
