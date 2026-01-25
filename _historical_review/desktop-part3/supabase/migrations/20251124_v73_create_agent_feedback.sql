-- Empire v7.3 - Migration 2.5: Create Agent Feedback Table
-- Task: Create agent_feedback table for Feature 9 (Intelligent Agent Router)
--
-- Feature 9: Intelligent Agent Router - Feedback Loop
-- Goal: Collect user feedback on routing decisions to continuously improve accuracy
-- Target: Enable learning from user feedback to maintain >90% routing accuracy

-- Step 1: Create feedback_type enum
CREATE TYPE feedback_type AS ENUM (
    'routing_quality',      -- Feedback on routing decision quality
    'workflow_performance', -- Feedback on workflow execution
    'result_quality',       -- Feedback on result quality
    'suggestion'            -- User suggestion for improvement
);

-- Step 2: Create sentiment enum
CREATE TYPE sentiment AS ENUM (
    'positive',
    'neutral',
    'negative'
);

-- Step 3: Create agent_feedback table
CREATE TABLE agent_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Routing context
    routing_cache_id UUID REFERENCES agent_router_cache(id) ON DELETE SET NULL,
    query_text TEXT NOT NULL,
    selected_workflow workflow_type NOT NULL,
    alternative_workflow workflow_type,  -- What user thought should have been used

    -- Feedback details
    feedback_type feedback_type NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    sentiment sentiment,
    feedback_text TEXT,
    improvement_suggestions TEXT,

    -- Routing decision evaluation
    was_routing_correct BOOLEAN,
    preferred_workflow workflow_type,
    routing_issues JSONB DEFAULT '[]'::jsonb,
    -- Structure: [{"issue": "too_slow", "severity": "high", "description": "..."}]

    -- Performance metrics reported by user
    perceived_quality INTEGER CHECK (perceived_quality >= 1 AND perceived_quality <= 5),
    perceived_speed INTEGER CHECK (perceived_speed >= 1 AND perceived_speed <= 5),
    perceived_accuracy INTEGER CHECK (perceived_accuracy >= 1 AND perceived_accuracy <= 5),
    would_use_again BOOLEAN,

    -- Execution context
    execution_id UUID,  -- Link to CrewAI/LangGraph execution
    session_id UUID,
    user_id VARCHAR(255) NOT NULL,
    user_role VARCHAR(100),

    -- Additional context
    query_complexity query_complexity,
    document_count INTEGER,
    execution_time_sec INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    processed_at TIMESTAMPTZ,  -- When feedback was incorporated into learning
    is_processed BOOLEAN DEFAULT FALSE,

    -- Verification and quality
    is_verified BOOLEAN DEFAULT FALSE,  -- Admin verified as quality feedback
    helpful_votes INTEGER DEFAULT 0,    -- Other users found this feedback helpful
    flagged_as_spam BOOLEAN DEFAULT FALSE
);

-- Step 4: Create indexes for efficient querying
CREATE INDEX idx_agent_feedback_routing_cache
ON agent_feedback(routing_cache_id)
WHERE routing_cache_id IS NOT NULL;

CREATE INDEX idx_agent_feedback_workflow
ON agent_feedback(selected_workflow);

CREATE INDEX idx_agent_feedback_rating
ON agent_feedback(rating DESC);

CREATE INDEX idx_agent_feedback_sentiment
ON agent_feedback(sentiment);

CREATE INDEX idx_agent_feedback_user
ON agent_feedback(user_id);

CREATE INDEX idx_agent_feedback_session
ON agent_feedback(session_id)
WHERE session_id IS NOT NULL;

CREATE INDEX idx_agent_feedback_created_at
ON agent_feedback(created_at DESC);

CREATE INDEX idx_agent_feedback_unprocessed
ON agent_feedback(created_at)
WHERE is_processed = FALSE;

CREATE INDEX idx_agent_feedback_incorrect_routing
ON agent_feedback(selected_workflow, preferred_workflow)
WHERE was_routing_correct = FALSE;

-- GIN index for JSONB columns
CREATE INDEX idx_agent_feedback_routing_issues
ON agent_feedback USING gin(routing_issues);

CREATE INDEX idx_agent_feedback_metadata
ON agent_feedback USING gin(metadata);

-- Step 5: Create function to submit feedback
CREATE OR REPLACE FUNCTION submit_agent_feedback(
    p_routing_cache_id UUID,
    p_query_text TEXT,
    p_selected_workflow workflow_type,
    p_rating INTEGER,
    p_user_id VARCHAR,
    p_feedback_text TEXT DEFAULT NULL,
    p_was_routing_correct BOOLEAN DEFAULT NULL,
    p_preferred_workflow workflow_type DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_feedback_id UUID;
    v_sentiment sentiment;
BEGIN
    -- Determine sentiment from rating
    v_sentiment := CASE
        WHEN p_rating >= 4 THEN 'positive'
        WHEN p_rating = 3 THEN 'neutral'
        ELSE 'negative'
    END;

    -- Insert feedback
    INSERT INTO agent_feedback (
        routing_cache_id,
        query_text,
        selected_workflow,
        feedback_type,
        rating,
        sentiment,
        feedback_text,
        was_routing_correct,
        preferred_workflow,
        user_id
    ) VALUES (
        p_routing_cache_id,
        p_query_text,
        p_selected_workflow,
        'routing_quality',
        p_rating,
        v_sentiment,
        p_feedback_text,
        p_was_routing_correct,
        p_preferred_workflow,
        p_user_id
    )
    RETURNING id INTO v_feedback_id;

    -- Update routing cache if linked
    IF p_routing_cache_id IS NOT NULL THEN
        PERFORM update_cache_performance(
            p_routing_cache_id,
            COALESCE(p_was_routing_correct, p_rating >= 4),
            p_rating::NUMERIC
        );
    END IF;

    RETURN v_feedback_id;
END;
$$ LANGUAGE plpgsql;

-- Step 6: Create function to get feedback statistics
CREATE OR REPLACE FUNCTION get_feedback_stats(
    p_workflow workflow_type DEFAULT NULL,
    p_days INTEGER DEFAULT 30
)
RETURNS TABLE (
    workflow workflow_type,
    total_feedback BIGINT,
    avg_rating NUMERIC,
    positive_pct NUMERIC,
    neutral_pct NUMERIC,
    negative_pct NUMERIC,
    correct_routing_pct NUMERIC,
    avg_quality INTEGER,
    avg_speed INTEGER,
    avg_accuracy INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        af.selected_workflow AS workflow,
        COUNT(*) AS total_feedback,
        ROUND(AVG(af.rating), 2) AS avg_rating,
        ROUND(COUNT(*) FILTER (WHERE af.sentiment = 'positive') * 100.0 / COUNT(*), 2) AS positive_pct,
        ROUND(COUNT(*) FILTER (WHERE af.sentiment = 'neutral') * 100.0 / COUNT(*), 2) AS neutral_pct,
        ROUND(COUNT(*) FILTER (WHERE af.sentiment = 'negative') * 100.0 / COUNT(*), 2) AS negative_pct,
        ROUND(COUNT(*) FILTER (WHERE af.was_routing_correct = TRUE) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE af.was_routing_correct IS NOT NULL), 0), 2) AS correct_routing_pct,
        ROUND(AVG(af.perceived_quality))::INTEGER AS avg_quality,
        ROUND(AVG(af.perceived_speed))::INTEGER AS avg_speed,
        ROUND(AVG(af.perceived_accuracy))::INTEGER AS avg_accuracy
    FROM agent_feedback af
    WHERE (p_workflow IS NULL OR af.selected_workflow = p_workflow)
      AND af.created_at >= NOW() - (p_days || ' days')::INTERVAL
      AND af.flagged_as_spam = FALSE
    GROUP BY af.selected_workflow;
END;
$$ LANGUAGE plpgsql;

-- Step 7: Create view for feedback analysis
CREATE OR REPLACE VIEW agent_feedback_summary AS
SELECT
    selected_workflow,
    COUNT(*) AS total_feedback,
    AVG(rating)::NUMERIC(3, 2) AS avg_rating,
    COUNT(*) FILTER (WHERE sentiment = 'positive') AS positive_count,
    COUNT(*) FILTER (WHERE sentiment = 'negative') AS negative_count,
    COUNT(*) FILTER (WHERE was_routing_correct = FALSE) AS incorrect_routing_count,
    AVG(perceived_quality)::NUMERIC(3, 2) AS avg_quality,
    AVG(perceived_speed)::NUMERIC(3, 2) AS avg_speed,
    AVG(perceived_accuracy)::NUMERIC(3, 2) AS avg_accuracy,
    COUNT(*) FILTER (WHERE is_processed = FALSE) AS unprocessed_count,
    MAX(created_at) AS last_feedback_at
FROM agent_feedback
WHERE flagged_as_spam = FALSE
  AND created_at >= NOW() - INTERVAL '30 days'
GROUP BY selected_workflow
ORDER BY total_feedback DESC;

-- Step 8: Create view for routing improvement opportunities
CREATE OR REPLACE VIEW routing_improvement_opportunities AS
SELECT
    af.selected_workflow AS wrong_workflow,
    af.preferred_workflow AS suggested_workflow,
    COUNT(*) AS frequency,
    AVG(af.rating)::NUMERIC(3, 2) AS avg_dissatisfaction_rating,
    array_agg(DISTINCT af.query_complexity) AS query_complexities,
    array_agg(af.feedback_text) FILTER (WHERE af.feedback_text IS NOT NULL) AS feedback_samples
FROM agent_feedback af
WHERE af.was_routing_correct = FALSE
  AND af.preferred_workflow IS NOT NULL
  AND af.flagged_as_spam = FALSE
  AND af.created_at >= NOW() - INTERVAL '90 days'
GROUP BY af.selected_workflow, af.preferred_workflow
HAVING COUNT(*) >= 3  -- At least 3 reports of this issue
ORDER BY frequency DESC, avg_dissatisfaction_rating;

-- Step 9: Add comments documenting the schema
COMMENT ON TABLE agent_feedback IS
'User feedback on agent routing decisions for continuous improvement (v7.3 Feature 9).
Enables learning from user experience to maintain >90% routing accuracy.';

COMMENT ON COLUMN agent_feedback.routing_cache_id IS
'Link to cached routing decision (optional reference)';

COMMENT ON COLUMN agent_feedback.was_routing_correct IS
'User assessment: was the routing decision correct?';

COMMENT ON COLUMN agent_feedback.preferred_workflow IS
'User suggestion: which workflow should have been used instead?';

COMMENT ON COLUMN agent_feedback.routing_issues IS
'Array of specific issues encountered: [{"issue": "too_slow", "severity": "high"}]';

COMMENT ON COLUMN agent_feedback.is_processed IS
'Has this feedback been incorporated into the learning algorithm?';

COMMENT ON VIEW agent_feedback_summary IS
'Summary of feedback by workflow for monitoring routing quality (v7.3 Feature 9)';

COMMENT ON VIEW routing_improvement_opportunities IS
'Identifies patterns where routing decisions were incorrect to improve algorithm (v7.3 Feature 9)';

COMMENT ON FUNCTION submit_agent_feedback IS
'Submit user feedback on routing decision with automatic sentiment analysis (v7.3 Feature 9)';

COMMENT ON FUNCTION get_feedback_stats IS
'Get comprehensive feedback statistics for a workflow over time period (v7.3 Feature 9)';

-- Step 10: Create trigger to update cache when feedback received
CREATE OR REPLACE FUNCTION update_cache_on_feedback()
RETURNS TRIGGER AS $$
BEGIN
    -- If feedback indicates incorrect routing, mark cache entry for review
    IF NEW.was_routing_correct = FALSE AND NEW.routing_cache_id IS NOT NULL THEN
        UPDATE agent_router_cache
        SET failed_executions = failed_executions + 1
        WHERE id = NEW.routing_cache_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_cache_on_feedback
AFTER INSERT ON agent_feedback
FOR EACH ROW
WHEN (NEW.was_routing_correct IS NOT NULL)
EXECUTE FUNCTION update_cache_on_feedback();

COMMENT ON TRIGGER trigger_update_cache_on_feedback ON agent_feedback IS
'Automatically update cache performance metrics when feedback indicates routing issues';
