-- ============================================================================
-- ROLLBACK: Create Audit Logs Table for Security Event Tracking
-- Original Migration: create_audit_logs_table.sql (Task 41)
-- Date: 2025-11-25
-- ============================================================================
--
-- PURPOSE: Remove audit logging infrastructure if causing issues
--
-- WHEN TO USE:
-- - Audit logs consuming excessive storage
-- - Performance issues from logging overhead
-- - Need to reset audit log schema
-- - Emergency rollback for storage issues
--
-- WARNING: Rolling back deletes ALL audit log data permanently!
-- Export audit logs before running if data retention is required.
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: DROP RLS POLICIES AND FUNCTIONS
-- ============================================================================

-- Drop RLS policy on audit_logs
DROP POLICY IF EXISTS admin_only_audit_logs ON audit_logs;

-- Drop helper functions
DROP FUNCTION IF EXISTS log_auth_event(VARCHAR, TEXT, VARCHAR, INET, VARCHAR, TEXT, JSONB);
DROP FUNCTION IF EXISTS log_authz_event(VARCHAR, TEXT, VARCHAR, VARCHAR, TEXT, VARCHAR, VARCHAR, VARCHAR, TEXT);
DROP FUNCTION IF EXISTS log_data_access(TEXT, VARCHAR, TEXT, VARCHAR, VARCHAR, JSONB);

RAISE NOTICE 'Dropped audit logging functions';

-- ============================================================================
-- PHASE 2: DROP INDEXES
-- ============================================================================

-- Drop all indexes on audit_logs table
DROP INDEX IF EXISTS idx_audit_logs_timestamp;
DROP INDEX IF EXISTS idx_audit_logs_user_id;
DROP INDEX IF EXISTS idx_audit_logs_user_timestamp;
DROP INDEX IF EXISTS idx_audit_logs_event_type;
DROP INDEX IF EXISTS idx_audit_logs_category;
DROP INDEX IF EXISTS idx_audit_logs_severity;
DROP INDEX IF EXISTS idx_audit_logs_status;
DROP INDEX IF EXISTS idx_audit_logs_status_timestamp;
DROP INDEX IF EXISTS idx_audit_logs_resource;
DROP INDEX IF EXISTS idx_audit_logs_request_id;
DROP INDEX IF EXISTS idx_audit_logs_session_id;
DROP INDEX IF EXISTS idx_audit_logs_retention;
DROP INDEX IF EXISTS idx_audit_logs_metadata;

RAISE NOTICE 'Dropped 13 audit log indexes';

-- ============================================================================
-- PHASE 3: DROP TABLE
-- ============================================================================

-- WARNING: This permanently deletes all audit log data!
DROP TABLE IF EXISTS audit_logs CASCADE;

RAISE NOTICE '⚠️  Dropped audit_logs table and all data';

-- ============================================================================
-- PHASE 4: VERIFICATION
-- ============================================================================

-- Verify table no longer exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_logs') THEN
        RAISE WARNING '⚠️  audit_logs table still exists!';
    ELSE
        RAISE NOTICE '✅ audit_logs table successfully removed';
    END IF;
END $$;

-- Verify functions no longer exist
DO $$
DECLARE
    func_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO func_count
    FROM information_schema.routines
    WHERE routine_name LIKE 'log_%'
      AND routine_schema = 'public';

    IF func_count = 0 THEN
        RAISE NOTICE '✅ All audit logging functions removed';
    ELSE
        RAISE WARNING '⚠️  % logging functions still exist', func_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- POST-ROLLBACK CHECKLIST
-- ============================================================================
--
-- After running this rollback:
--
-- 1. [ ] Update application code to handle missing audit_logs table
-- 2. [ ] Disable audit logging in application configuration
-- 3. [ ] Remove audit log calls from middleware
-- 4. [ ] Update monitoring to not expect audit metrics
-- 5. [ ] Document reason for rollback in incident log
-- 6. [ ] Plan alternative logging strategy (e.g., file-based, external service)
--
-- COMPLIANCE IMPACT:
-- - SOC 2: Missing audit trail for access control events
-- - GDPR: No user action tracking for data access transparency
-- - HIPAA: Missing PHI access logging
-- - Consider external audit logging service as alternative
--
-- ============================================================================
