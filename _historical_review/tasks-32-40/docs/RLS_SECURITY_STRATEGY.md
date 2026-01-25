# Row-Level Security (RLS) Strategy for Empire v7.3
## Task 41.2: Database-Level Data Isolation

**Date**: 2025-11-14
**Purpose**: Implement PostgreSQL Row-Level Security policies to enforce data isolation at the database level

---

## Executive Summary

Row-Level Security (RLS) is **critical** for preventing unauthorized data access, even if application-level security is bypassed. RLS ensures that:
- Users can only access their own data
- SQL injection attacks cannot leak other users' data
- Direct database access is restricted to authorized rows
- Compliance requirements (GDPR, HIPAA) are enforced at the database level

---

## Current RLS Status

### ✅ Already Protected (11 tables)
These tables already have RLS enabled:
- `user_memory_nodes`, `user_memory_edges` (user memory system)
- `ragas_evaluations` (RAG evaluation metrics)
- `cost_entries`, `budget_configs`, `cost_reports`, `cost_alerts` (cost tracking)
- `roles`, `user_roles`, `api_keys`, `rbac_audit_logs` (RBAC system)

### ❌ Missing RLS Protection (14 critical tables)

**Priority 1 - User Document Data:**
1. **documents** - `uploaded_by` field for user ownership
2. **document_metadata** - via `document_id` FK to documents
3. **document_chunks** - via `document_id` FK to documents
4. **document_versions** - `created_by` field for ownership
5. **document_approvals** - `submitted_by`, `reviewed_by` fields

**Priority 2 - User Activity Data:**
6. **chat_sessions** - `user_id` field
7. **chat_messages** - via `session_id` FK to chat_sessions
8. **chat_feedback** - via `session_id` FK to chat_sessions
9. **n8n_chat_histories** - `user_id` field
10. **search_queries** - `user_id` field

**Priority 3 - User Operations:**
11. **processing_tasks** - via `document_id` FK to documents
12. **batch_operations** - `user_id` field
13. **user_document_connections** - `user_id` field
14. **crewai_executions** - `user_id` field

---

## RLS Policy Design Patterns

### Pattern 1: Direct User Ownership
For tables with `user_id` or `uploaded_by` column:

```sql
-- Example: chat_sessions table
CREATE POLICY user_isolation ON chat_sessions
  USING (user_id = current_setting('app.current_user_id'));
```

### Pattern 2: Foreign Key Ownership (via documents)
For tables related to documents (e.g., document_chunks, document_metadata):

```sql
-- Example: document_chunks table
CREATE POLICY user_isolation ON document_chunks
  USING (
    document_id IN (
      SELECT document_id FROM documents
      WHERE uploaded_by = current_setting('app.current_user_id')
    )
  );
```

### Pattern 3: Foreign Key Ownership (via sessions)
For tables related to chat sessions (e.g., chat_messages):

```sql
-- Example: chat_messages table
CREATE POLICY user_isolation ON chat_messages
  USING (
    session_id IN (
      SELECT id FROM chat_sessions
      WHERE user_id = current_setting('app.current_user_id')
    )
  );
```

### Pattern 4: Admin Override
For tables that admins should access:

```sql
-- Example with admin override
CREATE POLICY user_or_admin_access ON documents
  USING (
    uploaded_by = current_setting('app.current_user_id')
    OR
    current_setting('app.user_role') = 'admin'
  );
```

---

## Implementation Plan

### Phase 1: Enable RLS on All User Tables
```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
-- ... (all 14 tables)
```

### Phase 2: Create Isolation Policies

**For documents table:**
```sql
CREATE POLICY user_documents_policy ON documents
  FOR ALL
  USING (
    uploaded_by = current_setting('app.current_user_id', TRUE)::TEXT
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );
```

**For document_metadata:**
```sql
CREATE POLICY user_document_metadata_policy ON document_metadata
  FOR ALL
  USING (
    document_id IN (
      SELECT document_id FROM documents
      WHERE uploaded_by = current_setting('app.current_user_id', TRUE)::TEXT
    )
  );
```

**For chat_sessions:**
```sql
CREATE POLICY user_chat_sessions_policy ON chat_sessions
  FOR ALL
  USING (
    user_id = current_setting('app.current_user_id', TRUE)::TEXT
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );
```

### Phase 3: Application Integration

**Set User Context in Application:**
In `app/middleware/auth.py`, after user authentication:

```python
async def set_user_context_for_rls(user_id: str, role: str, db_connection):
    """
    Set PostgreSQL session variables for RLS policy enforcement

    This ensures RLS policies can check current user ID and role
    """
    await db_connection.execute(
        "SELECT set_config('app.current_user_id', $1, false)",
        user_id
    )
    await db_connection.execute(
        "SELECT set_config('app.user_role', $2, false)",
        role
    )
```

**Usage in request lifecycle:**
```python
@app.middleware("http")
async def rls_context_middleware(request: Request, call_next):
    """Set RLS context for authenticated requests"""
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "user_role", "guest")

    if user_id:
        # Set PostgreSQL session variables
        async with get_db_connection() as conn:
            await set_user_context_for_rls(user_id, user_role, conn)

    response = await call_next(request)
    return response
```

---

## Security Benefits

### 1. Defense in Depth
- **Application bypass protection**: Even if application auth is bypassed, database enforces isolation
- **SQL injection mitigation**: Attackers cannot access other users' data via SQL injection
- **Direct database access protection**: DBA/admin queries respect user boundaries

### 2. Compliance
- **GDPR**: Ensures user data is isolated and only accessible by authorized users
- **HIPAA**: Protects PHI at the database level
- **SOC 2**: Demonstrates technical access controls at multiple layers

### 3. Audit Trail
- RLS enforcement logged in PostgreSQL logs
- Failed access attempts captured
- Compliance reporting made easier

---

## Testing Strategy

### Test 1: User Isolation
```python
# As user A
documents_a = await db.fetch("SELECT * FROM documents")
# Should only return user A's documents

# As user B
documents_b = await db.fetch("SELECT * FROM documents")
# Should only return user B's documents, not A's
```

### Test 2: Admin Access
```python
# As admin
all_documents = await db.fetch("SELECT * FROM documents")
# Should return ALL documents (admin override)
```

### Test 3: FK Isolation
```python
# As user A
chunks_a = await db.fetch("SELECT * FROM document_chunks")
# Should only return chunks for user A's documents
```

### Test 4: SQL Injection Protection
```python
# Attempt to bypass via SQL injection
malicious_query = "SELECT * FROM documents WHERE uploaded_by = 'attacker_id' OR 1=1"
result = await db.fetch(malicious_query)
# Should still only return current user's documents
```

---

## Migration Script Structure

```sql
-- Migration: enable_rls_for_user_tables.sql
BEGIN;

-- Phase 1: Enable RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_metadata ENABLE ROW LEVEL SECURITY;
-- ... (14 tables)

-- Phase 2: Create policies
CREATE POLICY user_documents_policy ON documents ...;
CREATE POLICY user_document_metadata_policy ON document_metadata ...;
-- ... (14 policies)

-- Phase 3: Verify
SELECT
    schemaname,
    tablename,
    rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

COMMIT;
```

---

## Rollback Plan

If RLS causes issues:
```sql
-- Disable RLS on specific table
ALTER TABLE documents DISABLE ROW LEVEL SECURITY;

-- Or drop specific policy
DROP POLICY user_documents_policy ON documents;
```

---

## Performance Considerations

1. **Indexes**: Ensure indexed columns used in RLS policies
   - `documents.uploaded_by` (already indexed)
   - `chat_sessions.user_id` (add index)
   - `search_queries.user_id` (add index)

2. **Query Planning**: RLS adds WHERE clauses to queries
   - Monitor query plans: `EXPLAIN ANALYZE`
   - Ensure indexes are used

3. **Connection Pooling**: Session variables persist per connection
   - Reset context between requests
   - Use `set_config(..., false)` for transaction-scoped settings

---

## Tables NOT Requiring RLS

**System Tables (no user isolation needed):**
- `embedding_generations` - system-level
- `search_cache` - shared cache
- `system_metrics`, `processing_logs`, `health_checks` - system monitoring
- `performance_metrics`, `alert_rules`, `alert_history` - monitoring
- `api_usage_log` - system-level (could add user filtering later)

**Shared Configuration:**
- `crewai_agents`, `crewai_crews`, `crewai_task_templates` - shared configs
- `admin_users`, `admin_sessions`, `admin_activity_log` - admin-only (restrict via app)
- `system_config` - admin-only (restrict via app)

**Related Tables (inherit isolation):**
- `crewai_task_executions`, `crewai_agent_interactions`, `crewai_generated_assets` - inherit from crewai_executions

---

## Implementation Checklist

- [ ] Create RLS migration SQL script
- [ ] Test migration on local Supabase instance
- [ ] Add RLS context setting to auth middleware
- [ ] Create automated RLS tests
- [ ] Add performance indexes for RLS columns
- [ ] Document RLS policies in code comments
- [ ] Update API documentation with RLS behavior
- [ ] Train team on RLS implications
- [ ] Monitor query performance post-deployment
- [ ] Set up alerts for RLS violations

---

## Next Steps

1. **Create migration script** (`migrations/enable_rls.sql`)
2. **Update auth middleware** to set user context
3. **Write RLS tests** in `tests/test_rls_isolation.py`
4. **Apply migration** to development environment
5. **Verify isolation** with test users
6. **Deploy to production** with rollback plan ready

---

**Document Version**: 1.0
**Last Updated**: 2025-11-14
**Status**: Ready for Implementation
