-- Migration: Enable Row-Level Security (RLS) for User Data Isolation
-- Task 41.2: Database-Level Data Isolation
-- Date: 2025-11-14
--
-- Purpose: Implement PostgreSQL RLS policies to enforce data isolation at database level
-- This ensures users can only access their own data, even if application security is bypassed
--
-- Security Benefits:
-- - Defense in depth: Database enforces isolation even if app auth fails
-- - SQL injection mitigation: Attackers cannot access other users' data
-- - Compliance: GDPR, HIPAA, SOC 2 requirements enforced at database level

BEGIN;

-- ============================================================================
-- PHASE 1: ENABLE ROW LEVEL SECURITY ON ALL USER TABLES
-- ============================================================================

-- Priority 1: User Document Data
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_approvals ENABLE ROW LEVEL SECURITY;

-- Priority 2: User Activity Data
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE n8n_chat_histories ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_queries ENABLE ROW LEVEL SECURITY;

-- Priority 3: User Operations
ALTER TABLE processing_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE batch_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_document_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE crewai_executions ENABLE ROW LEVEL SECURITY;

-- Log RLS enablement
RAISE NOTICE 'RLS enabled on 14 user-facing tables';

-- ============================================================================
-- PHASE 2: CREATE RLS POLICIES FOR DATA ISOLATION
-- ============================================================================

-- ----------------------------------------------------------------------------
-- PATTERN 1: Direct User Ownership (tables with user_id or uploaded_by)
-- ----------------------------------------------------------------------------

-- Documents table (uploaded_by field)
CREATE POLICY user_documents_policy ON documents
  FOR ALL
  USING (
    uploaded_by = current_setting('app.current_user_id', TRUE)::TEXT
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

-- Document versions table (created_by field)
CREATE POLICY user_document_versions_policy ON document_versions
  FOR ALL
  USING (
    created_by = current_setting('app.current_user_id', TRUE)::TEXT
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

-- Document approvals table (submitted_by and reviewed_by fields)
CREATE POLICY user_document_approvals_policy ON document_approvals
  FOR ALL
  USING (
    submitted_by = current_setting('app.current_user_id', TRUE)::TEXT
    OR
    reviewed_by = current_setting('app.current_user_id', TRUE)::TEXT
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

-- Chat sessions table (user_id field)
CREATE POLICY user_chat_sessions_policy ON chat_sessions
  FOR ALL
  USING (
    user_id = current_setting('app.current_user_id', TRUE)::TEXT
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

-- N8N chat histories table (user_id field)
CREATE POLICY user_n8n_chat_histories_policy ON n8n_chat_histories
  FOR ALL
  USING (
    user_id = current_setting('app.current_user_id', TRUE)::TEXT
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

-- Search queries table (user_id field)
CREATE POLICY user_search_queries_policy ON search_queries
  FOR ALL
  USING (
    user_id = current_setting('app.current_user_id', TRUE)::TEXT
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

-- Batch operations table (user_id field)
CREATE POLICY user_batch_operations_policy ON batch_operations
  FOR ALL
  USING (
    user_id = current_setting('app.current_user_id', TRUE)::TEXT
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

-- User document connections table (user_id field)
CREATE POLICY user_document_connections_policy ON user_document_connections
  FOR ALL
  USING (
    user_id = current_setting('app.current_user_id', TRUE)::TEXT
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

-- CrewAI executions table (user_id field)
CREATE POLICY user_crewai_executions_policy ON crewai_executions
  FOR ALL
  USING (
    user_id = current_setting('app.current_user_id', TRUE)::TEXT
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

RAISE NOTICE 'Created RLS policies for 9 tables with direct user ownership';

-- ----------------------------------------------------------------------------
-- PATTERN 2: Foreign Key Ownership via Documents
-- ----------------------------------------------------------------------------

-- Document metadata table (via document_id FK to documents)
CREATE POLICY user_document_metadata_policy ON document_metadata
  FOR ALL
  USING (
    document_id IN (
      SELECT document_id FROM documents
      WHERE uploaded_by = current_setting('app.current_user_id', TRUE)::TEXT
    )
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

-- Document chunks table (via document_id FK to documents)
CREATE POLICY user_document_chunks_policy ON document_chunks
  FOR ALL
  USING (
    document_id IN (
      SELECT document_id FROM documents
      WHERE uploaded_by = current_setting('app.current_user_id', TRUE)::TEXT
    )
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

-- Processing tasks table (via document_id FK to documents)
CREATE POLICY user_processing_tasks_policy ON processing_tasks
  FOR ALL
  USING (
    document_id IN (
      SELECT document_id FROM documents
      WHERE uploaded_by = current_setting('app.current_user_id', TRUE)::TEXT
    )
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

RAISE NOTICE 'Created RLS policies for 3 tables with FK ownership via documents';

-- ----------------------------------------------------------------------------
-- PATTERN 3: Foreign Key Ownership via Chat Sessions
-- ----------------------------------------------------------------------------

-- Chat messages table (via session_id FK to chat_sessions)
CREATE POLICY user_chat_messages_policy ON chat_messages
  FOR ALL
  USING (
    session_id IN (
      SELECT id FROM chat_sessions
      WHERE user_id = current_setting('app.current_user_id', TRUE)::TEXT
    )
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

-- Chat feedback table (via session_id FK to chat_sessions)
CREATE POLICY user_chat_feedback_policy ON chat_feedback
  FOR ALL
  USING (
    session_id IN (
      SELECT id FROM chat_sessions
      WHERE user_id = current_setting('app.current_user_id', TRUE)::TEXT
    )
    OR
    current_setting('app.user_role', TRUE) = 'admin'
  );

RAISE NOTICE 'Created RLS policies for 2 tables with FK ownership via chat_sessions';

-- ============================================================================
-- PHASE 3: CREATE PERFORMANCE INDEXES FOR RLS COLUMNS
-- ============================================================================

-- Indexes for user_id columns (if not already indexed)
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_search_queries_user_id ON search_queries(user_id);
CREATE INDEX IF NOT EXISTS idx_batch_operations_user_id ON batch_operations(user_id);
CREATE INDEX IF NOT EXISTS idx_user_document_connections_user_id ON user_document_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_crewai_executions_user_id ON crewai_executions(user_id);
CREATE INDEX IF NOT EXISTS idx_n8n_chat_histories_user_id ON n8n_chat_histories(user_id);

-- Indexes for uploaded_by columns (if not already indexed)
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON documents(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_document_versions_created_by ON document_versions(created_by);

-- Indexes for FK columns used in policies
CREATE INDEX IF NOT EXISTS idx_document_metadata_document_id ON document_metadata(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_document_id ON processing_tasks(document_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_feedback_session_id ON chat_feedback(session_id);

RAISE NOTICE 'Created performance indexes for RLS columns';

-- ============================================================================
-- PHASE 4: VERIFICATION QUERIES
-- ============================================================================

-- Verify RLS is enabled on all 14 tables
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

  IF rls_count = 14 THEN
    RAISE NOTICE '✅ RLS enabled on all 14 user-facing tables';
  ELSE
    RAISE WARNING '⚠️  RLS enabled on % out of 14 tables', rls_count;
  END IF;

  -- List tables with RLS enabled
  FOR rls_table IN
    SELECT tablename, rowsecurity
    FROM pg_tables
    WHERE schemaname = 'public'
      AND rowsecurity = TRUE
    ORDER BY tablename
  LOOP
    RAISE NOTICE '  ✅ %', rls_table.tablename;
  END LOOP;
END $$;

-- Verify policies were created
DO $$
DECLARE
  policy_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO policy_count
  FROM pg_policies
  WHERE schemaname = 'public';

  IF policy_count >= 14 THEN
    RAISE NOTICE '✅ Created % RLS policies', policy_count;
  ELSE
    RAISE WARNING '⚠️  Only % policies created (expected at least 14)', policy_count;
  END IF;
END $$;

-- List all policies created
SELECT
  schemaname,
  tablename,
  policyname,
  permissive,
  roles,
  cmd
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- ============================================================================
-- PHASE 5: TESTING QUERIES (For validation after deployment)
-- ============================================================================

-- Test queries to verify RLS is working (run manually after deployment)
-- These should be run with different user contexts set

-- Example test setup:
-- SET app.current_user_id = 'user-123';
-- SET app.user_role = 'viewer';
-- SELECT COUNT(*) FROM documents; -- Should only return user-123's documents

-- Example admin test:
-- SET app.current_user_id = 'admin-456';
-- SET app.user_role = 'admin';
-- SELECT COUNT(*) FROM documents; -- Should return ALL documents

COMMIT;

-- ============================================================================
-- ROLLBACK INSTRUCTIONS (IF NEEDED)
-- ============================================================================

-- If RLS causes issues, run this to disable:
/*
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

-- Or drop specific policies without disabling RLS:
-- DROP POLICY user_documents_policy ON documents;
-- DROP POLICY user_document_metadata_policy ON document_metadata;
-- etc.

COMMIT;
*/

-- ============================================================================
-- NOTES FOR DEPLOYMENT
-- ============================================================================

-- 1. Before running this migration:
--    - Back up the database
--    - Test on staging environment first
--    - Verify application code sets PostgreSQL session variables

-- 2. Application integration required:
--    - Middleware must set app.current_user_id and app.user_role
--    - See docs/RLS_SECURITY_STRATEGY.md for implementation details

-- 3. Performance considerations:
--    - Indexes created for all RLS columns
--    - Monitor query performance with EXPLAIN ANALYZE
--    - RLS adds WHERE clauses to all queries

-- 4. Testing checklist:
--    - Test user isolation (user A cannot see user B's data)
--    - Test admin access (admin can see all data)
--    - Test FK isolation (chunks only visible for owned documents)
--    - Test SQL injection protection

-- 5. Monitoring:
--    - Set up alerts for RLS policy violations
--    - Monitor query performance after deployment
--    - Review PostgreSQL logs for access attempts

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
