-- ============================================================================
-- Task 27: Add RLS Policies for user_memory_nodes and user_memory_edges
-- ============================================================================
-- Purpose: Ensure users can only access their own memory data
-- Date: 2025-01-09
-- ============================================================================

-- Enable Row-Level Security on user_memory_nodes
ALTER TABLE public.user_memory_nodes ENABLE ROW LEVEL SECURITY;

-- Enable Row-Level Security on user_memory_edges
ALTER TABLE public.user_memory_edges ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- RLS Policies for user_memory_nodes
-- ============================================================================

-- Policy: Users can only select their own memory nodes
CREATE POLICY user_memory_nodes_select_policy
ON public.user_memory_nodes
FOR SELECT
USING (
    user_id = current_setting('app.current_user_id', true)::text
    OR current_setting('app.current_user_id', true) IS NULL  -- Allow service role
);

-- Policy: Users can only insert their own memory nodes
CREATE POLICY user_memory_nodes_insert_policy
ON public.user_memory_nodes
FOR INSERT
WITH CHECK (
    user_id = current_setting('app.current_user_id', true)::text
    OR current_setting('app.current_user_id', true) IS NULL  -- Allow service role
);

-- Policy: Users can only update their own memory nodes
CREATE POLICY user_memory_nodes_update_policy
ON public.user_memory_nodes
FOR UPDATE
USING (
    user_id = current_setting('app.current_user_id', true)::text
    OR current_setting('app.current_user_id', true) IS NULL  -- Allow service role
);

-- Policy: Users can only delete their own memory nodes
CREATE POLICY user_memory_nodes_delete_policy
ON public.user_memory_nodes
FOR DELETE
USING (
    user_id = current_setting('app.current_user_id', true)::text
    OR current_setting('app.current_user_id', true) IS NULL  -- Allow service role
);

-- ============================================================================
-- RLS Policies for user_memory_edges
-- ============================================================================

-- Policy: Users can only select their own memory edges
CREATE POLICY user_memory_edges_select_policy
ON public.user_memory_edges
FOR SELECT
USING (
    user_id = current_setting('app.current_user_id', true)::text
    OR current_setting('app.current_user_id', true) IS NULL  -- Allow service role
);

-- Policy: Users can only insert their own memory edges
CREATE POLICY user_memory_edges_insert_policy
ON public.user_memory_edges
FOR INSERT
WITH CHECK (
    user_id = current_setting('app.current_user_id', true)::text
    OR current_setting('app.current_user_id', true) IS NULL  -- Allow service role
);

-- Policy: Users can only update their own memory edges
CREATE POLICY user_memory_edges_update_policy
ON public.user_memory_edges
FOR UPDATE
USING (
    user_id = current_setting('app.current_user_id', true)::text
    OR current_setting('app.current_user_id', true) IS NULL  -- Allow service role
);

-- Policy: Users can only delete their own memory edges
CREATE POLICY user_memory_edges_delete_policy
ON public.user_memory_edges
FOR DELETE
USING (
    user_id = current_setting('app.current_user_id', true)::text
    OR current_setting('app.current_user_id', true) IS NULL  -- Allow service role
);

-- ============================================================================
-- Helper Function: Set current user context
-- ============================================================================
-- This function should be called by the application to set the current user
-- before performing any memory operations.
-- ============================================================================

CREATE OR REPLACE FUNCTION set_user_context(p_user_id TEXT)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_user_id', p_user_id, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute on helper function to authenticated users
GRANT EXECUTE ON FUNCTION set_user_context(TEXT) TO authenticated;

-- ============================================================================
-- Vector Search Function for User Memories (with RLS)
-- ============================================================================

CREATE OR REPLACE FUNCTION match_user_memories(
    query_embedding vector(768),
    p_user_id TEXT,
    match_threshold DECIMAL(3, 2) DEFAULT 0.7,
    match_count INTEGER DEFAULT 10
) RETURNS TABLE (
    id UUID,
    user_id VARCHAR(100),
    session_id VARCHAR(255),
    node_type VARCHAR(50),
    content TEXT,
    summary TEXT,
    confidence_score FLOAT,
    importance_score FLOAT,
    last_mentioned_at TIMESTAMPTZ,
    mention_count INTEGER,
    similarity DECIMAL(5, 4),
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        umn.id,
        umn.user_id,
        umn.session_id,
        umn.node_type,
        umn.content,
        umn.summary,
        umn.confidence_score,
        umn.importance_score,
        umn.last_mentioned_at,
        umn.mention_count,
        (1 - (umn.embedding <=> query_embedding))::DECIMAL(5,4) AS similarity,
        umn.metadata
    FROM public.user_memory_nodes umn
    WHERE
        umn.user_id = p_user_id
        AND umn.is_active = true
        AND umn.embedding IS NOT NULL
        AND (1 - (umn.embedding <=> query_embedding)) >= match_threshold
    ORDER BY umn.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute on vector search function
GRANT EXECUTE ON FUNCTION match_user_memories(vector(768), TEXT, DECIMAL, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION match_user_memories(vector(768), TEXT, DECIMAL, INTEGER) TO anon;

-- ============================================================================
-- Verification Query
-- ============================================================================
-- Run this to verify RLS is enabled:
--
-- SELECT tablename, rowsecurity
-- FROM pg_tables
-- WHERE schemaname = 'public'
-- AND tablename IN ('user_memory_nodes', 'user_memory_edges');
--
-- Expected output:
-- user_memory_nodes    | true
-- user_memory_edges    | true
-- ============================================================================
