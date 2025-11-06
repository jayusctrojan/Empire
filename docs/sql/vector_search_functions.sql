-- Empire v7.3 - Vector Search RPC Functions
-- Optimized server-side vector similarity search functions for pgvector

-- Function: match_embeddings
-- Finds similar embeddings using HNSW index with optional filters
CREATE OR REPLACE FUNCTION match_embeddings(
    query_embedding vector(1024),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 10,
    filter_namespace text DEFAULT NULL,
    filter_model text DEFAULT NULL
)
RETURNS TABLE (
    chunk_id uuid,
    content_hash varchar,
    embedding vector(1024),
    model varchar,
    namespace varchar,
    metadata jsonb,
    created_at timestamptz,
    similarity float
)
LANGUAGE plpgsql
AS $$
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
        1 - (e.embedding <=> query_embedding) as similarity
    FROM embeddings_cache e
    WHERE (filter_namespace IS NULL OR e.namespace = filter_namespace)
      AND (filter_model IS NULL OR e.model = filter_model)
      AND 1 - (e.embedding <=> query_embedding) >= match_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION match_embeddings IS 'Find similar embeddings using cosine similarity with HNSW index';

-- Function: match_embeddings_with_metadata
-- Enhanced version with metadata filtering
CREATE OR REPLACE FUNCTION match_embeddings_with_metadata(
    query_embedding vector(1024),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 10,
    filter_namespace text DEFAULT NULL,
    filter_model text DEFAULT NULL,
    metadata_filters jsonb DEFAULT NULL
)
RETURNS TABLE (
    chunk_id uuid,
    content_hash varchar,
    embedding vector(1024),
    model varchar,
    namespace varchar,
    metadata jsonb,
    created_at timestamptz,
    similarity float
)
LANGUAGE plpgsql
AS $$
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
        1 - (e.embedding <=> query_embedding) as similarity
    FROM embeddings_cache e
    WHERE (filter_namespace IS NULL OR e.namespace = filter_namespace)
      AND (filter_model IS NULL OR e.model = filter_model)
      AND (metadata_filters IS NULL OR e.metadata @> metadata_filters)
      AND 1 - (e.embedding <=> query_embedding) >= match_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION match_embeddings_with_metadata IS 'Find similar embeddings with metadata filtering support';

-- Function: get_namespace_stats
-- Get statistics for a specific namespace
CREATE OR REPLACE FUNCTION get_namespace_stats(
    target_namespace text DEFAULT 'default'
)
RETURNS TABLE (
    namespace varchar,
    total_embeddings bigint,
    unique_models bigint,
    avg_dimensions numeric,
    oldest_entry timestamptz,
    newest_entry timestamptz
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        target_namespace::varchar as namespace,
        COUNT(*)::bigint as total_embeddings,
        COUNT(DISTINCT model)::bigint as unique_models,
        ROUND(AVG(dimensions), 2) as avg_dimensions,
        MIN(created_at) as oldest_entry,
        MAX(created_at) as newest_entry
    FROM embeddings_cache
    WHERE embeddings_cache.namespace = target_namespace
    GROUP BY target_namespace;
END;
$$;

COMMENT ON FUNCTION get_namespace_stats IS 'Get statistics for a specific namespace';

-- Function: bulk_upsert_embeddings
-- Optimized bulk upsert for embedding batches
-- Note: This is a template - actual implementation depends on Supabase version
CREATE OR REPLACE FUNCTION bulk_upsert_embeddings(
    embeddings_data jsonb
)
RETURNS TABLE (
    inserted_count int,
    updated_count int
)
LANGUAGE plpgsql
AS $$
DECLARE
    inserted int := 0;
    updated int := 0;
BEGIN
    -- Insert with ON CONFLICT UPDATE
    WITH upsert_result AS (
        INSERT INTO embeddings_cache (
            content_hash,
            chunk_id,
            embedding,
            model,
            dimensions,
            namespace,
            metadata
        )
        SELECT
            (item->>'content_hash')::varchar,
            (item->>'chunk_id')::uuid,
            (item->>'embedding')::vector(1024),
            (item->>'model')::varchar,
            (item->>'dimensions')::integer,
            COALESCE((item->>'namespace')::varchar, 'default'),
            COALESCE((item->>'metadata')::jsonb, '{}'::jsonb)
        FROM jsonb_array_elements(embeddings_data) AS item
        ON CONFLICT (content_hash, model, namespace)
        DO UPDATE SET
            embedding = EXCLUDED.embedding,
            chunk_id = EXCLUDED.chunk_id,
            dimensions = EXCLUDED.dimensions,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING
            CASE WHEN xmax = 0 THEN 1 ELSE 0 END as is_insert
    )
    SELECT
        COUNT(*) FILTER (WHERE is_insert = 1)::int,
        COUNT(*) FILTER (WHERE is_insert = 0)::int
    INTO inserted, updated
    FROM upsert_result;

    RETURN QUERY SELECT inserted, updated;
END;
$$;

COMMENT ON FUNCTION bulk_upsert_embeddings IS 'Bulk insert or update embeddings from JSONB array';

-- Example usage queries

-- Basic similarity search
-- SELECT * FROM match_embeddings(
--     '[0.1, 0.2, ...]'::vector(1024),
--     0.75,  -- threshold
--     10,    -- limit
--     'production',  -- namespace
--     'bge-m3'      -- model
-- );

-- Search with metadata filtering
-- SELECT * FROM match_embeddings_with_metadata(
--     '[0.1, 0.2, ...]'::vector(1024),
--     0.7,
--     10,
--     'legal-docs',
--     'text-embedding-3-small',
--     '{"document_type": "contract", "status": "active"}'::jsonb
-- );

-- Get namespace statistics
-- SELECT * FROM get_namespace_stats('production');

-- Bulk upsert
-- SELECT * FROM bulk_upsert_embeddings('[
--     {
--         "content_hash": "abc123...",
--         "chunk_id": "uuid-here",
--         "embedding": [0.1, 0.2, ...],
--         "model": "bge-m3",
--         "dimensions": 1024,
--         "namespace": "production",
--         "metadata": {"doc_type": "policy"}
--     }
-- ]'::jsonb);
