"""
Empire v7.3 - Organization Service
Multi-tenant organization management with membership and role control.

Portability boundary:
  PORTABLE: organizations, org_memberships, projects + children
  NOT PORTABLE: Global KB, CKO KB chats
"""

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import structlog

from app.services.supabase_storage import get_supabase_storage

logger = structlog.get_logger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Organization:
    id: str
    name: str
    slug: str
    logo_url: Optional[str] = None
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    member_count: int = 0
    user_role: Optional[str] = None  # Role of requesting user

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "logoUrl": self.logo_url,
            "settings": self.settings,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "memberCount": self.member_count,
            "userRole": self.user_role,
        }


@dataclass
class OrgMembership:
    id: str
    org_id: str
    user_id: str
    role: str
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "orgId": self.org_id,
            "userId": self.user_id,
            "role": self.role,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================================
# Service
# ============================================================================

class OrganizationService:
    """Manages organizations, memberships, and org-scoped data access."""

    def __init__(self):
        self.supabase = get_supabase_storage()
        logger.info("OrganizationService initialized")

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert organization name to URL-safe slug."""
        slug = name.lower().strip()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s-]+', '-', slug)
        return slug.strip('-')

    # =========================================================================
    # Organization CRUD
    # =========================================================================

    async def create_org(
        self,
        name: str,
        owner_user_id: str,
        slug: Optional[str] = None,
        logo_url: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Organization:
        """Create a new organization and add the creator as owner."""
        slug = slug or self._slugify(name)

        # Insert organization
        org_result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("organizations")
            .insert({
                "name": name,
                "slug": slug,
                "logo_url": logo_url,
                "settings": settings or {},
            })
            .execute()
        )

        if not org_result.data:
            raise ValueError("Failed to create organization")

        org_row = org_result.data[0]
        org_id = org_row["id"]

        # Add creator as owner
        await asyncio.to_thread(
            lambda: self.supabase.supabase.table("org_memberships")
            .insert({
                "org_id": org_id,
                "user_id": owner_user_id,
                "role": "owner",
            })
            .execute()
        )

        logger.info("Organization created", org_id=org_id, name=name, owner=owner_user_id)

        return self._row_to_org(org_row, user_role="owner", member_count=1)

    async def get_user_orgs(self, user_id: str) -> List[Organization]:
        """List organizations the user belongs to."""
        result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("org_memberships")
            .select("org_id, role, organizations(id, name, slug, logo_url, settings, created_at, updated_at)")
            .eq("user_id", user_id)
            .execute()
        )

        orgs = []
        for row in result.data or []:
            org_data = row.get("organizations")
            if not org_data:
                continue

            # Get member count for each org
            count_result = await asyncio.to_thread(
                lambda oid=row["org_id"]: self.supabase.supabase.table("org_memberships")
                .select("id", count="exact")
                .eq("org_id", oid)
                .execute()
            )
            member_count = count_result.count or 0

            orgs.append(self._row_to_org(
                org_data,
                user_role=row["role"],
                member_count=member_count,
            ))

        return orgs

    async def get_org(self, org_id: str, user_id: str) -> Optional[Organization]:
        """Get organization details. Returns None if user is not a member."""
        membership = await self._get_membership(org_id, user_id)
        if not membership:
            return None

        result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("organizations")
            .select("*")
            .eq("id", org_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            return None

        count_result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("org_memberships")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .execute()
        )

        return self._row_to_org(
            result.data[0],
            user_role=membership.role,
            member_count=count_result.count or 0,
        )

    async def update_org(
        self,
        org_id: str,
        user_id: str,
        name: Optional[str] = None,
        logo_url: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Optional[Organization]:
        """Update organization. Requires owner or admin role."""
        membership = await self._get_membership(org_id, user_id)
        if not membership or membership.role not in ("owner", "admin"):
            return None

        update_data: Dict[str, Any] = {}
        if name is not None:
            update_data["name"] = name
        if logo_url is not None:
            update_data["logo_url"] = logo_url
        if settings is not None:
            update_data["settings"] = settings

        if not update_data:
            return await self.get_org(org_id, user_id)

        result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("organizations")
            .update(update_data)
            .eq("id", org_id)
            .execute()
        )

        if not result.data:
            return None

        logger.info("Organization updated", org_id=org_id, fields=list(update_data.keys()))
        return await self.get_org(org_id, user_id)

    # =========================================================================
    # Membership Management
    # =========================================================================

    async def add_member(
        self,
        org_id: str,
        requesting_user_id: str,
        target_user_id: str,
        role: str = "member",
    ) -> Optional[OrgMembership]:
        """Add a member to the organization. Requires owner or admin role."""
        membership = await self._get_membership(org_id, requesting_user_id)
        if not membership or membership.role not in ("owner", "admin"):
            return None

        if role not in ("owner", "admin", "member", "viewer"):
            raise ValueError(f"Invalid role: {role}")
        if role == "owner" and membership.role != "owner":
            raise PermissionError("Only owners can assign the owner role")

        result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("org_memberships")
            .insert({
                "org_id": org_id,
                "user_id": target_user_id,
                "role": role,
            })
            .execute()
        )

        if not result.data:
            return None

        logger.info("Member added", org_id=org_id, user_id=target_user_id, role=role)
        return self._row_to_membership(result.data[0])

    async def remove_member(
        self,
        org_id: str,
        requesting_user_id: str,
        target_user_id: str,
    ) -> bool:
        """Remove a member. Requires owner/admin. Owners cannot remove themselves."""
        membership = await self._get_membership(org_id, requesting_user_id)
        if not membership or membership.role not in ("owner", "admin"):
            return False

        # Prevent owner from removing themselves
        target_membership = await self._get_membership(org_id, target_user_id)
        if target_membership and target_membership.role == "owner" and requesting_user_id == target_user_id:
            raise ValueError("Owner cannot remove themselves from the organization")
        if target_membership and target_membership.role == "owner" and membership.role != "owner":
            raise PermissionError("Only owners can remove other owners")

        result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("org_memberships")
            .delete()
            .eq("org_id", org_id)
            .eq("user_id", target_user_id)
            .execute()
        )

        removed = len(result.data or []) > 0
        if removed:
            logger.info("Member removed", org_id=org_id, user_id=target_user_id)
        return removed

    async def get_members(self, org_id: str, user_id: str) -> List[OrgMembership]:
        """List members of an organization. Requires membership."""
        membership = await self._get_membership(org_id, user_id)
        if not membership:
            return []

        result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("org_memberships")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at")
            .execute()
        )

        return [self._row_to_membership(row) for row in result.data or []]

    async def verify_membership(self, org_id: str, user_id: str) -> Optional[str]:
        """Verify user is a member and return their role. Used by middleware."""
        membership = await self._get_membership(org_id, user_id)
        return membership.role if membership else None

    # =========================================================================
    # Export (Acquisition Portability)
    # =========================================================================

    async def export_org_data(self, org_id: str, user_id: str) -> Dict[str, Any]:
        """
        Export all portable data for an organization.
        Returns a dict with all org data suitable for import into another instance.

        Portable: org info, memberships, projects, project_sources, conversations, artifacts
        NOT portable: Global KB, CKO KB chats
        """
        membership = await self._get_membership(org_id, user_id)
        if not membership or membership.role != "owner":
            raise PermissionError("Only the organization owner can export data")

        org = await self.get_org(org_id, user_id)
        if not org:
            raise ValueError("Organization not found")

        # Get all projects in this org
        projects_result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("projects")
            .select("*")
            .eq("org_id", org_id)
            .execute()
        )

        project_ids = [p["id"] for p in projects_result.data or []]

        # Get project sources for all org projects (single query)
        if project_ids:
            sources_result = await asyncio.to_thread(
                lambda: self.supabase.supabase.table("project_sources")
                .select("*")
                .in_("project_id", project_ids)
                .execute()
            )
            sources_data = sources_result.data or []
        else:
            sources_data = []

        return {
            "organization": org.to_dict(),
            "memberships": [m.to_dict() for m in await self.get_members(org_id, user_id)],
            "projects": projects_result.data or [],
            "project_sources": sources_data,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
        }

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _get_membership(self, org_id: str, user_id: str) -> Optional[OrgMembership]:
        """Get a user's membership in an org."""
        result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("org_memberships")
            .select("*")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            return None

        return self._row_to_membership(result.data[0])

    @staticmethod
    def _row_to_org(
        row: Dict[str, Any],
        user_role: Optional[str] = None,
        member_count: int = 0,
    ) -> Organization:
        return Organization(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            logo_url=row.get("logo_url"),
            settings=row.get("settings") or {},
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) if row.get("created_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")) if row.get("updated_at") else None,
            member_count=member_count,
            user_role=user_role,
        )

    @staticmethod
    def _row_to_membership(row: Dict[str, Any]) -> OrgMembership:
        return OrgMembership(
            id=row["id"],
            org_id=row["org_id"],
            user_id=row["user_id"],
            role=row["role"],
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) if row.get("created_at") else None,
        )


# ============================================================================
# Singleton
# ============================================================================

_service: Optional[OrganizationService] = None


def get_organization_service() -> OrganizationService:
    global _service
    if _service is None:
        _service = OrganizationService()
    return _service
