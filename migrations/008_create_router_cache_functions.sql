-- Empire v7.3 - Router Cache RPC Functions
-- Creates database functions for agent router caching
--
-- Usage:
--   Run this migration on Supabase PostgreSQL
--   supabase db push or apply via Supabase dashboard

-- =============================================================================
-- ROUTER CACHE TABLE (if not exists)
-- =============================================================================

CREATE TABLE IF NOT EXISTS router_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash TEXT NOT NULL,
    query_text TEXT NOT NULL,
    query_embedding vector(1536),  -- For semantic similarity search
    routing_decision JSONB NOT NULL,
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    user_id UUID REFERENCES auth.users(id),

    CONSTRAINT router_cache_query_hash_unique UNIQUE (query_hash)
);

-- Index for hash lookups
CREATE INDEX IF NOT EXISTS idx_router_cache_query_hash
ON router_cache (query_hash);

-- Index for expiration cleanup
CREATE INDEX IF NOT EXISTS idx_router_cache_expires_at
ON router_cache (expires_at)
WHERE expires_at > NOW();

-- Index for semantic similarity search (if pgvector is available)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        CREATE INDEX IF NOT EXISTS idx_router_cache_embedding
        ON router_cache USING ivfflat (query_embedding vector_cosine_ops)
        WITH (lists = 100);
    END IF;
END $$;

-- =============================================================================
-- RPC FUNCTIONS
-- =============================================================================

-- Function to increment cache hit count
CREATE OR REPLACE FUNCTION increment_cache_hit(p_cache_id UUID)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE router_cache
    SET hit_count = hit_count + 1,
        updated_at = NOW()
    WHERE id = p_cache_id;
END;
$$;

-- Function to get cached routing with semantic similarity
CREATE OR REPLACE FUNCTION get_cached_routing(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.85,
    match_count int DEFAULT 1
)
RETURNS TABLE (
    cache_id UUID,
    query_text TEXT,
    routing_decision JSONB,
    similarity float,
    hit_count INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        rc.id as cache_id,
        rc.query_text,
        rc.routing_decision,
        1 - (rc.query_embedding <=> query_embedding) as similarity,
        rc.hit_count
    FROM router_cache rc
    WHERE rc.expires_at > NOW()
        AND rc.query_embedding IS NOT NULL
        AND 1 - (rc.query_embedding <=> query_embedding) >= match_threshold
    ORDER BY rc.query_embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE router_cache ENABLE ROW LEVEL SECURITY;

-- Service role can do everything
CREATE POLICY IF NOT EXISTS "Service role full access to router_cache"
ON router_cache
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Users can read their own cache entries
CREATE POLICY IF NOT EXISTS "Users can read own router_cache"
ON router_cache
FOR SELECT
TO authenticated
USING (user_id = auth.uid() OR user_id IS NULL);

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE router_cache IS 'Cache for agent router decisions with semantic similarity support';
COMMENT ON FUNCTION increment_cache_hit IS 'Atomically increment cache hit counter';
COMMENT ON FUNCTION get_cached_routing IS 'Find semantically similar cached routing decisions';
