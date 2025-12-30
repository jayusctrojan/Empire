-- Empire v7.3 - Task 27: Hybrid Search Migration
-- Creates PostgreSQL full-text search capabilities, BM25-like ranking,
-- and vector similarity RPC functions for hybrid search

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For fuzzy matching
CREATE EXTENSION IF NOT EXISTS vector;    -- For vector similarity (already enabled)

-- ============================================================================
-- STEP 1: Add tsvector column to chunks table for full-text search
-- ============================================================================

-- Add tsvector column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chunks' AND column_name = 'content_tsv'
    ) THEN
        ALTER TABLE chunks ADD COLUMN content_tsv tsvector;
    END IF;
END $$;

-- Create GIN index for fast full-text search
CREATE INDEX IF NOT EXISTS idx_chunks_content_tsv ON chunks USING GIN (content_tsv);

-- Create trigram index for fuzzy search
CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON chunks USING GIN (content gin_trgm_ops);

-- Function to generate tsvector from content (called on insert/update)
CREATE OR REPLACE FUNCTION chunks_content_trigger()
RETURNS TRIGGER AS $$
BEGIN
    NEW.content_tsv := to_tsvector('english', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-generate tsvector
DROP TRIGGER IF EXISTS trgm_chunks_content_tsv ON chunks;
CREATE TRIGGER trgm_chunks_content_tsv
    BEFORE INSERT OR UPDATE ON chunks
    FOR EACH ROW
    EXECUTE FUNCTION chunks_content_trigger();

-- Backfill existing chunks with tsvector
UPDATE chunks SET content_tsv = to_tsvector('english', COALESCE(content, ''))
WHERE content_tsv IS NULL;

-- ============================================================================
-- STEP 2: Create BM25-like full-text search function
-- ============================================================================

-- Function for BM25-like full-text search using ts_rank_cd
CREATE OR REPLACE FUNCTION search_chunks_bm25(
    search_query TEXT,
    match_limit INTEGER DEFAULT 20,
    min_rank FLOAT DEFAULT 0.0,
    filter_namespace TEXT DEFAULT NULL,
    filter_metadata JSONB DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    content TEXT,
    rank FLOAT,
    metadata JSONB,
    file_id UUID
) AS $$
DECLARE
    tsquery_obj tsquery;
BEGIN
    -- Convert search query to tsquery
    -- Use plainto_tsquery for simple queries, websearch_to_tsquery for advanced
    tsquery_obj := plainto_tsquery('english', search_query);

    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.content,
        ts_rank_cd(c.content_tsv, tsquery_obj, 32) AS rank,  -- 32 = normalization by document length
        c.metadata,
        c.file_id
    FROM chunks c
    WHERE c.content_tsv @@ tsquery_obj
      AND ts_rank_cd(c.content_tsv, tsquery_obj, 32) >= min_rank
      AND (filter_namespace IS NULL OR c.metadata->>'namespace' = filter_namespace)
      AND (filter_metadata IS NULL OR c.metadata @> filter_metadata)
    ORDER BY rank DESC
    LIMIT match_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_chunks_bm25 IS 'BM25-like full-text search using PostgreSQL ts_rank_cd';

-- ============================================================================
-- STEP 3: Create fuzzy search function using trigrams
-- ============================================================================

CREATE OR REPLACE FUNCTION search_chunks_fuzzy(
    search_query TEXT,
    match_limit INTEGER DEFAULT 20,
    min_similarity FLOAT DEFAULT 0.3,
    filter_namespace TEXT DEFAULT NULL,
    filter_metadata JSONB DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    content TEXT,
    similarity FLOAT,
    metadata JSONB,
    file_id UUID
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.content,
        similarity(c.content, search_query) AS similarity,
        c.metadata,
        c.file_id
    FROM chunks c
    WHERE similarity(c.content, search_query) >= min_similarity
      AND (filter_namespace IS NULL OR c.metadata->>'namespace' = filter_namespace)
      AND (filter_metadata IS NULL OR c.metadata @> filter_metadata)
    ORDER BY similarity DESC
    LIMIT match_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_chunks_fuzzy IS 'Fuzzy search using PostgreSQL trigram similarity';

-- ============================================================================
-- STEP 4: Create vector similarity search RPC function
-- ============================================================================

CREATE OR REPLACE FUNCTION match_embeddings(
    query_embedding vector(1024),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INTEGER DEFAULT 10,
    filter_namespace TEXT DEFAULT NULL,
    filter_model TEXT DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    content_hash VARCHAR,
    embedding vector(1024),
    model VARCHAR,
    namespace VARCHAR,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.chunk_id,
        e.content_hash,
        e.embedding,
        e.model,
        e.namespace,
        e.metadata,
        e.created_at,
        1 - (e.embedding <=> query_embedding) AS similarity
    FROM embeddings_cache e
    WHERE (filter_namespace IS NULL OR e.namespace = filter_namespace)
      AND (filter_model IS NULL OR e.model = filter_model)
      AND 1 - (e.embedding <=> query_embedding) >= match_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION match_embeddings IS 'Vector similarity search using pgvector cosine distance';

-- ============================================================================
-- STEP 5: Create hybrid search function combining all methods with RRF
-- ============================================================================

CREATE OR REPLACE FUNCTION hybrid_search(
    search_query TEXT,
    query_embedding vector(1024),
    match_limit INTEGER DEFAULT 10,
    -- Dense search parameters
    dense_weight FLOAT DEFAULT 0.5,
    dense_threshold FLOAT DEFAULT 0.5,
    dense_count INTEGER DEFAULT 20,
    -- Sparse search parameters
    sparse_weight FLOAT DEFAULT 0.3,
    sparse_threshold FLOAT DEFAULT 0.0,
    sparse_count INTEGER DEFAULT 20,
    -- Fuzzy search parameters
    fuzzy_weight FLOAT DEFAULT 0.2,
    fuzzy_threshold FLOAT DEFAULT 0.3,
    fuzzy_count INTEGER DEFAULT 20,
    -- RRF parameter
    rrf_k INTEGER DEFAULT 60,
    -- Filters
    filter_namespace TEXT DEFAULT NULL,
    filter_metadata JSONB DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    content TEXT,
    rrf_score FLOAT,
    dense_score FLOAT,
    sparse_score FLOAT,
    fuzzy_score FLOAT,
    metadata JSONB,
    file_id UUID
) AS $$
WITH
-- Dense vector search results
dense_results AS (
    SELECT
        e.chunk_id,
        c.content,
        c.metadata,
        c.file_id,
        1 - (e.embedding <=> query_embedding) AS score,
        ROW_NUMBER() OVER (ORDER BY e.embedding <=> query_embedding) AS rank
    FROM embeddings_cache e
    JOIN chunks c ON e.chunk_id = c.id
    WHERE 1 - (e.embedding <=> query_embedding) >= dense_threshold
      AND (filter_namespace IS NULL OR e.namespace = filter_namespace)
    ORDER BY e.embedding <=> query_embedding
    LIMIT dense_count
),
-- Sparse BM25 search results
sparse_results AS (
    SELECT
        c.id AS chunk_id,
        c.content,
        c.metadata,
        c.file_id,
        ts_rank_cd(c.content_tsv, plainto_tsquery('english', search_query), 32) AS score,
        ROW_NUMBER() OVER (ORDER BY ts_rank_cd(c.content_tsv, plainto_tsquery('english', search_query), 32) DESC) AS rank
    FROM chunks c
    WHERE c.content_tsv @@ plainto_tsquery('english', search_query)
      AND ts_rank_cd(c.content_tsv, plainto_tsquery('english', search_query), 32) >= sparse_threshold
      AND (filter_namespace IS NULL OR c.metadata->>'namespace' = filter_namespace)
      AND (filter_metadata IS NULL OR c.metadata @> filter_metadata)
    ORDER BY score DESC
    LIMIT sparse_count
),
-- Fuzzy trigram search results
fuzzy_results AS (
    SELECT
        c.id AS chunk_id,
        c.content,
        c.metadata,
        c.file_id,
        similarity(c.content, search_query) AS score,
        ROW_NUMBER() OVER (ORDER BY similarity(c.content, search_query) DESC) AS rank
    FROM chunks c
    WHERE similarity(c.content, search_query) >= fuzzy_threshold
      AND (filter_namespace IS NULL OR c.metadata->>'namespace' = filter_namespace)
      AND (filter_metadata IS NULL OR c.metadata @> filter_metadata)
    ORDER BY score DESC
    LIMIT fuzzy_count
),
-- Combine all unique chunk_ids
all_chunks AS (
    SELECT DISTINCT chunk_id, content, metadata, file_id
    FROM (
        SELECT chunk_id, content, metadata, file_id FROM dense_results
        UNION
        SELECT chunk_id, content, metadata, file_id FROM sparse_results
        UNION
        SELECT chunk_id, content, metadata, file_id FROM fuzzy_results
    ) combined
),
-- Calculate RRF scores
rrf_scores AS (
    SELECT
        ac.chunk_id,
        ac.content,
        ac.metadata,
        ac.file_id,
        -- RRF formula: weight / (k + rank)
        COALESCE(dense_weight / (rrf_k + dr.rank), 0) +
        COALESCE(sparse_weight / (rrf_k + sr.rank), 0) +
        COALESCE(fuzzy_weight / (rrf_k + fr.rank), 0) AS rrf_score,
        dr.score AS dense_score,
        sr.score AS sparse_score,
        fr.score AS fuzzy_score
    FROM all_chunks ac
    LEFT JOIN dense_results dr ON ac.chunk_id = dr.chunk_id
    LEFT JOIN sparse_results sr ON ac.chunk_id = sr.chunk_id
    LEFT JOIN fuzzy_results fr ON ac.chunk_id = fr.chunk_id
)
SELECT
    rs.chunk_id,
    rs.content,
    rs.rrf_score,
    rs.dense_score,
    rs.sparse_score,
    rs.fuzzy_score,
    rs.metadata,
    rs.file_id
FROM rrf_scores rs
ORDER BY rs.rrf_score DESC
LIMIT match_limit;
$$ LANGUAGE SQL;

COMMENT ON FUNCTION hybrid_search IS 'Hybrid search combining dense, sparse, and fuzzy search with Reciprocal Rank Fusion';

-- ============================================================================
-- STEP 6: Create ILIKE pattern search function
-- ============================================================================

CREATE OR REPLACE FUNCTION search_chunks_ilike(
    search_pattern TEXT,
    match_limit INTEGER DEFAULT 20,
    filter_namespace TEXT DEFAULT NULL,
    filter_metadata JSONB DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    content TEXT,
    metadata JSONB,
    file_id UUID
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.content,
        c.metadata,
        c.file_id
    FROM chunks c
    WHERE c.content ILIKE '%' || search_pattern || '%'
      AND (filter_namespace IS NULL OR c.metadata->>'namespace' = filter_namespace)
      AND (filter_metadata IS NULL OR c.metadata @> filter_metadata)
    LIMIT match_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_chunks_ilike IS 'Case-insensitive pattern matching search';

-- ============================================================================
-- STEP 7: Create search statistics function
-- ============================================================================

CREATE OR REPLACE FUNCTION get_search_stats()
RETURNS TABLE (
    total_chunks BIGINT,
    chunks_with_tsv BIGINT,
    total_embeddings BIGINT,
    unique_namespaces BIGINT,
    avg_content_length NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        (SELECT COUNT(*) FROM chunks)::BIGINT AS total_chunks,
        (SELECT COUNT(*) FROM chunks WHERE content_tsv IS NOT NULL)::BIGINT AS chunks_with_tsv,
        (SELECT COUNT(*) FROM embeddings_cache)::BIGINT AS total_embeddings,
        (SELECT COUNT(DISTINCT namespace) FROM embeddings_cache)::BIGINT AS unique_namespaces,
        (SELECT ROUND(AVG(LENGTH(content))::NUMERIC, 2) FROM chunks) AS avg_content_length;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_search_stats IS 'Get statistics about searchable content';

-- ============================================================================
-- STEP 8: Create index usage hints for query optimization
-- ============================================================================

-- Add composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_chunks_namespace_content ON chunks USING GIN (content_tsv)
WHERE metadata->>'namespace' IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_embeddings_namespace_model ON embeddings_cache(namespace, model);

-- Add statistics comment
COMMENT ON INDEX idx_chunks_content_tsv IS 'GIN index for full-text search on chunks';
COMMENT ON INDEX idx_chunks_content_trgm IS 'GIN trigram index for fuzzy search on chunks';
