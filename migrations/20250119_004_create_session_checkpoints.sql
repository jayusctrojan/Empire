-- Migration: Create session_checkpoints table
-- Feature: Chat Context Window Management (011)
-- Date: 2025-01-19
-- Description: Point-in-time snapshots for recovery

-- Create session_checkpoints table
CREATE TABLE IF NOT EXISTS public.session_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id VARCHAR(255) NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    checkpoint_data JSONB NOT NULL,
    token_count INTEGER NOT NULL CHECK (token_count >= 0),
    label TEXT NULL,
    auto_tag VARCHAR(50) NULL CHECK (auto_tag IN ('code', 'decision', 'error_resolution', 'milestone', NULL)),
    is_abnormal_close BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 days')
);

-- Add comment on table
COMMENT ON TABLE public.session_checkpoints IS 'Point-in-time snapshots for crash recovery and session resume';

-- Add comments on columns
COMMENT ON COLUMN public.session_checkpoints.id IS 'Unique identifier';
COMMENT ON COLUMN public.session_checkpoints.conversation_id IS 'Parent conversation';
COMMENT ON COLUMN public.session_checkpoints.user_id IS 'Owner user ID';
COMMENT ON COLUMN public.session_checkpoints.checkpoint_data IS 'Full conversation state (messages, context_state, metadata)';
COMMENT ON COLUMN public.session_checkpoints.token_count IS 'Token count at checkpoint';
COMMENT ON COLUMN public.session_checkpoints.label IS 'User-provided label (from /save-progress)';
COMMENT ON COLUMN public.session_checkpoints.auto_tag IS 'Auto-generated tag: code, decision, error_resolution, milestone';
COMMENT ON COLUMN public.session_checkpoints.is_abnormal_close IS 'True if this is a crash recovery checkpoint';
COMMENT ON COLUMN public.session_checkpoints.expires_at IS '30-day TTL for cleanup';

-- Create indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_checkpoint_conversation ON public.session_checkpoints(conversation_id);
CREATE INDEX IF NOT EXISTS idx_checkpoint_user ON public.session_checkpoints(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_checkpoint_abnormal ON public.session_checkpoints(user_id) WHERE is_abnormal_close = TRUE;
CREATE INDEX IF NOT EXISTS idx_checkpoint_expires ON public.session_checkpoints(expires_at);
