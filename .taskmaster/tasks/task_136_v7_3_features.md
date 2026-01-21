# Task ID: 136

**Title:** Implement X-Request-ID Tracing Across Agent Chains

**Status:** done

**Dependencies:** 133 ✓, 122 ✓, 131 ✓

**Priority:** medium

**Description:** Create a middleware and utility functions to generate, propagate, and log X-Request-ID headers throughout the entire agent ecosystem, enabling end-to-end request tracing across multi-agent workflows.

**Details:**

Implement a comprehensive request tracing system using X-Request-ID headers:

1. Create middleware in `app/middleware/request_tracing.py`:
   - Generate a unique UUID for each incoming request if X-Request-ID is not present
   - Extract existing X-Request-ID from incoming requests if available
   - Add the request_id to the request context for access throughout the request lifecycle

2. Create utility functions in `app/utils/tracing.py`:
   - `get_request_id()`: Retrieve the current request_id from context
   - `with_request_id(headers)`: Add the current request_id to outgoing request headers
   - `log_with_request_id(message, level)`: Log with request_id included

3. Modify agent service calls:
   - Update all HTTP client calls to include X-Request-ID header using `with_request_id()`
   - Ensure all CrewAI agent chains propagate the request_id to downstream agents
   - Add request_id to agent context objects for access during execution

4. Update logging configuration:
   - Modify logging formatters to include request_id in all log entries
   - Create a custom log filter to inject request_id into log records

5. Enhance error responses:
   - Update error handling middleware to include request_id in all error responses
   - Add request_id to standardized error response format

6. Add request_id to metrics:
   - Include request_id as a label in Prometheus metrics
   - Enable correlation between metrics and logs

7. Create documentation:
   - Document the request tracing system for developers
   - Provide examples of how to use the tracing utilities

Example middleware implementation:
```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
from contextvars import ContextVar

# Context variable to store request_id
request_id_var = ContextVar("request_id", default=None)

class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract or generate request_id
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Store in context for this request
        token = request_id_var.set(request_id)
        
        # Process request
        response = await call_next(request)
        
        # Add request_id to response headers
        response.headers["X-Request-ID"] = request_id
        
        # Reset context
        request_id_var.reset(token)
        
        return response
```

Example utility functions:
```python
from app.middleware.request_tracing import request_id_var
import logging

def get_request_id():
    """Get the current request ID from context."""
    return request_id_var.get()

def with_request_id(headers=None):
    """Add request_id to headers for outgoing requests."""
    headers = headers or {}
    request_id = get_request_id()
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers

def log_with_request_id(message, level=logging.INFO):
    """Log with request_id included."""
    logger = logging.getLogger()
    request_id = get_request_id()
    extra = {"request_id": request_id} if request_id else {}
    logger.log(level, message, extra=extra)
```

**Test Strategy:**

1. Create unit tests in `tests/middleware/test_request_tracing.py`:
   - Test middleware with no existing X-Request-ID header
   - Test middleware with existing X-Request-ID header
   - Verify request_id is properly stored in context
   - Verify request_id is added to response headers

2. Create unit tests in `tests/utils/test_tracing.py`:
   - Test `get_request_id()` returns correct value
   - Test `with_request_id()` adds header correctly
   - Test `log_with_request_id()` includes request_id in logs

3. Create integration tests in `tests/integration/test_request_tracing.py`:
   - Test request_id propagation through multiple API calls
   - Test request_id propagation through agent chains
   - Verify logs contain consistent request_id across service boundaries

4. Test error scenarios:
   - Verify error responses include request_id
   - Test behavior when invalid request_id is provided

5. Performance testing:
   - Measure overhead of request tracing middleware
   - Verify no significant performance impact

6. Manual testing:
   - Use tools like Postman to trace requests through the system
   - Verify request_id appears in logs and responses
   - Test multi-agent workflows and verify end-to-end tracing

7. Create a test script that:
   - Initiates a complex multi-agent workflow
   - Verifies the same request_id appears in all logs
   - Checks metrics contain the request_id label
   - Validates error responses include the request_id
