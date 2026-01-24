# Task ID: 162

**Title:** Implement Tiered Rate Limiting for Sensitive Endpoints

**Status:** cancelled

**Dependencies:** None

**Priority:** high

**Description:** Apply stricter rate limits to authentication and upload endpoints to prevent brute force attacks, spam, and resource abuse.

**Details:**

Create a new file `app/middleware/rate_limit_tiers.py` to define endpoint-specific rate limits and modify the existing rate limiting middleware:

1. Define rate limit tiers as specified in the PRD:
```python
RATE_LIMIT_TIERS = {
    "/api/users/login": {"limit": 5, "period": 60},  # 5/minute
    "/api/users/register": {"limit": 3, "period": 60},  # 3/minute
    "/api/documents/upload": {"limit": 10, "period": 60},  # 10/minute
    "/api/query/*": {"limit": 60, "period": 60},  # 60/minute
    "/api/orchestration/*": {"limit": 30, "period": 60},  # 30/minute
    "default": {"limit": 200, "period": 60}  # 200/minute
}
```

2. Modify `app/middleware/rate_limit.py` to use these tiers:
   - Add function to match request path against patterns (supporting wildcards)
   - Determine applicable rate limit based on endpoint
   - Apply the appropriate limit
   - Return standardized 429 error when limit exceeded

3. Update Redis key generation to include the endpoint pattern to ensure separate rate limit buckets per endpoint type

4. Add proper error responses with retry-after headers when limits are exceeded

**Test Strategy:**

1. Create unit tests in `tests/test_rate_limiting.py` that verify:
   - Correct limit is applied to each endpoint type
   - Pattern matching works correctly with wildcards
   - Default limit is applied to unmatched endpoints
   - Rate limit counters increment correctly

2. Create integration tests that:
   - Verify rate limiting behavior for each endpoint type
   - Test rate limit reset after period expiration
   - Confirm correct error responses and status codes
   - Verify retry-after headers are present and accurate
