-- =============================================================================
-- AI STUDIO DATABASE MIGRATION
-- Task 70: Create Database Migrations for AI Studio
-- Feature Branch: 001-studio
-- Created: 2026-01-06
--
-- Tables:
--   1. studio_cko_sessions - CKO conversation sessions
--   2. studio_cko_messages - CKO conversation messages
--   3. studio_user_weights - User data weight configurations
--   4. studio_assets - Generated AI assets (5 types)
--   5. studio_classifications - Content department classifications
--
-- Includes:
--   - Indexes for all query patterns
--   - RLS policies for user data isolation
--   - Trigger for updated_at timestamps
-- =============================================================================

-- =============================================================================
-- HELPER: Updated timestamp trigger function
-- =============================================================================
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- TABLE 1: CKO SESSIONS (Conversations with Chief Knowledge Officer)
-- =============================================================================
CREATE TABLE IF NOT EXISTS studio_cko_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,

    -- Session metadata
    title TEXT,  -- Auto-generated from first message or user-defined

    -- Counters
    message_count INTEGER DEFAULT 0,
    pending_clarifications INTEGER DEFAULT 0,  -- For badge count

    -- Memory (NFR-011: Last 50 conversations with summarized context)
    context_summary TEXT,  -- CKO's memory of this conversation

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    last_message_at TIMESTAMPTZ
);

-- Indexes for studio_cko_sessions
CREATE INDEX IF NOT EXISTS idx_cko_sessions_user ON studio_cko_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_cko_sessions_updated ON studio_cko_sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cko_sessions_pending ON studio_cko_sessions(pending_clarifications)
    WHERE pending_clarifications > 0;
CREATE INDEX IF NOT EXISTS idx_cko_sessions_last_message ON studio_cko_sessions(last_message_at DESC);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS set_updated_at_cko_sessions ON studio_cko_sessions;
CREATE TRIGGER set_updated_at_cko_sessions
    BEFORE UPDATE ON studio_cko_sessions
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE studio_cko_sessions IS 'CKO (Chief Knowledge Officer) conversation sessions for AI Studio';
COMMENT ON COLUMN studio_cko_sessions.context_summary IS 'Summarized context for CKO memory continuity (NFR-011)';
COMMENT ON COLUMN studio_cko_sessions.pending_clarifications IS 'Count for notification badge (FR-009, FR-010)';

-- =============================================================================
-- TABLE 2: CKO MESSAGES
-- =============================================================================
CREATE TABLE IF NOT EXISTS studio_cko_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES studio_cko_sessions(id) ON DELETE CASCADE NOT NULL,

    -- Message content
    role TEXT NOT NULL CHECK (role IN ('user', 'cko')),
    content TEXT NOT NULL,

    -- Clarification tracking (FR-007 to FR-012)
    is_clarification BOOLEAN DEFAULT false,  -- Yellow highlight (#FEF3C7)
    clarification_type TEXT,  -- classification, asset_type, conflict, sensitive, department
    clarification_status TEXT DEFAULT 'pending' CHECK (clarification_status IN ('pending', 'answered', 'skipped', 'auto_skipped')),
    clarification_answer TEXT,  -- User's response
    clarification_created_at TIMESTAMPTZ,  -- For 7-day auto-skip (FR-012a)

    -- Sources and citations (FR-003)
    sources JSONB DEFAULT '[]'::jsonb,  -- [{doc_id, title, snippet, relevance_score, page_number}]

    -- Actions taken (FR-018)
    actions_performed JSONB DEFAULT '[]'::jsonb,  -- [{action: "reclassify", params: {...}, result: {...}}]

    -- Feedback (FR-038, FR-039)
    rating INTEGER CHECK (rating IS NULL OR rating BETWEEN -1 AND 1),  -- -1 = down, 0 = none, 1 = up
    rating_feedback TEXT,  -- Optional text feedback with thumbs down

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for studio_cko_messages
CREATE INDEX IF NOT EXISTS idx_cko_messages_session ON studio_cko_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_cko_messages_session_created ON studio_cko_messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_cko_messages_clarification ON studio_cko_messages(clarification_status)
    WHERE is_clarification = true;
CREATE INDEX IF NOT EXISTS idx_cko_messages_clarification_overdue ON studio_cko_messages(clarification_created_at)
    WHERE is_clarification = true AND clarification_status = 'pending';
CREATE INDEX IF NOT EXISTS idx_cko_messages_rating ON studio_cko_messages(rating)
    WHERE rating IS NOT NULL;

COMMENT ON TABLE studio_cko_messages IS 'Individual messages in CKO conversations';
COMMENT ON COLUMN studio_cko_messages.is_clarification IS 'Yellow highlighted clarification requests (FR-008)';
COMMENT ON COLUMN studio_cko_messages.clarification_status IS 'Status: pending, answered, skipped, auto_skipped (FR-012a after 7 days)';
COMMENT ON COLUMN studio_cko_messages.sources IS 'Citation sources for expandable citations (FR-003)';

-- =============================================================================
-- TABLE 3: USER DATA WEIGHTS
-- =============================================================================
CREATE TABLE IF NOT EXISTS studio_user_weights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE NOT NULL,

    -- Weight configuration (JSON for flexibility) (FR-013 to FR-019)
    weights JSONB DEFAULT '{
        "preset": "balanced",
        "departments": {},
        "recency": {
            "enabled": true,
            "last_30_days": 1.5,
            "last_year": 1.0,
            "older": 0.7
        },
        "source_types": {
            "enabled": true,
            "pdf": 1.0,
            "video": 0.9,
            "audio": 0.85,
            "web": 0.8,
            "notes": 0.7
        },
        "confidence": {
            "enabled": true,
            "high": 1.2,
            "medium": 1.0,
            "low": 0.8
        },
        "verified": {
            "enabled": true,
            "weight": 1.5
        }
    }'::jsonb,

    -- Pinned and muted documents (FR-016, FR-017)
    pinned_document_ids UUID[] DEFAULT '{}',
    muted_document_ids UUID[] DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for studio_user_weights
CREATE INDEX IF NOT EXISTS idx_user_weights_user ON studio_user_weights(user_id);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS set_updated_at_user_weights ON studio_user_weights;
CREATE TRIGGER set_updated_at_user_weights
    BEFORE UPDATE ON studio_user_weights
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE studio_user_weights IS 'Per-user weight configuration for CKO retrieval (FR-013 to FR-019)';
COMMENT ON COLUMN studio_user_weights.weights IS 'JSON weight config: preset, departments, recency, source_types, confidence, verified';
COMMENT ON COLUMN studio_user_weights.pinned_document_ids IS 'Documents always included with 2.0x weight (FR-016)';
COMMENT ON COLUMN studio_user_weights.muted_document_ids IS 'Documents excluded from retrieval (FR-017)';

-- =============================================================================
-- TABLE 4: GENERATED ASSETS (5 Types: SKILL, COMMAND, AGENT, PROMPT, WORKFLOW)
-- =============================================================================
CREATE TABLE IF NOT EXISTS studio_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,

    -- Asset identification (FR-024)
    asset_type TEXT NOT NULL CHECK (asset_type IN ('skill', 'command', 'agent', 'prompt', 'workflow')),
    department TEXT NOT NULL,  -- One of 12 departments
    name TEXT NOT NULL,
    title TEXT NOT NULL,  -- Human-readable title

    -- Content
    content TEXT NOT NULL,  -- YAML, MD, or JSON depending on type
    format TEXT NOT NULL CHECK (format IN ('yaml', 'md', 'json')),

    -- Status (FR-028, FR-029)
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),

    -- Source tracking
    source_document_id UUID,
    source_document_title TEXT,

    -- Classification metadata (from AGENT-001)
    classification_confidence NUMERIC(3,2) CHECK (classification_confidence >= 0 AND classification_confidence <= 1),
    classification_reasoning TEXT,
    keywords_matched JSONB DEFAULT '[]'::jsonb,
    secondary_department TEXT,
    secondary_confidence NUMERIC(3,2) CHECK (secondary_confidence IS NULL OR (secondary_confidence >= 0 AND secondary_confidence <= 1)),

    -- Asset decision metadata
    asset_decision_reasoning TEXT,

    -- Storage path (B2) (FR-028)
    storage_path TEXT,  -- crewai-suggestions/{type}/drafts/{name}.{format}

    -- Versioning (FR-027)
    version INTEGER DEFAULT 1,
    parent_version_id UUID REFERENCES studio_assets(id),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    published_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ
);

-- Indexes for studio_assets
CREATE INDEX IF NOT EXISTS idx_assets_user ON studio_assets(user_id);
CREATE INDEX IF NOT EXISTS idx_assets_type ON studio_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_assets_department ON studio_assets(department);
CREATE INDEX IF NOT EXISTS idx_assets_status ON studio_assets(status);
CREATE INDEX IF NOT EXISTS idx_assets_created ON studio_assets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_assets_user_type_status ON studio_assets(user_id, asset_type, status);
CREATE INDEX IF NOT EXISTS idx_assets_source_doc ON studio_assets(source_document_id) WHERE source_document_id IS NOT NULL;

-- Full-text search index for assets (FR-034)
CREATE INDEX IF NOT EXISTS idx_assets_search ON studio_assets USING gin(
    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, ''))
);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS set_updated_at_assets ON studio_assets;
CREATE TRIGGER set_updated_at_assets
    BEFORE UPDATE ON studio_assets
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE studio_assets IS 'Generated AI assets: SKILL (YAML), COMMAND (MD), AGENT (YAML), PROMPT (MD), WORKFLOW (JSON)';
COMMENT ON COLUMN studio_assets.asset_type IS 'One of: skill, command, agent, prompt, workflow (FR-024)';
COMMENT ON COLUMN studio_assets.department IS 'One of 12 departments from classification taxonomy';
COMMENT ON COLUMN studio_assets.version IS 'Version number, increments on edit (FR-027)';

-- =============================================================================
-- TABLE 5: CONTENT CLASSIFICATIONS (12 Departments)
-- =============================================================================
CREATE TABLE IF NOT EXISTS studio_classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,

    -- Source content
    document_id UUID,  -- Reference to documents_v2
    content_hash TEXT,  -- For deduplication
    filename TEXT,
    content_preview TEXT,  -- First 500 chars

    -- Primary classification (FR-030)
    department TEXT NOT NULL,
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    reasoning TEXT,
    keywords_matched JSONB DEFAULT '[]'::jsonb,

    -- Secondary classification
    secondary_department TEXT,
    secondary_confidence NUMERIC(3,2) CHECK (secondary_confidence IS NULL OR (secondary_confidence >= 0 AND secondary_confidence <= 1)),

    -- User corrections (FR-031, FR-032, FR-033)
    user_corrected_department TEXT,
    correction_reason TEXT,
    corrected_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for studio_classifications
CREATE INDEX IF NOT EXISTS idx_classifications_user ON studio_classifications(user_id);
CREATE INDEX IF NOT EXISTS idx_classifications_department ON studio_classifications(department);
CREATE INDEX IF NOT EXISTS idx_classifications_confidence ON studio_classifications(confidence);
CREATE INDEX IF NOT EXISTS idx_classifications_corrected ON studio_classifications(user_corrected_department)
    WHERE user_corrected_department IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_classifications_document ON studio_classifications(document_id)
    WHERE document_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_classifications_content_hash ON studio_classifications(content_hash)
    WHERE content_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_classifications_low_confidence ON studio_classifications(confidence)
    WHERE confidence < 0.70;  -- For FR-007: clarification threshold

COMMENT ON TABLE studio_classifications IS 'Content classifications into 12 departments (FR-030 to FR-033)';
COMMENT ON COLUMN studio_classifications.confidence IS 'Classification confidence 0.0-1.0 (< 0.70 triggers clarification)';
COMMENT ON COLUMN studio_classifications.user_corrected_department IS 'User correction for misclassified content (FR-031)';

-- =============================================================================
-- RLS POLICIES
-- =============================================================================

-- Enable RLS on all tables
ALTER TABLE studio_cko_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE studio_cko_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE studio_user_weights ENABLE ROW LEVEL SECURITY;
ALTER TABLE studio_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE studio_classifications ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Users can access own CKO sessions" ON studio_cko_sessions;
DROP POLICY IF EXISTS "Users can access own CKO messages" ON studio_cko_messages;
DROP POLICY IF EXISTS "Users can access own weights" ON studio_user_weights;
DROP POLICY IF EXISTS "Users can access own assets" ON studio_assets;
DROP POLICY IF EXISTS "Users can access own classifications" ON studio_classifications;

-- Create RLS policies (NFR-001, NFR-002, NFR-009)

-- CKO Sessions: Users can only see their own sessions
CREATE POLICY "Users can access own CKO sessions" ON studio_cko_sessions
    FOR ALL USING (auth.uid() = user_id);

-- CKO Messages: Users can only see messages from their own sessions
CREATE POLICY "Users can access own CKO messages" ON studio_cko_messages
    FOR ALL USING (session_id IN (
        SELECT id FROM studio_cko_sessions WHERE user_id = auth.uid()
    ));

-- User Weights: Users can only access their own weight configuration
CREATE POLICY "Users can access own weights" ON studio_user_weights
    FOR ALL USING (auth.uid() = user_id);

-- Assets: Users can only access their own generated assets
CREATE POLICY "Users can access own assets" ON studio_assets
    FOR ALL USING (auth.uid() = user_id);

-- Classifications: Users can only access their own classifications
CREATE POLICY "Users can access own classifications" ON studio_classifications
    FOR ALL USING (auth.uid() = user_id);

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to get pending clarifications count for a user
CREATE OR REPLACE FUNCTION get_pending_clarifications_count(p_user_id UUID)
RETURNS INTEGER AS $$
DECLARE
    count_result INTEGER;
BEGIN
    SELECT COALESCE(SUM(s.pending_clarifications), 0)
    INTO count_result
    FROM studio_cko_sessions s
    WHERE s.user_id = p_user_id;

    RETURN count_result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check for overdue clarifications (>24 hours for red dot)
CREATE OR REPLACE FUNCTION has_overdue_clarifications(p_user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM studio_cko_messages m
        JOIN studio_cko_sessions s ON m.session_id = s.id
        WHERE s.user_id = p_user_id
          AND m.is_clarification = true
          AND m.clarification_status = 'pending'
          AND m.clarification_created_at < NOW() - INTERVAL '24 hours'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to auto-skip clarifications older than 7 days (FR-012a)
CREATE OR REPLACE FUNCTION auto_skip_old_clarifications()
RETURNS INTEGER AS $$
DECLARE
    skipped_count INTEGER;
BEGIN
    WITH updated AS (
        UPDATE studio_cko_messages
        SET clarification_status = 'auto_skipped',
            clarification_answer = 'Auto-skipped after 7 days - CKO proceeded with best guess'
        WHERE is_clarification = true
          AND clarification_status = 'pending'
          AND clarification_created_at < NOW() - INTERVAL '7 days'
        RETURNING 1
    )
    SELECT COUNT(*) INTO skipped_count FROM updated;

    RETURN skipped_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =============================================================================
-- VERIFICATION
-- =============================================================================
DO $$
BEGIN
    -- Verify tables exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'studio_cko_sessions') THEN
        RAISE EXCEPTION 'studio_cko_sessions table was not created';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'studio_cko_messages') THEN
        RAISE EXCEPTION 'studio_cko_messages table was not created';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'studio_user_weights') THEN
        RAISE EXCEPTION 'studio_user_weights table was not created';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'studio_assets') THEN
        RAISE EXCEPTION 'studio_assets table was not created';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'studio_classifications') THEN
        RAISE EXCEPTION 'studio_classifications table was not created';
    END IF;

    RAISE NOTICE 'AI Studio migration completed successfully - 5 tables created with RLS policies';
END;
$$;
