# Feature Flag Admin Interface Guide

**Empire v7.3 - Task 3.5**

Comprehensive guide for administrators to manage feature flags using the Empire Admin API.

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Admin Endpoints](#admin-endpoints)
4. [Usage Examples](#usage-examples)
5. [Bulk Operations](#bulk-operations)
6. [Scheduled Changes](#scheduled-changes)
7. [Monitoring & Auditing](#monitoring--auditing)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The Feature Flag Admin Interface provides **secure, admin-only access** to manage feature flags across all Empire environments. This interface is built on top of the Feature Flag Management system (Task 3.2-3.4).

### Key Features

- **Admin-Only Access**: All write operations require admin role
- **Bulk Operations**: Enable/disable multiple flags simultaneously
- **Scheduled Changes**: Plan flag activations for future dates
- **Audit Trail**: Complete history of all flag changes
- **Statistics**: Usage metrics and change frequency
- **Public Read Access**: Applications can check flags without authentication

### Security Model

| Endpoint Type | Authentication | Authorization | Purpose |
|---------------|----------------|---------------|---------|
| **Read-Only** (LIST, GET, CHECK) | Optional | Public | Applications checking flags |
| **Admin-Only** (CREATE, UPDATE, DELETE) | Required | Admin role | Flag management |
| **Bulk Operations** | Required | Admin role | Multi-flag operations |
| **Scheduled Changes** | Required | Admin role | Planned rollouts |

---

## Authentication

The Feature Flag Admin API supports **two authentication methods**:

### 1. API Key Authentication (Recommended for Automation)

Use Empire API keys with admin role:

```bash
# Generate an admin API key first (via /api/rbac/keys endpoint)
# Then use the key in the Authorization header
curl -X POST https://jb-empire-api.onrender.com/api/feature-flags \
  -H "Authorization: emp_xxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "flag_name": "feature_new_feature",
    "enabled": false,
    "description": "New feature rollout",
    "created_by": "admin@empire.ai"
  }'
```

**API Key Format**: `emp_` followed by 32 alphanumeric characters

**Key Features**:
- Long-lived credentials (configurable expiration)
- Rate limiting (configurable per key)
- Audit logging of key usage
- Can be rotated without changing code

### 2. JWT Bearer Token Authentication (For User Sessions)

Use Clerk JWT tokens for user-based admin access:

```bash
# Use JWT token from Clerk authentication
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_course_management \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "rollout_percentage": 50,
    "updated_by": "user@empire.ai"
  }'
```

**JWT Features**:
- Short-lived tokens (24-hour expiry)
- User identity verification via Clerk
- Automatic role validation
- Session-based access

---

## Admin Endpoints

### Public/Read-Only Endpoints (No Auth Required)

#### 1. List All Flags

```http
GET /api/feature-flags?enabled_only=false
```

**Query Parameters**:
- `enabled_only` (boolean, default: `false`) - Filter to only enabled flags

**Response** (200 OK):
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "flag_name": "feature_course_management",
    "enabled": true,
    "description": "Feature 3: Enable Course & Curriculum Management features",
    "rollout_percentage": 50,
    "user_segments": [],
    "metadata": {"version": "v7.3", "feature_id": "F3"},
    "created_by": "system",
    "updated_by": "admin",
    "created_at": "2025-01-24T10:00:00Z",
    "updated_at": "2025-01-24T14:30:00Z"
  }
]
```

#### 2. Get Specific Flag

```http
GET /api/feature-flags/{flag_name}
```

**Example**:
```bash
curl https://jb-empire-api.onrender.com/api/feature-flags/feature_course_management
```

**Response** (200 OK): Single flag object

#### 3. Check Flag Status

```http
POST /api/feature-flags/{flag_name}/check
Content-Type: application/json
```

**Request Body**:
```json
{
  "user_id": "user_12345",
  "context": {
    "department": "finance",
    "environment": "production"
  }
}
```

**Response** (200 OK):
```json
{
  "flag_name": "feature_course_management",
  "enabled": true,
  "user_id": "user_12345"
}
```

---

### Admin-Only Endpoints (Require Admin Role)

#### 1. Create Feature Flag

```http
POST /api/feature-flags
Authorization: emp_xxxxxxxxxxxxxxxxxxxxx
Content-Type: application/json
```

**Request Body**:
```json
{
  "flag_name": "feature_new_capability",
  "enabled": false,
  "description": "New capability for testing",
  "rollout_percentage": 0,
  "user_segments": [],
  "metadata": {
    "version": "v7.3",
    "feature_id": "F10",
    "team": "backend"
  },
  "created_by": "admin@empire.ai"
}
```

**Response** (201 Created):
```json
{
  "id": "650e8400-e29b-41d4-a716-446655440000",
  "flag_name": "feature_new_capability",
  "enabled": false,
  ...
}
```

**Error Cases**:
- **400 Bad Request**: Flag already exists
- **401 Unauthorized**: Missing or invalid authentication
- **403 Forbidden**: User does not have admin role

#### 2. Update Feature Flag

```http
PUT /api/feature-flags/{flag_name}
Authorization: emp_xxxxxxxxxxxxxxxxxxxxx
Content-Type: application/json
```

**Request Body** (all fields optional):
```json
{
  "enabled": true,
  "rollout_percentage": 50,
  "user_segments": ["beta_users", "premium_customers"],
  "metadata": {
    "rollout_phase": "phase_2"
  },
  "updated_by": "admin@empire.ai"
}
```

**Response** (200 OK):
```json
{
  "message": "Feature flag updated successfully: feature_new_capability",
  "flag_name": "feature_new_capability"
}
```

#### 3. Delete Feature Flag

```http
DELETE /api/feature-flags/{flag_name}?deleted_by=admin@empire.ai
Authorization: emp_xxxxxxxxxxxxxxxxxxxxx
```

**Response** (204 No Content): Empty body on success

**Warning**: Deleting a flag will cause it to be disabled for all users immediately. Use with caution in production.

---

## Bulk Operations

Bulk operations allow administrators to enable or disable multiple flags simultaneously, useful for:
- **Rollback scenarios**: Disable all flags related to a problematic feature
- **Environment parity**: Sync flags between staging and production
- **Feature groups**: Enable related flags together (e.g., all v7.3 features)

### Bulk Enable

```http
POST /api/feature-flags/bulk/enable
Authorization: emp_xxxxxxxxxxxxxxxxxxxxx
Content-Type: application/json
```

**Request Body**:
```json
{
  "flag_names": [
    "feature_course_management",
    "feature_reporting_dashboard",
    "feature_integration_api"
  ],
  "updated_by": "admin@empire.ai"
}
```

**Response** (200 OK):
```json
{
  "message": "Bulk enable completed: 3 succeeded, 0 failed",
  "results": {
    "success": [
      "feature_course_management",
      "feature_reporting_dashboard",
      "feature_integration_api"
    ],
    "failed": []
  }
}
```

### Bulk Disable

```http
POST /api/feature-flags/bulk/disable
Authorization: emp_xxxxxxxxxxxxxxxxxxxxx
Content-Type: application/json
```

**Request Body**: Same as bulk enable

**Use Cases**:
```bash
# Scenario 1: Emergency rollback (disable all v7.3 features)
curl -X POST https://jb-empire-api.onrender.com/api/feature-flags/bulk/disable \
  -H "Authorization: emp_xxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "flag_names": [
      "feature_department_research_development",
      "feature_processing_status_details",
      "feature_course_management",
      "feature_reporting_dashboard",
      "feature_integration_api",
      "feature_webhook_notifications",
      "feature_advanced_search",
      "feature_batch_operations",
      "feature_api_versioning"
    ],
    "updated_by": "admin@empire.ai"
  }'

# Scenario 2: Enable beta features for testing
curl -X POST https://jb-empire-api.onrender.com/api/feature-flags/bulk/enable \
  -H "Authorization: emp_xxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "flag_names": ["feature_advanced_search", "feature_batch_operations"],
    "updated_by": "qa@empire.ai"
  }'
```

---

## Scheduled Changes

Schedule feature flag changes for future execution. This enables planned rollouts and time-based activations.

**Note**: The current implementation uses in-memory storage. For production, integrate with Celery task scheduler or database-backed scheduler for persistence across restarts.

### Schedule a Flag Change

```http
POST /api/feature-flags/schedule
Authorization: emp_xxxxxxxxxxxxxxxxxxxxx
Content-Type: application/json
```

**Request Body**:
```json
{
  "flag_name": "feature_course_management",
  "enabled": true,
  "rollout_percentage": 100,
  "scheduled_at": "2025-02-01T00:00:00Z",
  "updated_by": "admin@empire.ai"
}
```

**Response** (201 Created):
```json
{
  "message": "Flag change scheduled successfully for 2025-02-01T00:00:00",
  "schedule": {
    "id": 1,
    "flag_name": "feature_course_management",
    "enabled": true,
    "rollout_percentage": 100,
    "scheduled_at": "2025-02-01T00:00:00",
    "updated_by": "admin@empire.ai",
    "status": "pending",
    "created_at": "2025-01-24T15:00:00"
  },
  "note": "IMPORTANT: This is an in-memory scheduler. For production, integrate with Celery or database-backed scheduler."
}
```

### List Scheduled Changes

```http
GET /api/feature-flags/schedule
Authorization: emp_xxxxxxxxxxxxxxxxxxxxx
```

**Response** (200 OK):
```json
{
  "scheduled_changes": [
    {
      "id": 1,
      "flag_name": "feature_course_management",
      "enabled": true,
      "rollout_percentage": 100,
      "scheduled_at": "2025-02-01T00:00:00",
      "updated_by": "admin@empire.ai",
      "status": "pending",
      "created_at": "2025-01-24T15:00:00"
    }
  ],
  "count": 1,
  "note": "This is an in-memory scheduler. For production, integrate with Celery or database-backed scheduler."
}
```

### Use Cases

```bash
# Scenario 1: Weekend rollout (activate feature at midnight on Saturday)
curl -X POST https://jb-empire-api.onrender.com/api/feature-flags/schedule \
  -H "Authorization: emp_xxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "flag_name": "feature_reporting_dashboard",
    "enabled": true,
    "rollout_percentage": 0,
    "scheduled_at": "2025-02-01T00:00:00Z",
    "updated_by": "admin@empire.ai"
  }'

# Scenario 2: Gradual rollout (increase percentage over time)
# Schedule 1: 10% rollout at 9am
curl -X POST https://jb-empire-api.onrender.com/api/feature-flags/schedule \
  -H "Authorization: emp_xxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "flag_name": "feature_advanced_search",
    "rollout_percentage": 10,
    "scheduled_at": "2025-01-25T09:00:00Z",
    "updated_by": "admin@empire.ai"
  }'

# Schedule 2: 50% rollout at 1pm (if metrics look good)
curl -X POST https://jb-empire-api.onrender.com/api/feature-flags/schedule \
  -H "Authorization: emp_xxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "flag_name": "feature_advanced_search",
    "rollout_percentage": 50,
    "scheduled_at": "2025-01-25T13:00:00Z",
    "updated_by": "admin@empire.ai"
  }'
```

---

## Monitoring & Auditing

### View Audit Trail

```http
GET /api/feature-flags/{flag_name}/audit?limit=100
```

**Example**:
```bash
curl https://jb-empire-api.onrender.com/api/feature-flags/feature_course_management/audit?limit=50
```

**Response** (200 OK):
```json
{
  "flag_name": "feature_course_management",
  "audit_trail": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "flag_name": "feature_course_management",
      "action": "update",
      "old_value": {"enabled": false, "rollout_percentage": 0},
      "new_value": {"enabled": true, "rollout_percentage": 50},
      "changed_by": "admin@empire.ai",
      "changed_at": "2025-01-24T14:30:00Z",
      "ip_address": "192.168.1.100"
    }
  ],
  "count": 1
}
```

### View Statistics

```http
GET /api/feature-flags/stats/all
```

**Response** (200 OK):
```json
{
  "statistics": [
    {
      "flag_name": "feature_course_management",
      "total_changes": 15,
      "enabled_changes": 5,
      "disabled_changes": 10,
      "last_updated": "2025-01-24T14:30:00Z",
      "created_at": "2025-01-01T00:00:00Z"
    }
  ],
  "count": 9
}
```

---

## Best Practices

### 1. Use API Keys for Automation

For CI/CD pipelines and scripts, always use API keys instead of JWT tokens:

```bash
# Good: API key in environment variable
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_new_feature \
  -H "Authorization: $EMPIRE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "updated_by": "ci-cd-pipeline"}'

# Bad: Hardcoded JWT (expires after 24 hours)
curl -X PUT ... -H "Authorization: Bearer eyJhbGciOi..."
```

### 2. Always Provide `updated_by` Field

Track who made changes for audit purposes:

```json
{
  "enabled": true,
  "updated_by": "admin@empire.ai"  // Always include this
}
```

### 3. Use Gradual Rollouts

Instead of enabling a flag for 100% of users immediately, use gradual rollouts:

```bash
# Week 1: 10% rollout
curl -X PUT .../feature_new_feature -d '{"enabled": true, "rollout_percentage": 10}'

# Week 2: 50% rollout (if metrics look good)
curl -X PUT .../feature_new_feature -d '{"enabled": true, "rollout_percentage": 50}'

# Week 3: Full rollout
curl -X PUT .../feature_new_feature -d '{"enabled": true, "rollout_percentage": 100}'
```

### 4. Use Bulk Operations for Related Flags

Group related flags and manage them together:

```bash
# Enable all reporting features at once
curl -X POST .../bulk/enable -d '{
  "flag_names": [
    "feature_reporting_dashboard",
    "feature_reporting_exports",
    "feature_reporting_charts"
  ]
}'
```

### 5. Schedule Changes During Low-Traffic Windows

Use scheduled changes for overnight or weekend deployments:

```json
{
  "scheduled_at": "2025-02-01T02:00:00Z",  // 2 AM on Saturday
  "enabled": true
}
```

### 6. Monitor Audit Logs

Regularly review audit logs for unauthorized changes:

```bash
# Check recent changes
curl https://jb-empire-api.onrender.com/api/feature-flags/feature_new_feature/audit?limit=50
```

### 7. Document Flag Metadata

Use the `metadata` field to track additional context:

```json
{
  "metadata": {
    "jira_ticket": "EMP-123",
    "team": "backend",
    "rollout_phase": "beta",
    "expected_rollout_date": "2025-02-01"
  }
}
```

---

## Troubleshooting

### Issue 1: 401 Unauthorized

**Symptom**: All admin endpoints return 401

**Causes**:
1. Missing `Authorization` header
2. Invalid API key or JWT token
3. Expired JWT token (24-hour limit)

**Solutions**:
```bash
# Check if API key is correct format (emp_xxx)
echo $EMPIRE_API_KEY  # Should start with "emp_"

# For JWT: Get a fresh token from Clerk
# JWT tokens expire after 24 hours - re-authenticate

# Test with curl verbose mode
curl -v -X GET https://jb-empire-api.onrender.com/api/feature-flags/feature_test \
  -H "Authorization: emp_xxxxxxxxxxxxxxxxxxxxx"
```

### Issue 2: 403 Forbidden

**Symptom**: Authentication succeeds but admin endpoints return 403

**Cause**: User does not have admin role

**Solution**:
1. Verify user has admin role assigned in RBAC system
2. Use `/api/rbac/users/{user_id}/roles` to check roles
3. Assign admin role if missing:
```bash
curl -X POST https://jb-empire-api.onrender.com/api/rbac/roles/assign \
  -H "Authorization: $ADMIN_API_KEY" \
  -d '{"user_id": "user_123", "role_id": "admin"}'
```

### Issue 3: Bulk Operations Partially Fail

**Symptom**: Some flags update successfully, others fail

**Cause**: Some flags don't exist or validation failed

**Solution**: Check the response `failed` array for specific errors:
```json
{
  "results": {
    "success": ["feature_a", "feature_b"],
    "failed": [
      {"flag_name": "feature_c", "reason": "Flag not found"}
    ]
  }
}
```

Then fix each failure individually:
```bash
# Create missing flag first
curl -X POST .../feature-flags -d '{"flag_name": "feature_c", ...}'

# Retry bulk operation
curl -X POST .../bulk/enable -d '{"flag_names": ["feature_c"]}'
```

### Issue 4: Scheduled Changes Not Executing

**Symptom**: Scheduled changes remain in "pending" status after scheduled time

**Cause**: In-memory scheduler does not have a background worker running

**Solution** (Production):
1. Integrate with Celery for persistent scheduling:
```python
from celery import Celery
from datetime import datetime

@celery.task
def execute_scheduled_flag_change(flag_name, enabled, rollout_percentage, updated_by):
    ff_manager = get_feature_flag_manager()
    ff_manager.update_flag(
        flag_name=flag_name,
        enabled=enabled,
        rollout_percentage=rollout_percentage,
        updated_by=updated_by
    )

# Schedule with Celery
execute_scheduled_flag_change.apply_async(
    args=[flag_name, enabled, rollout_percentage, updated_by],
    eta=scheduled_at
)
```

### Issue 5: Cache Not Updating After Flag Change

**Symptom**: Flag changes not reflected immediately in application

**Cause**: Redis cache not invalidating properly

**Solution**:
1. Check cache TTL (default 60 seconds)
2. Wait for cache expiration or manually invalidate:
```bash
# Redis CLI
redis-cli -h <redis-host> -p 6379
> KEYS feature_flag:*
> DEL feature_flag:feature_name:*
```

3. Verify cache invalidation in feature_flags.py:320

---

## Summary

The Feature Flag Admin Interface provides:

✅ **Secure Admin Access**: Role-based authentication with API keys or JWT
✅ **Bulk Operations**: Manage multiple flags simultaneously
✅ **Scheduled Changes**: Plan rollouts in advance
✅ **Complete Audit Trail**: Track all changes for compliance
✅ **Statistics**: Monitor flag usage and change frequency
✅ **Public Read Access**: Applications can check flags without auth

**Next Steps**:
1. Generate an admin API key via `/api/rbac/keys`
2. Test endpoints using the examples in this guide
3. Set up automated flag management in CI/CD pipelines
4. Monitor audit logs regularly
5. For production: Integrate Celery scheduler for persistent scheduled changes

**Related Documentation**:
- [Feature Flag Implementation Summary](FEATURE_FLAG_IMPLEMENTATION_SUMMARY.md) - Technical architecture
- [Feature Flag Configuration Guide](FEATURE_FLAG_CONFIGURATION_GUIDE.md) - Developer integration
- [Feature Flag Deployment Guide](FEATURE_FLAG_DEPLOYMENT_GUIDE.md) - Production deployment
- [RBAC API Documentation](/api/rbac/docs) - Admin user and API key management

**Support**: Contact DevOps team or refer to Empire v7.3 documentation for additional help.
