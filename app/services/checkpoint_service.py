"""
Empire v7.3 - Checkpoint Service
Automatic checkpoint system for conversation recovery and state management.

Feature: Chat Context Window Management (011)
Task: 206 - Implement Automatic Checkpoint System
"""

import json
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4
import structlog

from app.core.database import get_supabase, get_redis
from app.models.context_models import (
    SessionCheckpoint,
    CheckpointAutoTag,
    ContextMessage,
    ConversationContext,
    CheckpointResponse,
    CheckpointListResponse,
    RecoveryCheckResponse,
)

logger = structlog.get_logger(__name__)

# Redis key patterns
CHECKPOINT_CACHE_KEY = "checkpoint:{checkpoint_id}"
CHECKPOINT_LIST_KEY = "checkpoints:{conversation_id}"
LAST_CHECKPOINT_KEY = "checkpoint:last:{conversation_id}"

# TTLs
CHECKPOINT_CACHE_TTL = 3600  # 1 hour
CHECKPOINT_LIST_TTL = 1800  # 30 minutes

# Limits
MAX_CHECKPOINTS_PER_SESSION = 50
CHECKPOINT_EXPIRATION_DAYS = 30


class CheckpointService:
    """
    Service for managing conversation checkpoints.

    Provides automatic and manual checkpoint creation, retrieval,
    and restoration for crash recovery and session management.
    """

    def __init__(self):
        self._max_checkpoints = MAX_CHECKPOINTS_PER_SESSION

    # ===========================================================================
    # Checkpoint Creation
    # ===========================================================================

    async def create_checkpoint(
        self,
        conversation_id: str,
        user_id: str,
        messages: List[ContextMessage],
        token_count: int,
        trigger: str = "auto",
        label: Optional[str] = None,
        is_abnormal_close: bool = False,
        project_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CheckpointResponse:
        """
        Create a new checkpoint of the current conversation state.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            messages: List of context messages to checkpoint
            token_count: Current token count
            trigger: Trigger type (auto, manual, pre_compaction, important_context)
            label: Optional user-provided label
            is_abnormal_close: True if this is a crash recovery checkpoint
            project_id: Optional project ID
            metadata: Optional additional metadata

        Returns:
            CheckpointResponse with checkpoint data
        """
        try:
            checkpoint_id = str(uuid4())

            # Detect content tags from recent messages
            auto_tags = self._detect_content_tags(messages)

            # Generate automatic label if none provided
            if not label:
                label = self._generate_auto_label(messages, auto_tags, trigger)

            # Determine primary auto tag (most relevant one)
            primary_tag = None
            if auto_tags:
                # Priority order: code > decision > error_resolution > milestone
                tag_priority = ["code", "decision", "error_resolution", "milestone"]
                for tag in tag_priority:
                    if tag in auto_tags:
                        primary_tag = tag
                        break

            # Prepare checkpoint data (conversation state snapshot)
            checkpoint_data = {
                "messages": [msg.model_dump() for msg in messages],
                "metadata": metadata or {},
                "project_id": project_id,
                "model": metadata.get("model") if metadata else None,
                "tags": auto_tags,
            }

            # Calculate expiration
            expires_at = datetime.utcnow() + timedelta(days=CHECKPOINT_EXPIRATION_DAYS)

            # Insert into database
            supabase = get_supabase()

            insert_data = {
                "id": checkpoint_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "checkpoint_data": json.dumps(checkpoint_data),
                "token_count": token_count,
                "label": label,
                "auto_tag": primary_tag,
                "is_abnormal_close": is_abnormal_close,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": expires_at.isoformat(),
            }

            result = supabase.table("session_checkpoints").insert(
                insert_data
            ).execute()

            if not result.data:
                return CheckpointResponse(
                    success=False,
                    error="Failed to insert checkpoint"
                )

            # Create checkpoint model
            checkpoint = SessionCheckpoint(
                id=checkpoint_id,
                conversation_id=conversation_id,
                user_id=user_id,
                checkpoint_data=checkpoint_data,
                token_count=token_count,
                label=label,
                auto_tag=CheckpointAutoTag(primary_tag) if primary_tag else None,
                is_abnormal_close=is_abnormal_close,
                created_at=datetime.utcnow(),
                expires_at=expires_at
            )

            # Cleanup old checkpoints if over limit
            await self._cleanup_old_checkpoints(conversation_id)

            # Cache last checkpoint timestamp
            await self._cache_last_checkpoint_time(conversation_id)

            # Invalidate checkpoint list cache
            await self._invalidate_checkpoint_list_cache(conversation_id)

            logger.info(
                "checkpoint_created",
                checkpoint_id=checkpoint_id,
                conversation_id=conversation_id,
                trigger=trigger,
                label=label,
                token_count=token_count,
                auto_tags=auto_tags
            )

            return CheckpointResponse(success=True, checkpoint=checkpoint)

        except Exception as e:
            logger.error(
                "create_checkpoint_failed",
                conversation_id=conversation_id,
                error=str(e)
            )
            return CheckpointResponse(success=False, error=str(e))

    # ===========================================================================
    # Checkpoint Retrieval
    # ===========================================================================

    async def get_checkpoints(
        self,
        conversation_id: str,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> CheckpointListResponse:
        """
        Get all checkpoints for a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID for authorization
            limit: Maximum results to return
            offset: Offset for pagination

        Returns:
            CheckpointListResponse with list of checkpoints
        """
        try:
            supabase = get_supabase()

            # Query checkpoints
            result = supabase.table("session_checkpoints").select(
                "id, conversation_id, user_id, token_count, label, auto_tag, "
                "is_abnormal_close, created_at, expires_at"
            ).eq(
                "conversation_id", conversation_id
            ).eq(
                "user_id", user_id
            ).gt(
                "expires_at", datetime.utcnow().isoformat()
            ).order(
                "created_at", desc=True
            ).range(offset, offset + limit - 1).execute()

            if not result.data:
                return CheckpointListResponse(
                    success=True,
                    checkpoints=[],
                    total=0
                )

            # Get total count
            count_result = supabase.table("session_checkpoints").select(
                "id", count="exact"
            ).eq(
                "conversation_id", conversation_id
            ).eq(
                "user_id", user_id
            ).gt(
                "expires_at", datetime.utcnow().isoformat()
            ).execute()

            total = count_result.count if count_result.count else len(result.data)

            # Convert to SessionCheckpoint objects (without full checkpoint_data)
            checkpoints = []
            for row in result.data:
                checkpoint = SessionCheckpoint(
                    id=row["id"],
                    conversation_id=row["conversation_id"],
                    user_id=row["user_id"],
                    checkpoint_data={},  # Don't include full data in list
                    token_count=row["token_count"],
                    label=row.get("label"),
                    auto_tag=CheckpointAutoTag(row["auto_tag"]) if row.get("auto_tag") else None,
                    is_abnormal_close=row.get("is_abnormal_close", False),
                    created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) if isinstance(row["created_at"], str) else row["created_at"],
                    expires_at=datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")) if isinstance(row["expires_at"], str) else row["expires_at"]
                )
                checkpoints.append(checkpoint)

            return CheckpointListResponse(
                success=True,
                checkpoints=checkpoints,
                total=total
            )

        except Exception as e:
            logger.error(
                "get_checkpoints_failed",
                conversation_id=conversation_id,
                error=str(e)
            )
            return CheckpointListResponse(success=False, error=str(e))

    async def get_checkpoint(
        self,
        checkpoint_id: str,
        user_id: str
    ) -> CheckpointResponse:
        """
        Get a specific checkpoint with full data.

        Args:
            checkpoint_id: Checkpoint ID
            user_id: User ID for authorization

        Returns:
            CheckpointResponse with checkpoint data
        """
        try:
            supabase = get_supabase()

            result = supabase.table("session_checkpoints").select(
                "*"
            ).eq(
                "id", checkpoint_id
            ).eq(
                "user_id", user_id
            ).single().execute()

            if not result.data:
                return CheckpointResponse(
                    success=False,
                    error="Checkpoint not found"
                )

            row = result.data

            # Parse checkpoint_data from JSON
            checkpoint_data = json.loads(row["checkpoint_data"]) if isinstance(
                row["checkpoint_data"], str
            ) else row["checkpoint_data"]

            checkpoint = SessionCheckpoint(
                id=row["id"],
                conversation_id=row["conversation_id"],
                user_id=row["user_id"],
                checkpoint_data=checkpoint_data,
                token_count=row["token_count"],
                label=row.get("label"),
                auto_tag=CheckpointAutoTag(row["auto_tag"]) if row.get("auto_tag") else None,
                is_abnormal_close=row.get("is_abnormal_close", False),
                created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) if isinstance(row["created_at"], str) else row["created_at"],
                expires_at=datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")) if isinstance(row["expires_at"], str) else row["expires_at"]
            )

            return CheckpointResponse(success=True, checkpoint=checkpoint)

        except Exception as e:
            logger.error(
                "get_checkpoint_failed",
                checkpoint_id=checkpoint_id,
                error=str(e)
            )
            return CheckpointResponse(success=False, error=str(e))

    # ===========================================================================
    # Checkpoint Restoration
    # ===========================================================================

    async def restore_checkpoint(
        self,
        checkpoint_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Restore conversation from a checkpoint.

        Args:
            checkpoint_id: Checkpoint to restore from
            user_id: User ID for authorization

        Returns:
            Dict with restored conversation data or None
        """
        try:
            # Get the checkpoint
            checkpoint_response = await self.get_checkpoint(checkpoint_id, user_id)

            if not checkpoint_response.success or not checkpoint_response.checkpoint:
                logger.warning(
                    "checkpoint_restore_failed_not_found",
                    checkpoint_id=checkpoint_id
                )
                return None

            checkpoint = checkpoint_response.checkpoint

            # Extract messages from checkpoint data
            checkpoint_data = checkpoint.checkpoint_data
            messages_data = checkpoint_data.get("messages", [])

            # Recreate ContextMessage objects
            messages = []
            for msg_data in messages_data:
                try:
                    # Handle datetime fields
                    if "created_at" in msg_data and isinstance(msg_data["created_at"], str):
                        msg_data["created_at"] = datetime.fromisoformat(
                            msg_data["created_at"].replace("Z", "+00:00")
                        )
                    message = ContextMessage(**msg_data)
                    messages.append(message)
                except Exception as msg_err:
                    logger.warning(
                        "checkpoint_message_parse_error",
                        error=str(msg_err)
                    )

            logger.info(
                "checkpoint_restored",
                checkpoint_id=checkpoint_id,
                conversation_id=checkpoint.conversation_id,
                messages_count=len(messages),
                token_count=checkpoint.token_count
            )

            return {
                "conversation_id": checkpoint.conversation_id,
                "messages": messages,
                "token_count": checkpoint.token_count,
                "metadata": checkpoint_data.get("metadata", {}),
                "project_id": checkpoint_data.get("project_id"),
                "restored_from": checkpoint_id,
                "restored_at": datetime.utcnow()
            }

        except Exception as e:
            logger.error(
                "restore_checkpoint_failed",
                checkpoint_id=checkpoint_id,
                error=str(e)
            )
            return None

    # ===========================================================================
    # Crash Recovery
    # ===========================================================================

    async def check_for_recovery(
        self,
        user_id: str
    ) -> RecoveryCheckResponse:
        """
        Check if there are any abnormal close checkpoints for recovery.

        Args:
            user_id: User ID

        Returns:
            RecoveryCheckResponse with recovery information
        """
        try:
            supabase = get_supabase()

            # Find most recent abnormal close checkpoint
            result = supabase.table("session_checkpoints").select(
                "*, chat_sessions(title)"
            ).eq(
                "user_id", user_id
            ).eq(
                "is_abnormal_close", True
            ).gt(
                "expires_at", datetime.utcnow().isoformat()
            ).order(
                "created_at", desc=True
            ).limit(1).execute()

            if not result.data:
                return RecoveryCheckResponse(
                    success=True,
                    has_recovery=False
                )

            row = result.data[0]

            # Parse checkpoint data
            checkpoint_data = json.loads(row["checkpoint_data"]) if isinstance(
                row["checkpoint_data"], str
            ) else row["checkpoint_data"]

            checkpoint = SessionCheckpoint(
                id=row["id"],
                conversation_id=row["conversation_id"],
                user_id=row["user_id"],
                checkpoint_data=checkpoint_data,
                token_count=row["token_count"],
                label=row.get("label"),
                auto_tag=CheckpointAutoTag(row["auto_tag"]) if row.get("auto_tag") else None,
                is_abnormal_close=True,
                created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) if isinstance(row["created_at"], str) else row["created_at"],
                expires_at=datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")) if isinstance(row["expires_at"], str) else row["expires_at"]
            )

            # Get conversation title
            conversation_title = None
            if row.get("chat_sessions"):
                conversation_title = row["chat_sessions"].get("title")

            return RecoveryCheckResponse(
                success=True,
                has_recovery=True,
                checkpoint=checkpoint,
                conversation_title=conversation_title
            )

        except Exception as e:
            logger.error(
                "check_for_recovery_failed",
                user_id=user_id,
                error=str(e)
            )
            return RecoveryCheckResponse(success=False, error=str(e))

    async def clear_recovery_checkpoint(
        self,
        checkpoint_id: str,
        user_id: str
    ) -> bool:
        """
        Clear an abnormal close checkpoint after successful recovery or dismissal.

        Args:
            checkpoint_id: Checkpoint ID to clear
            user_id: User ID for authorization

        Returns:
            True if successful
        """
        try:
            supabase = get_supabase()

            # Update to non-abnormal or delete
            result = supabase.table("session_checkpoints").update({
                "is_abnormal_close": False
            }).eq(
                "id", checkpoint_id
            ).eq(
                "user_id", user_id
            ).execute()

            return bool(result.data)

        except Exception as e:
            logger.error(
                "clear_recovery_checkpoint_failed",
                checkpoint_id=checkpoint_id,
                error=str(e)
            )
            return False

    # ===========================================================================
    # Content Detection
    # ===========================================================================

    def _detect_content_tags(
        self,
        messages: List[ContextMessage]
    ) -> List[str]:
        """
        Detect content types in recent messages to auto-tag the checkpoint.

        Args:
            messages: List of messages to analyze

        Returns:
            List of detected tags
        """
        tags = set()

        # Look at the last 5 messages
        recent_messages = messages[-5:] if len(messages) > 5 else messages

        for msg in recent_messages:
            content = msg.content.lower()

            # Check for code blocks
            if "```" in msg.content:
                tags.add("code")

            # Check for file paths (more specific pattern)
            if re.search(r'[\w\-\.\/]+\.[a-zA-Z]{2,4}', msg.content):
                # Exclude common false positives like URLs
                if not re.search(r'https?://', content):
                    tags.add("code")

            # Check for decision language
            decision_phrases = [
                "decided to", "will use", "chosen", "selected",
                "going with", "let's go with", "we'll use",
                "the approach is", "the solution is"
            ]
            if any(phrase in content for phrase in decision_phrases):
                tags.add("decision")

            # Check for error messages
            error_phrases = [
                "error:", "exception:", "failed:", "traceback",
                "error occurred", "failed to", "couldn't", "unable to"
            ]
            if any(phrase in content for phrase in error_phrases):
                tags.add("error_resolution")

            # Check for task completion
            completion_phrases = [
                "completed", "finished", "done", "implemented",
                "fixed", "resolved", "working now", "tests pass"
            ]
            if any(phrase in content for phrase in completion_phrases):
                tags.add("milestone")

        return list(tags)

    def _generate_auto_label(
        self,
        messages: List[ContextMessage],
        tags: List[str],
        trigger: str
    ) -> str:
        """
        Generate an automatic label based on content and tags.

        Args:
            messages: List of messages
            tags: Detected tags
            trigger: Trigger type

        Returns:
            Generated label string
        """
        timestamp = datetime.utcnow().strftime("%H:%M:%S")

        # Priority-based label generation
        if "code" in tags:
            # Try to extract filename from recent messages
            for msg in reversed(messages[-3:]):
                file_match = re.search(r'([\w\-]+\.[a-zA-Z]{2,4})', msg.content)
                if file_match:
                    return f"Code: {file_match.group(1)} ({timestamp})"
            return f"Code generated ({timestamp})"

        if "decision" in tags:
            return f"Decision made ({timestamp})"

        if "error_resolution" in tags:
            return f"Error resolved ({timestamp})"

        if "milestone" in tags:
            return f"Milestone reached ({timestamp})"

        # Trigger-based fallback
        if trigger == "pre_compaction":
            return f"Pre-compaction snapshot ({timestamp})"

        if trigger == "manual":
            return f"Manual checkpoint ({timestamp})"

        if trigger == "important_context":
            return f"Important context ({timestamp})"

        return f"Checkpoint ({timestamp})"

    # ===========================================================================
    # Cleanup
    # ===========================================================================

    async def _cleanup_old_checkpoints(
        self,
        conversation_id: str
    ) -> int:
        """
        Keep only the most recent checkpoints for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Number of checkpoints deleted
        """
        try:
            supabase = get_supabase()

            # Get count of checkpoints
            count_result = supabase.table("session_checkpoints").select(
                "id", count="exact"
            ).eq(
                "conversation_id", conversation_id
            ).execute()

            count = count_result.count if count_result.count else 0

            if count <= self._max_checkpoints:
                return 0

            # Get IDs of oldest checkpoints to delete
            to_delete = count - self._max_checkpoints

            oldest_result = supabase.table("session_checkpoints").select(
                "id"
            ).eq(
                "conversation_id", conversation_id
            ).order(
                "created_at", desc=False
            ).limit(to_delete).execute()

            if not oldest_result.data:
                return 0

            ids_to_delete = [row["id"] for row in oldest_result.data]

            # Delete oldest checkpoints
            for checkpoint_id in ids_to_delete:
                supabase.table("session_checkpoints").delete().eq(
                    "id", checkpoint_id
                ).execute()

            logger.info(
                "checkpoints_cleaned_up",
                conversation_id=conversation_id,
                deleted_count=len(ids_to_delete)
            )

            return len(ids_to_delete)

        except Exception as e:
            logger.error(
                "cleanup_checkpoints_failed",
                conversation_id=conversation_id,
                error=str(e)
            )
            return 0

    async def cleanup_expired_checkpoints(self) -> int:
        """
        Delete all expired checkpoints across all conversations.

        This should be run periodically as a background job.

        Returns:
            Number of checkpoints deleted
        """
        try:
            supabase = get_supabase()

            # Delete expired checkpoints
            result = supabase.table("session_checkpoints").delete().lt(
                "expires_at", datetime.utcnow().isoformat()
            ).execute()

            deleted_count = len(result.data) if result.data else 0

            if deleted_count > 0:
                logger.info(
                    "expired_checkpoints_cleaned",
                    deleted_count=deleted_count
                )

            return deleted_count

        except Exception as e:
            logger.error(
                "cleanup_expired_checkpoints_failed",
                error=str(e)
            )
            return 0

    # ===========================================================================
    # Cache Operations
    # ===========================================================================

    async def _cache_last_checkpoint_time(
        self,
        conversation_id: str
    ) -> bool:
        """Cache the timestamp of the last checkpoint."""
        try:
            redis = get_redis()
            key = LAST_CHECKPOINT_KEY.format(conversation_id=conversation_id)
            redis.setex(key, CHECKPOINT_CACHE_TTL, datetime.utcnow().isoformat())
            return True
        except Exception as e:
            logger.warning(
                "cache_last_checkpoint_time_failed",
                conversation_id=conversation_id,
                error=str(e)
            )
            return False

    async def get_last_checkpoint_time(
        self,
        conversation_id: str
    ) -> Optional[datetime]:
        """Get the timestamp of the last checkpoint from cache."""
        try:
            redis = get_redis()
            key = LAST_CHECKPOINT_KEY.format(conversation_id=conversation_id)
            data = redis.get(key)
            if data:
                return datetime.fromisoformat(data.decode() if isinstance(data, bytes) else data)
            return None
        except Exception as e:
            logger.warning(
                "get_last_checkpoint_time_failed",
                conversation_id=conversation_id,
                error=str(e)
            )
            return None

    async def _invalidate_checkpoint_list_cache(
        self,
        conversation_id: str
    ) -> bool:
        """Invalidate the checkpoint list cache."""
        try:
            redis = get_redis()
            key = CHECKPOINT_LIST_KEY.format(conversation_id=conversation_id)
            redis.delete(key)
            return True
        except Exception as e:
            logger.warning(
                "invalidate_checkpoint_list_cache_failed",
                conversation_id=conversation_id,
                error=str(e)
            )
            return False


    # ===========================================================================
    # API Route Helpers (Task 208 - Session Resume & Recovery UI)
    # ===========================================================================

    async def get_conversation_checkpoints(
        self,
        conversation_id: str,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get checkpoints for a conversation in dict format for API routes.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            limit: Maximum results

        Returns:
            List of checkpoint dicts
        """
        result = await self.get_checkpoints(conversation_id, user_id, limit=limit)

        if not result.success:
            return []

        checkpoints = []
        for i, cp in enumerate(result.checkpoints):
            checkpoints.append({
                "id": cp.id,
                "conversation_id": cp.conversation_id,
                "checkpoint_number": len(result.checkpoints) - i,  # Most recent = highest number
                "message_count": len(cp.checkpoint_data.get("messages", [])) if cp.checkpoint_data else 0,
                "token_count": cp.token_count,
                "summary": cp.label or "",
                "created_at": cp.created_at.isoformat() if cp.created_at else "",
                "trigger": cp.auto_tag.value if cp.auto_tag else "auto"
            })

        return checkpoints

    async def create_manual_checkpoint(
        self,
        conversation_id: str,
        user_id: str,
        trigger: str = "manual"
    ) -> Optional[Dict[str, Any]]:
        """
        Create a checkpoint by fetching current conversation state.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            trigger: Trigger type

        Returns:
            Created checkpoint dict or None
        """
        try:
            supabase = get_supabase()

            # Get context
            ctx_result = supabase.table("conversation_contexts").select(
                "id, total_tokens"
            ).eq(
                "conversation_id", conversation_id
            ).eq(
                "user_id", user_id
            ).single().execute()

            if not ctx_result.data:
                logger.warning(
                    "create_manual_checkpoint_no_context",
                    conversation_id=conversation_id
                )
                return None

            context_id = ctx_result.data["id"]
            token_count = ctx_result.data.get("total_tokens", 0)

            # Get messages
            msg_result = supabase.table("context_messages").select(
                "*"
            ).eq(
                "context_id", context_id
            ).order(
                "position", desc=False
            ).execute()

            if not msg_result.data:
                logger.warning(
                    "create_manual_checkpoint_no_messages",
                    conversation_id=conversation_id
                )
                return None

            # Convert to ContextMessage objects
            from app.models.context_models import MessageRole
            messages = []
            for row in msg_result.data:
                messages.append(ContextMessage(
                    id=row["id"],
                    context_id=row["context_id"],
                    role=MessageRole(row["role"]),
                    content=row["content"],
                    token_count=row["token_count"],
                    is_protected=row.get("is_protected", False),
                    position=row["position"],
                    created_at=datetime.fromisoformat(
                        row["created_at"].replace("Z", "+00:00")
                    ) if row.get("created_at") else datetime.utcnow()
                ))

            # Create checkpoint
            response = await self.create_checkpoint(
                conversation_id=conversation_id,
                user_id=user_id,
                messages=messages,
                token_count=token_count,
                trigger=trigger
            )

            if not response.success or not response.checkpoint:
                return None

            cp = response.checkpoint

            # Get checkpoint count for number
            count_result = supabase.table("session_checkpoints").select(
                "id", count="exact"
            ).eq(
                "conversation_id", conversation_id
            ).eq(
                "user_id", user_id
            ).execute()

            checkpoint_number = count_result.count if count_result.count else 1

            return {
                "id": cp.id,
                "conversation_id": cp.conversation_id,
                "checkpoint_number": checkpoint_number,
                "message_count": len(messages),
                "token_count": cp.token_count,
                "summary": cp.label or "",
                "created_at": cp.created_at.isoformat() if cp.created_at else "",
                "trigger": trigger
            }

        except Exception as e:
            logger.error(
                "create_manual_checkpoint_failed",
                conversation_id=conversation_id,
                error=str(e)
            )
            return None

    async def restore_from_checkpoint(
        self,
        conversation_id: str,
        checkpoint_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Restore conversation from checkpoint and return result summary.

        Args:
            conversation_id: Conversation ID
            checkpoint_id: Checkpoint to restore
            user_id: User ID

        Returns:
            Dict with restore result or None
        """
        try:
            # Get checkpoint data
            result = await self.restore_checkpoint(checkpoint_id, user_id)

            if not result:
                return None

            # Verify conversation matches
            if result.get("conversation_id") != conversation_id:
                logger.warning(
                    "restore_checkpoint_conversation_mismatch",
                    expected=conversation_id,
                    actual=result.get("conversation_id")
                )
                return None

            messages = result.get("messages", [])

            # Update the conversation context with restored messages
            supabase = get_supabase()

            # Get context
            ctx_result = supabase.table("conversation_contexts").select(
                "id"
            ).eq(
                "conversation_id", conversation_id
            ).eq(
                "user_id", user_id
            ).single().execute()

            if ctx_result.data:
                context_id = ctx_result.data["id"]

                # TRANSACTION SAFETY: Insert new messages BEFORE deleting old ones
                # This prevents data loss if any operation fails

                # Step 1: Get existing message IDs for later deletion
                existing_result = supabase.table("context_messages").select(
                    "id"
                ).eq("context_id", context_id).execute()
                existing_ids = [row["id"] for row in (existing_result.data or [])]

                # Step 2: Insert checkpoint messages with NEW UUIDs (avoids conflicts)
                new_message_ids = []
                for i, msg in enumerate(messages):
                    new_msg_id = str(uuid4())
                    new_message_ids.append(new_msg_id)
                    supabase.table("context_messages").insert({
                        "id": new_msg_id,
                        "context_id": context_id,
                        "role": msg.role.value,
                        "content": msg.content,
                        "token_count": msg.token_count,
                        "is_protected": msg.is_protected,
                        "position": i,
                        "created_at": msg.created_at.isoformat() if msg.created_at else datetime.utcnow().isoformat()
                    }).execute()

                # Step 3: Only after successful inserts, delete old messages
                # If insert failed above, this won't run and old data is preserved
                for old_id in existing_ids:
                    supabase.table("context_messages").delete().eq(
                        "id", old_id
                    ).execute()

                # Step 4: Update context totals
                total_tokens = sum(m.token_count for m in messages)
                supabase.table("conversation_contexts").update({
                    "total_tokens": total_tokens,
                    "message_count": len(messages),
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", context_id).execute()

            logger.info(
                "checkpoint_restore_applied",
                conversation_id=conversation_id,
                checkpoint_id=checkpoint_id,
                messages_restored=len(messages),
                token_count=result.get("token_count", 0)
            )

            return {
                "messages_restored": len(messages),
                "token_count": result.get("token_count", 0)
            }

        except Exception as e:
            logger.error(
                "restore_from_checkpoint_failed",
                conversation_id=conversation_id,
                checkpoint_id=checkpoint_id,
                error=str(e)
            )
            return None


# ===========================================================================
# Global Service Instance
# ===========================================================================

_checkpoint_service: Optional[CheckpointService] = None


def get_checkpoint_service() -> CheckpointService:
    """Get the checkpoint service instance."""
    global _checkpoint_service
    if _checkpoint_service is None:
        _checkpoint_service = CheckpointService()
    return _checkpoint_service
