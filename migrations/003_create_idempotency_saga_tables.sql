-- Empire v7.3 - Idempotency Keys and Saga Execution Tables
-- Data Persistence P0 Fix - Prevent duplicate processing and track multi-step operations
--
-- Usage:
--   Run this migration on Supabase PostgreSQL
--   supabase db push or apply via Supabase dashboard

-- =============================================================================
-- IDEMPOTENCY KEYS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key VARCHAR(255) PRIMARY KEY,
    operation VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    result JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    request_hash VARCHAR(64),

    -- Constraints
    CONSTRAINT idempotency_status_check CHECK (
        status IN ('in_progress', 'completed', 'failed')
    )
);

-- =============================================================================
-- IDEMPOTENCY INDEXES
-- =============================================================================

-- Primary lookup index (key is already primary key)
-- Index for cleanup query
CREATE INDEX IF NOT EXISTS idx_idempotency_expires_at
ON idempotency_keys (expires_at)
WHERE expires_at IS NOT NULL;

-- Index for operation type analysis
CREATE INDEX IF NOT EXISTS idx_idempotency_operation
ON idempotency_keys (operation);

-- Index for status filtering
CREATE INDEX IF NOT EXISTS idx_idempotency_status
ON idempotency_keys (status);

-- =============================================================================
-- IDEMPOTENCY COMMENTS
-- =============================================================================

COMMENT ON TABLE idempotency_keys IS 'Idempotency key cache for preventing duplicate operations';
COMMENT ON COLUMN idempotency_keys.key IS 'Unique idempotency key from client';
COMMENT ON COLUMN idempotency_keys.operation IS 'Operation name for metrics/debugging';
COMMENT ON COLUMN idempotency_keys.status IS 'Current status: in_progress, completed, failed';
COMMENT ON COLUMN idempotency_keys.result IS 'Cached result for completed operations';
COMMENT ON COLUMN idempotency_keys.request_hash IS 'Hash of request body for verification';

-- =============================================================================
-- SAGA EXECUTIONS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS saga_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    correlation_id VARCHAR(255),
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error TEXT,
    compensation_errors JSONB DEFAULT '[]'::jsonb,

    -- Constraints
    CONSTRAINT saga_status_check CHECK (
        status IN ('pending', 'in_progress', 'completed', 'failed', 'compensating', 'compensated', 'partially_compensated')
    )
);

-- =============================================================================
-- SAGA INDEXES
-- =============================================================================

-- Index for correlation ID lookups
CREATE INDEX IF NOT EXISTS idx_saga_correlation_id
ON saga_executions (correlation_id)
WHERE correlation_id IS NOT NULL;

-- Index for status filtering
CREATE INDEX IF NOT EXISTS idx_saga_status
ON saga_executions (status);

-- Index for name/status queries
CREATE INDEX IF NOT EXISTS idx_saga_name_status
ON saga_executions (name, status);

-- Index for cleanup queries
CREATE INDEX IF NOT EXISTS idx_saga_completed_at
ON saga_executions (completed_at)
WHERE completed_at IS NOT NULL;

-- =============================================================================
-- SAGA COMMENTS
-- =============================================================================

COMMENT ON TABLE saga_executions IS 'Saga pattern execution tracking for multi-step operations';
COMMENT ON COLUMN saga_executions.name IS 'Saga name (e.g., graph_sync, document_processing)';
COMMENT ON COLUMN saga_executions.correlation_id IS 'Correlation ID for distributed tracing';
COMMENT ON COLUMN saga_executions.status IS 'Current saga status';
COMMENT ON COLUMN saga_executions.steps IS 'Array of step statuses and results';
COMMENT ON COLUMN saga_executions.context IS 'Saga execution context data';
COMMENT ON COLUMN saga_executions.compensation_errors IS 'Array of errors from compensation steps';

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

-- Enable RLS on both tables
ALTER TABLE idempotency_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE saga_executions ENABLE ROW LEVEL SECURITY;

-- Service role policies
CREATE POLICY "Service role full access to idempotency_keys"
ON idempotency_keys
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Service role full access to saga_executions"
ON saga_executions
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to check if idempotency key exists and is valid
CREATE OR REPLACE FUNCTION check_idempotency_key(
    p_key VARCHAR(255),
    p_request_hash VARCHAR(64) DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    existing RECORD;
BEGIN
    SELECT * INTO existing
    FROM idempotency_keys
    WHERE key = p_key
      AND (expires_at IS NULL OR expires_at > NOW());

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'exists', false,
            'can_proceed', true
        );
    END IF;

    -- Check request hash if provided
    IF p_request_hash IS NOT NULL AND existing.request_hash IS NOT NULL THEN
        IF existing.request_hash != p_request_hash THEN
            RETURN jsonb_build_object(
                'exists', true,
                'can_proceed', false,
                'error', 'Request body does not match original request',
                'status', existing.status
            );
        END IF;
    END IF;

    -- Return existing result if completed
    IF existing.status = 'completed' THEN
        RETURN jsonb_build_object(
            'exists', true,
            'can_proceed', false,
            'status', 'completed',
            'result', existing.result
        );
    END IF;

    -- In progress
    IF existing.status = 'in_progress' THEN
        RETURN jsonb_build_object(
            'exists', true,
            'can_proceed', false,
            'status', 'in_progress',
            'error', 'Operation already in progress'
        );
    END IF;

    -- Failed - allow retry
    RETURN jsonb_build_object(
        'exists', true,
        'can_proceed', true,
        'status', 'failed',
        'previous_error', existing.error
    );
END;
$$;

-- Function to cleanup expired entries
CREATE OR REPLACE FUNCTION cleanup_expired_idempotency_keys()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM idempotency_keys
    WHERE expires_at < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- Function to get saga status summary
CREATE OR REPLACE FUNCTION get_saga_summary(p_saga_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    saga RECORD;
    step_count INTEGER;
    completed_steps INTEGER;
    failed_steps INTEGER;
BEGIN
    SELECT * INTO saga
    FROM saga_executions
    WHERE id = p_saga_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Saga not found');
    END IF;

    step_count := jsonb_array_length(saga.steps);
    completed_steps := (
        SELECT COUNT(*)
        FROM jsonb_array_elements(saga.steps) s
        WHERE s->>'status' = 'completed'
    );
    failed_steps := (
        SELECT COUNT(*)
        FROM jsonb_array_elements(saga.steps) s
        WHERE s->>'status' = 'failed'
    );

    RETURN jsonb_build_object(
        'id', saga.id,
        'name', saga.name,
        'status', saga.status,
        'total_steps', step_count,
        'completed_steps', completed_steps,
        'failed_steps', failed_steps,
        'created_at', saga.created_at,
        'completed_at', saga.completed_at,
        'has_errors', jsonb_array_length(saga.compensation_errors) > 0
    );
END;
$$;

COMMENT ON FUNCTION check_idempotency_key IS 'Check if idempotency key exists and if operation can proceed';
COMMENT ON FUNCTION cleanup_expired_idempotency_keys IS 'Remove expired idempotency keys';
COMMENT ON FUNCTION get_saga_summary IS 'Get summary of saga execution status';
