-- ============================================================================
-- ROLLBACK: RLS Policies for user_memory_nodes and user_memory_edges
-- Original Migration: add_memory_rls_policies.sql (Task 27)
-- Date: 2025-11-25
-- ============================================================================
--
-- PURPOSE: Remove RLS policies from user memory tables
--
-- WHEN TO USE:
-- - RLS policies blocking service account access
-- - Performance issues from policy evaluation
-- - Application not setting user context correctly
-- - Need to debug memory operations
--
-- WARNING: Rolling back removes data isolation for user memories!
-- All users could potentially access all memory data.
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: DROP HELPER FUNCTIONS
-- ============================================================================

-- Drop the match_user_memories function
DROP FUNCTION IF EXISTS match_user_memories(vector(768), TEXT, DECIMAL, INTEGER);

-- Drop the set_user_context function
DROP FUNCTION IF EXISTS set_user_context(TEXT);

RAISE NOTICE 'Dropped memory helper functions';

-- ============================================================================
-- PHASE 2: DROP RLS POLICIES FOR user_memory_nodes
-- ============================================================================

DROP POLICY IF EXISTS user_memory_nodes_select_policy ON user_memory_nodes;
DROP POLICY IF EXISTS user_memory_nodes_insert_policy ON user_memory_nodes;
DROP POLICY IF EXISTS user_memory_nodes_update_policy ON user_memory_nodes;
DROP POLICY IF EXISTS user_memory_nodes_delete_policy ON user_memory_nodes;

RAISE NOTICE 'Dropped user_memory_nodes RLS policies';

-- ============================================================================
-- PHASE 3: DROP RLS POLICIES FOR user_memory_edges
-- ============================================================================

DROP POLICY IF EXISTS user_memory_edges_select_policy ON user_memory_edges;
DROP POLICY IF EXISTS user_memory_edges_insert_policy ON user_memory_edges;
DROP POLICY IF EXISTS user_memory_edges_update_policy ON user_memory_edges;
DROP POLICY IF EXISTS user_memory_edges_delete_policy ON user_memory_edges;

RAISE NOTICE 'Dropped user_memory_edges RLS policies';

-- ============================================================================
-- PHASE 4: DISABLE ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE user_memory_nodes DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_memory_edges DISABLE ROW LEVEL SECURITY;

RAISE NOTICE 'Disabled RLS on memory tables';

-- ============================================================================
-- PHASE 5: VERIFICATION
-- ============================================================================

DO $$
DECLARE
    rls_status RECORD;
BEGIN
    -- Check user_memory_nodes
    SELECT tablename, rowsecurity INTO rls_status
    FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename = 'user_memory_nodes';

    IF NOT rls_status.rowsecurity THEN
        RAISE NOTICE '[OK] RLS disabled on user_memory_nodes';
    ELSE
        RAISE WARNING '[WARN] RLS still enabled on user_memory_nodes';
    END IF;

    -- Check user_memory_edges
    SELECT tablename, rowsecurity INTO rls_status
    FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename = 'user_memory_edges';

    IF NOT rls_status.rowsecurity THEN
        RAISE NOTICE '[OK] RLS disabled on user_memory_edges';
    ELSE
        RAISE WARNING '[WARN] RLS still enabled on user_memory_edges';
    END IF;
END $$;

-- Verify no policies remain
SELECT
    tablename,
    policyname,
    permissive,
    cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('user_memory_nodes', 'user_memory_edges')
ORDER BY tablename, policyname;

-- Verify functions removed
SELECT routine_name
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name IN ('match_user_memories', 'set_user_context');

COMMIT;

-- ============================================================================
-- POST-ROLLBACK CHECKLIST
-- ============================================================================
--
-- After running this rollback:
--
-- 1. [ ] Update application to use direct queries instead of match_user_memories
-- 2. [ ] Remove set_user_context calls from application code
-- 3. [ ] Implement application-level filtering for user memory access
-- 4. [ ] Test that memory operations work without user context
-- 5. [ ] Monitor for unauthorized memory access attempts
--
-- SECURITY IMPACT:
-- - User memories no longer isolated at database level
-- - Cross-user memory access possible if application bugs exist
-- - Consider using WHERE user_id = ? in all memory queries
--
-- ALTERNATIVE VECTOR SEARCH (without RLS):
--
-- SELECT id, content, similarity
-- FROM user_memory_nodes
-- WHERE user_id = '<user_id>'
--   AND is_active = true
--   AND embedding IS NOT NULL
--   AND (1 - (embedding <=> '<query_embedding>')) >= 0.7
-- ORDER BY embedding <=> '<query_embedding>'
-- LIMIT 10;
--
-- ============================================================================
