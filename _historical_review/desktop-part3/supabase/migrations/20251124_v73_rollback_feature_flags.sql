-- Empire v7.3 - Feature Flag System ROLLBACK
-- Removes feature_flags and feature_flag_audit tables and related objects

-- Step 1: Drop trigger
DROP TRIGGER IF EXISTS trigger_log_feature_flag_changes ON feature_flags;

-- Step 2: Drop functions
DROP FUNCTION IF EXISTS log_feature_flag_change();
DROP FUNCTION IF EXISTS get_feature_flag(VARCHAR, VARCHAR);
DROP FUNCTION IF EXISTS list_feature_flags();

-- Step 3: Drop view
DROP VIEW IF EXISTS feature_flag_statistics;

-- Step 4: Drop indexes from feature_flag_audit
DROP INDEX IF EXISTS idx_feature_flag_audit_changed_by;
DROP INDEX IF EXISTS idx_feature_flag_audit_changed_at;
DROP INDEX IF EXISTS idx_feature_flag_audit_flag_name;

-- Step 5: Drop indexes from feature_flags
DROP INDEX IF EXISTS idx_feature_flags_updated_at;
DROP INDEX IF EXISTS idx_feature_flags_enabled;
DROP INDEX IF EXISTS idx_feature_flags_name;

-- Step 6: Drop tables (CASCADE to handle any dependencies)
DROP TABLE IF EXISTS feature_flag_audit CASCADE;
DROP TABLE IF EXISTS feature_flags CASCADE;

-- Rollback complete - all feature flag infrastructure removed
