-- Empire v7.3 - Router Cache RPC Functions
-- Creates database functions for agent router caching
--
-- Usage:
--   Run this migration on Supabase PostgreSQL
--   supabase db push or apply via Supabase dashboard

-- =============================================================================
-- EXTENSIONS (ensure pgvector is available)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

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

-- Index for expiration cleanup (plain index - queries use runtime WHERE clause)
-- Note: Cannot use NOW() in partial index as it's STABLE, not IMMUTABLE
CREATE INDEX IF NOT EXISTS idx_router_cache_expires_at
ON router_cache (expires_at);

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

-- Drop any existing overloads to avoid "function name is not unique" errors
-- when CREATE OR REPLACE encounters a different parameter signature.
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT oid::regprocedure::text AS sig
        FROM pg_proc
        WHERE proname = 'get_cached_routing'
          AND pronamespace = 'public'::regnamespace
    LOOP
        EXECUTE 'DROP FUNCTION IF EXISTS ' || r.sig || ' CASCADE';
    END LOOP;

    FOR r IN
        SELECT oid::regprocedure::text AS sig
        FROM pg_proc
        WHERE proname = 'increment_cache_hit'
          AND pronamespace = 'public'::regnamespace
    LOOP
        EXECUTE 'DROP FUNCTION IF EXISTS ' || r.sig || ' CASCADE';
    END LOOP;
END $$;

-- Function to increment cache hit count
-- Uses SET search_path to prevent search-path hijacking in SECURITY DEFINER
CREATE OR REPLACE FUNCTION increment_cache_hit(p_cache_id UUID)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    UPDATE public.router_cache
    SET hit_count = hit_count + 1,
        updated_at = pg_catalog.now()
    WHERE id = p_cache_id;
END;
$$;

-- Function to get cached routing with semantic similarity
-- Uses SET search_path to prevent search-path hijacking in SECURITY DEFINER
CREATE OR REPLACE FUNCTION get_cached_routing(
    p_query_embedding vector(1536),
    p_match_threshold float DEFAULT 0.85,
    p_match_count int DEFAULT 1
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
SET search_path = pg_catalog, public
AS $$
BEGIN
    RETURN QUERY
    SELECT
        rc.id as cache_id,
        rc.query_text,
        rc.routing_decision,
        1 - (rc.query_embedding <=> p_query_embedding) as similarity,
        rc.hit_count
    FROM public.router_cache rc
    WHERE rc.expires_at > pg_catalog.now()
        AND rc.query_embedding IS NOT NULL
        AND 1 - (rc.query_embedding <=> p_query_embedding) >= p_match_threshold
    ORDER BY rc.query_embedding <=> p_query_embedding
    LIMIT p_match_count;
END;
$$;

-- =============================================================================
-- FUNCTION PRIVILEGES (restrict to service_role only)
-- =============================================================================

REVOKE ALL ON FUNCTION increment_cache_hit(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION increment_cache_hit(UUID) TO service_role;

REVOKE ALL ON FUNCTION get_cached_routing(vector(1536), float, int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION get_cached_routing(vector(1536), float, int) TO service_role;

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE router_cache ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (idempotent: DROP then CREATE)
DROP POLICY IF EXISTS "Service role full access to router_cache" ON router_cache;
CREATE POLICY "Service role full access to router_cache"
ON router_cache
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Users can read their own cache entries (idempotent: DROP then CREATE)
DROP POLICY IF EXISTS "Users can read own router_cache" ON router_cache;
CREATE POLICY "Users can read own router_cache"
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
