-- Empire v7.3 - Migration 2.4 ROLLBACK: Remove Agent Router Cache Table
-- This file provides the rollback procedure for the agent_router_cache migration

-- Step 1: Drop scheduled cleanup job if exists (pg_cron)
-- SELECT cron.unschedule('cleanup-routing-cache');

-- Step 2: Drop view
DROP VIEW IF EXISTS agent_router_cache_analytics;

-- Step 3: Drop functions
DROP FUNCTION IF EXISTS cleanup_expired_routing_cache();
DROP FUNCTION IF EXISTS update_cache_performance(UUID, BOOLEAN, NUMERIC);
DROP FUNCTION IF EXISTS increment_cache_hit(UUID);
DROP FUNCTION IF EXISTS get_cached_routing(VARCHAR, vector, NUMERIC);

-- Step 4: Drop indexes
DROP INDEX IF EXISTS idx_agent_router_factors;
DROP INDEX IF EXISTS idx_agent_router_alternatives;
DROP INDEX IF EXISTS idx_agent_router_embedding;
DROP INDEX IF EXISTS idx_agent_router_hit_count;
DROP INDEX IF EXISTS idx_agent_router_last_used;
DROP INDEX IF EXISTS idx_agent_router_expires_at;
DROP INDEX IF EXISTS idx_agent_router_selected_workflow;
DROP INDEX IF EXISTS idx_agent_router_query_hash;

-- Step 5: Drop table
DROP TABLE IF EXISTS agent_router_cache CASCADE;

-- Step 6: Drop enum types
DROP TYPE IF EXISTS query_complexity CASCADE;
DROP TYPE IF EXISTS workflow_type CASCADE;

-- Note: This rollback removes all routing cache data and analytics
-- Required for Feature 9 (Intelligent Agent Router) functionality
