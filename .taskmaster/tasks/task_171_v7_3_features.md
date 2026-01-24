# Task ID: 171

**Title:** Implement CORS Production Hardening

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Enhance CORS configuration to fail in production if wildcard origins are detected, preventing potential security vulnerabilities.

**Details:**

Modify the CORS configuration in `app/main.py` to:
1. Parse the `CORS_ORIGINS` environment variable into a list of allowed origins
2. Check if the environment is production (`ENVIRONMENT=production`)
3. If in production, raise a `RuntimeError` if:
   - `CORS_ORIGINS` is not set or empty
   - `CORS_ORIGINS` contains a wildcard (`*`)
4. Allow wildcard origins only in non-production environments
5. Add clear error messages explaining the security requirement

Example implementation:
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

**Test Strategy:**

1. Create unit tests that verify:
   - Application starts with explicit origins in production
   - Application fails with wildcard origins in production
   - Application fails with empty origins in production
   - Application allows wildcard in development/staging
2. Create integration tests that verify CORS headers are properly set
3. Test with various origin configurations to ensure proper behavior

## Subtasks

### 171.1. Create test fixtures for CORS hardening tests

**Status:** pending  
**Dependencies:** None  

Create a new test file tests/test_cors_hardening.py with necessary test fixtures and setup for testing CORS validation in different environments.

**Details:**

Create tests/test_cors_hardening.py with pytest fixtures that simulate different environment configurations (production vs development). Include fixtures for mocking environment variables like ENVIRONMENT and CORS_ORIGINS with various values. Set up the test structure with appropriate imports and mock application initialization.

### 171.2. Test wildcard CORS in production causes startup failure

**Status:** pending  
**Dependencies:** 171.1  

Implement a test case that verifies the application raises a RuntimeError when wildcard CORS origins are detected in production environment.

**Details:**

Add a test function in tests/test_cors_hardening.py that sets ENVIRONMENT='production' and CORS_ORIGINS='*' and verifies that application initialization raises a RuntimeError with an appropriate error message about wildcard CORS not being allowed in production.

### 171.3. Test missing CORS_ORIGINS in production causes startup failure

**Status:** pending  
**Dependencies:** 171.1  

Implement a test case that verifies the application raises a RuntimeError when CORS_ORIGINS is not set or empty in production environment.

**Details:**

Add a test function in tests/test_cors_hardening.py that sets ENVIRONMENT='production' and either doesn't set CORS_ORIGINS or sets it to an empty string. Verify that application initialization raises a RuntimeError with an appropriate error message about explicit CORS origins being required in production.

### 171.4. Test wildcard CORS in development is allowed with warning

**Status:** pending  
**Dependencies:** 171.1  

Implement a test case that verifies the application allows wildcard CORS origins in development environment but logs a warning.

**Details:**

Add a test function in tests/test_cors_hardening.py that sets ENVIRONMENT='development' and CORS_ORIGINS='*' or empty. Verify that application initialization succeeds without errors but logs an appropriate warning message about using wildcard CORS in development.

### 171.5. Implement validate_cors_origins() function

**Status:** pending  
**Dependencies:** None  

Create a new function validate_cors_origins() in app/core/startup_validation.py that handles CORS validation logic.

**Details:**

Create app/core/startup_validation.py if it doesn't exist. Implement validate_cors_origins() function that takes cors_origins list and environment as parameters. The function should validate that cors_origins is not empty and doesn't contain wildcards in production, raising appropriate RuntimeErrors with clear error messages. In non-production environments, it should return a default ['*'] if cors_origins is empty.

### 171.6. Update CORS configuration in app/main.py

**Status:** pending  
**Dependencies:** 171.5  

Modify the CORS configuration in app/main.py to use the new validate_cors_origins() function for validating CORS settings.

**Details:**

Update app/main.py to import and use the validate_cors_origins() function. Parse the CORS_ORIGINS environment variable into a list, get the current environment, and pass both to validate_cors_origins(). Use the validated origins list for configuring the CORS middleware. Remove any existing CORS validation logic from main.py that's now handled by the validation function.

### 171.7. Add structlog logging for CORS validation

**Status:** pending  
**Dependencies:** 171.5, 171.6  

Implement structured logging using structlog for CORS validation events in app/main.py.

**Details:**

Import structlog in app/main.py and add logging statements for CORS validation events. Log when CORS origins are validated successfully, including the list of allowed origins. In development, log a warning when wildcard origins are used. Ensure logs include relevant context such as environment name and validation status.
