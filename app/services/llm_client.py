"""
LLM Client Abstraction Layer

Thin wrapper normalizing Anthropic, OpenAI-compatible (Together AI), and Google
Gemini APIs for easy model swaps via config. Used by CKO conversation service,
vision service, and audio/video processor.
"""

import base64
import os
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional

import anthropic
import openai
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI


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

    async def generate_with_images(
        self,
        system: str,
        prompt: str,
        images: List[Dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> str:
        """Generate a response given text and images.

        Args:
            system: System prompt.
            prompt: User text prompt.
            images: Provider-neutral image list:
                    ``[{"data": bytes, "mime_type": "image/jpeg"}, ...]``
            max_tokens: Max response tokens.
            temperature: Sampling temperature.
            model: Override default model.

        Returns:
            Generated text response.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support generate_with_images"
        )

    def is_retryable(self, error: Exception) -> bool:
        """Return True if *error* is transient and the call should be retried."""
        return False


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

    async def generate_with_images(
        self,
        system: str,
        prompt: str,
        images: List[Dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> str:
        content: List[Dict[str, Any]] = []
        for img in images:
            b64 = base64.b64encode(img["data"]).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{img['mime_type']};base64,{b64}"},
            })
        content.append({"type": "text", "text": prompt})

        response = await self.client.chat.completions.create(
            model=model or self.DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    def is_retryable(self, error: Exception) -> bool:
        return isinstance(
            error,
            (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError),
        )


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

    async def generate_with_images(
        self,
        system: str,
        prompt: str,
        images: List[Dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> str:
        content: List[Dict[str, Any]] = []
        for img in images:
            b64 = base64.b64encode(img["data"]).decode("utf-8")
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img["mime_type"],
                    "data": b64,
                },
            })
        content.append({"type": "text", "text": prompt})

        response = await self.client.messages.create(
            model=model or self.DEFAULT_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text

    def is_retryable(self, error: Exception) -> bool:
        return isinstance(
            error,
            (anthropic.RateLimitError, anthropic.APIConnectionError),
        )


class GeminiLLMClient(LLMClient):
    """Google Gemini client for vision and general generation."""

    DEFAULT_MODEL = "gemini-3-flash-preview"

    def __init__(self, api_key: Optional[str] = None):
        from google import genai

        self._genai = genai
        self.client = genai.Client(
            api_key=api_key or os.environ.get("GOOGLE_API_KEY", ""),
        )

    async def generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> str:
        from google.genai import types

        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg["content"])],
            ))

        response = await self.client.aio.models.generate_content(
            model=model or self.DEFAULT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return response.text or ""

    async def stream(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        from google.genai import types

        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg["content"])],
            ))

        async for chunk in self.client.aio.models.generate_content_stream(
            model=model or self.DEFAULT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        ):
            if chunk.text:
                yield chunk.text

    async def generate_with_images(
        self,
        system: str,
        prompt: str,
        images: List[Dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> str:
        from google.genai import types

        parts: List[types.Part] = []
        for img in images:
            parts.append(types.Part.from_bytes(
                data=img["data"],
                mime_type=img["mime_type"],
            ))
        parts.append(types.Part.from_text(text=prompt))

        response = await self.client.aio.models.generate_content(
            model=model or self.DEFAULT_MODEL,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return response.text or ""

    def is_retryable(self, error: Exception) -> bool:
        error_name = type(error).__name__
        return error_name in ("ServerError", "TooManyRequests") or isinstance(
            error, (ConnectionError, TimeoutError)
        )


_clients: Dict[str, LLMClient] = {}


def get_llm_client(provider: str = "together") -> LLMClient:
    """Factory: get or create an LLM client by provider name."""
    if provider not in _clients:
        if provider == "together":
            _clients[provider] = TogetherLLMClient()
        elif provider == "anthropic":
            _clients[provider] = AnthropicLLMClient()
        elif provider == "gemini":
            _clients[provider] = GeminiLLMClient()
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
    return _clients[provider]
