# How to Obtain Clerk JWT Token for Load Testing

**Required for**: `query_load_test.py` execution
**Purpose**: Authenticate with Empire API endpoints that require user context

---

## Quick Start (Recommended Method)

### Method 1: From Browser Console (Easiest)

1. **Open Empire Chat UI**:
   ```
   https://jb-empire-chat.onrender.com
   ```

2. **Log in with your Clerk account**
   - Use your existing Empire account credentials

3. **Open Browser Developer Tools**:
   - **Chrome/Edge**: Press `F12` or `Cmd+Option+I` (Mac) / `Ctrl+Shift+I` (Windows)
   - **Firefox**: Press `F12` or `Cmd+Option+K` (Mac) / `Ctrl+Shift+K` (Windows)
   - **Safari**: Enable Developer Menu first (Preferences → Advanced → Show Develop menu), then `Cmd+Option+C`

4. **Go to Console tab**

5. **Run this command**:
   ```javascript
   window.__clerk_session_token__ ||
   localStorage.getItem('__clerk_session') ||
   document.cookie.split('; ').find(row => row.startsWith('__session=')).split('=')[1]
   ```

6. **Copy the token** (long string starting with `eyJ...`)

7. **Export to environment**:
   ```bash
   export CLERK_TEST_TOKEN='eyJ...'  # Paste your token here
   ```

8. **Run the load test**:
   ```bash
   cd tests/load_testing
   python3 query_load_test.py
   ```

---

## Method 2: From Clerk Dashboard (Test User)

If you have access to the Clerk dashboard:

1. **Go to Clerk Dashboard**:
   ```
   https://dashboard.clerk.com
   ```

2. **Select your Empire application**

3. **Navigate to**: Users → Create User

4. **Create a test user**:
   - Email: `test@empire.local`
   - Password: (choose a secure password)

5. **Get User ID**:
   - Click on the created user
   - Copy the User ID

6. **Generate Test Token**:
   - Go to: Configure → JWT Templates
   - Click "Default" template
   - In the preview section, you can generate a token for testing

**Note**: This method generates long-lived test tokens suitable for automated testing.

---

## Method 3: From API Request (Programmatic)

If you have username/password credentials:

```python
import requests

def get_clerk_token(email: str, password: str) -> str:
    """Get Clerk JWT token programmatically."""

    # Clerk sign-in endpoint
    signin_url = "https://api.clerk.com/v1/client/sign_ins"

    # Create sign-in attempt
    response = requests.post(
        signin_url,
        json={
            "identifier": email,
            "password": password,
            "strategy": "password"
        },
        headers={
            "Content-Type": "application/json"
        }
    )

    if response.status_code == 200:
        data = response.json()
        # Extract session token
        session_id = data['response']['sessions'][0]['id']

        # Get session token
        token_url = f"https://api.clerk.com/v1/client/sessions/{session_id}/tokens"
        token_response = requests.post(token_url)

        if token_response.status_code == 200:
            return token_response.json()['jwt']

    raise Exception(f"Failed to get token: {response.status_code}")

# Usage
token = get_clerk_token("your-email@example.com", "your-password")
print(f"export CLERK_TEST_TOKEN='{token}'")
```

---

## Method 4: From Production API (For Developers)

If you have direct access to the Empire API codebase:

```python
# In a Python shell with access to Empire code
from app.middleware.clerk_auth import create_test_token

# Create test token for a user
token = create_test_token(
    user_id="user_test_123",
    email="test@empire.local",
    expiration_hours=24
)

print(f"export CLERK_TEST_TOKEN='{token}'")
```

**Note**: This requires modifying `app/middleware/clerk_auth.py` to add a `create_test_token()` helper.

---

## Token Format & Validation

### Valid Token Format:
```
eyJ...  (starts with 'eyJ')
```

### Token Structure (JWT):
- **Header**: Algorithm and token type
- **Payload**: User claims (user_id, email, permissions)
- **Signature**: Cryptographic signature

### Validate Your Token:

```bash
# Check if token is valid JWT format
echo $CLERK_TEST_TOKEN | cut -d '.' -f 2 | base64 -d | jq

# Should output JSON with user claims:
# {
#   "sub": "user_...",
#   "email": "...",
#   "exp": ...,
#   ...
# }
```

---

## Troubleshooting

### Error: "Invalid token"
- **Cause**: Token expired or malformed
- **Solution**: Generate a new token using Method 1 or 2

### Error: "Authentication required"
- **Cause**: Token not set or not exported
- **Solution**:
  ```bash
  # Check if token is set
  echo $CLERK_TEST_TOKEN

  # If empty, export again
  export CLERK_TEST_TOKEN='your-token-here'
  ```

### Error: "Permission denied"
- **Cause**: Token doesn't have required permissions
- **Solution**: Use a token from an admin user or ensure user has query permissions

### Token Expires Quickly
- **Default Expiration**: 1 hour for session tokens
- **Solution**:
  - Use Method 2 (test user) for longer-lived tokens
  - Re-generate token before each test session
  - Or create a script to auto-refresh

---

## Running the Load Test

Once you have the token:

```bash
# 1. Export token
export CLERK_TEST_TOKEN='eyJ...'

# 2. Navigate to test directory
cd tests/load_testing

# 3. Run the test
python3 query_load_test.py

# 4. View results
ls -lh results/query_load_test_*.json
```

### Expected Output:
```
======================================================================
Empire v7.3 - Query Endpoint Load Test
======================================================================
Host: https://jb-empire-api.onrender.com
Auth: Configured ✅
Time: 2025-11-16 10:50:00

======================================================================
Test 1: Adaptive Endpoint (/api/query/adaptive)
======================================================================

SIMPLE_LOOKUP Queries:
----------------------------------------
  ✅ 200 | 1245ms | FRESH | What are California insurance requirements?...
  ✅ 200 | 876ms | FRESH | Explain our privacy policy...
  ✅ 200 | 923ms | FRESH | What is our refund policy?...

COMPLEX_RESEARCH Queries:
----------------------------------------
  ✅ 200 | 2134ms | FRESH | Compare our policies with current California...
  ✅ 200 | 1987ms | FRESH | What are the latest industry trends in compli...
  ✅ 200 | 2045ms | FRESH | How do our benefits compare to competitors?...

SIMILAR_QUERIES Queries:
----------------------------------------
  ✅ 200 | 1156ms | FRESH | What are California insurance requirements?...
  ✅ 200 | 234ms | CACHED | What are the insurance requirements for Calif...
  ✅ 200 | 198ms | CACHED | Tell me about California's insurance requirem...

📊 Statistics:
  Total Requests: 9
  Average: 1089ms
  P50: 923ms
  P95: 2098ms
  Min: 198ms
  Max: 2134ms
  Cache Hits: 2/9 (22.2%)
```

---

## Security Best Practices

### Do Not:
- ❌ Commit tokens to Git
- ❌ Share tokens in Slack/email
- ❌ Use production user tokens for testing
- ❌ Store tokens in plaintext files

### Do:
- ✅ Use environment variables
- ✅ Rotate tokens regularly
- ✅ Create dedicated test users
- ✅ Delete test tokens after use
- ✅ Use `.env` file (gitignored) for local development

### Example `.env.test` (gitignored):
```bash
# Test credentials - DO NOT COMMIT
CLERK_TEST_TOKEN=eyJ...
EMPIRE_API_URL=https://jb-empire-api.onrender.com
```

Then load:
```bash
source .env.test
python3 query_load_test.py
```

---

## Alternative: Run Without Authentication

For endpoints that don't require auth, you can test without a token:

```python
# Modify query_load_test.py
# Comment out authentication check:
# if not CLERK_TOKEN:
#     print("WARNING: ...")
#     sys.exit(1)

# Run without token
python3 query_load_test.py
```

**Note**: Query endpoints (`/api/query/adaptive`, `/api/query/auto`) require authentication, so this won't work for the main tests.

---

## FAQ

**Q: How long does the token last?**
A: Session tokens typically last 1 hour. Test user tokens can last 24+ hours.

**Q: Can I reuse the same token for multiple tests?**
A: Yes, as long as it hasn't expired.

**Q: Do I need a different token for each test?**
A: No, one token can be used for all tests in a session.

**Q: Can I test against localhost instead of production?**
A: Yes, set `EMPIRE_API_URL=http://localhost:8000` before running tests. You'll still need a token if the local API has auth enabled.

**Q: What if I don't have access to Clerk dashboard?**
A: Use Method 1 (browser console) - it works with any logged-in session.

---

## Quick Reference

```bash
# Get token from browser console (Method 1 - Recommended)
window.__clerk_session_token__ || localStorage.getItem('__clerk_session')

# Export to environment
export CLERK_TEST_TOKEN='eyJ...'

# Run test
cd tests/load_testing && python3 query_load_test.py

# View results
cat results/query_load_test_$(ls -t results/query_load_test_*.json | head -1)
```

---

**Last Updated**: 2025-11-16
**Next**: Run `query_load_test.py` with your token to validate cache performance
