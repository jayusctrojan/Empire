-- Empire v7.3 - Write-Ahead Log (WAL) Table
-- Data Persistence P0 Fix - Operations logged BEFORE execution
--
-- Usage:
--   Run this migration on Supabase PostgreSQL to enable WAL functionality
--   supabase db push or apply via Supabase dashboard

-- =============================================================================
-- WAL LOG TABLE
-- =============================================================================

-- Create the WAL log table
CREATE TABLE IF NOT EXISTS wal_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_type VARCHAR(100) NOT NULL,
    operation_data JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error TEXT,
    result JSONB,
    idempotency_key VARCHAR(255),
    correlation_id VARCHAR(255),

    -- Constraints
    CONSTRAINT wal_log_status_check CHECK (
        status IN ('pending', 'in_progress', 'completed', 'failed', 'compensated')
    ),
    CONSTRAINT wal_log_retry_check CHECK (retry_count >= 0)
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Index for finding pending/in-progress entries (primary query)
CREATE INDEX IF NOT EXISTS idx_wal_log_status_created
ON wal_log (status, created_at)
WHERE status IN ('pending', 'in_progress');

-- Index for idempotency key lookups
CREATE INDEX IF NOT EXISTS idx_wal_log_idempotency_key
ON wal_log (idempotency_key)
WHERE idempotency_key IS NOT NULL;

-- Index for correlation ID lookups
CREATE INDEX IF NOT EXISTS idx_wal_log_correlation_id
ON wal_log (correlation_id)
WHERE correlation_id IS NOT NULL;

-- Index for operation type filtering
CREATE INDEX IF NOT EXISTS idx_wal_log_operation_type
ON wal_log (operation_type);

-- Index for cleanup queries (completed entries older than X days)
CREATE INDEX IF NOT EXISTS idx_wal_log_cleanup
ON wal_log (status, created_at)
WHERE status IN ('completed', 'compensated');

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE wal_log IS 'Write-Ahead Log for operation persistence and crash recovery';
COMMENT ON COLUMN wal_log.operation_type IS 'Type of operation (e.g., create_document, sync_graph)';
COMMENT ON COLUMN wal_log.operation_data IS 'Operation parameters as JSON';
COMMENT ON COLUMN wal_log.status IS 'Current status: pending, in_progress, completed, failed, compensated';
COMMENT ON COLUMN wal_log.retry_count IS 'Number of retry attempts';
COMMENT ON COLUMN wal_log.idempotency_key IS 'Optional key for idempotent operations';
COMMENT ON COLUMN wal_log.correlation_id IS 'Optional correlation ID for distributed tracing';

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

-- Enable RLS
ALTER TABLE wal_log ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (for backend access)
CREATE POLICY "Service role full access to wal_log"
ON wal_log
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to get pending entries for replay
CREATE OR REPLACE FUNCTION get_pending_wal_entries(
    p_max_age_hours INTEGER DEFAULT 24,
    p_limit INTEGER DEFAULT 100
)
RETURNS SETOF wal_log
LANGUAGE SQL
STABLE
AS $$
    SELECT *
    FROM wal_log
    WHERE status IN ('pending', 'in_progress')
      AND created_at > NOW() - (p_max_age_hours || ' hours')::INTERVAL
      AND retry_count < max_retries
    ORDER BY created_at ASC
    LIMIT p_limit;
$$;

-- Function to mark entry as in-progress (with atomic check)
CREATE OR REPLACE FUNCTION mark_wal_in_progress(p_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    rows_updated INTEGER;
BEGIN
    UPDATE wal_log
    SET status = 'in_progress',
        updated_at = NOW()
    WHERE id = p_id
      AND status = 'pending';

    GET DIAGNOSTICS rows_updated = ROW_COUNT;
    RETURN rows_updated > 0;
END;
$$;

COMMENT ON FUNCTION get_pending_wal_entries IS 'Get pending WAL entries for replay';
COMMENT ON FUNCTION mark_wal_in_progress IS 'Atomically mark WAL entry as in-progress';
