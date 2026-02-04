# Implementation Analysis: Chat Context Window Management

**Feature Branch**: `011-chat-context-management`
**Date**: 2025-01-19
**Phase**: Analysis

## Executive Summary

The implementation plan is well-structured with 116 granular tasks organized by user story. TaskMaster has 10 high-level tasks (201-210) with 43 subtasks expanded. This analysis identifies gaps, risks, and recommendations for successful implementation.

## Task Coverage Analysis

### TaskMaster Tasks vs Speckit Tasks Mapping

| TaskMaster ID | Title | Speckit Phase | Coverage |
|---------------|-------|---------------|----------|
| 201 | Token Counting Service | Phase 2-3 (T008, T023-T030) | ✅ Well covered (7 subtasks) |
| 202 | Context Window Progress Bar | Phase 3 (T031-T035) | ✅ Well covered (7 subtasks) |
| 203 | Intelligent Condensation | Phase 4 (T039-T055) | ✅ Well covered (10 subtasks) |
| 204 | Inline Compaction Summary | Phase 4 (T051-T054) | ⚠️ Needs expansion |
| 205 | Protected Messages | Phase 8 (T102-T107) | ⚠️ Needs expansion |
| 206 | Automatic Checkpoints | Phase 5 (T058-T076) | ✅ Well covered (10 subtasks) |
| 207 | Session Memory | Phase 6 (T079-T083) | ⚠️ Needs expansion |
| 208 | Session Resume UI | Phase 6 (T084-T095) | ✅ Well covered (9 subtasks) |
| 209 | Compact Command | Phase 7 (T096-T101) | ⚠️ Needs expansion |
| 210 | Error Recovery | Phase 9 (T108-T116) | ⚠️ Needs expansion |

### Gaps Identified

**1. Database Migrations Missing from TaskMaster**

Speckit tasks.md has explicit migration tasks (T001-T007) but TaskMaster doesn't have a dedicated task for this. These are foundational blockers.

**Recommendation**: Add a new task or subtask for database schema setup:
- `create_conversation_contexts` table
- `context_messages` table
- `compaction_logs` table
- `session_checkpoints` table
- `session_memories` table
- RLS policies

**2. Pydantic Models Not Explicit in TaskMaster**

Speckit tasks.md has explicit model tasks (T009-T011) but these are implicit in TaskMaster subtasks.

**Recommendation**: Ensure task 201 subtasks include explicit Pydantic model creation.

**3. Route Registration Missing**

T019 (Register new routers in app/main.py) is a critical integration task not explicitly in TaskMaster.

**Recommendation**: Add to task 201 or 202 as a subtask.

**4. WebSocket Events for Real-time Updates**

T052 (WebSocket events for compaction progress) is critical for UX but may be implicit.

**Recommendation**: Ensure task 203 subtasks include WebSocket integration.

## Dependency Analysis

### Critical Path

```
Database Migrations (blocking)
       ↓
Token Counter (Task 201) ─────────────────────┐
       ↓                                       │
Progress Bar (Task 202) ──────────────────────┤
       ↓                                       │
Auto Compaction (Task 203) ───────────────────┤
       ↓                                       │
Protected Messages (Task 205) ────────────────┤
       ↓                                       │
Checkpoints (Task 206) ───────────────────────┤
       ↓                                       │
Session Memory (Task 207) ────────────────────┤
       ↓                                       │
Session Resume UI (Task 208) ─────────────────┘
```

### Bottlenecks

1. **Task 201 (Token Counting)** blocks Tasks 202 and 203
2. **Task 203 (Compaction)** blocks Tasks 204, 205, 206, 209, 210
3. **Task 206 (Checkpoints)** blocks Tasks 207, 208, 210

### Parallel Opportunities

- Tasks 204 (Inline Summary) and 205 (Protected Messages) can start after 203
- Frontend components (Progress Bar, Compaction Divider, Session Picker) can be built in parallel with backend work with mocked data

## Risk Assessment

### High Risk Items

| Risk | Impact | Mitigation |
|------|--------|------------|
| Summarization quality insufficient | Users lose important context | Test with diverse conversation types, tune prompt |
| Compaction takes too long | Poor UX, user frustration | Background processing, --fast option with Haiku |
| Token count drift | Unexpected compaction triggers | 5% buffer, conservative thresholds |
| Checkpoint storage costs | Increased Supabase costs | 50 checkpoint limit, 30-day TTL |

### Medium Risk Items

| Risk | Impact | Mitigation |
|------|--------|------------|
| WebSocket connection issues | Progress bar doesn't update | Polling fallback |
| Celery worker failures | Compaction doesn't complete | Task retries, dead letter queue |
| Session conflicts | Data inconsistency | Last-write-wins, conflict notification |

## Recommended Task Modifications

### 1. Add Database Setup Task

Create a new task before 201:
```
Task 200: Database Schema Setup
- Create all migration files
- Run migrations on Supabase
- Verify RLS policies
- Dependencies: None
- Blocks: 201, 206, 207
```

### 2. Expand Task 204 (Inline Compaction Summary)

Add subtasks:
- Create CompactionDivider.tsx component
- Implement collapsible summary view
- Add before/after token count display
- Integrate with chat message list

### 3. Expand Task 205 (Protected Messages)

Add subtasks:
- Implement toggle_message_protection() service method
- Create PATCH endpoint for protection toggle
- Update summarization to filter protected messages
- Ensure first message auto-protection
- Add lock icon UI component
- Add protection toggle to message context menu

### 4. Expand Task 207 (Session Memory)

Add subtasks:
- Implement session memory Pydantic models
- Create CRUD methods in session_resume_service
- Implement memory endpoints
- Handle retention policies (project vs indefinite)

### 5. Expand Task 209 (Compact Command)

Add subtasks:
- Create slash command parser for /compact
- Implement --force flag logic
- Implement --fast flag (Haiku selection)
- Add rate limit enforcement
- Create metrics display UI

### 6. Expand Task 210 (Error Recovery)

Add subtasks:
- Implement graceful degradation (fallback to truncation)
- Add structured logging for all operations
- Implement concurrent access handling
- Create "session updated elsewhere" notification
- Configure Prometheus dashboards

## Testing Strategy Recommendations

### Unit Tests (Required)

- `tests/unit/test_token_counter.py` - Token counting accuracy
- `tests/unit/test_summarization_service.py` - Summarization prompt effectiveness
- `tests/unit/test_checkpoint_service.py` - Checkpoint CRUD operations
- `tests/unit/test_context_manager_service.py` - Context management logic

### Integration Tests (Required)

- `tests/integration/test_context_api.py` - Full context API flow
- `tests/integration/test_compaction_api.py` - Compaction endpoint integration
- `tests/integration/test_checkpoint_api.py` - Checkpoint API flow
- `tests/integration/test_session_api.py` - Session resume flow

### E2E Tests (Recommended)

- `tests/e2e/test_compaction_flow.py` - Full compaction user journey
- `tests/e2e/test_crash_recovery.py` - Crash and recovery simulation

### Performance Tests (Recommended)

- Token counting: < 100ms for 200K tokens
- Compaction: 15-30s (Sonnet), 5-10s (Haiku)
- Progress bar update: < 100ms
- Checkpoint creation: < 2s

## Implementation Order Recommendation

### Week 1: Foundation (MVP Prep)

1. ✅ Task 201: Token Counting Service (with subtasks)
2. ✅ Task 202: Context Window Progress Bar (with subtasks)

### Week 2: Core Compaction (MVP Complete)

3. ✅ Task 203: Intelligent Condensation (with subtasks)
4. Task 204: Inline Compaction Summary (expand and implement)

### Week 3: Checkpoints

5. ✅ Task 206: Automatic Checkpoints (with subtasks)
6. Task 205: Protected Messages (expand and implement)

### Week 4: Session Resume

7. Task 207: Session Memory (expand and implement)
8. ✅ Task 208: Session Resume UI (with subtasks)

### Week 5: Power Features & Polish

9. Task 209: Compact Command (expand and implement)
10. Task 210: Error Recovery (expand and implement)

## Conclusion

The implementation plan is comprehensive with good task breakdown. Key recommendations:

1. **Add database migration task** as Task 200 (critical blocker)
2. **Expand tasks 204, 205, 207, 209, 210** with detailed subtasks
3. **Focus on MVP first**: Tasks 201-204 for core context management
4. **Test early**: Write unit tests before implementation
5. **Monitor timing**: Ensure compaction meets 15-30s target

The expanded TaskMaster tasks (201, 202, 203, 206, 208) are well-structured with 43 subtasks providing clear implementation guidance.
