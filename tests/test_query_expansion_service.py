"""
Tests for Query Expansion Service

Tests query expansion with Kimi K2.5 Thinking (Together AI), expansion strategies,
retry logic, and batch processing.

Run with: python3 -m pytest tests/test_query_expansion_service.py -v
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.services.query_expansion_service import (
    QueryExpansionService,
    QueryExpansionConfig,
    QueryExpansionResult,
    ExpansionStrategy,
    get_query_expansion_service
)


@pytest.fixture
def expansion_config():
    """Create test configuration"""
    return QueryExpansionConfig(
        model="qwen3.5:35b",
        provider="ollama_vlm",
        max_tokens=300,
        temperature=0.7,
        default_num_variations=5,
        max_retries=2,
        initial_retry_delay=0.1,
        timeout_seconds=5.0,
        enable_caching=True
    )


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client"""
    client = Mock()
    client.generate = AsyncMock(return_value="")
    return client


@pytest.fixture
def query_expansion_service(expansion_config):
    """Create query expansion service with mocked LLM client"""
    with patch('app.services.query_expansion_service.get_llm_client') as mock_factory:
        mock_client = Mock()
        mock_client.generate = AsyncMock(return_value="")
        mock_factory.return_value = mock_client

        service = QueryExpansionService(
            expansion_config,
            monitoring_service=None
        )

        yield service


class TestQueryExpansionConfig:
    """Tests for configuration"""

    def test_config_defaults(self):
        """Test default configuration values"""
        config = QueryExpansionConfig()
        assert config.model == "qwen3.5:35b"
        assert config.provider == "ollama_vlm"
        assert config.max_tokens == 300
        assert config.temperature == 0.7
        assert config.default_num_variations == 5
        assert config.max_retries == 3

    def test_config_custom_values(self):
        """Test custom configuration values"""
        config = QueryExpansionConfig(
            model="some-other-model",
            provider="anthropic",
            temperature=0.9,
            max_retries=5
        )
        assert config.model == "some-other-model"
        assert config.provider == "anthropic"
        assert config.temperature == 0.9
        assert config.max_retries == 5


class TestQueryExpansionService:
    """Tests for QueryExpansionService"""

    @pytest.mark.asyncio
    async def test_expand_query_basic(self, query_expansion_service):
        """Test basic query expansion"""
        query_expansion_service.client.generate = AsyncMock(return_value=(
            "insurance policy California\n"
            "California insurance coverage\n"
            "insurance plan California residents\n"
            "CA insurance policy details\n"
            "California state insurance requirements"
        ))

        result = await query_expansion_service.expand_query(
            "California insurance policy",
            num_variations=5,
            strategy=ExpansionStrategy.BALANCED
        )

        assert result.original_query == "California insurance policy"
        assert len(result.expanded_queries) == 6  # 5 + original
        assert "California insurance policy" in result.expanded_queries
        assert result.strategy == "balanced"
        assert result.model_used == "qwen3.5:35b"

    @pytest.mark.asyncio
    async def test_expand_query_synonyms_strategy(self, query_expansion_service):
        """Test query expansion with synonyms strategy"""
        query_expansion_service.client.generate = AsyncMock(return_value=(
            "insurance coverage policy\n"
            "protection policy coverage\n"
            "indemnity policy agreement"
        ))

        result = await query_expansion_service.expand_query(
            "insurance policy",
            num_variations=3,
            strategy=ExpansionStrategy.SYNONYMS,
            include_original=False
        )

        assert len(result.expanded_queries) == 3
        assert "insurance policy" not in result.expanded_queries
        assert result.strategy == "synonyms"

    @pytest.mark.asyncio
    async def test_expand_query_reformulate_strategy(self, query_expansion_service):
        """Test query expansion with reformulation strategy"""
        query_expansion_service.client.generate = AsyncMock(return_value=(
            "What is the California insurance policy?\n"
            "Details about insurance policies in California\n"
            "California state insurance policy information"
        ))

        result = await query_expansion_service.expand_query(
            "California insurance policy",
            num_variations=3,
            strategy=ExpansionStrategy.REFORMULATE
        )

        assert len(result.expanded_queries) == 4  # 3 + original
        assert result.strategy == "reformulate"

    @pytest.mark.asyncio
    async def test_expand_query_question_strategy(self, query_expansion_service):
        """Test query expansion with question strategy"""
        query_expansion_service.client.generate = AsyncMock(return_value=(
            "What is a California insurance policy?\n"
            "How do California insurance policies work?\n"
            "Why do I need a California insurance policy?"
        ))

        result = await query_expansion_service.expand_query(
            "California insurance policy",
            num_variations=3,
            strategy=ExpansionStrategy.QUESTION
        )

        assert len(result.expanded_queries) == 4
        assert any("what" in q.lower() or "how" in q.lower() or "why" in q.lower()
                   for q in result.expanded_queries)

    @pytest.mark.asyncio
    async def test_expand_query_custom_instructions(self, query_expansion_service):
        """Test query expansion with custom instructions"""
        query_expansion_service.client.generate = AsyncMock(return_value=(
            "life insurance policy California residents\n"
            "health insurance policy California requirements"
        ))

        result = await query_expansion_service.expand_query(
            "insurance policy",
            num_variations=2,
            custom_instructions="Focus on life and health insurance"
        )

        assert len(result.expanded_queries) == 3  # 2 + original

    @pytest.mark.asyncio
    async def test_expand_query_empty_query(self, query_expansion_service):
        """Test expansion with empty query"""
        result = await query_expansion_service.expand_query("")

        assert result.original_query == ""
        assert len(result.expanded_queries) == 0
        assert result.tokens_used == 0

    @pytest.mark.asyncio
    async def test_expand_query_short_query(self, query_expansion_service):
        """Test expansion with very short query"""
        result = await query_expansion_service.expand_query("ab")

        assert result.original_query == "ab"
        assert result.tokens_used == 0

    @pytest.mark.asyncio
    async def test_expand_query_caching(self, query_expansion_service):
        """Test query expansion caching"""
        query_expansion_service.client.generate = AsyncMock(
            return_value="insurance coverage\ninsurance plan"
        )

        # First call - should hit API
        result1 = await query_expansion_service.expand_query(
            "insurance",
            num_variations=2
        )
        assert not result1.cached
        assert query_expansion_service.client.generate.call_count == 1

        # Second call - should hit cache
        result2 = await query_expansion_service.expand_query(
            "insurance",
            num_variations=2
        )
        assert result2.cached
        assert query_expansion_service.client.generate.call_count == 1  # No additional call

    @pytest.mark.asyncio
    async def test_expand_query_no_include_original(self, query_expansion_service):
        """Test expansion without including original query"""
        query_expansion_service.client.generate = AsyncMock(
            return_value="coverage plan\nprotection policy"
        )

        result = await query_expansion_service.expand_query(
            "insurance",
            num_variations=2,
            include_original=False
        )

        assert len(result.expanded_queries) == 2
        assert "insurance" not in result.expanded_queries

    @pytest.mark.asyncio
    async def test_expand_query_temperature_override(self, query_expansion_service):
        """Test query expansion with custom temperature"""
        query_expansion_service.client.generate = AsyncMock(
            return_value="query variation"
        )

        result = await query_expansion_service.expand_query(
            "test query",
            temperature=0.9
        )

        # Verify temperature was passed to API
        call_kwargs = query_expansion_service.client.generate.call_args[1]
        assert call_kwargs['temperature'] == 0.9
        assert result.metadata['temperature'] == 0.9

    @pytest.mark.asyncio
    async def test_expand_query_max_variations_limit(self, query_expansion_service):
        """Test that max_variations limit is enforced"""
        # Generate more variations than max
        variations = "\n".join([f"query variation {i}" for i in range(20)])
        query_expansion_service.client.generate = AsyncMock(return_value=variations)

        result = await query_expansion_service.expand_query(
            "test query",
            num_variations=15  # Exceeds max of 10
        )

        # Should be capped at max_variations (10) + original
        assert len(result.expanded_queries) <= 11


class TestRetryLogic:
    """Tests for API retry logic"""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, query_expansion_service):
        """Test retry on rate limit error"""
        # First call fails with rate limit, second succeeds
        query_expansion_service.client.generate = AsyncMock(
            side_effect=[
                Exception("rate limit exceeded"),
                "retry success"
            ]
        )

        result = await query_expansion_service.expand_query("test query")

        assert len(result.expanded_queries) > 0
        assert query_expansion_service.client.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, query_expansion_service):
        """Test behavior when all retries are exhausted"""
        # All calls fail with rate limit
        query_expansion_service.client.generate = AsyncMock(
            side_effect=Exception("rate limit exceeded")
        )

        result = await query_expansion_service.expand_query("test query")

        # Should return original query as fallback
        assert result.original_query == "test query"
        assert "error" in result.metadata
        assert query_expansion_service.client.generate.call_count == 2  # max_retries=2


class TestBatchProcessing:
    """Tests for batch query expansion"""

    @pytest.mark.asyncio
    async def test_expand_batch(self, query_expansion_service):
        """Test batch expansion of multiple queries"""
        query_expansion_service.client.generate = AsyncMock(
            return_value="variation 1\nvariation 2"
        )

        queries = ["query 1", "query 2", "query 3"]
        results = await query_expansion_service.expand_batch(
            queries,
            num_variations=2,
            strategy=ExpansionStrategy.BALANCED
        )

        assert len(results) == 3
        assert all(isinstance(r, QueryExpansionResult) for r in results)
        assert results[0].original_query == "query 1"
        assert results[1].original_query == "query 2"
        assert results[2].original_query == "query 3"

    @pytest.mark.asyncio
    async def test_expand_batch_with_errors(self, query_expansion_service):
        """Test batch expansion with some failures"""
        import asyncio

        # First call succeeds, second times out, third succeeds
        query_expansion_service.client.generate = AsyncMock(
            side_effect=[
                "success variation",
                asyncio.TimeoutError("Timeout"),
                "success variation"
            ]
        )

        queries = ["query 1", "query 2", "query 3"]
        results = await query_expansion_service.expand_batch(queries, num_variations=1)

        assert len(results) == 3
        # First and third should succeed
        assert len(results[0].expanded_queries) > 0
        assert len(results[2].expanded_queries) > 0
        # Second should have error
        assert "error" in results[1].metadata


class TestPromptBuilding:
    """Tests for prompt construction"""

    def test_build_prompt_balanced(self, query_expansion_service):
        """Test prompt building for balanced strategy"""
        prompt = query_expansion_service._build_prompt(
            "test query",
            num_variations=3,
            strategy=ExpansionStrategy.BALANCED,
            custom_instructions=None
        )

        assert "test query" in prompt
        assert "3" in prompt or "three" in prompt.lower()
        assert "diverse" in prompt.lower() or "mix" in prompt.lower()

    def test_build_prompt_synonyms(self, query_expansion_service):
        """Test prompt building for synonyms strategy"""
        prompt = query_expansion_service._build_prompt(
            "test query",
            num_variations=3,
            strategy=ExpansionStrategy.SYNONYMS,
            custom_instructions=None
        )

        assert "synonym" in prompt.lower()

    def test_build_prompt_with_custom_instructions(self, query_expansion_service):
        """Test prompt building with custom instructions"""
        prompt = query_expansion_service._build_prompt(
            "test query",
            num_variations=3,
            strategy=ExpansionStrategy.BALANCED,
            custom_instructions="Focus on technical terms"
        )

        assert "Focus on technical terms" in prompt


class TestUtilities:
    """Tests for utility functions"""

    def test_parse_response_text_numbered_list(self, query_expansion_service):
        """Test parsing response with numbered list"""
        text = (
            "1. First query\n"
            "2. Second query\n"
            "3. Third query"
        )

        queries = query_expansion_service._parse_response_text(text, 3)

        assert len(queries) == 3
        assert queries[0] == "First query"
        assert queries[1] == "Second query"
        assert queries[2] == "Third query"

    def test_parse_response_text_bulleted_list(self, query_expansion_service):
        """Test parsing response with bulleted list"""
        text = (
            "- First query\n"
            "• Second query\n"
            "* Third query"
        )

        queries = query_expansion_service._parse_response_text(text, 3)

        assert len(queries) == 3
        assert queries[0] == "First query"

    def test_parse_response_text_with_quotes(self, query_expansion_service):
        """Test parsing response with quoted queries"""
        text = (
            '"First query"\n'
            "'Second query'\n"
            "Third query"
        )

        queries = query_expansion_service._parse_response_text(text, 3)

        assert len(queries) == 3
        assert queries[0] == "First query"
        assert queries[1] == "Second query"

    def test_parse_response_text_empty(self, query_expansion_service):
        """Test parsing empty response"""
        queries = query_expansion_service._parse_response_text("", 3)

        assert len(queries) == 0

    def test_clear_cache(self, query_expansion_service):
        """Test cache clearing"""
        # Add something to cache
        query_expansion_service._cache["test_key"] = Mock()
        assert len(query_expansion_service._cache) > 0

        query_expansion_service.clear_cache()
        assert len(query_expansion_service._cache) == 0

    def test_get_cache_stats(self, query_expansion_service):
        """Test cache statistics"""
        stats = query_expansion_service.get_cache_stats()

        assert "cache_size" in stats
        assert "cache_enabled" in stats
        assert stats["cache_enabled"] is True


class TestFactoryFunction:
    """Tests for factory function"""

    def test_get_query_expansion_service_singleton(self):
        """Test that factory returns singleton"""
        with patch('app.services.query_expansion_service.get_llm_client'):
            # Reset singleton
            import app.services.query_expansion_service as mod
            mod._query_expansion_service = None

            service1 = get_query_expansion_service()
            service2 = get_query_expansion_service()

            assert service1 is service2

            # Clean up singleton
            mod._query_expansion_service = None
