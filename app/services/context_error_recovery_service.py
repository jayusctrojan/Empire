"""
Empire v7.3 - Context Error Recovery Service
Automatic detection and recovery from context window overflow errors.

Feature: Chat Context Window Management (011)
Task: 210 - Implement Automatic Error Recovery
"""

import re
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from uuid import uuid4
import structlog
from prometheus_client import Counter, Histogram, Gauge

from app.core.database import get_supabase, get_redis
from app.models.context_models import (
    ContextMessage,
    ConversationContext,
    CompactionTrigger,
    CompactionResult,
    MessageRole,
)
from app.services.context_condensing_engine import (
    ContextCondensingEngine,
    get_condensing_engine,
)
from app.services.checkpoint_service import get_checkpoint_service

logger = structlog.get_logger(__name__)

# ==============================================================================
# Prometheus Metrics
# ==============================================================================

RECOVERY_ATTEMPTS = Counter(
    'empire_context_recovery_attempts_total',
    'Total number of context recovery attempts',
    ['attempt_number', 'success']
)

RECOVERY_LATENCY = Histogram(
    'empire_context_recovery_duration_seconds',
    'Duration of context recovery operations',
    ['attempt_number'],
    buckets=[1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0]
)

RECOVERY_REDUCTION = Histogram(
    'empire_context_recovery_reduction_percent',
    'Token reduction percentage during recovery',
    ['attempt_number'],
    buckets=[20, 30, 40, 50, 60, 70, 80]
)

ACTIVE_RECOVERIES = Gauge(
    'empire_context_recoveries_in_progress',
    'Number of recovery operations currently in progress'
)

# ==============================================================================
# Configuration
# ==============================================================================

# Error patterns that indicate context overflow
OVERFLOW_ERROR_PATTERNS = [
    r"context.?window.?full",
    r"maximum.?context.?length",
    r"too.?many.?tokens",
    r"context.?overflow",
    r"input.?too.?long",
    r"exceeds?.?token.?limit",
    r"max.?tokens.?exceeded",
    r"prompt.?is.?too.?long",
    r"request.?too.?large",
    r"context.?length.?exceeded",
    r"token.?limit.?exceeded",
    # Anthropic specific
    r"prompt_too_long",
    r"context_length_exceeded",
    # OpenAI specific
    r"maximum.?context.?length.?is",
    r"reduce.?the.?length.?of.?the.?messages",
    # Generic
    r"context.*limit",
    r"token.*exceeded",
]

# Redis key patterns
RECOVERY_LOCK_KEY = "context:{conversation_id}:recovery_lock"
RECOVERY_PROGRESS_KEY = "context:{conversation_id}:recovery_progress"

# TTLs
RECOVERY_LOCK_TTL = 180  # 3 minutes
RECOVERY_PROGRESS_TTL = 300  # 5 minutes

# Recovery configuration
MAX_RECOVERY_ATTEMPTS = 3
BASE_REDUCTION_PERCENT = 25  # Start with 25% reduction
REDUCTION_INCREMENT = 15  # Increase by 15% each attempt


class ContextErrorRecoveryService:
    """
    Service for automatic detection and recovery from context window overflow errors.

    This service:
    1. Detects overflow errors from various API providers
    2. Creates checkpoints before recovery
    3. Performs aggressive context reduction with increasing aggressiveness
    4. Preserves essential information (code, errors, decisions)
    5. Provides metrics and observability
    """

    def __init__(
        self,
        condensing_engine: Optional[ContextCondensingEngine] = None,
        max_attempts: int = MAX_RECOVERY_ATTEMPTS
    ):
        """
        Initialize the error recovery service.

        Args:
            condensing_engine: Optional condensing engine instance
            max_attempts: Maximum recovery attempts before giving up
        """
        self.condensing_engine = condensing_engine or get_condensing_engine()
        self.max_attempts = max_attempts
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in OVERFLOW_ERROR_PATTERNS
        ]

    # ==========================================================================
    # Error Detection
    # ==========================================================================

    def is_context_overflow_error(self, error: Exception) -> bool:
        """
        Determine if an error is due to context window overflow.

        Checks error message against known patterns from various LLM providers.

        Args:
            error: The exception to analyze

        Returns:
            True if this is a context overflow error
        """
        error_str = str(error).lower()

        # Also check error attributes if available
        if hasattr(error, 'code'):
            error_str += f" {str(error.code).lower()}"
        if hasattr(error, 'message'):
            error_str += f" {str(error.message).lower()}"
        if hasattr(error, 'body') and isinstance(error.body, dict):
            error_str += f" {str(error.body).lower()}"

        # Check against compiled patterns
        for pattern in self._compiled_patterns:
            if pattern.search(error_str):
                logger.info(
                    "Detected context overflow error",
                    error_preview=error_str[:200],
                    matched_pattern=pattern.pattern
                )
                return True

        return False

    def get_overflow_error_details(self, error: Exception) -> Dict[str, Any]:
        """
        Extract details from an overflow error for logging and analysis.

        Args:
            error: The exception to analyze

        Returns:
            Dictionary with error details
        """
        details = {
            "error_type": type(error).__name__,
            "error_message": str(error)[:500],
            "is_overflow": self.is_context_overflow_error(error),
        }

        # Extract additional details if available
        if hasattr(error, 'status_code'):
            details["status_code"] = error.status_code
        if hasattr(error, 'code'):
            details["error_code"] = error.code

        return details

    # ==========================================================================
    # Recovery Workflow
    # ==========================================================================

    async def handle_api_error(
        self,
        error: Exception,
        conversation_id: str,
        user_id: str
    ) -> Tuple[bool, str, Optional[CompactionResult]]:
        """
        Handle API errors, attempting recovery for context overflow.

        Args:
            error: The error that occurred
            conversation_id: Conversation ID
            user_id: User ID for authorization

        Returns:
            Tuple of (success, message, compaction_result)
        """
        # Check if this is a context overflow error
        if not self.is_context_overflow_error(error):
            error_details = self.get_overflow_error_details(error)
            logger.debug(
                "Non-overflow error, cannot recover automatically",
                conversation_id=conversation_id,
                error_details=error_details
            )
            return False, f"API error: {str(error)}", None

        # Attempt recovery
        return await self.recover_from_overflow(conversation_id, user_id)

    async def recover_from_overflow(
        self,
        conversation_id: str,
        user_id: str
    ) -> Tuple[bool, str, Optional[CompactionResult]]:
        """
        Attempt to recover from context overflow by reducing context.

        Tries multiple recovery attempts with increasing aggressiveness.

        Args:
            conversation_id: Conversation ID
            user_id: User ID

        Returns:
            Tuple of (success, message, final_compaction_result)
        """
        start_time = time.time()
        ACTIVE_RECOVERIES.inc()

        try:
            # Acquire recovery lock
            if not await self._acquire_recovery_lock(conversation_id):
                return False, "Recovery already in progress for this conversation", None

            # Get context and messages
            context, messages = await self._get_context_and_messages(
                conversation_id, user_id
            )

            if not context:
                await self._release_recovery_lock(conversation_id)
                return False, "Conversation not found", None

            logger.info(
                "Starting context overflow recovery",
                conversation_id=conversation_id,
                current_tokens=context.total_tokens,
                max_tokens=context.max_tokens
            )

            await self._update_progress(
                conversation_id, 0, "Initializing recovery"
            )

            # Try recovery with increasing aggressiveness
            final_result = None
            for attempt in range(1, self.max_attempts + 1):
                reduction_percent = BASE_REDUCTION_PERCENT + (attempt - 1) * REDUCTION_INCREMENT

                await self._update_progress(
                    conversation_id,
                    (attempt - 1) * 30,
                    f"Recovery attempt {attempt}/{self.max_attempts} ({reduction_percent}% reduction)"
                )

                try:
                    # Create checkpoint before aggressive reduction
                    checkpoint_service = get_checkpoint_service()
                    await checkpoint_service.create_checkpoint(
                        conversation_id=conversation_id,
                        user_id=user_id,
                        messages=messages,
                        token_count=context.total_tokens,
                        trigger="error_recovery",
                    )

                    # Perform aggressive context reduction
                    result = await self._reduce_context_aggressively(
                        conversation_id=conversation_id,
                        user_id=user_id,
                        context=context,
                        messages=messages,
                        target_reduction_percent=reduction_percent
                    )

                    if result.success:
                        duration = time.time() - start_time

                        # Record metrics
                        RECOVERY_ATTEMPTS.labels(
                            attempt_number=str(attempt),
                            success="true"
                        ).inc()
                        RECOVERY_LATENCY.labels(attempt_number=str(attempt)).observe(duration)
                        RECOVERY_REDUCTION.labels(attempt_number=str(attempt)).observe(
                            result.reduction_percent
                        )

                        logger.info(
                            "Context recovery successful",
                            conversation_id=conversation_id,
                            attempt=attempt,
                            pre_tokens=result.pre_tokens,
                            post_tokens=result.post_tokens,
                            reduction_percent=round(result.reduction_percent, 1),
                            duration_seconds=round(duration, 2)
                        )

                        await self._update_progress(
                            conversation_id, 100, "Recovery complete"
                        )

                        return (
                            True,
                            f"Recovered from context overflow (attempt {attempt}). "
                            f"Reduced context by {result.reduction_percent:.1f}%.",
                            result
                        )

                    final_result = result

                except Exception as e:
                    logger.warning(
                        "Recovery attempt failed",
                        conversation_id=conversation_id,
                        attempt=attempt,
                        error=str(e)
                    )
                    RECOVERY_ATTEMPTS.labels(
                        attempt_number=str(attempt),
                        success="false"
                    ).inc()

                    # Refresh context and messages for next attempt
                    context, messages = await self._get_context_and_messages(
                        conversation_id, user_id
                    )

            # All attempts failed
            await self._update_progress(
                conversation_id, 100, "Recovery failed"
            )

            return (
                False,
                f"Failed to recover from context overflow after {self.max_attempts} attempts",
                final_result
            )

        finally:
            await self._release_recovery_lock(conversation_id)
            ACTIVE_RECOVERIES.dec()

    # ==========================================================================
    # Aggressive Context Reduction
    # ==========================================================================

    async def _reduce_context_aggressively(
        self,
        conversation_id: str,
        user_id: str,
        context: ConversationContext,
        messages: List[ContextMessage],
        target_reduction_percent: float
    ) -> CompactionResult:
        """
        Aggressively reduce context size by the specified percentage.

        Uses a custom aggressive prompt and may remove non-essential messages
        if AI summarization doesn't achieve the target reduction.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            context: Current conversation context
            messages: List of context messages
            target_reduction_percent: Target reduction percentage

        Returns:
            CompactionResult with reduction details
        """
        # Build aggressive summarization prompt
        aggressive_prompt = self._get_aggressive_reduction_prompt()

        # First try AI-based compaction with aggressive prompt
        result = await self.condensing_engine.compact_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            trigger=CompactionTrigger.FORCE,
            custom_prompt=aggressive_prompt,
            fast=False  # Use full model for better quality in emergency
        )

        # Check if we achieved target reduction
        if result.success and result.reduction_percent >= target_reduction_percent:
            return result

        # If AI compaction wasn't enough, perform additional message removal
        if result.success and result.reduction_percent < target_reduction_percent:
            logger.info(
                "AI compaction insufficient, removing non-essential messages",
                conversation_id=conversation_id,
                achieved=result.reduction_percent,
                target=target_reduction_percent
            )

            # Calculate additional tokens to remove
            current_tokens = result.post_tokens
            target_tokens = int(result.pre_tokens * (1 - target_reduction_percent / 100))
            tokens_to_remove = current_tokens - target_tokens

            if tokens_to_remove > 0:
                # Get fresh messages after compaction
                _, current_messages = await self._get_context_and_messages(
                    conversation_id, user_id
                )

                # Remove non-essential messages
                removed_count = await self._remove_non_essential_messages(
                    context, current_messages, tokens_to_remove
                )

                if removed_count > 0:
                    result.messages_condensed += removed_count
                    result.post_tokens = await self._get_current_token_count(context.id)
                    result.reduction_percent = (
                        (result.pre_tokens - result.post_tokens) / result.pre_tokens * 100
                    )

        return result

    def _get_aggressive_reduction_prompt(self) -> str:
        """Get the aggressive summarization prompt for emergency reduction."""
        return """You are an EMERGENCY context reduction specialist. Your task is to AGGRESSIVELY
condense this conversation to fit within a smaller context window. This is critical to recover
from a context overflow error.

CRITICAL PRESERVATION RULES (in priority order):
1. Code snippets - Keep ALL code blocks VERBATIM, especially recent ones
2. File paths - Preserve all file paths and references
3. Error messages - Keep complete error messages and tracebacks
4. Key decisions - Preserve explicit decisions ("we decided to...", "chosen approach...")
5. Current task state - What is the user currently working on?

AGGRESSIVE REMOVAL RULES:
- Remove ALL pleasantries, greetings, thanks, and social niceties
- Remove explanatory text if code demonstrates the same concept
- Remove older messages that are superseded by newer ones
- Collapse multiple similar messages into single summaries
- Remove redundant confirmations and acknowledgments
- Prioritize RECENT messages over older ones

FORMAT:
[CONTEXT SUMMARY]
- Brief 2-3 sentence overview of conversation purpose

[ACTIVE TASK]
- Current task or problem being solved

[KEY DECISIONS]
- Bullet points of critical decisions made

[TECHNICAL DETAILS]
- Essential code, file paths, and error messages (verbatim)

[RECENT CONTEXT]
- Summary of most recent exchanges

Be EXTREMELY concise. Every token counts."""

    # ==========================================================================
    # Non-Essential Message Removal
    # ==========================================================================

    async def _remove_non_essential_messages(
        self,
        context: ConversationContext,
        messages: List[ContextMessage],
        tokens_to_remove: int
    ) -> int:
        """
        Remove non-essential messages to achieve token reduction target.

        Identifies and removes messages that don't contain essential information
        like code, errors, or key decisions.

        Args:
            context: Conversation context
            messages: List of messages to filter
            tokens_to_remove: Target tokens to remove

        Returns:
            Number of messages removed
        """
        # Identify non-essential messages (oldest first)
        non_essential = [
            msg for msg in messages
            if not msg.is_protected and not self._is_essential_message(msg)
        ]
        non_essential.sort(key=lambda x: x.created_at)

        supabase = get_supabase()
        removed_tokens = 0
        removed_ids = []

        for msg in non_essential:
            if removed_tokens >= tokens_to_remove:
                break

            removed_ids.append(msg.id)
            removed_tokens += msg.token_count

        if removed_ids:
            # Delete messages
            supabase.table("context_messages").delete().in_(
                "id", removed_ids
            ).execute()

            # Update context total tokens
            new_total = context.total_tokens - removed_tokens
            supabase.table("conversation_contexts").update({
                "total_tokens": new_total,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", context.id).execute()

            logger.info(
                "Removed non-essential messages",
                context_id=context.id,
                removed_count=len(removed_ids),
                removed_tokens=removed_tokens
            )

        return len(removed_ids)

    def _is_essential_message(self, message: ContextMessage) -> bool:
        """
        Determine if a message contains essential information.

        Essential messages include those with:
        - Code blocks
        - Error messages
        - File paths
        - Decision language

        Args:
            message: Message to analyze

        Returns:
            True if message is essential
        """
        content = message.content.lower() if message.content else ""

        # Code blocks are essential
        if "```" in content:
            return True

        # Error indicators
        error_patterns = [
            r"error[:\s]",
            r"exception[:\s]",
            r"traceback",
            r"failed[:\s]",
            r"stack\s*trace",
            r"caused\s*by",
        ]
        for pattern in error_patterns:
            if re.search(pattern, content):
                return True

        # File paths are essential
        file_path_pattern = r'[\w\-\.\/\\]+\.[a-zA-Z]{2,4}'
        if re.search(file_path_pattern, content):
            return True

        # Decision language
        decision_phrases = [
            "decided to", "will use", "chosen", "selected",
            "going with", "approach is", "solution is",
            "implemented", "created", "modified", "updated"
        ]
        for phrase in decision_phrases:
            if phrase in content:
                return True

        # Command outputs (indented or formatted)
        if message.role == MessageRole.ASSISTANT:
            # Assistant messages with structured content are often important
            if re.search(r'^[\s]{4,}', content, re.MULTILINE):
                return True

        return False

    # ==========================================================================
    # Lock and Progress Management
    # ==========================================================================

    async def _acquire_recovery_lock(self, conversation_id: str) -> bool:
        """Acquire recovery lock for conversation."""
        try:
            redis = get_redis()
            lock_key = RECOVERY_LOCK_KEY.format(conversation_id=conversation_id)
            result = redis.set(
                lock_key,
                datetime.utcnow().isoformat(),
                ex=RECOVERY_LOCK_TTL,
                nx=True
            )
            return result is True
        except Exception as e:
            logger.error(
                "Failed to acquire recovery lock",
                conversation_id=conversation_id,
                error=str(e)
            )
            return False

    async def _release_recovery_lock(self, conversation_id: str) -> None:
        """Release recovery lock for conversation."""
        try:
            redis = get_redis()
            lock_key = RECOVERY_LOCK_KEY.format(conversation_id=conversation_id)
            redis.delete(lock_key)
        except Exception as e:
            logger.warning(
                "Failed to release recovery lock",
                conversation_id=conversation_id,
                error=str(e)
            )

    async def _update_progress(
        self,
        conversation_id: str,
        percent: int,
        stage: str
    ) -> None:
        """Update recovery progress in Redis."""
        try:
            redis = get_redis()
            progress_key = RECOVERY_PROGRESS_KEY.format(
                conversation_id=conversation_id
            )

            import json
            progress_data = json.dumps({
                "percent": percent,
                "stage": stage,
                "updated_at": datetime.utcnow().isoformat()
            })

            redis.setex(progress_key, RECOVERY_PROGRESS_TTL, progress_data)
        except Exception as e:
            logger.warning(
                "Failed to update recovery progress",
                conversation_id=conversation_id,
                error=str(e)
            )

    async def get_recovery_progress(
        self,
        conversation_id: str
    ) -> Dict[str, Any]:
        """Get current recovery progress."""
        try:
            redis = get_redis()

            # Check if recovery is in progress
            lock_key = RECOVERY_LOCK_KEY.format(conversation_id=conversation_id)
            if not redis.exists(lock_key):
                return {
                    "in_progress": False,
                    "percent": 0,
                    "stage": "Idle"
                }

            # Get progress data
            progress_key = RECOVERY_PROGRESS_KEY.format(
                conversation_id=conversation_id
            )
            data = redis.get(progress_key)

            if data:
                import json
                progress = json.loads(data)
                progress["in_progress"] = True
                return progress

            return {
                "in_progress": True,
                "percent": 0,
                "stage": "Starting"
            }

        except Exception as e:
            logger.warning(
                "Failed to get recovery progress",
                conversation_id=conversation_id,
                error=str(e)
            )
            return {
                "in_progress": False,
                "percent": 0,
                "stage": "Unknown"
            }

    # ==========================================================================
    # Database Operations
    # ==========================================================================

    async def _get_context_and_messages(
        self,
        conversation_id: str,
        user_id: str
    ) -> Tuple[Optional[ConversationContext], List[ContextMessage]]:
        """Get context and messages from database."""
        try:
            supabase = get_supabase()

            # Get context
            ctx_result = supabase.table("conversation_contexts").select(
                "*"
            ).eq("conversation_id", conversation_id).eq(
                "user_id", user_id
            ).single().execute()

            if not ctx_result.data:
                return None, []

            context = ConversationContext(**ctx_result.data)

            # Get messages ordered by position
            msg_result = supabase.table("context_messages").select(
                "*"
            ).eq("context_id", context.id).order(
                "position"
            ).execute()

            messages = [
                ContextMessage(**msg) for msg in (msg_result.data or [])
            ]

            return context, messages

        except Exception as e:
            logger.error(
                "Failed to get context and messages",
                conversation_id=conversation_id,
                error=str(e)
            )
            return None, []

    async def _get_current_token_count(self, context_id: str) -> int:
        """Get current total token count for a context."""
        try:
            supabase = get_supabase()
            result = supabase.table("context_messages").select(
                "token_count"
            ).eq("context_id", context_id).execute()

            return sum(msg["token_count"] for msg in (result.data or []))

        except Exception:
            return 0


# ==============================================================================
# Global Instance
# ==============================================================================

_error_recovery_service: Optional[ContextErrorRecoveryService] = None


def get_error_recovery_service() -> ContextErrorRecoveryService:
    """Get the error recovery service instance."""
    global _error_recovery_service
    if _error_recovery_service is None:
        _error_recovery_service = ContextErrorRecoveryService()
    return _error_recovery_service
