"""
Session Management Service - Task 28

Manages user sessions with Redis (active session tracking) and Supabase (persistence).
Supports multiple concurrent sessions, session timeout, export, and deletion.
"""

import logging
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4

try:
    from app.core.database import get_supabase, get_redis
except ImportError:
    get_supabase = None
    get_redis = None

logger = logging.getLogger(__name__)


class Session:
    """Represents a user session"""

    def __init__(
        self,
        id: str = None,
        user_id: str = None,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        first_message_at: Optional[datetime] = None,
        last_message_at: Optional[datetime] = None,
        message_count: int = 0,
        total_tokens: int = 0,
        session_metadata: Optional[Dict[str, Any]] = None,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id or str(uuid4())
        self.user_id = user_id
        self.title = title
        self.summary = summary
        self.first_message_at = first_message_at
        self.last_message_at = last_message_at
        self.message_count = message_count
        self.total_tokens = total_tokens
        self.session_metadata = session_metadata or {}
        self.is_active = is_active
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for storage"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "summary": self.summary,
            "first_message_at": self.first_message_at.isoformat() if self.first_message_at else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
            "session_metadata": self.session_metadata,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create session from dictionary"""
        return cls(
            id=data.get("id"),
            user_id=data.get("user_id"),
            title=data.get("title"),
            summary=data.get("summary"),
            first_message_at=datetime.fromisoformat(data["first_message_at"]) if data.get("first_message_at") else None,
            last_message_at=datetime.fromisoformat(data["last_message_at"]) if data.get("last_message_at") else None,
            message_count=data.get("message_count", 0),
            total_tokens=data.get("total_tokens", 0),
            session_metadata=data.get("session_metadata", {}),
            is_active=data.get("is_active", True),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None
        )


class SessionManagementService:
    """
    Manages user sessions with Redis caching and Supabase persistence.

    Features:
    - Multiple concurrent sessions per user
    - Redis-backed active session tracking with TTL
    - Supabase persistence for long-term storage
    - Session timeout and automatic cleanup
    - Session export (JSON format)
    - Session deletion with cascade
    - Session activity tracking
    """

    def __init__(
        self,
        supabase_client=None,
        redis_client=None,
        session_timeout_minutes: int = 60,  # 1 hour default
        max_sessions_per_user: int = 10
    ):
        """
        Initialize the session management service.

        Args:
            supabase_client: Supabase client for persistence
            redis_client: Redis client for active session tracking
            session_timeout_minutes: Minutes before inactive session expires
            max_sessions_per_user: Maximum concurrent sessions per user
        """
        if supabase_client:
            self.supabase = supabase_client
        elif get_supabase:
            self.supabase = get_supabase()
        else:
            self.supabase = None

        if redis_client:
            self.redis = redis_client
        elif get_redis:
            self.redis = get_redis()
        else:
            self.redis = None

        self.session_timeout_minutes = session_timeout_minutes
        self.max_sessions_per_user = max_sessions_per_user
        self.logger = logger

    # ==================== Session Creation & Retrieval ====================

    async def create_session(
        self,
        user_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Session]:
        """
        Create a new session for a user.

        Args:
            user_id: User identifier
            title: Optional session title
            metadata: Optional session metadata

        Returns:
            Created Session or None if failed
        """
        try:
            # Check if user has reached max sessions
            active_sessions = await self.get_user_sessions(user_id, active_only=True)
            if len(active_sessions) >= self.max_sessions_per_user:
                self.logger.warning(f"User {user_id} has reached max sessions ({self.max_sessions_per_user})")
                # Deactivate oldest session
                oldest = min(active_sessions, key=lambda s: s.last_message_at or s.created_at)
                await self.deactivate_session(oldest.id, user_id)

            # Create session object
            session = Session(
                user_id=user_id,
                title=title or f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                session_metadata=metadata or {},
                is_active=True
            )

            # Persist to Supabase
            if self.supabase:
                response = self.supabase.table("chat_sessions").insert(session.to_dict()).execute()
                if not response.data:
                    self.logger.error("Failed to create session in Supabase")
                    return None

            # Cache in Redis with TTL
            if self.redis:
                await self._cache_session(session)

            self.logger.info(f"Created session {session.id} for user {user_id}")
            return session

        except Exception as e:
            self.logger.error(f"Error creating session: {e}")
            return None

    async def get_session(
        self,
        session_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Session]:
        """
        Retrieve a session by ID.

        Args:
            session_id: Session identifier
            user_id: Optional user ID for validation

        Returns:
            Session or None if not found
        """
        try:
            # Try Redis cache first
            if self.redis:
                cached = await self._get_cached_session(session_id)
                if cached:
                    # Validate user_id if provided
                    if user_id and cached.user_id != user_id:
                        return None
                    return cached

            # Fallback to Supabase
            if self.supabase:
                query = self.supabase.table("chat_sessions").select("*").eq("id", session_id)

                if user_id:
                    query = query.eq("user_id", user_id)

                response = query.single().execute()

                if response.data:
                    session = Session.from_dict(response.data)
                    # Cache for next time
                    if self.redis:
                        await self._cache_session(session)
                    return session

            return None

        except Exception as e:
            self.logger.error(f"Error retrieving session: {e}")
            return None

    async def get_user_sessions(
        self,
        user_id: str,
        active_only: bool = False,
        limit: int = 50
    ) -> List[Session]:
        """
        Get all sessions for a user.

        Args:
            user_id: User identifier
            active_only: Only return active sessions
            limit: Maximum number of sessions to return

        Returns:
            List of Session objects
        """
        try:
            if not self.supabase:
                return []

            query = self.supabase.table("chat_sessions") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("last_message_at", desc=True) \
                .limit(limit)

            if active_only:
                query = query.eq("is_active", True)

            response = query.execute()

            if response.data:
                return [Session.from_dict(row) for row in response.data]

            return []

        except Exception as e:
            self.logger.error(f"Error retrieving user sessions: {e}")
            return []

    async def get_active_sessions(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[Session]:
        """
        Get all active sessions for a user (convenience method).

        Args:
            user_id: User identifier
            limit: Maximum number of sessions to return

        Returns:
            List of active Session objects
        """
        return await self.get_user_sessions(
            user_id=user_id,
            active_only=True,
            limit=limit
        )

    # ==================== Session Updates ====================

    async def update_session_activity(
        self,
        session_id: str,
        user_id: str,
        message_count_delta: int = 1,
        tokens_delta: int = 0
    ) -> Optional[Session]:
        """
        Update session activity (message count, tokens, last activity time).

        Args:
            session_id: Session identifier
            user_id: User identifier
            message_count_delta: Number of messages to add
            tokens_delta: Number of tokens to add

        Returns:
            Updated Session or None if failed
        """
        try:
            now = datetime.now()

            # Get current session
            session = await self.get_session(session_id, user_id)
            if not session:
                return None

            # Update fields
            session.last_message_at = now
            session.message_count += message_count_delta
            session.total_tokens += tokens_delta
            session.updated_at = now

            if session.first_message_at is None:
                session.first_message_at = now

            # Update in Supabase
            if self.supabase:
                self.supabase.table("chat_sessions") \
                    .update(session.to_dict()) \
                    .eq("id", session_id) \
                    .eq("user_id", user_id) \
                    .execute()

            # Update cache
            if self.redis:
                await self._cache_session(session)

            return session

        except Exception as e:
            self.logger.error(f"Error updating session activity: {e}")
            return None

    async def update_session_metadata(
        self,
        session_id: str,
        user_id: str,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        metadata_updates: Optional[Dict[str, Any]] = None
    ) -> Optional[Session]:
        """
        Update session metadata.

        Args:
            session_id: Session identifier
            user_id: User identifier
            title: New title (optional)
            summary: New summary (optional)
            metadata_updates: Metadata fields to update (optional)

        Returns:
            Updated Session or None if failed
        """
        try:
            session = await self.get_session(session_id, user_id)
            if not session:
                return None

            # Update fields
            if title is not None:
                session.title = title
            if summary is not None:
                session.summary = summary
            if metadata_updates:
                session.session_metadata.update(metadata_updates)
            session.updated_at = datetime.now()

            # Update in Supabase
            if self.supabase:
                self.supabase.table("chat_sessions") \
                    .update(session.to_dict()) \
                    .eq("id", session_id) \
                    .eq("user_id", user_id) \
                    .execute()

            # Update cache
            if self.redis:
                await self._cache_session(session)

            return session

        except Exception as e:
            self.logger.error(f"Error updating session metadata: {e}")
            return None

    # ==================== Session Lifecycle ====================

    async def deactivate_session(
        self,
        session_id: str,
        user_id: str
    ) -> bool:
        """
        Deactivate a session (soft delete).

        Args:
            session_id: Session identifier
            user_id: User identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.supabase:
                self.supabase.table("chat_sessions") \
                    .update({"is_active": False, "updated_at": datetime.now().isoformat()}) \
                    .eq("id", session_id) \
                    .eq("user_id", user_id) \
                    .execute()

            # Remove from Redis cache
            if self.redis:
                await self._uncache_session(session_id)

            self.logger.info(f"Deactivated session {session_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error deactivating session: {e}")
            return False

    async def delete_session(
        self,
        session_id: str,
        user_id: str,
        cascade: bool = True
    ) -> bool:
        """
        Permanently delete a session.

        Args:
            session_id: Session identifier
            user_id: User identifier
            cascade: Delete related messages and feedback (default True)

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.supabase:
                # Cascade is handled by ON DELETE CASCADE in schema
                self.supabase.table("chat_sessions") \
                    .delete() \
                    .eq("id", session_id) \
                    .eq("user_id", user_id) \
                    .execute()

            # Remove from Redis cache
            if self.redis:
                await self._uncache_session(session_id)

            self.logger.info(f"Deleted session {session_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error deleting session: {e}")
            return False

    async def export_session(
        self,
        session_id: str,
        user_id: str,
        include_messages: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Export session data as JSON.

        Args:
            session_id: Session identifier
            user_id: User identifier
            include_messages: Include chat messages in export

        Returns:
            Dictionary with session data or None if failed
        """
        try:
            session = await self.get_session(session_id, user_id)
            if not session:
                return None

            export_data = session.to_dict()

            if include_messages and self.supabase:
                # Get messages
                messages_response = self.supabase.table("chat_messages") \
                    .select("*") \
                    .eq("session_id", session_id) \
                    .order("message_index") \
                    .execute()

                if messages_response.data:
                    export_data["messages"] = messages_response.data

            return export_data

        except Exception as e:
            self.logger.error(f"Error exporting session: {e}")
            return None

    # ==================== Session Cleanup ====================

    async def cleanup_expired_sessions(
        self,
        user_id: Optional[str] = None
    ) -> int:
        """
        Clean up sessions that have expired (no activity for session_timeout_minutes).

        Args:
            user_id: Optional user ID to limit cleanup to specific user

        Returns:
            Number of sessions deactivated
        """
        try:
            if not self.supabase:
                return 0

            cutoff_time = datetime.now() - timedelta(minutes=self.session_timeout_minutes)

            query = self.supabase.table("chat_sessions") \
                .update({"is_active": False, "updated_at": datetime.now().isoformat()}) \
                .lt("last_message_at", cutoff_time.isoformat()) \
                .eq("is_active", True)

            if user_id:
                query = query.eq("user_id", user_id)

            response = query.execute()

            count = len(response.data) if response.data else 0
            self.logger.info(f"Cleaned up {count} expired sessions")
            return count

        except Exception as e:
            self.logger.error(f"Error cleaning up expired sessions: {e}")
            return 0

    # ==================== Redis Caching ====================

    async def _cache_session(self, session: Session):
        """Cache session in Redis with TTL"""
        if not self.redis:
            return

        try:
            key = f"session:{session.id}"
            ttl_seconds = self.session_timeout_minutes * 60
            self.redis.setex(
                key,
                ttl_seconds,
                json.dumps(session.to_dict())
            )
        except Exception as e:
            self.logger.warning(f"Failed to cache session in Redis: {e}")

    async def _get_cached_session(self, session_id: str) -> Optional[Session]:
        """Get session from Redis cache"""
        if not self.redis:
            return None

        try:
            key = f"session:{session_id}"
            cached = self.redis.get(key)
            if cached:
                data = json.loads(cached)
                return Session.from_dict(data)
            return None
        except Exception as e:
            self.logger.warning(f"Failed to get cached session from Redis: {e}")
            return None

    async def _uncache_session(self, session_id: str):
        """Remove session from Redis cache"""
        if not self.redis:
            return

        try:
            key = f"session:{session_id}"
            self.redis.delete(key)
        except Exception as e:
            self.logger.warning(f"Failed to uncache session from Redis: {e}")

    # ==================== Session Statistics ====================

    async def get_session_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Get statistics about user's sessions.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with statistics
        """
        try:
            if not self.supabase:
                return {}

            # Get all sessions
            all_sessions = await self.get_user_sessions(user_id, active_only=False, limit=1000)
            active_sessions = [s for s in all_sessions if s.is_active]

            stats = {
                "total_sessions": len(all_sessions),
                "active_sessions": len(active_sessions),
                "total_messages": sum(s.message_count for s in all_sessions),
                "total_tokens": sum(s.total_tokens for s in all_sessions),
                "average_messages_per_session": sum(s.message_count for s in all_sessions) / len(all_sessions) if all_sessions else 0,
                "oldest_session_date": min(s.created_at for s in all_sessions).isoformat() if all_sessions else None,
                "newest_session_date": max(s.created_at for s in all_sessions).isoformat() if all_sessions else None
            }

            return stats

        except Exception as e:
            self.logger.error(f"Error getting session statistics: {e}")
            return {}
