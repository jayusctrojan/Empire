-- Empire v7.3 Migration: Execution Lineage and Provenance Tracking
-- Purpose: Track execution history, data lineage, and provenance for audit and debugging
-- Date: 2025-01-24

-- ============================================================================
-- EXECUTION LINEAGE TABLE
-- Tracks each step in workflow execution for provenance
-- ============================================================================

CREATE TABLE IF NOT EXISTS execution_lineage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL,
    parent_step_id UUID REFERENCES execution_lineage(id),
    agent_id TEXT NOT NULL,
    step_name TEXT NOT NULL,

    -- Status tracking
    status TEXT DEFAULT 'pending' CHECK (status IN (
        'pending', 'running', 'completed', 'failed', 'skipped', 'cancelled'
    )),

    -- Input/Output artifacts (JSONB for flexibility)
    input_artifacts JSONB DEFAULT '[]'::jsonb,
    output_artifacts JSONB DEFAULT '[]'::jsonb,

    -- Parameters used for this step
    parameters JSONB DEFAULT '{}'::jsonb,

    -- Metrics collected during execution
    metrics JSONB DEFAULT '{}'::jsonb,

    -- Error information
    error_message TEXT,
    error_traceback TEXT,

    -- Timing
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb
);

-- ============================================================================
-- LINEAGE ARTIFACTS TABLE
-- Stores artifact metadata for lineage tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS lineage_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    artifact_type TEXT NOT NULL CHECK (artifact_type IN (
        'data', 'model', 'config', 'document', 'embedding', 'report', 'intermediate'
    )),

    -- Content identification
    checksum TEXT NOT NULL,  -- SHA-256 hash for deduplication
    size_bytes BIGINT NOT NULL,

    -- Location (could be S3 path, local path, etc.)
    location TEXT,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- ARTIFACT USAGE TRACKING
-- Links artifacts to execution steps
-- ============================================================================

CREATE TABLE IF NOT EXISTS artifact_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES lineage_artifacts(id) ON DELETE CASCADE,
    step_id UUID NOT NULL REFERENCES execution_lineage(id) ON DELETE CASCADE,

    -- Usage type
    usage_type TEXT NOT NULL CHECK (usage_type IN ('input', 'output')),

    -- When this usage occurred
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure no duplicate entries
    UNIQUE (artifact_id, step_id, usage_type)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Primary lookups
CREATE INDEX IF NOT EXISTS idx_execution_lineage_workflow_id
    ON execution_lineage(workflow_id);

CREATE INDEX IF NOT EXISTS idx_execution_lineage_parent_step_id
    ON execution_lineage(parent_step_id);

CREATE INDEX IF NOT EXISTS idx_execution_lineage_agent_id
    ON execution_lineage(agent_id);

CREATE INDEX IF NOT EXISTS idx_execution_lineage_status
    ON execution_lineage(status);

-- Time-based queries
CREATE INDEX IF NOT EXISTS idx_execution_lineage_started_at
    ON execution_lineage(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_execution_lineage_created_at
    ON execution_lineage(created_at DESC);

-- Composite index for workflow analysis
CREATE INDEX IF NOT EXISTS idx_execution_lineage_workflow_status
    ON execution_lineage(workflow_id, status, created_at DESC);

-- Artifact indexes
CREATE INDEX IF NOT EXISTS idx_lineage_artifacts_checksum
    ON lineage_artifacts(checksum);

CREATE INDEX IF NOT EXISTS idx_lineage_artifacts_type
    ON lineage_artifacts(artifact_type);

CREATE INDEX IF NOT EXISTS idx_lineage_artifacts_created_at
    ON lineage_artifacts(created_at DESC);

-- Artifact usage indexes
CREATE INDEX IF NOT EXISTS idx_artifact_usage_artifact_id
    ON artifact_usage(artifact_id);

CREATE INDEX IF NOT EXISTS idx_artifact_usage_step_id
    ON artifact_usage(step_id);

-- JSONB indexes for metadata queries
CREATE INDEX IF NOT EXISTS idx_execution_lineage_metadata
    ON execution_lineage USING GIN (metadata);

CREATE INDEX IF NOT EXISTS idx_execution_lineage_metrics
    ON execution_lineage USING GIN (metrics);

CREATE INDEX IF NOT EXISTS idx_lineage_artifacts_metadata
    ON lineage_artifacts USING GIN (metadata);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get full ancestry of a step
CREATE OR REPLACE FUNCTION get_step_ancestry(p_step_id UUID)
RETURNS TABLE (
    step_id UUID,
    parent_step_id UUID,
    agent_id TEXT,
    step_name TEXT,
    depth INTEGER
) AS $$
WITH RECURSIVE ancestry AS (
    -- Base case: the starting step
    SELECT
        el.id,
        el.parent_step_id,
        el.agent_id,
        el.step_name,
        0 AS depth
    FROM execution_lineage el
    WHERE el.id = p_step_id

    UNION ALL

    -- Recursive case: parent steps
    SELECT
        el.id,
        el.parent_step_id,
        el.agent_id,
        el.step_name,
        a.depth + 1
    FROM execution_lineage el
    INNER JOIN ancestry a ON el.id = a.parent_step_id
)
SELECT * FROM ancestry ORDER BY depth DESC;
$$ LANGUAGE SQL;

-- Function to get all descendants of a step
CREATE OR REPLACE FUNCTION get_step_descendants(p_step_id UUID)
RETURNS TABLE (
    step_id UUID,
    parent_step_id UUID,
    agent_id TEXT,
    step_name TEXT,
    depth INTEGER
) AS $$
WITH RECURSIVE descendants AS (
    -- Base case: the starting step
    SELECT
        el.id AS step_id,
        el.parent_step_id,
        el.agent_id,
        el.step_name,
        0 AS depth
    FROM execution_lineage el
    WHERE el.id = p_step_id

    UNION ALL

    -- Recursive case: child steps
    SELECT
        el.id AS step_id,
        el.parent_step_id,
        el.agent_id,
        el.step_name,
        d.depth + 1
    FROM execution_lineage el
    INNER JOIN descendants d ON el.parent_step_id = d.step_id
)
SELECT * FROM descendants WHERE step_id != p_step_id ORDER BY depth;
$$ LANGUAGE SQL;

-- Function to get workflow summary statistics
CREATE OR REPLACE FUNCTION get_workflow_summary(p_workflow_id UUID)
RETURNS JSONB AS $$
DECLARE
    v_summary JSONB;
BEGIN
    SELECT jsonb_build_object(
        'workflow_id', p_workflow_id,
        'total_steps', COUNT(*),
        'completed_steps', COUNT(*) FILTER (WHERE status = 'completed'),
        'failed_steps', COUNT(*) FILTER (WHERE status = 'failed'),
        'skipped_steps', COUNT(*) FILTER (WHERE status = 'skipped'),
        'total_duration_seconds', EXTRACT(EPOCH FROM (MAX(completed_at) - MIN(started_at))),
        'agent_counts', jsonb_object_agg(agent_id, agent_count),
        'success_rate', ROUND(
            COUNT(*) FILTER (WHERE status = 'completed')::NUMERIC /
            NULLIF(COUNT(*) FILTER (WHERE status IN ('completed', 'failed')), 0) * 100, 2
        )
    ) INTO v_summary
    FROM (
        SELECT
            agent_id,
            status,
            started_at,
            completed_at,
            COUNT(*) OVER (PARTITION BY agent_id) as agent_count
        FROM execution_lineage
        WHERE workflow_id = p_workflow_id
    ) subq;

    RETURN v_summary;
END;
$$ LANGUAGE plpgsql;

-- Function to find artifacts that were derived from a given artifact
CREATE OR REPLACE FUNCTION get_derived_artifacts(p_artifact_id UUID)
RETURNS TABLE (
    artifact_id UUID,
    artifact_name TEXT,
    artifact_type TEXT,
    derivation_depth INTEGER
) AS $$
WITH RECURSIVE derived AS (
    -- Base case: steps that used this artifact as input
    SELECT
        au_out.artifact_id,
        la.name,
        la.artifact_type,
        1 AS depth
    FROM artifact_usage au_in
    INNER JOIN artifact_usage au_out ON au_in.step_id = au_out.step_id
    INNER JOIN lineage_artifacts la ON au_out.artifact_id = la.id
    WHERE au_in.artifact_id = p_artifact_id
    AND au_in.usage_type = 'input'
    AND au_out.usage_type = 'output'
    AND au_out.artifact_id != p_artifact_id

    UNION

    -- Recursive case: artifacts derived from derived artifacts
    SELECT
        au_out.artifact_id,
        la.name,
        la.artifact_type,
        d.depth + 1
    FROM derived d
    INNER JOIN artifact_usage au_in ON au_in.artifact_id = d.artifact_id
    INNER JOIN artifact_usage au_out ON au_in.step_id = au_out.step_id
    INNER JOIN lineage_artifacts la ON au_out.artifact_id = la.id
    WHERE au_in.usage_type = 'input'
    AND au_out.usage_type = 'output'
    AND au_out.artifact_id != d.artifact_id
    AND d.depth < 10  -- Limit recursion depth
)
SELECT DISTINCT * FROM derived ORDER BY derivation_depth;
$$ LANGUAGE SQL;

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

-- Enable RLS
ALTER TABLE execution_lineage ENABLE ROW LEVEL SECURITY;
ALTER TABLE lineage_artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifact_usage ENABLE ROW LEVEL SECURITY;

-- Policy for service role (full access)
CREATE POLICY execution_lineage_service_policy ON execution_lineage
    FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY lineage_artifacts_service_policy ON lineage_artifacts
    FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY artifact_usage_service_policy ON artifact_usage
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View for recent executions with basic stats
CREATE OR REPLACE VIEW recent_executions AS
SELECT
    el.workflow_id,
    el.id as step_id,
    el.agent_id,
    el.step_name,
    el.status,
    el.started_at,
    el.completed_at,
    EXTRACT(EPOCH FROM (el.completed_at - el.started_at)) as duration_seconds,
    jsonb_array_length(el.input_artifacts) as input_count,
    jsonb_array_length(el.output_artifacts) as output_count
FROM execution_lineage el
ORDER BY el.created_at DESC;

-- View for workflow health summary
CREATE OR REPLACE VIEW workflow_health AS
SELECT
    workflow_id,
    COUNT(*) as total_steps,
    COUNT(*) FILTER (WHERE status = 'completed') as completed,
    COUNT(*) FILTER (WHERE status = 'failed') as failed,
    COUNT(*) FILTER (WHERE status = 'running') as running,
    MIN(started_at) as workflow_start,
    MAX(completed_at) as workflow_end,
    EXTRACT(EPOCH FROM (MAX(completed_at) - MIN(started_at))) as total_duration_seconds
FROM execution_lineage
GROUP BY workflow_id;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE execution_lineage IS
    'Tracks each step in workflow execution for lineage and provenance';

COMMENT ON TABLE lineage_artifacts IS
    'Stores artifact metadata with checksums for deduplication and tracking';

COMMENT ON TABLE artifact_usage IS
    'Links artifacts to execution steps as inputs or outputs';

COMMENT ON FUNCTION get_step_ancestry IS
    'Returns the full ancestor chain of an execution step';

COMMENT ON FUNCTION get_step_descendants IS
    'Returns all steps that descended from a given step';

COMMENT ON FUNCTION get_workflow_summary IS
    'Returns summary statistics for a workflow execution';

COMMENT ON FUNCTION get_derived_artifacts IS
    'Finds all artifacts that were derived from a given artifact';
