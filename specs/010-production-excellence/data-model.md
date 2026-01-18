# Data Model: Production Excellence - 100/100 Readiness

**Date**: 2026-01-17
**Feature Branch**: `010-production-excellence`

## New Entities

### 1. DeadLetterQueue

**Purpose**: Store failed Celery task information for manual review and retry

**Table**: `dead_letter_queue`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique identifier |
| task_id | VARCHAR(255) | NOT NULL | Celery task ID |
| task_name | VARCHAR(255) | NOT NULL | Task function name |
| exception | TEXT | | Exception message and traceback |
| task_args | JSONB | | Task positional arguments |
| task_kwargs | JSONB | | Task keyword arguments |
| retries | INTEGER | DEFAULT 0 | Number of retry attempts |
| max_retries | INTEGER | DEFAULT 3 | Maximum allowed retries |
| status | VARCHAR(50) | DEFAULT 'pending_review' | pending_review, retrying, resolved, abandoned |
| resolution_notes | TEXT | | Admin notes on resolution |
| new_task_id | VARCHAR(255) | | ID of retry task if retried |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | When task failed |
| updated_at | TIMESTAMPTZ | | Last status update |
| retried_at | TIMESTAMPTZ | | When retry was attempted |
| resolved_at | TIMESTAMPTZ | | When marked resolved |

**Indexes**:
- `idx_dlq_status` ON status
- `idx_dlq_task_name` ON task_name
- `idx_dlq_created` ON created_at DESC

**State Transitions**:
```
pending_review → retrying → pending_review (if retry fails)
pending_review → retrying → resolved (if retry succeeds)
pending_review → abandoned (manual decision)
pending_review → resolved (manual fix)
```

### 2. AgentFeedback

**Purpose**: Store feedback on AI agent outputs for quality tracking and model improvement

**Table**: `agent_feedback`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique identifier |
| agent_id | VARCHAR(50) | NOT NULL | Agent identifier (e.g., AGENT-002, AGENT-008) |
| task_id | UUID | | Related task if applicable |
| feedback_type | VARCHAR(50) | NOT NULL | classification, generation, retrieval |
| input_summary | TEXT | | Summary of agent input |
| output_summary | TEXT | | Summary of agent output |
| rating | INTEGER | CHECK (1-5) | User rating |
| feedback_text | TEXT | | Detailed feedback |
| metadata | JSONB | DEFAULT '{}' | Additional context |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Feedback timestamp |
| created_by | UUID | REFERENCES auth.users(id) | User who provided feedback |

**Indexes**:
- `idx_agent_feedback_agent` ON agent_id
- `idx_agent_feedback_type` ON feedback_type
- `idx_agent_feedback_created` ON created_at DESC

### 3. HealthCheckResult (Runtime Only)

**Purpose**: Runtime health check status (not persisted)

**Pydantic Model**:
```python
class HealthCheckResult(BaseModel):
    component: str  # e.g., "supabase", "neo4j", "redis", "b2"
    status: Literal["healthy", "unhealthy", "degraded"]
    response_time_ms: float
    error: Optional[str]
    checked_at: datetime
```

### 4. TraceContext (Runtime Only)

**Purpose**: Distributed tracing context propagation

**Pydantic Model**:
```python
class TraceContext(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    sampled: bool
```

## Existing Entity Updates

### documents_v2

No schema changes. B2 integration uses existing columns:
- `file_path` - B2 key path
- `b2_file_id` - B2 file identifier
- `storage_status` - uploaded, processing, failed

### research_projects

No schema changes. Celery integration uses:
- `status` - pending, initializing, active, cancelled
- `task_ids` - Array of Celery task IDs (JSONB)

## Relationships

```
dead_letter_queue
  └── references: None (standalone)

agent_feedback
  └── created_by → auth.users(id)
  └── task_id → (optional, any task table)

documents_v2
  └── (existing relationships unchanged)
```

## Migration Plan

### Migration 001: Dead Letter Queue
```sql
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id VARCHAR(255) NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    exception TEXT,
    task_args JSONB,
    task_kwargs JSONB,
    retries INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    status VARCHAR(50) DEFAULT 'pending_review',
    resolution_notes TEXT,
    new_task_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    retried_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_dlq_status ON dead_letter_queue(status);
CREATE INDEX idx_dlq_task_name ON dead_letter_queue(task_name);
CREATE INDEX idx_dlq_created ON dead_letter_queue(created_at DESC);
```

### Migration 002: Agent Feedback
```sql
CREATE TABLE agent_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    task_id UUID,
    feedback_type VARCHAR(50) NOT NULL,
    input_summary TEXT,
    output_summary TEXT,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

CREATE INDEX idx_agent_feedback_agent ON agent_feedback(agent_id);
CREATE INDEX idx_agent_feedback_type ON agent_feedback(feedback_type);
CREATE INDEX idx_agent_feedback_created ON agent_feedback(created_at DESC);
```
