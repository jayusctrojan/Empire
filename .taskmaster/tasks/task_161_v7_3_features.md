# Task ID: 161

**Title:** Implement CORS Production Hardening

**Status:** cancelled

**Dependencies:** None

**Priority:** high

**Description:** Enhance CORS configuration to fail in production if wildcard origins are detected, preventing potential security vulnerabilities.

**Details:**

Modify `app/main.py` to enforce strict CORS rules in production environments:

1. Extract the current CORS configuration logic
2. Add environment-aware validation that:
   - Allows wildcard origins (`*`) in development only
   - Requires explicit origin list in production
   - Raises RuntimeError with clear error message if wildcard is detected in production

Implementation should follow the pattern provided in the PRD:
```python
cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
if not cors_origins or cors_origins == [""]:
    if os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError(
            "CORS_ORIGINS must be explicitly set in production. "
            "Set to specific origins like 'https://app.example.com,https://admin.example.com'"
        )
    cors_origins = ["*"]  # Allow in development only

if "*" in cors_origins and os.getenv("ENVIRONMENT") == "production":
    raise RuntimeError(
        "CORS_ORIGINS cannot be '*' in production. "
        "Set specific allowed origins for security."
    )
```

Ensure this validation happens before the FastAPI CORSMiddleware is initialized.

**Test Strategy:**

1. Create unit tests that verify:
   - Wildcard origins are allowed in development
   - Empty CORS settings default to wildcard in development
   - Empty CORS settings raise error in production
   - Wildcard origins raise error in production
   - Valid origin lists are accepted in all environments
2. Create integration tests that verify application startup behavior with different CORS configurations
3. Test with various environment configurations to ensure correct behavior in all scenarios
