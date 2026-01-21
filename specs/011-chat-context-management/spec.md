# Feature Specification: Chat Context Window Management

**Feature Branch**: `011-chat-context-management`
**Created**: 2025-01-19
**Status**: Draft
**Input**: User description: "Chat context window management with intelligent condensing, session checkpoints, and crash recovery"

## Clarifications

### Session 2025-01-19

- Q: What is the data retention policy for session memories and conversation contexts? → A: Project-based chats and Chief Knowledge Officer chat are retained while the project exists (deleted with project). All other chats have indefinite retention until user manually deletes.
- Q: What level of observability should be implemented? → A: Standard metrics + error logging (compaction rate, latency, storage usage, errors) integrated with existing Prometheus/Grafana stack.
- Q: How should concurrent edits from multiple devices/tabs be handled? → A: Last-write-wins with conflict notification (user sees "session updated elsewhere" and can refresh to sync).
- Q: What constraints and tradeoffs should be documented? → A: Added full Constraints & Tradeoffs section covering technical constraints, explicit tradeoffs with rationale, rejected alternatives, and assumptions.
- Q: What are realistic compaction timing targets? → A: Based on Claude Code/Roo Code research: Sonnet default with 15-30 second typical, 60 second max. Background processing with progress indicator. Optional `--fast` flag for Haiku (5-10 seconds).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Real-Time Context Window Visibility (Priority: P1)

As a user having a long conversation, I want to see how much of my context window is being used so I know when the conversation is approaching its limit and can take action proactively.

**Why this priority**: This is the foundational feature that enables all other context management capabilities. Without visibility, users cannot understand or manage their context window effectively.

**Independent Test**: Can be fully tested by sending multiple messages and observing the progress bar update in real-time. Delivers immediate value by removing uncertainty about context limits.

**Acceptance Scenarios**:

1. **Given** a new chat session, **When** the user sends their first message, **Then** the progress bar shows current token usage (e.g., "2,450 / 128,000 tokens - 2%") with green color
2. **Given** token usage reaches 70%, **When** the user views the progress bar, **Then** it displays in yellow/warning color with a subtle pulse animation
3. **Given** token usage reaches 85%, **When** the user views the progress bar, **Then** it displays in red/critical color with a more prominent warning indicator
4. **Given** any token usage level, **When** the user hovers over the progress bar, **Then** a tooltip shows detailed breakdown: used tokens, reserved for response, available space

---

### User Story 2 - Automatic Context Compaction (Priority: P1)

As a user in a long development session, I want the system to automatically condense older conversation history when approaching the limit so I can continue working without interruption or data loss.

**Why this priority**: This is the core functionality that prevents conversation breakage. Without automatic compaction, users would lose context or need to restart conversations frequently.

**Independent Test**: Can be tested by having a conversation that exceeds the 80% threshold and verifying that compaction occurs automatically, the conversation continues seamlessly, and key information is preserved.

**Acceptance Scenarios**:

1. **Given** context usage exceeds 80% threshold, **When** the user sends a new message, **Then** automatic compaction triggers in background with "Condensing context..." progress indicator
2. **Given** compaction is running in background, **When** user views the chat, **Then** they can continue reading previous messages and composing their next message
3. **Given** compaction is triggered, **When** summarization completes (15-30s typical, 60s max), **Then** an inline divider appears showing "Context condensed (45,230 → 18,450 tokens)" with before/after counts
4. **Given** compaction has occurred, **When** the user clicks the collapsible summary section, **Then** it expands to show what was condensed: key decisions, files mentioned, code preserved
5. **Given** compaction completes, **When** the user continues the conversation, **Then** they can chat immediately without any page refresh or restart

---

### User Story 3 - Crash Recovery & Checkpoints (Priority: P2)

As a user who has made significant progress in a conversation, I want the system to automatically save checkpoints at important moments so I can recover my work if the IDE or app crashes.

**Why this priority**: Data loss from crashes is a major pain point. This feature provides safety net protection, though users can work without it (just with more risk).

**Independent Test**: Can be tested by simulating a crash after code generation and verifying the recovery prompt appears on restart with the ability to restore full context.

**Acceptance Scenarios**:

1. **Given** the user generates code (file write detected), **When** the code is written, **Then** an automatic checkpoint is saved within 2 seconds with auto-tag "code"
2. **Given** the app was closed abnormally (crash/force quit), **When** the user restarts the app, **Then** a recovery prompt appears: "Resume from checkpoint? [timestamp] - [label]"
3. **Given** the user runs `/save-progress "completed auth feature"`, **When** the command executes, **Then** a checkpoint is saved with the custom label and confirmation message shows the checkpoint ID
4. **Given** a checkpoint exists, **When** the user selects "restore from checkpoint", **Then** full conversation context is restored including token count and message history

---

### User Story 4 - Session Resume (Priority: P2)

As a user returning to work on a project, I want to see my recent sessions and easily resume where I left off so I don't lose context between work sessions.

**Why this priority**: Continuity across sessions is important for productivity but is an enhancement to the core experience, not essential for basic operation.

**Independent Test**: Can be tested by closing and reopening the app, then selecting a previous session to resume and verifying full context restoration.

**Acceptance Scenarios**:

1. **Given** the user launches the app, **When** previous sessions exist, **Then** a session picker shows recent sessions with: title, last message preview, timestamp, checkpoint count
2. **Given** the session picker is displayed, **When** the user clicks "Resume Latest" on a session, **Then** the conversation loads with full context from the most recent state
3. **Given** a session has multiple checkpoints, **When** the user clicks "Browse Checkpoints", **Then** a timeline view shows all checkpoints with labels, tags, and timestamps
4. **Given** the user selects a specific checkpoint, **When** they click "Resume from here", **Then** the conversation restores to exactly that checkpoint state

---

### User Story 5 - Manual Compaction Control (Priority: P3)

As a power user, I want manual control over when compaction occurs so I can optimize my context window based on my current needs.

**Why this priority**: Manual control is a power user feature that complements automatic behavior but is not essential for the majority of users.

**Independent Test**: Can be tested by running the `/compact` command and verifying the compaction occurs with metrics displayed.

**Acceptance Scenarios**:

1. **Given** any conversation state, **When** the user runs `/compact`, **Then** compaction triggers in background with progress indicator and displays metrics on completion: pre_tokens, post_tokens, reduction percentage
2. **Given** the user runs `/compact --force`, **When** usage is below threshold, **Then** compaction still occurs (force override)
3. **Given** the user runs `/compact --fast`, **When** compaction triggers, **Then** Haiku is used instead of Sonnet for faster (5-10s) but lower-quality compaction
4. **Given** compaction was run recently, **When** the user runs `/compact` within 30 seconds, **Then** a rate limit message appears explaining the cooldown

---

### User Story 6 - Protected Messages (Priority: P3)

As a user, I want to mark certain messages as protected so they are never summarized or condensed, preserving critical context exactly as written.

**Why this priority**: This is an advanced customization feature that provides fine-grained control but has a reasonable default behavior (first message always protected).

**Independent Test**: Can be tested by marking a message as protected, triggering compaction, and verifying the protected message remains unchanged.

**Acceptance Scenarios**:

1. **Given** a conversation starts, **When** compaction occurs, **Then** the first message (system context) is always preserved unchanged
2. **Given** a message exists, **When** the user marks it as protected, **Then** a visual indicator (lock icon) appears on that message
3. **Given** protected messages exist, **When** compaction occurs, **Then** protected messages are never included in summarization

---

### Edge Cases

- What happens when summarization API is unavailable? → Graceful degradation to simple truncation with warning
- What happens when checkpoint storage fails? → Retry with exponential backoff, show warning but don't block conversation
- What happens when token count estimation differs from actual API usage? → Use conservative estimates, handle overflow errors gracefully with auto-recovery
- What happens when user tries to restore a checkpoint from a different model? → Warn about potential context incompatibility, allow with confirmation
- What happens during concurrent compaction attempts? → Serialize compaction operations, reject duplicates with informative message
- What happens when same session is open on multiple devices? → Last-write-wins with "session updated elsewhere" notification and refresh option

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST count tokens in real-time for all conversation messages using tiktoken library
- **FR-002**: System MUST display a persistent progress bar showing context window usage with color-coded status (green <70%, yellow 70-85%, red >85%)
- **FR-003**: System MUST automatically trigger context compaction when token usage exceeds configurable threshold (default: 80%)
- **FR-004**: System MUST use AI-powered summarization (Claude Sonnet by default) to condense conversation history while preserving critical information, with optional `--fast` flag for Haiku
- **FR-005**: System MUST preserve the first message and any user-marked protected messages during compaction
- **FR-006**: System MUST display an inline divider after compaction showing before/after token counts with collapsible summary
- **FR-007**: System MUST provide a `/compact` command for manual compaction with optional `--force` flag and `--fast` flag (uses Haiku for quicker but lower-quality compaction)
- **FR-008**: System MUST automatically create checkpoints when important context is detected (code generation, decisions, error resolution)
- **FR-009**: System MUST provide a `/save-progress` command for manual checkpoint creation with optional label
- **FR-010**: System MUST detect abnormal session termination and prompt for recovery on next launch
- **FR-011**: System MUST store checkpoints in Supabase with full message history and metadata
- **FR-012**: System MUST provide a session picker UI on app launch showing recent sessions with previews
- **FR-013**: System MUST allow resuming from any saved checkpoint with full context restoration
- **FR-014**: System MUST implement rate limiting for compaction (max 1 per 30 seconds)
- **FR-015**: System MUST handle API errors gracefully with automatic retry and fallback to simple truncation
- **FR-016**: System MUST retain project-based chats and Chief Knowledge Officer chats for the lifetime of the associated project (deleted when project is deleted)
- **FR-017**: System MUST retain all other chat sessions indefinitely until user manually deletes them
- **FR-018**: System MUST retain checkpoints for 30 days with a maximum of 50 checkpoints per session
- **FR-019**: System MUST expose Prometheus metrics for: compaction count, compaction latency, token reduction ratio, checkpoint count, storage usage per user
- **FR-020**: System MUST log all compaction and checkpoint errors with structured logging for debugging
- **FR-021**: System MUST use last-write-wins for concurrent session access and notify users when session was updated elsewhere with option to refresh
- **FR-022**: System MUST run compaction in background with progress indicator ("Condensing context...") allowing user to continue reading/composing while compaction runs

### Key Entities

- **ConversationContext**: Represents the current state of a conversation including all messages, token counts, and settings
- **ContextMessage**: Individual message within a conversation with metadata (role, content, token count, protection status)
- **CompactionResult**: Record of a compaction event with before/after metrics and summary preview
- **SessionCheckpoint**: Point-in-time snapshot of conversation state for recovery purposes
- **SessionMemory**: Persistent summary of a conversation for cross-session retrieval; lifecycle tied to chat type (project-bound or indefinite)
- **ContextWindowStatus**: Real-time status of context window usage with thresholds

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can continue conversations seamlessly after compaction without page refresh or restart
- **SC-002**: Context compaction preserves at least 90% of key technical information (code, decisions, file paths, errors)
- **SC-003**: Token count displayed is accurate within 5% of actual API token usage
- **SC-004**: Automatic compaction completes in 15-30 seconds typical, 60 seconds maximum (Sonnet); 5-10 seconds with `--fast` flag (Haiku)
- **SC-005**: Session can be resumed from checkpoint within 30 days of creation with full context restoration
- **SC-006**: Progress bar updates within 100ms of new message being sent
- **SC-007**: Crash recovery successfully restores 95%+ of sessions that ended abnormally
- **SC-008**: Users report 4.5/5 or higher satisfaction with context quality after compaction
- **SC-009**: System handles conversations up to 200K tokens before requiring compaction
- **SC-010**: Checkpoint auto-save occurs within 2 seconds of trigger event with no noticeable UI lag

## Constraints & Tradeoffs

### Technical Constraints

- **Token Counting**: Uses tiktoken library for local estimation; may differ from actual Anthropic API token count by up to 5%
- **Summarization Model**: Claude Sonnet (default) for quality, Claude Haiku (optional --fast) for speed
- **Compaction Timing**: 15-30 seconds typical, 60 seconds max (Sonnet); 5-10 seconds (Haiku); runs in background
- **Context Window Limit**: 200K tokens maximum before compaction is required (model-dependent)
- **Storage Backend**: Supabase PostgreSQL required for all persistence (checkpoints, sessions, memories)
- **Real-time Updates**: Progress bar must update within 100ms; WebSocket or polling required

### Explicit Tradeoffs

| Decision | Chosen Option | Rejected Alternative | Rationale |
|----------|---------------|---------------------|-----------|
| Summarization model | Sonnet (default) + Haiku (--fast option) | Haiku only | Quality preservation (95%+) worth the 15-30s wait; Haiku option for speed-sensitive cases |
| Compaction UX | Background with progress indicator | Blocking UI | User can continue reading/composing; 15-60s blocking would be unacceptable |
| Token counting accuracy vs performance | Local tiktoken estimation | Real-time API token counting | API calls add latency; 5% variance is acceptable with conservative buffers |
| Retention policy | Indefinite for non-project chats | Time-based TTL (30/90 days) | User trust and recovery value outweigh storage costs |
| Concurrent access handling | Last-write-wins | Optimistic locking with merge | Simplicity; multi-device editing is rare edge case |
| Compaction trigger | 80% threshold | 70% or 90% | Balance between proactive management and avoiding unnecessary compactions |

### Rejected Alternatives

- **Full conversation replay**: Storing complete message history and replaying on resume was rejected due to storage costs and load times for long conversations
- **Client-side only storage**: localStorage/IndexedDB approach rejected because it doesn't support cross-device sync or crash recovery
- **No compaction / simple truncation**: Dropping oldest messages without summarization rejected because it loses critical context
- **Real-time collaborative editing**: Google Docs-style CRDT sync rejected as overly complex for the use case
- **External summarization service**: Dedicated summarization microservice rejected; inline Claude calls are simpler and sufficient
- **Blocking compaction UX**: Freezing UI during 15-60s compaction rejected; background processing with progress indicator chosen instead

### Assumptions

- Users typically have 1-3 active long-running conversations at a time
- Average conversation reaches compaction threshold after ~2-4 hours of active use
- Most users will not need to restore checkpoints older than 7 days (but 30-day retention provides safety margin)
- Supabase storage costs are acceptable given compaction reduces per-conversation footprint by 60-75%
