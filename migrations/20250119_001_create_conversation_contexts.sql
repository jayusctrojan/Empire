-- Migration: Create conversation_contexts table
-- Feature: Chat Context Window Management (011)
-- Date: 2025-01-19
-- Description: Tracks real-time context window state for each conversation

-- Create conversation_contexts table
CREATE TABLE IF NOT EXISTS public.conversation_contexts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id VARCHAR(255) NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    max_tokens INTEGER NOT NULL DEFAULT 200000,
    threshold_percent INTEGER NOT NULL DEFAULT 80 CHECK (threshold_percent >= 0 AND threshold_percent <= 100),
    last_compaction_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_conversation_contexts_conversation UNIQUE (conversation_id)
);

-- Add comment on table
COMMENT ON TABLE public.conversation_contexts IS 'Tracks real-time context window state for each conversation';

-- Add comments on columns
COMMENT ON COLUMN public.conversation_contexts.id IS 'Unique identifier';
COMMENT ON COLUMN public.conversation_contexts.conversation_id IS 'Link to chat session';
COMMENT ON COLUMN public.conversation_contexts.user_id IS 'Owner user ID';
COMMENT ON COLUMN public.conversation_contexts.total_tokens IS 'Current token count in context';
COMMENT ON COLUMN public.conversation_contexts.max_tokens IS 'Maximum tokens allowed (model context limit)';
COMMENT ON COLUMN public.conversation_contexts.threshold_percent IS 'Compaction trigger threshold (default 80%)';
COMMENT ON COLUMN public.conversation_contexts.last_compaction_at IS 'Timestamp of last compaction';

-- Create indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_contexts_conversation ON public.conversation_contexts(conversation_id);
CREATE INDEX IF NOT EXISTS idx_contexts_user ON public.conversation_contexts(user_id);

-- Create trigger for updated_at timestamp
CREATE OR REPLACE FUNCTION update_conversation_contexts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_conversation_contexts_updated_at
    BEFORE UPDATE ON public.conversation_contexts
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_contexts_updated_at();
