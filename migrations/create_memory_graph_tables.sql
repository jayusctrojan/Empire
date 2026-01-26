-- ============================================================================
-- Task 32: Create Conversation Memory Graph Tables
-- ============================================================================
-- Purpose: Create user_memory_nodes and user_memory_edges tables for
--          conversation memory with graph-based storage
-- Date: 2025-01-09
-- Depends on: pgvector extension
-- ============================================================================

-- Ensure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- User Memory Nodes Table
-- ============================================================================
-- Stores facts, preferences, entities, and context from conversations
-- Each node belongs to a user and can be connected to other nodes via edges

CREATE TABLE IF NOT EXISTS public.user_memory_nodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,
    session_id VARCHAR(255),
    node_type VARCHAR(50) NOT NULL,  -- conversation, fact, preference, context, entity
    content TEXT NOT NULL,
    summary TEXT,
    embedding vector(768),  -- BGE-M3 768-dim embeddings for semantic search
    confidence_score FLOAT DEFAULT 1.0 CHECK (confidence_score >= 0 AND confidence_score <= 1),
    source_type VARCHAR(50) DEFAULT 'conversation',  -- conversation, document, system
    importance_score FLOAT DEFAULT 0.5 CHECK (importance_score >= 0 AND importance_score <= 1),
    first_mentioned_at TIMESTAMPTZ DEFAULT NOW(),
    last_mentioned_at TIMESTAMPTZ DEFAULT NOW(),
    mention_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Comments for documentation
COMMENT ON TABLE public.user_memory_nodes IS 'Stores conversation memory nodes (facts, preferences, entities) per user';
COMMENT ON COLUMN public.user_memory_nodes.node_type IS 'Type: conversation, fact, preference, context, entity';
COMMENT ON COLUMN public.user_memory_nodes.embedding IS 'BGE-M3 768-dimensional vector for semantic similarity search';
COMMENT ON COLUMN public.user_memory_nodes.importance_score IS 'Score 0-1 indicating memory importance for retrieval prioritization';
COMMENT ON COLUMN public.user_memory_nodes.mention_count IS 'Number of times this memory has been referenced';

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_user_id
    ON public.user_memory_nodes(user_id);

CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_session
    ON public.user_memory_nodes(user_id, session_id);

CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_type
    ON public.user_memory_nodes(node_type);

CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_active
    ON public.user_memory_nodes(is_active)
    WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_last_mentioned
    ON public.user_memory_nodes(user_id, last_mentioned_at DESC)
    WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_importance
    ON public.user_memory_nodes(user_id, importance_score DESC)
    WHERE is_active = true;

-- Vector similarity search index (IVFFlat for large datasets)
CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_embedding
    ON public.user_memory_nodes
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ============================================================================
-- User Memory Edges Table
-- ============================================================================
-- Stores relationships between memory nodes for graph traversal

CREATE TABLE IF NOT EXISTS public.user_memory_edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,
    source_node_id UUID NOT NULL REFERENCES user_memory_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES user_memory_nodes(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,  -- related_to, follows, contradicts, supports, etc.
    strength FLOAT DEFAULT 1.0 CHECK (strength >= 0 AND strength <= 1),
    directionality VARCHAR(20) DEFAULT 'directed',  -- directed, undirected
    first_observed_at TIMESTAMPTZ DEFAULT NOW(),
    last_observed_at TIMESTAMPTZ DEFAULT NOW(),
    observation_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(source_node_id, target_node_id, relationship_type)
);

-- Comments for documentation
COMMENT ON TABLE public.user_memory_edges IS 'Stores relationships between memory nodes for graph-based retrieval';
COMMENT ON COLUMN public.user_memory_edges.relationship_type IS 'Type: related_to, follows, contradicts, supports, mentions, etc.';
COMMENT ON COLUMN public.user_memory_edges.strength IS 'Relationship strength 0-1 for weighted graph traversal';
COMMENT ON COLUMN public.user_memory_edges.directionality IS 'Whether the relationship is directed or undirected';

-- Indexes for efficient graph queries
CREATE INDEX IF NOT EXISTS idx_user_memory_edges_user_id
    ON public.user_memory_edges(user_id);

CREATE INDEX IF NOT EXISTS idx_user_memory_edges_source
    ON public.user_memory_edges(source_node_id);

CREATE INDEX IF NOT EXISTS idx_user_memory_edges_target
    ON public.user_memory_edges(target_node_id);

CREATE INDEX IF NOT EXISTS idx_user_memory_edges_type
    ON public.user_memory_edges(relationship_type);

CREATE INDEX IF NOT EXISTS idx_user_memory_edges_active
    ON public.user_memory_edges(is_active)
    WHERE is_active = true;

-- Composite index for graph traversal
CREATE INDEX IF NOT EXISTS idx_user_memory_edges_traversal
    ON public.user_memory_edges(user_id, source_node_id, target_node_id)
    WHERE is_active = true;

-- ============================================================================
-- User Document Connections Table
-- ============================================================================
-- Links memory nodes to documents for cross-reference

CREATE TABLE IF NOT EXISTS public.user_document_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,
    memory_node_id UUID NOT NULL REFERENCES user_memory_nodes(id) ON DELETE CASCADE,
    document_entity_id VARCHAR(255) NOT NULL,
    document_entity_name VARCHAR(500) NOT NULL,
    document_id UUID,  -- Reference to documents table if available
    connection_type VARCHAR(50) DEFAULT 'related_to',
    relevance_score FLOAT DEFAULT 0.5 CHECK (relevance_score >= 0 AND relevance_score <= 1),
    first_connected_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(user_id, memory_node_id, document_entity_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_user_doc_connections_user
    ON public.user_document_connections(user_id);

CREATE INDEX IF NOT EXISTS idx_user_doc_connections_memory
    ON public.user_document_connections(memory_node_id);

CREATE INDEX IF NOT EXISTS idx_user_doc_connections_doc
    ON public.user_document_connections(document_id);

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function: Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for auto-updating timestamps
DROP TRIGGER IF EXISTS update_user_memory_nodes_timestamp ON public.user_memory_nodes;
CREATE TRIGGER update_user_memory_nodes_timestamp
    BEFORE UPDATE ON public.user_memory_nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_memory_edges_timestamp ON public.user_memory_edges;
CREATE TRIGGER update_user_memory_edges_timestamp
    BEFORE UPDATE ON public.user_memory_edges
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_document_connections_timestamp ON public.user_document_connections;
CREATE TRIGGER update_user_document_connections_timestamp
    BEFORE UPDATE ON public.user_document_connections
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Vector Search Function
-- ============================================================================
-- Semantic similarity search for user memories

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
$$ LANGUAGE plpgsql SECURITY INVOKER;

-- ============================================================================
-- Graph Traversal Function
-- ============================================================================
-- Traverse the memory graph from a starting node

CREATE OR REPLACE FUNCTION traverse_memory_graph(
    p_user_id TEXT,
    p_start_node_id UUID,
    p_max_depth INTEGER DEFAULT 2,
    p_relationship_types TEXT[] DEFAULT NULL
) RETURNS TABLE (
    node_id UUID,
    node_type VARCHAR(50),
    content TEXT,
    depth INTEGER,
    path UUID[],
    relationship_type VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE graph_traversal AS (
        -- Base case: start node
        SELECT
            n.id AS node_id,
            n.node_type,
            n.content,
            0 AS depth,
            ARRAY[n.id] AS path,
            NULL::VARCHAR(50) AS relationship_type
        FROM public.user_memory_nodes n
        WHERE n.id = p_start_node_id
          AND n.user_id = p_user_id
          AND n.is_active = true

        UNION ALL

        -- Recursive case: traverse edges
        SELECT
            n.id AS node_id,
            n.node_type,
            n.content,
            gt.depth + 1,
            gt.path || n.id,
            e.relationship_type
        FROM graph_traversal gt
        JOIN public.user_memory_edges e ON (
            e.source_node_id = gt.node_id
            OR (e.target_node_id = gt.node_id AND e.directionality = 'undirected')
        )
        JOIN public.user_memory_nodes n ON (
            n.id = CASE
                WHEN e.source_node_id = gt.node_id THEN e.target_node_id
                ELSE e.source_node_id
            END
        )
        WHERE
            gt.depth < p_max_depth
            AND n.user_id = p_user_id
            AND n.is_active = true
            AND e.is_active = true
            AND NOT (n.id = ANY(gt.path))  -- Prevent cycles
            AND (p_relationship_types IS NULL OR e.relationship_type = ANY(p_relationship_types))
    )
    SELECT DISTINCT
        gt.node_id,
        gt.node_type,
        gt.content,
        gt.depth,
        gt.path,
        gt.relationship_type
    FROM graph_traversal gt
    ORDER BY gt.depth, gt.node_id;
END;
$$ LANGUAGE plpgsql SECURITY INVOKER;

-- ============================================================================
-- Get Related Memories Function
-- ============================================================================
-- Get memories related to a specific node

CREATE OR REPLACE FUNCTION get_related_memories(
    p_user_id TEXT,
    p_node_id UUID,
    p_max_results INTEGER DEFAULT 10
) RETURNS TABLE (
    related_node_id UUID,
    node_type VARCHAR(50),
    content TEXT,
    summary TEXT,
    relationship_type VARCHAR(50),
    strength FLOAT,
    importance_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        CASE
            WHEN e.source_node_id = p_node_id THEN e.target_node_id
            ELSE e.source_node_id
        END AS related_node_id,
        n.node_type,
        n.content,
        n.summary,
        e.relationship_type,
        e.strength,
        n.importance_score
    FROM public.user_memory_edges e
    JOIN public.user_memory_nodes n ON (
        n.id = CASE
            WHEN e.source_node_id = p_node_id THEN e.target_node_id
            ELSE e.source_node_id
        END
    )
    WHERE
        (e.source_node_id = p_node_id OR e.target_node_id = p_node_id)
        AND e.user_id = p_user_id
        AND e.is_active = true
        AND n.is_active = true
    ORDER BY e.strength DESC, n.importance_score DESC
    LIMIT p_max_results;
END;
$$ LANGUAGE plpgsql SECURITY INVOKER;

-- ============================================================================
-- Atomic Increment Functions (Race Condition Fix)
-- ============================================================================

-- Atomic increment for mention_count in user_memory_nodes
CREATE OR REPLACE FUNCTION increment_node_mention_count(
    p_node_id UUID,
    p_user_id TEXT
) RETURNS INTEGER AS $$
DECLARE
    new_count INTEGER;
BEGIN
    UPDATE public.user_memory_nodes
    SET mention_count = mention_count + 1,
        last_mentioned_at = NOW(),
        updated_at = NOW()
    WHERE id = p_node_id
      AND user_id = p_user_id
    RETURNING mention_count INTO new_count;

    RETURN COALESCE(new_count, 0);
END;
$$ LANGUAGE plpgsql SECURITY INVOKER;

-- Atomic increment for observation_count in user_memory_edges
CREATE OR REPLACE FUNCTION increment_edge_observation_count(
    p_edge_id UUID,
    p_user_id TEXT
) RETURNS INTEGER AS $$
DECLARE
    new_count INTEGER;
BEGIN
    UPDATE public.user_memory_edges
    SET observation_count = observation_count + 1,
        last_observed_at = NOW(),
        updated_at = NOW()
    WHERE id = p_edge_id
      AND user_id = p_user_id
    RETURNING observation_count INTO new_count;

    RETURN COALESCE(new_count, 0);
END;
$$ LANGUAGE plpgsql SECURITY INVOKER;

-- ============================================================================
-- Grants
-- ============================================================================

-- Grant execute on functions
-- Note: Write functions (increment_*) only granted to authenticated users for security
GRANT EXECUTE ON FUNCTION increment_node_mention_count(UUID, TEXT) TO authenticated;

GRANT EXECUTE ON FUNCTION increment_edge_observation_count(UUID, TEXT) TO authenticated;

-- Read-only functions can be accessed by authenticated users
GRANT EXECUTE ON FUNCTION match_user_memories(vector(768), TEXT, DECIMAL, INTEGER) TO authenticated;

GRANT EXECUTE ON FUNCTION traverse_memory_graph(TEXT, UUID, INTEGER, TEXT[]) TO authenticated;

GRANT EXECUTE ON FUNCTION get_related_memories(TEXT, UUID, INTEGER) TO authenticated;

-- ============================================================================
-- Verification Query
-- ============================================================================
-- Run this to verify tables were created:
--
-- SELECT tablename FROM pg_tables
-- WHERE schemaname = 'public'
-- AND tablename IN ('user_memory_nodes', 'user_memory_edges', 'user_document_connections');
--
-- Expected output: 3 rows
-- ============================================================================
