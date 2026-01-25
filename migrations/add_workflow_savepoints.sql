-- Empire v7.3 Migration: Workflow Savepoints and State Management
-- Purpose: Enable workflow rollback/savepoint functionality for multi-agent orchestration
-- Date: 2025-01-24

-- ============================================================================
-- WORKFLOW SAVEPOINTS TABLE
-- Stores savepoint data for workflow rollback capabilities
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_savepoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL,
    agent_id TEXT NOT NULL,
    savepoint_name TEXT,

    -- Serialized state data
    state JSONB NOT NULL,
    state_checksum TEXT NOT NULL,  -- SHA-256 for integrity verification

    -- Context at savepoint
    step_index INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0,

    -- Artifacts at this point
    input_artifacts JSONB DEFAULT '[]'::jsonb,
    output_artifacts JSONB DEFAULT '[]'::jsonb,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,  -- Optional expiration for cleanup

    -- Constraints
    CONSTRAINT valid_step_index CHECK (step_index >= 0),
    CONSTRAINT valid_total_steps CHECK (total_steps >= 0)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Primary lookup by workflow
CREATE INDEX IF NOT EXISTS idx_workflow_savepoints_workflow_id
    ON workflow_savepoints(workflow_id);

-- Find savepoints by agent
CREATE INDEX IF NOT EXISTS idx_workflow_savepoints_agent_id
    ON workflow_savepoints(agent_id);

-- Timestamp-based queries (cleanup, history)
CREATE INDEX IF NOT EXISTS idx_workflow_savepoints_created_at
    ON workflow_savepoints(created_at DESC);

-- Expiration cleanup
CREATE INDEX IF NOT EXISTS idx_workflow_savepoints_expires_at
    ON workflow_savepoints(expires_at)
    WHERE expires_at IS NOT NULL;

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_workflow_savepoints_workflow_agent
    ON workflow_savepoints(workflow_id, agent_id, created_at DESC);

-- JSONB index for metadata queries
CREATE INDEX IF NOT EXISTS idx_workflow_savepoints_metadata
    ON workflow_savepoints USING GIN (metadata);

-- ============================================================================
-- WORKFLOW CONTEXT TABLE
-- Tracks active workflow execution state
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_contexts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL UNIQUE,

    -- Current state
    current_step INTEGER DEFAULT 0,
    current_agent_id TEXT,
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'paused', 'completed', 'failed', 'rolled_back')),

    -- Accumulated data
    accumulated_data JSONB DEFAULT '{}'::jsonb,
    errors JSONB DEFAULT '[]'::jsonb,

    -- Savepoint tracking
    last_savepoint_id UUID REFERENCES workflow_savepoints(id),
    savepoint_count INTEGER DEFAULT 0,

    -- Timing
    started_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Index for workflow lookup
CREATE INDEX IF NOT EXISTS idx_workflow_contexts_workflow_id
    ON workflow_contexts(workflow_id);

-- Index for status-based queries
CREATE INDEX IF NOT EXISTS idx_workflow_contexts_status
    ON workflow_contexts(status);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to create a savepoint
CREATE OR REPLACE FUNCTION create_workflow_savepoint(
    p_workflow_id UUID,
    p_agent_id TEXT,
    p_state JSONB,
    p_savepoint_name TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'::jsonb
) RETURNS UUID AS $$
DECLARE
    v_savepoint_id UUID;
    v_checksum TEXT;
BEGIN
    -- Calculate checksum
    v_checksum := encode(sha256(p_state::text::bytea), 'hex');

    -- Insert savepoint
    INSERT INTO workflow_savepoints (
        workflow_id, agent_id, state, state_checksum,
        savepoint_name, metadata
    ) VALUES (
        p_workflow_id, p_agent_id, p_state, v_checksum,
        p_savepoint_name, p_metadata
    ) RETURNING id INTO v_savepoint_id;

    -- Update context
    UPDATE workflow_contexts
    SET
        last_savepoint_id = v_savepoint_id,
        savepoint_count = savepoint_count + 1,
        updated_at = NOW()
    WHERE workflow_id = p_workflow_id;

    RETURN v_savepoint_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get the latest savepoint for a workflow
CREATE OR REPLACE FUNCTION get_latest_savepoint(
    p_workflow_id UUID
) RETURNS workflow_savepoints AS $$
DECLARE
    v_savepoint workflow_savepoints;
BEGIN
    SELECT * INTO v_savepoint
    FROM workflow_savepoints
    WHERE workflow_id = p_workflow_id
    ORDER BY created_at DESC
    LIMIT 1;

    RETURN v_savepoint;
END;
$$ LANGUAGE plpgsql;

-- Function to cleanup expired savepoints
CREATE OR REPLACE FUNCTION cleanup_expired_savepoints() RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    DELETE FROM workflow_savepoints
    WHERE expires_at IS NOT NULL AND expires_at < NOW();

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ROW LEVEL SECURITY (if needed)
-- ============================================================================

-- Enable RLS
ALTER TABLE workflow_savepoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_contexts ENABLE ROW LEVEL SECURITY;

-- Policy for service role (full access)
CREATE POLICY workflow_savepoints_service_policy ON workflow_savepoints
    FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY workflow_contexts_service_policy ON workflow_contexts
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE workflow_savepoints IS
    'Stores savepoint data for workflow rollback capabilities in multi-agent orchestration';

COMMENT ON TABLE workflow_contexts IS
    'Tracks active workflow execution state for savepoint and rollback management';

COMMENT ON FUNCTION create_workflow_savepoint IS
    'Creates a new savepoint for a workflow and updates the context';

COMMENT ON FUNCTION get_latest_savepoint IS
    'Retrieves the most recent savepoint for a given workflow';

COMMENT ON FUNCTION cleanup_expired_savepoints IS
    'Removes expired savepoints based on expires_at timestamp';
