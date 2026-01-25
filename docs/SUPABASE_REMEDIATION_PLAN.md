# Supabase Security & Performance Remediation Plan

## Executive Summary

**Total Issues: 214**
- Security Issues: 51
- Performance Issues: 163

---

## Issue Breakdown

### Security Issues (51)

| Category | Count | Severity | Description |
|----------|-------|----------|-------------|
| Function Search Path Mutable | 43 | WARN | Functions without `search_path` set |
| RLS Disabled | 1 | ERROR | `schema_migrations` table without RLS |
| Extensions in Public | 2 | WARN | `vector` and `pg_trgm` in public schema |
| Materialized View in API | 1 | WARN | `current_month_costs` accessible via API |
| RLS Policy Always True | 5 | WARN | Overly permissive RLS policies |

### Performance Issues (163)

| Category | Count | Severity | Description |
|----------|-------|----------|-------------|
| Auth RLS InitPlan | 53 | WARN | RLS policies using `auth.uid()` instead of `(select auth.uid())` |
| Multiple Permissive Policies | 108 | WARN | Tables with overlapping RLS policies |
| Duplicate Indexes | 2 | WARN | Identical indexes on same table |
| Unindexed Foreign Keys | 2 | WARN | FK columns without indexes |

---

## Implementation Plan

### Phase 1: Critical Security Fixes (Priority: HIGH)

**1.1 Enable RLS on schema_migrations**
```sql
ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;
-- This is a system table, restrict to service role only
CREATE POLICY "Service role only" ON public.schema_migrations
  FOR ALL TO service_role USING (true);
```

**1.2 Fix Function Search Paths (43 functions)**
All functions need `SET search_path = ''` added. This prevents search path manipulation attacks.

Functions to fix:
1. has_overdue_clarifications
2. check_concurrent_project_limit
3. update_retrieval_config_timestamp
4. get_pending_agent_clarifications_count
5. get_agent_performance_summary
6. get_rls_context
7. get_pending_clarifications_count
8. get_saga_summary
9. update_conversation_contexts_updated_at
10. match_session_memories
11. traverse_memory_graph
12. increment_share_view
13. cleanup_expired_session_memories
14. update_rag_enhancement_timestamp
15. check_idempotency_key
16. cleanup_expired_idempotency_keys
17. get_retrieval_params
18. update_agent_feedback_updated_at
19. get_user_roles
20. update_agent_clarification_timestamp
21. match_user_memories
22. update_content_sets_updated_at
23. get_related_memories
24. trigger_set_updated_at
25. mark_content_set_complete
26. update_session_memories_updated_at
27. expire_pending_clarification_requests
28. clear_rls_context
29. generate_share_token
30. auto_skip_old_clarifications
31. update_research_jobs_updated_at
32. get_compaction_costs_by_period
33. get_avg_rag_metrics
34. update_research_reports_updated_at
35. current_user_id
36. update_updated_at_column
37. session_has_role
38. mark_wal_in_progress
39. set_rls_context
40. user_has_role
41. is_admin
42. get_pending_wal_entries

---

### Phase 2: Fix Permissive RLS Policies (Priority: HIGH)

**2.1 Tables with overly permissive policies:**

| Table | Policy Name | Issue |
|-------|-------------|-------|
| content_set_files | Users can manage content set files | USING(true), WITH CHECK(true) |
| content_sets | Users can manage content sets | USING(true), WITH CHECK(true) |
| processing_manifests | Users can manage manifests | USING(true), WITH CHECK(true) |
| ragas_evaluations | ragas_service_insert | WITH CHECK(true) |
| rbac_audit_logs | audit_logs_insert_service | WITH CHECK(true) |

**Fix:** Replace `true` with proper user checks like `auth.uid() = user_id`

---

### Phase 3: Performance Fixes (Priority: MEDIUM)

**3.1 Fix Auth RLS InitPlan Issues (53 policies)**

Replace:
```sql
USING (auth.uid() = user_id)
```

With:
```sql
USING ((select auth.uid()) = user_id)
```

This prevents re-evaluation of `auth.uid()` for each row.

**3.2 Remove Duplicate Indexes (2)**

```sql
-- Table: user_document_connections
DROP INDEX IF EXISTS idx_user_doc_conn_memory_node;  -- Keep idx_user_doc_connections_memory
DROP INDEX IF EXISTS idx_user_doc_conn_user_id;      -- Keep idx_user_doc_connections_user
```

**3.3 Add Missing Foreign Key Indexes (2)**

```sql
-- agent_clarification_requests.session_id
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_clarification_requests_session_id
  ON public.agent_clarification_requests(session_id);

-- shared_reports.revoked_by
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_shared_reports_revoked_by
  ON public.shared_reports(revoked_by);
```

---

### Phase 4: Move Extensions (Priority: LOW)

**Note:** Moving extensions requires careful planning as it may break existing queries.

```sql
-- Create extensions schema if not exists
CREATE SCHEMA IF NOT EXISTS extensions;

-- Move vector extension (requires reconnection)
DROP EXTENSION IF EXISTS vector;
CREATE EXTENSION vector SCHEMA extensions;

-- Move pg_trgm extension
DROP EXTENSION IF EXISTS pg_trgm;
CREATE EXTENSION pg_trgm SCHEMA extensions;

-- Update search_path for users
ALTER DATABASE postgres SET search_path TO public, extensions;
```

**Warning:** This requires updating all queries that use these extensions!

---

### Phase 5: Restrict Materialized View Access (Priority: LOW)

```sql
-- Revoke public access to materialized view
REVOKE SELECT ON public.current_month_costs FROM anon, authenticated;
-- Grant only to specific roles that need it
GRANT SELECT ON public.current_month_costs TO service_role;
```

---

## Recommended Execution Order

1. **Immediate (Phase 1.1):** Enable RLS on schema_migrations
2. **Day 1 (Phase 1.2):** Fix function search paths (security critical)
3. **Day 1-2 (Phase 2):** Fix overly permissive RLS policies
4. **Day 2-3 (Phase 3):** Performance optimizations
5. **Day 4+ (Phase 4-5):** Extension moves and view restrictions (requires testing)

---

## Risk Assessment

| Phase | Risk Level | Rollback Complexity |
|-------|------------|---------------------|
| Phase 1.1 | Low | Easy - just disable RLS |
| Phase 1.2 | Medium | Medium - need to remove search_path |
| Phase 2 | High | Medium - restore old policies |
| Phase 3 | Low | Easy - recreate indexes |
| Phase 4 | High | Complex - requires code changes |
| Phase 5 | Medium | Easy - grant permissions back |

---

## Files to Create

1. `migrations/fix_function_search_paths.sql` - Phase 1.2
2. `migrations/fix_permissive_rls_policies.sql` - Phase 2
3. `migrations/fix_rls_initplan_performance.sql` - Phase 3.1
4. `migrations/fix_duplicate_indexes.sql` - Phase 3.2
5. `migrations/add_missing_fk_indexes.sql` - Phase 3.3
6. `migrations/enable_rls_schema_migrations.sql` - Phase 1.1

