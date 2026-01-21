# Chat Context Window Management System - PRD

**Version:** 1.0
**Date:** 2025-01-19
**Author:** Empire Development Team
**Status:** Draft

---

## Executive Summary

Empire v7.3 needs an intelligent chat context window management system that prevents important information loss during long conversations while maintaining efficient token usage. This system will implement automatic summarization, context condensing, and session memory management similar to Claude Code's approach.

---

## Problem Statement

### Current Issues

1. **Context Window Overflow**: Long conversations hit token limits, causing abrupt truncation of older messages
2. **Lost Context**: Important decisions, code snippets, and context from early conversation are lost
3. **No Summarization**: No intelligent summarization strategy to preserve key information
4. **Session Discontinuity**: No persistence of context across sessions or conversation restarts
5. **Manual Intervention Required**: Users must manually manage context by clearing or restarting
6. **No Visibility**: Users have no visibility into token usage or context window status

### Impact

- Poor user experience during long development sessions
- Lost productivity from re-explaining context
- Inconsistent AI responses due to missing historical context
- No way to maintain project-level memory across sessions

---

## Goals & Objectives

### Primary Goals

1. **Prevent Data Loss**: Ensure critical context is never lost during long conversations
2. **Automatic Management**: Intelligently manage context without user intervention
3. **Efficient Token Usage**: Optimize token usage through smart summarization
4. **Session Continuity**: Enable context persistence across sessions

### Success Metrics

| Metric | Target |
|--------|--------|
| Context preservation accuracy | >90% of key decisions/code retained |
| Auto-compaction latency | <3 seconds |
| Token reduction rate | 60-75% reduction per compaction |
| Session resume success rate | >95% |
| User satisfaction (context quality) | >4.5/5 rating |

---

## Functional Requirements

### FR-001: Intelligent Context Condensing

**Description**: Automatically summarize older parts of conversation while preserving essential information.

**Requirements**:
- Condense conversation history when token usage exceeds configurable threshold (default: 80%)
- Preserve key information: decisions, code snippets, error messages, file paths, task outcomes
- Use AI-powered summarization with customizable prompts
- Support both automatic and manual triggering
- Track pre/post token counts and display metrics

**Acceptance Criteria**:
- [ ] Summarization reduces tokens by 60-75% while retaining key information
- [ ] Automatic trigger activates at configured threshold
- [ ] Manual "/compact" command available
- [ ] Summarization completes in <3 seconds

### FR-002: Token Counting & Visibility

**Description**: Accurate token counting with user-visible progress indicators.

**Requirements**:
- Real-time token counting for conversation history
- Visual progress bar showing context window usage
- Display current usage, reserved output space, and available space
- Support for different content types (text, images, code blocks)
- Show token breakdown by message category

**Acceptance Criteria**:
- [ ] Token count accurate within 5% of actual API usage
- [ ] Progress bar updates in real-time
- [ ] Clear indication when approaching limits (warning at 70%, critical at 90%)

### FR-003: First Message Preservation

**Description**: Always preserve the initial system context and setup instructions.

**Requirements**:
- Mark first message and system prompts as "protected"
- Never condense protected messages
- Support user-defined protected message ranges
- Include initial slash commands and configuration in protected set

**Acceptance Criteria**:
- [ ] Initial context never summarized
- [ ] User can mark additional messages as protected
- [ ] Protected messages clearly indicated in UI

### FR-004: Automatic Error Recovery

**Description**: Gracefully handle context window overflow errors.

**Requirements**:
- Detect context window errors from API responses
- Automatically trigger context reduction (25% per attempt)
- Retry failed requests up to 3 times
- Preserve conversation state during recovery
- Log all recovery attempts for debugging

**Acceptance Criteria**:
- [ ] Automatic recovery handles 95%+ of overflow errors
- [ ] User notified of recovery actions
- [ ] No data loss during recovery process

### FR-005: Session Memory & Persistence

**Description**: Store and retrieve context across sessions for continuity.

**Requirements**:
- Save conversation summaries to Supabase
- Store per-project context memory
- Load relevant memories on session start
- Support session resume with full context restoration
- Intelligent memory selection based on current project/topic

**Acceptance Criteria**:
- [ ] Session can be resumed within 30 days
- [ ] Project-specific memories loaded automatically
- [ ] Memory retrieval adds <500ms to session start

### FR-006: Custom Condensing Prompts

**Description**: Allow customization of the summarization strategy.

**Requirements**:
- Default condensing prompt optimized for development context
- User-configurable prompt templates
- Domain-specific presets (debugging, code review, architecture, etc.)
- Prompt must instruct AI to preserve: code, errors, decisions, file paths

**Acceptance Criteria**:
- [ ] Default prompt preserves 90%+ of technical context
- [ ] Custom prompts can be saved and reused
- [ ] Presets available for common development tasks

### FR-007: Compact Command & API

**Description**: Manual control over context condensing.

**Requirements**:
- `/compact` command for manual trigger
- `/compact --force` to condense below threshold
- API endpoint for programmatic access
- Return metrics: pre_tokens, post_tokens, summary_preview
- Cooldown period to prevent rapid successive compactions

**Acceptance Criteria**:
- [ ] Command executes in <3 seconds
- [ ] Metrics returned include token counts
- [ ] Rate limited to 1 compaction per 30 seconds

### FR-008: Context Window Configuration

**Description**: Configurable context window management settings.

**Requirements**:
- Configurable auto-compact threshold (default: 80%)
- Model-specific context window limits
- Configurable output reservation (default: 20%)
- Safety buffer configuration (default: 10%)
- Per-conversation override capability

**Acceptance Criteria**:
- [ ] Settings persist across sessions
- [ ] Model-specific defaults applied automatically
- [ ] Settings accessible via API and UI

### FR-009: Same-Chat Continuation with Visual Indicator

**Description**: After compaction, conversation continues seamlessly in the same chat with a clear visual divider showing what happened.

**Requirements**:
- Display inline divider after compaction: `─── Context condensed (12,450 → 4,200 tokens) ───`
- Collapsible summary section showing what was condensed
- Click to expand full condensed summary details
- Show reduction percentage and cost (if applicable)
- Animation/transition to indicate compaction occurred
- No page refresh or chat restart required

**Acceptance Criteria**:
- [ ] User can continue chatting immediately after compaction
- [ ] Divider clearly shows before/after token counts
- [ ] Collapsible summary expands to show condensed content
- [ ] Summary includes: key decisions, files mentioned, code snippets preserved
- [ ] Visual indicator is non-intrusive but noticeable

### FR-010: Context Window Progress Bar UI

**Description**: Real-time visual progress bar showing context window usage with color-coded status.

**Requirements**:
- Persistent progress bar in chat header/footer area
- Color coding: Green (0-70%), Yellow/Warning (70-85%), Red/Critical (85-100%)
- Show numeric token count on hover: "45,230 / 128,000 tokens (35%)"
- Animate smoothly as messages are added
- Show reserved space for AI response (grayed out section)
- Pulse/glow animation when approaching threshold

**UI Mockup**:
```
┌────────────────────────────────────────────────────────────────┐
│ Context: [████████████░░░░░░░░░░░░░░░░░░] 35% (45K/128K)      │
│          ├─ Used ────┤├─ Reserved ─┤├─── Available ───┤       │
└────────────────────────────────────────────────────────────────┘
```

**Acceptance Criteria**:
- [ ] Progress bar visible at all times during chat
- [ ] Updates within 100ms of new message
- [ ] Color transitions smoothly between states
- [ ] Tooltip shows detailed breakdown on hover
- [ ] Warning indicator at 70%, critical at 85%

### FR-011: Automatic Checkpoint System (Crash Recovery)

**Description**: Automatically save conversation checkpoints at key moments to protect against IDE/app crashes, with intelligent detection of important context.

**Requirements**:
- **Auto-save triggers** (save checkpoint when):
  - Code is generated or modified (file write detected)
  - Important decisions are made (architecture, implementation choices)
  - Errors are resolved (error → success pattern)
  - Tasks are completed (todo item marked done)
  - Every N messages (configurable, default: 10 messages)
  - Before compaction occurs
  - At configurable time intervals (default: 5 minutes of activity)

- **Important context detection heuristics**:
  - Messages containing code blocks (```language)
  - Messages mentioning file paths
  - Messages with decision language ("decided to", "will use", "chosen approach")
  - Error resolution patterns
  - Task completion indicators

- **Manual save command**: `/save-progress` or `/checkpoint`
  - Optional label: `/save-progress "completed auth feature"`
  - Shows confirmation with checkpoint ID

- **Checkpoint storage**:
  - Store in Supabase with full message history
  - Include current token count and context state
  - Tag with auto-detected labels (code, decision, error-fix, etc.)
  - Keep last 50 checkpoints per session (configurable)

- **Recovery on crash/restart**:
  - Detect if previous session ended abnormally
  - Prompt: "Resume from checkpoint? [timestamp] - 'completed auth feature'"
  - Option to browse recent checkpoints
  - Full context restoration from checkpoint

**Acceptance Criteria**:
- [ ] Auto-save occurs within 2 seconds of trigger event
- [ ] No noticeable UI lag during checkpoint save
- [ ] Manual save confirms with checkpoint ID
- [ ] Crash recovery prompt appears on app restart
- [ ] Full context restored from checkpoint accurately
- [ ] Checkpoint list shows labels and timestamps

### FR-012: Session Resume & Recovery UI

**Description**: UI for browsing, selecting, and resuming from saved sessions and checkpoints.

**Requirements**:
- Session picker on app start: "Continue previous session or start new?"
- List recent sessions with:
  - Last message preview
  - Timestamp
  - Project association
  - Checkpoint count
  - Auto-generated session title
- Checkpoint browser within a session:
  - Timeline view of checkpoints
  - Labels and auto-detected tags
  - Token count at each checkpoint
  - Quick preview on hover
- "Resume from here" button for any checkpoint
- Search/filter sessions by project, date, keywords

**UI Mockup**:
```
┌─────────────────────────────────────────────────────────────────┐
│  Resume Session                                            [X]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Recent Sessions:                                               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 📁 Empire - Service Orchestration                       │   │
│  │    Last: "All 21 tests pass now..."                     │   │
│  │    🕐 2 hours ago  •  5 checkpoints  •  45K tokens      │   │
│  │    [Resume Latest] [Browse Checkpoints]                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 📁 Empire - Context Management PRD                      │   │
│  │    Last: "Let me update the PRD with..."                │   │
│  │    🕐 Just now  •  3 checkpoints  •  28K tokens         │   │
│  │    [Resume Latest] [Browse Checkpoints]                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [Start New Session]                    [View All Sessions]    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Acceptance Criteria**:
- [ ] Session picker appears on app launch
- [ ] Sessions sorted by recency
- [ ] Checkpoint browser shows timeline with labels
- [ ] Resume restores full context including token state
- [ ] Search filters sessions effectively

---

## Non-Functional Requirements

### NFR-001: Performance

- Summarization API call latency: <3 seconds
- Token counting: <100ms for any conversation length
- Memory retrieval: <500ms
- No noticeable UI lag during background operations

### NFR-002: Reliability

- 99.9% success rate for context preservation
- Graceful degradation if summarization service unavailable
- Fallback to simple truncation if AI summarization fails
- All operations idempotent and safe to retry

### NFR-003: Scalability

- Support conversations up to 200k tokens before compaction
- Handle concurrent summarization requests
- Memory storage supports unlimited sessions per user

### NFR-004: Security

- Session memories encrypted at rest
- No sensitive data leaked in summarizations
- User data isolation in multi-tenant environment
- Audit logging for all context operations

---

## Technical Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      Empire Chat System                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐    ┌──────────────────┐                  │
│  │  Chat Interface  │───▶│ Context Manager  │                  │
│  │  (Gradio/React)  │    │    Service       │                  │
│  └──────────────────┘    └────────┬─────────┘                  │
│                                   │                             │
│           ┌───────────────────────┼───────────────────────┐    │
│           │                       │                       │    │
│           ▼                       ▼                       ▼    │
│  ┌────────────────┐    ┌──────────────────┐    ┌────────────┐ │
│  │ Token Counter  │    │  Summarization   │    │  Session   │ │
│  │    Service     │    │     Engine       │    │  Memory    │ │
│  └────────────────┘    └──────────────────┘    └────────────┘ │
│           │                       │                       │    │
│           │                       │                       │    │
│           ▼                       ▼                       ▼    │
│  ┌────────────────┐    ┌──────────────────┐    ┌────────────┐ │
│  │   tiktoken /   │    │   Anthropic API  │    │  Supabase  │ │
│  │  Anthropic API │    │  (Claude Haiku)  │    │  (Memory)  │ │
│  └────────────────┘    └──────────────────┘    └────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Data Models

#### ConversationContext
```python
class ConversationContext(BaseModel):
    session_id: str
    user_id: str
    project_id: Optional[str]
    messages: List[ContextMessage]
    total_tokens: int
    max_tokens: int
    model: str
    protected_message_ids: List[str]
    last_compaction: Optional[datetime]
    compaction_count: int
    created_at: datetime
    updated_at: datetime
```

#### ContextMessage
```python
class ContextMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    token_count: int
    is_protected: bool
    is_summarized: bool
    original_message_ids: Optional[List[str]]  # For summarized messages
    created_at: datetime
    metadata: Dict[str, Any]
```

#### CompactionResult
```python
class CompactionResult(BaseModel):
    session_id: str
    trigger: Literal["manual", "auto", "error_recovery"]
    pre_tokens: int
    post_tokens: int
    reduction_percent: float
    messages_condensed: int
    summary_preview: str
    duration_ms: int
    cost_usd: float
    created_at: datetime
```

#### SessionMemory
```python
class SessionMemory(BaseModel):
    id: str
    user_id: str
    project_id: Optional[str]
    session_id: str
    summary: str
    key_decisions: List[str]
    code_references: List[CodeReference]
    tags: List[str]
    relevance_score: float
    created_at: datetime
    expires_at: datetime
```

#### SessionCheckpoint
```python
class SessionCheckpoint(BaseModel):
    id: str
    session_id: str
    user_id: str
    project_id: Optional[str]
    label: Optional[str]  # User-provided or auto-generated label
    trigger: Literal["auto", "manual", "pre_compaction", "important_context"]
    messages_snapshot: List[ContextMessage]  # Full message history at checkpoint
    token_count: int
    auto_tags: List[str]  # ["code", "decision", "error_fix", "task_complete"]
    metadata: Dict[str, Any]  # Additional context (files modified, etc.)
    created_at: datetime
```

#### ContextWindowStatus
```python
class ContextWindowStatus(BaseModel):
    session_id: str
    current_tokens: int
    max_tokens: int
    reserved_tokens: int  # For AI response
    available_tokens: int
    usage_percent: float
    status: Literal["normal", "warning", "critical"]  # <70%, 70-85%, >85%
    estimated_messages_remaining: int
    last_updated: datetime
```

### API Endpoints

#### Context Management Routes (`/api/context`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/context/status` | Get current context window status |
| POST | `/api/context/compact` | Trigger manual compaction |
| GET | `/api/context/history/{session_id}` | Get compaction history |
| PUT | `/api/context/settings` | Update context settings |
| POST | `/api/context/protect/{message_id}` | Mark message as protected |

#### Session Memory Routes (`/api/memory`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/memory/session/{session_id}` | Get session memory |
| POST | `/api/memory/session` | Save session memory |
| GET | `/api/memory/project/{project_id}` | Get project memories |
| POST | `/api/memory/search` | Search memories by relevance |
| DELETE | `/api/memory/{memory_id}` | Delete a memory |

#### Checkpoint Routes (`/api/checkpoint`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/checkpoint/save` | Create manual checkpoint (with optional label) |
| GET | `/api/checkpoint/session/{session_id}` | List checkpoints for session |
| GET | `/api/checkpoint/{checkpoint_id}` | Get checkpoint details |
| POST | `/api/checkpoint/{checkpoint_id}/restore` | Restore from checkpoint |
| DELETE | `/api/checkpoint/{checkpoint_id}` | Delete a checkpoint |
| GET | `/api/checkpoint/recent` | Get recent checkpoints across sessions |

#### Session Resume Routes (`/api/session`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/session/recent` | List recent sessions for user |
| GET | `/api/session/{session_id}` | Get session details with checkpoints |
| POST | `/api/session/{session_id}/resume` | Resume session from latest state |
| POST | `/api/session/recover` | Check for crash recovery (abnormal termination) |
| DELETE | `/api/session/{session_id}` | Delete session and all checkpoints |

### Database Schema

#### Table: conversation_contexts
```sql
CREATE TABLE conversation_contexts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    project_id UUID REFERENCES projects(id),
    messages JSONB NOT NULL DEFAULT '[]',
    total_tokens INTEGER DEFAULT 0,
    max_tokens INTEGER NOT NULL,
    model VARCHAR(100) NOT NULL,
    protected_message_ids TEXT[] DEFAULT '{}',
    last_compaction TIMESTAMPTZ,
    compaction_count INTEGER DEFAULT 0,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_contexts_user ON conversation_contexts(user_id);
CREATE INDEX idx_contexts_project ON conversation_contexts(project_id);
CREATE INDEX idx_contexts_session ON conversation_contexts(session_id);
```

#### Table: compaction_logs
```sql
CREATE TABLE compaction_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    trigger VARCHAR(50) NOT NULL,
    pre_tokens INTEGER NOT NULL,
    post_tokens INTEGER NOT NULL,
    reduction_percent DECIMAL(5,2) NOT NULL,
    messages_condensed INTEGER NOT NULL,
    summary_preview TEXT,
    duration_ms INTEGER NOT NULL,
    cost_usd DECIMAL(10,6),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_compaction_session ON compaction_logs(session_id);
CREATE INDEX idx_compaction_created ON compaction_logs(created_at);
```

#### Table: session_memories
```sql
CREATE TABLE session_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    project_id UUID REFERENCES projects(id),
    session_id VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    key_decisions JSONB DEFAULT '[]',
    code_references JSONB DEFAULT '[]',
    tags TEXT[] DEFAULT '{}',
    relevance_score DECIMAL(5,4) DEFAULT 0,
    embedding VECTOR(1024),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '30 days')
);

CREATE INDEX idx_memories_user ON session_memories(user_id);
CREATE INDEX idx_memories_project ON session_memories(project_id);
CREATE INDEX idx_memories_tags ON session_memories USING GIN(tags);
CREATE INDEX idx_memories_embedding ON session_memories USING hnsw(embedding vector_cosine_ops);
```

#### Table: session_checkpoints
```sql
CREATE TABLE session_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    project_id UUID REFERENCES projects(id),
    label VARCHAR(255),
    trigger VARCHAR(50) NOT NULL,  -- 'auto', 'manual', 'pre_compaction', 'important_context'
    messages_snapshot JSONB NOT NULL,
    token_count INTEGER NOT NULL,
    auto_tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_checkpoints_session ON session_checkpoints(session_id);
CREATE INDEX idx_checkpoints_user ON session_checkpoints(user_id);
CREATE INDEX idx_checkpoints_created ON session_checkpoints(created_at DESC);
CREATE INDEX idx_checkpoints_tags ON session_checkpoints USING GIN(auto_tags);

-- Keep only last 50 checkpoints per session (cleanup function)
CREATE OR REPLACE FUNCTION cleanup_old_checkpoints()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM session_checkpoints
    WHERE session_id = NEW.session_id
    AND id NOT IN (
        SELECT id FROM session_checkpoints
        WHERE session_id = NEW.session_id
        ORDER BY created_at DESC
        LIMIT 50
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_cleanup_checkpoints
AFTER INSERT ON session_checkpoints
FOR EACH ROW EXECUTE FUNCTION cleanup_old_checkpoints();
```

### Summarization Prompt Template

```
You are a context summarization assistant. Your task is to condense conversation history while preserving ALL critical technical information.

## MUST PRESERVE (Never lose these):
1. **Code snippets**: Include full code blocks, especially modified/created files
2. **File paths**: All file paths mentioned (e.g., app/services/auth.py)
3. **Error messages**: Complete error messages and stack traces
4. **Decisions made**: Architecture choices, implementation decisions, rejected alternatives
5. **Task outcomes**: What was accomplished, what failed, what's pending
6. **Configuration values**: Environment variables, settings, credentials references
7. **Dependencies**: Libraries, versions, package names mentioned

## SUMMARIZATION RULES:
- Condense conversational back-and-forth into key points
- Remove redundant explanations and re-statements
- Combine related information into coherent sections
- Use bullet points for multiple items
- Preserve exact technical terminology

## OUTPUT FORMAT:
### Session Summary
[Brief overview of conversation purpose]

### Key Decisions
- [Decision 1]
- [Decision 2]

### Code Changes
```[language]
[code that was created/modified]
```

### Files Modified
- [file path 1]: [what changed]
- [file path 2]: [what changed]

### Pending Items
- [Item 1]
- [Item 2]

### Important Context
[Any other critical information]
```

---

## Implementation Phases

### Phase 1: Core Token Management & Progress Bar (Week 1)
- Token counting service with tiktoken
- Context window progress bar component
- Color-coded status indicators (green/yellow/red)
- Real-time updates on message send
- Settings configuration UI
- Database tables creation

### Phase 2: Automatic Compaction with Inline UI (Week 2)
- Summarization engine with Anthropic API (Claude Haiku)
- Auto-trigger at configurable threshold
- Inline compaction divider component
- Collapsible summary section UI
- Protected message handling
- Compaction logging to database

### Phase 3: Checkpoint System & Crash Recovery (Week 3)
- Auto-checkpoint on important context detection
- Manual `/save-progress` command
- Checkpoint storage and management
- Crash detection on app start
- Recovery prompt UI
- Checkpoint browser component

### Phase 4: Session Resume & Memory (Week 4)
- Session picker UI on app launch
- Session listing with previews
- Checkpoint timeline browser
- Full context restoration
- Project-aware memory retrieval
- Memory search and relevance scoring

### Phase 5: Polish & Integration (Week 5)
- Desktop app Tauri integration
- Performance optimization
- Error handling edge cases
- User settings persistence
- Documentation and testing

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Summarization loses critical info | Medium | High | Comprehensive prompt + user feedback loop |
| API latency impacts UX | Low | Medium | Background processing + progress indicators |
| Memory storage costs | Low | Low | TTL-based cleanup + compression |
| Token counting inaccuracy | Medium | Low | Use native API counting when available |

---

## Dependencies

### External Services
- Anthropic API (Claude Haiku for summarization)
- Supabase (memory storage)
- tiktoken library (local token estimation)

### Internal Dependencies
- Chat service (message handling)
- Authentication (user context)
- Project service (project association)

---

## Open Questions

1. Should we support different summarization models (GPT-4 Turbo, etc.)?
2. What's the optimal default compaction threshold?
3. Should memory be shared across team members in a project?
4. How long should session memories be retained?

---

## Appendix

### Reference Implementations
- Claude Code `/compact` command
- Roo Code Intelligent Context Condensing
- MCP Memory Service consolidation patterns

### Related Documentation
- Anthropic Token Counting: https://docs.anthropic.com/en/docs/build-with-claude/token-counting
- Claude Code SDK Sessions: https://docs.claude.com/en/docs/claude-code/sdk/sdk-sessions
