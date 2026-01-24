# Task ID: 175

**Title:** Implement Standardized Error Responses

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Ensure all endpoints use a standardized error format from app/models/errors.py to provide consistent error responses across the API.

**Details:**

1. Enhance `app/models/errors.py` to define a standard error response model:
```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = Field(default=None)
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        schema_extra = {
            "example": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input parameters",
                    "details": {"field": "description of issue"},
                    "request_id": "123e4567-e89b-12d3-a456-426614174000",
                    "timestamp": "2025-01-15T12:00:00Z"
                }
            }
        }

class APIError(Exception):
    def __init__(self, 
                 code: str, 
                 message: str, 
                 status_code: int = 500, 
                 details: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)
        
    def to_response(self, request_id: Optional[str] = None) -> Dict[str, Any]:
        return {
            "error": ErrorResponse(
                code=self.code,
                message=self.message,
                details=self.details,
                request_id=request_id or str(uuid.uuid4())
            ).dict()
        }

# Define standard error types
class ValidationError(APIError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("VALIDATION_ERROR", message, 400, details)

class AuthenticationError(APIError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__("AUTHENTICATION_ERROR", message, 401)

class AuthorizationError(APIError):
    def __init__(self, message: str = "Not authorized"):
        super().__init__("AUTHORIZATION_ERROR", message, 403)

class NotFoundError(APIError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__("NOT_FOUND", message, 404)

class RateLimitedError(APIError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__("RATE_LIMITED", message, 429)

class ExternalServiceError(APIError):
    def __init__(self, message: str = "External service error"):
        super().__init__("EXTERNAL_SERVICE_ERROR", message, 502)

class ServiceUnavailableError(APIError):
    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__("SERVICE_UNAVAILABLE", message, 503)

class InternalError(APIError):
    def __init__(self, message: str = "Internal server error"):
        super().__init__("INTERNAL_ERROR", message, 500)
```

2. Modify `app/middleware/error_handler.py` to use these standardized errors:
```python
from fastapi import Request
from fastapi.responses import JSONResponse
from app.models.errors import APIError, InternalError
import structlog

logger = structlog.get_logger(__name__)

async def error_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID")
    
    if isinstance(exc, APIError):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_response(request_id)
        )
    
    # Handle unexpected errors
    logger.exception(
        "Unhandled exception in request",
        error_type=type(exc).__name__,
        error_message=str(exc),
        endpoint=request.url.path,
        method=request.method,
        request_id=request_id,
        user_id=request.state.user_id if hasattr(request.state, "user_id") else None
    )
    
    internal_error = InternalError()
    return JSONResponse(
        status_code=500,
        content=internal_error.to_response(request_id)
    )
```

3. Update all route handlers to use these error classes instead of raising raw exceptions or returning inconsistent error formats

**Test Strategy:**

1. Create unit tests that verify:
   - Each error type produces the correct status code
   - Error responses have the correct structure
   - Request IDs are properly propagated

2. Create integration tests that:
   - Trigger various error conditions
   - Verify the response format matches the standard
   - Check that all required fields are present

3. Test error handling for different HTTP methods and endpoints

## Subtasks

### 175.1. Create test fixtures for error response testing

**Status:** pending  
**Dependencies:** None  

Create tests/test_error_responses.py with endpoint fixtures to test various error scenarios

**Details:**

Create a new test file with fixtures that can trigger different error conditions. Include setup for validation errors, authentication errors, not found errors, and internal server errors. Set up test client and necessary mocks for external services.

### 175.2. Implement validation error response tests

**Status:** pending  
**Dependencies:** 175.1  

Create tests to verify validation errors return VALIDATION_ERROR code with 400 status

**Details:**

Add test cases that trigger validation errors by sending invalid data to endpoints. Verify the response contains the correct error code 'VALIDATION_ERROR', status code 400, and includes details about which fields failed validation.

### 175.3. Implement external service error response tests

**Status:** pending  
**Dependencies:** 175.1  

Create tests to verify external service errors return EXTERNAL_SERVICE_ERROR code with 502 status

**Details:**

Add test cases that simulate failures in external service calls. Mock external service dependencies to throw exceptions and verify the API returns the correct error code 'EXTERNAL_SERVICE_ERROR' with status code 502.

### 175.4. Implement request metadata tests for error responses

**Status:** pending  
**Dependencies:** 175.1, 175.2, 175.3  

Create tests to verify all errors include request_id and timestamp fields

**Details:**

Add assertions to all error response tests to verify that request_id and timestamp fields are always present and properly formatted. Test with both system-generated request IDs and those provided via X-Request-ID header.

### 175.5. Implement error logging correlation tests

**Status:** pending  
**Dependencies:** 175.4  

Create tests to verify error logs include request_id for correlation with responses

**Details:**

Create test cases that capture log output during error conditions and verify that the request_id in the logs matches the request_id in the error response. Test with both system-generated and client-provided request IDs.

### 175.6. Extend error models with StandardError and ErrorCode enum

**Status:** pending  
**Dependencies:** None  

Enhance app/models/errors.py with StandardError model and ErrorCode enum for consistent error typing

**Details:**

Refactor the error models to use an ErrorCode enum for all error types. Create a StandardError model that extends the existing ErrorResponse with additional fields as needed. Update all error classes to use the enum values for consistent error codes.

### 175.7. Update error handler middleware to use StandardError

**Status:** pending  
**Dependencies:** 175.6  

Modify app/middleware/error_handler.py to use StandardError for all exception types

**Details:**

Update the error handler middleware to convert all exceptions to StandardError instances. Implement specific mapping logic for common exceptions like ValidationError, NotFoundError, etc. Ensure all unhandled exceptions are converted to InternalError with appropriate logging.

### 175.8. Implement request_id extraction and propagation

**Status:** pending  
**Dependencies:** 175.7  

Add middleware to extract X-Request-ID header or generate a new request_id for each request

**Details:**

Create or update middleware to extract the X-Request-ID header from incoming requests. If not present, generate a new UUID. Store the request_id in request.state for use throughout the request lifecycle. Ensure it's propagated to error responses and logs.

### 175.9. Update structlog configuration for request_id inclusion

**Status:** pending  
**Dependencies:** 175.8  

Modify logging configuration to include request_id in all error logs for correlation

**Details:**

Update the structlog configuration to include request_id in the log context. Create a middleware or processor that adds the request_id from request.state to the log context. Ensure all log entries include the request_id field for correlation with API responses.

### 175.10. Implement stack trace logging for 500 errors

**Status:** pending  
**Dependencies:** 175.7, 175.9  

Add detailed stack trace logging only for 500-level internal server errors

**Details:**

Enhance the error handler to capture and log full stack traces only for 500-level errors (InternalError). For other error types, log only essential information. Configure structlog to format stack traces appropriately and ensure they're included in logs for debugging.
