"""
Empire v7.3 - Chat Service
Integrates Gradio chat UI with Task 46 LangGraph + Arcade.dev endpoints

Task 65: Project-scoped RAG integration
- Project-scoped chat using hybrid RAG endpoint
- Source count display
- Fallback to global-only when no project sources
"""

import os
import httpx
import asyncio
import json
from typing import AsyncIterator, Dict, Any, Optional, Tuple
from anthropic import Anthropic, AsyncAnthropic
from dataclasses import dataclass
import structlog

from app.core.langfuse_config import observe

logger = structlog.get_logger(__name__)


@dataclass
class ProjectChatContext:
    """Context for project-scoped chat"""
    project_id: str
    source_count: int = 0
    ready_source_count: int = 0
    has_sources: bool = False
    project_name: Optional[str] = None


class ChatService:
    """
    Chat service for integrating with Empire's query endpoints

    Features:
    - Streaming responses from Claude API
    - Knowledge base search and retrieval
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

    @observe(name="stream_chat_response")
    async def stream_chat_response(
        self,
        message: str,
        history: list[list[str]],
        use_auto_routing: bool = True,
        max_iterations: int = 3,
        auth_token: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Stream chat response token-by-token with comprehensive error handling

        Args:
            message: User's message
            history: Chat history [[user_msg, assistant_msg], ...]
            use_auto_routing: Use auto-routing vs direct LangGraph (default: True)
            max_iterations: Maximum LangGraph iterations (default: 3)
            auth_token: Clerk JWT token for authentication (optional)

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
                max_iterations,
                auth_token
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
        max_iterations: int,
        auth_token: Optional[str] = None
    ) -> str:
        """
        Make API request to Empire backend (extracted for retry logic)

        Args:
            endpoint: API endpoint path
            message: User's query
            max_iterations: Maximum iterations for adaptive workflows
            auth_token: Clerk JWT token for authentication (optional)

        Returns:
            Formatted response string

        Raises:
            Various httpx exceptions that will be handled by retry logic
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Prepare headers
            headers = {"Content-Type": "application/json"}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

            # Make request to Empire API
            response = await client.post(
                f"{self.api_base_url}{endpoint}",
                json={
                    "query": message,
                    "max_iterations": max_iterations,
                    "stream": False  # Get complete response for easier retry handling
                },
                headers=headers
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

            # Extract answer (already includes inline citations from Task 15)
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

            # Task 15: Add sources footer with citations
            sources_footer = result.get("sources_footer", "")
            if sources_footer:
                formatted += f"\n---\n{sources_footer}\n"

            logger.info(
                "API request successful",
                endpoint=endpoint,
                workflow_type=result.get("workflow_type"),
                iterations=result.get("iterations", 0),
                citations_count=len(result.get("citations", []))
            )

            return formatted

    @observe(name="direct_claude_stream")
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

    # =========================================================================
    # Task 65: Project-Scoped Chat Methods
    # =========================================================================

    async def get_project_context(
        self,
        project_id: str,
        user_id: str,
        auth_token: Optional[str] = None
    ) -> ProjectChatContext:
        """
        Get project context including source counts for display.

        Args:
            project_id: Project ID
            user_id: User ID
            auth_token: Authentication token

        Returns:
            ProjectChatContext with source information
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {"Content-Type": "application/json"}
                if auth_token:
                    headers["Authorization"] = f"Bearer {auth_token}"

                # Get project stats
                response = await client.get(
                    f"{self.api_base_url}/api/projects/{project_id}/sources/stats",
                    headers=headers
                )

                if response.status_code == 200:
                    stats = response.json()
                    ready_count = stats.get("ready_count", 0)
                    total_count = stats.get("total_sources", 0)

                    return ProjectChatContext(
                        project_id=project_id,
                        source_count=total_count,
                        ready_source_count=ready_count,
                        has_sources=ready_count > 0,
                        project_name=stats.get("project_name")
                    )
                else:
                    logger.warning(
                        "Failed to get project stats",
                        project_id=project_id,
                        status_code=response.status_code
                    )

        except Exception as e:
            logger.error(
                "Error getting project context",
                project_id=project_id,
                error=str(e)
            )

        # Return default context on error
        return ProjectChatContext(
            project_id=project_id,
            source_count=0,
            ready_source_count=0,
            has_sources=False
        )

    @observe(name="stream_project_chat_response")
    async def stream_project_chat_response(
        self,
        message: str,
        project_id: str,
        history: list[list[str]],
        auth_token: Optional[str] = None,
        include_global_kb: bool = True,
        enable_query_expansion: bool = True,
    ) -> AsyncIterator[str]:
        """
        Stream project-scoped chat response using hybrid RAG.

        Uses the project RAG endpoint which searches:
        1. Project sources (files, URLs, YouTube) with weight 1.0
        2. Global knowledge base with weight 0.7 (if enabled)

        Args:
            message: User's query
            project_id: Project ID for scoping
            history: Chat history
            auth_token: Authentication token
            include_global_kb: Include global knowledge base (default: True)
            enable_query_expansion: Use query expansion (default: True)

        Yields:
            Response tokens with project-scoped citations
        """
        # Get project context first
        context = await self.get_project_context(
            project_id=project_id,
            user_id="",  # Will be extracted from token
            auth_token=auth_token
        )

        # Show appropriate loading message
        if context.has_sources:
            yield f"🔍 Searching {context.ready_source_count} project source(s) + global knowledge...\n\n"
        else:
            yield "🔍 No project sources available, searching global knowledge base...\n\n"

        try:
            # Use project RAG endpoint if sources available, otherwise fallback
            if context.has_sources:
                result = await self._retry_with_backoff(
                    self._make_project_rag_request,
                    "project_rag_query",
                    project_id,
                    message,
                    auth_token,
                    include_global_kb,
                    enable_query_expansion
                )
            else:
                # Fallback to global-only query
                logger.info(
                    "No project sources, falling back to global query",
                    project_id=project_id
                )
                result = await self._retry_with_backoff(
                    self._make_api_request,
                    "global_fallback_query",
                    "/api/query/auto",
                    message,
                    3,  # max_iterations
                    auth_token
                )

            yield result

        except httpx.TimeoutException as e:
            error_msg = (
                "⏱️ **Query took too long. Try a simpler question.**\n\n"
                "The request exceeded the time limit. Consider asking about "
                "specific topics from your project sources."
            )
            logger.error("Project chat timeout", project_id=project_id, error=str(e))
            yield error_msg

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == 404:
                error_msg = (
                    "🔍 **Project not found**\n\n"
                    "The project may have been deleted or you don't have access."
                )
            elif status_code == 403:
                error_msg = (
                    "🔐 **Access denied**\n\n"
                    "You don't have permission to query this project."
                )
            else:
                error_msg = f"❌ **Error ({status_code})**\n\nFailed to query project sources."

            logger.error("Project chat HTTP error", project_id=project_id, status_code=status_code)
            yield error_msg

        except Exception as e:
            error_msg = (
                f"❌ **Error: {type(e).__name__}**\n\n"
                f"Failed to query project sources. Please try again.\n\n"
                f"*Technical details: {str(e)}*"
            )
            logger.error("Project chat error", project_id=project_id, error=str(e))
            yield error_msg

    async def _make_project_rag_request(
        self,
        project_id: str,
        message: str,
        auth_token: Optional[str],
        include_global_kb: bool,
        enable_query_expansion: bool
    ) -> str:
        """
        Make request to project RAG endpoint.

        Args:
            project_id: Project ID
            message: User query
            auth_token: Auth token
            include_global_kb: Include global KB
            enable_query_expansion: Use query expansion

        Returns:
            Formatted response string
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {"Content-Type": "application/json"}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

            response = await client.post(
                f"{self.api_base_url}/api/projects/{project_id}/rag/query",
                json={
                    "query": message,
                    "include_global_kb": include_global_kb,
                    "enable_query_expansion": enable_query_expansion,
                    "project_source_limit": 8,
                    "global_kb_limit": 5,
                },
                headers=headers
            )

            response.raise_for_status()

            try:
                result = response.json()
            except json.JSONDecodeError as e:
                logger.error("Failed to parse project RAG response", error=str(e))
                raise

            # Extract answer with citations
            answer = result.get("answer", "No answer provided")

            # Format response
            formatted = f"{answer}\n\n"

            # Task 66: Add formatted citation display section
            citations = result.get("citations", [])
            if citations:
                formatted += "---\n"
                formatted += "**📚 Sources:**\n"
                for citation in citations:
                    marker = citation.get("citation_marker", "")
                    title = citation.get("title", "Unknown")
                    file_type = citation.get("file_type", "").upper() if citation.get("file_type") else ""
                    page_num = citation.get("page_number")
                    timestamp = citation.get("youtube_timestamp")
                    link_url = citation.get("link_url")

                    # Build source line with type icon
                    type_icon = self._get_source_type_icon(file_type.lower() if file_type else "")
                    source_line = f"  {marker} {type_icon} **{title}**"

                    # Add page or timestamp info
                    if file_type == "PDF" and page_num:
                        source_line += f" (p.{page_num})"
                    elif file_type == "YOUTUBE" and timestamp:
                        source_line += f" ({self._format_timestamp(timestamp)})"

                    # Add link if available
                    if link_url and file_type in ["YOUTUBE", "WEBSITE"]:
                        source_line += f" — [Open]({link_url})"

                    formatted += source_line + "\n"

                formatted += "\n"

            # Add source metadata summary
            project_count = result.get("project_sources_count", 0)
            global_count = result.get("global_sources_count", 0)

            if project_count > 0 or global_count > 0:
                formatted += f"*{project_count} project source(s), {global_count} global source(s) used*\n"

            # Add processing time
            if "query_time_ms" in result:
                time_s = result["query_time_ms"] / 1000
                formatted += f"*Query time: {time_s:.2f}s*\n"

            logger.info(
                "Project RAG request successful",
                project_id=project_id,
                project_sources=project_count,
                global_sources=global_count,
                citations=len(citations)
            )

            return formatted

    def _get_source_type_icon(self, file_type: str) -> str:
        """Get icon for source type (Task 66)"""
        icons = {
            "pdf": "📄",
            "docx": "📝",
            "doc": "📝",
            "xlsx": "📊",
            "xls": "📊",
            "pptx": "📽️",
            "ppt": "📽️",
            "youtube": "🎥",
            "website": "🌐",
            "txt": "📃",
            "md": "📋",
            "csv": "📈",
        }
        return icons.get(file_type.lower(), "📎")

    def _format_timestamp(self, seconds: int) -> str:
        """Format seconds as MM:SS or HH:MM:SS (Task 66)"""
        if seconds < 3600:
            return f"{seconds // 60}:{seconds % 60:02d}"
        return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

    async def get_project_chat_response(
        self,
        message: str,
        project_id: str,
        history: list[list[str]],
        auth_token: Optional[str] = None
    ) -> str:
        """
        Get complete project-scoped chat response (non-streaming).

        Args:
            message: User's message
            project_id: Project ID
            history: Chat history
            auth_token: Auth token

        Returns:
            Complete response string
        """
        response_parts = []

        async for chunk in self.stream_project_chat_response(
            message=message,
            project_id=project_id,
            history=history,
            auth_token=auth_token
        ):
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
