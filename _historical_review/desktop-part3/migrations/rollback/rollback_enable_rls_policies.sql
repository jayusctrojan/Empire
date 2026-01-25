-- ============================================================================
-- ROLLBACK: Enable Row-Level Security (RLS) for User Data Isolation
-- Original Migration: enable_rls_policies.sql (Task 41.2)
-- Date: 2025-11-25
-- ============================================================================
--
-- PURPOSE: Safely revert RLS policies if they cause issues in production
--
-- WHEN TO USE:
-- - RLS policies causing query failures
-- - Performance issues from policy overhead
-- - Application unable to set session variables correctly
-- - Emergency rollback needed for service restoration
--
-- WARNING: Rolling back RLS removes database-level data isolation!
-- After rollback, rely ONLY on application-level security.
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: DROP ALL RLS POLICIES
-- ============================================================================

-- Priority 1: User Document Data policies
DROP POLICY IF EXISTS user_documents_policy ON documents;
DROP POLICY IF EXISTS user_document_metadata_policy ON document_metadata;
DROP POLICY IF EXISTS user_document_chunks_policy ON document_chunks;
DROP POLICY IF EXISTS user_document_versions_policy ON document_versions;
DROP POLICY IF EXISTS user_document_approvals_policy ON document_approvals;

-- Priority 2: User Activity Data policies
DROP POLICY IF EXISTS user_chat_sessions_policy ON chat_sessions;
DROP POLICY IF EXISTS user_chat_messages_policy ON chat_messages;
DROP POLICY IF EXISTS user_chat_feedback_policy ON chat_feedback;
DROP POLICY IF EXISTS user_n8n_chat_histories_policy ON n8n_chat_histories;
DROP POLICY IF EXISTS user_search_queries_policy ON search_queries;

-- Priority 3: User Operations policies
DROP POLICY IF EXISTS user_processing_tasks_policy ON processing_tasks;
DROP POLICY IF EXISTS user_batch_operations_policy ON batch_operations;
DROP POLICY IF EXISTS user_document_connections_policy ON user_document_connections;
DROP POLICY IF EXISTS user_crewai_executions_policy ON crewai_executions;

RAISE NOTICE 'Dropped 14 RLS policies';

-- ============================================================================
-- PHASE 2: DISABLE ROW LEVEL SECURITY ON ALL TABLES
-- ============================================================================

-- Priority 1: User Document Data
ALTER TABLE documents DISABLE ROW LEVEL SECURITY;
ALTER TABLE document_metadata DISABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks DISABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions DISABLE ROW LEVEL SECURITY;
ALTER TABLE document_approvals DISABLE ROW LEVEL SECURITY;

-- Priority 2: User Activity Data
ALTER TABLE chat_sessions DISABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages DISABLE ROW LEVEL SECURITY;
ALTER TABLE chat_feedback DISABLE ROW LEVEL SECURITY;
ALTER TABLE n8n_chat_histories DISABLE ROW LEVEL SECURITY;
ALTER TABLE search_queries DISABLE ROW LEVEL SECURITY;

-- Priority 3: User Operations
ALTER TABLE processing_tasks DISABLE ROW LEVEL SECURITY;
ALTER TABLE batch_operations DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_document_connections DISABLE ROW LEVEL SECURITY;
ALTER TABLE crewai_executions DISABLE ROW LEVEL SECURITY;

RAISE NOTICE 'Disabled RLS on 14 tables';

-- ============================================================================
-- PHASE 3: VERIFY ROLLBACK (Optional indexes are kept for performance)
-- ============================================================================

-- Note: We keep the indexes created for RLS columns as they may still
-- benefit query performance. Only the RLS policies are removed.

-- Verification: Confirm RLS is disabled
DO $$
DECLARE
    rls_table RECORD;
    rls_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO rls_count
    FROM pg_tables
    WHERE schemaname = 'public'
      AND rowsecurity = TRUE
      AND tablename IN (
        'documents', 'document_metadata', 'document_chunks', 'document_versions', 'document_approvals',
        'chat_sessions', 'chat_messages', 'chat_feedback', 'n8n_chat_histories', 'search_queries',
        'processing_tasks', 'batch_operations', 'user_document_connections', 'crewai_executions'
      );

    IF rls_count = 0 THEN
        RAISE NOTICE '✅ RLS successfully disabled on all 14 user-facing tables';
    ELSE
        RAISE WARNING '⚠️  RLS still enabled on % tables', rls_count;
    END IF;
END $$;

-- List tables to confirm RLS status
SELECT
    tablename,
    CASE WHEN rowsecurity THEN 'ENABLED' ELSE 'DISABLED' END as rls_status
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'documents', 'document_metadata', 'document_chunks', 'document_versions', 'document_approvals',
    'chat_sessions', 'chat_messages', 'chat_feedback', 'n8n_chat_histories', 'search_queries',
    'processing_tasks', 'batch_operations', 'user_document_connections', 'crewai_executions'
  )
ORDER BY tablename;

COMMIT;

-- ============================================================================
-- POST-ROLLBACK CHECKLIST
-- ============================================================================
--
-- After running this rollback:
--
-- 1. [ ] Verify application still sets session variables (harmless if unused)
-- 2. [ ] Test all CRUD operations work without policy checks
-- 3. [ ] Confirm query performance has returned to normal
-- 4. [ ] Update monitoring alerts to reflect RLS disabled state
-- 5. [ ] Document reason for rollback in incident log
-- 6. [ ] Plan remediation to re-enable RLS after fixing issues
--
-- SECURITY IMPACT:
-- - Database no longer enforces user isolation
-- - Application security becomes sole line of defense
-- - SQL injection could expose all user data
-- - Consider enabling WAF/IDS monitoring
--
-- ============================================================================
