-- Empire v7.3 - RBAC Tables Migration (Task 36)
-- Creates tables for Role-Based Access Control:
-- - roles: User role definitions (admin, editor, viewer, guest)
-- - user_roles: User-to-role assignments
-- - api_keys: API key management with bcrypt hashing
-- - rbac_audit_logs: Immutable audit log for RBAC operations

-- =============================================================================
-- ROLES TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    permissions JSONB DEFAULT '{}',

    -- Permission flags for quick access
    can_read_documents BOOLEAN DEFAULT true,
    can_write_documents BOOLEAN DEFAULT false,
    can_delete_documents BOOLEAN DEFAULT false,
    can_manage_users BOOLEAN DEFAULT false,
    can_manage_api_keys BOOLEAN DEFAULT false,
    can_view_audit_logs BOOLEAN DEFAULT false,

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for role lookup
CREATE INDEX IF NOT EXISTS idx_roles_role_name ON public.roles(role_name);
CREATE INDEX IF NOT EXISTS idx_roles_is_active ON public.roles(is_active);

-- Insert default roles
INSERT INTO public.roles (role_name, description, permissions, can_read_documents, can_write_documents, can_delete_documents, can_manage_users, can_manage_api_keys, can_view_audit_logs)
VALUES
    ('admin', 'Full administrative access', '{"documents": ["create", "read", "update", "delete"], "users": ["manage"], "api_keys": ["manage"], "audit_logs": ["view"]}', true, true, true, true, true, true),
    ('editor', 'Can read and write documents', '{"documents": ["create", "read", "update"]}', true, true, false, false, false, false),
    ('viewer', 'Read-only access to documents', '{"documents": ["read"]}', true, false, false, false, false, false),
    ('guest', 'Limited read-only access', '{"documents": ["read"]}', true, false, false, false, false, false)
ON CONFLICT (role_name) DO NOTHING;


-- =============================================================================
-- USER_ROLES TABLE (Many-to-Many relationship)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,  -- User ID from auth system (Clerk)
    role_id UUID NOT NULL REFERENCES public.roles(id) ON DELETE CASCADE,

    granted_by VARCHAR(255),  -- User ID who granted this role
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,  -- Optional expiration

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate active role assignments
    UNIQUE(user_id, role_id)
);

-- Create indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON public.user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON public.user_roles(role_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_is_active ON public.user_roles(is_active);
CREATE INDEX IF NOT EXISTS idx_user_roles_expires_at ON public.user_roles(expires_at) WHERE expires_at IS NOT NULL;


-- =============================================================================
-- API_KEYS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(255) NOT NULL,  -- Bcrypt hash (never store plaintext)
    key_prefix VARCHAR(12) NOT NULL,  -- First 12 chars for identification (emp_xxxxxxxx)

    user_id VARCHAR(255) NOT NULL,  -- Owner user ID
    role_id UUID REFERENCES public.roles(id) ON DELETE SET NULL,

    scopes TEXT[] DEFAULT '{}',  -- Permission scopes
    rate_limit_per_hour INTEGER DEFAULT 1000,

    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMPTZ,
    usage_count INTEGER DEFAULT 0,

    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoked_by VARCHAR(255),
    revoke_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_api_keys_key_prefix ON public.api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON public.api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_role_id ON public.api_keys(role_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON public.api_keys(is_active);
CREATE INDEX IF NOT EXISTS idx_api_keys_expires_at ON public.api_keys(expires_at) WHERE expires_at IS NOT NULL;

-- Partial index for active keys (most common query)
CREATE INDEX IF NOT EXISTS idx_api_keys_active_lookup
    ON public.api_keys(key_prefix, is_active)
    WHERE is_active = true;


-- =============================================================================
-- RBAC_AUDIT_LOGS TABLE (Immutable)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.rbac_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    event_type VARCHAR(100) NOT NULL,  -- api_key_created, role_assigned, etc.
    actor_user_id VARCHAR(255),  -- Who performed the action
    target_user_id VARCHAR(255),  -- Who was affected (optional)

    target_resource_type VARCHAR(50),  -- api_key, user_role, etc.
    target_resource_id UUID,

    action VARCHAR(50) NOT NULL,  -- create, revoke, assign, etc.
    result VARCHAR(20) NOT NULL,  -- success, failure, denied

    ip_address INET,
    user_agent TEXT,

    metadata JSONB DEFAULT '{}',
    error_message TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
    -- Note: No updated_at - audit logs are immutable
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_rbac_audit_logs_event_type ON public.rbac_audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_rbac_audit_logs_actor_user_id ON public.rbac_audit_logs(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_rbac_audit_logs_target_user_id ON public.rbac_audit_logs(target_user_id);
CREATE INDEX IF NOT EXISTS idx_rbac_audit_logs_created_at ON public.rbac_audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rbac_audit_logs_action ON public.rbac_audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_rbac_audit_logs_result ON public.rbac_audit_logs(result);

-- Combined index for common query patterns
CREATE INDEX IF NOT EXISTS idx_rbac_audit_logs_user_lookup
    ON public.rbac_audit_logs(actor_user_id, target_user_id, created_at DESC);


-- =============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =============================================================================

-- Enable RLS on all RBAC tables
ALTER TABLE public.roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rbac_audit_logs ENABLE ROW LEVEL SECURITY;

-- Roles table: Everyone can read active roles
CREATE POLICY roles_select_policy ON public.roles
    FOR SELECT
    USING (is_active = true);

-- Roles table: Only admins can modify (handled at application level)
-- No insert/update/delete policies - managed by service role only

-- User roles table: Users can see their own roles
CREATE POLICY user_roles_select_own_policy ON public.user_roles
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true));

-- API keys table: Users can see their own keys
CREATE POLICY api_keys_select_own_policy ON public.api_keys
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true));

-- API keys table: Users can insert their own keys
CREATE POLICY api_keys_insert_own_policy ON public.api_keys
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- API keys table: Users can update their own keys
CREATE POLICY api_keys_update_own_policy ON public.api_keys
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id', true));

-- Audit logs: Only admins can view (handled at application level with require_admin)
-- Service role has full access for writing


-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to check if a user has a specific role
CREATE OR REPLACE FUNCTION public.user_has_role(p_user_id VARCHAR, p_role_name VARCHAR)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM public.user_roles ur
        JOIN public.roles r ON ur.role_id = r.id
        WHERE ur.user_id = p_user_id
          AND r.role_name = p_role_name
          AND ur.is_active = true
          AND r.is_active = true
          AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
    );
END;
$$;

-- Function to get all active roles for a user
CREATE OR REPLACE FUNCTION public.get_user_roles(p_user_id VARCHAR)
RETURNS TABLE (
    role_id UUID,
    role_name VARCHAR,
    permissions JSONB,
    granted_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT r.id, r.role_name, r.permissions, ur.granted_at, ur.expires_at
    FROM public.user_roles ur
    JOIN public.roles r ON ur.role_id = r.id
    WHERE ur.user_id = p_user_id
      AND ur.is_active = true
      AND r.is_active = true
      AND (ur.expires_at IS NULL OR ur.expires_at > NOW());
END;
$$;

-- Function to check if user is admin
CREATE OR REPLACE FUNCTION public.is_admin(p_user_id VARCHAR)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN public.user_has_role(p_user_id, 'admin');
END;
$$;


-- =============================================================================
-- TRIGGERS FOR UPDATED_AT
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to roles table
DROP TRIGGER IF EXISTS update_roles_updated_at ON public.roles;
CREATE TRIGGER update_roles_updated_at
    BEFORE UPDATE ON public.roles
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Apply trigger to user_roles table
DROP TRIGGER IF EXISTS update_user_roles_updated_at ON public.user_roles;
CREATE TRIGGER update_user_roles_updated_at
    BEFORE UPDATE ON public.user_roles
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Apply trigger to api_keys table
DROP TRIGGER IF EXISTS update_api_keys_updated_at ON public.api_keys;
CREATE TRIGGER update_api_keys_updated_at
    BEFORE UPDATE ON public.api_keys
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();


-- =============================================================================
-- GRANTS (for service role access)
-- =============================================================================
-- These allow the application service role to bypass RLS when needed

GRANT ALL ON public.roles TO service_role;
GRANT ALL ON public.user_roles TO service_role;
GRANT ALL ON public.api_keys TO service_role;
GRANT ALL ON public.rbac_audit_logs TO service_role;


-- =============================================================================
-- COMMENTS FOR DOCUMENTATION
-- =============================================================================
COMMENT ON TABLE public.roles IS 'RBAC role definitions with permission configurations';
COMMENT ON TABLE public.user_roles IS 'User-to-role assignments (many-to-many)';
COMMENT ON TABLE public.api_keys IS 'API keys with bcrypt-hashed secrets for authentication';
COMMENT ON TABLE public.rbac_audit_logs IS 'Immutable audit log for all RBAC operations';

COMMENT ON COLUMN public.api_keys.key_hash IS 'Bcrypt hash of the full API key - never store plaintext';
COMMENT ON COLUMN public.api_keys.key_prefix IS 'First 12 characters (emp_xxxxxxxx) for identification without revealing full key';
COMMENT ON COLUMN public.rbac_audit_logs.created_at IS 'Immutable timestamp - no updated_at column as audit logs cannot be modified';
