# Task ID: 176

**Title:** Enhance Exception Logging

**Status:** done

**Dependencies:** 175 ✓

**Priority:** medium

**Description:** Improve exception logging to include error type, message, request context, stack trace, and request ID for better debugging and correlation.

**Details:**

1. Enhance the exception logging in `app/middleware/error_handler.py` to include comprehensive information:
```python
import traceback
from fastapi import Request
from fastapi.responses import JSONResponse
from app.models.errors import APIError, InternalError
import structlog

logger = structlog.get_logger(__name__)

async def error_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID")
    user_id = getattr(request.state, "user_id", None) if hasattr(request.state, "user_id") else None
    
    # Collect context information
    context = {
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "endpoint": request.url.path,
        "method": request.method,
        "request_id": request_id,
        "user_id": user_id,
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("User-Agent")
    }
    
    if isinstance(exc, APIError):
        # For known API errors, log at appropriate level
        if exc.status_code >= 500:
            logger.error(f"Server error: {exc.message}", **context)
        else:
            logger.info(f"Client error: {exc.message}", **context)
            
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_response(request_id)
        )
    
    # For unexpected errors, include stack trace
    stack_trace = traceback.format_exc()
    context["stack_trace"] = stack_trace
    
    logger.exception(
        "Unhandled exception in request",
        **context
    )
    
    # Return standardized 500 error
    internal_error = InternalError()
    return JSONResponse(
        status_code=500,
        content=internal_error.to_response(request_id)
    )
```

2. Add a middleware to ensure request IDs are always available:
```python
# app/middleware/request_id.py
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
            request.headers.__dict__["_list"].append(
                (b"x-request-id", request_id.encode())
            )
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

3. Register the middleware in `app/main.py`:
```python
from app.middleware.request_id import RequestIDMiddleware

app = FastAPI()
app.add_middleware(RequestIDMiddleware)
```

**Test Strategy:**

1. Create unit tests that verify:
   - All context fields are properly captured
   - Different error types are logged at appropriate levels
   - Stack traces are included for unexpected errors

2. Create integration tests that:
   - Trigger various error conditions
   - Verify logs contain all required information
   - Check that request IDs are properly propagated

3. Test with different types of requests and error scenarios
