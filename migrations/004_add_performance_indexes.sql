-- Empire v7.3 - Performance Indexes
-- Database optimization for common queries
--
-- Usage:
--   Run this migration on Supabase PostgreSQL to improve query performance
--   supabase db push or apply via Supabase dashboard
--
-- Note: All index creations are wrapped in IF EXISTS checks for table safety.

-- =============================================================================
-- CHAT SESSION INDEXES (if table exists)
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_sessions') THEN
        -- Index for user's chat sessions (most common query)
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_sessions' AND column_name = 'user_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions (user_id)';
        END IF;

        -- Index for recent sessions per user
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_sessions' AND column_name = 'user_id')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_sessions' AND column_name = 'updated_at') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated ON chat_sessions (user_id, updated_at DESC)';
        END IF;

        -- Index for session lookup by ID with status (only if status column exists)
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_sessions' AND column_name = 'status') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_chat_sessions_id_status ON chat_sessions (id, status) WHERE status = ''active''';
        END IF;
    END IF;
END $$;

-- =============================================================================
-- CHAT MESSAGES INDEXES (if table exists)
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_messages') THEN
        -- Index for messages in a session (ordered)
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_messages' AND column_name = 'session_id')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_messages' AND column_name = 'created_at') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created ON chat_messages (session_id, created_at DESC)';
        END IF;

        -- Index for messages by user
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_messages' AND column_name = 'user_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages (user_id)';
        END IF;
    END IF;
END $$;

-- =============================================================================
-- DOCUMENTS INDEXES (if table exists)
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents_v2') THEN
        -- Index for documents by status (for processing queue)
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents_v2' AND column_name = 'status')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents_v2' AND column_name = 'created_at') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_documents_status_created ON documents_v2 (status, created_at) WHERE status IN (''pending'', ''processing'')';
        END IF;

        -- Index for user's documents
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents_v2' AND column_name = 'user_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents_v2 (user_id)';
        END IF;

        -- Index for document type filtering
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents_v2' AND column_name = 'document_type') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_documents_type ON documents_v2 (document_type)';
        END IF;
    END IF;
END $$;

-- =============================================================================
-- VECTOR SEARCH INDEXES (if pgvector extension and column exist)
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')
       AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents_v2')
       AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents_v2' AND column_name = 'embedding') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_embedding_hnsw') THEN
            EXECUTE 'CREATE INDEX idx_documents_embedding_hnsw ON documents_v2 USING hnsw (embedding vector_cosine_ops)';
        END IF;
    END IF;
END $$;

-- =============================================================================
-- KNOWLEDGE ENTITY INDEXES (if table exists)
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'knowledge_entities') THEN
        -- Index for entity lookup by type
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'knowledge_entities' AND column_name = 'entity_type') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_knowledge_entities_type ON knowledge_entities (entity_type)';
        END IF;

        -- Index for entity name search
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'knowledge_entities' AND column_name = 'name') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_knowledge_entities_name ON knowledge_entities (name)';
        END IF;

        -- Index for document association
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'knowledge_entities' AND column_name = 'document_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_knowledge_entities_doc ON knowledge_entities (document_id)';
        END IF;
    END IF;
END $$;

-- =============================================================================
-- QUERY PERFORMANCE LOG INDEXES (if table exists)
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'query_performance_log') THEN
        -- Index for performance analysis by time
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'query_performance_log' AND column_name = 'created_at') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_query_perf_log_created ON query_performance_log (created_at DESC)';
        END IF;

        -- Index for slow query analysis
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'query_performance_log' AND column_name = 'duration_ms') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_query_perf_log_duration ON query_performance_log (duration_ms DESC) WHERE duration_ms > 1000';
        END IF;

        -- Index for query type analysis
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'query_performance_log' AND column_name = 'query_type') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_query_perf_log_type ON query_performance_log (query_type)';
        END IF;
    END IF;
END $$;

-- =============================================================================
-- AUDIT LOG INDEXES (if table exists)
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_logs') THEN
        -- Index for user activity lookup
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'user_id')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'created_at') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs (user_id, created_at DESC)';
        END IF;

        -- Index for event type filtering
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'event_type')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'created_at') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_audit_logs_event ON audit_logs (event_type, created_at DESC)';
        END IF;

        -- Index for resource-specific audits
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'resource_type')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'resource_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs (resource_type, resource_id)';
        END IF;
    END IF;
END $$;

-- =============================================================================
-- RECORD MANAGER INDEXES (if table exists)
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'record_manager_v2') THEN
        -- Index for record manager hash lookups
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'record_manager_v2' AND column_name = 'content_hash') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_record_manager_hash ON record_manager_v2 (content_hash)';
        END IF;

        -- Index for record manager document association
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'record_manager_v2' AND column_name = 'document_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_record_manager_doc ON record_manager_v2 (document_id)';
        END IF;
    END IF;
END $$;

-- =============================================================================
-- COMMENTS
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_chat_sessions_user_id') THEN
        EXECUTE 'COMMENT ON INDEX idx_chat_sessions_user_id IS ''Primary index for user session lookups''';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_status_created') THEN
        EXECUTE 'COMMENT ON INDEX idx_documents_status_created IS ''Index for processing queue queries''';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_query_perf_log_duration') THEN
        EXECUTE 'COMMENT ON INDEX idx_query_perf_log_duration IS ''Partial index for slow query analysis''';
    END IF;
END $$;
