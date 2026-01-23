-- ============================================================================
-- ROLLBACK: Performance Indexes for Empire v7.3
-- Original Migration: add_performance_indexes.sql (Task 43.3)
-- Date: 2025-11-25
-- ============================================================================
--
-- PURPOSE: Remove performance indexes if causing issues
--
-- WHEN TO USE:
-- - Indexes causing write performance degradation
-- - Index bloat consuming excessive storage
-- - Need to rebuild indexes from scratch
-- - Index corruption or inconsistencies
--
-- NOTE: Removing indexes will NOT delete data, only slow down queries.
-- The pg_trgm extension is left intact as other features may use it.
--
-- IMPORTANT: DROP INDEX CONCURRENTLY cannot run inside a transaction.
-- This script must be run outside a transaction block.
-- ============================================================================

-- ============================================================================
-- PHASE 1: DROP DOCUMENT INDEXES
-- ============================================================================

DROP INDEX CONCURRENTLY IF EXISTS idx_documents_user_id_status;
DROP INDEX CONCURRENTLY IF EXISTS idx_documents_created_at;
DROP INDEX CONCURRENTLY IF EXISTS idx_documents_doc_type;
DROP INDEX CONCURRENTLY IF EXISTS idx_documents_embedding_hnsw;

DO $$ BEGIN RAISE NOTICE 'Dropped document table indexes'; END $$;

-- ============================================================================
-- PHASE 2: DROP RECORD MANAGER INDEXES
-- ============================================================================

DROP INDEX CONCURRENTLY IF EXISTS idx_record_manager_key_namespace;
DROP INDEX CONCURRENTLY IF EXISTS idx_record_manager_updated_at;

DO $$ BEGIN RAISE NOTICE 'Dropped record manager indexes'; END $$;

-- ============================================================================
-- PHASE 3: DROP CHAT SESSION/MESSAGE INDEXES
-- ============================================================================

DROP INDEX CONCURRENTLY IF EXISTS idx_chat_sessions_user_id_updated;
DROP INDEX CONCURRENTLY IF EXISTS idx_chat_messages_session_timestamp;
DROP INDEX CONCURRENTLY IF EXISTS idx_chat_messages_role;

DO $$ BEGIN RAISE NOTICE 'Dropped chat session/message indexes'; END $$;

-- ============================================================================
-- PHASE 4: DROP KNOWLEDGE GRAPH INDEXES
-- ============================================================================

DROP INDEX CONCURRENTLY IF EXISTS idx_knowledge_entities_name_trgm;
DROP INDEX CONCURRENTLY IF EXISTS idx_knowledge_entities_type;
DROP INDEX CONCURRENTLY IF EXISTS idx_knowledge_entities_document_id;
DROP INDEX CONCURRENTLY IF EXISTS idx_knowledge_relationships_source;
DROP INDEX CONCURRENTLY IF EXISTS idx_knowledge_relationships_target;

DO $$ BEGIN RAISE NOTICE 'Dropped knowledge graph indexes'; END $$;

-- ============================================================================
-- PHASE 5: DROP USER MEMORY GRAPH INDEXES
-- ============================================================================

DROP INDEX CONCURRENTLY IF EXISTS idx_user_memory_nodes_user_id;
DROP INDEX CONCURRENTLY IF EXISTS idx_user_memory_nodes_type;
DROP INDEX CONCURRENTLY IF EXISTS idx_user_memory_edges_source;
DROP INDEX CONCURRENTLY IF EXISTS idx_user_memory_edges_target;

DO $$ BEGIN RAISE NOTICE 'Dropped user memory graph indexes'; END $$;

-- ============================================================================
-- PHASE 6: DROP PERFORMANCE MONITORING INDEXES
-- ============================================================================

DROP INDEX CONCURRENTLY IF EXISTS idx_query_perf_log_timestamp;
DROP INDEX CONCURRENTLY IF EXISTS idx_query_perf_log_endpoint_timestamp;
DROP INDEX CONCURRENTLY IF EXISTS idx_query_perf_log_user_id;
DROP INDEX CONCURRENTLY IF EXISTS idx_document_feedback_document_created;
DROP INDEX CONCURRENTLY IF EXISTS idx_document_feedback_user_id;

DO $$ BEGIN RAISE NOTICE 'Dropped performance monitoring indexes'; END $$;

-- ============================================================================
-- PHASE 7: DROP ERROR/AUDIT LOG INDEXES (Task 43.3 specific)
-- ============================================================================

-- Note: These may overlap with indexes from create_audit_logs_table migration
-- Only dropping Task 43.3 specific indexes
DROP INDEX CONCURRENTLY IF EXISTS idx_error_logs_timestamp;
DROP INDEX CONCURRENTLY IF EXISTS idx_error_logs_level;
DROP INDEX CONCURRENTLY IF EXISTS idx_error_logs_endpoint;

DO $$ BEGIN RAISE NOTICE 'Dropped error log indexes'; END $$;

-- ============================================================================
-- PHASE 8: DROP TABULAR DOCUMENT INDEXES
-- ============================================================================

DROP INDEX CONCURRENTLY IF EXISTS idx_tabular_rows_document_id;
DROP INDEX CONCURRENTLY IF EXISTS idx_tabular_rows_row_number;

DO $$ BEGIN RAISE NOTICE 'Dropped tabular document row indexes'; END $$;

-- ============================================================================
-- PHASE 9: DROP USER DOCUMENT CONNECTION INDEXES
-- ============================================================================

DROP INDEX CONCURRENTLY IF EXISTS idx_user_doc_connections_user_id;
DROP INDEX CONCURRENTLY IF EXISTS idx_user_doc_connections_document_id;

DO $$ BEGIN RAISE NOTICE 'Dropped user document connection indexes'; END $$;

-- ============================================================================
-- PHASE 10: VERIFICATION
-- ============================================================================

-- Count remaining indexes from Task 43.3
SELECT
    indexname,
    tablename,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
FROM pg_indexes
WHERE schemaname = 'public'
  AND (indexname LIKE 'idx_documents_%'
       OR indexname LIKE 'idx_record_manager_%'
       OR indexname LIKE 'idx_chat_%'
       OR indexname LIKE 'idx_knowledge_%'
       OR indexname LIKE 'idx_user_memory_%'
       OR indexname LIKE 'idx_query_perf_%'
       OR indexname LIKE 'idx_document_feedback_%'
       OR indexname LIKE 'idx_error_logs_%'
       OR indexname LIKE 'idx_tabular_%'
       OR indexname LIKE 'idx_user_doc_%')
ORDER BY tablename, indexname;

-- ============================================================================
-- POST-ROLLBACK CHECKLIST
-- ============================================================================
--
-- After running this rollback:
--
-- 1. [ ] Monitor query performance for degradation
-- 2. [ ] Check EXPLAIN ANALYZE on critical queries
-- 3. [ ] Consider adding back specific indexes that were beneficial
-- 4. [ ] Update ANALYZE statistics: ANALYZE <table_name>;
-- 5. [ ] Document which indexes were problematic
--
-- PERFORMANCE IMPACT:
-- - Vector similarity search will use sequential scan (slower)
-- - User lookup queries will be slower
-- - Time-based queries may timeout on large tables
-- - Consider running VACUUM ANALYZE after rollback
--
-- ============================================================================
