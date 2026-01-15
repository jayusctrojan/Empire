-- Migration: Create RLS Context Functions
-- Task 151: Implement RLS Database Context
-- Applied: 2025-01-14
--
-- Creates PostgreSQL functions for setting session variables for RLS enforcement.
-- NOTE: This migration has been applied via Supabase MCP.

-- set_rls_context: Sets session variables for RLS
CREATE OR REPLACE FUNCTION set_rls_context(
    p_user_id TEXT,
    p_role TEXT,
    p_request_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSONB;
BEGIN
    IF p_user_id IS NULL OR p_user_id = '' THEN
        RAISE EXCEPTION 'user_id cannot be null or empty';
    END IF;

    IF p_role IS NULL OR p_role = '' THEN
        p_role := 'guest';
    END IF;

    IF p_request_id IS NULL OR p_request_id = '' THEN
        p_request_id := gen_random_uuid()::TEXT;
    END IF;

    PERFORM set_config('app.current_user_id', p_user_id, true);
    PERFORM set_config('app.user_role', p_role, true);
    PERFORM set_config('app.request_id', p_request_id, true);
    PERFORM set_config('app.rls_context_set', 'true', true);

    result := jsonb_build_object(
        'success', true,
        'user_id', p_user_id,
        'role', p_role,
        'request_id', p_request_id,
        'set_at', NOW()
    );

    RETURN result;
END;
$$;

-- get_rls_context: Returns current RLS context for debugging
CREATE OR REPLACE FUNCTION get_rls_context()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN jsonb_build_object(
        'user_id', current_setting('app.current_user_id', true),
        'role', current_setting('app.user_role', true),
        'request_id', current_setting('app.request_id', true),
        'context_set', current_setting('app.rls_context_set', true) = 'true'
    );
END;
$$;

-- clear_rls_context: Clears RLS context (for testing)
CREATE OR REPLACE FUNCTION clear_rls_context()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    PERFORM set_config('app.current_user_id', '', true);
    PERFORM set_config('app.user_role', 'guest', true);
    PERFORM set_config('app.request_id', '', true);
    PERFORM set_config('app.rls_context_set', 'false', true);

    RETURN jsonb_build_object('success', true, 'cleared_at', NOW());
END;
$$;

-- current_user_id: Helper for RLS policies
CREATE OR REPLACE FUNCTION current_user_id()
RETURNS TEXT
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN NULLIF(current_setting('app.current_user_id', true), '');
END;
$$;

-- session_has_role: Check session role level (renamed to avoid conflict with existing has_role)
CREATE OR REPLACE FUNCTION session_has_role(required_role TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    user_role TEXT;
    role_hierarchy JSONB := '{"admin": 4, "editor": 3, "viewer": 2, "guest": 1}'::JSONB;
BEGIN
    user_role := COALESCE(current_setting('app.user_role', true), 'guest');
    RETURN (role_hierarchy->>user_role)::INT >= (role_hierarchy->>required_role)::INT;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION set_rls_context(TEXT, TEXT, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION get_rls_context() TO authenticated;
GRANT EXECUTE ON FUNCTION clear_rls_context() TO authenticated;
GRANT EXECUTE ON FUNCTION current_user_id() TO authenticated;
GRANT EXECUTE ON FUNCTION session_has_role(TEXT) TO authenticated;

GRANT EXECUTE ON FUNCTION set_rls_context(TEXT, TEXT, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION get_rls_context() TO service_role;
GRANT EXECUTE ON FUNCTION clear_rls_context() TO service_role;
GRANT EXECUTE ON FUNCTION current_user_id() TO service_role;
GRANT EXECUTE ON FUNCTION session_has_role(TEXT) TO service_role;

-- Comments
COMMENT ON FUNCTION set_rls_context IS 'Sets PostgreSQL session variables for RLS enforcement. Task 151.';
COMMENT ON FUNCTION get_rls_context IS 'Returns current RLS context as JSON for debugging.';
COMMENT ON FUNCTION clear_rls_context IS 'Clears RLS context. Used for testing.';
COMMENT ON FUNCTION current_user_id IS 'Gets current user ID from session context for RLS policies.';
COMMENT ON FUNCTION session_has_role IS 'Checks if session role meets required role level for RLS policies.';
