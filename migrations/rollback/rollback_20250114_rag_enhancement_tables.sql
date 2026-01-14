-- ============================================================================
-- Rollback: RAG Enhancement Services - Task 141
-- Drops all tables and functions created by 20250114_rag_enhancement_tables.sql
-- ============================================================================

-- Drop functions first (they depend on tables)
DROP FUNCTION IF EXISTS record_agent_outcome(VARCHAR, VARCHAR, BOOLEAN, FLOAT, INTEGER);
DROP FUNCTION IF EXISTS get_retrieval_params(VARCHAR, VARCHAR);
DROP FUNCTION IF EXISTS get_agent_performance_summary(VARCHAR);
DROP FUNCTION IF EXISTS get_avg_rag_metrics(TIMESTAMPTZ, TIMESTAMPTZ);

-- Drop triggers
DROP TRIGGER IF EXISTS trigger_update_retrieval_config_timestamp ON retrieval_parameter_configs;
DROP TRIGGER IF EXISTS trigger_update_agent_perf_timestamp ON agent_performance_history;
DROP TRIGGER IF EXISTS trigger_update_rag_metrics_timestamp ON rag_quality_metrics;

-- Drop trigger functions
DROP FUNCTION IF EXISTS update_retrieval_config_timestamp();
DROP FUNCTION IF EXISTS update_rag_enhancement_timestamp();

-- Drop tables (grounding_results first due to foreign key)
DROP TABLE IF EXISTS grounding_results;
DROP TABLE IF EXISTS retrieval_parameter_configs;
DROP TABLE IF EXISTS agent_performance_history;
DROP TABLE IF EXISTS rag_quality_metrics;

-- ============================================================================
-- Rollback Complete
-- ============================================================================
