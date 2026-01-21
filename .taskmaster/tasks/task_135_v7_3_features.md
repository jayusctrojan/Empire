# Task ID: 135

**Title:** Implement Standardized Error Response Model and Handling

**Status:** done

**Dependencies:** 107 ✓, 110 ✓, 125 ✓, 129 ✓

**Priority:** medium

**Description:** Create a standardized error response model and consistent error handling across all agents with a centralized error_handler middleware.

**Details:**

Implement a standardized approach to error handling across all agent routes:

1. Create `app/models/errors.py` with the following structure:
```python
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ErrorType(str, Enum):
    RETRIABLE = "retriable"
    PERMANENT = "permanent"

class AgentErrorResponse(BaseModel):
    error_code: str
    error_type: ErrorType
    agent_id: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: datetime = datetime.utcnow()
    
    class Config:
        schema_extra = {
            "example": {
                "error_code": "AGENT_PROCESSING_ERROR",
                "error_type": "retriable",
                "agent_id": "content_prep_agent",
                "message": "Failed to process content set",
                "details": {"reason": "Invalid file format"},
                "request_id": "req-123456",
                "timestamp": "2023-06-15T10:30:00Z"
            }
        }
```

2. Create an error handler middleware in `app/middleware/error_handler.py`:
```python
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.models.errors import AgentErrorResponse, ErrorType
import logging
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            # Extract agent_id from path if possible
            path_parts = request.url.path.split("/")
            agent_id = "unknown"
            for i, part in enumerate(path_parts):
                if part == "agent" and i + 1 < len(path_parts):
                    agent_id = path_parts[i + 1]
                    break
            
            # Generate request_id if not present
            request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
            
            # Log the error
            logger.error(f"Request error: {str(e)}", 
                        extra={"request_id": request_id, "agent_id": agent_id})
            
            # Create standardized error response
            error_response = AgentErrorResponse(
                error_code="INTERNAL_SERVER_ERROR",
                error_type=ErrorType.RETRIABLE,
                agent_id=agent_id,
                message="An unexpected error occurred",
                details={"exception": str(e)},
                request_id=request_id
            )
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error_response.dict()
            )
```

3. Update all agent route handlers to use the standardized error format:
```python
from fastapi import HTTPException
from app.models.errors import AgentErrorResponse, ErrorType

# Example of updated route handler
@router.post("/process")
async def process_content(request: ProcessRequest):
    try:
        # Processing logic
        result = await agent.process(request.content)
        return result
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=AgentErrorResponse(
                error_code="VALIDATION_ERROR",
                error_type=ErrorType.PERMANENT,
                agent_id="content_prep_agent",
                message="Invalid request format",
                details={"errors": e.errors()}
            ).dict()
        )
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=AgentErrorResponse(
                error_code="RESOURCE_NOT_FOUND",
                error_type=ErrorType.PERMANENT,
                agent_id="content_prep_agent",
                message="Requested resource not found",
                details={"resource_id": e.resource_id}
            ).dict()
        )
```

4. Register the middleware in the main FastAPI application:
```python
# In app/main.py
from app.middleware.error_handler import ErrorHandlerMiddleware

app = FastAPI()
app.add_middleware(ErrorHandlerMiddleware)
```

5. Create common error code constants in `app/constants/error_codes.py`:
```python
# Common error codes
VALIDATION_ERROR = "VALIDATION_ERROR"
RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
UNAUTHORIZED = "UNAUTHORIZED"
FORBIDDEN = "FORBIDDEN"
INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"

# Agent-specific error codes
AGENT_PROCESSING_ERROR = "AGENT_PROCESSING_ERROR"
AGENT_TIMEOUT = "AGENT_TIMEOUT"
AGENT_UNAVAILABLE = "AGENT_UNAVAILABLE"
```

6. Update all existing agent implementations to use the new error model and handling approach.

**Test Strategy:**

1. Unit test the AgentErrorResponse model:
   - Test serialization/deserialization
   - Test validation of required fields
   - Test default values (timestamp)
   - Test enum validation for error_type

2. Unit test the ErrorHandlerMiddleware:
   - Test with various exception types
   - Verify correct error response format
   - Test agent_id extraction from different URL patterns
   - Test request_id propagation
   - Test logging behavior

3. Integration tests for error handling:
   - Test each agent endpoint with invalid inputs
   - Test with simulated processing errors
   - Verify consistent error response format across all endpoints
   - Test with and without X-Request-ID header

4. Test error handling for specific scenarios:
   - Authentication failures
   - Authorization failures
   - Resource not found
   - Validation errors
   - Timeout errors
   - External service failures

5. End-to-end tests:
   - Verify client applications can properly parse and handle error responses
   - Test error recovery flows for retriable errors
   - Test appropriate client behavior for permanent errors

6. Performance testing:
   - Measure overhead of error handling middleware
   - Test under high load with frequent errors
