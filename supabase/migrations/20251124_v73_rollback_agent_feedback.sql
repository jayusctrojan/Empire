-- Empire v7.3 - Migration 2.5 ROLLBACK: Remove Agent Feedback Table
-- This file provides the rollback procedure for the agent_feedback migration

-- Step 1: Drop trigger and function
DROP TRIGGER IF EXISTS trigger_update_cache_on_feedback ON agent_feedback;
DROP FUNCTION IF EXISTS update_cache_on_feedback();

-- Step 2: Drop functions
DROP FUNCTION IF EXISTS get_feedback_stats(workflow_type, INTEGER);
DROP FUNCTION IF EXISTS submit_agent_feedback(UUID, TEXT, workflow_type, INTEGER, VARCHAR, TEXT, BOOLEAN, workflow_type);

-- Step 3: Drop views
DROP VIEW IF EXISTS routing_improvement_opportunities;
DROP VIEW IF EXISTS agent_feedback_summary;

-- Step 4: Drop indexes
DROP INDEX IF EXISTS idx_agent_feedback_metadata;
DROP INDEX IF EXISTS idx_agent_feedback_routing_issues;
DROP INDEX IF EXISTS idx_agent_feedback_incorrect_routing;
DROP INDEX IF EXISTS idx_agent_feedback_unprocessed;
DROP INDEX IF EXISTS idx_agent_feedback_created_at;
DROP INDEX IF EXISTS idx_agent_feedback_session;
DROP INDEX IF EXISTS idx_agent_feedback_user;
DROP INDEX IF EXISTS idx_agent_feedback_sentiment;
DROP INDEX IF EXISTS idx_agent_feedback_rating;
DROP INDEX IF EXISTS idx_agent_feedback_workflow;
DROP INDEX IF EXISTS idx_agent_feedback_routing_cache;

-- Step 5: Drop table
DROP TABLE IF EXISTS agent_feedback CASCADE;

-- Step 6: Drop enum types
DROP TYPE IF EXISTS sentiment CASCADE;
DROP TYPE IF EXISTS feedback_type CASCADE;

-- Note: This rollback removes all user feedback data and learning capabilities
-- Required for Feature 9 (Intelligent Agent Router) continuous improvement
