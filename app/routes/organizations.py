"""
Empire v7.3 - Organization API Routes

Endpoints:
- POST /api/organizations          - Create organization
- GET  /api/organizations          - List user's organizations
- GET  /api/organizations/{id}     - Get organization detail
- PUT  /api/organizations/{id}     - Update organization
- POST /api/organizations/{id}/members          - Add member
- GET  /api/organizations/{id}/members          - List members
- DELETE /api/organizations/{id}/members/{uid}  - Remove member
- GET  /api/organizations/{id}/export           - Export org data (owner only)
"""

from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user
from app.services.organization_service import (
    OrganizationService,
    get_organization_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/organizations", tags=["Organizations"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateOrgRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = Field(None, max_length=100, pattern=r'^[a-z0-9-]+$')
    logoUrl: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class UpdateOrgRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    logoUrl: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class AddMemberRequest(BaseModel):
    userId: str = Field(..., min_length=1)
    role: str = Field("member", pattern=r'^(owner|admin|member|viewer)$')


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    logoUrl: Optional[str] = None
    settings: Dict[str, Any] = {}
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    memberCount: int = 0
    userRole: Optional[str] = None


class MemberResponse(BaseModel):
    id: str
    orgId: str
    userId: str
    role: str
    createdAt: Optional[str] = None


# ============================================================================
# Routes
# ============================================================================

@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    request: CreateOrgRequest,
    user_id: str = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """Create a new organization. The creator becomes the owner."""
    try:
        org = await org_service.create_org(
            name=request.name,
            owner_user_id=user_id,
            slug=request.slug,
            logo_url=request.logoUrl,
            settings=request.settings,
        )
        return OrgResponse(**org.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("", response_model=List[OrgResponse])
async def list_organizations(
    user_id: str = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """List organizations the current user belongs to."""
    orgs = await org_service.get_user_orgs(user_id)
    return [OrgResponse(**o.to_dict()) for o in orgs]


@router.get("/{org_id}", response_model=OrgResponse)
async def get_organization(
    org_id: str,
    user_id: str = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """Get organization details. Requires membership."""
    org = await org_service.get_org(org_id, user_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found or access denied")
    return OrgResponse(**org.to_dict())


@router.put("/{org_id}", response_model=OrgResponse)
async def update_organization(
    org_id: str,
    request: UpdateOrgRequest,
    user_id: str = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """Update organization. Requires owner or admin role."""
    org = await org_service.update_org(
        org_id=org_id,
        user_id=user_id,
        name=request.name,
        logo_url=request.logoUrl,
        settings=request.settings,
    )
    if not org:
        raise HTTPException(status_code=403, detail="Insufficient permissions or org not found")
    return OrgResponse(**org.to_dict())


@router.post("/{org_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    org_id: str,
    request: AddMemberRequest,
    user_id: str = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """Add a member to the organization. Requires owner or admin role."""
    try:
        membership = await org_service.add_member(
            org_id=org_id,
            requesting_user_id=user_id,
            target_user_id=request.userId,
            role=request.role,
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return MemberResponse(**membership.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.get("/{org_id}/members", response_model=List[MemberResponse])
async def list_members(
    org_id: str,
    user_id: str = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """List members of an organization. Requires membership."""
    members = await org_service.get_members(org_id, user_id)
    if not members:
        raise HTTPException(status_code=404, detail="Organization not found or access denied")
    return [MemberResponse(**m.to_dict()) for m in members]


@router.delete("/{org_id}/members/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    org_id: str,
    target_user_id: str,
    user_id: str = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """Remove a member from the organization. Requires owner or admin role."""
    try:
        removed = await org_service.remove_member(
            org_id=org_id,
            requesting_user_id=user_id,
            target_user_id=target_user_id,
        )
        if not removed:
            raise HTTPException(status_code=403, detail="Insufficient permissions or member not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{org_id}/export")
async def export_organization(
    org_id: str,
    user_id: str = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
):
    """Export all portable organization data. Owner only."""
    try:
        data = await org_service.export_org_data(org_id, user_id)
        return data
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
