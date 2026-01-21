-- Migration: Add vector search support to session_memories
-- Feature: Chat Context Window Management (011)
-- Task: 207 - Implement Session Memory & Persistence
-- Date: 2025-01-20
-- Description: Adds embedding column, expires_at, and vector matching function

-- Ensure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column for semantic search (BGE-M3 uses 1024 dimensions)
ALTER TABLE public.session_memories
ADD COLUMN IF NOT EXISTS embedding vector(1024);

-- Add expires_at column for retention policy enforcement
ALTER TABLE public.session_memories
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

-- Add tags column for categorization
ALTER TABLE public.session_memories
ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';

-- Add comments on new columns
COMMENT ON COLUMN public.session_memories.embedding IS 'BGE-M3 embedding vector for semantic search';
COMMENT ON COLUMN public.session_memories.expires_at IS 'Expiration date based on retention policy (null = no expiration)';
COMMENT ON COLUMN public.session_memories.tags IS 'Array of tags for categorization';

-- Create index on embedding for vector similarity search
CREATE INDEX IF NOT EXISTS idx_memory_embedding ON public.session_memories
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create index on expires_at for cleanup queries
CREATE INDEX IF NOT EXISTS idx_memory_expires_at ON public.session_memories(expires_at)
WHERE expires_at IS NOT NULL;

-- Create index on tags using GIN
CREATE INDEX IF NOT EXISTS idx_memory_tags ON public.session_memories USING GIN(tags);

-- Create function for semantic memory matching
CREATE OR REPLACE FUNCTION match_session_memories(
    query_embedding vector(1024),
    match_user_id VARCHAR(255),
    match_project_id UUID DEFAULT NULL,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    conversation_id VARCHAR(255),
    user_id VARCHAR(255),
    project_id UUID,
    summary TEXT,
    key_decisions JSONB,
    files_mentioned JSONB,
    code_preserved JSONB,
    tags TEXT[],
    retention_type VARCHAR(20),
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        sm.id,
        sm.conversation_id,
        sm.user_id,
        sm.project_id,
        sm.summary,
        sm.key_decisions,
        sm.files_mentioned,
        sm.code_preserved,
        sm.tags,
        sm.retention_type,
        sm.created_at,
        sm.updated_at,
        sm.expires_at,
        1 - (sm.embedding <=> query_embedding) AS similarity
    FROM public.session_memories sm
    WHERE sm.user_id = match_user_id
      AND sm.embedding IS NOT NULL
      AND (match_project_id IS NULL OR sm.project_id = match_project_id)
      AND (sm.expires_at IS NULL OR sm.expires_at > NOW())
    ORDER BY sm.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Add comment on function
COMMENT ON FUNCTION match_session_memories IS 'Find similar session memories using vector cosine similarity';

-- Create function to cleanup expired memories
CREATE OR REPLACE FUNCTION cleanup_expired_session_memories()
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM public.session_memories
    WHERE expires_at IS NOT NULL
      AND expires_at < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    RETURN deleted_count;
END;
$$;

COMMENT ON FUNCTION cleanup_expired_session_memories IS 'Remove expired session memories and return count';
