# RBAC Frontend Integration Guide

## Overview

Empire Chat UI now includes a comprehensive RBAC Management Dashboard integrated with Clerk authentication. Users can manage API keys, view their roles, and monitor audit logs (admin only) directly from the web interface.

## Architecture

```
┌──────────────────────────────────────┐
│     Clerk Authentication Page         │
│        (/ - Root endpoint)            │
│   - Sign in/Sign up with Clerk       │
│   - JWT token stored in localStorage  │
└─────────────┬────────────────────────┘
              │ After auth: redirect
              ↓
    ┌─────────────────────┐
    │   Chat Interface    │
    │   (/chat endpoint)  │
    │  - AI Chat with     │
    │    streaming        │
    │  - Nav to RBAC →    │
    └──────────┬──────────┘
               │
               ↓
    ┌──────────────────────┐
    │  RBAC Dashboard      │
    │  (/rbac endpoint)    │
    │  - API Key Mgmt      │
    │  - Role Viewing      │
    │  - Audit Logs        │
    │  ← Back to Chat      │
    └──────────────────────┘
```

## Files Created/Modified

### New Files

1. **`rbac_dashboard.py`**
   - Standalone Gradio RBAC management dashboard
   - 3 tabs: API Keys, Roles, Audit Logs
   - All RBAC operations integrated

### Modified Files

1. **`app_with_auth.py`**
   - Integrated RBAC dashboard at `/rbac`
   - Added navigation buttons
   - Mounts both chat and RBAC Gradio apps

## Features

### 1. API Key Management Tab 🔑

Users can:
- **Create new API keys** with:
  - Custom name
  - Role assignment (admin, editor, viewer, guest)
  - Scopes (comma-separated permissions)
  - Expiration period (days, 0 = never)

- **List all API keys** showing:
  - Key ID
  - Name and role
  - Scopes
  - Creation date
  - Expiration date
  - Last used timestamp
  - Active status

- **Rotate API keys**:
  - Provide key ID
  - Get new key, old key revoked automatically

- **Revoke API keys**:
  - Provide key ID
  - Key immediately invalidated

**⚠️ Important**: New API keys are shown only once at creation. Users must copy and save them immediately.

### 2. Roles Tab 👤

Users can:
- **View available roles** (public):
  - Role name and description
  - Permissions list

- **View assigned roles**:
  - Current user's roles
  - Role descriptions
  - Permissions granted
  - Who granted the role
  - Grant timestamp
  - Expiration date

### 3. Audit Logs Tab 📊 (Admin Only)

Admins can:
- **View security events**:
  - API key creation/rotation/revocation
  - Role assignments/revocations
  - Authentication events

- **Filter by event type**:
  - Optional filter input
  - Leave empty for all events

- **Configure result limit**:
  - 10-200 events
  - Default: 50

## User Flow

### First-Time User

1. **Visit** https://jb-empire-chat.onrender.com/
2. **Sign in** using Clerk (email/password, OAuth, etc.)
3. **Redirected** to `/chat` after authentication
4. **Click** "🔐 RBAC Dashboard" button to manage API keys
5. **Create** first API key for programmatic access
6. **Copy** and save the API key (shown only once)
7. **Use** API key in scripts/services

### Returning User

1. **Visit** https://jb-empire-chat.onrender.com/
2. **Automatically authenticated** (if session valid)
3. **Navigate** between Chat and RBAC as needed
4. **Manage** API keys, view roles, check audit logs

## API Integration

All RBAC dashboard operations call the production RBAC API:

**Base URL**: `https://jb-empire-api.onrender.com/api/rbac`

### Authentication

The dashboard automatically:
1. Retrieves Clerk JWT from `localStorage`
2. Injects token into API requests as `Authorization: Bearer <token>`
3. Handles 401 errors (redirect to login)

### Endpoints Used

| Operation | Endpoint | Method |
|-----------|----------|--------|
| List roles | `/roles` | GET |
| Create key | `/keys` | POST |
| List user keys | `/keys` | GET |
| Rotate key | `/keys/rotate` | POST |
| Revoke key | `/keys/revoke` | POST |
| Get user roles | `/users/me/roles` | GET |
| Get audit logs | `/audit-logs` | GET |

## Local Development

### Run Integrated App

```bash
# Start the integrated app (chat + RBAC)
python3 app_with_auth.py
```

**Access**:
- Auth page: http://localhost:7860/
- Chat: http://localhost:7860/chat
- RBAC: http://localhost:7860/rbac

### Run RBAC Dashboard Standalone

```bash
# Start just the RBAC dashboard
python3 rbac_dashboard.py
```

**Access**: http://localhost:7861/

### Environment Variables

Add to `.env`:

```bash
# Clerk Authentication (required)
CLERK_SECRET_KEY=sk_test_xxxxx
CLERK_PUBLISHABLE_KEY=pk_test_xxxxx
VITE_CLERK_PUBLISHABLE_KEY=pk_test_xxxxx  # For frontend

# API Configuration
EMPIRE_API_URL=https://jb-empire-api.onrender.com

# UI Ports (optional, defaults shown)
CHAT_UI_PORT=7860
CHAT_UI_HOST=0.0.0.0
RBAC_DASHBOARD_PORT=7861
RBAC_DASHBOARD_HOST=0.0.0.0
```

**Security Note**: All actual credential values are in `.env` file (gitignored)

## Deployment to Render

### Update Chat UI Service (jb-empire-chat)

**Service ID**: `srv-d47ptdmr433s739ljolg`

1. **Update start command**:
   ```bash
   python3 app_with_auth.py
   ```

2. **Ensure environment variables are set**:
   - `CLERK_SECRET_KEY`
   - `CLERK_PUBLISHABLE_KEY`
   - `VITE_CLERK_PUBLISHABLE_KEY`
   - `EMPIRE_API_URL=https://jb-empire-api.onrender.com`

3. **Push code to main branch** (auto-deploy enabled)

4. **Verify deployment**:
   - Auth: https://jb-empire-chat.onrender.com/
   - Chat: https://jb-empire-chat.onrender.com/chat
   - RBAC: https://jb-empire-chat.onrender.com/rbac

### Deployment via Render MCP

```javascript
// Update environment variables
await render.update_environment_variables({
  serviceId: "srv-d47ptdmr433s739ljolg",
  envVars: [
    {key: "CLERK_PUBLISHABLE_KEY", value: "pk_test_xxxxx"},
    {key: "VITE_CLERK_PUBLISHABLE_KEY", value: "pk_test_xxxxx"}
  ]
});

// Trigger manual deploy (if auto-deploy disabled)
await render.create_deploy({
  serviceId: "srv-d47ptdmr433s739ljolg"
});
```

## Testing the Integration

### Test 1: Authentication Flow

1. Visit auth page: https://jb-empire-chat.onrender.com/
2. Sign in with Clerk
3. Verify redirect to `/chat`
4. Check `localStorage.getItem('clerk_session_token')` in browser console
5. Should see JWT token

### Test 2: API Key Creation

1. Click "🔐 RBAC Dashboard" button
2. Fill in create key form:
   - Name: "Test Key"
   - Role: viewer
   - Scopes: documents:read
   - Expires: 90 days
3. Click "🔒 Create API Key"
4. Copy the displayed API key (shown only once)
5. Verify key appears in "List My Keys" section

### Test 3: API Key Usage

```bash
# Use the created API key with the API
export API_KEY="emp_xxxxx..."

curl -X GET https://jb-empire-api.onrender.com/api/rbac/keys \
  -H "Authorization: $API_KEY"
```

Expected: 200 OK with list of keys

### Test 4: Role Viewing

1. In RBAC dashboard, click "Roles" tab
2. Click "📋 List All Roles"
3. Verify roles displayed: admin, editor, viewer, guest
4. Click "👤 View My Roles"
5. Verify your assigned roles displayed

### Test 5: Admin Features (If Admin)

1. Click "Audit Logs" tab
2. Click "📊 View Audit Logs"
3. Verify security events displayed
4. Test event type filter (e.g., "api_key_created")
5. Test limit parameter (e.g., 20 events)

### Test 6: Navigation

1. From RBAC dashboard, click "💬 Back to Chat"
2. Verify redirect to chat interface
3. From chat, click "🔐 RBAC Dashboard"
4. Verify redirect to RBAC dashboard
5. Verify token persists across navigation

## Security Considerations

### Token Storage

- JWT stored in `localStorage` for persistence
- Automatically injected into API requests
- Cleared on logout
- ⚠️ Users should log out on shared devices

### API Key Security

- Keys shown only once at creation
- Keys are bcrypt hashed in database
- Prefix shown in list view (emp_xxxxx...)
- Revoked keys cannot be reused

### RBAC Enforcement

- Backend validates JWT on every request
- Admin endpoints check role permissions
- Audit logs track all security events
- Failed auth attempts are logged

## Troubleshooting

### Issue: "Authentication failed" error

**Cause**: JWT token invalid or expired

**Solution**:
1. Check browser console for token
2. Click "🚪 Sign Out"
3. Sign in again
4. Token will be refreshed

### Issue: "403 Forbidden" on audit logs

**Cause**: User doesn't have admin role

**Solution**:
1. Contact administrator
2. Request admin role assignment
3. Admin uses `/api/rbac/users/assign-role` endpoint

### Issue: API key creation fails

**Possible causes**:
1. Invalid scope format → Use comma-separated list
2. Role doesn't exist → Use: admin, editor, viewer, guest
3. Missing authentication → Check if logged in
4. Backend API down → Check https://jb-empire-api.onrender.com/health

### Issue: Navigation buttons not working

**Solution**:
1. Check browser console for JavaScript errors
2. Verify `localStorage` has `clerk_session_token`
3. Clear cache and reload
4. Try different browser

## API Reference

### Create API Key

**Request**:
```json
POST /api/rbac/keys
Authorization: Bearer <clerk_jwt>

{
  "key_name": "Production Service Key",
  "role_name": "editor",
  "scopes": ["documents:read", "documents:write"],
  "expires_at": "2025-12-31T23:59:59Z"
}
```

**Response**:
```json
{
  "api_key": "emp_6dde71a6...",
  "key_id": "key_abc123",
  "user_id": "user_xxx",
  "key_name": "Production Service Key",
  "role_name": "editor",
  "scopes": ["documents:read", "documents:write"],
  "expires_at": "2025-12-31T23:59:59Z",
  "created_at": "2025-11-11T03:00:00Z"
}
```

### List User Keys

**Request**:
```bash
GET /api/rbac/keys
Authorization: Bearer <clerk_jwt>
```

**Response**:
```json
[
  {
    "id": "key_abc123",
    "key_name": "Production Service Key",
    "role": {
      "role_name": "editor",
      "permissions": ["documents:read", "documents:write"]
    },
    "scopes": ["documents:read", "documents:write"],
    "is_active": true,
    "created_at": "2025-11-11T03:00:00Z",
    "expires_at": "2025-12-31T23:59:59Z",
    "last_used_at": "2025-11-11T04:30:00Z"
  }
]
```

## Next Steps

### Enhancements

1. **User Profile Page**:
   - View account details
   - Manage preferences
   - Update email/password

2. **Team Management** (Admin):
   - Invite users
   - Assign roles
   - View team members

3. **Usage Analytics**:
   - API call count per key
   - Rate limit status
   - Cost tracking

4. **Notifications**:
   - Key expiration warnings
   - Security alerts
   - Role changes

5. **Advanced Filtering**:
   - Search audit logs
   - Filter by date range
   - Export to CSV

## Support

### Documentation

- **RBAC API**: `docs/clerk_rbac_integration.md`
- **Backend Auth**: `docs/CLERK_AUTHENTICATION_GUIDE.md`
- **API Reference**: https://jb-empire-api.onrender.com/docs

### Getting Help

1. Check Swagger UI: https://jb-empire-api.onrender.com/docs
2. Review audit logs (if admin)
3. Contact team for access issues
4. Report bugs via GitHub issues

---

**Last Updated**: November 11, 2025
**Version**: 1.0
**Status**: Production Ready
**Author**: Empire Development Team
