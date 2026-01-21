-- Migration: Create context_messages table
-- Feature: Chat Context Window Management (011)
-- Date: 2025-01-19
-- Description: Individual messages with token counts and protection status

-- Create context_messages table
CREATE TABLE IF NOT EXISTS public.context_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    context_id UUID NOT NULL REFERENCES public.conversation_contexts(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL CHECK (token_count >= 0),
    is_protected BOOLEAN NOT NULL DEFAULT FALSE,
    position INTEGER NOT NULL CHECK (position >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add comment on table
COMMENT ON TABLE public.context_messages IS 'Individual messages with token counts and protection status';

-- Add comments on columns
COMMENT ON COLUMN public.context_messages.id IS 'Unique identifier';
COMMENT ON COLUMN public.context_messages.context_id IS 'Parent conversation context';
COMMENT ON COLUMN public.context_messages.role IS 'Message role: user, assistant, or system';
COMMENT ON COLUMN public.context_messages.content IS 'Message content';
COMMENT ON COLUMN public.context_messages.token_count IS 'Number of tokens in this message';
COMMENT ON COLUMN public.context_messages.is_protected IS 'If true, cannot be summarized during compaction';
COMMENT ON COLUMN public.context_messages.position IS 'Order position in conversation';

-- Create indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_messages_context ON public.context_messages(context_id);
CREATE INDEX IF NOT EXISTS idx_messages_position ON public.context_messages(context_id, position);
CREATE INDEX IF NOT EXISTS idx_messages_protected ON public.context_messages(context_id) WHERE is_protected = TRUE;
