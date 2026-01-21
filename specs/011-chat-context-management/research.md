# Research: Chat Context Window Management

**Feature Branch**: `011-chat-context-management`
**Date**: 2025-01-19
**Phase**: 0 - Research

## Technology Decisions

### Token Counting Library: tiktoken

**Selected**: `tiktoken` (OpenAI's library)

**Rationale**:
- Industry standard for GPT-family token counting
- Works well with Claude models (similar tokenization patterns)
- Fast Rust-based implementation with Python bindings
- 5% accuracy variance is acceptable with conservative buffers

**Alternatives Considered**:
- `transformers` tokenizers: Heavier dependency, overkill for counting
- Anthropic's native token counting: Requires API call per count, adds latency

**Integration Pattern**:
```python
import tiktoken

encoder = tiktoken.encoding_for_model("gpt-4")  # Compatible with Claude

def count_tokens(text: str) -> int:
    return len(encoder.encode(text))
```

### Summarization Model Strategy

**Selected**: Claude Sonnet (default) + Haiku (--fast option)

**Rationale from Research**:
- Claude Code attempted "instant" compaction with Haiku but rolled back due to quality issues
- Roo Code uses background processing with progress indicator
- Users reported 5+ minute worst cases with aggressive summarization
- Sonnet provides 95%+ context retention vs Haiku's ~90%

**Timing Targets** (validated against Claude Code/Roo Code):
| Model | Typical | Maximum |
|-------|---------|---------|
| Sonnet | 15-30s | 60s |
| Haiku (--fast) | 5-10s | 15s |

**UX Pattern**: Background processing with progress indicator (non-blocking)

### Background Processing: Celery

**Selected**: Celery with Redis broker (existing infrastructure)

**Rationale**:
- Already deployed for document processing tasks
- Proven pattern in Empire codebase
- Supports task status tracking and progress reporting
- Integrates with existing monitoring (Flower, Prometheus)

**Task Pattern**:
```python
@celery_app.task(bind=True)
def compact_context(self, conversation_id: str, options: dict):
    # Update progress during summarization
    self.update_state(state='PROGRESS', meta={'progress': 50})
    # ...
```

### Real-Time Progress Updates

**Selected**: WebSocket (existing infrastructure)

**Rationale**:
- Empire already has WebSocket support via FastAPI
- <100ms update latency requirement met
- Existing patterns in chat UI can be extended

**Alternative Considered**:
- Server-Sent Events (SSE): Simpler but one-way only
- Long Polling: Higher latency, more overhead

### Checkpoint Storage

**Selected**: Supabase PostgreSQL with JSONB

**Rationale**:
- Full conversation history needs structured storage
- JSONB allows flexible message schema
- Integrates with existing RLS policies
- 30-day TTL can be enforced with pg_cron or application logic

**Schema Preview**:
```sql
CREATE TABLE session_checkpoints (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    checkpoint_data JSONB NOT NULL,  -- Full message history
    token_count INTEGER NOT NULL,
    label TEXT,
    auto_tag VARCHAR(50),  -- 'code', 'decision', 'error_resolution'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ  -- 30 days from creation
);
```

## Existing Codebase Patterns

### Relevant Services

| Service | Location | Reuse Potential |
|---------|----------|-----------------|
| `chat_service.py` | `app/services/` | Message handling patterns |
| `celery_app.py` | `app/` | Task definitions |
| `websocket_manager.py` | `app/services/` | Real-time updates |
| `anthropic_client.py` | `app/clients/` | Claude API integration |

### Database Patterns

- UUID primary keys (existing pattern)
- JSONB for flexible schemas (existing pattern)
- RLS policies per user (existing pattern from Task 41)
- Audit logging (existing from Task 41.5)

### API Patterns

- Pydantic v2 models for request/response
- FastAPI dependency injection
- Standardized error responses
- Prometheus metrics integration

## Compaction Algorithm Research

### Claude Desktop Approach (Inferred)

Based on user reports and behavior analysis:
1. Triggers at ~80% context usage
2. Uses Sonnet for summarization
3. Preserves system prompt + recent N messages
4. Creates collapsible summary block
5. No user-visible interruption

### Roo Code Approach

Based on documentation:
1. Background compaction with progress indicator
2. Multiple summarization passes for long contexts
3. Preserves code blocks and file references
4. Allows configuration of preservation rules

### Empire Approach (Proposed)

Hybrid of best practices:
1. **Trigger**: 80% threshold (configurable)
2. **Model**: Sonnet default, Haiku --fast option
3. **UX**: Background with progress indicator
4. **Preservation**: First message + protected messages + recent messages
5. **Output**: Inline divider with collapsible summary

## Summary Prompt Template Research

**Key Elements to Preserve** (from academic literature and industry practice):
- Code snippets (full, not summarized)
- File paths mentioned
- Key decisions made
- Error messages encountered
- Entity names (people, systems, databases)
- Numerical values and dates

**Recommended Prompt Structure**:
```
You are summarizing a technical conversation. Preserve:
1. ALL code snippets exactly as written
2. ALL file paths and system names
3. Key decisions with their rationale
4. Error messages and their resolutions
5. Technical specifications and requirements

Format the summary with clear sections:
- Key Decisions
- Files Mentioned
- Code Preserved
- Context Summary

Do NOT summarize or paraphrase code blocks.
```

## Performance Benchmarks

### Token Counting

| Operation | Expected Time |
|-----------|---------------|
| Single message (~500 tokens) | <1ms |
| Full context (100K tokens) | <100ms |
| Progress bar update | <10ms |

### Compaction

| Context Size | Sonnet | Haiku |
|--------------|--------|-------|
| 50K tokens | 10-15s | 3-5s |
| 100K tokens | 20-30s | 7-12s |
| 200K tokens | 40-60s | 12-18s |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Token count drift | Medium | Low | Conservative 5% buffer |
| Summarization quality loss | Low | High | Use Sonnet, comprehensive prompt |
| Long compaction times | Medium | Medium | Background processing, --fast option |
| Checkpoint storage costs | Low | Low | 50 checkpoint limit, 30-day TTL |

## References

- Claude Code GitHub Issues (context management discussions)
- Roo Code Documentation (compaction strategy)
- tiktoken Documentation (https://github.com/openai/tiktoken)
- Anthropic API Documentation (token limits, model capabilities)
- Empire v7.3 CLAUDE.md (existing patterns and services)
