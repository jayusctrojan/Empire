"""
Empire v7.3 - Context Condensing Engine
Intelligent summarization of conversation context using Claude AI.

Feature: Chat Context Window Management (011)
Task: 203 - Implement Intelligent Context Condensing Engine
"""

import os
import time
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import uuid4
import structlog
from prometheus_client import Counter, Histogram, Gauge

from app.core.token_counter import (
    TokenCounter,
    get_token_counter,
    count_tokens,
    count_message_tokens,
)
from app.core.database import get_supabase, get_redis
from app.models.context_models import (
    ContextMessage,
    ConversationContext,
    CompactionTrigger,
    CompactionResult,
    MessageRole,
)

# Task 206: Import checkpoint service for pre-compaction snapshots
from app.services.checkpoint_service import get_checkpoint_service

logger = structlog.get_logger(__name__)

# ==============================================================================
# Prometheus Metrics for Compaction Monitoring
# ==============================================================================

COMPACTION_COUNT = Counter(
    'empire_context_compaction_total',
    'Total number of compaction operations',
    ['trigger', 'model', 'success']
)

COMPACTION_LATENCY = Histogram(
    'empire_context_compaction_duration_seconds',
    'Duration of compaction operations',
    ['trigger', 'model'],
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 30.0]
)

COMPACTION_REDUCTION = Histogram(
    'empire_context_compaction_reduction_percent',
    'Token reduction percentage from compaction',
    ['trigger'],
    buckets=[10, 20, 30, 40, 50, 60, 70, 80, 90]
)

COMPACTION_IN_PROGRESS = Gauge(
    'empire_context_compaction_in_progress',
    'Number of compaction operations currently in progress'
)

COMPACTION_COST = Counter(
    'empire_context_compaction_cost_usd_total',
    'Total estimated cost of compaction operations in USD',
    ['model']
)

# ==============================================================================
# Configuration Constants
# ==============================================================================

# Model costs per 1K tokens (approximate, as of 2024)
# Note: Consider replacing with runtime/config lookup to avoid drift
MODEL_COSTS = {
    "claude-3-haiku-20240307": {"input": 0.0008, "output": 0.004},
    "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
    "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
}

# Redis key patterns
COMPACTION_LOCK_KEY = "context:{conversation_id}:compaction_lock"
COMPACTION_PROGRESS_KEY = "context:{conversation_id}:compaction_progress"
LAST_COMPACTION_KEY = "context:{conversation_id}:last_compaction"

# TTLs
COMPACTION_LOCK_TTL = 300  # 5 minutes
COMPACTION_PROGRESS_TTL = 600  # 10 minutes
LAST_COMPACTION_TTL = 86400  # 24 hours

# Cooldown period between compactions (seconds)
COMPACTION_COOLDOWN_SECONDS = 30

# Minimum messages required for compaction
MIN_MESSAGES_FOR_COMPACTION = 3

# Default compaction threshold (percentage)
DEFAULT_COMPACTION_THRESHOLD = 80


class ContextCondensingEngine:
    """
    Intelligent context condensation engine using Claude AI.

    Provides automatic and manual summarization of conversation history
    while preserving critical information like code snippets, decisions,
    and file paths.
    """

    def __init__(
        self,
        model: str = "claude-3-haiku-20240307",
        fast_model: str = "claude-3-5-haiku-20241022"
    ):
        """
        Initialize the condensing engine.

        Args:
            model: Default model for summarization
            fast_model: Fast model for quick compaction
        """
        self.model = model
        self.fast_model = fast_model
        self._token_counter: Optional[TokenCounter] = None
        self._anthropic_client = None
        self._default_prompt: Optional[str] = None

    @property
    def token_counter(self) -> TokenCounter:
        """Get token counter instance."""
        if self._token_counter is None:
            self._token_counter = get_token_counter()
        return self._token_counter

    @property
    def anthropic_client(self):
        """Lazy-load Anthropic client."""
        if self._anthropic_client is None:
            try:
                from anthropic import Anthropic
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY environment variable not set")
                self._anthropic_client = Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError("anthropic package not installed")
        return self._anthropic_client

    @property
    def default_prompt(self) -> str:
        """Load the default summarization prompt."""
        if self._default_prompt is None:
            self._default_prompt = self._load_default_prompt()
        return self._default_prompt

    def _load_default_prompt(self) -> str:
        """Load the summarization prompt from template file."""
        template_path = Path(__file__).parent.parent / "templates" / "summarization_prompt.txt"
        try:
            with open(template_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(
                "Summarization prompt template not found, using default",
                path=str(template_path)
            )
            return self._get_fallback_prompt()

    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if template file not found."""
        return """Summarize this conversation concisely while preserving:
1. All code snippets (verbatim in code blocks)
2. File paths and technical decisions
3. Error messages and resolutions
4. Action items and current state

Provide a structured summary with sections for Context, Decisions, Technical Details, and Pending Items."""

    # ===========================================================================
    # Compaction Eligibility Checks
    # ===========================================================================

    async def should_compact(
        self,
        conversation_id: str,
        current_tokens: int,
        max_tokens: int,
        threshold_percent: int = DEFAULT_COMPACTION_THRESHOLD
    ) -> bool:
        """
        Check if compaction should be triggered.

        Args:
            conversation_id: Conversation ID
            current_tokens: Current token count
            max_tokens: Maximum allowed tokens
            threshold_percent: Threshold percentage for triggering

        Returns:
            True if compaction should be triggered
        """
        try:
            # Check if above threshold
            usage_percent = (current_tokens / max_tokens) * 100 if max_tokens > 0 else 0
            if usage_percent < threshold_percent:
                return False

            # Check cooldown period
            if not await self._check_cooldown(conversation_id):
                logger.debug(
                    "Compaction in cooldown period",
                    conversation_id=conversation_id
                )
                return False

            # Check if compaction already in progress
            if await self._is_compaction_in_progress(conversation_id):
                logger.debug(
                    "Compaction already in progress",
                    conversation_id=conversation_id
                )
                return False

            return True

        except Exception as e:
            logger.error(
                "Failed to check compaction eligibility",
                conversation_id=conversation_id,
                error=str(e)
            )
            return False

    async def _check_cooldown(self, conversation_id: str) -> bool:
        """Check if cooldown period has passed since last compaction."""
        try:
            redis = get_redis()
            key = LAST_COMPACTION_KEY.format(conversation_id=conversation_id)
            last_compaction = redis.get(key)

            if last_compaction:
                last_time = datetime.fromisoformat(last_compaction.decode())
                cooldown_end = last_time + timedelta(seconds=COMPACTION_COOLDOWN_SECONDS)
                if datetime.now(timezone.utc) < cooldown_end:
                    return False

            return True

        except Exception as e:
            logger.warning(
                "Failed to check compaction cooldown",
                conversation_id=conversation_id,
                error=str(e)
            )
            # Allow compaction if we can't check cooldown
            return True

    async def _is_compaction_in_progress(self, conversation_id: str) -> bool:
        """Check if compaction is already in progress."""
        try:
            redis = get_redis()
            lock_key = COMPACTION_LOCK_KEY.format(conversation_id=conversation_id)
            return redis.exists(lock_key)
        except Exception:
            return False

    # ===========================================================================
    # Core Compaction Logic
    # ===========================================================================

    async def compact_conversation(
        self,
        conversation_id: str,
        user_id: str,
        trigger: CompactionTrigger = CompactionTrigger.AUTO,
        custom_prompt: Optional[str] = None,
        fast: bool = False
    ) -> CompactionResult:
        """
        Perform context compaction on a conversation.

        Args:
            conversation_id: Conversation to compact
            user_id: User ID for authorization
            trigger: How compaction was triggered
            custom_prompt: Optional custom summarization prompt
            fast: Use faster model (Claude Haiku)

        Returns:
            CompactionResult with details of the operation
        """
        start_time = time.time()
        model = self.fast_model if fast else self.model
        COMPACTION_IN_PROGRESS.inc()
        lock_acquired = False

        try:
            # Acquire compaction lock
            lock_acquired = await self._acquire_lock(conversation_id)
            if not lock_acquired:
                return CompactionResult(
                    session_id=conversation_id,
                    trigger=trigger,
                    pre_tokens=0,
                    post_tokens=0,
                    reduction_percent=0,
                    messages_condensed=0,
                    summary_preview="Compaction already in progress",
                    duration_ms=0,
                    success=False,
                    error_message="Compaction already in progress for this conversation",
                    model_used=model,
                    created_at=datetime.now(timezone.utc)
                )

            # Update progress
            await self._update_progress(conversation_id, 10, "Fetching messages")

            # Get context and messages from database
            context, messages = await self._get_context_and_messages(
                conversation_id, user_id
            )

            if not context or not messages:
                return CompactionResult(
                    session_id=conversation_id,
                    trigger=trigger,
                    pre_tokens=0,
                    post_tokens=0,
                    reduction_percent=0,
                    messages_condensed=0,
                    summary_preview="No context or messages found",
                    duration_ms=int((time.time() - start_time) * 1000),
                    success=False,
                    error_message="Context or messages not found",
                    model_used=model,
                    created_at=datetime.now(timezone.utc)
                )

            pre_tokens = context.total_tokens

            # Task 206: Create pre-compaction checkpoint
            try:
                checkpoint_service = get_checkpoint_service()
                await checkpoint_service.create_checkpoint(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    messages=messages,
                    token_count=pre_tokens,
                    trigger="pre_compaction",
                )
                logger.info(
                    "Pre-compaction checkpoint created",
                    conversation_id=conversation_id,
                    token_count=pre_tokens
                )
            except Exception as checkpoint_error:
                # Log but don't fail compaction if checkpoint fails
                logger.warning(
                    "Failed to create pre-compaction checkpoint",
                    conversation_id=conversation_id,
                    error=str(checkpoint_error)
                )

            # Filter condensable messages (exclude protected)
            condensable_messages = [
                msg for msg in messages if not msg.is_protected
            ]

            # Check minimum message requirement
            if len(condensable_messages) < MIN_MESSAGES_FOR_COMPACTION:
                return CompactionResult(
                    session_id=conversation_id,
                    trigger=trigger,
                    pre_tokens=pre_tokens,
                    post_tokens=pre_tokens,
                    reduction_percent=0,
                    messages_condensed=0,
                    summary_preview="Too few messages to compact",
                    duration_ms=int((time.time() - start_time) * 1000),
                    success=True,
                    model_used=model,
                    created_at=datetime.now(timezone.utc)
                )

            await self._update_progress(conversation_id, 30, "Preparing for summarization")

            # Prepare messages for summarization
            messages_for_summary = self._prepare_messages_for_summarization(
                condensable_messages
            )

            # Use custom prompt or default
            prompt = custom_prompt if custom_prompt else self.default_prompt

            await self._update_progress(conversation_id, 50, "Summarizing with AI")

            # Call Anthropic API for summarization
            summary, input_tokens, output_tokens = await self._summarize_with_anthropic(
                messages_for_summary,
                prompt,
                model
            )

            await self._update_progress(conversation_id, 70, "Processing summary")

            # Create summary message
            summary_token_count = count_message_tokens(summary, "assistant")
            summary_message_id = str(uuid4())

            await self._update_progress(conversation_id, 80, "Updating database")

            # Update database: delete old messages, insert summary
            await self._apply_compaction_to_database(
                context,
                condensable_messages,
                summary,
                summary_message_id,
                summary_token_count
            )

            # Calculate metrics
            protected_tokens = sum(
                msg.token_count for msg in messages if msg.is_protected
            )
            post_tokens = protected_tokens + summary_token_count

            duration_ms = int((time.time() - start_time) * 1000)
            reduction_percent = (
                ((pre_tokens - post_tokens) / pre_tokens) * 100
                if pre_tokens > 0 else 0
            )

            # Calculate cost
            cost_usd = self._calculate_cost(model, input_tokens, output_tokens)

            await self._update_progress(conversation_id, 90, "Recording compaction")

            # Log compaction result
            result = CompactionResult(
                session_id=conversation_id,
                trigger=trigger,
                pre_tokens=pre_tokens,
                post_tokens=post_tokens,
                reduction_percent=reduction_percent,
                messages_condensed=len(condensable_messages),
                summary_preview=summary[:200] + "..." if len(summary) > 200 else summary,
                summary_full=summary,
                duration_ms=duration_ms,
                cost_usd=cost_usd,
                model_used=model,
                success=True,
                created_at=datetime.now(timezone.utc)
            )

            await self._log_compaction(context.id, result)

            # Update last compaction time
            await self._set_last_compaction_time(conversation_id)

            await self._update_progress(conversation_id, 100, "Completed")

            # Record Prometheus metrics
            COMPACTION_COUNT.labels(
                trigger=trigger.value,
                model=model,
                success="true"
            ).inc()
            COMPACTION_LATENCY.labels(
                trigger=trigger.value,
                model=model
            ).observe(duration_ms / 1000)
            COMPACTION_REDUCTION.labels(trigger=trigger.value).observe(reduction_percent)
            COMPACTION_COST.labels(model=model).inc(cost_usd)

            logger.info(
                "Compaction completed",
                conversation_id=conversation_id,
                pre_tokens=pre_tokens,
                post_tokens=post_tokens,
                reduction_percent=round(reduction_percent, 1),
                messages_condensed=len(condensable_messages),
                duration_ms=duration_ms,
                cost_usd=round(cost_usd, 6)
            )

            return result

        except Exception as e:
            logger.error(
                "Compaction failed",
                conversation_id=conversation_id,
                error=str(e)
            )

            # Record failure metric
            COMPACTION_COUNT.labels(
                trigger=trigger.value,
                model=model,
                success="false"
            ).inc()

            return CompactionResult(
                session_id=conversation_id,
                trigger=trigger,
                pre_tokens=0,
                post_tokens=0,
                reduction_percent=0,
                messages_condensed=0,
                summary_preview=f"Compaction failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000),
                success=False,
                error_message=str(e),
                model_used=model,
                created_at=datetime.now(timezone.utc)
            )

        finally:
            # Only release the lock if we acquired it
            if lock_acquired:
                await self._release_lock(conversation_id)
            COMPACTION_IN_PROGRESS.dec()

    # ===========================================================================
    # Summarization
    # ===========================================================================

    async def _summarize_with_anthropic(
        self,
        messages: List[Dict[str, str]],
        prompt: str,
        model: str
    ) -> tuple[str, int, int]:
        """
        Call Anthropic API for summarization.

        Args:
            messages: List of message dicts with role and content
            prompt: Summarization prompt
            model: Model to use

        Returns:
            Tuple of (summary_text, input_tokens, output_tokens)
        """
        # Format messages for the API
        formatted_content = "\n\n".join([
            f"**{msg['role'].upper()}**: {msg['content']}"
            for msg in messages
        ])

        full_prompt = f"{prompt}\n\n---\n\nHERE IS THE CONVERSATION TO SUMMARIZE:\n\n{formatted_content}"

        try:
            response = self.anthropic_client.messages.create(
                model=model,
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": full_prompt}
                ]
            )

            summary = response.content[0].text
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            return summary, input_tokens, output_tokens

        except Exception as e:
            logger.error("Anthropic API call failed", error=str(e))
            raise

    def _prepare_messages_for_summarization(
        self,
        messages: List[ContextMessage]
    ) -> List[Dict[str, str]]:
        """Convert ContextMessage objects to dict format for API."""
        return [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
        ]

    def _calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate estimated API cost in USD."""
        costs = MODEL_COSTS.get(model, MODEL_COSTS["claude-3-haiku-20240307"])
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        return input_cost + output_cost

    # ===========================================================================
    # Database Operations
    # ===========================================================================

    async def _get_context_and_messages(
        self,
        conversation_id: str,
        user_id: str
    ) -> tuple[Optional[ConversationContext], List[ContextMessage]]:
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

    async def _apply_compaction_to_database(
        self,
        context: ConversationContext,
        condensed_messages: List[ContextMessage],
        summary: str,
        summary_message_id: str,
        summary_token_count: int
    ) -> None:
        """Apply compaction changes to database."""
        try:
            supabase = get_supabase()

            # Get IDs of condensed messages
            condensed_ids = [msg.id for msg in condensed_messages]

            # Delete condensed messages
            supabase.table("context_messages").delete().in_(
                "id", condensed_ids
            ).execute()

            # Get remaining messages to determine summary position
            # Summary should be inserted BEFORE remaining messages chronologically
            remaining_msgs = supabase.table("context_messages").select(
                "id", "position"
            ).eq("context_id", context.id).order(
                "position", desc=False
            ).execute()

            # Insert summary at position 0, shifting existing messages up if needed
            summary_position = 0
            if remaining_msgs.data:
                min_remaining_position = remaining_msgs.data[0]["position"]
                if min_remaining_position == 0:
                    # Position 0 is taken - shift all remaining messages up by 1
                    # to make room for the summary at position 0
                    for msg in remaining_msgs.data:
                        supabase.table("context_messages").update({
                            "position": msg["position"] + 1
                        }).eq("id", msg["id"]).execute()
                else:
                    # There's room before the first remaining message
                    summary_position = min_remaining_position - 1

            # Insert summary message
            supabase.table("context_messages").insert({
                "id": summary_message_id,
                "context_id": context.id,
                "role": "assistant",
                "content": summary,
                "token_count": summary_token_count,
                "is_protected": False,
                "position": summary_position,
                "metadata": json.dumps({
                    "is_summary": True,
                    "condensed_message_ids": condensed_ids,
                    "condensed_count": len(condensed_ids)
                })
            }).execute()

            # Update context total tokens
            remaining_result = supabase.table("context_messages").select(
                "token_count"
            ).eq("context_id", context.id).execute()

            new_total = sum(msg["token_count"] for msg in (remaining_result.data or []))

            supabase.table("conversation_contexts").update({
                "total_tokens": new_total,
                "last_compaction_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", context.id).execute()

        except Exception as e:
            logger.error(
                "Failed to apply compaction to database",
                context_id=context.id,
                error=str(e)
            )
            raise

    async def _log_compaction(
        self,
        context_id: str,
        result: CompactionResult
    ) -> None:
        """Log compaction result to database."""
        try:
            supabase = get_supabase()

            supabase.table("compaction_logs").insert({
                "id": str(uuid4()),
                "context_id": context_id,
                "pre_tokens": result.pre_tokens,
                "post_tokens": result.post_tokens,
                "reduction_percent": result.reduction_percent,
                "summary_preview": result.summary_preview,
                "messages_condensed": result.messages_condensed,
                "model_used": result.model_used,
                "duration_ms": result.duration_ms,
                "triggered_by": result.trigger.value,
                "cost_usd": result.cost_usd,
                "created_at": result.created_at.isoformat()
            }).execute()

        except Exception as e:
            logger.warning(
                "Failed to log compaction result",
                context_id=context_id,
                error=str(e)
            )

    # ===========================================================================
    # Lock and Progress Management
    # ===========================================================================

    async def _acquire_lock(self, conversation_id: str) -> bool:
        """Acquire compaction lock for conversation."""
        try:
            redis = get_redis()
            lock_key = COMPACTION_LOCK_KEY.format(conversation_id=conversation_id)

            # Use SET NX (only set if not exists)
            result = redis.set(
                lock_key,
                datetime.now(timezone.utc).isoformat(),
                ex=COMPACTION_LOCK_TTL,
                nx=True
            )

            return result is True

        except Exception as e:
            logger.error(
                "Failed to acquire compaction lock",
                conversation_id=conversation_id,
                error=str(e)
            )
            return False

    async def _release_lock(self, conversation_id: str) -> None:
        """Release compaction lock for conversation."""
        try:
            redis = get_redis()
            lock_key = COMPACTION_LOCK_KEY.format(conversation_id=conversation_id)
            redis.delete(lock_key)
        except Exception as e:
            logger.warning(
                "Failed to release compaction lock",
                conversation_id=conversation_id,
                error=str(e)
            )

    async def _update_progress(
        self,
        conversation_id: str,
        percent: int,
        stage: str
    ) -> None:
        """Update compaction progress in Redis."""
        try:
            redis = get_redis()
            progress_key = COMPACTION_PROGRESS_KEY.format(
                conversation_id=conversation_id
            )

            progress_data = json.dumps({
                "percent": percent,
                "stage": stage,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })

            redis.setex(progress_key, COMPACTION_PROGRESS_TTL, progress_data)

        except Exception as e:
            logger.warning(
                "Failed to update compaction progress",
                conversation_id=conversation_id,
                error=str(e)
            )

    async def _set_last_compaction_time(self, conversation_id: str) -> None:
        """Record last compaction time for cooldown tracking."""
        try:
            redis = get_redis()
            key = LAST_COMPACTION_KEY.format(conversation_id=conversation_id)
            redis.setex(key, LAST_COMPACTION_TTL, datetime.now(timezone.utc).isoformat())
        except Exception as e:
            logger.warning(
                "Failed to set last compaction time",
                conversation_id=conversation_id,
                error=str(e)
            )

    async def get_compaction_progress(
        self,
        conversation_id: str
    ) -> Dict[str, Any]:
        """Get current compaction progress."""
        try:
            redis = get_redis()
            progress_key = COMPACTION_PROGRESS_KEY.format(
                conversation_id=conversation_id
            )

            data = redis.get(progress_key)
            if data:
                return json.loads(data)

            # Check if lock exists (compaction in progress)
            lock_key = COMPACTION_LOCK_KEY.format(conversation_id=conversation_id)
            if redis.exists(lock_key):
                return {
                    "percent": 0,
                    "stage": "Starting",
                    "in_progress": True
                }

            return {
                "percent": 0,
                "stage": "Idle",
                "in_progress": False
            }

        except Exception as e:
            logger.warning(
                "Failed to get compaction progress",
                conversation_id=conversation_id,
                error=str(e)
            )
            return {
                "percent": 0,
                "stage": "Unknown",
                "in_progress": False
            }


# ==============================================================================
# Global Instance
# ==============================================================================

_condensing_engine: Optional[ContextCondensingEngine] = None


def get_condensing_engine() -> ContextCondensingEngine:
    """Get the context condensing engine instance."""
    global _condensing_engine
    if _condensing_engine is None:
        _condensing_engine = ContextCondensingEngine()
    return _condensing_engine
