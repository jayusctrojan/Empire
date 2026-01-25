-- Empire v7.3 - Task 26: Embeddings Cache Table Migration
-- Creates the embeddings_cache table for BGE-M3 embedding storage
-- Supports vector similarity search with pgvector extension

-- Enable pgvector extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create embeddings_cache table
CREATE TABLE IF NOT EXISTS embeddings_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content identification
    content_hash VARCHAR(64) NOT NULL,  -- SHA-256 hash of content
    chunk_id UUID,  -- Reference to chunks table (soft reference, no FK to handle both chunks/document_chunks)

    -- Embedding data
    embedding vector(1024),  -- Default for BGE-M3 (1024 dimensions)
    model VARCHAR(100) NOT NULL,  -- e.g., "bge-m3", "text-embedding-3-small"
    dimensions INTEGER NOT NULL DEFAULT 1024,

    -- Namespace for multi-tenant/segmented storage
    namespace VARCHAR(255) DEFAULT 'default',

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unique constraint: one embedding per content+model+namespace combination
    CONSTRAINT unique_content_model_namespace UNIQUE (content_hash, model, namespace)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_embeddings_cache_content_hash ON embeddings_cache(content_hash);
CREATE INDEX IF NOT EXISTS idx_embeddings_cache_chunk_id ON embeddings_cache(chunk_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_cache_model ON embeddings_cache(model);
CREATE INDEX IF NOT EXISTS idx_embeddings_cache_namespace ON embeddings_cache(namespace);
CREATE INDEX IF NOT EXISTS idx_embeddings_cache_created_at ON embeddings_cache(created_at DESC);

-- Composite index for namespace + model queries (common access pattern)
CREATE INDEX IF NOT EXISTS idx_embeddings_cache_namespace_model ON embeddings_cache(namespace, model);

-- Vector similarity search index (HNSW for fast approximate search)
CREATE INDEX IF NOT EXISTS idx_embeddings_cache_embedding_hnsw
    ON embeddings_cache USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_embeddings_cache_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
DROP TRIGGER IF EXISTS trigger_update_embeddings_cache_updated_at ON embeddings_cache;
CREATE TRIGGER trigger_update_embeddings_cache_updated_at
    BEFORE UPDATE ON embeddings_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_embeddings_cache_updated_at();

-- Row Level Security (RLS) policies
ALTER TABLE embeddings_cache ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read all embeddings
CREATE POLICY "Users can view all embeddings"
    ON embeddings_cache FOR SELECT
    USING (true);

-- Policy: Service role can insert embeddings
CREATE POLICY "Service role can insert embeddings"
    ON embeddings_cache FOR INSERT
    WITH CHECK (true);

-- Policy: Service role can update embeddings
CREATE POLICY "Service role can update embeddings"
    ON embeddings_cache FOR UPDATE
    USING (true)
    WITH CHECK (true);

-- Policy: Service role can delete embeddings
CREATE POLICY "Service role can delete embeddings"
    ON embeddings_cache FOR DELETE
    USING (true);

-- Comments for documentation
COMMENT ON TABLE embeddings_cache IS 'Cached embeddings with content hash-based deduplication for Empire v7.3';
COMMENT ON COLUMN embeddings_cache.content_hash IS 'SHA-256 hash of the content for deduplication';
COMMENT ON COLUMN embeddings_cache.embedding IS 'Vector embedding (default 1024 dimensions for BGE-M3)';
COMMENT ON COLUMN embeddings_cache.model IS 'Embedding model used (e.g., bge-m3, text-embedding-3-small)';
COMMENT ON COLUMN embeddings_cache.namespace IS 'Logical namespace for multi-tenant or segmented storage';
COMMENT ON COLUMN embeddings_cache.metadata IS 'Additional metadata about the embedding generation';
COMMENT ON COLUMN embeddings_cache.last_accessed_at IS 'Timestamp of last cache access for LRU eviction';

-- Utility function to clean up old cache entries
CREATE OR REPLACE FUNCTION cleanup_old_embeddings_cache(days_old INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM embeddings_cache
    WHERE created_at < NOW() - (days_old || ' days')::INTERVAL
    AND last_accessed_at < NOW() - (days_old || ' days')::INTERVAL;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_embeddings_cache IS 'Delete cache entries older than specified days (default 90)';

-- Utility function to get cache statistics
CREATE OR REPLACE FUNCTION get_embeddings_cache_stats()
RETURNS TABLE (
    total_embeddings BIGINT,
    total_size_mb NUMERIC,
    models_count BIGINT,
    oldest_entry TIMESTAMPTZ,
    newest_entry TIMESTAMPTZ,
    avg_dimension INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_embeddings,
        ROUND(pg_total_relation_size('embeddings_cache') / 1024.0 / 1024.0, 2) as total_size_mb,
        COUNT(DISTINCT model)::BIGINT as models_count,
        MIN(created_at) as oldest_entry,
        MAX(created_at) as newest_entry,
        ROUND(AVG(dimensions))::INTEGER as avg_dimension
    FROM embeddings_cache;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_embeddings_cache_stats IS 'Get statistics about the embeddings cache';

-- Function to refresh embedding index (called from Celery tasks)
CREATE OR REPLACE FUNCTION refresh_embedding_index()
RETURNS BOOLEAN AS $$
BEGIN
    -- REINDEX is safe for HNSW indexes
    REINDEX INDEX CONCURRENTLY idx_embeddings_cache_embedding_hnsw;
    RETURN TRUE;
EXCEPTION
    WHEN OTHERS THEN
        -- Log error but don't fail
        RAISE WARNING 'Failed to refresh embedding index: %', SQLERRM;
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_embedding_index IS 'Refresh the HNSW vector index for optimal search performance';
