# Task ID: 165

**Title:** Standardize Error Response Format

**Status:** cancelled

**Dependencies:** None

**Priority:** high

**Description:** Ensure all endpoints use a standardized error response format to provide consistent error handling across the API.

**Details:**

Create or update the error models and handlers to ensure standardized error responses:

1. Update `app/models/errors.py` to define standard error response models:
```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

class ErrorDetails(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ErrorResponse(BaseModel):
    error: ErrorDetails

# Define standard error codes
class ErrorCode:
    VALIDATION_ERROR = "VALIDATION_ERROR"  # 400
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"  # 401
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"  # 403
    NOT_FOUND = "NOT_FOUND"  # 404
    RATE_LIMITED = "RATE_LIMITED"  # 429
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"  # 502
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"  # 503
    INTERNAL_ERROR = "INTERNAL_ERROR"  # 500
```

2. Create error factory functions:
```python
def create_error_response(code: str, message: str, details: Dict[str, Any] = None, request_id: str = None) -> ErrorResponse:
    return ErrorResponse(
        error=ErrorDetails(
            code=code,
            message=message,
            details=details,
            request_id=request_id or str(uuid.uuid4()),
            timestamp=datetime.utcnow()
        )
    )
```

3. Update `app/middleware/error_handler.py` to use these standardized formats:
```python
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.models.errors import create_error_response, ErrorCode
import structlog

logger = structlog.get_logger(__name__)

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = {}
    for error in exc.errors():
        loc = "_".join([str(l) for l in error["loc"]])
        details[loc] = error["msg"]
        
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=create_error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message="Validation error",
            details=details,
            request_id=request.headers.get("X-Request-ID")
        ).dict()
    )

# Add similar handlers for other error types
```

4. Update all custom exception handlers to use the standardized format

5. Register the exception handlers in `app/main.py`:
```python
from app.middleware.error_handler import validation_exception_handler
from fastapi.exceptions import RequestValidationError

app = FastAPI()
app.add_exception_handler(RequestValidationError, validation_exception_handler)
# Register other exception handlers
```

**Test Strategy:**

1. Create unit tests that verify:
   - Error response format matches the specification
   - All error codes produce correct status codes
   - Error details are properly included
   - Request ID and timestamp are present

2. Create integration tests that:
   - Trigger various error conditions (validation, auth, not found, etc.)
   - Verify response format is consistent across all error types
   - Check that status codes match the error type
   - Confirm all required fields are present in responses

3. Create a test utility that validates error response structure against the schema
