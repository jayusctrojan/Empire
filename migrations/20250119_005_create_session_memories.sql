-- Migration: Create session_memories table
-- Feature: Chat Context Window Management (011)
-- Date: 2025-01-19
-- Description: Persistent summaries for session resume

-- Create session_memories table
CREATE TABLE IF NOT EXISTS public.session_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id VARCHAR(255) NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    project_id UUID NULL,
    summary TEXT NOT NULL,
    key_decisions JSONB NOT NULL DEFAULT '[]'::JSONB,
    files_mentioned JSONB NOT NULL DEFAULT '[]'::JSONB,
    code_preserved JSONB NOT NULL DEFAULT '[]'::JSONB,
    retention_type VARCHAR(20) NOT NULL CHECK (retention_type IN ('project', 'cko', 'indefinite')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add comment on table
COMMENT ON TABLE public.session_memories IS 'Persistent summaries for session resume';

-- Add comments on columns
COMMENT ON COLUMN public.session_memories.id IS 'Unique identifier';
COMMENT ON COLUMN public.session_memories.conversation_id IS 'Parent conversation';
COMMENT ON COLUMN public.session_memories.user_id IS 'Owner user ID';
COMMENT ON COLUMN public.session_memories.project_id IS 'Associated project (if any)';
COMMENT ON COLUMN public.session_memories.summary IS 'Conversation summary';
COMMENT ON COLUMN public.session_memories.key_decisions IS 'Array of decisions: [{decision, rationale, timestamp}]';
COMMENT ON COLUMN public.session_memories.files_mentioned IS 'Array of file paths: [{path, action, timestamp}]';
COMMENT ON COLUMN public.session_memories.code_preserved IS 'Important code snippets to preserve';
COMMENT ON COLUMN public.session_memories.retention_type IS 'Retention policy: project, cko, or indefinite';

-- Create indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_memory_conversation ON public.session_memories(conversation_id);
CREATE INDEX IF NOT EXISTS idx_memory_user ON public.session_memories(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_project ON public.session_memories(project_id) WHERE project_id IS NOT NULL;

-- Create trigger for updated_at timestamp
CREATE OR REPLACE FUNCTION update_session_memories_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_session_memories_updated_at
    BEFORE UPDATE ON public.session_memories
    FOR EACH ROW
    EXECUTE FUNCTION update_session_memories_updated_at();
