# Clerk Authentication Guide - Empire FastAPI Backend

## Overview

This guide explains the Clerk authentication implementation for securing Empire's chat endpoints. Clerk provides JWT-based authentication that verifies user identity before allowing access to protected endpoints.

## Implementation Details

### Components

1. **clerk-backend-api** - Python SDK for Clerk authentication
2. **clerk_auth.py** - FastAPI middleware for token verification
3. **Protected Endpoints** - Query endpoints requiring authentication
4. **Public Endpoints** - Health checks and documentation remain public
5. **clerk_auth.html** - Custom Clerk authentication page with JavaScript SDK
6. **app_with_auth.py** - Authenticated Gradio chat interface wrapper
7. **chat_service.py** - Updated to pass authentication tokens to API

### Architecture

```
Client Request
    ↓
    ├─→ Authorization: Bearer <JWT_TOKEN>
    ↓
FastAPI Endpoint with Depends(verify_clerk_token)
    ↓
clerk_auth.py: verify_clerk_token()
    ↓
    ├─→ Verify token with Clerk API
    ├─→ Get user details
    ├─→ Log authentication
    ↓
    ├─→ Success: Return user info dict
    └─→ Failure: Raise HTTPException 401
    ↓
Endpoint Handler (with user context)
```

## Setup Instructions

### 1. Install Dependencies

The required package is already in `requirements.txt`:

```bash
cd Empire
pip install -r requirements.txt
```

This installs `clerk-backend-api==0.8.0`

### 2. Get Clerk Secret Key

1. Sign up at https://clerk.com
2. Create a new application
3. Go to **API Keys** section
4. Copy your **Secret Key** (starts with `sk_`)

### 3. Configure Environment

Add to your `.env` file:

```bash
# Clerk Authentication
CLERK_SECRET_KEY=sk_test_your_secret_key_here
```

**Security Note**: Never commit this key to version control!

### 4. Restart Server

```bash
cd Empire
uvicorn app.main:app --reload --host 0.0.0.0 --port 8082
```

## Protected Endpoints

The following endpoints now require Clerk JWT authentication:

### Query Endpoints (Authenticated)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/query/auto` | POST | Auto-routed query processing |
| `/api/query/adaptive` | POST | Adaptive LangGraph query |
| `/api/query/adaptive/async` | POST | Async adaptive query |
| `/api/query/auto/async` | POST | Async auto-routed query |

### Public Endpoints (No Authentication)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Main health check |
| `/api/query/health` | GET | Query service health |
| `/docs` | GET | API documentation |
| `/openapi.json` | GET | OpenAPI schema |
| `/api/query/tools` | GET | List available tools |
| `/api/query/status/{task_id}` | GET | Check task status |
| `/api/query/batch` | POST | Batch query processing |

## Usage Examples

### Making Authenticated Requests

#### 1. Get JWT Token from Clerk (Frontend)

```javascript
// In your frontend app with Clerk
import { useAuth } from '@clerk/nextjs';

const { getToken } = useAuth();
const token = await getToken();
```

#### 2. Call Protected Endpoint

```javascript
// Make authenticated request
const response = await fetch('https://jb-empire-api.onrender.com/api/query/auto', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    query: 'What are California insurance requirements?',
    max_iterations: 3
  })
});

const data = await response.json();
```

#### 3. Handle Authentication Errors

```javascript
if (response.status === 401) {
  console.error('Authentication failed. Please sign in again.');
  // Redirect to login or refresh token
}
```

### Python Example

```python
import httpx
import os

# Get Clerk token (from your frontend or auth flow)
clerk_token = os.getenv("CLERK_JWT_TOKEN")

# Make authenticated request
async with httpx.AsyncClient() as client:
    response = await client.post(
        "https://jb-empire-api.onrender.com/api/query/auto",
        headers={
            "Authorization": f"Bearer {clerk_token}",
            "Content-Type": "application/json"
        },
        json={
            "query": "What are California insurance requirements?",
            "max_iterations": 3
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Answer: {result['answer']}")
    elif response.status_code == 401:
        print("Authentication failed!")
```

### cURL Example

```bash
curl -X POST "https://jb-empire-api.onrender.com/api/query/auto" \
  -H "Authorization: Bearer YOUR_CLERK_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are California insurance requirements?",
    "max_iterations": 3
  }'
```

## Middleware Details

### verify_clerk_token()

Located in `app/middleware/clerk_auth.py`

**Purpose**: Verify Clerk JWT tokens and extract user information

**Returns**:
```python
{
    "user_id": "user_2abc123...",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
}
```

**Raises**: `HTTPException(401)` if authentication fails

**Features**:
- Verifies JWT token with Clerk API
- Fetches user details from Clerk
- Structured logging of auth events
- User-friendly error messages

### verify_clerk_token_optional()

Optional authentication for endpoints that can work with or without auth.

**Returns**: User dict if authenticated, `None` if no token provided

## Error Responses

### 401 Unauthorized

```json
{
  "detail": "Invalid or expired token"
}
```

**Causes**:
- Token expired
- Invalid token format
- Clerk API communication failure
- User not found

### 403 Forbidden

```json
{
  "detail": "Insufficient permissions"
}
```

**Causes**:
- User doesn't have required permissions (future enhancement)

## Logging

All authentication events are logged with structured data:

### Successful Authentication

```json
{
  "event": "User authenticated",
  "user_id": "user_2abc123...",
  "email": "user@example.com",
  "timestamp": "2025-11-08T14:28:00Z",
  "level": "info"
}
```

### Failed Authentication

```json
{
  "event": "Authentication failed",
  "error": "Invalid token",
  "timestamp": "2025-11-08T14:28:00Z",
  "level": "error"
}
```

## Testing Authentication

### 1. Test Public Endpoint (No Auth Required)

```bash
curl -X GET "http://localhost:8082/api/query/health"
```

**Expected**: `200 OK` with health status

### 2. Test Protected Endpoint Without Auth

```bash
curl -X POST "http://localhost:8082/api/query/auto" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

**Expected**: `403 Forbidden` - "Not authenticated"

### 3. Test Protected Endpoint With Valid Auth

```bash
curl -X POST "http://localhost:8082/api/query/auto" \
  -H "Authorization: Bearer YOUR_VALID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "max_iterations": 2}'
```

**Expected**: `200 OK` with query results

### 4. Test With Invalid Token

```bash
curl -X POST "http://localhost:8082/api/query/auto" \
  -H "Authorization: Bearer invalid_token" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

**Expected**: `401 Unauthorized` - "Authentication failed"

## Gradio Chat UI Authentication

### Overview

The Empire chat UI has been updated to support Clerk authentication. There are two ways to run the authenticated chat interface:

1. **app_with_auth.py** - Full authentication wrapper with custom Clerk sign-in page
2. **chat_ui.py** - Original chat UI (now supports auth tokens if available)

### File Structure

```
Empire/
├── app_with_auth.py              # Authenticated Gradio wrapper
├── chat_ui.py                    # Original chat UI (auth-aware)
├── static/
│   └── clerk_auth.html          # Custom Clerk authentication page
└── app/
    └── services/
        └── chat_service.py      # Updated to accept auth tokens
```

### Custom Authentication Page

The `static/clerk_auth.html` file provides a custom Clerk sign-in interface:

**Features:**
- Clerk JavaScript SDK integration
- Sign-in/sign-up forms
- JWT token extraction and storage
- LocalStorage-based token management
- Redirect to chat interface after auth

**How it works:**

```javascript
// Load Clerk and get session token
const clerkInstance = window.Clerk;
await clerkInstance.load();

// Get JWT token after sign-in
const token = await clerkInstance.session.getToken();

// Store in localStorage for chat UI
localStorage.setItem("clerk_session_token", token);

// Redirect to /chat
window.location.href = "/chat";
```

### Authenticated Chat Wrapper (app_with_auth.py)

This FastAPI + Gradio application provides:

**Routes:**
- `/` - Serves the Clerk authentication page
- `/chat` - Serves the authenticated Gradio chat interface

**Token Injection:**

JavaScript is injected into the chat page to automatically add auth tokens to all requests:

```javascript
// Intercept fetch requests and add auth token
window.fetch = function(...args) {
    const token = localStorage.getItem('clerk_session_token');
    if (token && args[1]) {
        args[1].headers = args[1].headers || {};
        args[1].headers['X-Clerk-Session-Token'] = token;
    }
    return originalFetch.apply(this, args);
};
```

**Running locally:**

```bash
python3 app_with_auth.py
```

Then visit:
- http://localhost:7860/ - Auth page
- http://localhost:7860/chat - Chat interface (requires sign-in)

### Chat Service Token Handling

The `chat_service.py` has been updated to accept and pass authentication tokens:

```python
async def stream_chat_response(
    self,
    message: str,
    history: list,
    auth_token: Optional[str] = None  # New parameter
):
    # Token is passed to API requests
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
```

### Deployment to Render

**Environment Variables Required:**

For Chat UI Service (jb-empire-chat):
```bash
VITE_CLERK_PUBLISHABLE_KEY=<from .env>
EMPIRE_API_URL=https://jb-empire-api.onrender.com
CHAT_UI_PORT=7860
CHAT_UI_HOST=0.0.0.0
```

For API Service (jb-empire-api):
```bash
CLERK_SECRET_KEY=<from .env>
CLERK_PUBLISHABLE_KEY=<from .env>
```

**Note:** All actual credential values are in `.env` file (gitignored)

**Start Command for Chat UI:**

Update the Render service to use:
```bash
python3 app_with_auth.py
```

This will serve the authentication page at the root and the chat interface at `/chat`.

### Testing the Flow

1. **Visit the chat UI**: https://jb-empire-chat.onrender.com
2. **Sign in with Clerk**: Complete the authentication form
3. **Get redirected**: Automatically redirected to `/chat`
4. **Submit a query**: Token is automatically included in requests
5. **Backend validates**: API verifies token and processes query

### Troubleshooting Chat UI Authentication

**Issue: Token not being sent to API**

```bash
# Check localStorage in browser console
localStorage.getItem('clerk_session_token')

# Should return a JWT token string
```

**Issue: "Authentication required" error in chat**

```bash
# Verify token is in request headers (Network tab)
# Look for: X-Clerk-Session-Token: <token>
```

**Issue: Auth page not loading**

```bash
# Verify static files directory exists
ls -la static/clerk_auth.html

# Check FastAPI static mount
# Should see in logs: "Static files mounted at /static"
```

## Frontend Integration

### Next.js with Clerk

```typescript
// app/api/empire-query/route.ts
import { auth } from '@clerk/nextjs';

export async function POST(req: Request) {
  const { getToken } = auth();
  const token = await getToken();

  if (!token) {
    return new Response('Unauthorized', { status: 401 });
  }

  const body = await req.json();

  const response = await fetch(
    'https://jb-empire-api.onrender.com/api/query/auto',
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    }
  );

  return response;
}
```

### React Component

```typescript
// components/QueryInterface.tsx
import { useAuth } from '@clerk/nextjs';
import { useState } from 'react';

export function QueryInterface() {
  const { getToken } = useAuth();
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);

  const handleQuery = async (query: string) => {
    setLoading(true);
    try {
      const token = await getToken();
      
      const response = await fetch(
        'https://jb-empire-api.onrender.com/api/query/auto',
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            query,
            max_iterations: 3,
          }),
        }
      );

      if (!response.ok) {
        throw new Error('Query failed');
      }

      const data = await response.json();
      setResult(data.answer);
    } catch (error) {
      console.error('Query error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {/* Your UI components */}
    </div>
  );
}
```

## Security Best Practices

### 1. Token Management

- ✅ Always use HTTPS in production
- ✅ Store tokens securely (httpOnly cookies recommended)
- ✅ Refresh tokens before expiration
- ✅ Clear tokens on logout
- ❌ Never log tokens in production
- ❌ Never expose tokens in URLs

### 2. Environment Security

```bash
# ✅ Good - Use environment variables
CLERK_SECRET_KEY=sk_live_...

# ❌ Bad - Hardcoded in code
clerk_client = Clerk(bearer_auth="sk_live_hardcoded")
```

### 3. Error Handling

```python
# ✅ Good - Don't expose sensitive details
raise HTTPException(
    status_code=401,
    detail="Authentication failed"
)

# ❌ Bad - Exposes internal errors
raise HTTPException(
    status_code=401,
    detail=f"Clerk API error: {e.response.text}"
)
```

### 4. Rate Limiting

Consider adding rate limiting to prevent abuse:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/auto")
@limiter.limit("10/minute")
async def auto_routed_query(...):
    ...
```

## Troubleshooting

### Issue: 401 Unauthorized

**Possible Causes**:
1. Token expired → Refresh token on frontend
2. Invalid `CLERK_SECRET_KEY` → Check .env file
3. Clerk API down → Check Clerk status page
4. Token format incorrect → Ensure "Bearer " prefix

### Issue: 500 Internal Server Error

**Possible Causes**:
1. Clerk SDK not installed → `pip install clerk-backend-api`
2. Missing CLERK_SECRET_KEY → Add to .env
3. Network connectivity → Check Clerk API access

### Issue: "Not authenticated" (403)

**Possible Causes**:
1. No Authorization header → Add header to request
2. Malformed header → Check format: `Bearer <token>`

### Debug Commands

```bash
# Check if Clerk SDK is installed
python -c "import clerk_backend_api; print('Clerk SDK installed')"

# Check environment variable
echo $CLERK_SECRET_KEY

# Test Clerk API connectivity
curl -H "Authorization: Bearer sk_test_..." \
  https://api.clerk.com/v1/users
```

## Migration from Unauthenticated

If you had existing clients using unauthenticated endpoints:

### Option 1: Gradual Migration

Keep a separate unauthenticated endpoint temporarily:

```python
@router.post("/auto/public")
async def auto_routed_query_public(request: AdaptiveQueryRequest):
    """Temporary public endpoint - will be deprecated"""
    # Same logic without auth
```

### Option 2: API Key Fallback

Support both Clerk and API key auth:

```python
async def verify_auth(
    clerk_token: Optional[str] = Depends(verify_clerk_token_optional),
    api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    if clerk_token:
        return clerk_token
    if api_key and api_key == os.getenv("INTERNAL_API_KEY"):
        return {"user_id": "api_key_user"}
    raise HTTPException(401, "Authentication required")
```

## Future Enhancements

1. **Role-Based Access Control (RBAC)**
   - Admin users get access to all endpoints
   - Regular users have usage limits
   - Premium users get priority processing

2. **Usage Tracking**
   - Track queries per user
   - Implement usage quotas
   - Generate analytics

3. **Webhook Integration**
   - Sync user data from Clerk
   - Handle user.created, user.updated events
   - Automatically provision resources

4. **Multi-tenancy**
   - Isolate data by organization
   - Per-tenant rate limits
   - Organization-level billing

## Support

For issues or questions:
1. Check Clerk documentation: https://clerk.com/docs
2. Review structured logs for auth events
3. Test with Clerk's development tokens
4. Contact team for infrastructure issues

---

**Last Updated**: January 8, 2025
**Version**: 1.1 (Added Gradio Chat UI authentication)
**Author**: Empire Development Team
