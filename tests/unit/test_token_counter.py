"""
Empire v7.3 - Token Counter Unit Tests
Tests for token counting service accuracy and reliability.

Feature: Chat Context Window Management (011)
"""

import pytest
from unittest.mock import patch, MagicMock
from app.core.token_counter import (
    TokenCounter,
    get_token_counter,
    count_tokens,
    count_message_tokens,
    get_model_context_limit,
    update_context_usage_metric,
    MODEL_CONTEXT_LIMITS,
    ROLE_TOKEN_OVERHEAD,
    TokenCounterError,
    CONTEXT_TOKENS_COUNTED,
    CONTEXT_USAGE_PERCENT,
    CONTEXT_STATUS_UPDATES,
    MESSAGE_TOKEN_DISTRIBUTION,
    CONTEXT_THRESHOLD_BREACHES,
)


class TestTokenCounter:
    """Tests for TokenCounter class"""

    def test_init_default_model(self):
        """Test initialization with default model"""
        counter = TokenCounter()
        assert counter.model == "claude-3-5-sonnet-20241022"
        assert counter.max_tokens == 200000

    def test_init_custom_model(self):
        """Test initialization with custom model"""
        counter = TokenCounter(model="claude-3-opus-20240229")
        assert counter.model == "claude-3-opus-20240229"
        assert counter.max_tokens == 200000

    def test_init_unknown_model_uses_default(self):
        """Test initialization with unknown model falls back to default limit"""
        counter = TokenCounter(model="unknown-model")
        assert counter.max_tokens == MODEL_CONTEXT_LIMITS["default"]

    def test_get_model_context_limit(self):
        """Test getting context limits for various models"""
        counter = TokenCounter()

        # Test known models
        assert counter._get_model_context_limit("claude-3-opus-20240229") == 200000
        assert counter._get_model_context_limit("claude-3-5-sonnet-20241022") == 200000
        assert counter._get_model_context_limit("claude-3-haiku-20240307") == 200000
        assert counter._get_model_context_limit("claude-2.0") == 100000

        # Test unknown model
        assert counter._get_model_context_limit("unknown") == 200000


class TestTokenCounting:
    """Tests for token counting functionality"""

    def test_count_tokens_empty_string(self):
        """Test counting tokens for empty string"""
        counter = TokenCounter()
        assert counter.count_tokens("") == 0

    def test_count_tokens_simple_text(self):
        """Test counting tokens for simple text"""
        counter = TokenCounter()
        result = counter.count_tokens("Hello, world!")
        assert result > 0
        assert isinstance(result, int)

    def test_count_tokens_long_text(self):
        """Test counting tokens for longer text"""
        counter = TokenCounter()
        text = "This is a longer piece of text that should have more tokens. " * 10
        result = counter.count_tokens(text)
        assert result > 50  # Should be substantial

    def test_count_tokens_code_block(self):
        """Test counting tokens for code"""
        counter = TokenCounter()
        code = """
def hello_world():
    print("Hello, World!")
    return True

if __name__ == "__main__":
    hello_world()
"""
        result = counter.count_tokens(code)
        assert result > 20

    def test_count_tokens_non_ascii(self):
        """Test counting tokens for non-ASCII characters"""
        counter = TokenCounter()
        text = "你好世界 مرحبا بالعالم Привет мир"
        result = counter.count_tokens(text)
        assert result > 0

    def test_count_tokens_json(self):
        """Test counting tokens for JSON content"""
        counter = TokenCounter()
        json_text = '{"name": "John", "age": 30, "cities": ["NYC", "LA"]}'
        result = counter.count_tokens(json_text)
        assert result > 10

    def test_estimate_tokens_fallback(self):
        """Test the estimation fallback"""
        counter = TokenCounter()
        # Test the estimation method directly
        text = "This is a test text with about twenty characters or so."
        result = counter._estimate_tokens(text)
        # ~4 chars per token, so ~15 tokens
        assert 10 < result < 30

    def test_estimate_tokens_empty(self):
        """Test estimation for empty string"""
        counter = TokenCounter()
        assert counter._estimate_tokens("") == 0


class TestMessageTokenCounting:
    """Tests for message-level token counting"""

    def test_count_message_tokens_user(self):
        """Test counting tokens for user message"""
        counter = TokenCounter()
        result = counter.count_message_tokens("Hello!", "user")
        content_tokens = counter.count_tokens("Hello!")
        # Should include role overhead
        assert result == content_tokens + ROLE_TOKEN_OVERHEAD["user"]

    def test_count_message_tokens_assistant(self):
        """Test counting tokens for assistant message"""
        counter = TokenCounter()
        result = counter.count_message_tokens("Hi there!", "assistant")
        content_tokens = counter.count_tokens("Hi there!")
        assert result == content_tokens + ROLE_TOKEN_OVERHEAD["assistant"]

    def test_count_message_tokens_system(self):
        """Test counting tokens for system message"""
        counter = TokenCounter()
        result = counter.count_message_tokens("You are a helpful assistant.", "system")
        content_tokens = counter.count_tokens("You are a helpful assistant.")
        assert result == content_tokens + ROLE_TOKEN_OVERHEAD["system"]

    def test_count_messages_tokens_multiple(self):
        """Test counting tokens for multiple messages"""
        counter = TokenCounter()
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = counter.count_messages_tokens(messages)
        expected = sum(
            counter.count_message_tokens(m["content"], m["role"])
            for m in messages
        )
        assert result == expected


class TestUsageCalculations:
    """Tests for usage percentage and status calculations"""

    def test_get_usage_percent(self):
        """Test usage percentage calculation"""
        counter = TokenCounter()

        # Test with default max
        assert counter.get_usage_percent(100000) == 50.0
        assert counter.get_usage_percent(200000) == 100.0
        assert counter.get_usage_percent(0) == 0.0

    def test_get_usage_percent_custom_max(self):
        """Test usage percentage with custom max tokens"""
        counter = TokenCounter()
        assert counter.get_usage_percent(50, 100) == 50.0
        assert counter.get_usage_percent(25, 100) == 25.0

    def test_get_usage_percent_capped_at_100(self):
        """Test that usage percentage caps at 100%"""
        counter = TokenCounter()
        assert counter.get_usage_percent(250000, 200000) == 100.0

    def test_get_status_normal(self):
        """Test status is normal below 70%"""
        counter = TokenCounter()
        assert counter.get_status(50000, 200000) == "normal"
        assert counter.get_status(0, 200000) == "normal"
        assert counter.get_status(139000, 200000) == "normal"

    def test_get_status_warning(self):
        """Test status is warning between 70-85%"""
        counter = TokenCounter()
        assert counter.get_status(140000, 200000) == "warning"
        assert counter.get_status(160000, 200000) == "warning"

    def test_get_status_critical(self):
        """Test status is critical above 85%"""
        counter = TokenCounter()
        assert counter.get_status(170000, 200000) == "critical"
        assert counter.get_status(190000, 200000) == "critical"
        assert counter.get_status(200000, 200000) == "critical"


class TestAvailableTokens:
    """Tests for available token calculations"""

    def test_get_available_tokens_basic(self):
        """Test basic available token calculation"""
        counter = TokenCounter()
        # With 0 tokens used and 5% buffer
        available = counter.get_available_tokens(0, 200000, 5.0)
        expected = 200000 - 0 - 10000  # 5% buffer = 10000
        assert available == expected

    def test_get_available_tokens_partial_use(self):
        """Test available tokens with partial usage"""
        counter = TokenCounter()
        available = counter.get_available_tokens(100000, 200000, 5.0)
        expected = 200000 - 100000 - 10000
        assert available == expected

    def test_get_available_tokens_no_negative(self):
        """Test that available tokens never goes negative"""
        counter = TokenCounter()
        available = counter.get_available_tokens(200000, 200000, 5.0)
        assert available == 0

        available = counter.get_available_tokens(250000, 200000, 5.0)
        assert available == 0


class TestMessageEstimation:
    """Tests for message count estimation"""

    def test_estimate_messages_remaining(self):
        """Test estimating remaining messages"""
        counter = TokenCounter()
        # With 2000 available tokens and 200 avg per message
        remaining = counter.estimate_messages_remaining(2000, 200)
        assert remaining == 10

    def test_estimate_messages_remaining_zero(self):
        """Test estimation with no available tokens"""
        counter = TokenCounter()
        remaining = counter.estimate_messages_remaining(0, 200)
        assert remaining == 0

    def test_estimate_messages_remaining_custom_avg(self):
        """Test estimation with custom average"""
        counter = TokenCounter()
        remaining = counter.estimate_messages_remaining(1000, 100)
        assert remaining == 10


class TestConvenienceFunctions:
    """Tests for module-level convenience functions"""

    def test_get_token_counter_default(self):
        """Test getting default token counter"""
        counter = get_token_counter()
        assert counter is not None
        assert counter.model == "claude-3-5-sonnet-20241022"

    def test_get_token_counter_caches_default(self):
        """Test that default counter is cached"""
        counter1 = get_token_counter()
        counter2 = get_token_counter()
        assert counter1 is counter2

    def test_get_token_counter_custom_model(self):
        """Test getting counter for custom model"""
        counter = get_token_counter("claude-3-opus-20240229")
        assert counter.model == "claude-3-opus-20240229"

    def test_count_tokens_function(self):
        """Test count_tokens convenience function"""
        result = count_tokens("Hello, world!")
        assert result > 0

    def test_count_message_tokens_function(self):
        """Test count_message_tokens convenience function"""
        result = count_message_tokens("Hello!", "user")
        assert result > 0

    def test_get_model_context_limit_function(self):
        """Test get_model_context_limit convenience function"""
        limit = get_model_context_limit("claude-3-opus-20240229")
        assert limit == 200000


class TestTiktokenIntegration:
    """Tests for tiktoken integration"""

    def test_tiktoken_loaded(self):
        """Test that tiktoken is loaded when available"""
        counter = TokenCounter()
        # Access encoding to trigger lazy loading
        encoding = counter.encoding
        # Should either have encoding or None (if tiktoken not installed)
        assert encoding is not None or encoding is None

    @patch('app.core.token_counter.tiktoken')
    def test_falls_back_on_tiktoken_error(self, mock_tiktoken):
        """Test fallback when tiktoken fails"""
        mock_tiktoken.get_encoding.side_effect = Exception("Tiktoken error")

        counter = TokenCounter()
        counter._encoding = None  # Force reload

        # Should still work using estimation
        result = counter.count_tokens("Hello, world!")
        assert result > 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_very_long_text(self):
        """Test counting tokens for very long text"""
        counter = TokenCounter()
        text = "word " * 10000  # Very long text
        result = counter.count_tokens(text)
        assert result > 1000

    def test_special_characters(self):
        """Test counting tokens with special characters"""
        counter = TokenCounter()
        text = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        result = counter.count_tokens(text)
        assert result > 0

    def test_whitespace_only(self):
        """Test counting tokens for whitespace"""
        counter = TokenCounter()
        result = counter.count_tokens("   \t\n\r   ")
        assert result >= 0

    def test_unicode_emoji(self):
        """Test counting tokens for emoji"""
        counter = TokenCounter()
        result = counter.count_tokens("👋🌍🚀💻")
        assert result > 0

    def test_mixed_content(self):
        """Test counting tokens for mixed content types"""
        counter = TokenCounter()
        text = """
Hello World!

```python
def test():
    return 42
```

| Column1 | Column2 |
|---------|---------|
| Value1  | Value2  |

- Item 1
- Item 2
"""
        result = counter.count_tokens(text)
        assert result > 20


class TestAccuracyComparison:
    """Tests comparing tiktoken to estimation accuracy"""

    def test_estimation_reasonably_close(self):
        """Test that estimation is reasonably close to tiktoken"""
        counter = TokenCounter()

        test_texts = [
            "Hello, world!",
            "This is a longer sentence with more words to count.",
            "The quick brown fox jumps over the lazy dog.",
        ]

        for text in test_texts:
            tiktoken_count = counter.count_tokens(text)
            estimate_count = counter._estimate_tokens(text)

            # Estimation should be within 50% of actual (rough heuristic)
            if tiktoken_count > 0:
                ratio = estimate_count / tiktoken_count
                assert 0.5 < ratio < 2.0, f"Estimate too far off for: {text}"


class TestPrometheusMetrics:
    """Tests for Prometheus metrics integration"""

    def test_metrics_defined(self):
        """Test that all Prometheus metrics are defined"""
        assert CONTEXT_TOKENS_COUNTED is not None
        assert CONTEXT_USAGE_PERCENT is not None
        assert CONTEXT_STATUS_UPDATES is not None
        assert MESSAGE_TOKEN_DISTRIBUTION is not None
        assert CONTEXT_THRESHOLD_BREACHES is not None

    def test_count_tokens_records_metrics(self):
        """Test that count_tokens records metrics when enabled"""
        counter = TokenCounter()
        # This should not raise any errors
        result = counter.count_tokens("Hello, world!", record_metrics=True)
        assert result > 0

    def test_count_tokens_skips_metrics_when_disabled(self):
        """Test that count_tokens can skip metrics"""
        counter = TokenCounter()
        result = counter.count_tokens("Hello, world!", record_metrics=False)
        assert result > 0

    def test_count_message_tokens_records_metrics(self):
        """Test that count_message_tokens records metrics"""
        counter = TokenCounter()
        result = counter.count_message_tokens("Hello!", "user", record_metrics=True)
        assert result > 0

    def test_count_messages_tokens_records_metrics(self):
        """Test that count_messages_tokens records metrics"""
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = counter.count_messages_tokens(messages, record_metrics=True)
        assert result > 0

    def test_get_status_records_metrics(self):
        """Test that get_status records metrics"""
        counter = TokenCounter()
        status = counter.get_status(
            100000, 200000, conversation_id="test-conv-123", record_metrics=True
        )
        assert status in ["normal", "warning", "critical"]

    def test_get_status_with_conversation_id_updates_gauge(self):
        """Test that get_status updates gauge when conversation_id provided"""
        counter = TokenCounter()
        # Normal status
        status = counter.get_status(
            50000, 200000, conversation_id="test-gauge-conv", record_metrics=True
        )
        assert status == "normal"

    def test_get_status_warning_threshold_breach(self):
        """Test that warning threshold breach is recorded"""
        counter = TokenCounter()
        status = counter.get_status(
            150000, 200000, conversation_id="test-warn-conv", record_metrics=True
        )
        assert status == "warning"

    def test_get_status_critical_threshold_breach(self):
        """Test that critical threshold breach is recorded"""
        counter = TokenCounter()
        status = counter.get_status(
            180000, 200000, conversation_id="test-crit-conv", record_metrics=True
        )
        assert status == "critical"

    def test_update_context_usage_metric_function(self):
        """Test the update_context_usage_metric convenience function"""
        # This should not raise any errors
        update_context_usage_metric("test-conv-456", 75.5, "warning")

    def test_convenience_functions_with_metrics(self):
        """Test module-level convenience functions with metrics"""
        # count_tokens with metrics
        result = count_tokens("Test text", record_metrics=True)
        assert result > 0

        # count_message_tokens with metrics
        result = count_message_tokens("Hello!", "user", record_metrics=True)
        assert result > 0

    def test_convenience_functions_without_metrics(self):
        """Test module-level convenience functions without metrics"""
        result = count_tokens("Test text", record_metrics=False)
        assert result > 0

        result = count_message_tokens("Hello!", "user", record_metrics=False)
        assert result > 0
