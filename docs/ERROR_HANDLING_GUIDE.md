# Empire Chat Service - Error Handling Guide

## Overview

This guide documents the comprehensive error handling and loading state features implemented in the Empire chat service and UI. The implementation follows error handling patterns from `app/workflows/langgraph_workflows.py` and provides a robust, user-friendly experience.

## Features

### 1. Retry Logic with Exponential Backoff

**Implementation**: `app/services/chat_service.py`

- **Max Attempts**: 3 retries before failing
- **Backoff Strategy**: Exponential (1s, 2s, 4s delays)
- **Retry Conditions**:
  - ✅ Timeout errors (httpx.TimeoutException)
  - ✅ Connection errors (httpx.ConnectError)
  - ✅ Server errors (5xx status codes)
  - ❌ Client errors (4xx - no retry)
  - ❌ Unexpected errors (no retry)

**Code Example**:
```python
async def _retry_with_backoff(self, operation, operation_name, *args, **kwargs):
    """Execute operation with exponential backoff retry logic"""
    for attempt in range(1, self.max_retries + 1):
        try:
            result = await operation(*args, **kwargs)
            return result
        except httpx.TimeoutException as e:
            if attempt < self.max_retries:
                delay = self.base_backoff_delay * (2 ** (attempt - 1))
                await asyncio.sleep(delay)
            else:
                raise
```

### 2. Error Message Types

All error messages follow a consistent format with:
- **Emoji indicator** for quick visual identification
- **Bold title** with error type and status code
- **User-friendly description** of what went wrong
- **Actionable guidance** on how to resolve

#### Network Errors
```
🌐 Unable to connect to Empire API. Please check your connection.

The service might be temporarily unavailable. Please try again in a few moments.
```

#### Timeout Errors
```
⏱️ Query took too long. Try a simpler question.

The request exceeded the time limit (5 minutes). Consider breaking down your 
question into smaller parts or asking about specific topics.
```

#### HTTP Status Errors

| Status Code | Emoji | Message |
|-------------|-------|---------|
| 400 | ⚠️ | Invalid request - Please rephrase your question |
| 401 | 🔐 | Authentication error - Contact administrator |
| 404 | 🔍 | Endpoint not found |
| 429 | 🚦 | Rate limit exceeded - Wait before trying again |
| 500+ | 🔧 | Server error - Team notified, try later |

#### JSON Parsing Errors
```
📄 Response parsing error

Received an invalid response from the API. This has been logged for investigation.
```

### 3. Structured Logging

**Library**: `structlog`

All errors and operations are logged with structured data for easy filtering and analysis.

**Log Levels**:
- `INFO`: Successful operations, attempt tracking
- `WARNING`: Retryable errors (timeouts, connection issues)
- `ERROR`: Non-retryable errors, exhausted retries

**Example Log Output**:
```json
{
  "event": "Operation timeout",
  "operation": "chat_query",
  "attempt": 1,
  "max_retries": 3,
  "error": "Request timeout",
  "timestamp": "2025-11-08T13:15:00Z",
  "level": "warning"
}
```

**Key Log Points**:
1. Service initialization
2. Query start (with query length, endpoint)
3. Each retry attempt
4. Successful completion (with duration)
5. All error conditions (with context)

### 4. Loading States and Progress Indicators

**Implementation**: `chat_ui.py`

#### Initial Loading Indicator
```
🔍 Processing your query...
```
Shown immediately when query starts, replaced by actual response when ready.

#### Progress Tracking in UI
- Loading indicator appears at start of every query
- Real-time status updates during processing
- Smooth transition from loading to response
- Error states clearly distinguished with color coding

#### Visual Feedback (CSS Styling)
```css
/* Loading messages - Blue background */
.message-wrap:has-text("🔍") {
    background-color: #e7f3ff !important;
    border-left: 4px solid #0366d6 !important;
}

/* Error messages - Red background */
.message-wrap:has-text("❌") {
    background-color: #fee !important;
    border-left: 4px solid #c33 !important;
}

/* Success messages - Green background */
.message-wrap:has-text("✅") {
    background-color: #efe !important;
    border-left: 4px solid #3c3 !important;
}
```

### 5. UI Enhancements

**Updated Features**:
- Status indicator legend in header
- Enhanced error display with emoji icons
- Mobile-responsive design maintained
- Queue management for concurrent requests
- Detailed footer with usage tips

**Status Indicator Legend**:
```
💡 Status Indicators:
- 🔍 = Processing your query
- ⏱️ = Timeout (query too complex)
- 🌐 = Connection issue
- 🔧 = Server error (retrying automatically)
```

## Testing

### Test Suite: `tests/test_chat_service_error_handling.py`

Comprehensive test coverage for:
- ✅ Retry logic (first attempt success, success after retries, exhaustion)
- ✅ All error types (network, timeout, HTTP status codes)
- ✅ Exponential backoff timing
- ✅ User-friendly error messages
- ✅ Loading indicators
- ✅ No retry on client errors (4xx)
- ✅ Retry on server errors (5xx)

**Run Tests**:
```bash
cd Empire
pytest tests/test_chat_service_error_handling.py -v
```

**Expected Output**:
```
test_retry_with_backoff_success_first_attempt PASSED
test_retry_with_backoff_success_after_retries PASSED
test_retry_with_backoff_exhausted PASSED
test_connection_error_handling PASSED
test_timeout_error_handling PASSED
test_http_400_error PASSED
test_http_401_error PASSED
test_http_429_error PASSED
test_http_500_error PASSED
test_json_parsing_error PASSED
test_exponential_backoff_timing PASSED
test_no_retry_on_client_errors PASSED
test_retry_on_server_errors PASSED
```

## Architecture

### Error Flow Diagram

```
User Query
    ↓
chat_ui.py: chat_function()
    ↓
    ├─→ Show loading indicator (🔍)
    ↓
ChatService.stream_chat_response()
    ↓
    ├─→ Call _retry_with_backoff()
    ↓
    ├─→ Attempt 1
    │   ├─→ Success → Return result
    │   └─→ Error → Log & retry
    ↓
    ├─→ Attempt 2 (delay: 1s)
    │   ├─→ Success → Return result
    │   └─→ Error → Log & retry
    ↓
    ├─→ Attempt 3 (delay: 2s)
    │   ├─→ Success → Return result
    │   └─→ Error → Log & fail
    ↓
Error Handler (by type)
    ├─→ NetworkError → 🌐 User message
    ├─→ TimeoutError → ⏱️ User message
    ├─→ HTTPError → Status-specific message
    └─→ JSONError → 📄 User message
    ↓
UI Display
    └─→ Color-coded error message with guidance
```

### Code Organization

```
Empire/
├── app/services/
│   └── chat_service.py          # Core service with error handling
├── chat_ui.py                   # Gradio UI with loading states
├── tests/
│   └── test_chat_service_error_handling.py  # Comprehensive test suite
└── docs/
    └── ERROR_HANDLING_GUIDE.md  # This document
```

## Usage Examples

### Basic Query (Success)
```python
async for chunk in chat_service.stream_chat_response(
    message="What are California insurance requirements?",
    history=[],
    use_auto_routing=True,
    max_iterations=3
):
    print(chunk)
```

**Output**:
```
🔍 Processing your query...

California insurance requirements include...

**Workflow**: langgraph
**Iterations**: 2
**Processing Time**: 1.23s
```

### Query with Retry (Network Issue)
```
🔍 Processing your query...

[Attempt 1] Connection failed
[Wait 1 second]
[Attempt 2] Connection failed
[Wait 2 seconds]
[Attempt 3] Success!

Your answer here...
```

### Query with Error
```
🔍 Processing your query...

🌐 Unable to connect to Empire API. Please check your connection.

The service might be temporarily unavailable. Please try again in a few moments.
```

## Configuration

### Environment Variables

```bash
# .env file
EMPIRE_API_URL=https://jb-empire-api.onrender.com
ANTHROPIC_API_KEY=your_key_here
CHAT_UI_PORT=7860
CHAT_UI_HOST=0.0.0.0
CHAT_MODEL=claude-3-5-sonnet-20241022
```

### Service Configuration

**Timeout Settings**:
```python
self.timeout = httpx.Timeout(300.0, connect=10.0)  # 5 min total, 10s connect
```

**Retry Settings**:
```python
self.max_retries = 3
self.base_backoff_delay = 1.0  # seconds
```

## Best Practices

### For Users
1. **Simple queries first** - Test with basic questions before complex ones
2. **Break down complex questions** - If you get a timeout, simplify
3. **Check error messages** - They provide specific guidance
4. **Use retry button** - UI provides automatic retry for failed queries

### For Developers
1. **Always use structured logging** - Include context in all log calls
2. **Test error conditions** - Use the comprehensive test suite
3. **User-friendly messages** - Never expose raw errors to users
4. **Graceful degradation** - System continues functioning despite errors
5. **Monitor retry rates** - High retry rates indicate infrastructure issues

## Monitoring & Debugging

### Log Analysis

**Find all errors**:
```bash
grep "ERROR" logs/chat_service.log | jq
```

**Find retry attempts**:
```bash
grep "Retrying after backoff" logs/chat_service.log | jq
```

**Find timeout issues**:
```bash
grep "timeout" logs/chat_service.log | jq '.operation, .attempt'
```

### Metrics to Track
- **Retry rate**: Percentage of queries requiring retries
- **Error rate by type**: Network, timeout, HTTP status
- **Average retries**: Number of retries per query
- **Success after retry**: Percentage of queries succeeding after retry

## Future Enhancements

1. **Circuit Breaker Pattern** - Prevent cascading failures
2. **Fallback Strategies** - Alternative endpoints when primary fails
3. **Caching** - Cache successful responses to reduce load
4. **Metrics Dashboard** - Grafana/Prometheus integration
5. **Alert System** - Notify on high error rates
6. **Adaptive Timeouts** - Adjust based on query complexity

## References

- **Pattern Source**: `app/workflows/langgraph_workflows.py` (lines 180-195)
- **Structlog Docs**: https://www.structlog.org/
- **HTTPX Error Handling**: https://www.python-httpx.org/exceptions/
- **Gradio Streaming**: https://www.gradio.app/docs/chatinterface

## Support

For issues or questions:
1. Check this guide first
2. Review test suite for examples
3. Check structured logs for debugging
4. Contact team for infrastructure issues

---

**Last Updated**: November 8, 2025
**Version**: 1.0
**Author**: Empire Development Team
