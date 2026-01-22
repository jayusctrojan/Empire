"""
Empire v7.3 - RBAC Service
Service for managing RBAC and API keys with secure storage in Supabase.

Features:
- Bcrypt hashing for API keys (never stores plaintext)
- Audit logging for all operations
- Role-based permission checks
- API key lifecycle management
"""

import secrets
import bcrypt
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4
import structlog

from app.core.supabase_client import get_supabase_client

logger = structlog.get_logger(__name__)


def normalize_iso_timestamp(timestamp_str: str) -> str:
    """
    Normalize ISO timestamp from Supabase to ensure Python datetime compatibility.

    Supabase may return timestamps with variable microsecond precision (e.g., 5 digits),
    but Python's datetime.fromisoformat() expects exactly 6 digits.

    Example:
        '2025-11-12T02:35:36.04126+00:00' -> '2025-11-12T02:35:36.041260+00:00'
    """
    # Replace 'Z' with '+00:00' for timezone
    normalized = timestamp_str.replace('Z', '+00:00')

    # Check if there are microseconds
    if '.' in normalized:
        # Split into datetime and timezone parts
        if '+' in normalized:
            datetime_part, tz_part = normalized.rsplit('+', 1)
            tz_str = '+' + tz_part
        elif normalized.count('-') > 2:  # Has negative timezone
            datetime_part, tz_part = normalized.rsplit('-', 1)
            tz_str = '-' + tz_part
        else:
            datetime_part = normalized
            tz_str = ''

        # Split datetime into date and fractional seconds
        if '.' in datetime_part:
            base_part, microseconds = datetime_part.split('.')
            # Pad or truncate microseconds to exactly 6 digits
            microseconds = microseconds.ljust(6, '0')[:6]
            normalized = f"{base_part}.{microseconds}{tz_str}"

    return normalized


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
            - key_prefix: First 12 chars (emp_xxxxxxxx)
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

        Args:
            user_id: User ID creating the key
            key_name: Human-readable name for the key
            role_id: UUID of role to assign
            scopes: Optional permission scopes
            rate_limit_per_hour: Rate limit (default 1000)
            expires_at: Optional expiration datetime
            ip_address: IP address of request
            user_agent: User agent of request

        Returns:
            dict: Contains full API key (SHOWN ONCE), key_id, prefix, etc.

        Raises:
            Exception: If database operation fails
        """
        # Generate secure key
        full_key, key_hash, key_prefix = self._generate_api_key()
        key_id = str(uuid4())

        # Insert into database (stores hash, not plaintext)
        try:
            result = self.supabase.table("api_keys").insert({
                "id": key_id,
                "key_name": key_name,
                "key_hash": key_hash,
                "key_prefix": key_prefix,
                "user_id": user_id,
                "role_id": role_id,
                "scopes": scopes or [],
                "rate_limit_per_hour": rate_limit_per_hour,
                "is_active": True,
                "usage_count": 0,
                "expires_at": expires_at.isoformat() if expires_at else None
            }).execute()

            if not result.data:
                raise Exception("Failed to create API key: No data returned")

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
                "api_key_created",
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

        except Exception as e:
            logger.error("api_key_creation_failed", error=str(e), user_id=user_id)
            raise

    async def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate an API key by checking bcrypt hash.

        Args:
            api_key: Full API key to validate (emp_xxx...)

        Returns:
            dict: Key metadata if valid, None if invalid
        """
        try:
            # Extract prefix for faster lookup
            key_prefix = api_key[:12]

            # Find keys with matching prefix
            result = self.supabase.table("api_keys").select("*").eq(
                "key_prefix", key_prefix
            ).eq("is_active", True).execute()

            if not result.data:
                logger.warning("api_key_not_found", key_prefix=key_prefix)
                return None

            # Check bcrypt hash
            for key_record in result.data:
                if bcrypt.checkpw(api_key.encode('utf-8'), key_record["key_hash"].encode('utf-8')):
                    # Check if key is expired
                    if key_record.get("expires_at"):
                        normalized_timestamp = normalize_iso_timestamp(key_record["expires_at"])
                        expires_at = datetime.fromisoformat(normalized_timestamp)
                        if datetime.now(expires_at.tzinfo) > expires_at:
                            logger.warning(
                                "api_key_expired",
                                key_id=key_record["id"],
                                expires_at=key_record["expires_at"]
                            )
                            return None

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

                    logger.debug("api_key_validated", key_id=key_id)
                    return key_record

            # No matching hash found
            logger.warning("api_key_invalid", key_prefix=key_prefix)
            return None

        except Exception as e:
            logger.error("api_key_validation_error", error=str(e))
            return None

    async def list_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """
        List all API keys for a user (prefix only, not full key).

        Args:
            user_id: User ID to list keys for

        Returns:
            List of API key metadata dictionaries
        """
        try:
            result = self.supabase.table("api_keys").select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).execute()

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

        except Exception as e:
            logger.error("list_api_keys_failed", error=str(e), user_id=user_id)
            raise

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

        Args:
            key_id: ID of key to rotate
            user_id: User ID performing the rotation
            new_key_name: Optional new name for rotated key
            expires_at: Optional new expiration
            ip_address: IP address of request
            user_agent: User agent of request

        Returns:
            dict: New API key details (with full key visible)

        Raises:
            ValueError: If key not found
            PermissionError: If user doesn't own the key
        """
        try:
            # Get old key details
            old_key = self.supabase.table("api_keys").select("*").eq("id", key_id).execute()

            if not old_key.data or len(old_key.data) == 0:
                raise ValueError(f"API key {key_id} not found")

            old_key_data = old_key.data[0]

            # Check ownership
            if old_key_data["user_id"] != user_id:
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
                key_name=new_key_name or f"{old_key_data['key_name']} (Rotated)",
                role_id=old_key_data["role_id"],
                scopes=old_key_data.get("scopes", []),
                rate_limit_per_hour=old_key_data["rate_limit_per_hour"],
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

            logger.info(
                "api_key_rotated",
                old_key_id=key_id,
                new_key_id=new_key["key_id"],
                user_id=user_id
            )

            return new_key

        except (ValueError, PermissionError):
            raise
        except Exception as e:
            logger.error("api_key_rotation_failed", error=str(e), key_id=key_id)
            raise

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

        Args:
            key_id: ID of key to revoke
            user_id: User ID performing the revocation
            revoke_reason: Reason for revocation
            ip_address: IP address of request
            user_agent: User agent of request

        Raises:
            ValueError: If key not found
            PermissionError: If user doesn't own the key
        """
        try:
            # Check ownership
            key_record = self.supabase.table("api_keys").select("user_id").eq("id", key_id).execute()

            if not key_record.data or len(key_record.data) == 0:
                raise ValueError(f"API key {key_id} not found")

            if key_record.data[0]["user_id"] != user_id:
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

            logger.info("api_key_revoked", key_id=key_id, user_id=user_id)

        except (ValueError, PermissionError):
            raise
        except Exception as e:
            logger.error("api_key_revocation_failed", error=str(e), key_id=key_id)
            raise

    # ==================== ROLE METHODS ====================

    async def list_roles(self) -> List[Dict[str, Any]]:
        """
        Get all available roles.

        Returns:
            List of role dictionaries
        """
        try:
            result = self.supabase.table("roles").select("*").eq("is_active", True).execute()
            return result.data if result.data else []

        except Exception as e:
            logger.error("list_roles_failed", error=str(e))
            raise

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

        Args:
            user_id: User ID to assign role to
            role_name: Name of role (admin, editor, viewer, guest)
            granted_by: User ID granting the role
            expires_at: Optional expiration datetime
            ip_address: IP address of request
            user_agent: User agent of request

        Returns:
            dict: User role assignment details

        Raises:
            ValueError: If role not found
        """
        try:
            # Get role ID
            role = self.supabase.table("roles").select("id").eq("role_name", role_name).execute()

            if not role.data or len(role.data) == 0:
                raise ValueError(f"Role {role_name} not found")

            role_id = role.data[0]["id"]
            user_role_id = str(uuid4())

            # Insert user_role
            result = self.supabase.table("user_roles").insert({
                "id": user_role_id,
                "user_id": user_id,
                "role_id": role_id,
                "granted_by": granted_by,
                "granted_at": datetime.utcnow().isoformat(),
                "expires_at": expires_at.isoformat() if expires_at else None,
                "is_active": True
            }).execute()

            if not result.data:
                raise Exception("Failed to assign role: No data returned")

            # Fetch the complete user_role with nested role info
            user_role = self.supabase.table("user_roles").select(
                "*, role:roles(*)"
            ).eq("id", user_role_id).execute()

            if not user_role.data:
                raise Exception("Failed to fetch user role with role details")

            # Log event
            await self._log_audit_event(
                event_type="role_assigned",
                actor_user_id=granted_by,
                target_user_id=user_id,
                target_resource_type="user_role",
                target_resource_id=user_role_id,
                action="assign",
                result="success",
                metadata={"role": role_name},
                ip_address=ip_address,
                user_agent=user_agent
            )

            logger.info(
                "role_assigned",
                user_id=user_id,
                role=role_name,
                granted_by=granted_by
            )

            return user_role.data[0]

        except ValueError:
            raise
        except Exception as e:
            logger.error("assign_role_failed", error=str(e), user_id=user_id)
            raise

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

        Args:
            user_id: User ID to revoke role from
            role_name: Name of role to revoke
            revoked_by: User ID revoking the role
            ip_address: IP address of request
            user_agent: User agent of request

        Raises:
            ValueError: If role not found
        """
        try:
            # Get role ID
            role = self.supabase.table("roles").select("id").eq("role_name", role_name).execute()

            if not role.data or len(role.data) == 0:
                raise ValueError(f"Role {role_name} not found")

            role_id = role.data[0]["id"]

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

            logger.info(
                "role_revoked",
                user_id=user_id,
                role=role_name,
                revoked_by=revoked_by
            )

        except ValueError:
            raise
        except Exception as e:
            logger.error("revoke_role_failed", error=str(e), user_id=user_id)
            raise

    async def get_user_roles(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all active roles for a user.

        Args:
            user_id: User ID to get roles for

        Returns:
            List of user role dictionaries with nested role info
        """
        try:
            result = self.supabase.table("user_roles").select(
                "*, role:roles(*)"
            ).eq("user_id", user_id).eq("is_active", True).execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error("get_user_roles_failed", error=str(e), user_id=user_id)
            raise

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

        Args:
            event_type: Type of event (api_key_created, role_assigned, etc.)
            action: Action performed (create, revoke, assign, etc.)
            result: Result of action (success, failure, denied)
            actor_user_id: User ID who performed the action
            target_user_id: User ID affected by the action
            target_resource_type: Type of resource affected
            target_resource_id: UUID of affected resource
            ip_address: IP address of request
            user_agent: User agent of request
            metadata: Additional metadata
            error_message: Error message if result was failure
        """
        try:
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
                "error_message": error_message,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

        except Exception as e:
            # Don't raise on audit log failures, just log them
            logger.error("audit_log_failed", error=str(e), event_type=event_type)

    async def get_audit_logs(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get audit logs with optional filters.

        Args:
            event_type: Filter by event type
            user_id: Filter by actor or target user ID
            limit: Maximum number of records to return
            offset: Offset for pagination

        Returns:
            List of audit log dictionaries
        """
        try:
            query = self.supabase.table("rbac_audit_logs").select("*")

            if event_type:
                query = query.eq("event_type", event_type)

            if user_id:
                query = query.or_(f"actor_user_id.eq.{user_id},target_user_id.eq.{user_id}")

            result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error("get_audit_logs_failed", error=str(e))
            raise


# Dependency injection for FastAPI
def get_rbac_service() -> RBACService:
    """
    FastAPI dependency for RBAC service.

    Returns:
        RBACService instance
    """
    return RBACService()
