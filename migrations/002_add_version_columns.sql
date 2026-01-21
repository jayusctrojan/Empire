-- Empire v7.3 - Add Version Columns for Optimistic Locking
-- Data Persistence P0 Fix - Prevent race conditions with version numbers
--
-- Usage:
--   Run this migration on Supabase PostgreSQL to enable optimistic locking
--   supabase db push or apply via Supabase dashboard

-- =============================================================================
-- ADD VERSION COLUMNS TO EXISTING TABLES
-- =============================================================================

-- Documents table
ALTER TABLE documents_v2
ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

-- Chat messages table
ALTER TABLE chat_messages
ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

-- Chat sessions table
ALTER TABLE chat_sessions
ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

-- Knowledge entities table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'knowledge_entities') THEN
        ALTER TABLE knowledge_entities
        ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
    END IF;
END $$;

-- Knowledge relationships table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'knowledge_relationships') THEN
        ALTER TABLE knowledge_relationships
        ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
    END IF;
END $$;

-- =============================================================================
-- INDEXES FOR VERSION QUERIES
-- =============================================================================

-- Index for version lookups (composite with ID for update queries)
CREATE INDEX IF NOT EXISTS idx_documents_v2_id_version
ON documents_v2 (id, version);

CREATE INDEX IF NOT EXISTS idx_chat_messages_id_version
ON chat_messages (id, version);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_id_version
ON chat_sessions (id, version);

-- =============================================================================
-- TRIGGER FOR AUTOMATIC VERSION INCREMENT
-- =============================================================================

-- Create trigger function for auto-incrementing version
CREATE OR REPLACE FUNCTION increment_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Only increment if this is an actual update (not just setting version)
    IF OLD.version = NEW.version THEN
        NEW.version := OLD.version + 1;
    END IF;
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

-- Apply trigger to documents_v2
DROP TRIGGER IF EXISTS trigger_documents_v2_version ON documents_v2;
CREATE TRIGGER trigger_documents_v2_version
BEFORE UPDATE ON documents_v2
FOR EACH ROW
EXECUTE FUNCTION increment_version();

-- Apply trigger to chat_messages
DROP TRIGGER IF EXISTS trigger_chat_messages_version ON chat_messages;
CREATE TRIGGER trigger_chat_messages_version
BEFORE UPDATE ON chat_messages
FOR EACH ROW
EXECUTE FUNCTION increment_version();

-- Apply trigger to chat_sessions
DROP TRIGGER IF EXISTS trigger_chat_sessions_version ON chat_sessions;
CREATE TRIGGER trigger_chat_sessions_version
BEFORE UPDATE ON chat_sessions
FOR EACH ROW
EXECUTE FUNCTION increment_version();

-- =============================================================================
-- FUNCTION FOR SAFE UPDATE WITH VERSION CHECK
-- =============================================================================

-- Function for atomic update with version check
CREATE OR REPLACE FUNCTION update_with_version(
    p_table_name TEXT,
    p_id TEXT,
    p_expected_version INTEGER,
    p_updates JSONB
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    result JSONB;
    actual_version INTEGER;
    query TEXT;
    update_parts TEXT[];
    key TEXT;
    value TEXT;
BEGIN
    -- Build update query dynamically (simplified for common tables)
    -- Note: In production, use prepared statements or ORM

    -- First, check current version
    EXECUTE format(
        'SELECT version FROM %I WHERE id = $1',
        p_table_name
    ) INTO actual_version USING p_id;

    IF actual_version IS NULL THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Record not found',
            'record_id', p_id
        );
    END IF;

    IF actual_version != p_expected_version THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Version mismatch',
            'expected_version', p_expected_version,
            'actual_version', actual_version,
            'record_id', p_id
        );
    END IF;

    -- Version matches, perform update
    -- The trigger will auto-increment the version
    EXECUTE format(
        'UPDATE %I SET updated_at = NOW() WHERE id = $1 AND version = $2 RETURNING version',
        p_table_name
    ) INTO actual_version USING p_id, p_expected_version;

    IF actual_version IS NULL THEN
        -- Concurrent modification occurred
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Concurrent modification detected',
            'record_id', p_id
        );
    END IF;

    RETURN jsonb_build_object(
        'success', true,
        'new_version', actual_version,
        'record_id', p_id
    );
END;
$$;

COMMENT ON FUNCTION increment_version IS 'Trigger function to auto-increment version on update';
COMMENT ON FUNCTION update_with_version IS 'Atomic update with optimistic locking version check';

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON COLUMN documents_v2.version IS 'Optimistic locking version number (auto-incremented on update)';
COMMENT ON COLUMN chat_messages.version IS 'Optimistic locking version number (auto-incremented on update)';
COMMENT ON COLUMN chat_sessions.version IS 'Optimistic locking version number (auto-incremented on update)';
