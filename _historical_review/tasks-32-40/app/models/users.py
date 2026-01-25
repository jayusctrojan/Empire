"""
Pydantic models for user management
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    GUEST = "guest"


class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


# ============================================================================
# Request Models
# ============================================================================

class CreateUserRequest(BaseModel):
    """Request to create a new user"""
    username: str = Field(..., min_length=3, max_length=100, description="Username (unique)")
    email: EmailStr = Field(..., description="Email address (unique)")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name")
    role: UserRole = Field(default=UserRole.VIEWER, description="User role")


class UpdateUserRequest(BaseModel):
    """Request to update user information"""
    email: Optional[EmailStr] = Field(None, description="New email address")
    full_name: Optional[str] = Field(None, max_length=255, description="New full name")
    role: Optional[UserRole] = Field(None, description="New role")


class ChangePasswordRequest(BaseModel):
    """Request to change own password"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")


class AdminResetPasswordRequest(BaseModel):
    """Request for admin to reset user password"""
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")
    notify_user: bool = Field(default=True, description="Send notification email to user")


class SuspendUserRequest(BaseModel):
    """Request to suspend user account"""
    reason: str = Field(..., min_length=10, description="Reason for suspension")
    notify_user: bool = Field(default=True, description="Send notification email to user")


class ActivateUserRequest(BaseModel):
    """Request to activate/reactivate user account"""
    notify_user: bool = Field(default=True, description="Send notification email to user")


# ============================================================================
# Response Models
# ============================================================================

class UserResponse(BaseModel):
    """User information response"""
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    login_count: int = 0
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    """Response for listing users"""
    users: List[UserResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class CreateUserResponse(BaseModel):
    """Response after creating a user"""
    user_id: str
    username: str
    email: str
    message: str = "User created successfully"


class PasswordResetResponse(BaseModel):
    """Response after password reset"""
    user_id: str
    message: str = "Password reset successfully"


class UserSuspensionResponse(BaseModel):
    """Response after suspending/activating user"""
    user_id: str
    is_active: bool
    message: str


class ActivityLogEntry(BaseModel):
    """Activity log entry for user management actions"""
    id: str
    admin_user_id: Optional[str] = None
    action_type: str
    resource_type: str
    resource_id: Optional[str] = None
    action_details: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None
    created_at: datetime


class ActivityLogListResponse(BaseModel):
    """Response for listing activity logs"""
    logs: List[ActivityLogEntry]
    total: int
    page: int
    page_size: int
    has_more: bool


class UserDataExport(BaseModel):
    """Complete user data export for GDPR compliance"""
    user_profile: Dict[str, Any]
    activity_logs: List[Dict[str, Any]]
    sessions: List[Dict[str, Any]]
    api_keys: List[Dict[str, Any]]  # Without sensitive key material
    roles: List[Dict[str, Any]]
    export_timestamp: datetime
    export_requested_by: str


class GDPRDeleteResponse(BaseModel):
    """Response after GDPR-compliant user deletion"""
    user_id: str
    deleted: bool
    items_deleted: Dict[str, int]  # Count of deleted items by type
    anonymized: Dict[str, int]  # Count of anonymized items by type
    message: str
