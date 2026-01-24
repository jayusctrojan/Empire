# Task ID: 172

**Title:** Implement Tiered Rate Limiting for Sensitive Endpoints

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Apply stricter rate limits to authentication and upload endpoints to prevent brute force attacks, spam, and resource abuse.

**Details:**

1. Create a new file `app/middleware/rate_limit_tiers.py` to define rate limit configurations for different endpoint patterns:
```python
RATE_LIMIT_TIERS = {
    "/api/users/login": {"limit": 5, "period": 60},  # 5 per minute
    "/api/users/register": {"limit": 3, "period": 60},  # 3 per minute
    "/api/documents/upload": {"limit": 10, "period": 60},  # 10 per minute
    "/api/query/*": {"limit": 60, "period": 60},  # 60 per minute
    "/api/orchestration/*": {"limit": 30, "period": 60},  # 30 per minute
    "default": {"limit": 200, "period": 60}  # 200 per minute
}
```

2. Modify `app/middleware/rate_limit.py` to use these tiered configurations:
   - Implement pattern matching for endpoints
   - Apply the most specific matching rate limit
   - Fall back to default limit if no pattern matches
   - Use Redis to track request counts
   - Return standardized 429 error responses when limits are exceeded

3. Add proper headers to responses:
   - `X-RateLimit-Limit`: The rate limit ceiling
   - `X-RateLimit-Remaining`: The number of requests left
   - `X-RateLimit-Reset`: The time when the limit resets

**Test Strategy:**

1. Create unit tests in `tests/test_rate_limiting.py` that verify:
   - Correct rate limit is applied for each endpoint pattern
   - Pattern matching works correctly for wildcard patterns
   - Default limit is applied when no pattern matches

2. Create integration tests that:
   - Verify rate limiting actually blocks requests after limit is reached
   - Test rate limit headers are correctly set
   - Verify different clients get separate rate limits
   - Test rate limit reset behavior

3. Load test to ensure rate limiting doesn't add significant overhead

## Subtasks

### 172.1. Create test_rate_limiting.py with Redis mock fixtures

**Status:** pending  
**Dependencies:** None  

Set up the test file with necessary fixtures to mock Redis for rate limiting tests

**Details:**

Create tests/test_rate_limiting.py with Redis mock fixtures that simulate the rate limiting behavior without requiring a real Redis instance. Include setup and teardown methods to initialize and clean up the mock Redis environment for each test.

### 172.2. Implement test for login endpoint rate limiting

**Status:** pending  
**Dependencies:** 172.1  

Create test case to verify login endpoint blocks after 5 requests per minute

**Details:**

Add a test function in tests/test_rate_limiting.py that sends 6 consecutive requests to the login endpoint and verifies that the 6th request returns a 429 status code. Ensure the test checks that the first 5 requests succeed with 200 status codes.

### 172.3. Implement test for registration endpoint rate limiting

**Status:** pending  
**Dependencies:** 172.1  

Create test case to verify registration endpoint blocks after 3 requests per minute

**Details:**

Add a test function in tests/test_rate_limiting.py that sends 4 consecutive requests to the registration endpoint and verifies that the 4th request returns a 429 status code. Ensure the test checks that the first 3 requests succeed with 200 status codes.

### 172.4. Implement test for upload endpoint rate limiting

**Status:** pending  
**Dependencies:** 172.1  

Create test case to verify upload endpoint blocks after 10 requests per minute

**Details:**

Add a test function in tests/test_rate_limiting.py that sends 11 consecutive requests to the document upload endpoint and verifies that the 11th request returns a 429 status code. Ensure the test checks that the first 10 requests succeed with 200 status codes.

### 172.5. Implement test for Retry-After header in rate limit responses

**Status:** pending  
**Dependencies:** 172.2, 172.3, 172.4  

Create test case to verify rate limit responses include the Retry-After header

**Details:**

Add a test function in tests/test_rate_limiting.py that triggers a rate limit response and verifies that the response includes the Retry-After header with an appropriate value indicating when the client can retry the request.

### 172.6. Create rate_limit_tiers.py with RateLimitTier model

**Status:** pending  
**Dependencies:** None  

Implement the rate limit tiers configuration file with appropriate models and constants

**Details:**

Create app/middleware/rate_limit_tiers.py that defines a RateLimitTier model class and the RATE_LIMIT_TIERS constant dictionary mapping endpoint patterns to their respective rate limits. Include pattern matching utility functions to determine the appropriate tier for a given endpoint.

### 172.7. Update rate_limit.py to support tiered rate limiting

**Status:** pending  
**Dependencies:** 172.6  

Modify the existing rate limiting middleware to use the tiered configuration

**Details:**

Update app/middleware/rate_limit.py to use the RATE_LIMIT_TIERS configuration. Implement pattern matching for endpoints to apply the most specific matching rate limit, falling back to the default limit if no pattern matches. Ensure Redis is used to track request counts and implement standardized 429 error responses.

### 172.8. Add rate limit decorators to login endpoint

**Status:** pending  
**Dependencies:** 172.7  

Apply rate limiting to the login endpoint with a limit of 5 requests per minute

**Details:**

Update app/routes/users.py to apply the rate limiting decorator to the login endpoint. Ensure the decorator is configured to use the '/api/users/login' tier which allows 5 requests per minute. Verify that the rate limit is applied before any authentication logic.

### 172.9. Add rate limit decorators to register endpoint

**Status:** pending  
**Dependencies:** 172.7  

Apply rate limiting to the registration endpoint with a limit of 3 requests per minute

**Details:**

Update app/routes/users.py to apply the rate limiting decorator to the register endpoint. Ensure the decorator is configured to use the '/api/users/register' tier which allows 3 requests per minute. Verify that the rate limit is applied before any registration logic.

### 172.10. Add rate limit decorators to upload endpoint

**Status:** pending  
**Dependencies:** 172.7  

Apply rate limiting to the document upload endpoint with a limit of 10 requests per minute

**Details:**

Update app/routes/documents.py to apply the rate limiting decorator to the upload endpoint. Ensure the decorator is configured to use the '/api/documents/upload' tier which allows 10 requests per minute. Verify that the rate limit is applied before any file processing logic.

### 172.11. Add rate limit decorators to query endpoints

**Status:** pending  
**Dependencies:** 172.7  

Apply rate limiting to all query endpoints with a limit of 60 requests per minute

**Details:**

Update app/routes/query.py to apply the rate limiting decorator to all query endpoints. Ensure the decorator is configured to use the '/api/query/*' tier which allows 60 requests per minute. Verify that the wildcard pattern correctly matches all endpoints in the query module.

### 172.12. Update rate limit response with standardized ErrorResponse

**Status:** pending  
**Dependencies:** 172.7  

Enhance rate limit responses to use a standardized error format with Retry-After header

**Details:**

Modify the rate limiting middleware to return a standardized ErrorResponse object when rate limits are exceeded. Include the Retry-After header in the response with the time (in seconds) until the rate limit resets. Ensure the response includes appropriate HTTP headers: X-RateLimit-Limit, X-RateLimit-Remaining, and X-RateLimit-Reset.
