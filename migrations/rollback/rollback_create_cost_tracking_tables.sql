-- ============================================================================
-- ROLLBACK: Cost Tracking Tables
-- Original Migration: create_cost_tracking_tables.sql (Task 30)
-- Date: 2025-11-25
-- ============================================================================
--
-- PURPOSE: Remove cost tracking infrastructure
--
-- WHEN TO USE:
-- - Cost tracking causing performance issues
-- - Need to reset cost data
-- - Switching to alternative cost tracking solution
-- - Storage concerns from large cost_entries table
--
-- WARNING: This will permanently delete ALL cost tracking data!
-- Export data before running if historical costs are needed.
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: DROP MATERIALIZED VIEW AND REFRESH FUNCTION
-- ============================================================================

-- Drop the refresh function first
DROP FUNCTION IF EXISTS refresh_current_month_costs();

-- Drop the materialized view
DROP MATERIALIZED VIEW IF EXISTS current_month_costs;

DO $$ BEGIN RAISE NOTICE 'Dropped current_month_costs materialized view'; END $$;

-- ============================================================================
-- PHASE 2: DROP HELPER FUNCTIONS
-- ============================================================================

DROP FUNCTION IF EXISTS get_current_month_spending(TEXT);
DROP FUNCTION IF EXISTS get_budget_usage_percent(TEXT);

DO $$ BEGIN RAISE NOTICE 'Dropped cost helper functions'; END $$;

-- ============================================================================
-- PHASE 3: DROP TRIGGERS
-- ============================================================================

DROP TRIGGER IF EXISTS trigger_budget_configs_updated_at ON budget_configs;
DROP TRIGGER IF EXISTS trigger_cost_reports_updated_at ON cost_reports;

-- Drop trigger functions
DROP FUNCTION IF EXISTS update_budget_configs_updated_at();
DROP FUNCTION IF EXISTS update_cost_reports_updated_at();

DO $$ BEGIN RAISE NOTICE 'Dropped cost tracking triggers'; END $$;

-- ============================================================================
-- PHASE 4: DROP RLS POLICIES
-- ============================================================================

-- cost_entries policies
DROP POLICY IF EXISTS cost_entries_service_role_all ON cost_entries;
DROP POLICY IF EXISTS cost_entries_user_read ON cost_entries;

-- budget_configs policies
DROP POLICY IF EXISTS budget_configs_service_role_all ON budget_configs;
DROP POLICY IF EXISTS budget_configs_authenticated_read ON budget_configs;

-- cost_reports policies
DROP POLICY IF EXISTS cost_reports_service_role_all ON cost_reports;
DROP POLICY IF EXISTS cost_reports_authenticated_read ON cost_reports;

-- cost_alerts policies
DROP POLICY IF EXISTS cost_alerts_service_role_all ON cost_alerts;

DO $$ BEGIN RAISE NOTICE 'Dropped cost tracking RLS policies'; END $$;

-- ============================================================================
-- PHASE 5: DROP INDEXES
-- ============================================================================

-- cost_entries indexes
DROP INDEX IF EXISTS idx_cost_entries_service;
DROP INDEX IF EXISTS idx_cost_entries_category;
DROP INDEX IF EXISTS idx_cost_entries_timestamp;
DROP INDEX IF EXISTS idx_cost_entries_operation;
DROP INDEX IF EXISTS idx_cost_entries_user_id;
DROP INDEX IF EXISTS idx_cost_entries_session_id;
DROP INDEX IF EXISTS idx_cost_entries_service_timestamp;
DROP INDEX IF EXISTS idx_cost_entries_month_service;

-- budget_configs indexes
DROP INDEX IF EXISTS idx_budget_configs_service;
DROP INDEX IF EXISTS idx_budget_configs_enabled;

-- cost_reports indexes
DROP INDEX IF EXISTS idx_cost_reports_month;
DROP INDEX IF EXISTS idx_cost_reports_total_cost;

-- cost_alerts indexes
DROP INDEX IF EXISTS idx_cost_alerts_service;
DROP INDEX IF EXISTS idx_cost_alerts_sent_at;
DROP INDEX IF EXISTS idx_cost_alerts_type;

DO $$ BEGIN RAISE NOTICE 'Dropped cost tracking indexes'; END $$;

-- ============================================================================
-- PHASE 6: DROP TABLES (Order matters due to FK constraints)
-- ============================================================================

-- Drop cost_alerts first (references budget_configs)
DROP TABLE IF EXISTS cost_alerts CASCADE;
DO $$ BEGIN RAISE NOTICE 'Dropped cost_alerts table'; END $$;

-- Drop cost_reports
DROP TABLE IF EXISTS cost_reports CASCADE;
DO $$ BEGIN RAISE NOTICE 'Dropped cost_reports table'; END $$;

-- Drop budget_configs
DROP TABLE IF EXISTS budget_configs CASCADE;
DO $$ BEGIN RAISE NOTICE 'Dropped budget_configs table'; END $$;

-- Drop cost_entries
DROP TABLE IF EXISTS cost_entries CASCADE;
DO $$ BEGIN RAISE NOTICE 'Dropped cost_entries table'; END $$;

-- ============================================================================
-- PHASE 7: REVOKE PERMISSIONS
-- ============================================================================

-- Permissions are automatically revoked when tables are dropped
-- No explicit REVOKE needed

-- ============================================================================
-- PHASE 8: VERIFICATION
-- ============================================================================

DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name IN ('cost_entries', 'budget_configs', 'cost_reports', 'cost_alerts');

    IF table_count = 0 THEN
        RAISE NOTICE '✅ All cost tracking tables successfully removed';
    ELSE
        RAISE WARNING '⚠️  % cost tracking tables still exist', table_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- POST-ROLLBACK CHECKLIST
-- ============================================================================
--
-- After running this rollback:
--
-- 1. [ ] Update application code to handle missing cost tables
-- 2. [ ] Disable cost tracking in application configuration
-- 3. [ ] Remove cost tracking API endpoints or make them return errors
-- 4. [ ] Update monitoring dashboards to remove cost widgets
-- 5. [ ] Consider external cost tracking service (e.g., AWS Cost Explorer)
--
-- DATA LOSS:
-- - All historical cost entries deleted
-- - Budget configurations lost
-- - Monthly cost reports removed
-- - Alert history cleared
--
-- ALTERNATIVE: Export data before rollback:
-- COPY cost_entries TO '/tmp/cost_entries_backup.csv' CSV HEADER;
-- COPY budget_configs TO '/tmp/budget_configs_backup.csv' CSV HEADER;
-- COPY cost_reports TO '/tmp/cost_reports_backup.csv' CSV HEADER;
--
-- ============================================================================
