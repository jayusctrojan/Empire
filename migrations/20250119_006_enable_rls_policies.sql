-- Migration: Enable RLS policies for context management tables
-- Feature: Chat Context Window Management (011)
-- Date: 2025-01-19
-- Description: Row Level Security policies for user data isolation

-- ============================================================================
-- conversation_contexts RLS
-- ============================================================================
ALTER TABLE public.conversation_contexts ENABLE ROW LEVEL SECURITY;

-- Users can only access their own contexts
CREATE POLICY "Users can view own contexts"
    ON public.conversation_contexts
    FOR SELECT
    USING (user_id = auth.uid()::VARCHAR);

CREATE POLICY "Users can insert own contexts"
    ON public.conversation_contexts
    FOR INSERT
    WITH CHECK (user_id = auth.uid()::VARCHAR);

CREATE POLICY "Users can update own contexts"
    ON public.conversation_contexts
    FOR UPDATE
    USING (user_id = auth.uid()::VARCHAR);

CREATE POLICY "Users can delete own contexts"
    ON public.conversation_contexts
    FOR DELETE
    USING (user_id = auth.uid()::VARCHAR);

-- ============================================================================
-- context_messages RLS
-- ============================================================================
ALTER TABLE public.context_messages ENABLE ROW LEVEL SECURITY;

-- Users can access messages for contexts they own
CREATE POLICY "Users can view own context messages"
    ON public.context_messages
    FOR SELECT
    USING (
        context_id IN (
            SELECT id FROM public.conversation_contexts
            WHERE user_id = auth.uid()::VARCHAR
        )
    );

CREATE POLICY "Users can insert own context messages"
    ON public.context_messages
    FOR INSERT
    WITH CHECK (
        context_id IN (
            SELECT id FROM public.conversation_contexts
            WHERE user_id = auth.uid()::VARCHAR
        )
    );

CREATE POLICY "Users can update own context messages"
    ON public.context_messages
    FOR UPDATE
    USING (
        context_id IN (
            SELECT id FROM public.conversation_contexts
            WHERE user_id = auth.uid()::VARCHAR
        )
    );

CREATE POLICY "Users can delete own context messages"
    ON public.context_messages
    FOR DELETE
    USING (
        context_id IN (
            SELECT id FROM public.conversation_contexts
            WHERE user_id = auth.uid()::VARCHAR
        )
    );

-- ============================================================================
-- compaction_logs RLS
-- ============================================================================
ALTER TABLE public.compaction_logs ENABLE ROW LEVEL SECURITY;

-- Users can view compaction logs for their contexts
CREATE POLICY "Users can view own compaction logs"
    ON public.compaction_logs
    FOR SELECT
    USING (
        context_id IN (
            SELECT id FROM public.conversation_contexts
            WHERE user_id = auth.uid()::VARCHAR
        )
    );

-- Insert is allowed for contexts user owns
CREATE POLICY "Users can insert own compaction logs"
    ON public.compaction_logs
    FOR INSERT
    WITH CHECK (
        context_id IN (
            SELECT id FROM public.conversation_contexts
            WHERE user_id = auth.uid()::VARCHAR
        )
    );

-- ============================================================================
-- session_checkpoints RLS
-- ============================================================================
ALTER TABLE public.session_checkpoints ENABLE ROW LEVEL SECURITY;

-- Users can only access their own checkpoints
CREATE POLICY "Users can view own checkpoints"
    ON public.session_checkpoints
    FOR SELECT
    USING (user_id = auth.uid()::VARCHAR);

CREATE POLICY "Users can insert own checkpoints"
    ON public.session_checkpoints
    FOR INSERT
    WITH CHECK (user_id = auth.uid()::VARCHAR);

CREATE POLICY "Users can delete own checkpoints"
    ON public.session_checkpoints
    FOR DELETE
    USING (user_id = auth.uid()::VARCHAR);

-- ============================================================================
-- session_memories RLS
-- ============================================================================
ALTER TABLE public.session_memories ENABLE ROW LEVEL SECURITY;

-- Users can only access their own memories
CREATE POLICY "Users can view own memories"
    ON public.session_memories
    FOR SELECT
    USING (user_id = auth.uid()::VARCHAR);

CREATE POLICY "Users can insert own memories"
    ON public.session_memories
    FOR INSERT
    WITH CHECK (user_id = auth.uid()::VARCHAR);

CREATE POLICY "Users can update own memories"
    ON public.session_memories
    FOR UPDATE
    USING (user_id = auth.uid()::VARCHAR);

CREATE POLICY "Users can delete own memories"
    ON public.session_memories
    FOR DELETE
    USING (user_id = auth.uid()::VARCHAR);

-- ============================================================================
-- Service role bypass policies (for backend services)
-- ============================================================================
-- Note: The service_role key in Supabase bypasses RLS by default.
-- These comments document that backend services using SUPABASE_SERVICE_KEY
-- will have full access for operations like:
-- - Background compaction via Celery workers
-- - Automated checkpoint cleanup
-- - Admin operations
