"""
Empire v7.3 - Chat Service
Integrates Gradio chat UI with Task 46 LangGraph + Arcade.dev endpoints
"""

import os
import httpx
import asyncio
import json
from typing import AsyncIterator, Dict, Any, Optional
from anthropic import Anthropic, AsyncAnthropic
import structlog

logger = structlog.get_logger(__name__)


class ChatService:
    """
    Chat service for integrating with Empire's query endpoints

    Features:
    - Streaming responses from Claude API
    - Integration with Task 46 LangGraph adaptive workflows
    - Auto-routing to optimal workflow (LangGraph/CrewAI/Simple RAG)
    - Token-by-token response streaming for better UX
    - Retry logic with exponential backoff
    - Comprehensive error handling and user-friendly messages
    """

    def __init__(self):
        """Initialize chat service with API clients"""
        self.anthropic_client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.api_base_url = os.getenv(
            "EMPIRE_API_URL",
            "https://jb-empire-api.onrender.com"
        )
        self.timeout = httpx.Timeout(300.0, connect=10.0)  # 5 min for long queries
        self.max_retries = 3
        self.base_backoff_delay = 1.0  # Initial delay in seconds

        logger.info("ChatService initialized", api_url=self.api_base_url)

    async def _retry_with_backoff(
        self,
        operation,
        operation_name: str,
        *args,
        **kwargs
    ):
        """
        Execute operation with exponential backoff retry logic

        Args:
            operation: Async function to execute
            operation_name: Name for logging
            *args, **kwargs: Arguments for the operation

        Returns:
            Result from successful operation

        Raises:
            Exception: If all retries exhausted
        """
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "Attempting operation",
                    operation=operation_name,
                    attempt=attempt,
                    max_retries=self.max_retries
                )
                result = await operation(*args, **kwargs)
                
                if attempt > 1:
                    logger.info(
                        "Operation succeeded after retry",
                        operation=operation_name,
                        attempt=attempt
                    )
                
                return result

            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(
                    "Operation timeout",
                    operation=operation_name,
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(e)
                )
                
                if attempt < self.max_retries:
                    delay = self.base_backoff_delay * (2 ** (attempt - 1))
                    logger.info(
                        "Retrying after backoff",
                        operation=operation_name,
                        delay_seconds=delay
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Operation failed after all retries",
                        operation=operation_name,
                        total_attempts=attempt
                    )

            except httpx.ConnectError as e:
                last_exception = e
                logger.warning(
                    "Connection error",
                    operation=operation_name,
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(e)
                )
                
                if attempt < self.max_retries:
                    delay = self.base_backoff_delay * (2 ** (attempt - 1))
                    logger.info(
                        "Retrying after backoff",
                        operation=operation_name,
                        delay_seconds=delay
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Connection failed after all retries",
                        operation=operation_name,
                        total_attempts=attempt
                    )

            except httpx.HTTPStatusError as e:
                last_exception = e
                logger.error(
                    "HTTP status error",
                    operation=operation_name,
                    status_code=e.response.status_code,
                    attempt=attempt,
                    error=str(e)
                )
                
                # Don't retry on client errors (4xx), only server errors (5xx)
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    delay = self.base_backoff_delay * (2 ** (attempt - 1))
                    logger.info(
                        "Retrying server error after backoff",
                        operation=operation_name,
                        delay_seconds=delay
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "HTTP error not retryable or retries exhausted",
                        operation=operation_name,
                        status_code=e.response.status_code
                    )
                    raise

            except Exception as e:
                last_exception = e
                logger.error(
                    "Unexpected error in operation",
                    operation=operation_name,
                    attempt=attempt,
                    error=str(e),
                    error_type=type(e).__name__
                )
                
                # Don't retry on unexpected errors
                raise

        # If we exhausted all retries, raise the last exception
        raise last_exception

    async def stream_chat_response(
        self,
        message: str,
        history: list[list[str]],
        use_auto_routing: bool = True,
        max_iterations: int = 3
    ) -> AsyncIterator[str]:
        """
        Stream chat response token-by-token with comprehensive error handling

        Args:
            message: User's message
            history: Chat history [[user_msg, assistant_msg], ...]
            use_auto_routing: Use auto-routing vs direct LangGraph (default: True)
            max_iterations: Maximum LangGraph iterations (default: 3)

        Yields:
            Response tokens as they arrive, including progress indicators
        """
        # Yield initial progress indicator
        yield "🔍 Processing your query...\n\n"

        try:
            # Choose endpoint based on routing preference
            endpoint = "/api/query/auto" if use_auto_routing else "/api/query/adaptive"

            logger.info(
                "Starting chat query",
                query_length=len(message),
                endpoint=endpoint,
                max_iterations=max_iterations
            )

            # Wrap the API call with retry logic
            result = await self._retry_with_backoff(
                self._make_api_request,
                "chat_query",
                endpoint,
                message,
                max_iterations
            )

            # Clear progress indicator and show result
            yield result

        except httpx.TimeoutException as e:
            error_msg = (
                "⏱️ **Query took too long. Try a simpler question.**\n\n"
                "The request exceeded the time limit (5 minutes). "
                "Consider breaking down your question into smaller parts or "
                "asking about specific topics."
            )
            logger.error(
                "Query timeout",
                query_length=len(message),
                error=str(e)
            )
            yield error_msg

        except httpx.ConnectError as e:
            error_msg = (
                "🌐 **Unable to connect to Empire API. Please check your connection.**\n\n"
                "The service might be temporarily unavailable. "
                "Please try again in a few moments."
            )
            logger.error(
                "Connection error",
                api_url=self.api_base_url,
                error=str(e)
            )
            yield error_msg

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            
            if status_code == 400:
                error_msg = (
                    f"⚠️ **Invalid request (Error {status_code})**\n\n"
                    "Your query couldn't be processed. Please rephrase your question."
                )
            elif status_code == 401:
                error_msg = (
                    f"🔐 **Authentication error (Error {status_code})**\n\n"
                    "API authentication failed. Please contact the administrator."
                )
            elif status_code == 404:
                error_msg = (
                    f"🔍 **Endpoint not found (Error {status_code})**\n\n"
                    "The requested service endpoint was not found."
                )
            elif status_code == 429:
                error_msg = (
                    f"🚦 **Rate limit exceeded (Error {status_code})**\n\n"
                    "Too many requests. Please wait a moment before trying again."
                )
            elif status_code >= 500:
                error_msg = (
                    f"🔧 **Server error (Error {status_code})**\n\n"
                    "The Empire API encountered an internal error. "
                    "The team has been notified. Please try again later."
                )
            else:
                error_msg = (
                    f"❌ **API error (Error {status_code})**\n\n"
                    "An unexpected error occurred. Please try again."
                )
            
            logger.error(
                "HTTP status error",
                status_code=status_code,
                query_length=len(message),
                error=str(e)
            )
            yield error_msg

        except json.JSONDecodeError as e:
            error_msg = (
                "📄 **Response parsing error**\n\n"
                "Received an invalid response from the API. "
                "This has been logged for investigation."
            )
            logger.error(
                "JSON parsing error",
                query_length=len(message),
                error=str(e),
                error_position=e.pos if hasattr(e, 'pos') else None
            )
            yield error_msg

        except Exception as e:
            error_msg = (
                f"❌ **Unexpected error: {type(e).__name__}**\n\n"
                "An unexpected error occurred while processing your request. "
                "Please try again or contact support if the issue persists.\n\n"
                f"*Technical details: {str(e)}*"
            )
            logger.error(
                "Unexpected error in chat streaming",
                query_length=len(message),
                error=str(e),
                error_type=type(e).__name__
            )
            yield error_msg

    async def _make_api_request(
        self,
        endpoint: str,
        message: str,
        max_iterations: int
    ) -> str:
        """
        Make API request to Empire backend (extracted for retry logic)

        Args:
            endpoint: API endpoint path
            message: User's query
            max_iterations: Maximum iterations for adaptive workflows

        Returns:
            Formatted response string

        Raises:
            Various httpx exceptions that will be handled by retry logic
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Make request to Empire API
            response = await client.post(
                f"{self.api_base_url}{endpoint}",
                json={
                    "query": message,
                    "max_iterations": max_iterations,
                    "stream": False  # Get complete response for easier retry handling
                }
            )
            
            # Raise exception for bad status codes
            response.raise_for_status()

            # Parse JSON response
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                logger.error(
                    "Failed to parse API response as JSON",
                    response_text=response.text[:200],
                    error=str(e)
                )
                raise

            # Extract answer
            answer = result.get("answer", "No answer provided")

            # Format response with metadata
            formatted = f"{answer}\n\n"

            # Add workflow metadata if available
            if "workflow_type" in result:
                formatted += f"**Workflow**: {result['workflow_type']}\n"
            if "iterations" in result and result["iterations"] > 0:
                formatted += f"**Iterations**: {result['iterations']}\n"
            if "processing_time_ms" in result:
                time_s = result['processing_time_ms'] / 1000
                formatted += f"**Processing Time**: {time_s:.2f}s\n"

            logger.info(
                "API request successful",
                endpoint=endpoint,
                workflow_type=result.get("workflow_type"),
                iterations=result.get("iterations", 0)
            )

            return formatted

    async def direct_claude_stream(
        self,
        message: str,
        history: list[list[str]]
    ) -> AsyncIterator[str]:
        """
        Stream response directly from Claude API (bypass Empire endpoints)

        Useful for testing or simple queries without workflow orchestration

        Args:
            message: User's message
            history: Chat history

        Yields:
            Response tokens as they arrive
        """
        try:
            # Convert history to Claude messages format
            messages = []
            for user_msg, assistant_msg in history:
                messages.append({"role": "user", "content": user_msg})
                if assistant_msg:
                    messages.append({"role": "assistant", "content": assistant_msg})

            # Add current message
            messages.append({"role": "user", "content": message})

            logger.info(
                "Starting direct Claude stream",
                message_count=len(messages),
                model=os.getenv("CHAT_MODEL", "claude-3-5-sonnet-20241022")
            )

            # Stream from Claude
            async with self.anthropic_client.messages.stream(
                model=os.getenv("CHAT_MODEL", "claude-3-5-sonnet-20241022"),
                max_tokens=4096,
                messages=messages
            ) as stream:
                async for text in stream.text_stream:
                    yield text

            logger.info("Direct Claude stream completed successfully")

        except Exception as e:
            error_msg = (
                f"❌ **Claude API Error: {type(e).__name__}**\n\n"
                "Failed to get response from Claude API. "
                f"Please try again.\n\n*Technical details: {str(e)}*"
            )
            logger.error(
                "Claude streaming error",
                error=str(e),
                error_type=type(e).__name__
            )
            yield error_msg

    async def get_chat_response(
        self,
        message: str,
        history: list[list[str]],
        use_empire_api: bool = True,
        use_auto_routing: bool = True
    ) -> str:
        """
        Get complete chat response (non-streaming)

        Args:
            message: User's message
            history: Chat history
            use_empire_api: Use Empire API vs direct Claude (default: True)
            use_auto_routing: Use auto-routing when using Empire API (default: True)

        Returns:
            Complete response string
        """
        response_parts = []

        if use_empire_api:
            async for chunk in self.stream_chat_response(
                message, history, use_auto_routing
            ):
                response_parts.append(chunk)
        else:
            async for chunk in self.direct_claude_stream(message, history):
                response_parts.append(chunk)

        return "".join(response_parts)


# Global singleton instance
_chat_service = None


def get_chat_service() -> ChatService:
    """
    Get singleton instance of ChatService

    Returns:
        ChatService instance
    """
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
