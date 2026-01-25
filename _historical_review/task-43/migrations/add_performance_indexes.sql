-- Performance Indexes for Empire v7.3
-- Task 43.3: Optimize and Re-Test for Throughput and Latency
--
-- This migration adds strategic indexes to improve query performance
-- based on load testing results and identified bottlenecks.
--
-- All indexes are created with CONCURRENTLY to avoid table locks during creation.
--
-- Usage:
--   psql -d empire -f migrations/add_performance_indexes.sql
--
-- Or via Supabase MCP:
--   Use mcp__supabase__apply_migration tool

-- ============================================================================
-- Documents Table Indexes
-- ============================================================================

-- User document lookups by status (common filtering pattern)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_user_id_status
ON documents_v2(user_id, processing_status)
WHERE processing_status IS NOT NULL;

COMMENT ON INDEX idx_documents_user_id_status IS
'Optimizes user document queries filtered by processing status (Task 43.3)';

-- Recent documents query (dashboard, list views)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_created_at
ON documents_v2(created_at DESC)
WHERE deleted_at IS NULL;

COMMENT ON INDEX idx_documents_created_at IS
'Optimizes recent documents queries with descending order (Task 43.3)';

-- Document type filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_doc_type
ON documents_v2(doc_type)
WHERE doc_type IS NOT NULL;

COMMENT ON INDEX idx_documents_doc_type IS
'Optimizes document queries filtered by type (Task 43.3)';

-- ============================================================================
-- Vector Search Optimization (HNSW)
-- ============================================================================

-- HNSW index for fast approximate nearest neighbor search
-- Parameters:
--   m = 16: Max connections per layer (higher = better recall, more memory)
--   ef_construction = 64: Build-time search depth (higher = better index quality)
--
-- Runtime tuning:
--   SET hnsw.ef_search = 40;  -- Query-time search depth

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_embedding_hnsw
ON documents_v2 USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64)
WHERE embedding IS NOT NULL;

COMMENT ON INDEX idx_documents_embedding_hnsw IS
'HNSW index for fast vector similarity search (Task 43.3)';

-- ============================================================================
-- Record Manager Indexes (Duplicate Prevention)
-- ============================================================================

-- Fast duplicate detection
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_record_manager_key_namespace
ON record_manager_v2(key, namespace);

COMMENT ON INDEX idx_record_manager_key_namespace IS
'Optimizes duplicate checking in record manager (Task 43.3)';

-- Cleanup queries by timestamp
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_record_manager_updated_at
ON record_manager_v2(updated_at DESC);

COMMENT ON INDEX idx_record_manager_updated_at IS
'Optimizes cleanup queries by update timestamp (Task 43.3)';

-- ============================================================================
-- Chat Sessions and Messages
-- ============================================================================

-- User chat sessions (recent first)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_sessions_user_id_updated
ON chat_sessions(user_id, updated_at DESC)
WHERE deleted_at IS NULL;

COMMENT ON INDEX idx_chat_sessions_user_id_updated IS
'Optimizes user chat session queries (Task 43.3)';

-- Session messages (chronological order)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_messages_session_timestamp
ON chat_messages(session_id, timestamp DESC);

COMMENT ON INDEX idx_chat_messages_session_timestamp IS
'Optimizes chat message queries by session (Task 43.3)';

-- Message role filtering (user vs assistant)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_messages_role
ON chat_messages(role)
WHERE role IS NOT NULL;

COMMENT ON INDEX idx_chat_messages_role IS
'Optimizes queries filtering by message role (Task 43.3)';

-- ============================================================================
-- Knowledge Graph Entities and Relationships
-- ============================================================================

-- Text search on entity names (trigram for fuzzy matching)
-- Requires pg_trgm extension
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_knowledge_entities_name_trgm
ON knowledge_entities USING gin(name gin_trgm_ops);

COMMENT ON INDEX idx_knowledge_entities_name_trgm IS
'Enables fuzzy text search on entity names (Task 43.3)';

-- Entity type filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_knowledge_entities_type
ON knowledge_entities(entity_type)
WHERE entity_type IS NOT NULL;

COMMENT ON INDEX idx_knowledge_entities_type IS
'Optimizes entity queries filtered by type (Task 43.3)';

-- Entity document references
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_knowledge_entities_document_id
ON knowledge_entities(document_id)
WHERE document_id IS NOT NULL;

COMMENT ON INDEX idx_knowledge_entities_document_id IS
'Optimizes entity lookups by source document (Task 43.3)';

-- Relationship lookups (both directions)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_knowledge_relationships_source
ON knowledge_relationships(source_entity_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_knowledge_relationships_target
ON knowledge_relationships(target_entity_id);

COMMENT ON INDEX idx_knowledge_relationships_source IS
'Optimizes relationship queries by source entity (Task 43.3)';

COMMENT ON INDEX idx_knowledge_relationships_target IS
'Optimizes relationship queries by target entity (Task 43.3)';

-- ============================================================================
-- User Memory Graph (Neo4j-style in Postgres)
-- ============================================================================

-- Memory node lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_memory_nodes_user_id
ON user_memory_nodes(user_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_memory_nodes_type
ON user_memory_nodes(node_type)
WHERE node_type IS NOT NULL;

COMMENT ON INDEX idx_user_memory_nodes_user_id IS
'Optimizes user memory queries (Task 43.3)';

COMMENT ON INDEX idx_user_memory_nodes_type IS
'Optimizes memory node queries by type (Task 43.3)';

-- Memory edge traversal
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_memory_edges_source
ON user_memory_edges(source_node_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_memory_edges_target
ON user_memory_edges(target_node_id);

COMMENT ON INDEX idx_user_memory_edges_source IS
'Optimizes memory graph traversal from source (Task 43.3)';

COMMENT ON INDEX idx_user_memory_edges_target IS
'Optimizes memory graph traversal to target (Task 43.3)';

-- ============================================================================
-- Performance Monitoring Tables
-- ============================================================================

-- Query performance log analytics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_query_perf_log_timestamp
ON query_performance_log(timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_query_perf_log_endpoint_timestamp
ON query_performance_log(endpoint, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_query_perf_log_user_id
ON query_performance_log(user_id)
WHERE user_id IS NOT NULL;

COMMENT ON INDEX idx_query_perf_log_timestamp IS
'Optimizes performance log queries by time (Task 43.3)';

COMMENT ON INDEX idx_query_perf_log_endpoint_timestamp IS
'Optimizes performance analysis by endpoint (Task 43.3)';

-- Document feedback analytics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_feedback_document_created
ON document_feedback(document_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_feedback_user_id
ON document_feedback(user_id);

COMMENT ON INDEX idx_document_feedback_document_created IS
'Optimizes document feedback queries (Task 43.3)';

-- ============================================================================
-- Error Logs and Audit Logs
-- ============================================================================

-- Error log queries (recent errors, error type analysis)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_error_logs_timestamp
ON error_logs(timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_error_logs_level
ON error_logs(level)
WHERE level IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_error_logs_endpoint
ON error_logs(endpoint)
WHERE endpoint IS NOT NULL;

COMMENT ON INDEX idx_error_logs_timestamp IS
'Optimizes recent error queries (Task 43.3)';

COMMENT ON INDEX idx_error_logs_level IS
'Optimizes error queries by severity level (Task 43.3)';

-- Audit log queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_timestamp
ON audit_logs(timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_user_id
ON audit_logs(user_id)
WHERE user_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_event_type
ON audit_logs(event_type);

COMMENT ON INDEX idx_audit_logs_timestamp IS
'Optimizes audit log time-based queries (Task 43.3)';

COMMENT ON INDEX idx_audit_logs_user_id IS
'Optimizes audit queries by user (Task 43.3)';

-- ============================================================================
-- Tabular Document Rows
-- ============================================================================

-- Row lookups by document
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tabular_rows_document_id
ON tabular_document_rows(document_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tabular_rows_row_number
ON tabular_document_rows(document_id, row_number);

COMMENT ON INDEX idx_tabular_rows_document_id IS
'Optimizes tabular row queries by document (Task 43.3)';

COMMENT ON INDEX idx_tabular_rows_row_number IS
'Optimizes ordered row retrieval (Task 43.3)';

-- ============================================================================
-- User Document Connections
-- ============================================================================

-- Connection lookups (both directions)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_doc_connections_user_id
ON user_document_connections(user_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_doc_connections_document_id
ON user_document_connections(document_id);

COMMENT ON INDEX idx_user_doc_connections_user_id IS
'Optimizes user connection queries (Task 43.3)';

COMMENT ON INDEX idx_user_doc_connections_document_id IS
'Optimizes document connection queries (Task 43.3)';

-- ============================================================================
-- Statistics Update
-- ============================================================================

-- Update table statistics for query planner optimization
ANALYZE documents_v2;
ANALYZE record_manager_v2;
ANALYZE chat_sessions;
ANALYZE chat_messages;
ANALYZE knowledge_entities;
ANALYZE knowledge_relationships;
ANALYZE user_memory_nodes;
ANALYZE user_memory_edges;
ANALYZE query_performance_log;
ANALYZE document_feedback;
ANALYZE error_logs;
ANALYZE audit_logs;
ANALYZE tabular_document_rows;
ANALYZE user_document_connections;

-- ============================================================================
-- Index Validation
-- ============================================================================

-- Query to check index sizes and usage
-- Run this after migration to verify index creation

/*
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size,
    idx_scan as times_used,
    idx_tup_read as rows_read,
    idx_tup_fetch as rows_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND indexname LIKE 'idx_%'
ORDER BY pg_relation_size(indexname::regclass) DESC;
*/

-- ============================================================================
-- Performance Tuning Recommendations
-- ============================================================================

-- For vector similarity search, set runtime parameters:
-- SET hnsw.ef_search = 40;  -- Adjust based on recall/speed tradeoff

-- For connection pooling (set in postgresql.conf or connection string):
-- max_connections = 100
-- shared_buffers = 256MB  -- 25% of RAM
-- effective_cache_size = 1GB  -- 75% of RAM
-- work_mem = 16MB  -- Per query operation
-- maintenance_work_mem = 128MB  -- For VACUUM, CREATE INDEX

-- For query optimization:
-- random_page_cost = 1.1  -- SSD optimization
-- effective_io_concurrency = 200  -- SSD optimization

-- ============================================================================
-- Migration Complete
-- ============================================================================

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Performance indexes migration complete (Task 43.3)';
    RAISE NOTICE 'Run ANALYZE to update query planner statistics';
    RAISE NOTICE 'Monitor pg_stat_user_indexes to validate index usage';
END $$;
