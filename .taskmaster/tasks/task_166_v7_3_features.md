# Task ID: 166

**Title:** Enhance Exception Logging

**Status:** cancelled

**Dependencies:** 165 ✗

**Priority:** medium

**Description:** Improve exception handling to include detailed context information for better debugging and observability in production.

**Details:**

Enhance the exception logging in error handlers to include more context:

1. Update `app/middleware/error_handler.py` to include comprehensive logging:
```python
import traceback
import structlog
from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)

async def generic_exception_handler(request: Request, exc: Exception):
    # Extract user ID if available
    user_id = getattr(request.state, "user_id", None) if hasattr(request, "state") else None
    
    # Get request ID from header or generate one
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    
    # Log the exception with context
    logger.exception(
        "Unhandled exception in request",
        error_type=type(exc).__name__,
        error_message=str(exc),
        endpoint=request.url.path,
        method=request.method,
        request_id=request_id,
        user_id=user_id,
        traceback=traceback.format_exc()
    )
    
    # Create standardized error response
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred",
            request_id=request_id
        ).dict()
    )
```

2. Add try-except blocks with enhanced logging in all service methods:
```python
try:
    # Service method implementation
    return result
except Exception as e:
    logger.exception(
        "Error in service method",
        error_type=type(e).__name__,
        error_message=str(e),
        method="method_name",
        params={"param1": value1, "param2": value2},  # Include relevant parameters
        user_id=user_id,
        request_id=request_id
    )
    raise
```

3. Update all custom exception handlers to include similar detailed logging

4. Ensure all logs include the request ID for correlation

5. Register the enhanced exception handler in `app/main.py`:
```python
from app.middleware.error_handler import generic_exception_handler

app = FastAPI()
app.add_exception_handler(Exception, generic_exception_handler)
```

**Test Strategy:**

1. Create unit tests that verify:
   - Exception logs include all required context fields
   - User ID is correctly extracted and included
   - Request ID is properly propagated
   - Stack traces are included for 500 errors

2. Create integration tests that:
   - Trigger various exception types
   - Verify log output contains all required information
   - Check that request context is properly captured
   - Confirm correlation between logs and error responses

3. Test with various request scenarios to ensure all context is properly captured
