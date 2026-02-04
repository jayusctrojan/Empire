-- Performance Indexes for Empire v7.3
-- Task 43.3: Optimize and Re-Test for Throughput and Latency
--
-- This migration adds strategic indexes to improve query performance
-- based on load testing results and identified bottlenecks.
--
-- Note: All operations wrapped in IF EXISTS for safety.
--
-- Usage:
--   psql -d empire -f migrations/add_performance_indexes.sql

-- ============================================================================
-- Documents Table Indexes (if table exists)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents_v2') THEN
        -- User document lookups by status
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents_v2' AND column_name = 'user_id')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents_v2' AND column_name = 'processing_status') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_documents_user_id_status ON documents_v2(user_id, processing_status) WHERE processing_status IS NOT NULL';
        END IF;

        -- Recent documents query
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents_v2' AND column_name = 'created_at') THEN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents_v2' AND column_name = 'deleted_at') THEN
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents_v2(created_at DESC) WHERE deleted_at IS NULL';
            ELSE
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents_v2(created_at DESC)';
            END IF;
        END IF;

        -- Document type filtering
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents_v2' AND column_name = 'doc_type') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents_v2(doc_type) WHERE doc_type IS NOT NULL';
        END IF;

        -- HNSW vector search (if pgvector available)
        IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents_v2' AND column_name = 'embedding') THEN
            IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_embedding_hnsw') THEN
                EXECUTE 'CREATE INDEX idx_documents_embedding_hnsw ON documents_v2 USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64) WHERE embedding IS NOT NULL';
            END IF;
        END IF;
    END IF;
END $$;

-- ============================================================================
-- Record Manager Indexes (if table exists)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'record_manager_v2') THEN
        -- Fast duplicate detection
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'record_manager_v2' AND column_name = 'key')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'record_manager_v2' AND column_name = 'namespace') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_record_manager_key_namespace ON record_manager_v2(key, namespace)';
        END IF;

        -- Cleanup queries by timestamp
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'record_manager_v2' AND column_name = 'updated_at') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_record_manager_updated_at ON record_manager_v2(updated_at DESC)';
        END IF;
    END IF;
END $$;

-- ============================================================================
-- Chat Sessions and Messages (if tables exist)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_sessions') THEN
        -- User chat sessions (recent first)
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_sessions' AND column_name = 'user_id')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_sessions' AND column_name = 'updated_at') THEN
            -- Check if deleted_at column exists before using in WHERE clause
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_sessions' AND column_name = 'deleted_at') THEN
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id_updated ON chat_sessions(user_id, updated_at DESC) WHERE deleted_at IS NULL';
            ELSE
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id_updated ON chat_sessions(user_id, updated_at DESC)';
            END IF;
        END IF;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_messages') THEN
        -- Session messages (chronological order)
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_messages' AND column_name = 'session_id')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_messages' AND column_name = 'timestamp') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_chat_messages_session_timestamp ON chat_messages(session_id, timestamp DESC)';
        END IF;

        -- Message role filtering
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_messages' AND column_name = 'role') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_chat_messages_role ON chat_messages(role) WHERE role IS NOT NULL';
        END IF;
    END IF;
END $$;

-- ============================================================================
-- Knowledge Graph Entities and Relationships (if tables exist)
-- ============================================================================

DO $$
BEGIN
    -- Enable pg_trgm if not already enabled (for fuzzy text search)
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
        BEGIN
            EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_trgm';
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Could not create pg_trgm extension: %', SQLERRM;
        END;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'knowledge_entities') THEN
        -- Text search on entity names (trigram for fuzzy matching)
        IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'knowledge_entities' AND column_name = 'name') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_knowledge_entities_name_trgm ON knowledge_entities USING gin(name gin_trgm_ops)';
        END IF;

        -- Entity type filtering
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'knowledge_entities' AND column_name = 'entity_type') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_knowledge_entities_type ON knowledge_entities(entity_type) WHERE entity_type IS NOT NULL';
        END IF;

        -- Entity document references
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'knowledge_entities' AND column_name = 'document_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_knowledge_entities_document_id ON knowledge_entities(document_id) WHERE document_id IS NOT NULL';
        END IF;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'knowledge_relationships') THEN
        -- Relationship lookups (both directions)
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'knowledge_relationships' AND column_name = 'source_entity_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_knowledge_relationships_source ON knowledge_relationships(source_entity_id)';
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'knowledge_relationships' AND column_name = 'target_entity_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_knowledge_relationships_target ON knowledge_relationships(target_entity_id)';
        END IF;
    END IF;
END $$;

-- ============================================================================
-- User Memory Graph (if tables exist)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_memory_nodes') THEN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_memory_nodes' AND column_name = 'user_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_user_id ON user_memory_nodes(user_id)';
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_memory_nodes' AND column_name = 'node_type') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_type ON user_memory_nodes(node_type) WHERE node_type IS NOT NULL';
        END IF;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_memory_edges') THEN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_memory_edges' AND column_name = 'source_node_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_user_memory_edges_source ON user_memory_edges(source_node_id)';
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_memory_edges' AND column_name = 'target_node_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_user_memory_edges_target ON user_memory_edges(target_node_id)';
        END IF;
    END IF;
END $$;

-- ============================================================================
-- Performance Monitoring Tables (if exist)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'query_performance_log') THEN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'query_performance_log' AND column_name = 'timestamp') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_query_perf_log_timestamp ON query_performance_log(timestamp DESC)';
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'query_performance_log' AND column_name = 'endpoint')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'query_performance_log' AND column_name = 'timestamp') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_query_perf_log_endpoint_timestamp ON query_performance_log(endpoint, timestamp DESC)';
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'query_performance_log' AND column_name = 'user_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_query_perf_log_user_id ON query_performance_log(user_id) WHERE user_id IS NOT NULL';
        END IF;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'document_feedback') THEN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'document_feedback' AND column_name = 'document_id')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'document_feedback' AND column_name = 'created_at') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_document_feedback_document_created ON document_feedback(document_id, created_at DESC)';
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'document_feedback' AND column_name = 'user_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_document_feedback_user_id ON document_feedback(user_id)';
        END IF;
    END IF;
END $$;

-- ============================================================================
-- Error Logs and Audit Logs (if tables exist)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'error_logs') THEN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'error_logs' AND column_name = 'timestamp') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_error_logs_timestamp ON error_logs(timestamp DESC)';
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'error_logs' AND column_name = 'level') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_error_logs_level ON error_logs(level) WHERE level IS NOT NULL';
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'error_logs' AND column_name = 'endpoint') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_error_logs_endpoint ON error_logs(endpoint) WHERE endpoint IS NOT NULL';
        END IF;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_logs') THEN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'timestamp') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC)';
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'user_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id) WHERE user_id IS NOT NULL';
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'event_type') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type)';
        END IF;
    END IF;
END $$;

-- ============================================================================
-- Additional Tables (if exist)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tabular_document_rows') THEN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'tabular_document_rows' AND column_name = 'document_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_tabular_rows_document_id ON tabular_document_rows(document_id)';
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'tabular_document_rows' AND column_name = 'document_id')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'tabular_document_rows' AND column_name = 'row_number') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_tabular_rows_row_number ON tabular_document_rows(document_id, row_number)';
        END IF;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_document_connections') THEN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_document_connections' AND column_name = 'user_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_user_doc_connections_user_id ON user_document_connections(user_id)';
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_document_connections' AND column_name = 'document_id') THEN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_user_doc_connections_document_id ON user_document_connections(document_id)';
        END IF;
    END IF;
END $$;

-- ============================================================================
-- Statistics Update (safe - will skip non-existent tables)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents_v2') THEN
        EXECUTE 'ANALYZE documents_v2';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'record_manager_v2') THEN
        EXECUTE 'ANALYZE record_manager_v2';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_sessions') THEN
        EXECUTE 'ANALYZE chat_sessions';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_messages') THEN
        EXECUTE 'ANALYZE chat_messages';
    END IF;
END $$;

-- ============================================================================
-- Migration Complete
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Performance indexes migration complete (Task 43.3)';
END $$;
