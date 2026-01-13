-- Feature 007: Content Prep Agent - Task 129
-- Agent Clarification Tables for CKO Chat Integration
--
-- Creates tables for:
-- 1. Agent chat sessions (tracks agent-user communication sessions)
-- 2. Agent clarification requests (stores clarification questions and responses)
-- 3. Clarification conversation logs (audit trail)

-- ============================================================================
-- Agent Chat Sessions
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,           -- e.g., "AGENT-016"
    user_id UUID NOT NULL,                   -- Reference to user
    is_active BOOLEAN DEFAULT TRUE,
    title VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes
    CONSTRAINT fk_agent_sessions_user FOREIGN KEY (user_id)
        REFERENCES auth.users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_sessions_user_agent
    ON agent_chat_sessions(user_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_active
    ON agent_chat_sessions(is_active) WHERE is_active = TRUE;

-- ============================================================================
-- Agent Clarification Requests
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_clarification_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES agent_chat_sessions(id) ON DELETE CASCADE,
    agent_id VARCHAR(50) NOT NULL,
    user_id UUID NOT NULL,
    message TEXT NOT NULL,                   -- The clarification question
    clarification_type VARCHAR(50) NOT NULL, -- ordering, content_type, completeness, etc.
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, answered, timeout, cancelled
    context JSONB DEFAULT '{}',              -- Additional context (content_set_id, files, etc.)
    response TEXT,                           -- User's response
    response_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('pending', 'answered', 'timeout', 'cancelled')),
    CONSTRAINT valid_clarification_type CHECK (clarification_type IN (
        'ordering', 'content_type', 'completeness', 'metadata', 'general'
    ))
);

CREATE INDEX IF NOT EXISTS idx_clarification_requests_user_status
    ON agent_clarification_requests(user_id, status);
CREATE INDEX IF NOT EXISTS idx_clarification_requests_agent
    ON agent_clarification_requests(agent_id);
CREATE INDEX IF NOT EXISTS idx_clarification_requests_pending
    ON agent_clarification_requests(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_clarification_requests_expires
    ON agent_clarification_requests(expires_at) WHERE status = 'pending';

-- ============================================================================
-- Clarification Conversation Logs (Audit Trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS clarification_conversation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_set_id UUID,                     -- Reference to content set being clarified
    agent_id VARCHAR(50) NOT NULL,
    user_id UUID NOT NULL,
    question TEXT NOT NULL,
    answer TEXT,                             -- NULL if timeout/cancelled
    outcome VARCHAR(50) NOT NULL,            -- ordering_updated, no_change, timeout, cancelled
    clarification_type VARCHAR(50) NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_outcome CHECK (outcome IN (
        'ordering_updated', 'no_change', 'timeout', 'cancelled', 'partial_update'
    ))
);

CREATE INDEX IF NOT EXISTS idx_clarification_logs_content_set
    ON clarification_conversation_logs(content_set_id);
CREATE INDEX IF NOT EXISTS idx_clarification_logs_user
    ON clarification_conversation_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_clarification_logs_agent
    ON clarification_conversation_logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_clarification_logs_created
    ON clarification_conversation_logs(created_at DESC);

-- ============================================================================
-- Row Level Security
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE agent_chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_clarification_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE clarification_conversation_logs ENABLE ROW LEVEL SECURITY;

-- Policies for agent_chat_sessions
CREATE POLICY "Users can view their own agent sessions"
    ON agent_chat_sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can manage agent sessions"
    ON agent_chat_sessions FOR ALL
    USING (auth.role() = 'service_role');

-- Policies for agent_clarification_requests
CREATE POLICY "Users can view their own clarification requests"
    ON agent_clarification_requests FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can update their own pending requests"
    ON agent_clarification_requests FOR UPDATE
    USING (auth.uid() = user_id AND status = 'pending');

CREATE POLICY "Service role can manage clarification requests"
    ON agent_clarification_requests FOR ALL
    USING (auth.role() = 'service_role');

-- Policies for clarification_conversation_logs
CREATE POLICY "Users can view their own clarification logs"
    ON clarification_conversation_logs FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can manage clarification logs"
    ON clarification_conversation_logs FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function to auto-expire pending requests
CREATE OR REPLACE FUNCTION expire_pending_clarification_requests()
RETURNS void AS $$
BEGIN
    UPDATE agent_clarification_requests
    SET status = 'timeout', updated_at = NOW()
    WHERE status = 'pending'
    AND expires_at < NOW();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get pending clarification count for user
CREATE OR REPLACE FUNCTION get_pending_agent_clarifications_count(p_user_id UUID)
RETURNS INTEGER AS $$
DECLARE
    count_result INTEGER;
BEGIN
    SELECT COUNT(*) INTO count_result
    FROM agent_clarification_requests
    WHERE user_id = p_user_id AND status = 'pending';

    RETURN count_result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- Update Trigger
-- ============================================================================

CREATE OR REPLACE FUNCTION update_agent_clarification_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_agent_sessions_timestamp
    BEFORE UPDATE ON agent_chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_clarification_timestamp();

CREATE TRIGGER trigger_update_clarification_requests_timestamp
    BEFORE UPDATE ON agent_clarification_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_clarification_timestamp();

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE agent_chat_sessions IS
    'Chat sessions between AI agents and users for clarification communication';
COMMENT ON TABLE agent_clarification_requests IS
    'Clarification requests from agents to users with response tracking';
COMMENT ON TABLE clarification_conversation_logs IS
    'Audit trail of all clarification conversations for compliance';

COMMENT ON COLUMN agent_clarification_requests.clarification_type IS
    'Type of clarification: ordering, content_type, completeness, metadata, general';
COMMENT ON COLUMN agent_clarification_requests.status IS
    'Request status: pending, answered, timeout, cancelled';
COMMENT ON COLUMN clarification_conversation_logs.outcome IS
    'Result of clarification: ordering_updated, no_change, timeout, cancelled, partial_update';
