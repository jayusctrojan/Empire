-- Migration: Create compaction_logs table
-- Feature: Chat Context Window Management (011)
-- Date: 2025-01-19
-- Description: Audit trail of compaction events

-- Create compaction_logs table
CREATE TABLE IF NOT EXISTS public.compaction_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    context_id UUID NOT NULL REFERENCES public.conversation_contexts(id) ON DELETE CASCADE,
    pre_tokens INTEGER NOT NULL CHECK (pre_tokens >= 0),
    post_tokens INTEGER NOT NULL CHECK (post_tokens >= 0),
    reduction_percent DECIMAL(5,2) NOT NULL CHECK (reduction_percent >= 0 AND reduction_percent <= 100),
    summary_preview TEXT NULL,
    messages_condensed INTEGER NOT NULL CHECK (messages_condensed >= 0),
    model_used VARCHAR(50) NOT NULL,
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
    triggered_by VARCHAR(20) NOT NULL CHECK (triggered_by IN ('auto', 'manual', 'force', 'error_recovery')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add comment on table
COMMENT ON TABLE public.compaction_logs IS 'Audit trail of compaction events';

-- Add comments on columns
COMMENT ON COLUMN public.compaction_logs.id IS 'Unique identifier';
COMMENT ON COLUMN public.compaction_logs.context_id IS 'Context that was compacted';
COMMENT ON COLUMN public.compaction_logs.pre_tokens IS 'Token count before compaction';
COMMENT ON COLUMN public.compaction_logs.post_tokens IS 'Token count after compaction';
COMMENT ON COLUMN public.compaction_logs.reduction_percent IS 'Percentage of tokens reduced';
COMMENT ON COLUMN public.compaction_logs.summary_preview IS 'First 500 chars of summary';
COMMENT ON COLUMN public.compaction_logs.messages_condensed IS 'Number of messages summarized';
COMMENT ON COLUMN public.compaction_logs.model_used IS 'AI model used: claude-sonnet-4 or claude-haiku';
COMMENT ON COLUMN public.compaction_logs.duration_ms IS 'Compaction duration in milliseconds';
COMMENT ON COLUMN public.compaction_logs.triggered_by IS 'Trigger type: auto, manual, force, or error_recovery';

-- Create indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_compaction_context ON public.compaction_logs(context_id);
CREATE INDEX IF NOT EXISTS idx_compaction_created ON public.compaction_logs(created_at);
