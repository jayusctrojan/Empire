# Tasks: Content Prep Agent (AGENT-016)

**Input**: Design documents from `/specs/007-content-prep-agent/`
**Prerequisites**: prd.md (complete), architecture.md (complete)
**TaskMaster IDs**: 122-131 (mapped below)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US5)
- **[TM-XXX]**: Maps to TaskMaster task ID for tracking

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database schema and project structure

- [ ] T001 [P] [TM-123] Create database migration `migrations/create_content_sets.sql` with content_sets, content_set_files, AND processing_manifests tables
- [ ] T002 [P] [TM-123] Add Neo4j constraints for ContentSet nodes in migration
- [ ] T003 [P] Create Pydantic models in `app/models/content_sets.py` (ContentSet, ContentFile, ProcessingManifest)
- [ ] T004 Register Content Prep routes in `app/main.py`

---

## Phase 2: Foundational (Core Agent - TM-122)

**Purpose**: Core Content Prep Agent service that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

**📋 NOTE**: Implementation code exists in `architecture.md` (lines 116-625). Tasks below are "integrate from architecture" - copy, adapt, and wire up the existing code.

- [ ] T005 [TM-122] Copy ContentPrepAgent class from architecture.md to `app/services/content_prep_agent.py`
- [ ] T006 [TM-122] Integrate SEQUENCE_PATTERNS regex list from architecture.md (lines 138-148)
- [ ] T007 [TM-122] Integrate CONTENT_SET_INDICATORS patterns from architecture.md (lines 150-154)
- [ ] T008 [TM-122] Integrate `_extract_sequence()` method from architecture.md (lines 374-386)
- [ ] T009 [TM-122] Integrate `_extract_prefix()` method from architecture.md (lines 301-322)
- [ ] T010 [TM-122] Integrate `_detect_by_pattern()` method from architecture.md (lines 265-299)
- [ ] T011 [TM-122] Integrate CrewAI agent configuration from architecture.md (lines 202-212)
- [ ] T012 [TM-122] Integrate database storage methods from architecture.md (lines 528-600)

**Checkpoint**: Core agent ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Course Upload Ordering (Priority: P1) 🎯 MVP

**Goal**: System detects numbered modules and processes in correct chronological order

**Independent Test**: Upload 5 numbered course files in random order → verify processing order matches sequence

**Maps to**: TM-125 (Set Detection and Ordering Logic)

### Implementation for User Story 1

- [ ] T013 [US1] [TM-125] Implement `analyze_folder()` method in ContentPrepAgent
- [ ] T014 [US1] [TM-125] Implement `_create_content_set()` method to build ContentSet from grouped files
- [ ] T015 [US1] [TM-125] Implement chronological sorting by sequence_number in content sets
- [ ] T016 [US1] [TM-125] Implement gap detection logic to identify missing files in sequence
- [ ] T017 [US1] [TM-126] Implement `generate_manifest()` method to create ProcessingManifest
- [ ] T018 [US1] [TM-124] Create POST `/api/content-prep/analyze` endpoint in `app/routes/content_prep.py`
- [ ] T019 [US1] [TM-124] Create POST `/api/content-prep/manifest` endpoint
- [ ] T020 [US1] [TM-124] Create GET `/api/content-prep/sets` endpoint to list detected sets

**Checkpoint**: Course files can be uploaded and ordered chronologically

---

## Phase 4: User Story 2 - Completeness Warning (Priority: P1)

**Goal**: Warn users about incomplete content sets, require acknowledgment before proceeding

**Independent Test**: Upload files 1, 2, 4 (missing 3) → verify warning and blocking behavior

**Maps to**: TM-125 (gap detection), TM-124 (validate endpoint)

### Implementation for User Story 2

- [ ] T021 [US2] [TM-125] Enhance gap detection to populate `missing_files` list with descriptive names
- [ ] T022 [US2] [TM-124] Create POST `/api/content-prep/validate/{set_id}` endpoint
- [ ] T023 [US2] Implement `validate_completeness()` method returning is_complete and missing_files
- [ ] T024 [US2] Add `proceed_incomplete` flag to manifest generation requiring explicit acknowledgment
- [ ] T025 [US2] Add audit logging when user proceeds despite incomplete set

**Checkpoint**: Incomplete sets are detected and require user acknowledgment

---

## Phase 5: User Story 3 - Documentation Set Grouping (Priority: P2)

**Goal**: Group related documentation files by shared prefix/naming convention

**Independent Test**: Upload api-auth.md, api-users.md, api-orders.md → verify grouped as "api" set

### Implementation for User Story 3

- [ ] T026 [US3] Extend `_extract_prefix()` to handle documentation naming patterns
- [ ] T027 [US3] Add documentation-specific patterns to CONTENT_SET_INDICATORS
- [ ] T028 [US3] Implement cross-file reference validation (detect broken links)
- [ ] T029 [US3] Add "documentation" detection_method option

**Checkpoint**: Documentation files are automatically grouped and ordered

---

## Phase 6: User Story 4 - Standalone File Pass-Through (Priority: P1)

**Goal**: Single files bypass set detection and process immediately

**Independent Test**: Upload single PDF → verify <100ms overhead vs normal processing

### Implementation for User Story 4

- [ ] T030 [US4] Add early-exit in `analyze_folder()` for single-file uploads
- [ ] T031 [US4] Implement latency tracking to verify <100ms overhead (SC-004)
- [ ] T032 [US4] Add Prometheus metric for standalone file processing time

**Checkpoint**: Single files process immediately without ordering overhead

---

## Phase 7: User Story 5 - Chat-Based Ordering Clarification (Priority: P2)

**Goal**: Agent asks ordering questions via CKO Chat when confidence is low

**Independent Test**: Upload ambiguously named files → verify chat message sent, response parsed, ordering updated

**Maps to**: TM-129

### Implementation for User Story 5

- [ ] T033 [US5] [TM-129] Define ordering confidence threshold (80%)
- [ ] T034 [US5] [TM-129] Implement `_calculate_ordering_confidence()` method
- [ ] T035 [US5] [TM-129] Create CKO Chat message format for ordering clarification
- [ ] T036 [US5] [TM-129] Implement chat message sending to CKO interface
- [ ] T037 [US5] [TM-129] Implement response parsing for natural language ordering confirmation
- [ ] T038 [US5] [TM-129] Add conversation logging for audit trail
- [ ] T039 [US5] [TM-129] Add state management to pause processing while awaiting clarification

**Checkpoint**: Agent communicates with users via chat for ambiguous ordering

---

## Phase 8: B2 & Celery Integration (Priority: P1)

**Goal**: Hook into existing B2 workflow and Celery task processing

**Maps to**: TM-127, TM-128

### Implementation

- [ ] T040 [TM-127] Modify `app/services/b2_workflow.py` to trigger content prep on new uploads
- [ ] T041 [TM-127] Implement manifest-based file ordering in B2 workflow
- [ ] T042 [TM-128] Create Celery tasks in `app/tasks/content_prep_tasks.py`
- [ ] T043 [TM-128] Implement `analyze_folder_task` Celery task
- [ ] T044 [TM-128] Implement `process_manifest_task` Celery task
- [ ] T045 [TM-128] Modify `app/tasks/source_processing.py` to accept manifest context
- [ ] T046 [TM-128] Pass content_set metadata to chunking service for enhanced chunking

**Checkpoint**: Content prep fully integrated with B2 workflow and Celery

---

## Phase 9: Neo4j Knowledge Graph Integration (Priority: P2)

**Goal**: Create graph relationships for content sets and document sequences

### Implementation

- [ ] T047 Create ContentSet nodes in Neo4j when sets are detected
- [ ] T048 Create PART_OF relationships: (Document)-[:PART_OF]->(ContentSet)
- [ ] T049 Create PRECEDES relationships: (Document)-[:PRECEDES]->(Document)
- [ ] T050 Create DEPENDS_ON relationships based on manifest dependencies
- [ ] T051 Store sequence_number as property on Document nodes

**Checkpoint**: Knowledge graph reflects content set structure

---

## Phase 10: Retention & Cleanup (Priority: P3)

**Goal**: Implement 90-day retention policy for content set metadata

**Maps to**: TM-130

### Implementation

- [ ] T052 [TM-130] Create Celery beat task for daily cleanup in `app/tasks/content_prep_tasks.py`
- [ ] T053 [TM-130] Implement `cleanup_expired_content_sets()` function
- [ ] T054 [TM-130] Add completed_at timestamp tracking for retention calculation
- [ ] T055 [TM-130] Add Prometheus metric for cleanup operations

**Checkpoint**: Content set metadata automatically cleaned up after 90 days

---

## Phase 11: Polish & Testing

**Purpose**: Comprehensive testing and observability

**Maps to**: TM-131

### Tests

- [ ] T056 [TM-131] Create unit tests in `tests/test_content_prep_agent.py` for sequence detection
- [ ] T057 [TM-131] Create unit tests for gap detection logic
- [ ] T058 [TM-131] Create unit tests for content set grouping
- [ ] T059 [TM-131] Create integration tests for API endpoints
- [ ] T060 [TM-131] Create integration tests for B2 workflow hook
- [ ] T061 [TM-131] Add load tests for 100-file content sets (SC-007)
- [ ] T067 [TM-131] Add performance test for <5s analysis time on 50 files (SC-003)
- [ ] T068 [TM-131] Add LLM ordering accuracy validation test (SC-005: >90% agreement)

### Observability

- [ ] T062 Add Prometheus metrics for content_prep operations
- [ ] T063 Add structlog logging throughout ContentPrepAgent
- [ ] T064 Update agent registry in `app/services/crewai_service.py` with AGENT-016

### Documentation

- [ ] T065 Add API documentation for /api/content-prep endpoints
- [ ] T066 Update CLAUDE.md with Content Prep Agent section

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ─────────────────────────────────────┐
                                                      │
Phase 2 (Foundational) ◄──────────────────────────────┘
         │
         ├──► Phase 3 (US1: Course Ordering) ──► MVP!
         │
         ├──► Phase 4 (US2: Completeness Warning)
         │
         ├──► Phase 5 (US3: Doc Grouping)
         │
         ├──► Phase 6 (US4: Standalone Pass-Through)
         │
         └──► Phase 7 (US5: Chat Clarification)

Phase 8 (B2 Integration) ◄─── Depends on Phase 3, 4

Phase 9 (Neo4j) ◄─── Depends on Phase 3

Phase 10 (Retention) ◄─── Depends on Phase 1

Phase 11 (Testing) ◄─── Depends on all above
```

### TaskMaster ID Mapping

| TaskMaster ID | Tasks.md IDs | Description |
|---------------|--------------|-------------|
| TM-122 | T005-T012 | Core Agent Service |
| TM-123 | T001-T002 | Database Schema |
| TM-124 | T018-T020, T022 | API Routes |
| TM-125 | T013-T016, T021 | Set Detection & Ordering |
| TM-126 | T017 | Manifest Generation |
| TM-127 | T040-T041 | B2 Integration |
| TM-128 | T042-T046 | Celery Tasks |
| TM-129 | T033-T039 | Chat Clarification |
| TM-130 | T052-T055 | Retention Policy |
| TM-131 | T056-T061 | Test Suite |

---

## Implementation Strategy

### MVP First (User Stories 1 + 4)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T012)
3. Complete Phase 3: US1 Course Ordering (T013-T020)
4. Complete Phase 6: US4 Standalone Pass-Through (T030-T032)
5. **STOP and VALIDATE**: Test with real course files
6. Deploy to staging

### Full Feature Set

After MVP validated:
- Add Phase 4: US2 Completeness Warning
- Add Phase 8: B2 Integration
- Add Phase 7: US5 Chat Clarification
- Add Phase 9: Neo4j Integration
- Add Phase 10: Retention

---

## Notes

- Total tasks: 68
- MVP tasks: 24 (T001-T012, T013-T020, T030-T032)
- TaskMaster provides high-level tracking (10 tasks)
- This file provides granular subtasks for implementation
- Phase 2 tasks reference existing code in architecture.md - minimal implementation effort
