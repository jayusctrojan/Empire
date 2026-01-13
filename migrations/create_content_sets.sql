-- Migration: Content Prep Agent Tables
-- Feature: 007-content-prep-agent (AGENT-016)
-- Created: 2026-01-13
-- Description: Creates tables for content set detection, file ordering, and processing manifests

-- ============================================================================
-- Table: content_sets
-- Purpose: Store detected content sets (groups of related files)
-- ============================================================================
CREATE TABLE IF NOT EXISTS content_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    detection_method VARCHAR(50) NOT NULL DEFAULT 'pattern',
    is_complete BOOLEAN DEFAULT FALSE,
    missing_files JSONB DEFAULT '[]'::jsonb,
    file_count INTEGER NOT NULL DEFAULT 0,
    processing_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,  -- For 90-day retention policy
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Constraints
    CONSTRAINT valid_detection_method CHECK (
        detection_method IN ('pattern', 'metadata', 'manual', 'llm')
    ),
    CONSTRAINT valid_processing_status CHECK (
        processing_status IN ('pending', 'processing', 'complete', 'failed', 'cancelled')
    )
);

COMMENT ON TABLE content_sets IS 'Groups of related files detected by Content Prep Agent (AGENT-016)';
COMMENT ON COLUMN content_sets.detection_method IS 'How the set was detected: pattern, metadata, manual, or llm';
COMMENT ON COLUMN content_sets.completed_at IS 'Timestamp for 90-day retention policy calculation';

-- ============================================================================
-- Table: content_set_files
-- Purpose: Store individual files within a content set with ordering info
-- ============================================================================
CREATE TABLE IF NOT EXISTS content_set_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_set_id UUID NOT NULL REFERENCES content_sets(id) ON DELETE CASCADE,
    b2_path VARCHAR(500) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    sequence_number INTEGER,
    detection_pattern VARCHAR(50),  -- Which pattern matched (numeric_prefix, module, chapter, etc.)
    dependencies JSONB DEFAULT '[]'::jsonb,
    estimated_complexity VARCHAR(20) DEFAULT 'medium',
    file_type VARCHAR(50),
    size_bytes BIGINT DEFAULT 0,
    processing_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Constraints
    CONSTRAINT valid_complexity CHECK (
        estimated_complexity IN ('low', 'medium', 'high')
    ),
    CONSTRAINT valid_file_status CHECK (
        processing_status IN ('pending', 'processing', 'complete', 'failed', 'skipped')
    )
);

COMMENT ON TABLE content_set_files IS 'Individual files within a content set, ordered by sequence_number';
COMMENT ON COLUMN content_set_files.sequence_number IS 'Detected ordering position (1, 2, 3, etc.)';
COMMENT ON COLUMN content_set_files.detection_pattern IS 'Regex pattern that matched: numeric_prefix, module, chapter, etc.';

-- ============================================================================
-- Table: processing_manifests
-- Purpose: Store generated processing orders with context for Celery tasks
-- ============================================================================
CREATE TABLE IF NOT EXISTS processing_manifests (
    manifest_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_set_id UUID REFERENCES content_sets(id) ON DELETE SET NULL,
    content_set_name VARCHAR(255),
    ordered_files JSONB NOT NULL,
    total_files INTEGER NOT NULL,
    warnings JSONB DEFAULT '[]'::jsonb,
    estimated_time_seconds INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    context JSONB DEFAULT '{}'::jsonb,
    processing_status VARCHAR(50) DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT valid_manifest_status CHECK (
        processing_status IN ('pending', 'processing', 'complete', 'failed', 'cancelled')
    )
);

COMMENT ON TABLE processing_manifests IS 'Generated processing orders for content sets';
COMMENT ON COLUMN processing_manifests.ordered_files IS 'JSON array of files in processing order with dependencies';
COMMENT ON COLUMN processing_manifests.context IS 'Shared context passed to downstream processing tasks';

-- ============================================================================
-- Indexes for efficient querying
-- ============================================================================

-- Content sets indexes
CREATE INDEX IF NOT EXISTS idx_content_sets_status ON content_sets(processing_status);
CREATE INDEX IF NOT EXISTS idx_content_sets_created ON content_sets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_sets_updated ON content_sets(updated_at);
CREATE INDEX IF NOT EXISTS idx_content_sets_completed ON content_sets(completed_at)
    WHERE completed_at IS NOT NULL;  -- For retention policy cleanup

-- Content set files indexes
CREATE INDEX IF NOT EXISTS idx_content_set_files_set_id ON content_set_files(content_set_id);
CREATE INDEX IF NOT EXISTS idx_content_set_files_sequence ON content_set_files(content_set_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_content_set_files_status ON content_set_files(processing_status);
CREATE INDEX IF NOT EXISTS idx_content_set_files_b2_path ON content_set_files(b2_path);

-- Processing manifests indexes
CREATE INDEX IF NOT EXISTS idx_manifests_set_id ON processing_manifests(content_set_id);
CREATE INDEX IF NOT EXISTS idx_manifests_status ON processing_manifests(processing_status);
CREATE INDEX IF NOT EXISTS idx_manifests_created ON processing_manifests(created_at DESC);

-- ============================================================================
-- Row Level Security (RLS)
-- ============================================================================

ALTER TABLE content_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_set_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_manifests ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to manage content sets
CREATE POLICY "Users can manage content sets"
ON content_sets FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

CREATE POLICY "Users can manage content set files"
ON content_set_files FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

CREATE POLICY "Users can manage manifests"
ON processing_manifests FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

-- Service role has full access
CREATE POLICY "Service role full access to content_sets"
ON content_sets FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Service role full access to content_set_files"
ON content_set_files FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Service role full access to processing_manifests"
ON processing_manifests FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ============================================================================
-- Trigger: Auto-update updated_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION update_content_sets_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_content_sets_updated_at
    BEFORE UPDATE ON content_sets
    FOR EACH ROW
    EXECUTE FUNCTION update_content_sets_updated_at();

-- ============================================================================
-- Function: Mark content set as complete and set completed_at
-- ============================================================================

CREATE OR REPLACE FUNCTION mark_content_set_complete(set_id UUID)
RETURNS void AS $$
BEGIN
    UPDATE content_sets
    SET processing_status = 'complete',
        completed_at = NOW(),
        updated_at = NOW()
    WHERE id = set_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION mark_content_set_complete IS 'Marks a content set as complete and sets completed_at for retention tracking';
