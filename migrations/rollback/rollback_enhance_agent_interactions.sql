-- ============================================================================
-- ROLLBACK: Enhanced Inter-Agent Interaction Schema
-- Original Migration: 20251112_enhance_agent_interactions.sql (Task 39.1)
-- Date: 2025-11-25
-- ============================================================================
--
-- PURPOSE: Revert the enhanced agent interaction schema additions
--
-- WHEN TO USE:
-- - New columns causing application compatibility issues
-- - Need to revert to simpler interaction model
-- - Performance issues from new indexes or constraints
-- - Rolling back Task 39 feature set
--
-- NOTE: This removes columns and may cause data loss for data stored in them.
-- Export interaction data before running if needed.
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: DROP MONITORING VIEWS
-- ============================================================================

DROP VIEW IF EXISTS crewai_pending_responses;
DROP VIEW IF EXISTS crewai_unresolved_conflicts;

RAISE NOTICE 'Dropped monitoring views';

-- ============================================================================
-- PHASE 2: DROP TRIGGER AND FUNCTION
-- ============================================================================

DROP TRIGGER IF EXISTS trigger_update_agent_interactions_timestamp ON crewai_agent_interactions;
DROP FUNCTION IF EXISTS update_agent_interactions_updated_at();

RAISE NOTICE 'Dropped update trigger';

-- ============================================================================
-- PHASE 3: DROP INDEXES
-- ============================================================================

DROP INDEX IF EXISTS idx_agent_interactions_event_type;
DROP INDEX IF EXISTS idx_agent_interactions_state_key;
DROP INDEX IF EXISTS idx_agent_interactions_conflict;
DROP INDEX IF EXISTS idx_agent_interactions_broadcast;
DROP INDEX IF EXISTS idx_agent_interactions_priority;
DROP INDEX IF EXISTS idx_agent_interactions_response_pending;

RAISE NOTICE 'Dropped agent interaction indexes';

-- ============================================================================
-- PHASE 4: DROP CHECK CONSTRAINTS
-- ============================================================================

ALTER TABLE crewai_agent_interactions
DROP CONSTRAINT IF EXISTS check_interaction_type;

ALTER TABLE crewai_agent_interactions
DROP CONSTRAINT IF EXISTS check_event_fields;

ALTER TABLE crewai_agent_interactions
DROP CONSTRAINT IF EXISTS check_state_fields;

ALTER TABLE crewai_agent_interactions
DROP CONSTRAINT IF EXISTS check_conflict_fields;

ALTER TABLE crewai_agent_interactions
DROP CONSTRAINT IF EXISTS check_priority_range;

RAISE NOTICE 'Dropped check constraints';

-- ============================================================================
-- PHASE 5: DROP ADDED COLUMNS
-- ============================================================================

ALTER TABLE crewai_agent_interactions
DROP COLUMN IF EXISTS event_type,
DROP COLUMN IF EXISTS event_data,
DROP COLUMN IF EXISTS state_key,
DROP COLUMN IF EXISTS state_value,
DROP COLUMN IF EXISTS state_version,
DROP COLUMN IF EXISTS previous_state,
DROP COLUMN IF EXISTS conflict_detected,
DROP COLUMN IF EXISTS conflict_type,
DROP COLUMN IF EXISTS conflict_resolved,
DROP COLUMN IF EXISTS resolution_strategy,
DROP COLUMN IF EXISTS resolution_data,
DROP COLUMN IF EXISTS resolved_at,
DROP COLUMN IF EXISTS metadata,
DROP COLUMN IF EXISTS priority,
DROP COLUMN IF EXISTS requires_response,
DROP COLUMN IF EXISTS response_deadline,
DROP COLUMN IF EXISTS is_broadcast,
DROP COLUMN IF EXISTS updated_at;

RAISE NOTICE 'Dropped enhanced interaction columns';

-- ============================================================================
-- PHASE 6: REMOVE COLUMN COMMENTS
-- ============================================================================

-- Comments are automatically removed with columns
-- Just reset the table comment if needed
COMMENT ON TABLE crewai_agent_interactions IS 'Stores basic inter-agent interactions';

-- ============================================================================
-- PHASE 7: VERIFICATION
-- ============================================================================

DO $$
DECLARE
    col_count INTEGER;
BEGIN
    -- Check that new columns are removed
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns
    WHERE table_name = 'crewai_agent_interactions'
      AND column_name IN (
        'event_type', 'event_data', 'state_key', 'state_value', 'state_version',
        'previous_state', 'conflict_detected', 'conflict_type', 'conflict_resolved',
        'resolution_strategy', 'resolution_data', 'resolved_at', 'metadata',
        'priority', 'requires_response', 'response_deadline', 'is_broadcast', 'updated_at'
      );

    IF col_count = 0 THEN
        RAISE NOTICE '✅ All enhanced columns successfully removed';
    ELSE
        RAISE WARNING '⚠️  % enhanced columns still exist', col_count;
    END IF;
END $$;

-- List remaining columns
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'crewai_agent_interactions'
ORDER BY ordinal_position;

COMMIT;

-- ============================================================================
-- POST-ROLLBACK CHECKLIST
-- ============================================================================
--
-- After running this rollback:
--
-- 1. [ ] Update CrewAI service to not use enhanced interaction features
-- 2. [ ] Disable event publication, state sync, and conflict resolution
-- 3. [ ] Revert to basic message-based interactions
-- 4. [ ] Remove monitoring dashboards for conflicts/pending responses
-- 5. [ ] Update tests to not expect enhanced columns
--
-- FEATURE IMPACT:
-- - Event publication (Task 39.3) disabled
-- - State synchronization (Task 39.4) disabled
-- - Conflict resolution (Task 39.5) disabled
-- - Advanced messaging (Task 39.2) limited
-- - Broadcast messaging unavailable
-- - Priority-based message ordering unavailable
--
-- ============================================================================
