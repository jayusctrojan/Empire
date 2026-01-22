# Task ID: 170

**Title:** Implement Environment Variable Validation

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Create a startup validation module that fails fast if required environment variables are missing, ensuring the application doesn't start in an invalid state.

**Details:**

Create a new module `app/core/startup_validation.py` that validates critical and recommended environment variables. The module should:
1. Define lists of critical variables (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `REDIS_URL`, `ANTHROPIC_API_KEY`, `ENVIRONMENT`) and recommended variables (`NEO4J_URI`, `NEO4J_PASSWORD`, `LLAMAINDEX_SERVICE_URL`, `CREWAI_SERVICE_URL`)
2. Implement a `validate_environment()` function that checks for missing variables
3. Raise a `RuntimeError` with a clear message if any critical variables are missing
4. Log warnings for missing recommended variables
5. Return a dictionary with lists of missing variables by category

Modify `app/main.py` to call this validation function during application startup before any services are initialized.

**Test Strategy:**

1. Create unit tests in `tests/test_startup_validation.py` that:
   - Test successful validation when all critical variables are present
   - Test failure when critical variables are missing
   - Test warning generation for missing recommended variables
   - Test the returned dictionary structure
2. Create integration tests that verify the application fails to start when critical variables are missing
3. Test with various combinations of missing variables to ensure proper error messages

## Subtasks

### 170.1. Create test_startup_validation.py with test fixtures

**Status:** pending  
**Dependencies:** None  

Create a test file with fixtures for environment variable validation tests

**Details:**

Create tests/test_startup_validation.py with pytest fixtures that can mock environment variables for testing. Include fixtures for setting up different environment scenarios (all vars present, missing critical vars, missing recommended vars, empty string vars).

### 170.2. Test missing critical env var causes startup failure

**Status:** pending  
**Dependencies:** 170.1  

Implement test case to verify that missing critical environment variables cause application startup to fail

**Details:**

Create a test function that mocks environment with one or more missing critical variables and verifies that validate_environment() raises a RuntimeError with appropriate error message listing the missing variables.

### 170.3. Test missing recommended env var logs warning but continues

**Status:** pending  
**Dependencies:** 170.1  

Implement test case to verify that missing recommended variables generate warnings but don't prevent startup

**Details:**

Create a test function that mocks environment with all critical variables but missing recommended variables, and verifies that validate_environment() logs warnings but returns successfully with a dictionary containing the missing recommended variables.

### 170.4. Test empty string env var treated as missing

**Status:** pending  
**Dependencies:** 170.1  

Implement test case to verify that environment variables with empty string values are treated as missing

**Details:**

Create a test function that sets critical and recommended environment variables to empty strings and verifies they are treated the same as missing variables (raising errors for critical vars, warnings for recommended vars).

### 170.5. Test all env vars present logs success message

**Status:** pending  
**Dependencies:** 170.1  

Implement test case to verify that when all environment variables are present, a success message is logged

**Details:**

Create a test function that mocks environment with all critical and recommended variables present and verifies that validate_environment() logs a success message and returns an empty dictionary (no missing variables).

### 170.6. Create startup_validation.py with environment variable constants

**Status:** pending  
**Dependencies:** None  

Create the startup validation module with constants for critical and recommended environment variables

**Details:**

Create app/core/startup_validation.py module and define CRITICAL_ENV_VARS and RECOMMENDED_ENV_VARS lists containing the required environment variables as specified in the task description. CRITICAL_ENV_VARS should include SUPABASE_URL, SUPABASE_SERVICE_KEY, REDIS_URL, ANTHROPIC_API_KEY, and ENVIRONMENT. RECOMMENDED_ENV_VARS should include NEO4J_URI, NEO4J_PASSWORD, LLAMAINDEX_SERVICE_URL, and CREWAI_SERVICE_URL.

### 170.7. Implement validate_environment() function

**Status:** pending  
**Dependencies:** 170.6  

Implement the core validation function that checks for missing environment variables

**Details:**

Implement validate_environment() function in app/core/startup_validation.py that checks for missing critical and recommended variables, raises RuntimeError for missing critical variables, logs warnings for missing recommended variables, and returns a dictionary with lists of missing variables by category.

### 170.8. Add structlog logging for validation results

**Status:** pending  
**Dependencies:** 170.7  

Implement structured logging for environment variable validation results

**Details:**

Add structlog logging to the validate_environment() function to log validation results with appropriate log levels (error for missing critical vars, warning for missing recommended vars, info for successful validation). Include structured data in logs for easier parsing and monitoring.

### 170.9. Add startup hook in app/main.py

**Status:** pending  
**Dependencies:** 170.7, 170.8  

Modify app/main.py to call validate_environment() during application startup

**Details:**

Modify app/main.py to import and call the validate_environment() function during application startup, before any services are initialized. Ensure the application fails to start if validate_environment() raises a RuntimeError due to missing critical environment variables.
