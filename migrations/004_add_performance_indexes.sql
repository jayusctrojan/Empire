-- Empire v7.3 - Performance Indexes
-- Database optimization for common queries
--
-- Usage:
--   Run this migration on Supabase PostgreSQL to improve query performance
--   supabase db push or apply via Supabase dashboard
--
-- Note: CONCURRENTLY cannot be used in transactions.
-- Run these indexes individually if needed.

-- =============================================================================
-- CHAT SESSION INDEXES
-- =============================================================================

-- Index for user's chat sessions (most common query)
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id
ON chat_sessions (user_id);

-- Index for recent sessions per user
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated
ON chat_sessions (user_id, updated_at DESC);

-- Index for session lookup by ID with status
CREATE INDEX IF NOT EXISTS idx_chat_sessions_id_status
ON chat_sessions (id, status)
WHERE status = 'active';

-- =============================================================================
-- CHAT MESSAGES INDEXES
-- =============================================================================

-- Index for messages in a session (ordered)
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
ON chat_messages (session_id, created_at DESC);

-- Index for messages by user
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id
ON chat_messages (user_id);

-- =============================================================================
-- DOCUMENTS INDEXES
-- =============================================================================

-- Index for documents by status (for processing queue)
CREATE INDEX IF NOT EXISTS idx_documents_status_created
ON documents_v2 (status, created_at)
WHERE status IN ('pending', 'processing');

-- Index for user's documents
CREATE INDEX IF NOT EXISTS idx_documents_user_id
ON documents_v2 (user_id);

-- Index for document search by title (requires pg_trgm extension)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_title_trgm') THEN
            EXECUTE 'CREATE INDEX idx_documents_title_trgm ON documents_v2 USING gin (title gin_trgm_ops)';
        END IF;
    ELSE
        RAISE NOTICE 'pg_trgm extension not available, skipping trigram index on documents_v2.title';
    END IF;
END $$;

-- Index for document type filtering
CREATE INDEX IF NOT EXISTS idx_documents_type
ON documents_v2 (document_type);

-- =============================================================================
-- VECTOR SEARCH INDEXES
-- =============================================================================

-- HNSW index for embedding similarity search (fast approximate)
-- Only create if pgvector extension is available and column exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'vector'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents_v2' AND column_name = 'embedding'
    ) THEN
        -- Check if index already exists
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_embedding_hnsw'
        ) THEN
            EXECUTE 'CREATE INDEX idx_documents_embedding_hnsw ON documents_v2 USING hnsw (embedding vector_cosine_ops)';
        END IF;
    END IF;
END $$;

-- =============================================================================
-- KNOWLEDGE ENTITY INDEXES
-- =============================================================================

-- Indexes for knowledge_entities (if table exists)
-- Note: Cannot use CONCURRENTLY inside DO blocks/transactions
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'knowledge_entities') THEN
        -- Index for entity lookup by type
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_knowledge_entities_type') THEN
            EXECUTE 'CREATE INDEX idx_knowledge_entities_type ON knowledge_entities (entity_type)';
        END IF;

        -- Index for entity name search
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_knowledge_entities_name') THEN
            EXECUTE 'CREATE INDEX idx_knowledge_entities_name ON knowledge_entities (name)';
        END IF;

        -- Index for document association
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_knowledge_entities_doc') THEN
            EXECUTE 'CREATE INDEX idx_knowledge_entities_doc ON knowledge_entities (document_id)';
        END IF;
    END IF;
END $$;

-- =============================================================================
-- QUERY PERFORMANCE LOG INDEXES
-- =============================================================================

-- Index for performance analysis by time
CREATE INDEX IF NOT EXISTS idx_query_perf_log_created
ON query_performance_log (created_at DESC);

-- Index for slow query analysis
CREATE INDEX IF NOT EXISTS idx_query_perf_log_duration
ON query_performance_log (duration_ms DESC)
WHERE duration_ms > 1000;

-- Index for query type analysis
CREATE INDEX IF NOT EXISTS idx_query_perf_log_type
ON query_performance_log (query_type);

-- =============================================================================
-- AUDIT LOG INDEXES
-- =============================================================================

-- Index for user activity lookup
CREATE INDEX IF NOT EXISTS idx_audit_logs_user
ON audit_logs (user_id, created_at DESC);

-- Index for event type filtering
CREATE INDEX IF NOT EXISTS idx_audit_logs_event
ON audit_logs (event_type, created_at DESC);

-- Index for resource-specific audits
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource
ON audit_logs (resource_type, resource_id);

-- =============================================================================
-- RECORD MANAGER INDEXES
-- =============================================================================

-- Index for record manager hash lookups
CREATE INDEX IF NOT EXISTS idx_record_manager_hash
ON record_manager_v2 (content_hash);

-- Index for record manager document association
CREATE INDEX IF NOT EXISTS idx_record_manager_doc
ON record_manager_v2 (document_id);

-- =============================================================================
-- PARTIAL INDEXES FOR COMMON FILTERS
-- =============================================================================

-- Partial index for active documents only
CREATE INDEX IF NOT EXISTS idx_documents_active
ON documents_v2 (id, title, updated_at)
WHERE status = 'completed' AND deleted_at IS NULL;

-- Note: Partial index with NOW() becomes stale immediately after creation
-- Instead, use a regular index on (session_id, created_at) and filter in queries
-- Partial index for recent messages removed - use idx_chat_messages_session_created instead

-- =============================================================================
-- COMPOSITE INDEXES FOR COMMON JOINS
-- =============================================================================

-- Index for session + message queries
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_user
ON chat_messages (session_id, user_id, created_at DESC);

-- Index for document + status queries
CREATE INDEX IF NOT EXISTS idx_documents_user_status
ON documents_v2 (user_id, status, updated_at DESC);

-- =============================================================================
-- STATISTICS AND MAINTENANCE
-- =============================================================================

-- Analyze tables to update statistics after index creation
-- Run these manually after migration:
-- ANALYZE chat_sessions;
-- ANALYZE chat_messages;
-- ANALYZE documents_v2;
-- ANALYZE query_performance_log;
-- ANALYZE audit_logs;
-- ANALYZE record_manager_v2;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON INDEX idx_chat_sessions_user_id IS 'Primary index for user session lookups';
COMMENT ON INDEX idx_documents_status_created IS 'Index for processing queue queries';
COMMENT ON INDEX idx_query_perf_log_duration IS 'Partial index for slow query analysis';
