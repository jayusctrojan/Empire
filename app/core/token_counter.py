"""
Empire v7.3 - Token Counter Service
Provides accurate token counting for context window management using tiktoken.

Feature: Chat Context Window Management (011)
"""

import os
from typing import Optional, List
from datetime import datetime
import structlog
from prometheus_client import Counter, Gauge, Histogram

logger = structlog.get_logger(__name__)

# ==============================================================================
# Prometheus Metrics for Token Monitoring
# ==============================================================================

# Counter for total tokens counted across all operations
CONTEXT_TOKENS_COUNTED = Counter(
    'empire_context_tokens_counted_total',
    'Total tokens counted across all context operations',
    ['operation', 'model']  # operation: count_tokens, count_message, count_messages
)

# Gauge for current context usage percentage (per conversation)
CONTEXT_USAGE_PERCENT = Gauge(
    'empire_context_usage_percent',
    'Current context window usage percentage',
    ['conversation_id', 'status']  # status: normal, warning, critical
)

# Counter for context status updates
CONTEXT_STATUS_UPDATES = Counter(
    'empire_context_status_updates_total',
    'Total context status updates',
    ['status', 'model']  # status: normal, warning, critical
)

# Histogram for token count distribution per message
MESSAGE_TOKEN_DISTRIBUTION = Histogram(
    'empire_message_token_count',
    'Distribution of token counts per message',
    ['role'],  # role: user, assistant, system
    buckets=[10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
)

# Counter for context threshold breaches
CONTEXT_THRESHOLD_BREACHES = Counter(
    'empire_context_threshold_breaches_total',
    'Number of times context window threshold was breached',
    ['threshold_type']  # threshold_type: warning (70%), critical (85%)
)

# Model context limits for Claude models
MODEL_CONTEXT_LIMITS = {
    "claude-opus-4-20250514": 200000,
    "claude-sonnet-4-20250514": 200000,
    "claude-3-opus-20240229": 200000,
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-5-sonnet-20240620": 200000,
    "claude-3-sonnet-20240229": 200000,
    "claude-3-5-haiku-20241022": 200000,
    "claude-3-haiku-20240307": 200000,
    # Legacy models
    "claude-2.1": 200000,
    "claude-2.0": 100000,
    # Default fallback
    "default": 200000,
}

# Role token overhead (approximate tokens added by message formatting)
ROLE_TOKEN_OVERHEAD = {
    "system": 4,
    "user": 4,
    "assistant": 4,
}


class TokenCounterError(Exception):
    """Raised when token counting fails"""
    pass


class TokenCounter:
    """
    Token counting service using tiktoken with cl100k_base encoding.

    Provides accurate token counting for Claude models with ~5% accuracy
    compared to actual Anthropic API usage.
    """

    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize the token counter for a specific model.

        Args:
            model: The Claude model ID to use for context limits
        """
        self.model = model
        self.max_tokens = self._get_model_context_limit(model)
        self._encoding = None

    def _get_model_context_limit(self, model: str) -> int:
        """Get the context window limit for a model."""
        return MODEL_CONTEXT_LIMITS.get(model, MODEL_CONTEXT_LIMITS["default"])

    @property
    def encoding(self):
        """Lazy-load tiktoken encoding."""
        if self._encoding is None:
            try:
                import tiktoken
                # cl100k_base is the closest encoding to Claude's tokenizer
                self._encoding = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                logger.warning("tiktoken not installed, falling back to estimation")
                self._encoding = None
            except Exception:
                logger.exception("Failed to load tiktoken encoding")
                self._encoding = None
        return self._encoding

    def count_tokens(self, text: str, record_metrics: bool = True) -> int:
        """
        Count the number of tokens in a text string.

        Args:
            text: The text to count tokens for
            record_metrics: Whether to record Prometheus metrics

        Returns:
            Number of tokens in the text
        """
        if not text:
            return 0

        try:
            if self.encoding is not None:
                token_count = len(self.encoding.encode(text))
            else:
                token_count = self._estimate_tokens(text)

            # Record Prometheus metrics
            if record_metrics:
                CONTEXT_TOKENS_COUNTED.labels(
                    operation="count_tokens",
                    model=self.model
                ).inc(token_count)

            return token_count
        except Exception as e:
            logger.warning("Token counting failed, using estimation", error=str(e))
            return self._estimate_tokens(text)

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count using character-based heuristic.

        Claude typically uses ~4 characters per token on average.
        This provides a conservative estimate.

        Args:
            text: The text to estimate tokens for

        Returns:
            Estimated number of tokens
        """
        if not text:
            return 0
        # Average ~4 characters per token, round up for safety
        return max(1, (len(text) + 3) // 4)

    def count_message_tokens(
        self,
        content: str,
        role: str = "user",
        record_metrics: bool = True
    ) -> int:
        """
        Count tokens for a message including role overhead.

        Args:
            content: Message content
            role: Message role (user, assistant, system)
            record_metrics: Whether to record Prometheus metrics

        Returns:
            Total token count including role overhead
        """
        # Don't double-count - pass False to inner count_tokens
        content_tokens = self.count_tokens(content, record_metrics=False)
        overhead = ROLE_TOKEN_OVERHEAD.get(role, 4)
        total_tokens = content_tokens + overhead

        # Record Prometheus metrics
        if record_metrics:
            CONTEXT_TOKENS_COUNTED.labels(
                operation="count_message",
                model=self.model
            ).inc(total_tokens)

            MESSAGE_TOKEN_DISTRIBUTION.labels(role=role).observe(total_tokens)

        return total_tokens

    def count_messages_tokens(
        self,
        messages: List[dict],
        record_metrics: bool = True
    ) -> int:
        """
        Count total tokens for a list of messages.

        Args:
            messages: List of message dicts with 'content' and 'role' keys
            record_metrics: Whether to record Prometheus metrics

        Returns:
            Total token count for all messages
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "user")
            # Record individual message metrics
            total += self.count_message_tokens(content, role, record_metrics=record_metrics)

        # Record batch operation metric
        if record_metrics:
            CONTEXT_TOKENS_COUNTED.labels(
                operation="count_messages",
                model=self.model
            ).inc(total)

        return total

    def get_usage_percent(
        self,
        current_tokens: int,
        max_tokens: Optional[int] = None
    ) -> float:
        """
        Calculate the percentage of context window used.

        Args:
            current_tokens: Current token count
            max_tokens: Optional max tokens (uses model default if not specified)

        Returns:
            Usage percentage (0-100)
        """
        max_tok = max_tokens or self.max_tokens
        if max_tok <= 0:
            return 0.0
        return min(100.0, (current_tokens / max_tok) * 100)

    def get_status(
        self,
        current_tokens: int,
        max_tokens: Optional[int] = None,
        conversation_id: Optional[str] = None,
        record_metrics: bool = True
    ) -> str:
        """
        Get the context window status based on usage.

        Args:
            current_tokens: Current token count
            max_tokens: Optional max tokens (uses model default if not specified)
            conversation_id: Optional conversation ID for metrics labeling
            record_metrics: Whether to record Prometheus metrics

        Returns:
            Status string: 'normal', 'warning', or 'critical'
        """
        usage_percent = self.get_usage_percent(current_tokens, max_tokens)

        if usage_percent < 70:
            status = "normal"
        elif usage_percent < 85:
            status = "warning"
        else:
            status = "critical"

        # Record Prometheus metrics
        if record_metrics:
            CONTEXT_STATUS_UPDATES.labels(
                status=status,
                model=self.model
            ).inc()

            # Track threshold breaches
            if usage_percent >= 70 and usage_percent < 85:
                CONTEXT_THRESHOLD_BREACHES.labels(threshold_type="warning").inc()
            elif usage_percent >= 85:
                CONTEXT_THRESHOLD_BREACHES.labels(threshold_type="critical").inc()

            # Update usage gauge if conversation_id provided
            if conversation_id:
                CONTEXT_USAGE_PERCENT.labels(
                    conversation_id=conversation_id,
                    status=status
                ).set(usage_percent)

        return status

    def get_available_tokens(
        self,
        current_tokens: int,
        max_tokens: Optional[int] = None,
        reserved_percent: float = 5.0
    ) -> int:
        """
        Calculate available tokens with a safety buffer.

        Args:
            current_tokens: Current token count
            max_tokens: Optional max tokens (uses model default if not specified)
            reserved_percent: Percentage to reserve as safety buffer (default 5%)

        Returns:
            Number of available tokens
        """
        max_tok = max_tokens or self.max_tokens
        reserved = int(max_tok * reserved_percent / 100)
        available = max_tok - current_tokens - reserved
        return max(0, available)

    def estimate_messages_remaining(
        self,
        available_tokens: int,
        avg_tokens_per_message: int = 200
    ) -> int:
        """
        Estimate how many messages can still fit in the context.

        Args:
            available_tokens: Number of available tokens
            avg_tokens_per_message: Average tokens per message (default 200)

        Returns:
            Estimated number of messages that can fit
        """
        if avg_tokens_per_message <= 0:
            return 0
        return max(0, available_tokens // avg_tokens_per_message)


# Global token counter instance with default model
_default_counter: Optional[TokenCounter] = None


def get_token_counter(model: str = "claude-3-5-sonnet-20241022") -> TokenCounter:
    """
    Get a token counter instance for the specified model.

    Uses a cached instance for the default model.

    Args:
        model: Model ID to get counter for

    Returns:
        TokenCounter instance
    """
    global _default_counter

    if model == "claude-3-5-sonnet-20241022":
        if _default_counter is None:
            _default_counter = TokenCounter(model)
        return _default_counter

    return TokenCounter(model)


# Convenience functions
def count_tokens(text: str, record_metrics: bool = True) -> int:
    """Count tokens in text using the default counter."""
    return get_token_counter().count_tokens(text, record_metrics=record_metrics)


def count_message_tokens(content: str, role: str = "user", record_metrics: bool = True) -> int:
    """Count tokens in a message using the default counter."""
    return get_token_counter().count_message_tokens(content, role, record_metrics=record_metrics)


def get_model_context_limit(model: str) -> int:
    """Get the context limit for a model."""
    return MODEL_CONTEXT_LIMITS.get(model, MODEL_CONTEXT_LIMITS["default"])


def update_context_usage_metric(
    conversation_id: str,
    usage_percent: float,
    status: str
) -> None:
    """
    Update the Prometheus gauge for context usage.

    This can be called externally to update the gauge without
    recalculating status.

    Args:
        conversation_id: Conversation ID for labeling
        usage_percent: Current usage percentage
        status: Current status (normal, warning, critical)
    """
    CONTEXT_USAGE_PERCENT.labels(
        conversation_id=conversation_id,
        status=status
    ).set(usage_percent)
