"""
Empire v7.3 - RBAC Models
Pydantic models for Role-Based Access Control (RBAC) and API key management
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class RoleEnum(str, Enum):
    """Available role names for RBAC."""
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    GUEST = "guest"


# ==================== REQUEST MODELS ====================


class APIKeyCreateRequest(BaseModel):
    """Request model for creating a new API key."""
    key_name: str = Field(..., min_length=1, max_length=255, description="Human-readable name for the API key")
    role_id: str = Field(..., description="UUID of role to assign to this API key")
    scopes: List[str] = Field(default_factory=list, description="Optional permission scopes")
    rate_limit_per_hour: int = Field(default=1000, ge=1, le=10000, description="Requests per hour limit")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration datetime")

    @validator('key_name')
    def validate_key_name(cls, v):
        """Strip whitespace and validate key name is not empty."""
        if not v.strip():
            raise ValueError("key_name cannot be empty")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "key_name": "Production API Key",
                "role_id": "660e8400-e29b-41d4-a716-446655440000",
                "scopes": ["documents:read", "documents:write"],
                "rate_limit_per_hour": 1000,
                "expires_at": "2025-12-31T23:59:59Z"
            }
        }


class APIKeyRotateRequest(BaseModel):
    """Request model for rotating an existing API key."""
    key_id: str = Field(..., description="UUID of key to rotate")
    new_key_name: Optional[str] = Field(None, description="Optional new name for rotated key")
    expires_at: Optional[datetime] = Field(None, description="Optional new expiration")

    class Config:
        json_schema_extra = {
            "example": {
                "key_id": "550e8400-e29b-41d4-a716-446655440000",
                "new_key_name": "Production API Key (Rotated)",
                "expires_at": "2026-12-31T23:59:59Z"
            }
        }


class APIKeyRevokeRequest(BaseModel):
    """Request model for revoking an API key."""
    key_id: str = Field(..., description="UUID of key to revoke")
    revoke_reason: str = Field(..., min_length=1, max_length=500, description="Reason for revocation")

    class Config:
        json_schema_extra = {
            "example": {
                "key_id": "550e8400-e29b-41d4-a716-446655440000",
                "revoke_reason": "Key compromised - rotating to new key"
            }
        }


class UserRoleAssignRequest(BaseModel):
    """Request model for assigning a role to a user."""
    user_id: str = Field(..., description="User ID (from Clerk or auth system)")
    role_name: RoleEnum = Field(..., description="Role to assign")
    expires_at: Optional[datetime] = Field(None, description="Optional role expiration")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_2abc123xyz",
                "role_name": "editor",
                "expires_at": "2025-12-31T23:59:59Z"
            }
        }


class UserRoleRevokeRequest(BaseModel):
    """Request model for revoking a role from a user."""
    user_id: str = Field(..., description="User ID")
    role_name: RoleEnum = Field(..., description="Role to revoke")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_2abc123xyz",
                "role_name": "editor"
            }
        }


# ==================== RESPONSE MODELS ====================


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
    key_id: str = Field(..., description="UUID of the API key")
    key_name: str = Field(..., description="Human-readable name")
    key_prefix: str = Field(..., description="Only prefix visible (emp_xxxxx)")
    role_id: Optional[str] = Field(None, description="Assigned role UUID")
    scopes: List[str] = Field(default_factory=list, description="Permission scopes")
    rate_limit_per_hour: int = Field(..., description="Rate limit")
    is_active: bool = Field(..., description="Whether the key is active")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")
    usage_count: int = Field(default=0, description="Number of times key has been used")
    expires_at: Optional[datetime] = Field(None, description="Expiration datetime")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "key_id": "550e8400-e29b-41d4-a716-446655440000",
                "key_name": "Production API Key",
                "key_prefix": "emp_12345678",
                "role_id": "660e8400-e29b-41d4-a716-446655440000",
                "scopes": ["documents:read", "documents:write"],
                "rate_limit_per_hour": 1000,
                "is_active": True,
                "last_used_at": "2025-01-10T14:30:00Z",
                "usage_count": 1523,
                "expires_at": "2025-12-31T23:59:59Z",
                "created_at": "2025-01-10T12:00:00Z"
            }
        }


class APIKeyListResponse(BaseModel):
    """Response model for listing API keys."""
    keys: List[APIKeyListItem] = Field(..., description="List of API keys")
    total: int = Field(..., description="Total number of keys")

    class Config:
        json_schema_extra = {
            "example": {
                "keys": [
                    {
                        "key_id": "550e8400-e29b-41d4-a716-446655440000",
                        "key_name": "Production API Key",
                        "key_prefix": "emp_12345678",
                        "role_id": "660e8400-e29b-41d4-a716-446655440000",
                        "scopes": ["documents:read", "documents:write"],
                        "rate_limit_per_hour": 1000,
                        "is_active": True,
                        "last_used_at": "2025-01-10T14:30:00Z",
                        "usage_count": 1523,
                        "expires_at": "2025-12-31T23:59:59Z",
                        "created_at": "2025-01-10T12:00:00Z"
                    }
                ],
                "total": 1
            }
        }


class RoleInfo(BaseModel):
    """Response model for role information."""
    id: str = Field(..., description="Role UUID")
    role_name: str = Field(..., description="Role name (admin, editor, viewer, guest)")
    description: Optional[str] = Field(None, description="Role description")
    permissions: Dict[str, Any] = Field(default_factory=dict, description="Permission configuration")
    can_read_documents: bool = Field(..., description="Can read documents")
    can_write_documents: bool = Field(..., description="Can write documents")
    can_delete_documents: bool = Field(..., description="Can delete documents")
    can_manage_users: bool = Field(..., description="Can manage users")
    can_manage_api_keys: bool = Field(..., description="Can manage API keys")
    can_view_audit_logs: bool = Field(..., description="Can view audit logs")
    is_active: bool = Field(..., description="Whether the role is active")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "660e8400-e29b-41d4-a716-446655440000",
                "role_name": "editor",
                "description": "Can read and write documents",
                "permissions": {
                    "documents": ["read", "write"],
                    "embeddings": ["read", "write"]
                },
                "can_read_documents": True,
                "can_write_documents": True,
                "can_delete_documents": False,
                "can_manage_users": False,
                "can_manage_api_keys": False,
                "can_view_audit_logs": False,
                "is_active": True,
                "created_at": "2025-01-01T00:00:00Z"
            }
        }


class UserRoleInfo(BaseModel):
    """Response model for user role assignment."""
    id: str = Field(..., description="User role assignment UUID")
    user_id: str = Field(..., description="User ID")
    role: RoleInfo = Field(..., description="Role information")
    granted_by: Optional[str] = Field(None, description="User ID who granted this role")
    granted_at: datetime = Field(..., description="When the role was granted")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration datetime")
    is_active: bool = Field(..., description="Whether the assignment is active")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440000",
                "user_id": "user_2abc123xyz",
                "role": {
                    "id": "660e8400-e29b-41d4-a716-446655440000",
                    "role_name": "editor",
                    "description": "Can read and write documents",
                    "permissions": {
                        "documents": ["read", "write"]
                    },
                    "can_read_documents": True,
                    "can_write_documents": True,
                    "can_delete_documents": False,
                    "can_manage_users": False,
                    "can_manage_api_keys": False,
                    "can_view_audit_logs": False,
                    "is_active": True,
                    "created_at": "2025-01-01T00:00:00Z"
                },
                "granted_by": "user_admin123",
                "granted_at": "2025-01-10T12:00:00Z",
                "expires_at": "2025-12-31T23:59:59Z",
                "is_active": True
            }
        }


class AuditLogEntry(BaseModel):
    """Response model for audit log entries."""
    id: str = Field(..., description="Audit log entry UUID")
    event_type: str = Field(..., description="Type of event (api_key_created, role_assigned, etc.)")
    actor_user_id: Optional[str] = Field(None, description="User ID who performed the action")
    target_user_id: Optional[str] = Field(None, description="User ID who was affected by the action")
    target_resource_type: Optional[str] = Field(None, description="Type of resource affected (api_key, user_role, etc.)")
    target_resource_id: Optional[str] = Field(None, description="UUID of the affected resource")
    action: str = Field(..., description="Action performed (create, revoke, assign, etc.)")
    result: str = Field(..., description="Result of the action (success, failure, denied)")
    ip_address: Optional[str] = Field(None, description="IP address of the actor")
    user_agent: Optional[str] = Field(None, description="User agent of the actor")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional event metadata")
    error_message: Optional[str] = Field(None, description="Error message if result was failure")
    created_at: datetime = Field(..., description="When the event occurred")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "880e8400-e29b-41d4-a716-446655440000",
                "event_type": "api_key_created",
                "actor_user_id": "user_2abc123xyz",
                "target_user_id": None,
                "target_resource_type": "api_key",
                "target_resource_id": "550e8400-e29b-41d4-a716-446655440000",
                "action": "create",
                "result": "success",
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "metadata": {
                    "key_name": "Production API Key",
                    "role_id": "660e8400-e29b-41d4-a716-446655440000"
                },
                "error_message": None,
                "created_at": "2025-01-10T12:00:00Z"
            }
        }
