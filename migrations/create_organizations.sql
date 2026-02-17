-- ============================================================================
-- Organizations & Multi-Tenant Foundation
-- Creates the organization layer for multi-tenant SaaS with acquisition-ready
-- data portability. org_id on projects only — child data (project_sources,
-- conversations, artifacts) inherits scope via project FK.
--
-- Portability boundary:
--   PORTABLE: organizations, org_memberships, projects + children
--   NOT PORTABLE: Global KB (documents, chunks, embeddings), CKO KB chats
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 1. Organizations Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    logo_url TEXT,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 2. Organization Memberships (user <-> org, with roles)
-- ============================================================================
CREATE TABLE IF NOT EXISTS org_memberships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    role TEXT NOT NULL DEFAULT 'member'
        CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, user_id)
);

-- ============================================================================
-- 3. Add org_id to projects (nullable for migration)
-- ============================================================================
ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE SET NULL;

-- ============================================================================
-- 4. Indexes
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_org_memberships_user_id ON org_memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_org_memberships_org_id ON org_memberships(org_id);
CREATE INDEX IF NOT EXISTS idx_projects_org_id ON projects(org_id);
CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);

-- ============================================================================
-- 5. RLS Policies
-- ============================================================================

-- Organizations: users can only see orgs they belong to
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_member_read ON organizations;
CREATE POLICY org_member_read ON organizations
    FOR SELECT
    USING (
        id IN (
            SELECT org_id FROM org_memberships
            WHERE user_id = COALESCE(
                NULLIF(current_setting('app.user_id', true), '')::UUID,
                '00000000-0000-0000-0000-000000000000'::UUID
            )
        )
    );

DROP POLICY IF EXISTS org_owner_admin_write ON organizations;
CREATE POLICY org_owner_admin_write ON organizations
    FOR ALL
    USING (
        id IN (
            SELECT org_id FROM org_memberships
            WHERE user_id = COALESCE(
                NULLIF(current_setting('app.user_id', true), '')::UUID,
                '00000000-0000-0000-0000-000000000000'::UUID
            )
            AND role IN ('owner', 'admin')
        )
    );

-- Org memberships: users can see memberships for orgs they belong to
ALTER TABLE org_memberships ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS membership_org_member_read ON org_memberships;
CREATE POLICY membership_org_member_read ON org_memberships
    FOR SELECT
    USING (
        org_id IN (
            SELECT org_id FROM org_memberships AS m
            WHERE m.user_id = COALESCE(
                NULLIF(current_setting('app.user_id', true), '')::UUID,
                '00000000-0000-0000-0000-000000000000'::UUID
            )
        )
    );

DROP POLICY IF EXISTS membership_owner_admin_write ON org_memberships;
CREATE POLICY membership_owner_admin_write ON org_memberships
    FOR ALL
    USING (
        org_id IN (
            SELECT org_id FROM org_memberships AS m
            WHERE m.user_id = COALESCE(
                NULLIF(current_setting('app.user_id', true), '')::UUID,
                '00000000-0000-0000-0000-000000000000'::UUID
            )
            AND m.role IN ('owner', 'admin')
        )
    );

-- ============================================================================
-- 6. Updated_at trigger
-- ============================================================================
CREATE OR REPLACE FUNCTION update_organizations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_organizations_updated_at ON organizations;
CREATE TRIGGER trigger_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW
    EXECUTE FUNCTION update_organizations_updated_at();
