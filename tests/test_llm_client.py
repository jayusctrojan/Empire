"""Tests for LLM client abstraction layer."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_client import (
    LLMClient,
    TogetherLLMClient,
    AnthropicLLMClient,
    get_llm_client,
    _clients,
)


# ---------------------------------------------------------------------------
# TogetherLLMClient
# ---------------------------------------------------------------------------


class TestTogetherLLMClient:
    """Tests for the Together AI (OpenAI-compatible) LLM client."""

    @pytest.fixture(autouse=True)
    def clear_singletons(self):
        _clients.clear()
        yield
        _clients.clear()

    @pytest.fixture
    def client(self):
        with patch.dict("os.environ", {"TOGETHER_API_KEY": "test-key"}):
            return TogetherLLMClient(api_key="test-key")

    @pytest.mark.asyncio
    async def test_generate_returns_text(self, client):
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello from Kimi"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await client.generate(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert result == "Hello from Kimi"
        client.client.chat.completions.create.assert_awaited_once()
        call_kwargs = client.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "moonshotai/Kimi-K2.5-Thinking"
        assert call_kwargs["messages"][0] == {"role": "system", "content": "You are helpful."}
        assert call_kwargs["messages"][1] == {"role": "user", "content": "Hi"}

    @pytest.mark.asyncio
    async def test_generate_with_custom_model(self, client):
        mock_choice = MagicMock()
        mock_choice.message.content = "Custom model response"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await client.generate(
            system="test",
            messages=[{"role": "user", "content": "test"}],
            model="custom/model-v1",
        )

        call_kwargs = client.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "custom/model-v1"

    @pytest.mark.asyncio
    async def test_generate_handles_none_content(self, client):
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await client.generate(
            system="test",
            messages=[{"role": "user", "content": "test"}],
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self, client):
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello"

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " world"

        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta.content = None  # finish chunk

        async def mock_stream():
            for chunk in [chunk1, chunk2, chunk3]:
                yield chunk

        client.client.chat.completions.create = AsyncMock(return_value=mock_stream())

        tokens = []
        async for token in client.stream(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
        ):
            tokens.append(token)

        assert tokens == ["Hello", " world"]


# ---------------------------------------------------------------------------
# AnthropicLLMClient
# ---------------------------------------------------------------------------


class TestAnthropicLLMClient:
    """Tests for the Anthropic Claude LLM client."""

    @pytest.fixture(autouse=True)
    def clear_singletons(self):
        _clients.clear()
        yield
        _clients.clear()

    @pytest.fixture
    def client(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            return AnthropicLLMClient(api_key="test-key")

    @pytest.mark.asyncio
    async def test_generate_returns_text(self, client):
        mock_content = MagicMock()
        mock_content.text = "Hello from Claude"
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        client.client.messages.create = AsyncMock(return_value=mock_response)

        result = await client.generate(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert result == "Hello from Claude"
        client.client.messages.create.assert_awaited_once()
        call_kwargs = client.client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["system"] == "You are helpful."

    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self, client):
        mock_stream_ctx = AsyncMock()

        async def mock_text_stream():
            for token in ["Hello", " from", " Claude"]:
                yield token

        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_ctx)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_stream_ctx.text_stream = mock_text_stream()

        client.client.messages.stream = MagicMock(return_value=mock_stream_ctx)

        tokens = []
        async for token in client.stream(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
        ):
            tokens.append(token)

        assert tokens == ["Hello", " from", " Claude"]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestGetLLMClient:
    """Tests for the factory function."""

    @pytest.fixture(autouse=True)
    def clear_singletons(self):
        _clients.clear()
        yield
        _clients.clear()

    def test_returns_together_client(self):
        with patch.dict("os.environ", {"TOGETHER_API_KEY": "test"}):
            client = get_llm_client("together")
            assert isinstance(client, TogetherLLMClient)

    def test_returns_anthropic_client(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
            client = get_llm_client("anthropic")
            assert isinstance(client, AnthropicLLMClient)

    def test_caches_clients(self):
        with patch.dict("os.environ", {"TOGETHER_API_KEY": "test"}):
            client1 = get_llm_client("together")
            client2 = get_llm_client("together")
            assert client1 is client2

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm_client("unknown")
