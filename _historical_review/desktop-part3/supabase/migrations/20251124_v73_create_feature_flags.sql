-- Empire v7.3 - Feature Flag System
-- Creates feature_flags and feature_flag_audit tables for zero-cost flag management
-- Uses existing Supabase PostgreSQL + Upstash Redis infrastructure

-- Step 1: Create feature_flags table
CREATE TABLE IF NOT EXISTS feature_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_name VARCHAR(100) UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT FALSE,
    description TEXT,
    rollout_percentage INTEGER DEFAULT 0 CHECK (rollout_percentage >= 0 AND rollout_percentage <= 100),

    -- User segments for targeted rollouts (array of user IDs or criteria)
    user_segments JSONB DEFAULT '[]'::jsonb,

    -- Additional metadata (feature dependencies, experimental flags, etc.)
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Audit fields
    created_by VARCHAR(255),
    updated_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Step 2: Create feature_flag_audit table for compliance
CREATE TABLE IF NOT EXISTS feature_flag_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_name VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL, -- 'created', 'enabled', 'disabled', 'updated', 'deleted'
    previous_state JSONB,
    new_state JSONB,
    changed_by VARCHAR(255) NOT NULL,
    changed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Optional context (reason for change, ticket number, etc.)
    change_context JSONB DEFAULT '{}'::jsonb
);

-- Step 3: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_feature_flags_name ON feature_flags(flag_name);
CREATE INDEX IF NOT EXISTS idx_feature_flags_enabled ON feature_flags(enabled);
CREATE INDEX IF NOT EXISTS idx_feature_flags_updated_at ON feature_flags(updated_at);
CREATE INDEX IF NOT EXISTS idx_feature_flag_audit_flag_name ON feature_flag_audit(flag_name);
CREATE INDEX IF NOT EXISTS idx_feature_flag_audit_changed_at ON feature_flag_audit(changed_at);
CREATE INDEX IF NOT EXISTS idx_feature_flag_audit_changed_by ON feature_flag_audit(changed_by);

-- Step 4: Create function to log flag changes automatically
CREATE OR REPLACE FUNCTION log_feature_flag_change()
RETURNS TRIGGER AS $$
DECLARE
    v_action VARCHAR(50);
    v_previous_state JSONB;
    v_new_state JSONB;
BEGIN
    -- Determine action type
    IF TG_OP = 'INSERT' THEN
        v_action := 'created';
        v_previous_state := NULL;
        v_new_state := row_to_json(NEW)::jsonb;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.enabled = FALSE AND NEW.enabled = TRUE THEN
            v_action := 'enabled';
        ELSIF OLD.enabled = TRUE AND NEW.enabled = FALSE THEN
            v_action := 'disabled';
        ELSE
            v_action := 'updated';
        END IF;
        v_previous_state := row_to_json(OLD)::jsonb;
        v_new_state := row_to_json(NEW)::jsonb;
    ELSIF TG_OP = 'DELETE' THEN
        v_action := 'deleted';
        v_previous_state := row_to_json(OLD)::jsonb;
        v_new_state := NULL;
    END IF;

    -- Insert audit log
    INSERT INTO feature_flag_audit (
        flag_name,
        action,
        previous_state,
        new_state,
        changed_by
    ) VALUES (
        COALESCE(NEW.flag_name, OLD.flag_name),
        v_action,
        v_previous_state,
        v_new_state,
        COALESCE(NEW.updated_by, OLD.updated_by, 'system')
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 5: Create trigger for automatic audit logging
DROP TRIGGER IF EXISTS trigger_log_feature_flag_changes ON feature_flags;
CREATE TRIGGER trigger_log_feature_flag_changes
    AFTER INSERT OR UPDATE OR DELETE ON feature_flags
    FOR EACH ROW
    EXECUTE FUNCTION log_feature_flag_change();

-- Step 6: Create helper function to get flag state
CREATE OR REPLACE FUNCTION get_feature_flag(
    p_flag_name VARCHAR,
    p_user_id VARCHAR DEFAULT NULL
)
RETURNS JSONB AS $$
DECLARE
    v_flag RECORD;
    v_user_hash INTEGER;
    v_is_in_segment BOOLEAN := FALSE;
BEGIN
    -- Get flag data
    SELECT * INTO v_flag
    FROM feature_flags
    WHERE flag_name = p_flag_name;

    -- Flag not found
    IF NOT FOUND THEN
        RETURN jsonb_build_object('enabled', false, 'reason', 'flag_not_found');
    END IF;

    -- Flag is disabled globally
    IF NOT v_flag.enabled THEN
        RETURN jsonb_build_object('enabled', false, 'reason', 'flag_disabled');
    END IF;

    -- Check user segments if provided
    IF p_user_id IS NOT NULL AND jsonb_array_length(v_flag.user_segments) > 0 THEN
        -- Check if user is in allowed segments
        SELECT EXISTS(
            SELECT 1
            FROM jsonb_array_elements_text(v_flag.user_segments) AS segment
            WHERE segment = p_user_id
        ) INTO v_is_in_segment;

        IF NOT v_is_in_segment THEN
            RETURN jsonb_build_object('enabled', false, 'reason', 'not_in_segment');
        END IF;
    END IF;

    -- Check rollout percentage if user_id provided
    IF p_user_id IS NOT NULL AND v_flag.rollout_percentage < 100 THEN
        -- Hash user_id to deterministic 0-99 value
        v_user_hash := abs(hashtext(p_user_id)) % 100;

        IF v_user_hash >= v_flag.rollout_percentage THEN
            RETURN jsonb_build_object('enabled', false, 'reason', 'rollout_percentage');
        END IF;
    END IF;

    -- Flag is enabled for this user
    RETURN jsonb_build_object(
        'enabled', true,
        'reason', 'enabled',
        'metadata', v_flag.metadata,
        'rollout_percentage', v_flag.rollout_percentage
    );
END;
$$ LANGUAGE plpgsql;

-- Step 7: Create helper function to list all flags
CREATE OR REPLACE FUNCTION list_feature_flags()
RETURNS TABLE (
    flag_name VARCHAR,
    enabled BOOLEAN,
    description TEXT,
    rollout_percentage INTEGER,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ff.flag_name,
        ff.enabled,
        ff.description,
        ff.rollout_percentage,
        ff.updated_at
    FROM feature_flags ff
    ORDER BY ff.flag_name;
END;
$$ LANGUAGE plpgsql;

-- Step 8: Create view for flag statistics
CREATE OR REPLACE VIEW feature_flag_statistics AS
SELECT
    ff.flag_name,
    ff.enabled,
    ff.rollout_percentage,
    COUNT(DISTINCT ffa.id) AS change_count,
    MAX(ffa.changed_at) AS last_changed,
    COUNT(DISTINCT CASE WHEN ffa.action = 'enabled' THEN ffa.id END) AS enable_count,
    COUNT(DISTINCT CASE WHEN ffa.action = 'disabled' THEN ffa.id END) AS disable_count,
    ff.created_at,
    ff.updated_at
FROM feature_flags ff
LEFT JOIN feature_flag_audit ffa ON ff.flag_name = ffa.flag_name
GROUP BY ff.id, ff.flag_name, ff.enabled, ff.rollout_percentage, ff.created_at, ff.updated_at;

-- Step 9: Insert initial feature flags for Empire v7.3 (all disabled by default)
INSERT INTO feature_flags (flag_name, enabled, description, rollout_percentage, metadata, created_by)
VALUES
    (
        'feature_department_research_development',
        FALSE,
        'Feature 1: Enable Research & Development department (12th department)',
        0,
        '{"version": "v7.3", "feature_id": "F1", "migration": "20251124_v73_add_research_development_department.sql"}'::jsonb,
        'system'
    ),
    (
        'feature_processing_status_details',
        FALSE,
        'Feature 2: Enable detailed processing status tracking with JSONB columns',
        0,
        '{"version": "v7.3", "feature_id": "F2", "migration": "20251124_v73_add_processing_status_details.sql"}'::jsonb,
        'system'
    ),
    (
        'feature_source_metadata',
        FALSE,
        'Feature 3: Enable source metadata and citation management',
        0,
        '{"version": "v7.3", "feature_id": "F3", "migration": "20251124_v73_add_source_metadata.sql"}'::jsonb,
        'system'
    ),
    (
        'feature_agent_router_cache',
        FALSE,
        'Feature 4: Enable intelligent agent routing cache with vector similarity',
        0,
        '{"version": "v7.3", "feature_id": "F4", "migration": "20251124_v73_create_agent_router_cache.sql"}'::jsonb,
        'system'
    ),
    (
        'feature_agent_feedback',
        FALSE,
        'Feature 5: Enable agent feedback collection system',
        0,
        '{"version": "v7.3", "feature_id": "F5", "migration": "20251124_v73_create_agent_feedback.sql"}'::jsonb,
        'system'
    ),
    (
        'feature_course_management',
        FALSE,
        'Feature 6: Enable LMS course content addition and management',
        0,
        '{"version": "v7.3", "feature_id": "F6", "migration": "20251124_v73_create_course_structure_tables.sql"}'::jsonb,
        'system'
    ),
    (
        'feature_enhanced_search',
        FALSE,
        'Feature 7: Enable enhanced search capabilities with filters',
        0,
        '{"version": "v7.3", "feature_id": "F7", "requires": ["F3"]}'::jsonb,
        'system'
    ),
    (
        'feature_book_processing',
        FALSE,
        'Feature 8: Enable book processing with chapter detection (PDF, EPUB, MOBI)',
        0,
        '{"version": "v7.3", "feature_id": "F8", "migration": "20251124_v73_create_book_metadata_tables.sql"}'::jsonb,
        'system'
    ),
    (
        'feature_bulk_embeddings',
        FALSE,
        'Feature 9: Enable bulk embedding generation for performance',
        0,
        '{"version": "v7.3", "feature_id": "F9", "requires": ["F2"]}'::jsonb,
        'system'
    )
ON CONFLICT (flag_name) DO NOTHING;

-- Step 10: Add comment documentation
COMMENT ON TABLE feature_flags IS 'Feature flag management for Empire v7.3 - zero-cost solution using Supabase + Redis cache';
COMMENT ON TABLE feature_flag_audit IS 'Audit trail for feature flag changes - compliance and debugging';
COMMENT ON FUNCTION get_feature_flag(VARCHAR, VARCHAR) IS 'Check if a feature flag is enabled for a given user with rollout percentage support';
COMMENT ON FUNCTION list_feature_flags() IS 'List all feature flags with their current state';
COMMENT ON VIEW feature_flag_statistics IS 'Statistics and change history for each feature flag';

-- Migration complete
