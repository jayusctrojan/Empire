-- Empire v7.3 - Migration 2.2: Add Processing Status Details (JSONB)
-- Task: Add processing_status_details JSONB column for real-time status tracking
--
-- Feature 2: Loading Process Status UI
-- Goal: Track detailed processing stages with timestamps, progress, and error information
--
-- Processing stages:
--   - uploading: File upload in progress
--   - parsing: Document content extraction
--   - embedding: Vector embedding generation
--   - indexing: Storage in Supabase/Neo4j
--   - complete: All processing finished
--   - failed: Processing error occurred

-- Step 1: Add processing_status_details JSONB column to documents table
ALTER TABLE documents
ADD COLUMN processing_status_details JSONB DEFAULT '{}'::jsonb;

-- Step 2: Add processing_status_details to processing_tasks table
ALTER TABLE processing_tasks
ADD COLUMN processing_status_details JSONB DEFAULT '{}'::jsonb;

-- Step 3: Add processing_status_details to crewai_executions table
ALTER TABLE crewai_executions
ADD COLUMN processing_status_details JSONB DEFAULT '{}'::jsonb;

-- Step 4: Add GIN indexes for efficient JSONB querying
CREATE INDEX IF NOT EXISTS idx_documents_processing_status_details
ON documents USING gin(processing_status_details);

CREATE INDEX IF NOT EXISTS idx_processing_tasks_status_details
ON processing_tasks USING gin(processing_status_details);

CREATE INDEX IF NOT EXISTS idx_crewai_executions_status_details
ON crewai_executions USING gin(processing_status_details);

-- Step 5: Create helper function to update processing status
CREATE OR REPLACE FUNCTION update_processing_status(
    p_table_name TEXT,
    p_record_id UUID,
    p_stage TEXT,
    p_progress INTEGER DEFAULT NULL,
    p_message TEXT DEFAULT NULL,
    p_error TEXT DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    v_status_details JSONB;
BEGIN
    -- Build status details JSON
    v_status_details := jsonb_build_object(
        'current_stage', p_stage,
        'updated_at', NOW(),
        'progress_percent', COALESCE(p_progress, 0),
        'message', p_message,
        'error', p_error,
        'stages', jsonb_build_object(
            p_stage, jsonb_build_object(
                'started_at', NOW(),
                'status', CASE WHEN p_error IS NOT NULL THEN 'failed' ELSE 'in_progress' END
            )
        )
    );

    -- Update the appropriate table
    CASE p_table_name
        WHEN 'documents' THEN
            UPDATE documents
            SET processing_status_details = processing_status_details || v_status_details
            WHERE id = p_record_id;

        WHEN 'processing_tasks' THEN
            UPDATE processing_tasks
            SET processing_status_details = processing_status_details || v_status_details
            WHERE id = p_record_id;

        WHEN 'crewai_executions' THEN
            UPDATE crewai_executions
            SET processing_status_details = processing_status_details || v_status_details
            WHERE id = p_record_id;

        ELSE
            RAISE EXCEPTION 'Invalid table name: %', p_table_name;
    END CASE;
END;
$$ LANGUAGE plpgsql;

-- Step 6: Add comments documenting the schema
COMMENT ON COLUMN documents.processing_status_details IS
'Detailed processing status for Feature 2 (Loading Status UI) - v7.3.
Structure: {
  "current_stage": "uploading|parsing|embedding|indexing|complete|failed",
  "progress_percent": 0-100,
  "updated_at": "ISO timestamp",
  "message": "Optional status message",
  "error": "Optional error details",
  "stages": {
    "uploading": {"started_at": "ISO", "completed_at": "ISO", "status": "in_progress|complete|failed"},
    "parsing": {...},
    "embedding": {...},
    "indexing": {...}
  }
}';

COMMENT ON COLUMN processing_tasks.processing_status_details IS
'Detailed Celery task processing status for Feature 2 (Loading Status UI) - v7.3.
Tracks stage-by-stage progress of background tasks.';

COMMENT ON COLUMN crewai_executions.processing_status_details IS
'Detailed CrewAI workflow status for Feature 2 (Loading Status UI) - v7.3.
Tracks multi-agent execution progress and task coordination.';

-- Step 7: Create view for active processing jobs (useful for monitoring)
CREATE OR REPLACE VIEW active_processing_jobs AS
SELECT
    d.id,
    d.document_id,
    d.filename,
    d.processing_status,
    d.processing_status_details->>'current_stage' AS current_stage,
    (d.processing_status_details->>'progress_percent')::INTEGER AS progress_percent,
    d.processing_status_details->>'message' AS status_message,
    (d.processing_status_details->>'updated_at')::TIMESTAMPTZ AS last_update,
    d.created_at,
    EXTRACT(EPOCH FROM (NOW() - d.created_at)) AS processing_time_seconds
FROM documents d
WHERE d.processing_status NOT IN ('complete', 'failed')
  AND d.processing_status_details IS NOT NULL
  AND d.processing_status_details->>'current_stage' IS NOT NULL
ORDER BY d.created_at DESC;

COMMENT ON VIEW active_processing_jobs IS
'Shows all documents currently being processed with detailed status information - v7.3 Feature 2';

-- Step 8: Create function to mark stage as complete
CREATE OR REPLACE FUNCTION complete_processing_stage(
    p_table_name TEXT,
    p_record_id UUID,
    p_stage TEXT
)
RETURNS VOID AS $$
DECLARE
    v_stage_path TEXT;
BEGIN
    v_stage_path := 'stages.' || p_stage;

    CASE p_table_name
        WHEN 'documents' THEN
            UPDATE documents
            SET processing_status_details = jsonb_set(
                processing_status_details,
                ARRAY['stages', p_stage, 'completed_at'],
                to_jsonb(NOW()::TEXT),
                true
            )
            WHERE id = p_record_id;

        WHEN 'processing_tasks' THEN
            UPDATE processing_tasks
            SET processing_status_details = jsonb_set(
                processing_status_details,
                ARRAY['stages', p_stage, 'completed_at'],
                to_jsonb(NOW()::TEXT),
                true
            )
            WHERE id = p_record_id;

        WHEN 'crewai_executions' THEN
            UPDATE crewai_executions
            SET processing_status_details = jsonb_set(
                processing_status_details,
                ARRAY['stages', p_stage, 'completed_at'],
                to_jsonb(NOW()::TEXT),
                true
            )
            WHERE id = p_record_id;
    END CASE;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_processing_status IS
'Helper function to update processing status details for real-time status tracking (v7.3 Feature 2)';

COMMENT ON FUNCTION complete_processing_stage IS
'Helper function to mark a processing stage as complete with timestamp (v7.3 Feature 2)';
