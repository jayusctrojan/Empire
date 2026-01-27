# Tasks: Chat Context Window Management

**Input**: Design documents from `/specs/011-chat-context-management/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/
**Branch**: `011-chat-context-management`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US6)
- File paths follow Empire structure: `app/` for backend, `empire-desktop/` for frontend

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database migrations and core module structure

- [ ] T001 Create database migration `migrations/20250119_001_create_conversation_contexts.sql`
- [ ] T002 [P] Create database migration `migrations/20250119_002_create_context_messages.sql`
- [ ] T003 [P] Create database migration `migrations/20250119_003_create_compaction_logs.sql`
- [ ] T004 [P] Create database migration `migrations/20250119_004_create_session_checkpoints.sql`
- [ ] T005 [P] Create database migration `migrations/20250119_005_create_session_memories.sql`
- [ ] T006 Create database migration `migrations/20250119_006_enable_rls_policies.sql`
- [ ] T007 Run all migrations and verify schema in Supabase

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T008 Create token counter module `app/core/token_counter.py` with tiktoken integration
- [ ] T009 [P] Create context Pydantic models `app/models/context_models.py`
- [ ] T010 [P] Create checkpoint Pydantic models `app/models/checkpoint_models.py`
- [ ] T011 [P] Create session Pydantic models `app/models/session_models.py`
- [ ] T012 Create context manager service base `app/services/context_manager_service.py` (skeleton)
- [ ] T013 [P] Create summarization service base `app/services/summarization_service.py` (skeleton)
- [ ] T014 [P] Create checkpoint service base `app/services/checkpoint_service.py` (skeleton)
- [ ] T015 [P] Create session resume service base `app/services/session_resume_service.py` (skeleton)
- [ ] T016 Add context routes to `app/routes/context_management.py` (extend existing)
- [ ] T017 [P] Create checkpoint routes `app/routes/checkpoints.py`
- [ ] T018 [P] Create session routes `app/routes/sessions.py`
- [ ] T019 Register new routers in `app/main.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Real-Time Context Window Visibility (Priority: P1) 🎯 MVP

**Goal**: Users can see context window usage with color-coded progress bar

**Independent Test**: Progress bar shows accurate token count, updates on message send

### Tests for User Story 1

- [ ] T020 [P] [US1] Unit test for token counter in `tests/unit/test_token_counter.py`
- [ ] T021 [P] [US1] Unit test for context manager service in `tests/unit/test_context_manager_service.py`
- [ ] T022 [P] [US1] Integration test for context API in `tests/integration/test_context_api.py`

### Implementation for User Story 1

- [ ] T023 [US1] Implement `count_tokens()` function in `app/core/token_counter.py`
- [ ] T024 [US1] Implement `count_message_tokens()` helper in `app/core/token_counter.py`
- [ ] T025 [US1] Implement `ContextWindowStatus` model in `app/models/context_models.py`
- [ ] T026 [US1] Implement `get_context_status()` in `app/services/context_manager_service.py`
- [ ] T027 [US1] Implement `add_message_to_context()` in `app/services/context_manager_service.py`
- [ ] T028 [US1] Implement GET `/context/{conversation_id}` endpoint in `app/routes/context_management.py`
- [ ] T029 [US1] Implement POST `/context/{conversation_id}/messages` endpoint in `app/routes/context_management.py`
- [ ] T030 [US1] Add Redis caching for context state (real-time updates)
- [ ] T031 [P] [US1] Create `ContextProgressBar.tsx` component in `empire-desktop/src/components/`
- [ ] T032 [US1] Create `useContextWindow.ts` hook in `empire-desktop/src/hooks/`
- [ ] T033 [US1] Integrate progress bar into chat UI with color-coded status (green/yellow/red)
- [ ] T034 [US1] Add tooltip with detailed token breakdown on hover
- [ ] T035 [US1] Add Prometheus metrics for token counting (`context_tokens_total`, `context_usage_percent`)

**Checkpoint**: User Story 1 complete - progress bar shows real-time token usage

---

## Phase 4: User Story 2 - Automatic Context Compaction (Priority: P1)

**Goal**: System automatically condenses conversation when approaching limits

**Independent Test**: Compaction triggers at 80%, runs in background, shows inline divider

### Tests for User Story 2

- [ ] T036 [P] [US2] Unit test for summarization service in `tests/unit/test_summarization_service.py`
- [ ] T037 [P] [US2] Integration test for compaction in `tests/integration/test_compaction_api.py`
- [ ] T038 [P] [US2] E2E test for compaction flow in `tests/e2e/test_compaction_flow.py`

### Implementation for User Story 2

- [ ] T039 [US2] Implement summarization prompt template in `app/services/summarization_service.py`
- [ ] T040 [US2] Implement `summarize_messages()` with Sonnet in `app/services/summarization_service.py`
- [ ] T041 [US2] Implement `summarize_messages_fast()` with Haiku in `app/services/summarization_service.py`
- [ ] T042 [US2] Create Celery task `compact_context` in `app/tasks/compaction_tasks.py`
- [ ] T043 [US2] Implement progress tracking in compaction task (Redis-based)
- [ ] T044 [US2] Implement `trigger_compaction()` in `app/services/context_manager_service.py`
- [ ] T045 [US2] Implement auto-compaction check in `add_message_to_context()` (80% threshold)
- [ ] T046 [US2] Implement compaction lock mechanism (prevent duplicate compaction)
- [ ] T047 [US2] Implement rate limiting for compaction (30-second cooldown)
- [ ] T048 [US2] Implement POST `/context/{conversation_id}/compact` endpoint
- [ ] T049 [US2] Implement GET `/context/{conversation_id}/compact/status` endpoint
- [ ] T050 [US2] Store compaction results in `compaction_logs` table
- [ ] T051 [P] [US2] Create `CompactionDivider.tsx` component in `empire-desktop/src/components/`
- [ ] T052 [US2] Add WebSocket events for compaction progress updates
- [ ] T053 [US2] Integrate "Condensing context..." indicator in chat UI
- [ ] T054 [US2] Add collapsible summary view to compaction divider
- [ ] T055 [US2] Add Prometheus metrics for compaction (`compaction_count`, `compaction_latency_seconds`, `compaction_reduction_percent`)

**Checkpoint**: User Story 2 complete - auto-compaction works with background processing

---

## Phase 5: User Story 3 - Crash Recovery & Checkpoints (Priority: P2)

**Goal**: Auto-checkpoints on important events, crash recovery on app restart

**Independent Test**: Checkpoint saved on code generation, recovery prompt on crash

### Tests for User Story 3

- [ ] T056 [P] [US3] Unit test for checkpoint service in `tests/unit/test_checkpoint_service.py`
- [ ] T057 [P] [US3] Integration test for checkpoint API in `tests/integration/test_checkpoint_api.py`

### Implementation for User Story 3

- [ ] T058 [US3] Implement `create_checkpoint()` in `app/services/checkpoint_service.py`
- [ ] T059 [US3] Implement `get_checkpoint()` in `app/services/checkpoint_service.py`
- [ ] T060 [US3] Implement `list_checkpoints()` in `app/services/checkpoint_service.py`
- [ ] T061 [US3] Implement `delete_checkpoint()` in `app/services/checkpoint_service.py`
- [ ] T062 [US3] Implement auto-checkpoint triggers (code generation detection)
- [ ] T063 [US3] Implement checkpoint limit enforcement (max 50 per conversation)
- [ ] T064 [US3] Implement checkpoint expiration (30-day TTL)
- [ ] T065 [US3] Implement POST `/checkpoints/{conversation_id}` endpoint (manual /save-progress)
- [ ] T066 [US3] Implement POST `/checkpoints/{conversation_id}/auto` endpoint (internal)
- [ ] T067 [US3] Implement GET `/checkpoints/{conversation_id}` endpoint (list)
- [ ] T068 [US3] Implement GET `/checkpoints/{conversation_id}/{checkpoint_id}` endpoint
- [ ] T069 [US3] Implement DELETE `/checkpoints/{conversation_id}/{checkpoint_id}` endpoint
- [ ] T070 [US3] Implement `check_recovery()` in `app/services/checkpoint_service.py`
- [ ] T071 [US3] Implement `restore_from_checkpoint()` in `app/services/checkpoint_service.py`
- [ ] T072 [US3] Implement GET `/recovery/check` endpoint
- [ ] T073 [US3] Implement POST `/recovery/{conversation_id}/restore` endpoint
- [ ] T074 [US3] Mark abnormal close checkpoints on session termination detection
- [ ] T075 [US3] Add recovery prompt UI in `empire-desktop/` on app launch
- [ ] T076 [US3] Add Prometheus metrics for checkpoints (`checkpoint_count`, `checkpoint_recovery_success`)

**Checkpoint**: User Story 3 complete - checkpoints save and crash recovery works

---

## Phase 6: User Story 4 - Session Resume (Priority: P2)

**Goal**: Session picker on launch, full context restoration from any checkpoint

**Independent Test**: Sessions listed on launch, resume restores full context

### Tests for User Story 4

- [ ] T077 [P] [US4] Unit test for session resume service in `tests/unit/test_session_resume_service.py`
- [ ] T078 [P] [US4] Integration test for session API in `tests/integration/test_session_api.py`

### Implementation for User Story 4

- [ ] T079 [US4] Implement `list_sessions()` in `app/services/session_resume_service.py`
- [ ] T080 [US4] Implement `get_session_detail()` in `app/services/session_resume_service.py`
- [ ] T081 [US4] Implement `resume_session()` in `app/services/session_resume_service.py`
- [ ] T082 [US4] Implement `get_session_memory()` in `app/services/session_resume_service.py`
- [ ] T083 [US4] Implement `update_session_memory()` in `app/services/session_resume_service.py`
- [ ] T084 [US4] Implement GET `/sessions` endpoint (list recent)
- [ ] T085 [US4] Implement GET `/sessions/{session_id}` endpoint
- [ ] T086 [US4] Implement POST `/sessions/{session_id}/resume` endpoint
- [ ] T087 [US4] Implement GET `/sessions/picker` endpoint (optimized for app launch)
- [ ] T088 [US4] Implement GET `/sessions/{session_id}/checkpoints/timeline` endpoint
- [ ] T089 [US4] Implement conflict detection (session updated elsewhere)
- [ ] T090 [US4] Implement POST `/sessions/{session_id}/refresh` endpoint
- [ ] T091 [P] [US4] Create `SessionPicker.tsx` component in `empire-desktop/src/components/`
- [ ] T092 [P] [US4] Create `CheckpointBrowser.tsx` component in `empire-desktop/src/components/`
- [ ] T093 [US4] Create `sessionApi.ts` client in `empire-desktop/src/services/`
- [ ] T094 [US4] Integrate session picker into app launch flow
- [ ] T095 [US4] Add "Browse Checkpoints" timeline view UI

**Checkpoint**: User Story 4 complete - session picker and resume work

---

## Phase 7: User Story 5 - Manual Compaction Control (Priority: P3)

**Goal**: /compact command with --force and --fast flags

**Independent Test**: /compact works with flags, displays metrics on completion

### Implementation for User Story 5

- [ ] T096 [US5] Implement `/compact` slash command handler
- [ ] T097 [US5] Implement `--force` flag (compact even below threshold)
- [ ] T098 [US5] Implement `--fast` flag (use Haiku model)
- [ ] T099 [US5] Add compaction metrics display after completion
- [ ] T100 [US5] Implement rate limit message (30-second cooldown)
- [ ] T101 [US5] Implement GET `/context/{conversation_id}/compact/history` endpoint

**Checkpoint**: User Story 5 complete - manual compaction control works

---

## Phase 8: User Story 6 - Protected Messages (Priority: P3)

**Goal**: Mark messages as protected, first message always preserved

**Independent Test**: Protected messages remain unchanged after compaction

### Implementation for User Story 6

- [ ] T102 [US6] Implement `toggle_message_protection()` in `app/services/context_manager_service.py`
- [ ] T103 [US6] Implement PATCH `/context/{conversation_id}/messages/{message_id}/protect` endpoint
- [ ] T104 [US6] Update summarization to skip protected messages
- [ ] T105 [US6] Ensure first message (system context) is always protected
- [ ] T106 [US6] Add lock icon UI for protected messages in chat
- [ ] T107 [US6] Add protection toggle action to message context menu

**Checkpoint**: User Story 6 complete - protected messages preserved

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Error handling, graceful degradation, documentation

- [ ] T108 Implement graceful degradation when Anthropic API unavailable (fallback to truncation)
- [ ] T109 [P] Add comprehensive error handling across all services
- [ ] T110 [P] Add structured logging with structlog for all operations
- [ ] T111 Implement data retention policies (project-based vs indefinite)
- [ ] T112 [P] Add concurrent access handling (last-write-wins with notification)
- [ ] T113 Add "session updated elsewhere" notification in desktop UI
- [ ] T114 [P] Run quickstart.md validation for all scenarios
- [ ] T115 [P] Update API documentation in `docs/`
- [ ] T116 Final Prometheus dashboard configuration for context management metrics

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - database migrations first
- **Phase 2 (Foundational)**: Depends on Phase 1 - BLOCKS all user stories
- **Phase 3-4 (US1, US2)**: P1 stories - implement in order (US1 → US2)
- **Phase 5-6 (US3, US4)**: P2 stories - can start after US1 complete
- **Phase 7-8 (US5, US6)**: P3 stories - can start after US2 complete
- **Phase 9 (Polish)**: Depends on all desired user stories

### User Story Dependencies

```
US1 (Token Visibility) ──┬──► US2 (Auto Compaction) ──┬──► US5 (Manual Controls)
                         │                            │
                         │                            └──► US6 (Protected Messages)
                         │
                         └──► US3 (Checkpoints) ────────► US4 (Session Resume)
```

- **US1** blocks **US2**: Token counting required for compaction trigger
- **US1** blocks **US3**: Token count needed for checkpoint metadata
- **US2** blocks **US5**: Compaction logic needed for /compact command
- **US2** blocks **US6**: Compaction logic needs protected message filtering
- **US3** blocks **US4**: Checkpoint storage needed for session resume

### Parallel Opportunities

- All migrations (T001-T006) marked [P] can run in parallel
- All Pydantic models (T009-T011) can run in parallel
- All service skeletons (T013-T015) can run in parallel
- All route files (T016-T018) can run in parallel
- Tests for each user story can run in parallel
- Frontend components within a story can run in parallel

---

## Implementation Strategy

### MVP First (P1 Stories Only)

1. Complete Phase 1: Setup (migrations)
2. Complete Phase 2: Foundational (models, services skeleton)
3. Complete Phase 3: User Story 1 (token visibility)
4. Complete Phase 4: User Story 2 (auto compaction)
5. **STOP and VALIDATE**: Test US1 + US2 independently
6. Deploy MVP with context management

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Test independently → Progress bar visible
3. Add US2 → Test independently → Auto-compaction works
4. Add US3 → Test independently → Checkpoints save
5. Add US4 → Test independently → Session resume works
6. Add US5 + US6 → Test independently → Power user features
7. Polish → Production ready

---

## Notes

- [P] tasks = different files, no dependencies
- [USn] label maps task to specific user story
- Background processing via Celery is critical for UX
- Sonnet model for quality (15-30s), Haiku for speed (5-10s)
- All endpoints require authentication (existing middleware)
- RLS policies enforce per-user data isolation
