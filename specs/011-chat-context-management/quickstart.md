# Quickstart: Chat Context Window Management

**Feature Branch**: `011-chat-context-management`
**Date**: 2025-01-19
**Phase**: 1 - Quick Validation

## Overview

This document provides quick test scenarios to validate each phase of the implementation independently.

## Prerequisites

```bash
# Ensure services are running
docker-compose up -d  # Neo4j, Redis
uvicorn app.main:app --reload --port 8000
celery -A app.celery_app worker --loglevel=info

# Environment variables required
export ANTHROPIC_API_KEY=<your-key>
export SUPABASE_URL=<your-url>
export SUPABASE_SERVICE_KEY=<your-key>
export REDIS_URL=<your-redis-url>
```

## Phase 1: Token Counting & Progress Bar

### Backend Test

```bash
# Create a test conversation context
curl -X POST http://localhost:8000/api/v1/context \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "conversation_id": "test-123",
    "max_tokens": 200000,
    "threshold_percent": 80
  }'

# Add a message and check token count
curl -X POST http://localhost:8000/api/v1/context/test-123/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "role": "user",
    "content": "Hello, I need help with my Python project."
  }'

# Expected response:
# {
#   "message_id": "msg-456",
#   "token_count": 12,
#   "context_status": {
#     "total_tokens": 12,
#     "max_tokens": 200000,
#     "used_percent": 0.006,
#     "status": "normal"
#   }
# }

# Get current context status
curl http://localhost:8000/api/v1/context/test-123 \
  -H "Authorization: Bearer <token>"
```

### Frontend Test

1. Open the chat interface in the desktop app
2. Verify the progress bar is visible at the top of the chat
3. Send a message and observe the progress bar update within 100ms
4. Verify color changes:
   - Green when < 70%
   - Yellow when 70-85%
   - Red when > 85%
5. Hover over progress bar to see tooltip with detailed breakdown

### Unit Test

```bash
pytest tests/unit/test_token_counter.py -v
pytest tests/unit/test_context_manager_service.py -v
```

## Phase 2: Automatic Compaction

### Backend Test

```bash
# Simulate high token usage (mock or real)
# This should trigger automatic compaction

# Check compaction status
curl http://localhost:8000/api/v1/context/test-123/compact/status \
  -H "Authorization: Bearer <token>"

# Expected during compaction:
# {
#   "status": "in_progress",
#   "progress": 45,
#   "stage": "summarizing",
#   "started_at": "2025-01-19T12:00:00Z"
# }

# Expected after compaction:
# {
#   "status": "completed",
#   "result": {
#     "pre_tokens": 160000,
#     "post_tokens": 48000,
#     "reduction_percent": 70.0,
#     "duration_ms": 23450
#   }
# }
```

### Manual Compaction Test

```bash
# Trigger manual compaction
curl -X POST http://localhost:8000/api/v1/context/test-123/compact \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"force": true}'

# Test --fast flag (Haiku model)
curl -X POST http://localhost:8000/api/v1/context/test-123/compact \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"force": true, "fast": true}'
```

### Frontend Test

1. Use a conversation until it reaches ~80% capacity
2. Verify "Condensing context..." indicator appears
3. Verify you can continue reading/composing while compaction runs
4. After completion, verify inline divider appears showing before/after counts
5. Click the divider to expand and see summary details

### Timing Validation

- Sonnet: Should complete in 15-30 seconds (60s max)
- Haiku (--fast): Should complete in 5-10 seconds (15s max)

## Phase 3: Checkpoints

### Backend Test

```bash
# Create manual checkpoint (/save-progress)
curl -X POST http://localhost:8000/api/v1/checkpoints/test-123 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"label": "completed auth feature"}'

# Expected response:
# {
#   "id": "checkpoint-789",
#   "label": "completed auth feature",
#   "token_count": 45000,
#   "created_at": "2025-01-19T12:00:00Z"
# }

# List checkpoints
curl http://localhost:8000/api/v1/checkpoints/test-123 \
  -H "Authorization: Bearer <token>"

# Check for crash recovery
curl http://localhost:8000/api/v1/recovery/check \
  -H "Authorization: Bearer <token>"
```

### Auto-Checkpoint Test

1. In a conversation, generate code (write to file)
2. Verify checkpoint is created within 2 seconds
3. Check checkpoint has `auto_tag: "code"`

### Crash Recovery Test

1. Start a conversation and make progress
2. Force-quit the app (simulate crash)
3. Reopen the app
4. Verify recovery prompt appears with checkpoint info
5. Click "Resume from checkpoint"
6. Verify full context is restored

## Phase 4: Session Resume

### Backend Test

```bash
# Get session picker data
curl http://localhost:8000/api/v1/sessions/picker \
  -H "Authorization: Bearer <token>"

# Resume a session
curl -X POST http://localhost:8000/api/v1/sessions/session-123/resume \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{}'

# Resume from specific checkpoint
curl -X POST http://localhost:8000/api/v1/sessions/session-123/resume \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"checkpoint_id": "checkpoint-789"}'
```

### Frontend Test

1. Close the app normally
2. Reopen the app
3. Verify session picker appears showing recent sessions
4. Verify each session shows: title, preview, timestamp, checkpoint count
5. Click "Resume Latest" on a session
6. Verify conversation loads with full context
7. Click "Browse Checkpoints" to see timeline view
8. Select a specific checkpoint and resume from it

## Phase 5: Manual Controls

### /compact Command Test

```bash
# Via chat interface, type:
/compact

# Expected: Compaction triggers with progress indicator

# With --force flag:
/compact --force

# Expected: Compaction runs even if below threshold

# With --fast flag:
/compact --fast

# Expected: Uses Haiku model, completes in 5-10 seconds

# Rate limit test:
/compact
# Wait < 30 seconds
/compact

# Expected: "Please wait 30 seconds before compacting again"
```

### /save-progress Command Test

```bash
# Via chat interface, type:
/save-progress "completed user auth"

# Expected:
# "Checkpoint saved: completed user auth (ID: checkpoint-xxx)"
```

### Protected Messages Test

1. Mark a message as protected (click lock icon)
2. Verify lock icon appears on the message
3. Trigger compaction
4. Verify protected message remains unchanged in full
5. Verify first message (system context) is always preserved

## Integration Test Suite

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run specific test file
pytest tests/integration/test_context_api.py -v
pytest tests/integration/test_checkpoint_api.py -v
pytest tests/integration/test_session_api.py -v

# Run e2e compaction flow
pytest tests/e2e/test_compaction_flow.py -v
```

## Performance Benchmarks

```bash
# Run performance tests
pytest tests/performance/ -v --benchmark

# Expected results:
# - Token counting: < 100ms for 200K tokens
# - Progress bar update: < 10ms
# - Context status API: < 50ms response time
# - Checkpoint creation: < 2 seconds
```

## Success Criteria Checklist

| Criteria | Test | Pass |
|----------|------|------|
| SC-001: Seamless continuation | Continue chat after compaction | [ ] |
| SC-002: 90% info preservation | Review summary quality | [ ] |
| SC-003: 5% token accuracy | Compare counts | [ ] |
| SC-004: Sonnet 15-30s / Haiku 5-10s | Time compaction | [ ] |
| SC-005: 30-day checkpoint resume | Test old checkpoint | [ ] |
| SC-006: 100ms progress update | Measure UI latency | [ ] |
| SC-007: 95% crash recovery | Simulate crashes | [ ] |
| SC-009: 200K token handling | Large conversation | [ ] |
| SC-010: 2s auto-checkpoint | Time checkpoint creation | [ ] |

## Troubleshooting

### Compaction Not Triggering

1. Check token count is actually above threshold
2. Verify Celery worker is running
3. Check Redis connection
4. Review logs: `docker logs celery-worker`

### Token Count Mismatch

1. tiktoken and Anthropic may differ by ~5%
2. Conservative buffers should handle this
3. Check encoding model: should use `cl100k_base`

### Checkpoint Not Saving

1. Verify Supabase connection
2. Check RLS policies allow insert
3. Verify checkpoint limit (max 50) not reached

### Session Resume Fails

1. Check checkpoint hasn't expired (30-day TTL)
2. Verify checkpoint_data JSONB is valid
3. Check for conflict (session updated elsewhere)
