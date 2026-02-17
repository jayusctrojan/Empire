"""
Empire v7.3 - Organization Service Tests
Phase 0: Multi-Tenant Organization Layer

Tests for:
- Organization CRUD (create, get, update, list)
- Membership management (add, remove, list members)
- Role-based access control (owner, admin, member, viewer)
- Data export for portability
- Slug generation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone

from app.services.organization_service import (
    OrganizationService,
    Organization,
    OrgMembership,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_supabase():
    """Create a mock Supabase storage instance."""
    mock = MagicMock()
    mock.supabase = MagicMock()
    return mock


@pytest.fixture
def org_service(mock_supabase):
    """Create OrganizationService with mocked Supabase."""
    with patch("app.services.organization_service.get_supabase_storage", return_value=mock_supabase):
        service = OrganizationService()
    return service


@pytest.fixture
def sample_org_row():
    return {
        "id": "org-123",
        "name": "Acme Corp",
        "slug": "acme-corp",
        "logo_url": None,
        "settings": {},
        "created_at": "2026-01-15T10:00:00+00:00",
        "updated_at": "2026-01-15T10:00:00+00:00",
    }


@pytest.fixture
def sample_membership_row():
    return {
        "id": "mem-456",
        "org_id": "org-123",
        "user_id": "user-789",
        "role": "owner",
        "created_at": "2026-01-15T10:00:00+00:00",
    }


# ============================================================================
# Slug Generation Tests
# ============================================================================

class TestSlugGeneration:
    def test_basic_name(self):
        assert OrganizationService._slugify("Acme Corp") == "acme-corp"

    def test_special_characters(self):
        assert OrganizationService._slugify("Jay's Company!") == "jays-company"

    def test_multiple_spaces(self):
        assert OrganizationService._slugify("My   Big   Company") == "my-big-company"

    def test_leading_trailing_whitespace(self):
        assert OrganizationService._slugify("  Trimmed  ") == "trimmed"

    def test_unicode_stripped(self):
        slug = OrganizationService._slugify("Caf\u00e9 & Bar")
        assert "&" not in slug
        assert slug == "caf-bar"


# ============================================================================
# Create Organization Tests
# ============================================================================

class TestCreateOrg:
    @pytest.mark.asyncio
    async def test_create_org_success(self, org_service, mock_supabase, sample_org_row):
        # Mock insert org
        mock_supabase.supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_org_row]
        )

        org = await org_service.create_org(
            name="Acme Corp",
            owner_user_id="user-789",
        )

        assert org.name == "Acme Corp"
        assert org.slug == "acme-corp"
        assert org.user_role == "owner"
        assert org.member_count == 1

    @pytest.mark.asyncio
    async def test_create_org_custom_slug(self, org_service, mock_supabase, sample_org_row):
        sample_org_row["slug"] = "custom-slug"
        mock_supabase.supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_org_row]
        )

        org = await org_service.create_org(
            name="Acme Corp",
            owner_user_id="user-789",
            slug="custom-slug",
        )

        assert org.slug == "custom-slug"

    @pytest.mark.asyncio
    async def test_create_org_failure(self, org_service, mock_supabase):
        mock_supabase.supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with pytest.raises(ValueError, match="Failed to create organization"):
            await org_service.create_org(name="Bad Org", owner_user_id="user-1")


# ============================================================================
# Get Organization Tests
# ============================================================================

class TestGetOrg:
    @pytest.mark.asyncio
    async def test_get_org_as_member(self, org_service, mock_supabase, sample_org_row, sample_membership_row):
        # Mock membership check
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_membership_row]
        )
        # Mock org fetch
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_org_row]
        )
        # Mock member count
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            count=3
        )

        org = await org_service.get_org("org-123", "user-789")

        assert org is not None
        assert org.id == "org-123"
        assert org.name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_get_org_not_member(self, org_service, mock_supabase):
        # Mock membership check — no membership found
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = await org_service.get_org("org-123", "stranger")
        assert result is None


# ============================================================================
# Update Organization Tests
# ============================================================================

class TestUpdateOrg:
    @pytest.mark.asyncio
    async def test_update_org_success(self, org_service, mock_supabase, sample_org_row, sample_membership_row):
        """Test owner can update org name."""
        # Mock membership check — owner role
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_membership_row]
        )
        # Mock update
        updated_row = {**sample_org_row, "name": "New Name"}
        mock_supabase.supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_row]
        )
        # Mock get_org after update (membership + org fetch + count)
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[updated_row]
        )
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            count=1
        )

        result = await org_service.update_org("org-123", "user-789", name="New Name")

        assert result is not None

    @pytest.mark.asyncio
    async def test_update_requires_admin(self, org_service, mock_supabase, sample_membership_row):
        # Mock membership check — viewer role
        viewer_membership = {**sample_membership_row, "role": "viewer"}
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[viewer_membership]
        )

        result = await org_service.update_org("org-123", "user-789", name="New Name")
        assert result is None  # Denied


# ============================================================================
# Membership Tests
# ============================================================================

class TestMembership:
    @pytest.mark.asyncio
    async def test_add_member_by_admin(self, org_service, mock_supabase, sample_membership_row):
        admin_membership = {**sample_membership_row, "role": "admin"}

        # Mock membership check (requester is admin)
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[admin_membership]
        )
        # Mock insert
        new_member = {
            "id": "mem-new",
            "org_id": "org-123",
            "user_id": "new-user",
            "role": "member",
            "created_at": "2026-01-15T12:00:00+00:00",
        }
        mock_supabase.supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[new_member]
        )

        result = await org_service.add_member("org-123", "user-789", "new-user", "member")

        assert result is not None
        assert result.user_id == "new-user"
        assert result.role == "member"

    @pytest.mark.asyncio
    async def test_add_member_denied_for_regular_member(self, org_service, mock_supabase, sample_membership_row):
        member_role = {**sample_membership_row, "role": "member"}
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[member_role]
        )

        result = await org_service.add_member("org-123", "user-789", "new-user")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_role_raises(self, org_service, mock_supabase, sample_membership_row):
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_membership_row]
        )

        with pytest.raises(ValueError, match="Invalid role"):
            await org_service.add_member("org-123", "user-789", "new-user", "superadmin")

    @pytest.mark.asyncio
    async def test_owner_cannot_remove_self(self, org_service, mock_supabase, sample_membership_row):
        # Both requester and target are the same owner
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_membership_row]
        )

        with pytest.raises(ValueError, match="Owner cannot remove themselves"):
            await org_service.remove_member("org-123", "user-789", "user-789")


# ============================================================================
# Data Model Tests
# ============================================================================

class TestDataModels:
    def test_org_to_dict(self):
        org = Organization(
            id="org-1",
            name="Test",
            slug="test",
            member_count=5,
            user_role="admin",
        )
        d = org.to_dict()
        assert d["id"] == "org-1"
        assert d["memberCount"] == 5
        assert d["userRole"] == "admin"

    def test_membership_to_dict(self):
        mem = OrgMembership(
            id="mem-1",
            org_id="org-1",
            user_id="user-1",
            role="member",
        )
        d = mem.to_dict()
        assert d["orgId"] == "org-1"
        assert d["role"] == "member"


# ============================================================================
# Export Tests
# ============================================================================

class TestExport:
    @pytest.mark.asyncio
    async def test_export_org_data_success(self, org_service, mock_supabase, sample_org_row, sample_membership_row):
        """Test owner can export org data."""
        # Mock membership check — owner
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_membership_row]
        )
        # Mock get_org internals (org fetch + count)
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_org_row]
        )
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            count=1, data=[sample_membership_row]
        )
        # Mock projects + sources
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[], count=0
        )
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[sample_membership_row]
        )

        result = await org_service.export_org_data("org-123", "user-789")

        assert "organization" in result
        assert "memberships" in result
        assert "version" in result

    @pytest.mark.asyncio
    async def test_export_requires_owner(self, org_service, mock_supabase, sample_membership_row):
        # Mock membership as member (not owner)
        member_row = {**sample_membership_row, "role": "member"}
        mock_supabase.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[member_row]
        )

        with pytest.raises(PermissionError, match="Only the organization owner"):
            await org_service.export_org_data("org-123", "user-789")
