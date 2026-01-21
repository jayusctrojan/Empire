"""
Unit tests for Context Condensing Engine

Feature: Chat Context Window Management (011)
Task: 203 - Implement Intelligent Context Condensing Engine
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.context_condensing_engine import (
    ContextCondensingEngine,
    get_condensing_engine,
    COMPACTION_COOLDOWN_SECONDS,
    MIN_MESSAGES_FOR_COMPACTION,
)
from app.models.context_models import (
    ContextMessage,
    ConversationContext,
    CompactionTrigger,
    CompactionResult,
    MessageRole,
)


class TestContextCondensingEngine:
    """Tests for ContextCondensingEngine class."""

    @pytest.fixture
    def engine(self):
        """Create engine instance."""
        return ContextCondensingEngine()

    @pytest.fixture
    def mock_context(self):
        """Create mock conversation context."""
        return ConversationContext(
            id="ctx-123",
            conversation_id="conv-123",
            user_id="user-123",
            total_tokens=150000,
            max_tokens=200000,
            threshold_percent=80,
            last_compaction_at=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    @pytest.fixture
    def mock_messages(self):
        """Create mock messages."""
        return [
            ContextMessage(
                id=f"msg-{i}",
                context_id="ctx-123",
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                content=f"Test message content {i}",
                token_count=1000,
                is_protected=i == 0,  # First message is protected
                position=i,
                created_at=datetime.utcnow()
            )
            for i in range(10)
        ]

    # ==========================================================================
    # should_compact Tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_should_compact_below_threshold(self, engine):
        """Should not compact when below threshold."""
        with patch.object(engine, '_check_cooldown', return_value=True):
            with patch.object(engine, '_is_compaction_in_progress', return_value=False):
                result = await engine.should_compact(
                    conversation_id="conv-123",
                    current_tokens=50000,
                    max_tokens=200000,
                    threshold_percent=80
                )
                assert result is False

    @pytest.mark.asyncio
    async def test_should_compact_above_threshold(self, engine):
        """Should compact when above threshold."""
        with patch.object(engine, '_check_cooldown', return_value=True):
            with patch.object(engine, '_is_compaction_in_progress', return_value=False):
                result = await engine.should_compact(
                    conversation_id="conv-123",
                    current_tokens=170000,
                    max_tokens=200000,
                    threshold_percent=80
                )
                assert result is True

    @pytest.mark.asyncio
    async def test_should_compact_in_cooldown(self, engine):
        """Should not compact when in cooldown period."""
        with patch.object(engine, '_check_cooldown', return_value=False):
            result = await engine.should_compact(
                conversation_id="conv-123",
                current_tokens=170000,
                max_tokens=200000,
                threshold_percent=80
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_should_compact_in_progress(self, engine):
        """Should not compact when already in progress."""
        with patch.object(engine, '_check_cooldown', return_value=True):
            with patch.object(engine, '_is_compaction_in_progress', return_value=True):
                result = await engine.should_compact(
                    conversation_id="conv-123",
                    current_tokens=170000,
                    max_tokens=200000,
                    threshold_percent=80
                )
                assert result is False

    # ==========================================================================
    # compact_conversation Tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_compact_conversation_success(self, engine, mock_context, mock_messages):
        """Test successful compaction."""
        with patch.object(engine, '_acquire_lock', return_value=True):
            with patch.object(engine, '_release_lock', return_value=None):
                with patch.object(engine, '_update_progress', return_value=None):
                    with patch.object(
                        engine, '_get_context_and_messages',
                        return_value=(mock_context, mock_messages)
                    ):
                        with patch.object(
                            engine, '_summarize_with_anthropic',
                            return_value=("Summary of conversation", 5000, 500)
                        ):
                            with patch.object(
                                engine, '_apply_compaction_to_database',
                                return_value=None
                            ):
                                with patch.object(
                                    engine, '_log_compaction',
                                    return_value=None
                                ):
                                    with patch.object(
                                        engine, '_set_last_compaction_time',
                                        return_value=None
                                    ):
                                        result = await engine.compact_conversation(
                                            conversation_id="conv-123",
                                            user_id="user-123",
                                            trigger=CompactionTrigger.MANUAL
                                        )

                                        assert result.success is True
                                        assert result.messages_condensed == 9  # 10 - 1 protected
                                        assert result.pre_tokens == 150000

    @pytest.mark.asyncio
    async def test_compact_conversation_lock_failed(self, engine):
        """Test compaction when lock cannot be acquired."""
        with patch.object(engine, '_acquire_lock', return_value=False):
            result = await engine.compact_conversation(
                conversation_id="conv-123",
                user_id="user-123",
                trigger=CompactionTrigger.MANUAL
            )

            assert result.success is False
            assert "already in progress" in result.error_message

    @pytest.mark.asyncio
    async def test_compact_conversation_no_context(self, engine):
        """Test compaction when context not found."""
        with patch.object(engine, '_acquire_lock', return_value=True):
            with patch.object(engine, '_release_lock', return_value=None):
                with patch.object(engine, '_update_progress', return_value=None):
                    with patch.object(
                        engine, '_get_context_and_messages',
                        return_value=(None, [])
                    ):
                        result = await engine.compact_conversation(
                            conversation_id="conv-123",
                            user_id="user-123",
                            trigger=CompactionTrigger.MANUAL
                        )

                        assert result.success is False
                        assert "not found" in result.error_message

    @pytest.mark.asyncio
    async def test_compact_conversation_too_few_messages(
        self, engine, mock_context
    ):
        """Test compaction with too few messages."""
        messages = [
            ContextMessage(
                id="msg-1",
                context_id="ctx-123",
                role=MessageRole.USER,
                content="Single message",
                token_count=100,
                is_protected=False,
                position=0,
                created_at=datetime.utcnow()
            )
        ]

        with patch.object(engine, '_acquire_lock', return_value=True):
            with patch.object(engine, '_release_lock', return_value=None):
                with patch.object(engine, '_update_progress', return_value=None):
                    with patch.object(
                        engine, '_get_context_and_messages',
                        return_value=(mock_context, messages)
                    ):
                        result = await engine.compact_conversation(
                            conversation_id="conv-123",
                            user_id="user-123",
                            trigger=CompactionTrigger.MANUAL
                        )

                        assert result.success is True
                        assert result.messages_condensed == 0
                        assert "Too few" in result.summary_preview

    # ==========================================================================
    # Prompt Loading Tests
    # ==========================================================================

    def test_load_default_prompt(self, engine):
        """Test default prompt is loaded."""
        prompt = engine.default_prompt
        assert prompt is not None
        assert len(prompt) > 0

    def test_get_fallback_prompt(self, engine):
        """Test fallback prompt."""
        prompt = engine._get_fallback_prompt()
        assert "summarize" in prompt.lower()
        assert "code snippets" in prompt.lower()

    # ==========================================================================
    # Message Preparation Tests
    # ==========================================================================

    def test_prepare_messages_for_summarization(self, engine, mock_messages):
        """Test message preparation for API."""
        prepared = engine._prepare_messages_for_summarization(mock_messages)

        assert len(prepared) == 10
        assert all("role" in msg and "content" in msg for msg in prepared)
        assert prepared[0]["role"] == "user"

    # ==========================================================================
    # Cost Calculation Tests
    # ==========================================================================

    def test_calculate_cost_haiku(self, engine):
        """Test cost calculation for Haiku model."""
        cost = engine._calculate_cost(
            model="claude-3-haiku-20240307",
            input_tokens=10000,
            output_tokens=1000
        )

        # Expected: (10000/1000 * 0.00025) + (1000/1000 * 0.00125)
        expected = (10 * 0.00025) + (1 * 0.00125)
        assert abs(cost - expected) < 0.0001

    def test_calculate_cost_sonnet(self, engine):
        """Test cost calculation for Sonnet model."""
        cost = engine._calculate_cost(
            model="claude-3-5-sonnet-20241022",
            input_tokens=10000,
            output_tokens=1000
        )

        # Expected: (10000/1000 * 0.003) + (1000/1000 * 0.015)
        expected = (10 * 0.003) + (1 * 0.015)
        assert abs(cost - expected) < 0.0001


class TestCompactionProgress:
    """Tests for compaction progress tracking."""

    @pytest.fixture
    def engine(self):
        """Create engine instance."""
        return ContextCondensingEngine()

    @pytest.mark.asyncio
    async def test_get_compaction_progress_idle(self, engine):
        """Test progress when no compaction running."""
        with patch('app.services.context_condensing_engine.get_redis') as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis_instance.get.return_value = None
            mock_redis_instance.exists.return_value = False
            mock_redis.return_value = mock_redis_instance

            progress = await engine.get_compaction_progress("conv-123")

            assert progress["in_progress"] is False
            assert progress["stage"] == "Idle"

    @pytest.mark.asyncio
    async def test_get_compaction_progress_in_progress(self, engine):
        """Test progress when compaction is running."""
        import json

        progress_data = json.dumps({
            "percent": 50,
            "stage": "Summarizing with AI",
            "updated_at": datetime.utcnow().isoformat()
        })

        with patch('app.services.context_condensing_engine.get_redis') as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis_instance.get.return_value = progress_data.encode()
            mock_redis.return_value = mock_redis_instance

            progress = await engine.get_compaction_progress("conv-123")

            assert progress["percent"] == 50
            assert progress["stage"] == "Summarizing with AI"


class TestCooldownMechanism:
    """Tests for compaction cooldown."""

    @pytest.fixture
    def engine(self):
        """Create engine instance."""
        return ContextCondensingEngine()

    @pytest.mark.asyncio
    async def test_check_cooldown_no_previous(self, engine):
        """Test cooldown when no previous compaction."""
        with patch('app.services.context_condensing_engine.get_redis') as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis_instance.get.return_value = None
            mock_redis.return_value = mock_redis_instance

            result = await engine._check_cooldown("conv-123")
            assert result is True

    @pytest.mark.asyncio
    async def test_check_cooldown_in_cooldown(self, engine):
        """Test cooldown when still in cooldown period."""
        recent_time = datetime.utcnow().isoformat()

        with patch('app.services.context_condensing_engine.get_redis') as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis_instance.get.return_value = recent_time.encode()
            mock_redis.return_value = mock_redis_instance

            result = await engine._check_cooldown("conv-123")
            assert result is False

    @pytest.mark.asyncio
    async def test_check_cooldown_expired(self, engine):
        """Test cooldown when cooldown period has passed."""
        old_time = (
            datetime.utcnow() - timedelta(seconds=COMPACTION_COOLDOWN_SECONDS + 10)
        ).isoformat()

        with patch('app.services.context_condensing_engine.get_redis') as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis_instance.get.return_value = old_time.encode()
            mock_redis.return_value = mock_redis_instance

            result = await engine._check_cooldown("conv-123")
            assert result is True


class TestPrometheusMetrics:
    """Tests for Prometheus metrics recording."""

    def test_metrics_registered(self):
        """Test that all metrics are registered."""
        from app.services.context_condensing_engine import (
            COMPACTION_COUNT,
            COMPACTION_LATENCY,
            COMPACTION_REDUCTION,
            COMPACTION_IN_PROGRESS,
            COMPACTION_COST,
        )

        # Metrics should exist
        assert COMPACTION_COUNT is not None
        assert COMPACTION_LATENCY is not None
        assert COMPACTION_REDUCTION is not None
        assert COMPACTION_IN_PROGRESS is not None
        assert COMPACTION_COST is not None


class TestGlobalInstance:
    """Tests for global engine instance."""

    def test_get_condensing_engine_singleton(self):
        """Test that get_condensing_engine returns singleton."""
        engine1 = get_condensing_engine()
        engine2 = get_condensing_engine()

        assert engine1 is engine2

    def test_engine_initialization(self):
        """Test engine initializes correctly."""
        engine = get_condensing_engine()

        assert engine.model == "claude-3-haiku-20240307"
        assert engine.fast_model == "claude-3-5-haiku-20241022"
