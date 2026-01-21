# Task ID: 160

**Title:** Implement Environment Variable Validation

**Status:** cancelled

**Dependencies:** None

**Priority:** high

**Description:** Create a startup validation module that fails fast if required environment variables are missing, ensuring the application doesn't start in an invalid state.

**Details:**

Create a new file `app/core/startup_validation.py` that validates critical and recommended environment variables. The module should:
1. Define two categories of variables: critical (must be present) and recommended
2. Check for presence of all variables at startup
3. Raise RuntimeError if any critical variables are missing
4. Log warnings for missing recommended variables
5. Return a dictionary with missing variables by category

Implement the validation function as specified in the PRD, with proper error messages and logging.

Integrate this validation in `app/main.py` by calling it during application startup before any services are initialized:
```python
from app.core.startup_validation import validate_environment

# At the beginning of FastAPI app initialization
def startup_event():
    validate_environment()
    # Other startup tasks

app = FastAPI()
app.add_event_handler("startup", startup_event)
```

**Test Strategy:**

1. Create unit tests in `tests/test_startup_validation.py` that:
   - Test successful validation when all critical variables are present
   - Test failure when critical variables are missing
   - Test warning generation for missing recommended variables
   - Verify correct error messages and return values
2. Create integration tests that verify the application fails to start when critical variables are missing
3. Test with various combinations of missing variables to ensure all validation paths work correctly
