-- Empire v7.3 - Full-Text Search Functions
-- PostgreSQL BM25-like search using ts_rank_cd

-- Prerequisites: chunks table must have tsvector column for full-text search
-- Add tsvector column to chunks table if not exists
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS content_tsv tsvector;

-- Create GIN index for fast full-text search
CREATE INDEX IF NOT EXISTS idx_chunks_content_tsv ON chunks USING GIN(content_tsv);

-- Trigger to auto-update tsvector when content changes
CREATE OR REPLACE FUNCTION update_chunks_tsv()
RETURNS TRIGGER AS $$
BEGIN
    NEW.content_tsv = to_tsvector('english', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_chunks_tsv
    BEFORE INSERT OR UPDATE OF content ON chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_chunks_tsv();

-- Backfill existing chunks (run once after adding tsvector column)
-- UPDATE chunks SET content_tsv = to_tsvector('english', COALESCE(content, ''));

-- Function: bm25_search
-- BM25-like full-text search using PostgreSQL ts_rank_cd
CREATE OR REPLACE FUNCTION bm25_search(
    search_query text,
    match_threshold float DEFAULT 0.1,
    match_count int DEFAULT 20,
    filter_namespace text DEFAULT NULL,
    filter_metadata jsonb DEFAULT NULL
)
RETURNS TABLE (
    chunk_id uuid,
    content text,
    file_id uuid,
    metadata jsonb,
    bm25_score float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id as chunk_id,
        c.content,
        c.file_id,
        c.metadata,
        ts_rank_cd(
            c.content_tsv,
            plainto_tsquery('english', search_query),
            32  -- BM25-like normalization flag
        ) as bm25_score
    FROM chunks c
    WHERE c.content_tsv @@ plainto_tsquery('english', search_query)
      AND (filter_namespace IS NULL OR c.namespace = filter_namespace)
      AND (filter_metadata IS NULL OR c.metadata @> filter_metadata)
      AND ts_rank_cd(
          c.content_tsv,
          plainto_tsquery('english', search_query),
          32
      ) >= match_threshold
    ORDER BY bm25_score DESC
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION bm25_search IS 'BM25-like full-text search using PostgreSQL ts_rank_cd';

-- Function: hybrid_text_search
-- Combined exact phrase and fuzzy search
CREATE OR REPLACE FUNCTION hybrid_text_search(
    search_query text,
    use_fuzzy boolean DEFAULT true,
    match_threshold float DEFAULT 0.1,
    match_count int DEFAULT 20,
    filter_namespace text DEFAULT NULL
)
RETURNS TABLE (
    chunk_id uuid,
    content text,
    file_id uuid,
    metadata jsonb,
    search_score float,
    search_type text
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF use_fuzzy THEN
        -- Fuzzy search using trigram similarity
        RETURN QUERY
        SELECT
            c.id as chunk_id,
            c.content,
            c.file_id,
            c.metadata,
            similarity(c.content, search_query) as search_score,
            'fuzzy'::text as search_type
        FROM chunks c
        WHERE c.content % search_query  -- % is trigram similarity operator
          AND (filter_namespace IS NULL OR c.namespace = filter_namespace)
          AND similarity(c.content, search_query) >= match_threshold
        ORDER BY search_score DESC
        LIMIT match_count;
    ELSE
        -- Exact full-text search
        RETURN QUERY
        SELECT
            c.id as chunk_id,
            c.content,
            c.file_id,
            c.metadata,
            ts_rank_cd(
                c.content_tsv,
                plainto_tsquery('english', search_query),
                32
            ) as search_score,
            'exact'::text as search_type
        FROM chunks c
        WHERE c.content_tsv @@ plainto_tsquery('english', search_query)
          AND (filter_namespace IS NULL OR c.namespace = filter_namespace)
        ORDER BY search_score DESC
        LIMIT match_count;
    END IF;
END;
$$;

COMMENT ON FUNCTION hybrid_text_search IS 'Combined exact phrase and fuzzy full-text search';

-- Function: multi_field_search
-- Search across content, title, and metadata
CREATE OR REPLACE FUNCTION multi_field_search(
    search_query text,
    search_fields text[] DEFAULT ARRAY['content'],
    match_count int DEFAULT 20,
    boost_weights float[] DEFAULT ARRAY[1.0]
)
RETURNS TABLE (
    chunk_id uuid,
    content text,
    file_id uuid,
    metadata jsonb,
    combined_score float
)
LANGUAGE plpgsql
AS $$
DECLARE
    query_tsquery tsquery := plainto_tsquery('english', search_query);
BEGIN
    RETURN QUERY
    SELECT
        c.id as chunk_id,
        c.content,
        c.file_id,
        c.metadata,
        (
            COALESCE(
                CASE WHEN 'content' = ANY(search_fields)
                    THEN ts_rank_cd(c.content_tsv, query_tsquery) * boost_weights[1]
                    ELSE 0
                END, 0
            ) +
            COALESCE(
                CASE WHEN 'metadata' = ANY(search_fields)
                    THEN ts_rank_cd(to_tsvector('english', c.metadata::text), query_tsquery) * boost_weights[2]
                    ELSE 0
                END, 0
            )
        ) as combined_score
    FROM chunks c
    WHERE (
        ('content' = ANY(search_fields) AND c.content_tsv @@ query_tsquery)
        OR
        ('metadata' = ANY(search_fields) AND to_tsvector('english', c.metadata::text) @@ query_tsquery)
    )
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION multi_field_search IS 'Search across multiple fields with configurable boost weights';

-- Enable pg_trgm extension for fuzzy matching (if not already enabled)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create trigram index for fuzzy search
CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON chunks USING GIN(content gin_trgm_ops);

-- Example usage:

-- Basic BM25 search
-- SELECT * FROM bm25_search('insurance policy california', 0.1, 10);

-- Fuzzy text search
-- SELECT * FROM hybrid_text_search('insurence policey', true, 0.3, 10);

-- Multi-field search with boosting
-- SELECT * FROM multi_field_search(
--     'contract terms',
--     ARRAY['content', 'metadata'],
--     20,
--     ARRAY[1.0, 0.5]  -- Content boost = 1.0, metadata boost = 0.5
-- );

-- Search with namespace and metadata filtering
-- SELECT * FROM bm25_search(
--     'employee benefits',
--     0.1,
--     10,
--     'production',
--     '{"document_type": "policy"}'::jsonb
-- );
