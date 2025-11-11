# RBAC API Design - Task 31.2

## API Key Management Endpoints Design

### Overview
FastAPI endpoints for Role-Based Access Control (RBAC) and API key lifecycle management with secure storage in Supabase.

### Architecture Decisions

**Security Principles:**
1. API keys NEVER stored in plaintext (always bcrypt hashed)
2. key_prefix exposed for identification (first 8 chars: `emp_xxxx`)
3. Full key shown ONCE at creation, never retrievable again
4. All operations logged to rbac_audit_logs table
5. RLS policies enforce role-based access at database level

**API Key Format:**
- Prefix: `emp_` (Empire identifier)
- Random secure token: 32 bytes (hex encoded = 64 chars)
- Full format: `emp_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef`
- Stored: bcrypt hash of full key
- Exposed: Only prefix (`emp_12345678`)

---

## 1. Pydantic Models

### Request Models

```python
# app/models/rbac.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class RoleEnum(str, Enum):
    """Available role names."""
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    GUEST = "guest"


class APIKeyCreateRequest(BaseModel):
    """Request model for creating a new API key."""
    key_name: str = Field(..., min_length=1, max_length=255, description="Human-readable name for the API key")
    role_id: str = Field(..., description="UUID of role to assign to this API key")
    scopes: List[str] = Field(default_factory=list, description="Optional permission scopes")
    rate_limit_per_hour: int = Field(default=1000, ge=1, le=10000, description="Requests per hour limit")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration datetime")

    @validator('key_name')
    def validate_key_name(cls, v):
        if not v.strip():
            raise ValueError("key_name cannot be empty")
        return v.strip()


class APIKeyRotateRequest(BaseModel):
    """Request model for rotating an existing API key."""
    key_id: str = Field(..., description="UUID of key to rotate")
    new_key_name: Optional[str] = Field(None, description="Optional new name for rotated key")
    expires_at: Optional[datetime] = Field(None, description="Optional new expiration")


class APIKeyRevokeRequest(BaseModel):
    """Request model for revoking an API key."""
    key_id: str = Field(..., description="UUID of key to revoke")
    revoke_reason: str = Field(..., min_length=1, max_length=500, description="Reason for revocation")


class UserRoleAssignRequest(BaseModel):
    """Request model for assigning a role to a user."""
    user_id: str = Field(..., description="User ID (from Clerk or auth system)")
    role_name: RoleEnum = Field(..., description="Role to assign")
    expires_at: Optional[datetime] = Field(None, description="Optional role expiration")


class UserRoleRevokeRequest(BaseModel):
    """Request model for revoking a role from a user."""
    user_id: str = Field(..., description="User ID")
    role_name: RoleEnum = Field(..., description="Role to revoke")
```

### Response Models

```python
class APIKeyCreateResponse(BaseModel):
    """Response model for API key creation - ONLY time full key is visible."""
    key_id: str = Field(..., description="UUID of created key")
    key_name: str = Field(..., description="Human-readable name")
    api_key: str = Field(..., description="FULL API KEY - save this, it will never be shown again")
    key_prefix: str = Field(..., description="First 8 chars for identification")
    role_id: str = Field(..., description="Assigned role UUID")
    scopes: List[str] = Field(..., description="Permission scopes")
    rate_limit_per_hour: int = Field(..., description="Rate limit")
    expires_at: Optional[datetime] = Field(None, description="Expiration datetime")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "key_id": "550e8400-e29b-41d4-a716-446655440000",
                "key_name": "Production API Key",
                "api_key": "emp_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "key_prefix": "emp_12345678",
                "role_id": "660e8400-e29b-41d4-a716-446655440000",
                "scopes": ["documents:read", "documents:write"],
                "rate_limit_per_hour": 1000,
                "expires_at": "2025-12-31T23:59:59Z",
                "created_at": "2025-01-10T12:00:00Z"
            }
        }


class APIKeyListItem(BaseModel):
    """Response model for individual API key in list (no full key)."""
    key_id: str
    key_name: str
    key_prefix: str  # Only prefix visible
    role_id: Optional[str]
    scopes: List[str]
    rate_limit_per_hour: int
    is_active: bool
    last_used_at: Optional[datetime]
    usage_count: int
    expires_at: Optional[datetime]
    created_at: datetime


class APIKeyListResponse(BaseModel):
    """Response model for listing API keys."""
    keys: List[APIKeyListItem]
    total: int


class RoleInfo(BaseModel):
    """Response model for role information."""
    id: str
    role_name: str
    description: Optional[str]
    permissions: dict
    can_read_documents: bool
    can_write_documents: bool
    can_delete_documents: bool
    can_manage_users: bool
    can_manage_api_keys: bool
    can_view_audit_logs: bool
    is_active: bool
    created_at: datetime


class UserRoleInfo(BaseModel):
    """Response model for user role assignment."""
    id: str
    user_id: str
    role: RoleInfo
    granted_by: Optional[str]
    granted_at: datetime
    expires_at: Optional[datetime]
    is_active: bool


class AuditLogEntry(BaseModel):
    """Response model for audit log entries."""
    id: str
    event_type: str
    actor_user_id: Optional[str]
    target_user_id: Optional[str]
    target_resource_type: Optional[str]
    target_resource_id: Optional[str]
    action: str
    result: str  # 'success', 'failure', 'denied'
    ip_address: Optional[str]
    user_agent: Optional[str]
    metadata: dict
    error_message: Optional[str]
    created_at: datetime
```

---

## 2. FastAPI Route Structure

### File: `app/routes/rbac.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import List, Optional
import structlog

from app.models.rbac import (
    APIKeyCreateRequest, APIKeyCreateResponse,
    APIKeyRotateRequest, APIKeyListResponse,
    APIKeyRevokeRequest, UserRoleAssignRequest,
    UserRoleRevokeRequest, RoleInfo, UserRoleInfo,
    AuditLogEntry
)
from app.services.rbac_service import RBACService
from app.middleware.auth import get_current_user, require_admin

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/rbac", tags=["RBAC"])


# ==================== API KEY ENDPOINTS ====================

@router.post(
    "/keys",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API Key",
    description="Generate a new API key. The full key is returned ONCE and never stored in plaintext."
)
async def create_api_key(
    request: APIKeyCreateRequest,
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends(),
    http_request: Request = None
):
    """
    Create a new API key with bcrypt hashing.

    **SECURITY**: Full key is shown ONLY in this response. Save it securely.
    """
    try:
        result = await rbac_service.create_api_key(
            user_id=current_user,
            key_name=request.key_name,
            role_id=request.role_id,
            scopes=request.scopes,
            rate_limit_per_hour=request.rate_limit_per_hour,
            expires_at=request.expires_at,
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info(
            "API key created",
            key_id=result["key_id"],
            user_id=current_user,
            key_name=request.key_name
        )

        return APIKeyCreateResponse(**result)

    except Exception as e:
        logger.error("Failed to create API key", error=str(e), user_id=current_user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}"
        )


@router.get(
    "/keys",
    response_model=APIKeyListResponse,
    summary="List API Keys",
    description="List all API keys for the current user (admins see all keys)"
)
async def list_api_keys(
    current_user: str = Depends(get_current_user),
    is_admin: bool = Depends(require_admin),
    rbac_service: RBACService = Depends(),
    user_id: Optional[str] = None
):
    """
    List API keys. Regular users see only their keys, admins can filter by user_id.
    """
    try:
        # Non-admins can only see their own keys
        if not is_admin:
            user_id = current_user
        elif user_id is None:
            user_id = current_user

        keys = await rbac_service.list_api_keys(user_id=user_id)

        return APIKeyListResponse(
            keys=keys,
            total=len(keys)
        )

    except Exception as e:
        logger.error("Failed to list API keys", error=str(e), user_id=current_user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list API keys: {str(e)}"
        )


@router.post(
    "/keys/rotate",
    response_model=APIKeyCreateResponse,
    summary="Rotate API Key",
    description="Generate a new key for an existing API key ID. Old key is revoked."
)
async def rotate_api_key(
    request: APIKeyRotateRequest,
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends(),
    http_request: Request = None
):
    """
    Rotate an API key by generating a new key and revoking the old one.
    """
    try:
        result = await rbac_service.rotate_api_key(
            key_id=request.key_id,
            user_id=current_user,
            new_key_name=request.new_key_name,
            expires_at=request.expires_at,
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info(
            "API key rotated",
            old_key_id=request.key_id,
            new_key_id=result["key_id"],
            user_id=current_user
        )

        return APIKeyCreateResponse(**result)

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to rotate API key", error=str(e), key_id=request.key_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rotate API key: {str(e)}"
        )


@router.post(
    "/keys/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke API Key",
    description="Permanently revoke an API key"
)
async def revoke_api_key(
    request: APIKeyRevokeRequest,
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends(),
    http_request: Request = None
):
    """
    Revoke an API key permanently.
    """
    try:
        await rbac_service.revoke_api_key(
            key_id=request.key_id,
            user_id=current_user,
            revoke_reason=request.revoke_reason,
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info(
            "API key revoked",
            key_id=request.key_id,
            user_id=current_user,
            reason=request.revoke_reason
        )

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to revoke API key", error=str(e), key_id=request.key_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke API key: {str(e)}"
        )


# ==================== ROLE MANAGEMENT ENDPOINTS ====================

@router.get(
    "/roles",
    response_model=List[RoleInfo],
    summary="List Available Roles",
    description="Get all available roles in the system"
)
async def list_roles(
    rbac_service: RBACService = Depends()
):
    """
    List all roles (admin, editor, viewer, guest).
    """
    try:
        roles = await rbac_service.list_roles()
        return roles

    except Exception as e:
        logger.error("Failed to list roles", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list roles: {str(e)}"
        )


@router.post(
    "/users/assign-role",
    response_model=UserRoleInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Assign Role to User",
    description="Assign a role to a user (admin only)"
)
async def assign_user_role(
    request: UserRoleAssignRequest,
    current_user: str = Depends(require_admin),  # Only admins
    rbac_service: RBACService = Depends(),
    http_request: Request = None
):
    """
    Assign a role to a user. Only admins can assign roles.
    """
    try:
        result = await rbac_service.assign_user_role(
            user_id=request.user_id,
            role_name=request.role_name,
            granted_by=current_user,
            expires_at=request.expires_at,
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info(
            "Role assigned to user",
            user_id=request.user_id,
            role=request.role_name,
            granted_by=current_user
        )

        return UserRoleInfo(**result)

    except Exception as e:
        logger.error("Failed to assign role", error=str(e), user_id=request.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign role: {str(e)}"
        )


@router.post(
    "/users/revoke-role",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke Role from User",
    description="Revoke a role from a user (admin only)"
)
async def revoke_user_role(
    request: UserRoleRevokeRequest,
    current_user: str = Depends(require_admin),  # Only admins
    rbac_service: RBACService = Depends(),
    http_request: Request = None
):
    """
    Revoke a role from a user. Only admins can revoke roles.
    """
    try:
        await rbac_service.revoke_user_role(
            user_id=request.user_id,
            role_name=request.role_name,
            revoked_by=current_user,
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info(
            "Role revoked from user",
            user_id=request.user_id,
            role=request.role_name,
            revoked_by=current_user
        )

    except Exception as e:
        logger.error("Failed to revoke role", error=str(e), user_id=request.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke role: {str(e)}"
        )


@router.get(
    "/users/{user_id}/roles",
    response_model=List[UserRoleInfo],
    summary="Get User Roles",
    description="Get all active roles for a specific user"
)
async def get_user_roles(
    user_id: str,
    current_user: str = Depends(get_current_user),
    is_admin: bool = Depends(require_admin),
    rbac_service: RBACService = Depends()
):
    """
    Get all roles for a user. Regular users can only see their own roles.
    """
    try:
        # Non-admins can only see their own roles
        if not is_admin and user_id != current_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own roles"
            )

        roles = await rbac_service.get_user_roles(user_id=user_id)
        return roles

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user roles", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user roles: {str(e)}"
        )


# ==================== AUDIT LOG ENDPOINTS ====================

@router.get(
    "/audit-logs",
    response_model=List[AuditLogEntry],
    summary="Get Audit Logs",
    description="Get audit logs for RBAC events (admin only)"
)
async def get_audit_logs(
    current_user: str = Depends(require_admin),  # Only admins
    rbac_service: RBACService = Depends(),
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get audit logs for RBAC operations. Only admins can view audit logs.
    """
    try:
        logs = await rbac_service.get_audit_logs(
            event_type=event_type,
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        return logs

    except Exception as e:
        logger.error("Failed to get audit logs", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit logs: {str(e)}"
        )
```

---

## 3. Service Layer Architecture

### File: `app/services/rbac_service.py`

```python
import secrets
import bcrypt
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog
from uuid import uuid4

from app.core.supabase_client import get_supabase_client

logger = structlog.get_logger(__name__)


class RBACService:
    """
    Service for managing RBAC and API keys with secure storage in Supabase.

    Features:
    - Bcrypt hashing for API keys (never stores plaintext)
    - Audit logging for all operations
    - Role-based permission checks
    - API key lifecycle management
    """

    def __init__(self):
        self.supabase = get_supabase_client()

    # ==================== API KEY METHODS ====================

    def _generate_api_key(self) -> tuple[str, str, str]:
        """
        Generate a secure API key.

        Returns:
            tuple: (full_key, key_hash, key_prefix)
            - full_key: emp_xxxx (64 char hex token)
            - key_hash: bcrypt hash of full_key
            - key_prefix: First 8 chars (emp_xxxxx)
        """
        # Generate 32 random bytes = 64 hex chars
        random_token = secrets.token_hex(32)
        full_key = f"emp_{random_token}"

        # Hash with bcrypt (never store plaintext)
        key_hash = bcrypt.hashpw(full_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Extract prefix for identification (first 12 chars: "emp_" + 8 hex)
        key_prefix = full_key[:12]

        return full_key, key_hash, key_prefix

    async def create_api_key(
        self,
        user_id: str,
        key_name: str,
        role_id: str,
        scopes: List[str] = None,
        rate_limit_per_hour: int = 1000,
        expires_at: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new API key with bcrypt hashing.

        Returns:
            dict: Contains full API key (SHOWN ONCE), key_id, prefix, etc.
        """
        # Generate secure key
        full_key, key_hash, key_prefix = self._generate_api_key()

        # Insert into database (stores hash, not plaintext)
        result = self.supabase.table("api_keys").insert({
            "id": str(uuid4()),
            "key_name": key_name,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "user_id": user_id,
            "role_id": role_id,
            "scopes": scopes or [],
            "rate_limit_per_hour": rate_limit_per_hour,
            "is_active": True,
            "expires_at": expires_at.isoformat() if expires_at else None
        }).execute()

        key_id = result.data[0]["id"]

        # Log creation event
        await self._log_audit_event(
            event_type="api_key_created",
            actor_user_id=user_id,
            target_resource_type="api_key",
            target_resource_id=key_id,
            action="create",
            result="success",
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"key_name": key_name, "role_id": role_id}
        )

        logger.info(
            "API key created",
            key_id=key_id,
            user_id=user_id,
            key_prefix=key_prefix
        )

        # Return full key (ONLY TIME IT'S VISIBLE)
        return {
            "key_id": key_id,
            "key_name": key_name,
            "api_key": full_key,  # ⚠️ FULL KEY - save this!
            "key_prefix": key_prefix,
            "role_id": role_id,
            "scopes": scopes or [],
            "rate_limit_per_hour": rate_limit_per_hour,
            "expires_at": expires_at,
            "created_at": result.data[0]["created_at"]
        }

    async def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate an API key by checking bcrypt hash.

        Args:
            api_key: Full API key to validate (emp_xxx...)

        Returns:
            dict: Key metadata if valid, None if invalid
        """
        # Extract prefix for faster lookup
        key_prefix = api_key[:12]

        # Find keys with matching prefix
        result = self.supabase.table("api_keys").select("*").eq("key_prefix", key_prefix).eq("is_active", True).execute()

        if not result.data:
            return None

        # Check bcrypt hash
        for key_record in result.data:
            if bcrypt.checkpw(api_key.encode('utf-8'), key_record["key_hash"].encode('utf-8')):
                # Valid key found - update usage stats
                key_id = key_record["id"]

                self.supabase.table("api_keys").update({
                    "last_used_at": datetime.utcnow().isoformat(),
                    "usage_count": key_record["usage_count"] + 1
                }).eq("id", key_id).execute()

                # Log usage
                await self._log_audit_event(
                    event_type="api_key_used",
                    actor_user_id=key_record["user_id"],
                    target_resource_type="api_key",
                    target_resource_id=key_id,
                    action="use",
                    result="success"
                )

                return key_record

        # No matching hash found
        return None

    async def list_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """
        List all API keys for a user (prefix only, not full key).
        """
        result = self.supabase.table("api_keys").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()

        # Return without full key (only prefix)
        return [{
            "key_id": k["id"],
            "key_name": k["key_name"],
            "key_prefix": k["key_prefix"],
            "role_id": k.get("role_id"),
            "scopes": k.get("scopes", []),
            "rate_limit_per_hour": k["rate_limit_per_hour"],
            "is_active": k["is_active"],
            "last_used_at": k.get("last_used_at"),
            "usage_count": k.get("usage_count", 0),
            "expires_at": k.get("expires_at"),
            "created_at": k["created_at"]
        } for k in result.data]

    async def rotate_api_key(
        self,
        key_id: str,
        user_id: str,
        new_key_name: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rotate an API key: revoke old, create new with same permissions.
        """
        # Get old key details
        old_key = self.supabase.table("api_keys").select("*").eq("id", key_id).single().execute()

        if not old_key.data:
            raise ValueError(f"API key {key_id} not found")

        # Check ownership
        if old_key.data["user_id"] != user_id:
            raise PermissionError("You do not own this API key")

        # Revoke old key
        await self.revoke_api_key(
            key_id=key_id,
            user_id=user_id,
            revoke_reason="Rotated to new key",
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Create new key with same permissions
        new_key = await self.create_api_key(
            user_id=user_id,
            key_name=new_key_name or f"{old_key.data['key_name']} (Rotated)",
            role_id=old_key.data["role_id"],
            scopes=old_key.data.get("scopes", []),
            rate_limit_per_hour=old_key.data["rate_limit_per_hour"],
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Log rotation event
        await self._log_audit_event(
            event_type="api_key_rotated",
            actor_user_id=user_id,
            target_resource_type="api_key",
            target_resource_id=key_id,
            action="rotate",
            result="success",
            metadata={"old_key_id": key_id, "new_key_id": new_key["key_id"]},
            ip_address=ip_address,
            user_agent=user_agent
        )

        return new_key

    async def revoke_api_key(
        self,
        key_id: str,
        user_id: str,
        revoke_reason: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        Revoke an API key permanently.
        """
        # Check ownership
        key_record = self.supabase.table("api_keys").select("user_id").eq("id", key_id).single().execute()

        if not key_record.data:
            raise ValueError(f"API key {key_id} not found")

        if key_record.data["user_id"] != user_id:
            raise PermissionError("You do not own this API key")

        # Revoke
        self.supabase.table("api_keys").update({
            "is_active": False,
            "revoked_at": datetime.utcnow().isoformat(),
            "revoked_by": user_id,
            "revoke_reason": revoke_reason
        }).eq("id", key_id).execute()

        # Log revocation
        await self._log_audit_event(
            event_type="api_key_revoked",
            actor_user_id=user_id,
            target_resource_type="api_key",
            target_resource_id=key_id,
            action="revoke",
            result="success",
            metadata={"reason": revoke_reason},
            ip_address=ip_address,
            user_agent=user_agent
        )

        logger.info("API key revoked", key_id=key_id, user_id=user_id)

    # ==================== ROLE METHODS ====================

    async def list_roles(self) -> List[Dict[str, Any]]:
        """Get all available roles."""
        result = self.supabase.table("roles").select("*").eq("is_active", True).execute()
        return result.data

    async def assign_user_role(
        self,
        user_id: str,
        role_name: str,
        granted_by: str,
        expires_at: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Assign a role to a user.
        """
        # Get role ID
        role = self.supabase.table("roles").select("id").eq("role_name", role_name).single().execute()

        if not role.data:
            raise ValueError(f"Role {role_name} not found")

        role_id = role.data["id"]

        # Insert user_role
        result = self.supabase.table("user_roles").insert({
            "id": str(uuid4()),
            "user_id": user_id,
            "role_id": role_id,
            "granted_by": granted_by,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "is_active": True
        }).execute()

        # Log event
        await self._log_audit_event(
            event_type="role_assigned",
            actor_user_id=granted_by,
            target_user_id=user_id,
            target_resource_type="user_role",
            target_resource_id=result.data[0]["id"],
            action="assign",
            result="success",
            metadata={"role": role_name},
            ip_address=ip_address,
            user_agent=user_agent
        )

        return result.data[0]

    async def revoke_user_role(
        self,
        user_id: str,
        role_name: str,
        revoked_by: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        Revoke a role from a user.
        """
        # Get role ID
        role = self.supabase.table("roles").select("id").eq("role_name", role_name).single().execute()

        if not role.data:
            raise ValueError(f"Role {role_name} not found")

        role_id = role.data["id"]

        # Deactivate user_role
        self.supabase.table("user_roles").update({
            "is_active": False,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("user_id", user_id).eq("role_id", role_id).execute()

        # Log event
        await self._log_audit_event(
            event_type="role_revoked",
            actor_user_id=revoked_by,
            target_user_id=user_id,
            action="revoke",
            result="success",
            metadata={"role": role_name},
            ip_address=ip_address,
            user_agent=user_agent
        )

    async def get_user_roles(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all active roles for a user.
        """
        result = self.supabase.table("user_roles").select("*, role:roles(*)").eq("user_id", user_id).eq("is_active", True).execute()
        return result.data

    # ==================== AUDIT LOG METHODS ====================

    async def _log_audit_event(
        self,
        event_type: str,
        action: str,
        result: str,
        actor_user_id: Optional[str] = None,
        target_user_id: Optional[str] = None,
        target_resource_type: Optional[str] = None,
        target_resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[dict] = None,
        error_message: Optional[str] = None
    ):
        """
        Log an audit event (immutable).
        """
        self.supabase.table("rbac_audit_logs").insert({
            "id": str(uuid4()),
            "event_type": event_type,
            "actor_user_id": actor_user_id,
            "target_user_id": target_user_id,
            "target_resource_type": target_resource_type,
            "target_resource_id": target_resource_id,
            "action": action,
            "result": result,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "metadata": metadata or {},
            "error_message": error_message
        }).execute()

    async def get_audit_logs(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get audit logs with optional filters.
        """
        query = self.supabase.table("rbac_audit_logs").select("*")

        if event_type:
            query = query.eq("event_type", event_type)

        if user_id:
            query = query.or_(f"actor_user_id.eq.{user_id},target_user_id.eq.{user_id}")

        result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

        return result.data
```

---

## 4. Authentication Middleware

### File: `app/middleware/auth.py`

```python
from fastapi import Depends, HTTPException, status, Header
from typing import Optional
import structlog

from app.services.rbac_service import RBACService

logger = structlog.get_logger(__name__)


async def get_current_user(
    authorization: Optional[str] = Header(None),
    rbac_service: RBACService = Depends()
) -> str:
    """
    Extract and validate user from JWT or API key.

    Returns:
        user_id: Validated user ID
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )

    # Check if API key
    if authorization.startswith("emp_"):
        api_key = authorization
        key_record = await rbac_service.validate_api_key(api_key)

        if not key_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )

        return key_record["user_id"]

    # Check if Bearer token (JWT)
    elif authorization.startswith("Bearer "):
        # TODO: Implement JWT validation (Clerk or custom)
        # For now, extract user_id from token
        token = authorization.split(" ")[1]
        # Validate token and extract user_id
        # This would integrate with Clerk or your JWT system
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="JWT authentication not yet implemented"
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Use 'emp_xxx' API key or 'Bearer <token>'"
        )


async def require_admin(
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends()
) -> bool:
    """
    Check if current user has admin role.

    Returns:
        True if admin, raises HTTPException if not
    """
    roles = await rbac_service.get_user_roles(current_user)

    is_admin = any(r["role"]["role_name"] == "admin" for r in roles if r.get("role"))

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )

    return True
```

---

## 5. Integration with FastAPI App

### File: `app/main.py` (additions)

```python
from app.routes import rbac

# Add RBAC router
app.include_router(rbac.router)
```

---

## 6. Supabase Client Helper

### File: `app/core/supabase_client.py`

```python
import os
from supabase import create_client, Client


def get_supabase_client() -> Client:
    """
    Get Supabase client instance.

    Returns:
        Supabase client with RLS enabled
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")  # Service key bypasses RLS for admin operations

    return create_client(url, key)
```

---

## 7. Testing Plan

### Unit Tests
- Test API key generation (format, uniqueness)
- Test bcrypt hashing and validation
- Test key rotation (old revoked, new created)
- Test permission checks

### Integration Tests
- Test full API key lifecycle (create → use → rotate → revoke)
- Test role assignment flow
- Test audit logging for all operations
- Test RLS policies (users can't see other users' keys)

### Security Tests
- Verify plaintext keys never stored in database
- Test rate limiting
- Test expired key rejection
- Test revoked key rejection

---

## 8. Next Steps (Delegation to Cline)

**Implementation Tasks (1-3 files each):**
1. Create Pydantic models (`app/models/rbac.py`)
2. Create RBAC service (`app/services/rbac_service.py`)
3. Create authentication middleware (`app/middleware/auth.py`)
4. Create Supabase client helper (`app/core/supabase_client.py`)
5. Create FastAPI routes (`app/routes/rbac.py`)
6. Add router to main app (`app/main.py`)
7. Create unit tests (`tests/test_rbac.py`)

Each task is suitable for Cline with visual diff review.
