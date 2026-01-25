-- Empire v7.3 - Migration 2.4: Create Agent Router Cache Table
-- Task: Create agent_router_cache table for Feature 9 (Intelligent Agent Router)
--
-- Feature 9: Intelligent Agent Router
-- Goal: Cache routing decisions for similar queries to achieve <100ms decision time
-- Target: >90% routing accuracy with intelligent caching
--
-- Workflow types:
--   - langgraph: Complex iterative queries, external data, research
--   - crewai: Multi-document analysis, multi-agent coordination
--   - simple_rag: Direct knowledge base lookups, straightforward queries

-- Step 1: Create workflow_type enum
CREATE TYPE workflow_type AS ENUM (
    'langgraph',
    'crewai',
    'simple_rag'
);

-- Step 2: Create query_complexity enum
CREATE TYPE query_complexity AS ENUM (
    'low',
    'medium',
    'high'
);

-- Step 3: Create agent_router_cache table
CREATE TABLE agent_router_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Query identification and caching
    query_hash VARCHAR(64) NOT NULL UNIQUE,
    query_text TEXT NOT NULL,
    query_embedding vector(1024),  -- For semantic similarity matching

    -- Routing decision
    selected_workflow workflow_type NOT NULL,
    confidence_score NUMERIC(3, 2) NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    routing_time_ms INTEGER NOT NULL CHECK (routing_time_ms >= 0),

    -- Query characteristics
    complexity query_complexity NOT NULL,
    query_type VARCHAR(100),  -- e.g., comparison, research, factual, analytical
    requires_multiple_documents BOOLEAN DEFAULT FALSE,
    requires_external_data BOOLEAN DEFAULT FALSE,
    estimated_processing_time_sec INTEGER,

    -- Alternative workflows considered
    alternative_workflows JSONB DEFAULT '[]'::jsonb,
    -- Structure: [{"workflow": "crewai", "confidence": 0.65, "reason": "..."}]

    -- Routing reasoning and metadata
    reasoning TEXT,
    routing_factors JSONB DEFAULT '{}'::jsonb,
    -- Structure: {"complexity_score": 0.8, "doc_count": 3, "query_length": 45}

    -- Performance tracking
    hit_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    average_user_rating NUMERIC(2, 1),  -- 1.0-5.0 from user feedback
    successful_executions INTEGER DEFAULT 0,
    failed_executions INTEGER DEFAULT 0,

    -- Cache management
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '7 days') NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,

    -- User and session context
    user_id VARCHAR(255),
    session_id UUID,

    CONSTRAINT valid_rating CHECK (average_user_rating IS NULL OR (average_user_rating >= 1.0 AND average_user_rating <= 5.0))
);

-- Step 4: Create indexes for efficient querying
CREATE INDEX idx_agent_router_query_hash
ON agent_router_cache(query_hash);

CREATE INDEX idx_agent_router_selected_workflow
ON agent_router_cache(selected_workflow);

CREATE INDEX idx_agent_router_expires_at
ON agent_router_cache(expires_at)
WHERE is_active = TRUE;

CREATE INDEX idx_agent_router_last_used
ON agent_router_cache(last_used_at DESC);

CREATE INDEX idx_agent_router_hit_count
ON agent_router_cache(hit_count DESC);

-- Vector similarity index for semantic caching
CREATE INDEX idx_agent_router_embedding
ON agent_router_cache USING ivfflat(query_embedding vector_cosine_ops)
WITH (lists = 100);

-- GIN index for JSONB columns
CREATE INDEX idx_agent_router_alternatives
ON agent_router_cache USING gin(alternative_workflows);

CREATE INDEX idx_agent_router_factors
ON agent_router_cache USING gin(routing_factors);

-- Step 5: Create function to get cached routing decision
CREATE OR REPLACE FUNCTION get_cached_routing(
    p_query_hash VARCHAR,
    p_query_embedding vector(1024) DEFAULT NULL,
    p_similarity_threshold NUMERIC DEFAULT 0.85
)
RETURNS TABLE (
    cache_id UUID,
    selected_workflow workflow_type,
    confidence_score NUMERIC,
    routing_time_ms INTEGER,
    reasoning TEXT,
    cache_age_seconds INTEGER,
    is_exact_match BOOLEAN
) AS $$
BEGIN
    -- First try exact hash match
    RETURN QUERY
    SELECT
        c.id,
        c.selected_workflow,
        c.confidence_score,
        c.routing_time_ms,
        c.reasoning,
        EXTRACT(EPOCH FROM (NOW() - c.created_at))::INTEGER AS cache_age_seconds,
        TRUE AS is_exact_match
    FROM agent_router_cache c
    WHERE c.query_hash = p_query_hash
      AND c.is_active = TRUE
      AND c.expires_at > NOW()
    LIMIT 1;

    -- If no exact match and embedding provided, try semantic similarity
    IF NOT FOUND AND p_query_embedding IS NOT NULL THEN
        RETURN QUERY
        SELECT
            c.id,
            c.selected_workflow,
            c.confidence_score,
            c.routing_time_ms,
            c.reasoning,
            EXTRACT(EPOCH FROM (NOW() - c.created_at))::INTEGER AS cache_age_seconds,
            FALSE AS is_exact_match
        FROM agent_router_cache c
        WHERE c.query_embedding IS NOT NULL
          AND c.is_active = TRUE
          AND c.expires_at > NOW()
          AND (1 - (c.query_embedding <=> p_query_embedding)) >= p_similarity_threshold
        ORDER BY c.query_embedding <=> p_query_embedding
        LIMIT 1;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Step 6: Create function to increment cache hit count
CREATE OR REPLACE FUNCTION increment_cache_hit(p_cache_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE agent_router_cache
    SET hit_count = hit_count + 1,
        last_used_at = NOW()
    WHERE id = p_cache_id;
END;
$$ LANGUAGE plpgsql;

-- Step 7: Create function to update cache performance
CREATE OR REPLACE FUNCTION update_cache_performance(
    p_cache_id UUID,
    p_success BOOLEAN,
    p_user_rating NUMERIC DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    IF p_success THEN
        UPDATE agent_router_cache
        SET successful_executions = successful_executions + 1,
            average_user_rating = CASE
                WHEN p_user_rating IS NOT NULL THEN
                    COALESCE((average_user_rating * successful_executions + p_user_rating) / (successful_executions + 1), p_user_rating)
                ELSE average_user_rating
            END
        WHERE id = p_cache_id;
    ELSE
        UPDATE agent_router_cache
        SET failed_executions = failed_executions + 1
        WHERE id = p_cache_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Step 8: Create function to clean up expired cache entries
CREATE OR REPLACE FUNCTION cleanup_expired_routing_cache()
RETURNS INTEGER AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    WITH deleted AS (
        DELETE FROM agent_router_cache
        WHERE expires_at < NOW()
          OR (is_active = FALSE AND last_used_at < NOW() - INTERVAL '30 days')
        RETURNING id
    )
    SELECT COUNT(*) INTO v_deleted_count FROM deleted;

    RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Step 9: Create view for cache analytics
CREATE OR REPLACE VIEW agent_router_cache_analytics AS
SELECT
    selected_workflow,
    COUNT(*) AS total_entries,
    SUM(hit_count) AS total_hits,
    AVG(confidence_score)::NUMERIC(3, 2) AS avg_confidence,
    AVG(routing_time_ms)::INTEGER AS avg_routing_time_ms,
    AVG(average_user_rating)::NUMERIC(2, 1) AS avg_user_rating,
    SUM(successful_executions) AS total_successes,
    SUM(failed_executions) AS total_failures,
    (SUM(successful_executions)::NUMERIC / NULLIF(SUM(successful_executions + failed_executions), 0) * 100)::NUMERIC(5, 2) AS success_rate_pct
FROM agent_router_cache
WHERE is_active = TRUE
GROUP BY selected_workflow
ORDER BY total_hits DESC;

-- Step 10: Add comments documenting the schema
COMMENT ON TABLE agent_router_cache IS
'Caching layer for intelligent agent routing decisions (v7.3 Feature 9).
Stores routing decisions to achieve <100ms response time and >90% accuracy.
Uses both exact hash matching and semantic similarity for cache hits.';

COMMENT ON COLUMN agent_router_cache.query_hash IS
'SHA-256 hash of normalized query for exact matching';

COMMENT ON COLUMN agent_router_cache.query_embedding IS
'BGE-M3 vector embedding for semantic similarity matching';

COMMENT ON COLUMN agent_router_cache.alternative_workflows IS
'Array of alternative workflow options considered with confidence scores';

COMMENT ON COLUMN agent_router_cache.routing_factors IS
'Factors influencing the routing decision (complexity, document count, etc.)';

COMMENT ON COLUMN agent_router_cache.hit_count IS
'Number of times this cache entry was used (popularity metric)';

COMMENT ON VIEW agent_router_cache_analytics IS
'Analytics view for monitoring cache performance and routing accuracy (v7.3 Feature 9)';

COMMENT ON FUNCTION get_cached_routing IS
'Retrieve cached routing decision by hash or semantic similarity (v7.3 Feature 9)';

COMMENT ON FUNCTION increment_cache_hit IS
'Increment cache hit counter and update last used timestamp (v7.3 Feature 9)';

COMMENT ON FUNCTION update_cache_performance IS
'Update cache entry performance metrics based on execution results (v7.3 Feature 9)';

COMMENT ON FUNCTION cleanup_expired_routing_cache IS
'Clean up expired and inactive cache entries (v7.3 Feature 9)';

-- Step 11: Schedule automatic cleanup (using pg_cron if available)
-- Note: This requires pg_cron extension, which may not be available in all environments
-- If pg_cron is available, uncomment the following:
-- SELECT cron.schedule(
--     'cleanup-routing-cache',
--     '0 2 * * *',  -- Run daily at 2 AM
--     $$SELECT cleanup_expired_routing_cache();$$
-- );
