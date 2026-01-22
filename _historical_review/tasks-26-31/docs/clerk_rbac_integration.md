# Clerk JWT Authentication with RBAC

## Overview

Empire v7.3's RBAC system now supports **dual authentication**:
1. **API Keys** (`emp_xxx` format) - For service-to-service communication
2. **Clerk JWT Tokens** (Bearer tokens) - For user authentication from frontend

## Authentication Flow

### API Key Authentication
```
Authorization: emp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Process**:
1. Client sends API key in `Authorization` header
2. Middleware validates key via bcrypt comparison
3. Returns `user_id` from API key record

**Use Cases**:
- Server-to-server API calls
- Automated scripts and services
- Integration testing
- Background workers

### Clerk JWT Authentication
```
Authorization: Bearer <clerk_session_token>
```

**Process**:
1. User signs in via Clerk on frontend
2. Frontend sends JWT session token
3. Middleware validates token with Clerk API
4. Returns `user_id` from Clerk session

**Use Cases**:
- User-facing web applications
- Mobile apps
- Frontend dashboards
- Interactive sessions

## Implementation Details

### Middleware: `app/middleware/auth.py`

The `get_current_user()` function handles both authentication methods:

```python
async def get_current_user(
    authorization: Optional[str] = Header(None),
    rbac_service: RBACService = Depends(get_rbac_service)
) -> str:
    """
    Extract and validate user from JWT or API key.

    Supports two authentication methods:
    1. API Key: Authorization header with emp_xxx format
    2. JWT Token: Authorization header with Bearer <token> format
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    # API Key authentication
    if authorization.startswith("emp_"):
        key_record = await rbac_service.validate_api_key(authorization)
        if not key_record:
            raise HTTPException(status_code=401, detail="Invalid or expired API key")
        return key_record["user_id"]

    # Clerk JWT authentication
    elif authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        session = clerk_client.sessions.verify_token(token)
        if not session:
            raise HTTPException(status_code=401, detail="Invalid or expired JWT token")
        return session.user_id

    else:
        raise HTTPException(status_code=401, detail="Invalid authorization format")
```

### Clerk Client: `app/middleware/clerk_auth.py`

```python
from clerk_backend_api import Clerk
import os

# Initialize Clerk client with secret key
clerk_client = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))
```

## Environment Variables Required

### Local Development (.env)
```bash
CLERK_SECRET_KEY=sk_test_xxxxxxxxxxxxx
CLERK_PUBLISHABLE_KEY=pk_test_xxxxxxxxxxxx  # For frontend
```

### Render Production
Configured via Render dashboard or MCP:
```bash
CLERK_SECRET_KEY=sk_live_xxxxxxxxxxxxx
CLERK_PUBLISHABLE_KEY=pk_live_xxxxxxxxxxxx
```

## Frontend Integration Example

### React with Clerk

```javascript
import { ClerkProvider, SignIn, useAuth } from "@clerk/clerk-react";

function App() {
  return (
    <ClerkProvider publishableKey={process.env.REACT_APP_CLERK_PUBLISHABLE_KEY}>
      <AuthenticatedApp />
    </ClerkProvider>
  );
}

function AuthenticatedApp() {
  const { getToken } = useAuth();

  // Get Clerk session token
  const token = await getToken();

  // Call RBAC endpoints with Bearer token
  const response = await fetch("https://jb-empire-api.onrender.com/api/rbac/keys", {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json"
    }
  });

  return <div>...</div>;
}
```

### Python Client with JWT

```python
import requests

# User obtains JWT from Clerk frontend
clerk_jwt_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."

headers = {
    "Authorization": f"Bearer {clerk_jwt_token}",
    "Content-Type": "application/json"
}

# List user's API keys
response = requests.get(
    "https://jb-empire-api.onrender.com/api/rbac/keys",
    headers=headers
)

print(response.json())
```

## RBAC Endpoints with Dual Auth

All 9 RBAC endpoints support **both** authentication methods:

| Endpoint | Method | Auth Required | Admin Only |
|----------|--------|---------------|------------|
| `/api/rbac/roles` | GET | ❌ Public | No |
| `/api/rbac/keys` | POST | ✅ API Key or JWT | No |
| `/api/rbac/keys` | GET | ✅ API Key or JWT | No |
| `/api/rbac/keys/rotate` | POST | ✅ API Key or JWT | No |
| `/api/rbac/keys/revoke` | POST | ✅ API Key or JWT | No |
| `/api/rbac/users/assign-role` | POST | ✅ API Key or JWT | ✅ Yes |
| `/api/rbac/users/revoke-role` | POST | ✅ API Key or JWT | ✅ Yes |
| `/api/rbac/users/{user_id}/roles` | GET | ✅ API Key or JWT | No* |
| `/api/rbac/audit-logs` | GET | ✅ API Key or JWT | ✅ Yes |

*Non-admins can only view their own roles

## Testing

### Test with API Key
```bash
# Create API key via service (see test_rbac_integration.py)
export TEST_API_KEY="emp_xxxxx..."

# Test endpoint
curl -X GET https://jb-empire-api.onrender.com/api/rbac/keys \
  -H "Authorization: $TEST_API_KEY"
```

### Test with Clerk JWT
```bash
# Obtain JWT from Clerk (via frontend or Clerk Dashboard)
export CLERK_JWT="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."

# Test endpoint
curl -X GET https://jb-empire-api.onrender.com/api/rbac/keys \
  -H "Authorization: Bearer $CLERK_JWT"
```

## Security Considerations

### API Keys
- ✅ Bcrypt hashed (never stored in plaintext)
- ✅ One-time view (shown only at creation)
- ✅ Rotation support
- ✅ Revocation support
- ✅ Rate limiting per key
- ✅ Expiration dates
- ✅ Scope-based permissions

### Clerk JWTs
- ✅ Validated against Clerk API
- ✅ Short-lived tokens (auto-refresh)
- ✅ User session management
- ✅ Multi-factor authentication support
- ✅ OAuth/SSO integration
- ✅ Automatic token rotation

### Best Practices

1. **Use JWT for User Sessions**:
   - Frontend applications
   - Interactive user sessions
   - Web and mobile apps

2. **Use API Keys for Services**:
   - Background workers
   - Cron jobs
   - Server-to-server communication
   - Long-running processes

3. **Never Commit Keys or Tokens**:
   - Store in `.env` file (gitignored)
   - Use environment variables
   - Rotate keys regularly

4. **Monitor Audit Logs**:
   - Track all RBAC operations
   - Review suspicious activity
   - Compliance reporting

## Troubleshooting

### JWT Authentication Fails
```
jwt_authentication_failed error="Invalid token"
```

**Solutions**:
1. Check `CLERK_SECRET_KEY` is set correctly
2. Verify token is not expired (check exp claim)
3. Ensure token format is `Bearer <token>`
4. Verify Clerk project ID matches

### API Key Authentication Fails
```
api_key_authentication_failed key_prefix=emp_xxxx
```

**Solutions**:
1. Verify API key is active (not revoked)
2. Check expiration date
3. Confirm key hasn't been rotated
4. Use full key (not just prefix)

### Permission Denied
```
admin_access_denied roles=[] user_id=user_xxx
```

**Solutions**:
1. Assign appropriate role via `/api/rbac/users/assign-role`
2. Verify user has active role assignment
3. Check role expiration date
4. Contact admin to grant permissions

## Production Deployment Status

✅ **Deployed to Render**: https://jb-empire-api.onrender.com
✅ **RBAC Endpoints Live**: All 9 endpoints operational
✅ **Clerk Integration**: Active and ready
✅ **Swagger UI**: https://jb-empire-api.onrender.com/docs

## Next Steps

1. ✅ Deploy RBAC to production - **DONE**
2. ✅ Integrate Clerk JWT authentication - **DONE**
3. ⏭️ Test with real Clerk tokens from frontend
4. ⏭️ Update frontend to use RBAC endpoints
5. ⏭️ Set up role assignments for users
6. ⏭️ Configure budget alerts and monitoring

## Support

For issues or questions:
- Check Swagger UI: https://jb-empire-api.onrender.com/docs
- Review audit logs: GET `/api/rbac/audit-logs` (admin only)
- See integration tests: `tests/test_rbac_integration.py`
- API documentation: `docs/rbac_api_design.md`
