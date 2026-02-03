-- Migration: Create Agent Feedback Table
-- Task 188: Agent Feedback System
-- Date: 2025-01-17

-- =============================================================================
-- Part 1: Create agent_feedback table
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.agent_feedback (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Agent identification
    agent_id VARCHAR(50) NOT NULL,
    task_id UUID,

    -- Feedback type and content
    feedback_type VARCHAR(50) NOT NULL,  -- 'classification', 'generation', 'retrieval', 'orchestration'
    input_summary TEXT,
    output_summary TEXT,

    -- Rating (1-5 scale)
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,

    -- Additional metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- User who provided feedback
    created_by UUID
);

-- =============================================================================
-- Part 2: Create indexes for query performance
-- =============================================================================

-- Index for agent-based queries
CREATE INDEX IF NOT EXISTS idx_agent_feedback_agent_id
ON agent_feedback(agent_id);

-- Index for feedback type filtering
CREATE INDEX IF NOT EXISTS idx_agent_feedback_type
ON agent_feedback(feedback_type);

-- Index for time-based queries (most recent first)
CREATE INDEX IF NOT EXISTS idx_agent_feedback_created_at
ON agent_feedback(created_at DESC);

-- Index for user-based queries
CREATE INDEX IF NOT EXISTS idx_agent_feedback_created_by
ON agent_feedback(created_by)
WHERE created_by IS NOT NULL;

-- Composite index for common query pattern (agent + type + time)
CREATE INDEX IF NOT EXISTS idx_agent_feedback_agent_type_time
ON agent_feedback(agent_id, feedback_type, created_at DESC);

-- Index for rating-based queries
CREATE INDEX IF NOT EXISTS idx_agent_feedback_rating
ON agent_feedback(rating)
WHERE rating IS NOT NULL;

-- =============================================================================
-- Part 3: Trigger for updated_at timestamp
-- =============================================================================

CREATE OR REPLACE FUNCTION update_agent_feedback_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_agent_feedback_updated_at ON agent_feedback;
CREATE TRIGGER trigger_agent_feedback_updated_at
    BEFORE UPDATE ON agent_feedback
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_feedback_updated_at();

-- =============================================================================
-- Part 4: Row Level Security (RLS)
-- =============================================================================

-- Enable RLS
ALTER TABLE public.agent_feedback ENABLE ROW LEVEL SECURITY;

-- Users can view feedback they created
CREATE POLICY "Users can view their own feedback"
ON public.agent_feedback
FOR SELECT
USING (created_by = auth.uid()::uuid OR created_by IS NULL);

-- Users can insert their own feedback
CREATE POLICY "Users can insert their own feedback"
ON public.agent_feedback
FOR INSERT
WITH CHECK (created_by = auth.uid()::uuid OR created_by IS NULL);

-- Users can update their own feedback
CREATE POLICY "Users can update their own feedback"
ON public.agent_feedback
FOR UPDATE
USING (created_by = auth.uid()::uuid)
WITH CHECK (created_by = auth.uid()::uuid);

-- Service role has full access
CREATE POLICY "Service role has full access to feedback"
ON public.agent_feedback
FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

-- =============================================================================
-- Part 5: Comments for documentation
-- =============================================================================

COMMENT ON TABLE agent_feedback IS 'Stores user feedback for AI agent outputs (Task 188)';
COMMENT ON COLUMN agent_feedback.agent_id IS 'Identifier of the agent that produced the output';
COMMENT ON COLUMN agent_feedback.task_id IS 'Optional reference to related task';
COMMENT ON COLUMN agent_feedback.feedback_type IS 'Type of feedback: classification, generation, retrieval, orchestration';
COMMENT ON COLUMN agent_feedback.input_summary IS 'Summary of the input provided to the agent (max 500 chars)';
COMMENT ON COLUMN agent_feedback.output_summary IS 'Summary of the agent output (max 500 chars)';
COMMENT ON COLUMN agent_feedback.rating IS 'User rating from 1 (poor) to 5 (excellent)';
COMMENT ON COLUMN agent_feedback.feedback_text IS 'Optional free-text feedback from user';
COMMENT ON COLUMN agent_feedback.metadata IS 'Additional context-specific metadata as JSON';
