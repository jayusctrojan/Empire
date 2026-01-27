# Data Model: Chat Context Window Management

**Feature Branch**: `011-chat-context-management`
**Date**: 2025-01-19
**Phase**: 1 - Data Model

## Entity Relationship Diagram

```
┌─────────────────────────┐
│   ConversationContext   │
├─────────────────────────┤
│ id: UUID (PK)           │
│ conversation_id: UUID   │───────┐
│ user_id: UUID           │       │
│ total_tokens: INTEGER   │       │
│ max_tokens: INTEGER     │       │
│ threshold_percent: INT  │       │
│ last_compaction_at: TS  │       │
│ created_at: TIMESTAMPTZ │       │
│ updated_at: TIMESTAMPTZ │       │
└─────────────────────────┘       │
           │                      │
           │ 1:N                  │
           ▼                      │
┌─────────────────────────┐       │
│     ContextMessage      │       │
├─────────────────────────┤       │
│ id: UUID (PK)           │       │
│ context_id: UUID (FK)   │───────┘
│ role: VARCHAR(20)       │
│ content: TEXT           │
│ token_count: INTEGER    │
│ is_protected: BOOLEAN   │
│ position: INTEGER       │
│ created_at: TIMESTAMPTZ │
└─────────────────────────┘
           │
           │ N:M (via compaction)
           ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│   CompactionResult      │       │   SessionCheckpoint     │
├─────────────────────────┤       ├─────────────────────────┤
│ id: UUID (PK)           │       │ id: UUID (PK)           │
│ context_id: UUID (FK)   │       │ conversation_id: UUID   │
│ pre_tokens: INTEGER     │       │ checkpoint_data: JSONB  │
│ post_tokens: INTEGER    │       │ token_count: INTEGER    │
│ reduction_percent: FLOAT│       │ label: TEXT             │
│ summary_preview: TEXT   │       │ auto_tag: VARCHAR(50)   │
│ messages_condensed: INT │       │ is_abnormal_close: BOOL │
│ model_used: VARCHAR(50) │       │ created_at: TIMESTAMPTZ │
│ duration_ms: INTEGER    │       │ expires_at: TIMESTAMPTZ │
│ created_at: TIMESTAMPTZ │       └─────────────────────────┘
└─────────────────────────┘                   │
                                              │ 1:N
                                              ▼
                                  ┌─────────────────────────┐
                                  │    SessionMemory        │
                                  ├─────────────────────────┤
                                  │ id: UUID (PK)           │
                                  │ conversation_id: UUID   │
                                  │ project_id: UUID (null) │
                                  │ summary: TEXT           │
                                  │ key_decisions: JSONB    │
                                  │ files_mentioned: JSONB  │
                                  │ retention_type: VARCHAR │
                                  │ created_at: TIMESTAMPTZ │
                                  │ updated_at: TIMESTAMPTZ │
                                  └─────────────────────────┘
```

## Table Definitions

### conversation_contexts

Tracks real-time context window state for each conversation.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| conversation_id | UUID | NOT NULL, FK chat_sessions(id) | Link to chat session |
| user_id | UUID | NOT NULL, FK auth.users(id) | Owner user |
| total_tokens | INTEGER | NOT NULL, DEFAULT 0 | Current token count |
| max_tokens | INTEGER | NOT NULL, DEFAULT 200000 | Model's context limit |
| threshold_percent | INTEGER | NOT NULL, DEFAULT 80 | Compaction trigger threshold |
| last_compaction_at | TIMESTAMPTZ | NULL | Last compaction timestamp |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Indexes**:
- `idx_contexts_conversation` on (conversation_id) - Lookup by conversation
- `idx_contexts_user` on (user_id) - List user's contexts

### context_messages

Individual messages with token counts and protection status.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| context_id | UUID | NOT NULL, FK conversation_contexts(id) | Parent context |
| role | VARCHAR(20) | NOT NULL | 'user', 'assistant', 'system' |
| content | TEXT | NOT NULL | Message content |
| token_count | INTEGER | NOT NULL | Tokens in this message |
| is_protected | BOOLEAN | NOT NULL, DEFAULT FALSE | Cannot be summarized |
| position | INTEGER | NOT NULL | Order in conversation |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation timestamp |

**Indexes**:
- `idx_messages_context` on (context_id) - Get messages for context
- `idx_messages_position` on (context_id, position) - Ordered retrieval
- `idx_messages_protected` on (context_id) WHERE is_protected = TRUE - Find protected

### compaction_logs

Audit trail of compaction events.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| context_id | UUID | NOT NULL, FK conversation_contexts(id) | Context compacted |
| pre_tokens | INTEGER | NOT NULL | Tokens before compaction |
| post_tokens | INTEGER | NOT NULL | Tokens after compaction |
| reduction_percent | DECIMAL(5,2) | NOT NULL | Percentage reduction |
| summary_preview | TEXT | NULL | First 500 chars of summary |
| messages_condensed | INTEGER | NOT NULL | Number of messages summarized |
| model_used | VARCHAR(50) | NOT NULL | 'claude-sonnet-4' or 'claude-haiku' |
| duration_ms | INTEGER | NOT NULL | Compaction duration |
| triggered_by | VARCHAR(20) | NOT NULL | 'auto', 'manual', 'force' |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Compaction timestamp |

**Indexes**:
- `idx_compaction_context` on (context_id) - History for context
- `idx_compaction_created` on (created_at) - Time-based queries

### session_checkpoints

Point-in-time snapshots for recovery.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| conversation_id | UUID | NOT NULL, FK chat_sessions(id) | Parent conversation |
| user_id | UUID | NOT NULL, FK auth.users(id) | Owner user |
| checkpoint_data | JSONB | NOT NULL | Full conversation state |
| token_count | INTEGER | NOT NULL | Tokens at checkpoint |
| label | TEXT | NULL | User-provided label |
| auto_tag | VARCHAR(50) | NULL | 'code', 'decision', 'error_resolution' |
| is_abnormal_close | BOOLEAN | NOT NULL, DEFAULT FALSE | Crash recovery checkpoint |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Checkpoint timestamp |
| expires_at | TIMESTAMPTZ | NOT NULL | 30 days from creation |

**Indexes**:
- `idx_checkpoint_conversation` on (conversation_id) - Get checkpoints for conversation
- `idx_checkpoint_user` on (user_id, created_at DESC) - User's recent checkpoints
- `idx_checkpoint_abnormal` on (user_id) WHERE is_abnormal_close = TRUE - Find crash recovery
- `idx_checkpoint_expires` on (expires_at) - Cleanup query

**Constraints**:
- Maximum 50 checkpoints per conversation (enforced in application)

### session_memories

Persistent summaries for session resume.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| conversation_id | UUID | NOT NULL, FK chat_sessions(id) | Parent conversation |
| user_id | UUID | NOT NULL, FK auth.users(id) | Owner user |
| project_id | UUID | NULL, FK projects(id) | Associated project (if any) |
| summary | TEXT | NOT NULL | Conversation summary |
| key_decisions | JSONB | NOT NULL, DEFAULT '[]' | Array of decisions |
| files_mentioned | JSONB | NOT NULL, DEFAULT '[]' | Array of file paths |
| code_preserved | JSONB | NOT NULL, DEFAULT '[]' | Important code snippets |
| retention_type | VARCHAR(20) | NOT NULL | 'project', 'cko', 'indefinite' |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Indexes**:
- `idx_memory_conversation` on (conversation_id) - Get memory for conversation
- `idx_memory_user` on (user_id, updated_at DESC) - User's recent sessions
- `idx_memory_project` on (project_id) WHERE project_id IS NOT NULL - Project sessions

## JSONB Schema Definitions

### checkpoint_data (SessionCheckpoint)

```json
{
  "messages": [
    {
      "id": "uuid",
      "role": "user|assistant|system",
      "content": "string",
      "token_count": 123,
      "is_protected": false,
      "created_at": "2025-01-19T12:00:00Z"
    }
  ],
  "context_state": {
    "total_tokens": 45000,
    "max_tokens": 200000,
    "compaction_count": 2
  },
  "metadata": {
    "model": "claude-sonnet-4",
    "checkpoint_reason": "code_generation"
  }
}
```

### key_decisions (SessionMemory)

```json
[
  {
    "decision": "Use JWT for authentication",
    "rationale": "Industry standard, stateless",
    "timestamp": "2025-01-19T12:00:00Z"
  }
]
```

### files_mentioned (SessionMemory)

```json
[
  {
    "path": "app/services/auth_service.py",
    "action": "created",
    "timestamp": "2025-01-19T12:00:00Z"
  }
]
```

## Redis Cache Schema

### Context Window State (Real-time)

**Key Pattern**: `context:{conversation_id}:state`

```json
{
  "total_tokens": 45000,
  "max_tokens": 200000,
  "threshold_percent": 80,
  "status": "normal|warning|critical",
  "last_updated": "2025-01-19T12:00:00Z"
}
```
**TTL**: 24 hours (refreshed on activity)

### Compaction Lock

**Key Pattern**: `context:{conversation_id}:compaction_lock`

**Value**: `{task_id}` or empty
**TTL**: 5 minutes (prevents duplicate compaction)

### Compaction Progress

**Key Pattern**: `context:{conversation_id}:compaction_progress`

```json
{
  "task_id": "celery-task-uuid",
  "progress": 50,
  "status": "summarizing|processing|finalizing",
  "started_at": "2025-01-19T12:00:00Z"
}
```
**TTL**: 10 minutes

## Row Level Security Policies

### conversation_contexts

```sql
CREATE POLICY "Users can only access own contexts"
ON conversation_contexts
FOR ALL
USING (user_id = auth.uid());
```

### context_messages

```sql
CREATE POLICY "Users can only access own messages"
ON context_messages
FOR ALL
USING (
  context_id IN (
    SELECT id FROM conversation_contexts WHERE user_id = auth.uid()
  )
);
```

### session_checkpoints

```sql
CREATE POLICY "Users can only access own checkpoints"
ON session_checkpoints
FOR ALL
USING (user_id = auth.uid());
```

### session_memories

```sql
CREATE POLICY "Users can only access own memories"
ON session_memories
FOR ALL
USING (user_id = auth.uid());
```

## Migration Files

### 20250119_001_create_conversation_contexts.sql

Creates `conversation_contexts` table with indexes.

### 20250119_002_create_context_messages.sql

Creates `context_messages` table with indexes and FK to contexts.

### 20250119_003_create_compaction_logs.sql

Creates `compaction_logs` table with indexes.

### 20250119_004_create_session_checkpoints.sql

Creates `session_checkpoints` table with indexes and expiration.

### 20250119_005_create_session_memories.sql

Creates `session_memories` table with indexes and FK to projects.

### 20250119_006_enable_rls_policies.sql

Enables RLS on all new tables with user isolation policies.
