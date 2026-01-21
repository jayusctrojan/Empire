"""
Empire v7.3 - Context Manager Service
Manages context window state with Redis caching for real-time updates.

Feature: Chat Context Window Management (011)
"""

import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4
import structlog

from app.core.database import get_supabase, get_redis
from app.core.token_counter import (
    TokenCounter,
    get_token_counter,
    count_message_tokens,
    update_context_usage_metric,
)
from app.models.context_models import (
    ContextWindowStatus,
    ContextMessage,
    ConversationContext,
    ContextStatus,
    MessageRole,
    AddMessageRequest,
    AddMessageResponse,
    ContextStatusResponse,
)

logger = structlog.get_logger(__name__)

# Redis key patterns
CONTEXT_STATE_KEY = "context:{conversation_id}:state"
COMPACTION_LOCK_KEY = "context:{conversation_id}:compaction_lock"
COMPACTION_PROGRESS_KEY = "context:{conversation_id}:compaction_progress"

# TTLs
CONTEXT_STATE_TTL = 86400  # 24 hours
COMPACTION_LOCK_TTL = 300  # 5 minutes
COMPACTION_PROGRESS_TTL = 600  # 10 minutes


class ContextManagerService:
    """
    Service for managing conversation context windows.

    Provides real-time context tracking with Redis caching
    and Supabase persistence.
    """

    def __init__(self):
        self._token_counter: Optional[TokenCounter] = None

    @property
    def token_counter(self) -> TokenCounter:
        """Get the token counter instance."""
        if self._token_counter is None:
            self._token_counter = get_token_counter()
        return self._token_counter

    # ===========================================================================
    # Context State Management
    # ===========================================================================

    async def get_context_status(
        self,
        conversation_id: str,
        user_id: str
    ) -> ContextStatusResponse:
        """
        Get the current context window status.

        First checks Redis cache, falls back to database if not cached.

        Args:
            conversation_id: Conversation ID
            user_id: User ID for authorization

        Returns:
            ContextStatusResponse with current status
        """
        try:
            # Try Redis cache first
            status = await self._get_cached_status(conversation_id)
            if status:
                return ContextStatusResponse(success=True, status=status)

            # Fall back to database
            context = await self._get_context_from_db(conversation_id, user_id)
            if not context:
                return ContextStatusResponse(
                    success=False,
                    error=f"Context not found for conversation {conversation_id}"
                )

            # Build status from database context
            status = self._build_status(context)

            # Cache the status
            await self._cache_status(conversation_id, status)

            return ContextStatusResponse(success=True, status=status)

        except Exception as e:
            logger.error(
                "Failed to get context status",
                conversation_id=conversation_id,
                error=str(e)
            )
            return ContextStatusResponse(success=False, error=str(e))

    async def create_context(
        self,
        conversation_id: str,
        user_id: str,
        max_tokens: int = 200000,
        threshold_percent: int = 80
    ) -> Optional[ConversationContext]:
        """
        Create a new context for a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            max_tokens: Maximum tokens allowed
            threshold_percent: Compaction trigger threshold

        Returns:
            Created ConversationContext or None on failure
        """
        try:
            supabase = get_supabase()

            context_data = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "total_tokens": 0,
                "max_tokens": max_tokens,
                "threshold_percent": threshold_percent,
            }

            result = supabase.table("conversation_contexts").insert(
                context_data
            ).execute()

            if result.data:
                context = ConversationContext(**result.data[0])
                logger.info(
                    "Created conversation context",
                    conversation_id=conversation_id,
                    context_id=context.id
                )
                return context

            return None

        except Exception as e:
            logger.error(
                "Failed to create context",
                conversation_id=conversation_id,
                error=str(e)
            )
            return None

    async def add_message_to_context(
        self,
        conversation_id: str,
        user_id: str,
        request: AddMessageRequest
    ) -> AddMessageResponse:
        """
        Add a message to the context window.

        Counts tokens, stores the message, updates context state,
        and checks if compaction should be triggered.

        Args:
            conversation_id: Conversation ID
            user_id: User ID for authorization
            request: Message details

        Returns:
            AddMessageResponse with result
        """
        try:
            # Get or create context
            context = await self._get_or_create_context(
                conversation_id, user_id
            )
            if not context:
                return AddMessageResponse(
                    success=False,
                    error="Failed to get or create context"
                )

            # Count tokens
            token_count = count_message_tokens(
                request.content,
                request.role.value
            )

            # Get current message count for position
            position = await self._get_next_position(context.id)

            # Auto-protect system messages and first messages
            should_auto_protect = self._should_auto_protect(
                role=request.role,
                content=request.content,
                position=position,
                is_protected=request.is_protected
            )

            # Insert message
            supabase = get_supabase()
            message_data = {
                "context_id": context.id,
                "role": request.role.value,
                "content": request.content,
                "token_count": token_count,
                "is_protected": should_auto_protect or request.is_protected,
                "position": position,
            }

            result = supabase.table("context_messages").insert(
                message_data
            ).execute()

            if not result.data:
                return AddMessageResponse(
                    success=False,
                    error="Failed to insert message"
                )

            message_id = result.data[0]["id"]

            # Update context total tokens
            new_total = context.total_tokens + token_count
            supabase.table("conversation_contexts").update({
                "total_tokens": new_total,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", context.id).execute()

            # Build updated status
            status = ContextWindowStatus(
                conversation_id=conversation_id,
                current_tokens=new_total,
                max_tokens=context.max_tokens,
                threshold_percent=context.threshold_percent,
                usage_percent=self.token_counter.get_usage_percent(
                    new_total, context.max_tokens
                ),
                status=ContextStatus(self.token_counter.get_status(
                    new_total, context.max_tokens, conversation_id=conversation_id
                )),
                available_tokens=self.token_counter.get_available_tokens(
                    new_total, context.max_tokens
                ),
                estimated_messages_remaining=self.token_counter.estimate_messages_remaining(
                    self.token_counter.get_available_tokens(new_total, context.max_tokens)
                ),
                is_compacting=False,
                last_compaction_at=context.last_compaction_at,
                last_updated=datetime.utcnow()
            )

            # Cache the updated status
            await self._cache_status(conversation_id, status)

            # Check if compaction should be triggered
            compaction_triggered = False
            threshold_tokens = int(context.max_tokens * context.threshold_percent / 100)
            if new_total >= threshold_tokens:
                compaction_triggered = await self._should_trigger_compaction(
                    conversation_id
                )
                if compaction_triggered:
                    logger.info(
                        "Compaction triggered",
                        conversation_id=conversation_id,
                        current_tokens=new_total,
                        threshold=threshold_tokens
                    )

            return AddMessageResponse(
                success=True,
                message_id=message_id,
                token_count=token_count,
                context_status=status,
                compaction_triggered=compaction_triggered
            )

        except Exception as e:
            logger.error(
                "Failed to add message to context",
                conversation_id=conversation_id,
                error=str(e)
            )
            return AddMessageResponse(success=False, error=str(e))

    async def toggle_message_protection(
        self,
        message_id: str,
        user_id: str,
        is_protected: bool
    ) -> bool:
        """
        Toggle protection status for a message.

        Protected messages are preserved during compaction.

        Args:
            message_id: Message ID
            user_id: User ID for authorization
            is_protected: New protection status

        Returns:
            True if successful
        """
        try:
            supabase = get_supabase()

            # Verify ownership through context
            msg_result = supabase.table("context_messages").select(
                "context_id"
            ).eq("id", message_id).single().execute()

            if not msg_result.data:
                return False

            context_id = msg_result.data["context_id"]

            ctx_result = supabase.table("conversation_contexts").select(
                "user_id"
            ).eq("id", context_id).single().execute()

            if not ctx_result.data or ctx_result.data["user_id"] != user_id:
                return False

            # Update protection status
            supabase.table("context_messages").update({
                "is_protected": is_protected
            }).eq("id", message_id).execute()

            return True

        except Exception as e:
            logger.error(
                "Failed to toggle message protection",
                message_id=message_id,
                error=str(e)
            )
            return False

    # ===========================================================================
    # Redis Cache Operations
    # ===========================================================================

    async def _get_cached_status(
        self,
        conversation_id: str
    ) -> Optional[ContextWindowStatus]:
        """Get cached context status from Redis."""
        try:
            redis = get_redis()
            key = CONTEXT_STATE_KEY.format(conversation_id=conversation_id)
            data = redis.get(key)

            if data:
                return ContextWindowStatus(**json.loads(data))
            return None

        except Exception as e:
            logger.warning(
                "Failed to get cached status",
                conversation_id=conversation_id,
                error=str(e)
            )
            return None

    async def _cache_status(
        self,
        conversation_id: str,
        status: ContextWindowStatus
    ) -> bool:
        """Cache context status in Redis."""
        try:
            redis = get_redis()
            key = CONTEXT_STATE_KEY.format(conversation_id=conversation_id)

            # Serialize status to JSON
            data = status.model_dump_json()
            redis.setex(key, CONTEXT_STATE_TTL, data)
            return True

        except Exception as e:
            logger.warning(
                "Failed to cache status",
                conversation_id=conversation_id,
                error=str(e)
            )
            return False

    async def _invalidate_cache(self, conversation_id: str) -> bool:
        """Invalidate cached context status."""
        try:
            redis = get_redis()
            key = CONTEXT_STATE_KEY.format(conversation_id=conversation_id)
            redis.delete(key)
            return True
        except Exception as e:
            logger.warning(
                "Failed to invalidate cache",
                conversation_id=conversation_id,
                error=str(e)
            )
            return False

    # ===========================================================================
    # Database Operations
    # ===========================================================================

    async def _get_context_from_db(
        self,
        conversation_id: str,
        user_id: str
    ) -> Optional[ConversationContext]:
        """Get context from database."""
        try:
            supabase = get_supabase()

            result = supabase.table("conversation_contexts").select(
                "*"
            ).eq("conversation_id", conversation_id).eq(
                "user_id", user_id
            ).single().execute()

            if result.data:
                return ConversationContext(**result.data)
            return None

        except Exception as e:
            logger.error(
                "Failed to get context from DB",
                conversation_id=conversation_id,
                error=str(e)
            )
            return None

    async def _get_or_create_context(
        self,
        conversation_id: str,
        user_id: str
    ) -> Optional[ConversationContext]:
        """Get existing context or create new one."""
        context = await self._get_context_from_db(conversation_id, user_id)
        if context:
            return context
        return await self.create_context(conversation_id, user_id)

    async def _get_next_position(self, context_id: str) -> int:
        """Get the next position for a message in the context."""
        try:
            supabase = get_supabase()

            result = supabase.table("context_messages").select(
                "position"
            ).eq("context_id", context_id).order(
                "position", desc=True
            ).limit(1).execute()

            if result.data:
                return result.data[0]["position"] + 1
            return 0

        except Exception:
            return 0

    def _build_status(
        self,
        context: ConversationContext
    ) -> ContextWindowStatus:
        """Build status object from context."""
        usage_percent = self.token_counter.get_usage_percent(
            context.total_tokens, context.max_tokens
        )
        status_str = self.token_counter.get_status(
            context.total_tokens,
            context.max_tokens,
            conversation_id=context.conversation_id
        )
        available = self.token_counter.get_available_tokens(
            context.total_tokens, context.max_tokens
        )

        return ContextWindowStatus(
            conversation_id=context.conversation_id,
            current_tokens=context.total_tokens,
            max_tokens=context.max_tokens,
            threshold_percent=context.threshold_percent,
            usage_percent=usage_percent,
            status=ContextStatus(status_str),
            available_tokens=available,
            estimated_messages_remaining=self.token_counter.estimate_messages_remaining(available),
            is_compacting=False,
            last_compaction_at=context.last_compaction_at,
            last_updated=datetime.utcnow()
        )

    # ===========================================================================
    # Protected Message Helpers
    # ===========================================================================

    def _should_auto_protect(
        self,
        role: MessageRole,
        content: str,
        position: int,
        is_protected: bool
    ) -> bool:
        """
        Determine if a message should be automatically protected.

        Auto-protects:
        - System messages (always)
        - First message in conversation (position 0)
        - Setup/configuration commands (/system, /config, /mode, etc.)

        Args:
            role: Message role
            content: Message content
            position: Position in conversation
            is_protected: Explicit protection flag

        Returns:
            True if message should be auto-protected
        """
        # Already protected
        if is_protected:
            return True

        # System messages are always protected
        if role == MessageRole.SYSTEM:
            return True

        # First message in conversation is protected
        if position == 0:
            return True

        # Setup commands are protected
        if role == MessageRole.USER:
            setup_commands = [
                "/system", "/config", "/mode", "/project",
                "/setup", "/context", "/init", "/persona"
            ]
            content_lower = content.lower().strip()
            for cmd in setup_commands:
                if content_lower.startswith(cmd):
                    return True

        return False

    # ===========================================================================
    # Compaction Helpers
    # ===========================================================================

    async def _should_trigger_compaction(
        self,
        conversation_id: str
    ) -> bool:
        """
        Check if compaction should be triggered.

        Checks for:
        - No active compaction (lock)
        - 30-second cooldown since last compaction
        """
        try:
            redis = get_redis()
            lock_key = COMPACTION_LOCK_KEY.format(conversation_id=conversation_id)

            # Check if lock exists (compaction in progress)
            if redis.exists(lock_key):
                return False

            # TODO: Check 30-second cooldown from last compaction
            # For now, allow trigger if no lock

            return True

        except Exception as e:
            logger.warning(
                "Failed to check compaction eligibility",
                conversation_id=conversation_id,
                error=str(e)
            )
            return False


# Global service instance
_context_manager: Optional[ContextManagerService] = None


def get_context_manager() -> ContextManagerService:
    """Get the context manager service instance."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManagerService()
    return _context_manager
