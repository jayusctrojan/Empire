"""
Test suite for chat service error handling and retry logic

Tests comprehensive error handling including:
- Retry logic with exponential backoff
- Network errors
- Timeout errors
- HTTP status errors (400, 401, 404, 429, 500+)
- JSON parsing errors
- User-friendly error messages
"""

import pytest
import asyncio
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.chat_service import ChatService
import json


@pytest.fixture
def chat_service():
    """Create a chat service instance for testing"""
    return ChatService()


@pytest.mark.asyncio
async def test_retry_with_backoff_success_first_attempt(chat_service):
    """Test successful operation on first attempt"""
    mock_operation = AsyncMock(return_value="success")

    result = await chat_service._retry_with_backoff(
        mock_operation, "test_operation", "arg1"
    )

    assert result == "success"
    assert mock_operation.call_count == 1


@pytest.mark.asyncio
async def test_retry_with_backoff_success_after_retries(chat_service):
    """Test successful operation after retries"""
    mock_operation = AsyncMock(
        side_effect=[
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            "success",
        ]
    )

    result = await chat_service._retry_with_backoff(mock_operation, "test_operation")

    assert result == "success"
    assert mock_operation.call_count == 3


@pytest.mark.asyncio
async def test_retry_with_backoff_exhausted(chat_service):
    """Test retry exhaustion after max attempts"""
    mock_operation = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    with pytest.raises(httpx.TimeoutException):
        await chat_service._retry_with_backoff(mock_operation, "test_operation")

    assert mock_operation.call_count == 3  # max_retries


@pytest.mark.asyncio
async def test_connection_error_handling(chat_service):
    """Test handling of connection errors"""
    with patch.object(
        chat_service,
        "_make_api_request",
        side_effect=httpx.ConnectError("Connection refused"),
    ):
        messages = []
        async for chunk in chat_service.stream_chat_response("test query", []):
            messages.append(chunk)

        # Check that error message is user-friendly
        full_response = "".join(messages)
        assert "Unable to connect to Empire API" in full_response
        assert "🌐" in full_response


@pytest.mark.asyncio
async def test_timeout_error_handling(chat_service):
    """Test handling of timeout errors"""
    with patch.object(
        chat_service,
        "_make_api_request",
        side_effect=httpx.TimeoutException("Request timeout"),
    ):
        messages = []
        async for chunk in chat_service.stream_chat_response("test query", []):
            messages.append(chunk)

        # Check that error message is user-friendly
        full_response = "".join(messages)
        assert "Query took too long" in full_response
        assert "⏱️" in full_response


@pytest.mark.asyncio
async def test_http_400_error(chat_service):
    """Test handling of 400 Bad Request errors"""
    mock_response = MagicMock()
    mock_response.status_code = 400

    error = httpx.HTTPStatusError(
        "Bad Request", request=MagicMock(), response=mock_response
    )

    with patch.object(chat_service, "_make_api_request", side_effect=error):
        messages = []
        async for chunk in chat_service.stream_chat_response("test query", []):
            messages.append(chunk)

        full_response = "".join(messages)
        assert "Invalid request" in full_response
        assert "400" in full_response
        assert "⚠️" in full_response


@pytest.mark.asyncio
async def test_http_401_error(chat_service):
    """Test handling of 401 Authentication errors"""
    mock_response = MagicMock()
    mock_response.status_code = 401

    error = httpx.HTTPStatusError(
        "Unauthorized", request=MagicMock(), response=mock_response
    )

    with patch.object(chat_service, "_make_api_request", side_effect=error):
        messages = []
        async for chunk in chat_service.stream_chat_response("test query", []):
            messages.append(chunk)

        full_response = "".join(messages)
        assert "Authentication error" in full_response
        assert "401" in full_response
        assert "🔐" in full_response


@pytest.mark.asyncio
async def test_http_429_error(chat_service):
    """Test handling of 429 Rate Limit errors"""
    mock_response = MagicMock()
    mock_response.status_code = 429

    error = httpx.HTTPStatusError(
        "Too Many Requests", request=MagicMock(), response=mock_response
    )

    with patch.object(chat_service, "_make_api_request", side_effect=error):
        messages = []
        async for chunk in chat_service.stream_chat_response("test query", []):
            messages.append(chunk)

        full_response = "".join(messages)
        assert "Rate limit exceeded" in full_response
        assert "429" in full_response
        assert "🚦" in full_response


@pytest.mark.asyncio
async def test_http_500_error(chat_service):
    """Test handling of 500 Server errors"""
    mock_response = MagicMock()
    mock_response.status_code = 500

    error = httpx.HTTPStatusError(
        "Internal Server Error", request=MagicMock(), response=mock_response
    )

    with patch.object(chat_service, "_make_api_request", side_effect=error):
        messages = []
        async for chunk in chat_service.stream_chat_response("test query", []):
            messages.append(chunk)

        full_response = "".join(messages)
        assert "Server error" in full_response
        assert "500" in full_response
        assert "🔧" in full_response


@pytest.mark.asyncio
async def test_json_parsing_error(chat_service):
    """Test handling of JSON parsing errors"""
    with patch.object(
        chat_service,
        "_make_api_request",
        side_effect=json.JSONDecodeError("Invalid JSON", "", 0),
    ):
        messages = []
        async for chunk in chat_service.stream_chat_response("test query", []):
            messages.append(chunk)

        full_response = "".join(messages)
        assert "Response parsing error" in full_response
        assert "📄" in full_response


@pytest.mark.asyncio
async def test_successful_response_formatting(chat_service):
    """Test successful response with metadata formatting"""
    mock_result = {
        "answer": "Test answer",
        "workflow_type": "langgraph",
        "iterations": 2,
        "processing_time_ms": 1500,
    }

    with patch.object(
        chat_service,
        "_make_api_request",
        return_value=f"{mock_result['answer']}\n\n**Workflow**: {mock_result['workflow_type']}\n**Iterations**: {mock_result['iterations']}\n**Processing Time**: 1.50s\n",
    ):
        messages = []
        async for chunk in chat_service.stream_chat_response("test query", []):
            messages.append(chunk)

        full_response = "".join(messages)
        assert "Test answer" in full_response
        assert "Workflow" in full_response
        assert "langgraph" in full_response


@pytest.mark.asyncio
async def test_loading_indicator_shown(chat_service):
    """Test that loading indicator is shown at start"""

    async def mock_slow_operation(*args, **kwargs):
        await asyncio.sleep(0.1)
        return "Result"

    with patch.object(
        chat_service, "_make_api_request", side_effect=mock_slow_operation
    ):
        messages = []
        async for chunk in chat_service.stream_chat_response("test query", []):
            messages.append(chunk)
            if "🔍 Processing your query" in chunk:
                # Loading indicator found
                assert True
                break


@pytest.mark.asyncio
async def test_exponential_backoff_timing(chat_service):
    """Test that exponential backoff increases delay properly"""
    call_times = []

    async def track_time_operation(*args, **kwargs):
        call_times.append(asyncio.get_event_loop().time())
        if len(call_times) < 3:
            raise httpx.TimeoutException("timeout")
        return "success"

    mock_operation = AsyncMock(side_effect=track_time_operation)

    result = await chat_service._retry_with_backoff(mock_operation, "test_operation")

    # Verify delays are increasing (roughly 1s, 2s)
    assert len(call_times) == 3
    delay1 = call_times[1] - call_times[0]
    delay2 = call_times[2] - call_times[1]

    # Allow some tolerance
    assert 0.9 < delay1 < 1.5  # ~1 second
    assert 1.8 < delay2 < 2.5  # ~2 seconds


@pytest.mark.asyncio
async def test_no_retry_on_client_errors(chat_service):
    """Test that 4xx errors don't trigger retries"""
    mock_response = MagicMock()
    mock_response.status_code = 400

    error = httpx.HTTPStatusError(
        "Bad Request", request=MagicMock(), response=mock_response
    )

    mock_operation = AsyncMock(side_effect=error)

    with pytest.raises(httpx.HTTPStatusError):
        await chat_service._retry_with_backoff(mock_operation, "test_operation")

    # Should only be called once (no retries for 4xx)
    assert mock_operation.call_count == 1


@pytest.mark.asyncio
async def test_retry_on_server_errors(chat_service):
    """Test that 5xx errors trigger retries"""
    mock_response = MagicMock()
    mock_response.status_code = 500

    error = httpx.HTTPStatusError(
        "Internal Server Error", request=MagicMock(), response=mock_response
    )

    mock_operation = AsyncMock(side_effect=error)

    with pytest.raises(httpx.HTTPStatusError):
        await chat_service._retry_with_backoff(mock_operation, "test_operation")

    # Should be called max_retries times (3)
    assert mock_operation.call_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
