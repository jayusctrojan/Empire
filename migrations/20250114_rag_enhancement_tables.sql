-- ============================================================================
-- RAG Enhancement Services - Task 141
-- Database tables for RAG quality metrics, agent performance, adaptive retrieval
-- Feature: 008-rag-enhancement-services
-- Created: 2025-01-14
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- Table: rag_quality_metrics
-- Stores RAGAS metrics and quality scores for each query
-- ============================================================================

CREATE TABLE IF NOT EXISTS rag_quality_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL,
    query_text TEXT NOT NULL,
    intent_type VARCHAR(50) NOT NULL CHECK (intent_type IN (
        'factual', 'analytical', 'comparative', 'procedural', 'creative'
    )),

    -- RAGAS Metrics (0.0 - 1.0 scale)
    context_relevance FLOAT CHECK (context_relevance >= 0 AND context_relevance <= 1),
    answer_relevance FLOAT CHECK (answer_relevance >= 0 AND answer_relevance <= 1),
    faithfulness FLOAT CHECK (faithfulness >= 0 AND faithfulness <= 1),
    coverage FLOAT CHECK (coverage >= 0 AND coverage <= 1),

    -- Retrieval Parameters Used
    retrieval_params JSONB DEFAULT '{}',  -- {dense_weight, sparse_weight, fuzzy_weight, top_k}

    -- Agent Selection
    selected_agent_id VARCHAR(20),
    agent_selection_reason TEXT,

    -- Grounding
    grounding_score FLOAT CHECK (grounding_score >= 0 AND grounding_score <= 1),
    ungrounded_claims INTEGER DEFAULT 0 CHECK (ungrounded_claims >= 0),

    -- Output Validation
    validation_passed BOOLEAN DEFAULT true,
    validation_issues JSONB DEFAULT '[]',

    -- User Feedback
    user_feedback INTEGER CHECK (user_feedback IN (-1, 0, 1)),  -- negative, neutral, positive
    feedback_text TEXT,

    -- Performance Tracking
    processing_time_ms INTEGER CHECK (processing_time_ms >= 0),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for rag_quality_metrics
CREATE INDEX IF NOT EXISTS idx_rag_metrics_intent
    ON rag_quality_metrics(intent_type);
CREATE INDEX IF NOT EXISTS idx_rag_metrics_agent
    ON rag_quality_metrics(selected_agent_id);
CREATE INDEX IF NOT EXISTS idx_rag_metrics_created
    ON rag_quality_metrics(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_metrics_query_id
    ON rag_quality_metrics(query_id);
CREATE INDEX IF NOT EXISTS idx_rag_metrics_quality
    ON rag_quality_metrics(context_relevance, faithfulness);
CREATE INDEX IF NOT EXISTS idx_rag_metrics_grounding
    ON rag_quality_metrics(grounding_score);

-- Composite index for dashboard queries
CREATE INDEX IF NOT EXISTS idx_rag_metrics_intent_created
    ON rag_quality_metrics(intent_type, created_at DESC);

-- ============================================================================
-- Table: agent_performance_history
-- Tracks historical performance of each agent per task type
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_performance_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(20) NOT NULL CHECK (agent_id ~ '^AGENT-\d{3}$'),
    task_type VARCHAR(100) NOT NULL,

    -- Performance Metrics
    success_count INTEGER DEFAULT 0 CHECK (success_count >= 0),
    failure_count INTEGER DEFAULT 0 CHECK (failure_count >= 0),
    avg_quality_score FLOAT CHECK (avg_quality_score >= 0 AND avg_quality_score <= 1),
    avg_processing_time_ms INTEGER CHECK (avg_processing_time_ms >= 0),

    -- Time Window for aggregation
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure window_start < window_end
    CHECK (window_start < window_end)
);

-- Indexes for agent_performance_history
CREATE INDEX IF NOT EXISTS idx_agent_perf_agent
    ON agent_performance_history(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_perf_task
    ON agent_performance_history(task_type);
CREATE INDEX IF NOT EXISTS idx_agent_perf_agent_task
    ON agent_performance_history(agent_id, task_type);
CREATE INDEX IF NOT EXISTS idx_agent_perf_window
    ON agent_performance_history(window_start, window_end);
CREATE INDEX IF NOT EXISTS idx_agent_perf_quality
    ON agent_performance_history(avg_quality_score DESC);

-- ============================================================================
-- Table: retrieval_parameter_configs
-- Stores optimal retrieval parameters per intent type and complexity
-- ============================================================================

CREATE TABLE IF NOT EXISTS retrieval_parameter_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_type VARCHAR(50) NOT NULL CHECK (intent_type IN (
        'factual', 'analytical', 'comparative', 'procedural', 'creative'
    )),
    query_complexity VARCHAR(20) NOT NULL CHECK (query_complexity IN (
        'low', 'medium', 'high'
    )),

    -- Hybrid Search Weights (must sum to 1.0)
    dense_weight FLOAT DEFAULT 0.4 CHECK (dense_weight >= 0 AND dense_weight <= 1),
    sparse_weight FLOAT DEFAULT 0.3 CHECK (sparse_weight >= 0 AND sparse_weight <= 1),
    fuzzy_weight FLOAT DEFAULT 0.3 CHECK (fuzzy_weight >= 0 AND fuzzy_weight <= 1),

    -- Retrieval Settings
    top_k INTEGER DEFAULT 10 CHECK (top_k > 0 AND top_k <= 100),
    rerank_threshold FLOAT DEFAULT 0.5 CHECK (rerank_threshold >= 0 AND rerank_threshold <= 1),
    graph_expansion_depth INTEGER DEFAULT 1 CHECK (graph_expansion_depth >= 0 AND graph_expansion_depth <= 5),

    -- Learning Metrics
    total_queries INTEGER DEFAULT 0 CHECK (total_queries >= 0),
    avg_quality_score FLOAT CHECK (avg_quality_score >= 0 AND avg_quality_score <= 1),
    positive_feedback_count INTEGER DEFAULT 0 CHECK (positive_feedback_count >= 0),
    negative_feedback_count INTEGER DEFAULT 0 CHECK (negative_feedback_count >= 0),

    -- Manual Override Flag
    is_manual_override BOOLEAN DEFAULT false,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),

    -- Unique constraint for intent + complexity combination
    UNIQUE(intent_type, query_complexity)
);

-- Indexes for retrieval_parameter_configs
CREATE INDEX IF NOT EXISTS idx_retrieval_config_intent
    ON retrieval_parameter_configs(intent_type);
CREATE INDEX IF NOT EXISTS idx_retrieval_config_complexity
    ON retrieval_parameter_configs(query_complexity);

-- ============================================================================
-- Table: grounding_results
-- Stores claim grounding analysis results
-- ============================================================================

CREATE TABLE IF NOT EXISTS grounding_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL,
    rag_metrics_id UUID REFERENCES rag_quality_metrics(id) ON DELETE CASCADE,

    -- Claim Counts
    total_claims INTEGER NOT NULL CHECK (total_claims >= 0),
    grounded_claims INTEGER NOT NULL CHECK (grounded_claims >= 0),
    ungrounded_claims INTEGER NOT NULL CHECK (ungrounded_claims >= 0),

    -- Claim Details (array of claim objects)
    -- [{claim: string, grounding_score: float, supporting_sources: [{source_id, chunk_id, relevance}]}]
    claim_details JSONB DEFAULT '[]',

    -- Overall Scores
    overall_grounding_score FLOAT NOT NULL CHECK (
        overall_grounding_score >= 0 AND overall_grounding_score <= 1
    ),
    confidence_level VARCHAR(20) NOT NULL CHECK (confidence_level IN (
        'high', 'medium', 'low'
    )),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure claim counts are consistent
    CHECK (grounded_claims + ungrounded_claims = total_claims)
);

-- Indexes for grounding_results
CREATE INDEX IF NOT EXISTS idx_grounding_query
    ON grounding_results(query_id);
CREATE INDEX IF NOT EXISTS idx_grounding_score
    ON grounding_results(overall_grounding_score);
CREATE INDEX IF NOT EXISTS idx_grounding_confidence
    ON grounding_results(confidence_level);
CREATE INDEX IF NOT EXISTS idx_grounding_metrics
    ON grounding_results(rag_metrics_id);
CREATE INDEX IF NOT EXISTS idx_grounding_created
    ON grounding_results(created_at DESC);

-- ============================================================================
-- Row Level Security (RLS)
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE rag_quality_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_performance_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE retrieval_parameter_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE grounding_results ENABLE ROW LEVEL SECURITY;

-- Policies for rag_quality_metrics
CREATE POLICY "Service role has full access to rag_quality_metrics"
    ON rag_quality_metrics FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Authenticated users can read rag_quality_metrics"
    ON rag_quality_metrics FOR SELECT
    TO authenticated
    USING (true);

-- Policies for agent_performance_history
CREATE POLICY "Service role has full access to agent_performance_history"
    ON agent_performance_history FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Authenticated users can read agent_performance_history"
    ON agent_performance_history FOR SELECT
    TO authenticated
    USING (true);

-- Policies for retrieval_parameter_configs
CREATE POLICY "Service role has full access to retrieval_parameter_configs"
    ON retrieval_parameter_configs FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Authenticated users can read retrieval_parameter_configs"
    ON retrieval_parameter_configs FOR SELECT
    TO authenticated
    USING (true);

-- Policies for grounding_results
CREATE POLICY "Service role has full access to grounding_results"
    ON grounding_results FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Authenticated users can read grounding_results"
    ON grounding_results FOR SELECT
    TO authenticated
    USING (true);

-- ============================================================================
-- Update Triggers
-- ============================================================================

-- Function for updating timestamps
CREATE OR REPLACE FUNCTION update_rag_enhancement_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for rag_quality_metrics
CREATE TRIGGER trigger_update_rag_metrics_timestamp
    BEFORE UPDATE ON rag_quality_metrics
    FOR EACH ROW
    EXECUTE FUNCTION update_rag_enhancement_timestamp();

-- Trigger for agent_performance_history
CREATE TRIGGER trigger_update_agent_perf_timestamp
    BEFORE UPDATE ON agent_performance_history
    FOR EACH ROW
    EXECUTE FUNCTION update_rag_enhancement_timestamp();

-- Function for updating last_updated on retrieval configs
CREATE OR REPLACE FUNCTION update_retrieval_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for retrieval_parameter_configs
CREATE TRIGGER trigger_update_retrieval_config_timestamp
    BEFORE UPDATE ON retrieval_parameter_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_retrieval_config_timestamp();

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function: Get average RAGAS metrics for a time period
CREATE OR REPLACE FUNCTION get_avg_rag_metrics(
    p_start_date TIMESTAMPTZ DEFAULT NOW() - INTERVAL '30 days',
    p_end_date TIMESTAMPTZ DEFAULT NOW()
)
RETURNS TABLE (
    avg_context_relevance FLOAT,
    avg_answer_relevance FLOAT,
    avg_faithfulness FLOAT,
    avg_coverage FLOAT,
    avg_grounding_score FLOAT,
    total_queries BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        AVG(context_relevance)::FLOAT,
        AVG(answer_relevance)::FLOAT,
        AVG(faithfulness)::FLOAT,
        AVG(coverage)::FLOAT,
        AVG(grounding_score)::FLOAT,
        COUNT(*)::BIGINT
    FROM rag_quality_metrics
    WHERE created_at BETWEEN p_start_date AND p_end_date;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: Get agent performance summary
CREATE OR REPLACE FUNCTION get_agent_performance_summary(p_agent_id VARCHAR(20))
RETURNS TABLE (
    task_type VARCHAR(100),
    total_success INTEGER,
    total_failure INTEGER,
    success_rate FLOAT,
    avg_quality FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        aph.task_type,
        SUM(aph.success_count)::INTEGER,
        SUM(aph.failure_count)::INTEGER,
        CASE
            WHEN SUM(aph.success_count + aph.failure_count) > 0
            THEN SUM(aph.success_count)::FLOAT / SUM(aph.success_count + aph.failure_count)
            ELSE 0.0
        END,
        AVG(aph.avg_quality_score)::FLOAT
    FROM agent_performance_history aph
    WHERE aph.agent_id = p_agent_id
    GROUP BY aph.task_type;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: Get optimal retrieval parameters
CREATE OR REPLACE FUNCTION get_retrieval_params(
    p_intent_type VARCHAR(50),
    p_complexity VARCHAR(20)
)
RETURNS TABLE (
    dense_weight FLOAT,
    sparse_weight FLOAT,
    fuzzy_weight FLOAT,
    top_k INTEGER,
    rerank_threshold FLOAT,
    graph_expansion_depth INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        rpc.dense_weight,
        rpc.sparse_weight,
        rpc.fuzzy_weight,
        rpc.top_k,
        rpc.rerank_threshold,
        rpc.graph_expansion_depth
    FROM retrieval_parameter_configs rpc
    WHERE rpc.intent_type = p_intent_type
    AND rpc.query_complexity = p_complexity;

    -- If no config found, return defaults
    IF NOT FOUND THEN
        RETURN QUERY SELECT 0.4::FLOAT, 0.3::FLOAT, 0.3::FLOAT, 10::INTEGER, 0.5::FLOAT, 1::INTEGER;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: Record agent outcome for performance tracking
CREATE OR REPLACE FUNCTION record_agent_outcome(
    p_agent_id VARCHAR(20),
    p_task_type VARCHAR(100),
    p_success BOOLEAN,
    p_quality_score FLOAT,
    p_processing_time_ms INTEGER
)
RETURNS void AS $$
DECLARE
    v_window_start TIMESTAMPTZ := DATE_TRUNC('day', NOW());
    v_window_end TIMESTAMPTZ := DATE_TRUNC('day', NOW()) + INTERVAL '1 day';
BEGIN
    INSERT INTO agent_performance_history (
        agent_id, task_type,
        success_count, failure_count,
        avg_quality_score, avg_processing_time_ms,
        window_start, window_end
    )
    VALUES (
        p_agent_id, p_task_type,
        CASE WHEN p_success THEN 1 ELSE 0 END,
        CASE WHEN p_success THEN 0 ELSE 1 END,
        p_quality_score, p_processing_time_ms,
        v_window_start, v_window_end
    )
    ON CONFLICT (agent_id, task_type)
    WHERE window_start = v_window_start AND window_end = v_window_end
    DO UPDATE SET
        success_count = agent_performance_history.success_count + CASE WHEN p_success THEN 1 ELSE 0 END,
        failure_count = agent_performance_history.failure_count + CASE WHEN p_success THEN 0 ELSE 1 END,
        avg_quality_score = (
            (agent_performance_history.avg_quality_score *
             (agent_performance_history.success_count + agent_performance_history.failure_count)) +
            p_quality_score
        ) / (agent_performance_history.success_count + agent_performance_history.failure_count + 1),
        avg_processing_time_ms = (
            (agent_performance_history.avg_processing_time_ms *
             (agent_performance_history.success_count + agent_performance_history.failure_count)) +
            p_processing_time_ms
        ) / (agent_performance_history.success_count + agent_performance_history.failure_count + 1),
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- Default Retrieval Parameter Configurations
-- ============================================================================

-- Insert default configurations for each intent type and complexity
INSERT INTO retrieval_parameter_configs
    (intent_type, query_complexity, dense_weight, sparse_weight, fuzzy_weight, top_k, rerank_threshold, graph_expansion_depth)
VALUES
    -- Factual queries - favor precision
    ('factual', 'low', 0.5, 0.3, 0.2, 5, 0.6, 0),
    ('factual', 'medium', 0.5, 0.3, 0.2, 10, 0.5, 1),
    ('factual', 'high', 0.5, 0.3, 0.2, 15, 0.4, 1),

    -- Analytical queries - favor recall
    ('analytical', 'low', 0.4, 0.3, 0.3, 10, 0.5, 1),
    ('analytical', 'medium', 0.4, 0.3, 0.3, 20, 0.4, 2),
    ('analytical', 'high', 0.4, 0.3, 0.3, 30, 0.3, 3),

    -- Comparative queries - need multiple sources
    ('comparative', 'low', 0.4, 0.4, 0.2, 15, 0.5, 1),
    ('comparative', 'medium', 0.4, 0.4, 0.2, 25, 0.4, 2),
    ('comparative', 'high', 0.4, 0.4, 0.2, 35, 0.3, 3),

    -- Procedural queries - balanced approach
    ('procedural', 'low', 0.45, 0.35, 0.2, 8, 0.55, 1),
    ('procedural', 'medium', 0.45, 0.35, 0.2, 15, 0.45, 2),
    ('procedural', 'high', 0.45, 0.35, 0.2, 25, 0.35, 2),

    -- Creative queries - more fuzzy matching
    ('creative', 'low', 0.3, 0.3, 0.4, 10, 0.4, 1),
    ('creative', 'medium', 0.3, 0.3, 0.4, 20, 0.35, 2),
    ('creative', 'high', 0.3, 0.3, 0.4, 30, 0.3, 3)
ON CONFLICT (intent_type, query_complexity) DO NOTHING;

-- ============================================================================
-- Grants
-- ============================================================================

-- Grant permissions to service role
GRANT ALL ON rag_quality_metrics TO service_role;
GRANT ALL ON agent_performance_history TO service_role;
GRANT ALL ON retrieval_parameter_configs TO service_role;
GRANT ALL ON grounding_results TO service_role;

-- Grant read access to authenticated users
GRANT SELECT ON rag_quality_metrics TO authenticated;
GRANT SELECT ON agent_performance_history TO authenticated;
GRANT SELECT ON retrieval_parameter_configs TO authenticated;
GRANT SELECT ON grounding_results TO authenticated;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE rag_quality_metrics IS
    'Stores RAGAS quality metrics for each RAG query - Task 141';
COMMENT ON TABLE agent_performance_history IS
    'Historical performance tracking per agent per task type - Task 141';
COMMENT ON TABLE retrieval_parameter_configs IS
    'Optimal retrieval parameters by intent type and complexity - Task 141';
COMMENT ON TABLE grounding_results IS
    'Claim grounding analysis and citation verification - Task 141';

COMMENT ON COLUMN rag_quality_metrics.context_relevance IS
    'RAGAS metric: How relevant are retrieved chunks to the query (0-1)';
COMMENT ON COLUMN rag_quality_metrics.answer_relevance IS
    'RAGAS metric: How relevant is the answer to the query (0-1)';
COMMENT ON COLUMN rag_quality_metrics.faithfulness IS
    'RAGAS metric: How faithful is the answer to the retrieved context (0-1)';
COMMENT ON COLUMN rag_quality_metrics.coverage IS
    'RAGAS metric: How much of the relevant info is covered (0-1)';

COMMENT ON FUNCTION get_avg_rag_metrics IS
    'Returns average RAGAS metrics for a given time period';
COMMENT ON FUNCTION get_agent_performance_summary IS
    'Returns performance summary for a specific agent';
COMMENT ON FUNCTION get_retrieval_params IS
    'Returns optimal retrieval parameters for intent type and complexity';
COMMENT ON FUNCTION record_agent_outcome IS
    'Records agent execution outcome for performance tracking';

-- ============================================================================
-- Migration Complete
-- ============================================================================
