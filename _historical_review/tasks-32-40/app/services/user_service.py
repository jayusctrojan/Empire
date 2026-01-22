"""
User Management Service - Task 33.1
Handles user CRUD operations, password management, and account suspension
"""

import uuid
import bcrypt
from datetime import datetime
from typing import Dict, Any, List, Optional
import structlog

from app.core.supabase_client import get_supabase_client

logger = structlog.get_logger(__name__)


class UserService:
    """Service for managing user accounts"""

    def __init__(self):
        self.supabase = get_supabase_client()

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role: str = "viewer",
        created_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new admin user

        Args:
            username: Unique username
            email: Unique email address
            password: Plain text password (will be hashed)
            full_name: Optional full name
            role: User role (admin, editor, viewer, guest)
            created_by: User ID of admin creating this user
            ip_address: IP address for audit log
            user_agent: User agent for audit log

        Returns:
            Dict with user_id and username

        Raises:
            ValueError: If username or email already exists
        """
        try:
            # Check if username exists
            existing_username = self.supabase.table("admin_users").select("id").eq(
                "username", username
            ).execute()

            if existing_username.data:
                raise ValueError(f"Username '{username}' already exists")

            # Check if email exists
            existing_email = self.supabase.table("admin_users").select("id").eq(
                "email", email
            ).execute()

            if existing_email.data:
                raise ValueError(f"Email '{email}' already exists")

            # Hash password with bcrypt
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            # Generate user ID
            user_id = str(uuid.uuid4())

            # Insert user
            user_data = {
                "id": user_id,
                "username": username,
                "email": email,
                "password_hash": password_hash,
                "full_name": full_name,
                "role": role,
                "is_active": True,
                "login_count": 0,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            result = self.supabase.table("admin_users").insert(user_data).execute()

            if not result.data:
                raise Exception("Failed to insert user record")

            # Log activity
            await self._log_activity(
                admin_user_id=created_by,
                action_type="user_created",
                resource_type="user",
                resource_id=user_id,
                action_details={
                    "username": username,
                    "email": email,
                    "role": role
                },
                ip_address=ip_address,
                user_agent=user_agent
            )

            logger.info(
                "User created successfully",
                user_id=user_id,
                username=username,
                created_by=created_by
            )

            return {
                "user_id": user_id,
                "username": username,
                "email": email
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error("Failed to create user", error=str(e), username=username)
            raise

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by ID

        Args:
            user_id: User ID

        Returns:
            User data dict or None if not found
        """
        try:
            result = self.supabase.table("admin_users").select("*").eq("id", user_id).execute()

            if not result.data:
                return None

            user = result.data[0]

            # Remove password_hash from response
            user.pop("password_hash", None)

            return user

        except Exception as e:
            logger.error("Failed to get user", error=str(e), user_id=user_id)
            raise

    async def list_users(
        self,
        limit: int = 50,
        offset: int = 0,
        role_filter: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        List all users with pagination and filtering

        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip
            role_filter: Optional role to filter by
            is_active: Optional active status filter

        Returns:
            List of user dicts
        """
        try:
            query = self.supabase.table("admin_users").select("*")

            if role_filter:
                query = query.eq("role", role_filter)

            if is_active is not None:
                query = query.eq("is_active", is_active)

            result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

            users = result.data if result.data else []

            # Remove password_hash from all users
            for user in users:
                user.pop("password_hash", None)

            return users

        except Exception as e:
            logger.error("Failed to list users", error=str(e))
            raise

    async def update_user(
        self,
        user_id: str,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        role: Optional[str] = None,
        updated_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update user information

        Args:
            user_id: User ID to update
            email: New email (optional)
            full_name: New full name (optional)
            role: New role (optional)
            updated_by: User ID of admin updating
            ip_address: IP address for audit log
            user_agent: User agent for audit log

        Returns:
            Updated user data

        Raises:
            ValueError: If user not found or email already exists
        """
        try:
            # Check if user exists
            existing = self.supabase.table("admin_users").select("*").eq("id", user_id).execute()

            if not existing.data:
                raise ValueError(f"User {user_id} not found")

            update_data = {"updated_at": datetime.utcnow().isoformat()}

            # Check if new email already exists (if changing email)
            if email and email != existing.data[0]["email"]:
                email_check = self.supabase.table("admin_users").select("id").eq("email", email).execute()
                if email_check.data:
                    raise ValueError(f"Email '{email}' already exists")
                update_data["email"] = email

            if full_name is not None:
                update_data["full_name"] = full_name

            if role is not None:
                update_data["role"] = role

            # Update user
            result = self.supabase.table("admin_users").update(update_data).eq("id", user_id).execute()

            if not result.data:
                raise Exception("Failed to update user")

            # Log activity
            await self._log_activity(
                admin_user_id=updated_by,
                action_type="user_updated",
                resource_type="user",
                resource_id=user_id,
                action_details={
                    "changes": update_data
                },
                ip_address=ip_address,
                user_agent=user_agent
            )

            logger.info("User updated successfully", user_id=user_id, updated_by=updated_by)

            # Remove password_hash from response
            user = result.data[0]
            user.pop("password_hash", None)

            return user

        except ValueError:
            raise
        except Exception as e:
            logger.error("Failed to update user", error=str(e), user_id=user_id)
            raise

    async def delete_user(
        self,
        user_id: str,
        deleted_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Delete a user (hard delete)

        Args:
            user_id: User ID to delete
            deleted_by: User ID of admin deleting
            ip_address: IP address for audit log
            user_agent: User agent for audit log

        Returns:
            True if deleted successfully

        Raises:
            ValueError: If user not found
        """
        try:
            # Check if user exists
            existing = self.supabase.table("admin_users").select("username").eq("id", user_id).execute()

            if not existing.data:
                raise ValueError(f"User {user_id} not found")

            username = existing.data[0]["username"]

            # Delete user (cascades to admin_sessions via foreign key)
            self.supabase.table("admin_users").delete().eq("id", user_id).execute()

            # Log activity
            await self._log_activity(
                admin_user_id=deleted_by,
                action_type="user_deleted",
                resource_type="user",
                resource_id=user_id,
                action_details={
                    "username": username
                },
                ip_address=ip_address,
                user_agent=user_agent
            )

            logger.info("User deleted successfully", user_id=user_id, deleted_by=deleted_by)

            return True

        except ValueError:
            raise
        except Exception as e:
            logger.error("Failed to delete user", error=str(e), user_id=user_id)
            raise

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Change user's own password

        Args:
            user_id: User ID
            current_password: Current password for verification
            new_password: New password
            ip_address: IP address for audit log
            user_agent: User agent for audit log

        Returns:
            True if password changed successfully

        Raises:
            ValueError: If current password is incorrect
        """
        try:
            # Get user
            result = self.supabase.table("admin_users").select("password_hash").eq("id", user_id).execute()

            if not result.data:
                raise ValueError(f"User {user_id} not found")

            stored_hash = result.data[0]["password_hash"]

            # Verify current password
            if not bcrypt.checkpw(current_password.encode('utf-8'), stored_hash.encode('utf-8')):
                raise ValueError("Current password is incorrect")

            # Hash new password
            new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            # Update password
            self.supabase.table("admin_users").update({
                "password_hash": new_password_hash,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", user_id).execute()

            # Log activity
            await self._log_activity(
                admin_user_id=user_id,
                action_type="password_changed",
                resource_type="user",
                resource_id=user_id,
                action_details={"self_service": True},
                ip_address=ip_address,
                user_agent=user_agent
            )

            logger.info("Password changed successfully", user_id=user_id)

            return True

        except ValueError:
            raise
        except Exception as e:
            logger.error("Failed to change password", error=str(e), user_id=user_id)
            raise

    async def admin_reset_password(
        self,
        user_id: str,
        new_password: str,
        admin_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Admin-initiated password reset

        Args:
            user_id: User ID whose password to reset
            new_password: New password
            admin_id: Admin user ID performing the reset
            ip_address: IP address for audit log
            user_agent: User agent for audit log

        Returns:
            True if password reset successfully

        Raises:
            ValueError: If user not found
        """
        try:
            # Check if user exists
            existing = self.supabase.table("admin_users").select("username").eq("id", user_id).execute()

            if not existing.data:
                raise ValueError(f"User {user_id} not found")

            # Hash new password
            new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            # Update password
            self.supabase.table("admin_users").update({
                "password_hash": new_password_hash,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", user_id).execute()

            # Log activity
            await self._log_activity(
                admin_user_id=admin_id,
                action_type="password_reset",
                resource_type="user",
                resource_id=user_id,
                action_details={
                    "admin_initiated": True,
                    "reset_by": admin_id
                },
                ip_address=ip_address,
                user_agent=user_agent
            )

            logger.info("Password reset by admin", user_id=user_id, admin_id=admin_id)

            return True

        except ValueError:
            raise
        except Exception as e:
            logger.error("Failed to reset password", error=str(e), user_id=user_id)
            raise

    async def suspend_user(
        self,
        user_id: str,
        reason: str,
        suspended_by: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Suspend user account

        Args:
            user_id: User ID to suspend
            reason: Reason for suspension
            suspended_by: Admin user ID performing suspension
            ip_address: IP address for audit log
            user_agent: User agent for audit log

        Returns:
            True if suspended successfully

        Raises:
            ValueError: If user not found
        """
        try:
            # Check if user exists
            existing = self.supabase.table("admin_users").select("username").eq("id", user_id).execute()

            if not existing.data:
                raise ValueError(f"User {user_id} not found")

            # Suspend user
            self.supabase.table("admin_users").update({
                "is_active": False,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", user_id).execute()

            # Invalidate all user sessions
            self.supabase.table("admin_sessions").update({
                "is_active": False
            }).eq("admin_user_id", user_id).execute()

            # Log activity
            await self._log_activity(
                admin_user_id=suspended_by,
                action_type="user_suspended",
                resource_type="user",
                resource_id=user_id,
                action_details={
                    "reason": reason,
                    "suspended_by": suspended_by
                },
                ip_address=ip_address,
                user_agent=user_agent
            )

            logger.info("User suspended", user_id=user_id, reason=reason, suspended_by=suspended_by)

            return True

        except ValueError:
            raise
        except Exception as e:
            logger.error("Failed to suspend user", error=str(e), user_id=user_id)
            raise

    async def activate_user(
        self,
        user_id: str,
        activated_by: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Activate/reactivate user account

        Args:
            user_id: User ID to activate
            activated_by: Admin user ID performing activation
            ip_address: IP address for audit log
            user_agent: User agent for audit log

        Returns:
            True if activated successfully

        Raises:
            ValueError: If user not found
        """
        try:
            # Check if user exists
            existing = self.supabase.table("admin_users").select("username").eq("id", user_id).execute()

            if not existing.data:
                raise ValueError(f"User {user_id} not found")

            # Activate user
            self.supabase.table("admin_users").update({
                "is_active": True,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", user_id).execute()

            # Log activity
            await self._log_activity(
                admin_user_id=activated_by,
                action_type="user_activated",
                resource_type="user",
                resource_id=user_id,
                action_details={
                    "activated_by": activated_by
                },
                ip_address=ip_address,
                user_agent=user_agent
            )

            logger.info("User activated", user_id=user_id, activated_by=activated_by)

            return True

        except ValueError:
            raise
        except Exception as e:
            logger.error("Failed to activate user", error=str(e), user_id=user_id)
            raise

    async def export_user_data(
        self,
        user_id: str,
        exported_by: str
    ) -> Dict[str, Any]:
        """
        Export all user data for GDPR compliance

        Args:
            user_id: User ID to export data for
            exported_by: Admin user ID requesting the export

        Returns:
            Dict containing all user data (profile, logs, sessions, keys, roles)

        Raises:
            ValueError: If user not found
        """
        try:
            # Get user profile
            user = await self.get_user(user_id=user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")

            # Get activity logs (both as actor and subject)
            activity_logs = await self.get_activity_logs(
                user_id=user_id,
                limit=10000  # Get all logs
            )

            # Get sessions
            sessions_result = self.supabase.table("admin_sessions").select(
                "id, created_at, last_accessed_at, expires_at, ip_address, user_agent, is_active"
            ).eq("admin_user_id", user_id).execute()
            sessions = sessions_result.data if sessions_result.data else []

            # Get API keys (without sensitive key hashes)
            keys_result = self.supabase.table("api_keys").select(
                "id, key_name, key_prefix, role_id, created_at, expires_at, last_used_at, is_active"
            ).eq("user_id", user_id).execute()
            api_keys = keys_result.data if keys_result.data else []

            # Get role assignments
            roles_result = self.supabase.table("user_roles").select(
                "id, role_id, granted_at, granted_by, expires_at, is_active"
            ).eq("user_id", user_id).execute()
            roles = roles_result.data if roles_result.data else []

            export_data = {
                "user_profile": user,
                "activity_logs": activity_logs,
                "sessions": sessions,
                "api_keys": api_keys,
                "roles": roles,
                "export_timestamp": datetime.utcnow().isoformat(),
                "export_requested_by": exported_by
            }

            # Log the export action
            await self._log_activity(
                admin_user_id=exported_by,
                action_type="user_data_exported",
                resource_type="user",
                resource_id=user_id,
                action_details={"export_timestamp": export_data["export_timestamp"]}
            )

            logger.info("User data exported", user_id=user_id, exported_by=exported_by)

            return export_data

        except ValueError:
            raise
        except Exception as e:
            logger.error("Failed to export user data", error=str(e), user_id=user_id)
            raise

    async def gdpr_delete_user(
        self,
        user_id: str,
        deleted_by: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        GDPR-compliant user deletion with anonymization of audit logs

        Args:
            user_id: User ID to delete
            deleted_by: Admin user ID performing the deletion
            ip_address: IP address for audit log
            user_agent: User agent for audit log

        Returns:
            Dict with deletion statistics

        Raises:
            ValueError: If user not found
        """
        try:
            # Check if user exists
            user = await self.get_user(user_id=user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")

            username = user["username"]
            items_deleted = {}
            items_anonymized = {}

            # 1. Revoke and delete all API keys
            keys_result = self.supabase.table("api_keys").select("id").eq("user_id", user_id).execute()
            if keys_result.data:
                self.supabase.table("api_keys").delete().eq("user_id", user_id).execute()
                items_deleted["api_keys"] = len(keys_result.data)

            # 2. Delete all sessions
            sessions_result = self.supabase.table("admin_sessions").select("id").eq("admin_user_id", user_id).execute()
            if sessions_result.data:
                self.supabase.table("admin_sessions").delete().eq("admin_user_id", user_id).execute()
                items_deleted["sessions"] = len(sessions_result.data)

            # 3. Delete role assignments
            roles_result = self.supabase.table("user_roles").select("id").eq("user_id", user_id).execute()
            if roles_result.data:
                self.supabase.table("user_roles").delete().eq("user_id", user_id).execute()
                items_deleted["user_roles"] = len(roles_result.data)

            # 4. Anonymize activity logs (preserve audit trail but remove PII)
            # Update logs where user was the actor
            actor_logs = self.supabase.table("admin_activity_log").select("id").eq("admin_user_id", user_id).execute()
            if actor_logs.data:
                self.supabase.table("admin_activity_log").update({
                    "admin_user_id": None,
                    "action_details": {"anonymized": True, "original_user": "deleted_user"}
                }).eq("admin_user_id", user_id).execute()
                items_anonymized["activity_logs_as_actor"] = len(actor_logs.data)

            # Update logs where user was the subject (in resource_id)
            subject_logs = self.supabase.table("admin_activity_log").select("id").eq(
                "resource_type", "user"
            ).eq("resource_id", user_id).execute()
            if subject_logs.data:
                self.supabase.table("admin_activity_log").update({
                    "resource_id": "deleted_user",
                    "action_details": {"anonymized": True}
                }).eq("resource_type", "user").eq("resource_id", user_id).execute()
                items_anonymized["activity_logs_as_subject"] = len(subject_logs.data)

            # 5. Delete the user profile
            self.supabase.table("admin_users").delete().eq("id", user_id).execute()
            items_deleted["user_profile"] = 1

            # Log the GDPR deletion (before we delete the user)
            await self._log_activity(
                admin_user_id=deleted_by,
                action_type="user_gdpr_deleted",
                resource_type="user",
                resource_id="deleted_user",
                action_details={
                    "original_username": username,
                    "items_deleted": items_deleted,
                    "items_anonymized": items_anonymized
                },
                ip_address=ip_address,
                user_agent=user_agent
            )

            logger.info(
                "User GDPR deleted",
                user_id=user_id,
                username=username,
                deleted_by=deleted_by,
                items_deleted=items_deleted,
                items_anonymized=items_anonymized
            )

            return {
                "user_id": user_id,
                "deleted": True,
                "items_deleted": items_deleted,
                "items_anonymized": items_anonymized
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error("Failed to GDPR delete user", error=str(e), user_id=user_id)
            raise

    async def get_activity_logs(
        self,
        user_id: Optional[str] = None,
        action_type: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get activity logs with optional filtering

        Args:
            user_id: Filter by user ID (either admin_user_id or resource_id for user actions)
            action_type: Filter by action type
            resource_type: Filter by resource type
            limit: Maximum number of logs to return
            offset: Number of logs to skip

        Returns:
            List of activity log entries
        """
        try:
            query = self.supabase.table("admin_activity_log").select("*")

            # Filter by user_id (either as actor or target)
            if user_id:
                query = query.or_(f"admin_user_id.eq.{user_id},resource_id.eq.{user_id}")

            # Filter by action type
            if action_type:
                query = query.eq("action_type", action_type)

            # Filter by resource type
            if resource_type:
                query = query.eq("resource_type", resource_type)

            # Order by most recent first
            result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error("Failed to get activity logs", error=str(e))
            raise

    async def _log_activity(
        self,
        admin_user_id: Optional[str],
        action_type: str,
        resource_type: str,
        resource_id: str,
        action_details: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        Log activity to admin_activity_log table

        Args:
            admin_user_id: Admin user ID performing the action
            action_type: Type of action
            resource_type: Type of resource
            resource_id: Resource ID
            action_details: Details of the action
            ip_address: IP address
            user_agent: User agent
        """
        try:
            log_data = {
                "admin_user_id": admin_user_id,
                "action_type": action_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action_details": action_details,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "status": "success",
                "created_at": datetime.utcnow().isoformat()
            }

            self.supabase.table("admin_activity_log").insert(log_data).execute()

        except Exception as e:
            logger.error("Failed to log activity", error=str(e), action_type=action_type)


def get_user_service() -> UserService:
    """Dependency injection for UserService"""
    return UserService()
