# Implementation Plan: Codebase Hardening & Completion

**Feature Branch**: `009-codebase-hardening`
**Created**: 2025-01-14
**Estimated Tasks**: 11 main tasks (151-161) with 8 subtasks for refactoring and testing

---

## Overview

This plan addresses 11 improvement areas identified in codebase analysis, organized into 4 phases with 25 implementation tasks.

---

## Phase 1: Security Critical (Week 1)

### Task 151: Implement RLS Database Context Middleware
**Priority**: CRITICAL
**Effort**: 4 hours
**Dependencies**: None

**Objective**: Set PostgreSQL session variables for RLS enforcement

**Files to Modify**:
- `app/middleware/rls_context.py` - Complete TODO implementation

**Implementation Steps**:
1. Create async context manager for RLS session
2. Implement `SET app.current_user_id` command
3. Implement `SET app.current_role` command
4. Add connection cleanup in finally block
5. Add error handling for connection failures
6. Add structlog logging for RLS operations
7. Create unit tests for RLS context setting

**Acceptance Criteria**:
- [ ] Session variables set on authenticated requests
- [ ] Variables cleared after request completion
- [ ] Graceful handling of connection failures
- [ ] Tests verify RLS enforcement

---

### Task 152: Implement WebSocket JWT Authentication
**Priority**: CRITICAL
**Effort**: 4 hours
**Dependencies**: None

**Objective**: Secure WebSocket connections with token validation

**Files to Modify**:
- `app/routes/research_projects.py` - Add auth to WebSocket handler
- `app/middleware/websocket_auth.py` - Create new file

**Implementation Steps**:
1. Create WebSocketAuthenticator class
2. Implement JWT token validation in handshake
3. Add connection limit tracking per user (max 5)
4. Implement connection tracking in Redis
5. Add graceful token expiration handling
6. Define WebSocket-specific close codes
7. Create unit and integration tests

**Acceptance Criteria**:
- [ ] Invalid tokens rejected with 4001
- [ ] Connection limits enforced with 4002
- [ ] User context available in handlers
- [ ] Tests for all auth scenarios

---

### Task 153: Create Exception Hierarchy and Base Classes
**Priority**: CRITICAL
**Effort**: 3 hours
**Dependencies**: None

**Objective**: Define structured exception classes for Empire

**Files to Create**:
- `app/core/exceptions.py` - Exception hierarchy

**Implementation Steps**:
1. Create EmpireBaseException with error_code, details, cause
2. Create DatabaseException hierarchy (Supabase, Neo4j)
3. Create ExternalServiceException hierarchy
4. Create ValidationException hierarchy
5. Create AuthException hierarchy
6. Create CircuitBreakerException
7. Add to_dict() method for API responses
8. Create unit tests for exception serialization

**Acceptance Criteria**:
- [ ] All exception types defined
- [ ] Error codes documented
- [ ] Serialization to JSON works
- [ ] Tests for all exception types

---

### Task 154: Create Error Handling Decorators
**Priority**: CRITICAL
**Effort**: 3 hours
**Dependencies**: Task 153

**Objective**: Reduce exception handling boilerplate

**Files to Create**:
- `app/core/error_handlers.py` - Decorators and utilities

**Implementation Steps**:
1. Create @handle_exceptions decorator for async functions
2. Create @handle_sync_exceptions for sync functions
3. Add configurable logging and reraise behavior
4. Create error response formatter
5. Create retry decorator with backoff
6. Create unit tests for decorators

**Acceptance Criteria**:
- [ ] Decorators reduce boilerplate
- [ ] Logging includes context
- [ ] Retry logic works correctly
- [ ] Tests for all decorators

---

### Task 155: Replace Bare Exceptions (Security Files)
**Priority**: CRITICAL
**Effort**: 6 hours
**Dependencies**: Tasks 153, 154

**Objective**: Fix exception handling in security-critical files

**Files to Modify**:
- `app/middleware/auth.py`
- `app/middleware/rbac.py`
- `app/middleware/rls_context.py`
- `app/routes/auth.py`
- `app/services/auth_service.py`

**Implementation Steps**:
1. Identify all bare exceptions in security files
2. Replace with specific exception types
3. Add structured logging with context
4. Apply error handling decorators
5. Ensure no `except: pass` remains
6. Create tests for error scenarios

**Acceptance Criteria**:
- [ ] Zero bare exceptions in security files
- [ ] All errors logged with context
- [ ] Decorators applied consistently
- [ ] Tests for error paths

---

## Phase 2: Core Functionality (Week 2)

### Task 156: Implement Neo4j Document Node Creation
**Priority**: HIGH
**Effort**: 4 hours
**Dependencies**: Task 153

**Objective**: Create Document nodes in Neo4j when documents are processed

**Files to Modify**:
- `app/tasks/graph_sync.py` - Implement create_document_node()

**Implementation Steps**:
1. Complete create_document_node() function
2. Define Document node schema (id, title, source, created_at, etc.)
3. Add upsert logic for document updates
4. Implement batch document creation
5. Add error handling with Neo4jException
6. Create integration tests with test Neo4j

**Acceptance Criteria**:
- [ ] Documents create corresponding nodes
- [ ] Upsert handles duplicates
- [ ] Batch processing works
- [ ] Tests with real Neo4j queries

---

### Task 157: Implement Entity Extraction for Graph
**Priority**: HIGH
**Effort**: 6 hours
**Dependencies**: Task 156

**Objective**: Extract named entities from documents using LLM

**Files to Modify**:
- `app/tasks/graph_sync.py` - Implement extract_entities()

**Implementation Steps**:
1. Create LLM prompt for entity extraction
2. Define entity types (Person, Organization, Location, etc.)
3. Implement entity extraction with Claude Haiku
4. Add confidence scoring for entities
5. Implement deduplication logic
6. Add error handling and retry
7. Create unit tests with mock LLM

**Acceptance Criteria**:
- [ ] Entities extracted from document text
- [ ] Confidence scores assigned
- [ ] Deduplication works
- [ ] Tests with mock responses

---

### Task 158: Implement Graph Relationship Creation
**Priority**: HIGH
**Effort**: 4 hours
**Dependencies**: Tasks 156, 157

**Objective**: Create relationships between documents and entities

**Files to Modify**:
- `app/tasks/graph_sync.py` - Implement create_relationships()

**Implementation Steps**:
1. Implement MENTIONS relationship (Document -> Entity)
2. Implement RELATED_TO relationship (Entity -> Entity)
3. Add confidence scores to relationships
4. Implement batch relationship creation
5. Add orphan entity cleanup
6. Create integration tests

**Acceptance Criteria**:
- [ ] MENTIONS relationships created
- [ ] Related entities linked
- [ ] Orphans cleaned up
- [ ] Tests verify relationships

---

### Task 159: Complete Research Report Generation
**Priority**: HIGH
**Effort**: 8 hours
**Dependencies**: Task 153

**Objective**: Replace placeholder with actual report generation

**Files to Modify**:
- `app/tasks/research_tasks.py` - Implement report generation

**Implementation Steps**:
1. Create ReportGenerator class
2. Implement executive summary generation
3. Implement section-by-section analysis
4. Add citation extraction and formatting
5. Add methodology section
6. Calculate confidence scores
7. Implement report caching
8. Create unit tests with mock LLM

**Acceptance Criteria**:
- [ ] Reports contain actual content
- [ ] Citations properly formatted
- [ ] Confidence scores calculated
- [ ] Tests verify report structure

---

### Task 160: Complete LlamaIndex Document Parsing
**Priority**: HIGH
**Effort**: 6 hours
**Dependencies**: Task 153

**Objective**: Implement actual document parsing

**Files to Modify**:
- `app/tasks/document_processing.py` - Complete parsing

**Implementation Steps**:
1. Implement PDF parsing with LlamaParse
2. Implement DOCX parsing
3. Implement TXT/MD parsing
4. Add metadata extraction (title, author, date)
5. Implement chunking integration
6. Add progress callbacks
7. Create tests for each file type

**Acceptance Criteria**:
- [ ] PDF, DOCX, TXT, MD supported
- [ ] Metadata extracted accurately
- [ ] Chunking produces semantic units
- [ ] Tests for each format

---

### Task 161: Replace Bare Exceptions (Core Files)
**Priority**: HIGH
**Effort**: 6 hours
**Dependencies**: Tasks 153, 154

**Objective**: Fix exception handling in remaining core files

**Files to Modify**:
- `app/tasks/research_tasks.py` (12 exceptions)
- `app/services/document_management.py` (8 exceptions)
- `app/services/classification_service.py` (6 exceptions)
- `app/tasks/document_processing.py` (5 exceptions)
- `app/tasks/graph_sync.py` (4 exceptions)

**Implementation Steps**:
1. Audit all bare exceptions in listed files
2. Replace with specific exception types
3. Add structured logging
4. Apply decorators where applicable
5. Remove all `except: pass` blocks
6. Create error scenario tests

**Acceptance Criteria**:
- [ ] Zero bare exceptions in core files
- [ ] All errors logged
- [ ] No silent exception swallowing
- [ ] Tests for error paths

---

## Phase 3: Infrastructure (Week 3)

### Task 162: Implement B2 File Upload
**Priority**: HIGH
**Effort**: 4 hours
**Dependencies**: Task 153

**Objective**: Complete file upload implementation

**Files to Modify**:
- `app/services/b2_storage.py` - Implement upload_file()
- `app/services/document_management.py` - Connect upload

**Implementation Steps**:
1. Implement upload_file() with retry logic
2. Add content hash verification after upload
3. Add progress tracking callback
4. Implement upload metadata
5. Add error handling with B2Exception
6. Create integration tests with mock B2

**Acceptance Criteria**:
- [ ] Files upload reliably
- [ ] Hash verification passes
- [ ] Progress tracked
- [ ] Tests verify upload

---

### Task 163: Implement B2 File Operations
**Priority**: HIGH
**Effort**: 4 hours
**Dependencies**: Task 162

**Objective**: Complete download, delete, and presigned URL operations

**Files to Modify**:
- `app/services/b2_storage.py` - Implement remaining methods

**Implementation Steps**:
1. Implement download_file() with streaming
2. Implement delete_file() with verification
3. Implement get_presigned_url() with expiry
4. Implement multipart upload for large files
5. Add cleanup for failed uploads
6. Create tests for all operations

**Acceptance Criteria**:
- [ ] Download works with streaming
- [ ] Delete removes file and verifies
- [ ] Presigned URLs expire correctly
- [ ] Multipart handles 1GB+ files

---

### Task 164: Implement CrewAI Workflow Execution
**Priority**: HIGH
**Effort**: 6 hours
**Dependencies**: Task 153

**Objective**: Complete multi-agent workflow orchestration

**Files to Modify**:
- `app/tasks/crewai_workflows.py` - Complete workflow execution
- `app/services/async_crew_execution.py` - Complete async handling

**Implementation Steps**:
1. Implement execute_workflow() method
2. Add agent failure handling with retry
3. Implement fallback to single-agent
4. Add progress tracking
5. Implement result aggregation
6. Add timeout handling
7. Create integration tests

**Acceptance Criteria**:
- [ ] Workflows execute end-to-end
- [ ] Agent failures handled
- [ ] Fallback activates correctly
- [ ] Tests for full workflow

---

### Task 165: Implement Circuit Breaker Core
**Priority**: HIGH
**Effort**: 4 hours
**Dependencies**: Task 153

**Objective**: Create circuit breaker implementation

**Files to Create**:
- `app/core/circuit_breaker.py` - Circuit breaker class

**Implementation Steps**:
1. Implement CircuitBreaker class with 3 states
2. Add failure counting and threshold logic
3. Implement recovery timeout
4. Add half-open state with limited calls
5. Add state change callbacks
6. Implement force_open/force_close
7. Create comprehensive unit tests

**Acceptance Criteria**:
- [ ] State transitions work correctly
- [ ] Thresholds enforced
- [ ] Recovery timeout works
- [ ] Tests for all states

---

### Task 166: Integrate Circuit Breakers with Services
**Priority**: HIGH
**Effort**: 4 hours
**Dependencies**: Task 165

**Objective**: Protect external service calls with circuit breakers

**Files to Modify**:
- `app/services/arcade_service.py`
- `app/tasks/crewai_workflows.py`
- `app/tasks/document_processing.py` (LlamaIndex)
- `app/services/embedding_service.py` (Ollama)
- `app/services/neo4j_http_client.py`

**Implementation Steps**:
1. Create circuit breaker instances for each service
2. Wrap external calls with breaker.call()
3. Implement fallback functions
4. Add Prometheus metrics
5. Create integration tests

**Acceptance Criteria**:
- [ ] All external services protected
- [ ] Fallbacks work when open
- [ ] Metrics exported
- [ ] Tests verify breaker behavior

---

### Task 167: Replace Bare Exceptions (Remaining Files)
**Priority**: MEDIUM
**Effort**: 8 hours
**Dependencies**: Tasks 153, 154

**Objective**: Fix all remaining bare exceptions

**Files to Modify**:
- All remaining files with bare exceptions (~15 files)

**Implementation Steps**:
1. Run grep to find all remaining bare exceptions
2. Replace each with specific exception type
3. Add structured logging
4. Apply decorators
5. Create tests for error scenarios

**Acceptance Criteria**:
- [ ] Zero bare exceptions in codebase
- [ ] All errors properly typed
- [ ] Logging complete
- [ ] Full test coverage

---

## Phase 4: Quality (Week 4)

### Task 168: Refactor multi_agent_orchestration.py
**Priority**: HIGH
**Effort**: 6 hours
**Dependencies**: None

**Objective**: Break 2,224 line file into modules

**Files to Create**:
- `app/services/orchestration/__init__.py`
- `app/services/orchestration/coordinator.py`
- `app/services/orchestration/state_machine.py`
- `app/services/orchestration/agents/base.py`
- `app/services/orchestration/agents/research.py`
- `app/services/orchestration/agents/analysis.py`
- `app/services/orchestration/agents/writing.py`
- `app/services/orchestration/agents/review.py`
- `app/services/orchestration/utils/prompts.py`
- `app/services/orchestration/utils/formatters.py`

**Implementation Steps**:
1. Create directory structure
2. Extract coordinator logic
3. Extract each agent to own file
4. Extract utilities
5. Add backward-compatible imports
6. Update all import statements
7. Verify all tests pass

**Acceptance Criteria**:
- [ ] No file exceeds 400 lines
- [ ] All tests pass
- [ ] Backward compatibility maintained
- [ ] Imports work correctly

---

### Task 169: Refactor content_summarizer_agent.py
**Priority**: HIGH
**Effort**: 4 hours
**Dependencies**: None

**Objective**: Break 1,508 line file into modules

**Files to Create**:
- `app/services/summarizer/__init__.py`
- `app/services/summarizer/agent.py`
- `app/services/summarizer/extractors.py`
- `app/services/summarizer/formatters.py`
- `app/services/summarizer/templates.py`

**Implementation Steps**:
1. Create directory structure
2. Extract core agent logic
3. Extract key point extractors
4. Extract formatters
5. Extract templates
6. Add backward-compatible imports
7. Verify tests pass

**Acceptance Criteria**:
- [ ] No file exceeds 400 lines
- [ ] All tests pass
- [ ] Single responsibility per file

---

### Task 170: Refactor document_analysis_agents.py
**Priority**: HIGH
**Effort**: 4 hours
**Dependencies**: None

**Objective**: Break 1,285 line file into modules

**Files to Create**:
- `app/services/analysis/__init__.py`
- `app/services/analysis/base.py`
- `app/services/analysis/research_analyst.py`
- `app/services/analysis/content_strategist.py`
- `app/services/analysis/fact_checker.py`

**Implementation Steps**:
1. Create directory structure
2. Extract base class
3. Extract each agent
4. Add backward-compatible imports
5. Verify tests pass

**Acceptance Criteria**:
- [ ] Each agent in own file
- [ ] Base class shared
- [ ] Tests pass

---

### Task 171: Refactor chunking_service.py
**Priority**: HIGH
**Effort**: 4 hours
**Dependencies**: None

**Objective**: Break 1,475 line file into modules

**Files to Create**:
- `app/services/chunking/__init__.py`
- `app/services/chunking/service.py`
- `app/services/chunking/strategies/base.py`
- `app/services/chunking/strategies/sentence.py`
- `app/services/chunking/strategies/markdown.py`
- `app/services/chunking/strategies/semantic.py`
- `app/services/chunking/validators.py`

**Implementation Steps**:
1. Create directory structure
2. Extract main service
3. Extract each strategy
4. Extract validators
5. Add backward-compatible imports
6. Verify tests pass

**Acceptance Criteria**:
- [ ] Each strategy in own file
- [ ] Service interface clean
- [ ] Tests pass

---

### Task 172: Add Unit Tests for RAG Enhancement Services
**Priority**: HIGH
**Effort**: 6 hours
**Dependencies**: None

**Objective**: Test new services from Tasks 141-150

**Files to Create**:
- `tests/unit/services/test_adaptive_retrieval_service.py`
- `tests/unit/services/test_agent_selector_service.py`
- `tests/unit/services/test_answer_grounding_evaluator.py`
- `tests/unit/services/test_quality_gate_service.py`
- `tests/unit/services/test_enhanced_rag_pipeline.py`
- `tests/unit/services/test_output_validator_service.py`

**Implementation Steps**:
1. Create test files for each service
2. Test core functionality
3. Test edge cases
4. Test error handling
5. Achieve >80% coverage per file

**Acceptance Criteria**:
- [ ] All 6 services tested
- [ ] Edge cases covered
- [ ] >80% coverage

---

### Task 173: Add Integration Tests for Neo4j and B2
**Priority**: HIGH
**Effort**: 6 hours
**Dependencies**: Tasks 156-158, 162-163

**Objective**: Test database and storage integrations

**Files to Create**:
- `tests/integration/neo4j/test_graph_sync.py`
- `tests/integration/neo4j/test_entity_queries.py`
- `tests/integration/b2/test_file_operations.py`

**Implementation Steps**:
1. Set up test fixtures for Neo4j
2. Create graph sync tests
3. Create entity query tests
4. Set up test fixtures for B2
5. Create file operation tests
6. Add cleanup for test data

**Acceptance Criteria**:
- [ ] Graph operations tested
- [ ] B2 operations tested
- [ ] Test data cleaned up

---

### Task 174: Add E2E Tests for Critical Flows
**Priority**: HIGH
**Effort**: 6 hours
**Dependencies**: Tasks 159-160

**Objective**: Test complete user workflows

**Files to Create**:
- `tests/e2e/test_document_flow.py`
- `tests/e2e/test_research_flow.py`
- `tests/e2e/test_auth_flow.py`

**Implementation Steps**:
1. Create document upload → process → query test
2. Create research project → execute → report test
3. Create auth flow test
4. Add fixtures for test data
5. Add cleanup

**Acceptance Criteria**:
- [ ] Document flow works E2E
- [ ] Research flow works E2E
- [ ] Auth flow verified

---

### Task 175: Add Security Tests
**Priority**: HIGH
**Effort**: 4 hours
**Dependencies**: Tasks 151-152

**Objective**: Verify security controls

**Files to Create**:
- `tests/security/test_rls_isolation.py`
- `tests/security/test_websocket_auth.py`
- `tests/security/test_input_validation.py`

**Implementation Steps**:
1. Create RLS isolation tests (cross-user access)
2. Create WebSocket auth tests
3. Create input validation tests
4. Test rate limiting
5. Test auth bypass attempts

**Acceptance Criteria**:
- [ ] RLS prevents cross-user access
- [ ] WebSocket rejects invalid tokens
- [ ] Input validation catches bad input

---

## Summary

### Task Count by Phase
| Phase | Tasks | Effort |
|-------|-------|--------|
| Phase 1: Security | 5 | 20 hours |
| Phase 2: Core | 6 | 34 hours |
| Phase 3: Infrastructure | 6 | 30 hours |
| Phase 4: Quality | 8 | 40 hours |
| **Total** | **25** | **124 hours** |

### Dependencies Graph
```
Phase 1 (Security):
  151 (RLS) ──────────────────────────┐
  152 (WebSocket) ────────────────────┤
  153 (Exceptions) ───┬───────────────┴──> Phase 2
  154 (Decorators) ───┘
  155 (Security Exceptions) ──────────────────────┘

Phase 2 (Core):
  156 (Graph Nodes) ──┬──> 158 (Relationships)
  157 (Entities) ─────┘
  159 (Reports)
  160 (LlamaIndex)
  161 (Core Exceptions)

Phase 3 (Infrastructure):
  162 (B2 Upload) ──> 163 (B2 Ops)
  164 (CrewAI)
  165 (Circuit Core) ──> 166 (Circuit Integration)
  167 (Remaining Exceptions)

Phase 4 (Quality):
  168-171 (Refactoring) - Parallel
  172-175 (Testing) - After refactoring
```

### Success Metrics
| Metric | Before | After |
|--------|--------|-------|
| Bare Exceptions | 48 | 0 |
| Files >1000 lines | 4 | 0 |
| Test Coverage | 45% | 75% |
| Security Score | 80 | 95 |
| Integration Score | 65 | 90 |
