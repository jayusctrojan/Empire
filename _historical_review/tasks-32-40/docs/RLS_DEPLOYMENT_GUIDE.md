# Row-Level Security (RLS) Deployment Guide
## Task 41.2: Database-Level Data Isolation

**Date**: 2025-11-14
**Purpose**: Step-by-step guide to deploy PostgreSQL RLS policies for Empire v7.3
**Status**: Ready for deployment

---

## Overview

This guide walks through deploying Row-Level Security (RLS) policies to enforce database-level data isolation in Empire v7.3. RLS ensures users can only access their own data, even if application-level security is bypassed.

**What's Included:**
- ✅ RLS migration script (`migrations/enable_rls_policies.sql`)
- ✅ RLS context middleware (`app/middleware/rls_context.py`)
- ✅ Integration with FastAPI (`app/main.py`)
- ✅ Documentation and testing strategy

---

## Prerequisites

Before deploying RLS:

1. **Backup Database**
   ```bash
   # Using Supabase Dashboard:
   # 1. Go to Database > Backups
   # 2. Create manual backup
   # 3. Download backup file
   ```

2. **Test on Staging First**
   - Deploy to staging/development environment
   - Run full test suite
   - Verify user isolation works correctly

3. **Application Code Updated**
   - ✅ RLS context middleware created
   - ✅ Middleware integrated into FastAPI app
   - ⏳ Session variable setting (requires DB connection implementation)

---

## Deployment Steps

### Step 1: Review the Migration

**File**: `migrations/enable_rls_policies.sql`

**What it does:**
1. Enables RLS on 14 user-facing tables
2. Creates 14 RLS policies (3 patterns: direct ownership, FK via documents, FK via sessions)
3. Creates performance indexes for RLS columns
4. Includes verification queries

**Tables protected:**
- **Priority 1 (Documents)**: documents, document_metadata, document_chunks, document_versions, document_approvals
- **Priority 2 (Activity)**: chat_sessions, chat_messages, chat_feedback, n8n_chat_histories, search_queries
- **Priority 3 (Operations)**: processing_tasks, batch_operations, user_document_connections, crewai_executions

### Step 2: Apply Migration Using Supabase MCP

**Option A: Using Supabase MCP (Recommended)**

```python
# Using Claude Code with Supabase MCP
from pathlib import Path

migration_path = Path("/Users/jaybajaj/.../Empire/migrations/enable_rls_policies.sql")
migration_sql = migration_path.read_text()

# Apply migration via Supabase MCP
mcp__supabase__apply_migration(
    name="enable_rls_policies",
    query=migration_sql
)
```

**Option B: Using Supabase Dashboard**

1. Open Supabase Dashboard: https://app.supabase.com/project/[your-project-id]
2. Navigate to: **SQL Editor** tab
3. Click **New Query**
4. Paste contents of `migrations/enable_rls_policies.sql`
5. Click **Run** to execute
6. Verify output shows "RLS enabled on all 14 user-facing tables"

**Option C: Using psql CLI**

```bash
# Connect to Supabase PostgreSQL
psql "postgresql://postgres:[password]@[host]:5432/postgres"

# Run migration
\i migrations/enable_rls_policies.sql

# Verify
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public' AND rowsecurity = TRUE;
```

### Step 3: Verify RLS is Enabled

After applying the migration, verify RLS is active:

**Check 1: RLS Enabled on Tables**
```sql
SELECT
    schemaname,
    tablename,
    rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
    AND tablename IN (
        'documents', 'document_metadata', 'document_chunks',
        'document_versions', 'document_approvals',
        'chat_sessions', 'chat_messages', 'chat_feedback',
        'n8n_chat_histories', 'search_queries',
        'processing_tasks', 'batch_operations',
        'user_document_connections', 'crewai_executions'
    )
ORDER BY tablename;
```

Expected: 14 rows with `rowsecurity = TRUE`

**Check 2: Policies Created**
```sql
SELECT
    tablename,
    policyname,
    permissive,
    cmd
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;
```

Expected: At least 14 policies (one per table)

**Check 3: Indexes Created**
```sql
SELECT
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE schemaname = 'public'
    AND indexname LIKE 'idx_%user_id%'
    OR indexname LIKE 'idx_%uploaded_by%'
    OR indexname LIKE 'idx_%document_id%'
    OR indexname LIKE 'idx_%session_id%'
ORDER BY tablename;
```

Expected: Multiple indexes for RLS columns

### Step 4: Update Application Environment Variables

Add to `.env` file:

```bash
# Task 41.2: Row-Level Security
RLS_ENABLED=true  # Enable RLS context middleware
```

Restart FastAPI application to load the new middleware.

### Step 5: Implement PostgreSQL Session Variable Setting

**Current Status**: RLS middleware is integrated but session variables are not yet set.

**Next Steps**:

1. Update `app/middleware/rls_context.py` to actually set PostgreSQL session variables
2. Use direct PostgreSQL connection (not Supabase REST API) to execute:
   ```sql
   SELECT set_config('app.current_user_id', 'user-123', false);
   SELECT set_config('app.user_role', 'viewer', false);
   ```

3. Options for implementation:
   - **Option A**: Use `asyncpg` library for direct PostgreSQL connection
   - **Option B**: Use Supabase MCP's `execute_sql` function
   - **Option C**: Use SQLAlchemy ORM if already configured

**Example with asyncpg**:
```python
import asyncpg

async def _set_rls_context(self, user_id: str, role: str):
    """Set PostgreSQL session variables for RLS"""
    db_url = os.getenv("DATABASE_URL")  # Supabase PostgreSQL URL

    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(
            "SELECT set_config('app.current_user_id', $1, false)",
            user_id
        )
        await conn.execute(
            "SELECT set_config('app.user_role', $2, false)",
            role
        )
        logger.debug("rls_context_set", user_id=user_id, role=role)
    finally:
        await conn.close()
```

---

## Testing the RLS Implementation

### Test 1: User Isolation (Basic)

**Objective**: Verify users can only see their own data

```sql
-- Set user context to user-A
SELECT set_config('app.current_user_id', 'user-A', false);
SELECT set_config('app.user_role', 'viewer', false);

-- Query documents - should only return user-A's documents
SELECT document_id, title, uploaded_by FROM documents;
-- Expected: Only documents where uploaded_by = 'user-A'

-- Set user context to user-B
SELECT set_config('app.current_user_id', 'user-B', false);
SELECT set_config('app.user_role', 'viewer', false);

-- Query documents - should only return user-B's documents
SELECT document_id, title, uploaded_by FROM documents;
-- Expected: Only documents where uploaded_by = 'user-B'
-- user-A's documents should NOT appear
```

### Test 2: Admin Override

**Objective**: Verify admins can see all data

```sql
-- Set admin context
SELECT set_config('app.current_user_id', 'admin-456', false);
SELECT set_config('app.user_role', 'admin', false);

-- Query documents - should return ALL documents
SELECT COUNT(*) FROM documents;
-- Expected: Total count of all documents (not just admin's)

-- Verify admin sees both user-A and user-B documents
SELECT DISTINCT uploaded_by FROM documents ORDER BY uploaded_by;
-- Expected: Multiple users including user-A, user-B
```

### Test 3: Foreign Key Isolation

**Objective**: Verify FK-based policies work correctly

```sql
-- Set user context
SELECT set_config('app.current_user_id', 'user-A', false);
SELECT set_config('app.user_role', 'viewer', false);

-- Query document chunks (FK to documents)
SELECT chunk_id, document_id FROM document_chunks;
-- Expected: Only chunks for documents where uploaded_by = 'user-A'

-- Attempt to query another user's chunks should return empty
SELECT chunk_id, document_id FROM document_chunks
WHERE document_id IN (
    SELECT document_id FROM documents WHERE uploaded_by = 'user-B'
);
-- Expected: Empty result (RLS blocks access)
```

### Test 4: SQL Injection Protection

**Objective**: Verify RLS blocks SQL injection attempts

```sql
-- Attempt SQL injection to bypass RLS
SELECT set_config('app.current_user_id', 'user-A', false);

-- Malicious query attempting to access all data
SELECT * FROM documents
WHERE uploaded_by = 'user-A' OR 1=1;
-- Expected: Still only returns user-A's documents
-- RLS policy overrides the WHERE clause
```

### Test 5: Application-Level Testing

**Create test script**: `tests/test_rls_isolation.py`

```python
import pytest
import asyncpg
import os

@pytest.mark.asyncio
async def test_user_isolation():
    """Test that users can only access their own data"""
    db_url = os.getenv("DATABASE_URL")

    conn = await asyncpg.connect(db_url)

    try:
        # Set user-A context
        await conn.execute("SELECT set_config('app.current_user_id', 'user-A', false)")
        await conn.execute("SELECT set_config('app.user_role', 'viewer', false)")

        # Query documents
        docs_a = await conn.fetch("SELECT * FROM documents")

        # All documents should belong to user-A
        for doc in docs_a:
            assert doc['uploaded_by'] == 'user-A'

        # Set user-B context
        await conn.execute("SELECT set_config('app.current_user_id', 'user-B', false)")

        # Query documents again
        docs_b = await conn.fetch("SELECT * FROM documents")

        # All documents should belong to user-B
        for doc in docs_b:
            assert doc['uploaded_by'] == 'user-B'

        # Verify no overlap
        doc_ids_a = {doc['document_id'] for doc in docs_a}
        doc_ids_b = {doc['document_id'] for doc in docs_b}
        assert len(doc_ids_a & doc_ids_b) == 0  # No common documents

    finally:
        await conn.close()

@pytest.mark.asyncio
async def test_admin_access():
    """Test that admins can access all data"""
    db_url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(db_url)

    try:
        # Set admin context
        await conn.execute("SELECT set_config('app.current_user_id', 'admin-123', false)")
        await conn.execute("SELECT set_config('app.user_role', 'admin', false)")

        # Query documents - should get ALL documents
        all_docs = await conn.fetch("SELECT * FROM documents")

        # Get unique uploaders
        uploaders = {doc['uploaded_by'] for doc in all_docs}

        # Should see documents from multiple users
        assert len(uploaders) > 1

    finally:
        await conn.close()
```

Run tests:
```bash
pytest tests/test_rls_isolation.py -v
```

---

## Performance Considerations

### 1. Query Performance Impact

RLS adds WHERE clauses to every query. Monitor query performance:

```sql
-- Check query plans with RLS
EXPLAIN ANALYZE
SELECT * FROM documents;

-- Verify indexes are being used
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM documents
WHERE uploaded_by = 'user-123';
```

Expected: Index scan on `idx_documents_uploaded_by`

### 2. Indexing Strategy

All RLS columns are indexed:
- `documents.uploaded_by` → `idx_documents_uploaded_by`
- `chat_sessions.user_id` → `idx_chat_sessions_user_id`
- `document_chunks.document_id` → `idx_document_chunks_document_id`
- etc.

Verify indexes are used in query plans.

### 3. Connection Pooling

PostgreSQL session variables persist per connection:
- Use `set_config(..., false)` for session-scoped variables
- Connection pooling automatically resets variables on connection reuse
- No manual cleanup needed

---

## Rollback Instructions

If RLS causes issues:

**Option 1: Disable RLS without removing policies**

```sql
BEGIN;

-- Disable RLS on all tables
ALTER TABLE documents DISABLE ROW LEVEL SECURITY;
ALTER TABLE document_metadata DISABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks DISABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions DISABLE ROW LEVEL SECURITY;
ALTER TABLE document_approvals DISABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions DISABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages DISABLE ROW LEVEL SECURITY;
ALTER TABLE chat_feedback DISABLE ROW LEVEL SECURITY;
ALTER TABLE n8n_chat_histories DISABLE ROW LEVEL SECURITY;
ALTER TABLE search_queries DISABLE ROW LEVEL SECURITY;
ALTER TABLE processing_tasks DISABLE ROW LEVEL SECURITY;
ALTER TABLE batch_operations DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_document_connections DISABLE ROW LEVEL SECURITY;
ALTER TABLE crewai_executions DISABLE ROW LEVEL SECURITY;

COMMIT;
```

**Option 2: Remove specific policies**

```sql
-- Drop policies (keeps RLS enabled but removes enforcement)
DROP POLICY user_documents_policy ON documents;
DROP POLICY user_document_metadata_policy ON document_metadata;
-- ... repeat for all policies
```

**Option 3: Disable via environment variable**

```bash
# In .env file
RLS_ENABLED=false
```

Restart application - RLS middleware will be inactive.

---

## Monitoring and Alerts

### 1. RLS Policy Violations

Monitor PostgreSQL logs for RLS denials:

```sql
-- Enable logging of RLS denials (Supabase Dashboard > Settings > Database > Log Settings)
ALTER SYSTEM SET log_row_security = 'on';
SELECT pg_reload_conf();
```

### 2. Query Performance

Monitor slow queries with RLS:

```sql
-- Check pg_stat_statements for slow queries
SELECT
    query,
    mean_exec_time,
    calls
FROM pg_stat_statements
WHERE query LIKE '%documents%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### 3. Application Metrics

Track RLS context setting in application logs:

```python
logger.info(
    "rls_context_set",
    user_id=user_id,
    role=role,
    endpoint=request.url.path
)
```

---

## Security Benefits Summary

✅ **Defense in Depth**: Database enforces isolation even if application auth fails
✅ **SQL Injection Mitigation**: Attackers cannot access other users' data via injection
✅ **Direct DB Access Protection**: DBA/admin queries respect user boundaries
✅ **Compliance**: GDPR, HIPAA, SOC 2 requirements enforced at database level
✅ **Audit Trail**: RLS enforcement logged in PostgreSQL logs

---

## Next Steps

1. ✅ RLS migration created (`migrations/enable_rls_policies.sql`)
2. ✅ RLS middleware integrated (`app/middleware/rls_context.py`)
3. ⏳ **Implement PostgreSQL session variable setting** (see Step 5 above)
4. ⏳ **Apply migration to staging environment**
5. ⏳ **Run RLS test suite** (`tests/test_rls_isolation.py`)
6. ⏳ **Monitor query performance** (EXPLAIN ANALYZE)
7. ⏳ **Deploy to production** (after successful staging tests)

---

## References

- **RLS Strategy Document**: `docs/RLS_SECURITY_STRATEGY.md`
- **Migration Script**: `migrations/enable_rls_policies.sql`
- **Middleware Implementation**: `app/middleware/rls_context.py`
- **PostgreSQL RLS Docs**: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- **Supabase RLS Guide**: https://supabase.com/docs/guides/auth/row-level-security

---

**Document Version**: 1.0
**Last Updated**: 2025-11-14
**Status**: Ready for deployment (pending session variable implementation)
