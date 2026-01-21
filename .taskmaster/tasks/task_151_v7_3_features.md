# Task ID: 151

**Title:** Implement PostgreSQL Session Variables for Row-Level Security

**Status:** done

**Dependencies:** 101 ✓, 123 ✓

**Priority:** medium

**Description:** Create PostgreSQL functions for managing row-level security context, including set_rls_context, get_rls_context, clear_rls_context, current_user_id, and session_has_role functions. Update middleware to call these functions via Supabase RPC.

**Details:**

Implement the following PostgreSQL functions in a new migration file `migrations/rls_context_functions.sql`:

1. `set_rls_context(key text, value text)`: Sets a session variable for RLS context
   ```sql
   CREATE OR REPLACE FUNCTION set_rls_context(key text, value text)
   RETURNS void AS $$
   BEGIN
     PERFORM set_config('app.rls_' || key, value, false);
   EXCEPTION
     WHEN OTHERS THEN
       RAISE EXCEPTION 'Failed to set RLS context: %', SQLERRM;
   END;
   $$ LANGUAGE plpgsql SECURITY DEFINER;
   ```

2. `get_rls_context(key text)`: Retrieves a session variable
   ```sql
   CREATE OR REPLACE FUNCTION get_rls_context(key text)
   RETURNS text AS $$
   BEGIN
     RETURN current_setting('app.rls_' || key, true);
   EXCEPTION
     WHEN OTHERS THEN
       RETURN NULL;
   END;
   $$ LANGUAGE plpgsql SECURITY DEFINER;
   ```

3. `clear_rls_context()`: Clears all RLS context variables
   ```sql
   CREATE OR REPLACE FUNCTION clear_rls_context()
   RETURNS void AS $$
   DECLARE
     setting_name text;
   BEGIN
     FOR setting_name IN 
       SELECT name FROM pg_settings WHERE name LIKE 'app.rls_%'
     LOOP
       PERFORM set_config(setting_name, NULL, false);
     END LOOP;
   EXCEPTION
     WHEN OTHERS THEN
       RAISE EXCEPTION 'Failed to clear RLS context: %', SQLERRM;
   END;
   $$ LANGUAGE plpgsql SECURITY DEFINER;
   ```

4. `current_user_id()`: Returns the current user ID from context
   ```sql
   CREATE OR REPLACE FUNCTION current_user_id()
   RETURNS uuid AS $$
   BEGIN
     RETURN get_rls_context('user_id')::uuid;
   EXCEPTION
     WHEN OTHERS THEN
       RETURN NULL;
   END;
   $$ LANGUAGE plpgsql SECURITY DEFINER;
   ```

5. `session_has_role(role_name text)`: Checks if the current session has a specific role
   ```sql
   CREATE OR REPLACE FUNCTION session_has_role(role_name text)
   RETURNS boolean AS $$
   DECLARE
     roles text;
   BEGIN
     roles := get_rls_context('roles');
     RETURN roles LIKE '%' || role_name || '%';
   EXCEPTION
     WHEN OTHERS THEN
       RETURN false;
   END;
   $$ LANGUAGE plpgsql SECURITY DEFINER;
   ```

Next, update the middleware in `app/middleware/auth.py` to set these context variables via Supabase RPC calls:

```python
from fastapi import Request, Response
from app.db.supabase import get_supabase_client

async def rls_middleware(request: Request, call_next):
    # Extract user information from request (JWT token)
    user_id = extract_user_id(request)
    user_roles = extract_user_roles(request)
    
    try:
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Set RLS context via RPC
        if user_id:
            await supabase.rpc('set_rls_context', {'key': 'user_id', 'value': str(user_id)})
            
        if user_roles:
            roles_str = ','.join(user_roles)
            await supabase.rpc('set_rls_context', {'key': 'roles', 'value': roles_str})
        
        # Process the request
        response = await call_next(request)
        
        # Clear RLS context after request is processed
        await supabase.rpc('clear_rls_context')
        
        return response
    except Exception as e:
        # Security-first error handling - return 503 on failure
        return Response(
            content={"error": "Service temporarily unavailable"},
            status_code=503,
            media_type="application/json"
        )
```

Finally, register the middleware in the main FastAPI application:

```python
# In app/main.py
from app.middleware.auth import rls_middleware

app = FastAPI()
app.middleware("http")(rls_middleware)
```

**Test Strategy:**

1. **Unit Tests for PostgreSQL Functions**:
   - Create a test file `tests/db/test_rls_functions.sql` to test each function individually
   - Test `set_rls_context` with various key-value pairs
   - Test `get_rls_context` retrieves the correct values
   - Test `clear_rls_context` properly removes all context variables
   - Test `current_user_id` returns the expected UUID
   - Test `session_has_role` correctly identifies roles in the context

2. **Integration Tests for Middleware**:
   - Create a test file `tests/middleware/test_rls_middleware.py`
   - Test middleware correctly extracts user information from requests
   - Test middleware makes appropriate RPC calls to Supabase
   - Test middleware clears context after request processing
   - Test error handling returns 503 status code on failure

3. **Security Tests**:
   - Verify RLS policies correctly use the context variables
   - Test that unauthorized access is properly prevented
   - Test that context variables are properly isolated between concurrent requests
   - Verify SQL injection prevention in the functions

4. **Performance Tests**:
   - Measure overhead of setting and clearing context variables
   - Test with concurrent requests to ensure no context leakage
   - Benchmark database queries with RLS enabled vs. disabled

5. **End-to-End Tests**:
   - Create test scenarios that use RLS to restrict data access
   - Verify different user roles see appropriate data
   - Test API endpoints that rely on RLS for data filtering
