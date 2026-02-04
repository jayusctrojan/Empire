-- Empire v7.3 - Add Version Columns for Optimistic Locking
-- Data Persistence P0 Fix - Prevent race conditions with version numbers
--
-- Usage:
--   Run this migration on Supabase PostgreSQL to enable optimistic locking
--   supabase db push or apply via Supabase dashboard

-- =============================================================================
-- ADD VERSION COLUMNS TO EXISTING TABLES
-- =============================================================================

-- Documents table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents_v2') THEN
        ALTER TABLE documents_v2
        ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
    END IF;
END $$;

-- Chat messages table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_messages') THEN
        ALTER TABLE chat_messages
        ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
    END IF;
END $$;

-- Chat sessions table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_sessions') THEN
        ALTER TABLE chat_sessions
        ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
    END IF;
END $$;

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
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents_v2') THEN
        CREATE INDEX IF NOT EXISTS idx_documents_v2_id_version
        ON documents_v2 (id, version);
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_messages') THEN
        CREATE INDEX IF NOT EXISTS idx_chat_messages_id_version
        ON chat_messages (id, version);
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_sessions') THEN
        CREATE INDEX IF NOT EXISTS idx_chat_sessions_id_version
        ON chat_sessions (id, version);
    END IF;
END $$;

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

-- Apply trigger to documents_v2 (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents_v2') THEN
        DROP TRIGGER IF EXISTS trigger_documents_v2_version ON documents_v2;
        CREATE TRIGGER trigger_documents_v2_version
        BEFORE UPDATE ON documents_v2
        FOR EACH ROW
        EXECUTE FUNCTION increment_version();
    END IF;
END $$;

-- Apply trigger to chat_messages (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_messages') THEN
        DROP TRIGGER IF EXISTS trigger_chat_messages_version ON chat_messages;
        CREATE TRIGGER trigger_chat_messages_version
        BEFORE UPDATE ON chat_messages
        FOR EACH ROW
        EXECUTE FUNCTION increment_version();
    END IF;
END $$;

-- Apply trigger to chat_sessions (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_sessions') THEN
        DROP TRIGGER IF EXISTS trigger_chat_sessions_version ON chat_sessions;
        CREATE TRIGGER trigger_chat_sessions_version
        BEFORE UPDATE ON chat_sessions
        FOR EACH ROW
        EXECUTE FUNCTION increment_version();
    END IF;
END $$;

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
    set_clause TEXT := '';
    key TEXT;
    value JSONB;
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

    -- Build SET clause from p_updates JSONB
    FOR key, value IN SELECT * FROM jsonb_each(p_updates)
    LOOP
        IF set_clause != '' THEN
            set_clause := set_clause || ', ';
        END IF;
        -- Format value based on type (text, number, boolean, null)
        IF jsonb_typeof(value) = 'string' THEN
            set_clause := set_clause || format('%I = %L', key, value #>> '{}');
        ELSIF jsonb_typeof(value) = 'null' THEN
            set_clause := set_clause || format('%I = NULL', key);
        ELSE
            set_clause := set_clause || format('%I = %s', key, value);
        END IF;
    END LOOP;

    -- Add updated_at to the SET clause
    IF set_clause != '' THEN
        set_clause := set_clause || ', ';
    END IF;
    set_clause := set_clause || 'updated_at = NOW()';

    -- Version matches, perform update with p_updates
    -- The trigger will auto-increment the version
    query := format(
        'UPDATE %I SET %s WHERE id = $1 AND version = $2 RETURNING version',
        p_table_name,
        set_clause
    );

    EXECUTE query INTO actual_version USING p_id, p_expected_version;

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

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents_v2') THEN
        COMMENT ON COLUMN documents_v2.version IS 'Optimistic locking version number (auto-incremented on update)';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_messages') THEN
        COMMENT ON COLUMN chat_messages.version IS 'Optimistic locking version number (auto-incremented on update)';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_sessions') THEN
        COMMENT ON COLUMN chat_sessions.version IS 'Optimistic locking version number (auto-incremented on update)';
    END IF;
END $$;
