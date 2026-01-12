# Tasks: Markdown-Aware Document Splitting

**Input**: Design documents from `/specs/006-markdown-chunking/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md, data-model.md, contracts/

**Tests**: Unit tests included for core chunking logic (per spec FR-009 observability requirement)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `app/` at repository root (FastAPI structure)
- **Tests**: `tests/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and data structures

- [ ] T001 Create MarkdownSection dataclass in app/services/chunking_service.py
- [ ] T002 Create MarkdownChunkerConfig dataclass in app/services/chunking_service.py
- [ ] T003 [P] Add header detection regex constant: `HEADER_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core chunking infrastructure that MUST be complete before user story implementation

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Create MarkdownChunkerStrategy class skeleton in app/services/chunking_service.py implementing ChunkingStrategy interface
- [ ] T005 Implement `_count_tokens()` method using tiktoken in app/services/chunking_service.py
- [ ] T006 Implement `is_markdown_content()` method with min_headers threshold check in app/services/chunking_service.py
- [ ] T007 [P] Create test file tests/unit/test_markdown_chunking.py with test fixtures for markdown documents

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Query Returns Contextually Complete Answers (Priority: P1) 🎯 MVP

**Goal**: Split markdown documents by headers so retrieved chunks contain complete sections with context

**Independent Test**: Upload a structured PDF, query for a topic within a section, verify chunk starts with the relevant header

### Tests for User Story 1

- [ ] T008 [P] [US1] Unit test for header detection in tests/unit/test_markdown_chunking.py
- [ ] T009 [P] [US1] Unit test for section extraction with various header levels in tests/unit/test_markdown_chunking.py
- [ ] T010 [P] [US1] Unit test for header hierarchy building in tests/unit/test_markdown_chunking.py

### Implementation for User Story 1

- [ ] T011 [US1] Implement `_split_by_headers()` method to extract MarkdownSection objects in app/services/chunking_service.py
- [ ] T012 [US1] Implement `_build_header_hierarchy()` method to create parent header chain in app/services/chunking_service.py
- [ ] T013 [US1] Implement `chunk()` method for header-based splitting in app/services/chunking_service.py
- [ ] T014 [US1] Add section_header and header_level to chunk metadata in app/services/chunking_service.py
- [ ] T015 [US1] Add header_hierarchy dict to chunk metadata in app/services/chunking_service.py
- [ ] T016 [US1] Add logging for chunking strategy used and chunk statistics (FR-009) in app/services/chunking_service.py

**Checkpoint**: User Story 1 complete - documents split by headers with hierarchy metadata

---

## Phase 4: User Story 2 - Documents Without Headers Are Still Processed (Priority: P2)

**Goal**: Ensure backward compatibility - documents without headers fall back to sentence-based chunking

**Independent Test**: Upload a plain text document with no headers, verify it chunks successfully using existing strategy

### Tests for User Story 2

- [ ] T017 [P] [US2] Unit test for markdown detection with no headers (fallback case) in tests/unit/test_markdown_chunking.py
- [ ] T018 [P] [US2] Unit test for malformed headers treated as regular text in tests/unit/test_markdown_chunking.py

### Implementation for User Story 2

- [ ] T019 [US2] Add fallback to SentenceSplitter when is_markdown_content() returns False in app/services/chunking_service.py
- [ ] T020 [US2] Add is_markdown_content() detection in document_processor.py in app/services/document_processor.py
- [ ] T021 [US2] Update source_processing.py to route LlamaParse output through markdown detection in app/tasks/source_processing.py
- [ ] T022 [US2] Add integration test for non-markdown document processing in tests/unit/test_markdown_chunking.py

**Checkpoint**: User Story 2 complete - backward compatibility verified

---

## Phase 5: User Story 3 - Large Sections Are Properly Subdivided (Priority: P2)

**Goal**: Subdivide sections exceeding 1024 tokens while preserving header context in metadata

**Independent Test**: Upload a document with a 5000+ token section, verify multiple chunks each retain section header in metadata

### Tests for User Story 3

- [ ] T023 [P] [US3] Unit test for large section detection (>1024 tokens) in tests/unit/test_markdown_chunking.py
- [ ] T024 [P] [US3] Unit test for sentence-split fallback with header metadata preservation in tests/unit/test_markdown_chunking.py
- [ ] T025 [P] [US3] Unit test for chunk_index and total_section_chunks metadata in tests/unit/test_markdown_chunking.py

### Implementation for User Story 3

- [ ] T026 [US3] Implement `_chunk_oversized_section()` method using SentenceSplitter in app/services/chunking_service.py
- [ ] T027 [US3] Add is_header_split boolean to chunk metadata in app/services/chunking_service.py
- [ ] T028 [US3] Add chunk_index and total_section_chunks to metadata for subdivided sections in app/services/chunking_service.py
- [ ] T029 [US3] Implement chunk_overlap (200 tokens) for sentence-split sections in app/services/chunking_service.py

**Checkpoint**: User Story 3 complete - large sections properly subdivided

---

## Phase 6: User Story 4 - Header Metadata Enables Filtered Search (Priority: P3)

**Goal**: Allow filtering queries by section type using header metadata

**Independent Test**: Query with a section filter, verify only chunks from matching sections are returned

### Tests for User Story 4

- [ ] T030 [P] [US4] Unit test for header_level filtering in tests/unit/test_markdown_chunking.py
- [ ] T031 [P] [US4] Unit test for section_header text matching in tests/unit/test_markdown_chunking.py

### Implementation for User Story 4

- [ ] T032 [US4] Ensure all metadata fields are properly indexed for filtering in app/services/chunking_service.py
- [ ] T033 [US4] Add documentation for metadata-based filtering in quickstart.md in specs/006-markdown-chunking/quickstart.md

**Checkpoint**: User Story 4 complete - filtered search by header enabled

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T034 [P] Run all unit tests and verify 100% pass rate
- [ ] T035 [P] Add performance benchmark comparing markdown vs sentence chunking
- [ ] T036 Code cleanup and refactoring in app/services/chunking_service.py
- [ ] T037 [P] Update CLAUDE.md with 006-markdown-chunking technology stack
- [ ] T038 Run quickstart.md validation with sample documents
- [ ] T039 Verify SC-001: 80% chunks start with header (test corpus analysis)
- [ ] T040 Verify SC-004: <10% performance overhead (benchmark comparison)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - US1 (P1) must complete before US2-US4 for integration
  - US2 and US3 (both P2) can proceed in parallel after US1
  - US4 (P3) depends on US1-US3 metadata being in place
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - Core chunking logic
- **User Story 2 (P2)**: Depends on US1 - Adds fallback behavior
- **User Story 3 (P2)**: Depends on US1 - Adds oversized section handling
- **User Story 4 (P3)**: Depends on US1-US3 - Uses metadata for filtering

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Metadata tasks after core logic tasks
- Integration tasks (document_processor, source_processing) after core chunking

### Parallel Opportunities

- All Setup tasks (T001-T003) can run in parallel
- T007 (test fixtures) can run parallel with T004-T006
- All tests for a user story marked [P] can run in parallel
- US2 and US3 can run in parallel (both P2, different concerns)

---

## Parallel Example: Phase 3 (User Story 1)

```bash
# Launch all tests for User Story 1 together:
Task: "Unit test for header detection in tests/unit/test_markdown_chunking.py"
Task: "Unit test for section extraction in tests/unit/test_markdown_chunking.py"
Task: "Unit test for header hierarchy building in tests/unit/test_markdown_chunking.py"

# Then sequential implementation (dependencies between tasks):
Task: "Implement _split_by_headers() method"
Task: "Implement _build_header_hierarchy() method"
Task: "Implement chunk() method"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T007)
3. Complete Phase 3: User Story 1 (T008-T016)
4. **STOP and VALIDATE**: Test header-based splitting independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → **MVP!** (header-aware chunking works)
3. Add User Story 2 → Test independently → Backward compatibility
4. Add User Story 3 → Test independently → Large section handling
5. Add User Story 4 → Test independently → Filtered search
6. Each story adds value without breaking previous stories

### Files Modified Summary

| File | Tasks | Purpose |
|------|-------|---------|
| `app/services/chunking_service.py` | T001-T006, T011-T016, T019, T026-T029, T032, T036 | Core chunking implementation |
| `app/services/document_processor.py` | T020 | Markdown detection |
| `app/tasks/source_processing.py` | T021 | LlamaParse integration |
| `tests/unit/test_markdown_chunking.py` | T007-T010, T017-T018, T022-T025, T030-T031, T034 | Unit tests |
| `specs/006-markdown-chunking/quickstart.md` | T033, T38 | Documentation |

---

## Summary

- **Total Tasks**: 40
- **User Story 1 (P1 MVP)**: 9 tasks (T008-T016)
- **User Story 2 (P2)**: 6 tasks (T017-T022)
- **User Story 3 (P2)**: 7 tasks (T023-T029)
- **User Story 4 (P3)**: 4 tasks (T030-T033)
- **Setup/Foundational**: 7 tasks (T001-T007)
- **Polish**: 7 tasks (T034-T040)

**MVP Scope**: Complete through Phase 3 (User Story 1) = 16 tasks for working header-aware chunking

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
