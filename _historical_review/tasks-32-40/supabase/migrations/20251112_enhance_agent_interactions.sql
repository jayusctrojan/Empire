-- Task 39.1: Enhanced Inter-Agent Interaction Schema
-- Adds support for events, state synchronization, conflict resolution, and advanced messaging

-- Add new columns to crewai_agent_interactions table
ALTER TABLE crewai_agent_interactions

-- Event Publication Fields (Subtask 39.3)
ADD COLUMN event_type VARCHAR(100),
ADD COLUMN event_data JSONB,

-- State Synchronization Fields (Subtask 39.4)
ADD COLUMN state_key VARCHAR(255),
ADD COLUMN state_value JSONB,
ADD COLUMN state_version INTEGER DEFAULT 1,
ADD COLUMN previous_state JSONB,

-- Conflict Resolution Fields (Subtask 39.5)
ADD COLUMN conflict_detected BOOLEAN DEFAULT FALSE,
ADD COLUMN conflict_type VARCHAR(100),
ADD COLUMN conflict_resolved BOOLEAN DEFAULT FALSE,
ADD COLUMN resolution_strategy VARCHAR(50),
ADD COLUMN resolution_data JSONB,
ADD COLUMN resolved_at TIMESTAMPTZ,

-- Advanced Messaging Fields (Subtask 39.2)
ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb,
ADD COLUMN priority INTEGER DEFAULT 0,
ADD COLUMN requires_response BOOLEAN DEFAULT FALSE,
ADD COLUMN response_deadline TIMESTAMPTZ,
ADD COLUMN is_broadcast BOOLEAN GENERATED ALWAYS AS (to_agent_id IS NULL) STORED,

-- Audit and tracking
ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_agent_interactions_event_type
    ON crewai_agent_interactions(event_type)
    WHERE event_type IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_interactions_state_key
    ON crewai_agent_interactions(state_key)
    WHERE state_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_interactions_conflict
    ON crewai_agent_interactions(conflict_detected, conflict_resolved)
    WHERE conflict_detected = TRUE;

CREATE INDEX IF NOT EXISTS idx_agent_interactions_broadcast
    ON crewai_agent_interactions(execution_id, is_broadcast)
    WHERE is_broadcast = TRUE;

CREATE INDEX IF NOT EXISTS idx_agent_interactions_priority
    ON crewai_agent_interactions(execution_id, priority DESC, created_at);

CREATE INDEX IF NOT EXISTS idx_agent_interactions_response_pending
    ON crewai_agent_interactions(to_agent_id, requires_response, response_deadline)
    WHERE requires_response = TRUE AND response IS NULL;

-- Add check constraints
ALTER TABLE crewai_agent_interactions
ADD CONSTRAINT check_interaction_type
    CHECK (interaction_type IN ('message', 'event', 'state_sync', 'delegation', 'conflict', 'response'));

ALTER TABLE crewai_agent_interactions
ADD CONSTRAINT check_event_fields
    CHECK (
        (interaction_type = 'event' AND event_type IS NOT NULL) OR
        (interaction_type != 'event')
    );

ALTER TABLE crewai_agent_interactions
ADD CONSTRAINT check_state_fields
    CHECK (
        (interaction_type = 'state_sync' AND state_key IS NOT NULL AND state_value IS NOT NULL) OR
        (interaction_type != 'state_sync')
    );

ALTER TABLE crewai_agent_interactions
ADD CONSTRAINT check_conflict_fields
    CHECK (
        (interaction_type = 'conflict' AND conflict_type IS NOT NULL) OR
        (interaction_type != 'conflict')
    );

ALTER TABLE crewai_agent_interactions
ADD CONSTRAINT check_priority_range
    CHECK (priority BETWEEN -10 AND 10);

-- Add update trigger for updated_at
CREATE OR REPLACE FUNCTION update_agent_interactions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_agent_interactions_timestamp
    BEFORE UPDATE ON crewai_agent_interactions
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_interactions_updated_at();

-- Add comments for documentation
COMMENT ON TABLE crewai_agent_interactions IS 'Stores all inter-agent interactions including messages, events, state sync, delegations, and conflicts';
COMMENT ON COLUMN crewai_agent_interactions.interaction_type IS 'Type of interaction: message, event, state_sync, delegation, conflict, response';
COMMENT ON COLUMN crewai_agent_interactions.event_type IS 'Event type for event interactions: task_completed, task_failed, delegation_accepted, etc.';
COMMENT ON COLUMN crewai_agent_interactions.state_key IS 'State key for state synchronization (e.g., task_1_progress, shared_context)';
COMMENT ON COLUMN crewai_agent_interactions.state_version IS 'Version number for optimistic locking and conflict detection';
COMMENT ON COLUMN crewai_agent_interactions.conflict_type IS 'Type of conflict: concurrent_update, duplicate_assignment, resource_contention, etc.';
COMMENT ON COLUMN crewai_agent_interactions.resolution_strategy IS 'Conflict resolution strategy: latest_wins, manual, merge, rollback';
COMMENT ON COLUMN crewai_agent_interactions.is_broadcast IS 'Computed column: true if to_agent_id is NULL (broadcast to all agents)';
COMMENT ON COLUMN crewai_agent_interactions.priority IS 'Message priority (-10 to 10, higher = more urgent)';

-- Create view for unresolved conflicts (useful for monitoring)
CREATE OR REPLACE VIEW crewai_unresolved_conflicts AS
SELECT
    i.id,
    i.execution_id,
    i.from_agent_id,
    i.to_agent_id,
    i.conflict_type,
    i.state_key,
    i.created_at,
    e.crew_id,
    e.status as execution_status,
    EXTRACT(EPOCH FROM (NOW() - i.created_at))/60 as age_minutes
FROM crewai_agent_interactions i
JOIN crewai_executions e ON i.execution_id = e.id
WHERE i.conflict_detected = TRUE
  AND i.conflict_resolved = FALSE
ORDER BY i.priority DESC, i.created_at;

COMMENT ON VIEW crewai_unresolved_conflicts IS 'Shows all unresolved conflicts across all executions for monitoring and alerting';

-- Create view for pending responses (useful for monitoring)
CREATE OR REPLACE VIEW crewai_pending_responses AS
SELECT
    i.id,
    i.execution_id,
    i.from_agent_id,
    i.to_agent_id,
    i.interaction_type,
    i.message,
    i.response_deadline,
    i.created_at,
    CASE
        WHEN i.response_deadline < NOW() THEN 'overdue'
        WHEN i.response_deadline < NOW() + INTERVAL '5 minutes' THEN 'urgent'
        ELSE 'pending'
    END as status,
    EXTRACT(EPOCH FROM (i.response_deadline - NOW()))/60 as minutes_until_deadline
FROM crewai_agent_interactions i
WHERE i.requires_response = TRUE
  AND i.response IS NULL
ORDER BY i.response_deadline NULLS LAST;

COMMENT ON VIEW crewai_pending_responses IS 'Shows all interactions awaiting responses with deadline tracking';
