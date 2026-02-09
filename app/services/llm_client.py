"""
LLM Client Abstraction Layer

Thin wrapper normalizing Anthropic and OpenAI-compatible APIs (Together AI, etc.)
for easy model swaps via config. Used by CKO conversation service and other
services that need LLM generation.
"""

import os
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Optional

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic


class LLMClient(ABC):
    """Base LLM client interface."""

    @abstractmethod
    async def generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> str:
        """Generate a complete response."""

    @abstractmethod
    async def stream(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream response tokens."""


class TogetherLLMClient(LLMClient):
    """Together AI client (OpenAI-compatible API)."""

    DEFAULT_MODEL = "moonshotai/Kimi-K2.5-Thinking"

    def __init__(self, api_key: Optional[str] = None):
        self.client = AsyncOpenAI(
            api_key=api_key or os.environ.get("TOGETHER_API_KEY", ""),
            base_url="https://api.together.xyz/v1",
        )

    async def generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> str:
        full_messages = [{"role": "system", "content": system}] + messages
        response = await self.client.chat.completions.create(
            model=model or self.DEFAULT_MODEL,
            messages=full_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    async def stream(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        full_messages = [{"role": "system", "content": system}] + messages
        response = await self.client.chat.completions.create(
            model=model or self.DEFAULT_MODEL,
            messages=full_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class AnthropicLLMClient(LLMClient):
    """Anthropic Claude client (fallback)."""

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: Optional[str] = None):
        self.client = AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY", ""),
        )

    async def generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> str:
        response = await self.client.messages.create(
            model=model or self.DEFAULT_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
        )
        return response.content[0].text

    async def stream(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model=model or self.DEFAULT_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text


_clients: Dict[str, LLMClient] = {}


def get_llm_client(provider: str = "together") -> LLMClient:
    """Factory: get or create an LLM client by provider name."""
    if provider not in _clients:
        if provider == "together":
            _clients[provider] = TogetherLLMClient()
        elif provider == "anthropic":
            _clients[provider] = AnthropicLLMClient()
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
    return _clients[provider]
