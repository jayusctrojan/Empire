# Feature Flags Developer Guide

**Empire v7.3 - Complete Developer Documentation**

Quick reference guide for developers using feature flags in Empire applications.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [How Feature Flags Work](#how-feature-flags-work)
3. [Using Feature Flags in Code](#using-feature-flags-in-code)
4. [Common Use Cases](#common-use-cases)
5. [Best Practices](#best-practices)
6. [Adding New Feature Flags](#adding-new-feature-flags)
7. [Testing with Feature Flags](#testing-with-feature-flags)
8. [Troubleshooting](#troubleshooting)
9. [Architecture Overview](#architecture-overview)
10. [Additional Resources](#additional-resources)

---

## Quick Start

### 1. Check if a Feature is Enabled

```python
from app.core.feature_flags import get_feature_flag_manager

async def my_endpoint():
    ff = get_feature_flag_manager()

    if await ff.is_enabled("feature_course_management"):
        # New feature code
        return handle_with_new_feature()
    else:
        # Legacy code
        return handle_legacy_way()
```

### 2. Check for Specific User

```python
async def user_specific_feature(user_id: str):
    ff = get_feature_flag_manager()

    # Respects rollout percentage (e.g., 50% of users)
    if await ff.is_enabled("feature_advanced_search", user_id=user_id):
        return advanced_search_results()
    else:
        return basic_search_results()
```

### 3. Block Endpoint Entirely

```python
from fastapi import HTTPException

@app.post("/api/courses")
async def create_course(course_data: dict):
    ff = get_feature_flag_manager()

    if not await ff.is_enabled("feature_course_management"):
        raise HTTPException(
            status_code=403,
            detail="Course management feature is not enabled"
        )

    return create_course_logic(course_data)
```

---

## How Feature Flags Work

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       Application Code                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  await ff.is_enabled("feature_name", user_id)          │ │
│  └───────────────────────┬────────────────────────────────┘ │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ▼
         ┌─────────────────────────────────────┐
         │   FeatureFlagManager (Singleton)    │
         │   app/core/feature_flags.py         │
         └─────────┬──────────────────┬────────┘
                   │                  │
        Cache Hit? │                  │ Cache Miss
                   ▼                  ▼
          ┌──────────────┐   ┌──────────────────┐
          │    Redis     │   │   Supabase DB    │
          │  (L1 Cache)  │   │ feature_flags    │
          │  <5ms        │   │ table (<50ms)    │
          └──────────────┘   └──────────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │  PostgreSQL Function     │
                         │  get_feature_flag()      │
                         │  - Checks enabled        │
                         │  - Applies rollout %     │
                         │  - User hash: hash(uid)%100│
                         └──────────────────────────┘
```

### Performance Characteristics

- **Cached Lookup**: <5ms (Redis L1 cache, 60-second TTL)
- **Uncached Lookup**: <50ms (Supabase database query)
- **Cache Invalidation**: Automatic on flag updates

### Rollout Percentage Logic

```python
# Deterministic user hash
user_hash = abs(hash(user_id)) % 100  # 0-99

# Check if user is in rollout percentage
if user_hash < rollout_percentage:
    return True  # User sees the feature
else:
    return False  # User does not see the feature
```

**Key Property**: Same user always gets same result for a given rollout percentage (deterministic).

---

## Using Feature Flags in Code

### Pattern 1: Simple Enable/Disable Check

**Use Case**: Toggle entire feature on/off

```python
from app.core.feature_flags import get_feature_flag_manager

async def some_endpoint():
    ff = get_feature_flag_manager()

    if not await ff.is_enabled("feature_course_management"):
        raise HTTPException(status_code=403, detail="Feature not enabled")

    # Feature code here
    return {"message": "Course created successfully"}
```

### Pattern 2: User-Specific Check with Rollout

**Use Case**: Gradual rollout to percentage of users

```python
async def get_dashboard(user_id: str):
    ff = get_feature_flag_manager()

    # Respects rollout_percentage in database
    # E.g., if rollout_percentage=50, only 50% of users see new dashboard
    if await ff.is_enabled("feature_reporting_dashboard", user_id=user_id):
        return render_new_dashboard()
    else:
        return render_legacy_dashboard()
```

### Pattern 3: FastAPI Dependency for Route Protection

**Use Case**: Protect entire route with feature flag

```python
from fastapi import Depends, HTTPException
from app.core.feature_flags import get_feature_flag_manager

async def require_feature(flag_name: str):
    """Dependency to check if feature is enabled"""
    ff = get_feature_flag_manager()
    if not await ff.is_enabled(flag_name):
        raise HTTPException(
            status_code=403,
            detail=f"Feature not enabled: {flag_name}"
        )
    return True

# Use in route
@app.post("/api/courses")
async def create_course(
    course_data: dict,
    _: bool = Depends(lambda: require_feature("feature_course_management"))
):
    return create_course_logic(course_data)
```

### Pattern 4: Conditional Logic with Context

**Use Case**: Feature flag with additional context (advanced)

```python
async def process_document(doc_id: str, user_id: str, department: str):
    ff = get_feature_flag_manager()

    # Check flag with additional context
    context = {"department": department, "environment": "production"}

    if await ff.is_enabled("feature_batch_operations", user_id=user_id, context=context):
        # Use batch processing
        return batch_process_document(doc_id)
    else:
        # Use single document processing
        return process_single_document(doc_id)
```

### Pattern 5: Progressive Enhancement

**Use Case**: Add new features without breaking existing functionality

```python
async def get_search_results(query: str, user_id: str):
    ff = get_feature_flag_manager()

    # Base search
    results = basic_search(query)

    # Add advanced features if enabled
    if await ff.is_enabled("feature_advanced_search", user_id=user_id):
        results = apply_advanced_ranking(results)
        results = add_semantic_search(results, query)

    if await ff.is_enabled("feature_search_suggestions", user_id=user_id):
        results["suggestions"] = generate_suggestions(query)

    return results
```

---

## Common Use Cases

### Use Case 1: A/B Testing

Test two different implementations and measure which performs better:

```python
async def get_pricing_page(user_id: str):
    ff = get_feature_flag_manager()

    # 50% of users see new pricing model
    if await ff.is_enabled("feature_new_pricing_model", user_id=user_id):
        # Variant A: New pricing
        pricing = calculate_new_pricing()
        analytics.track("pricing_variant", {"variant": "A", "user_id": user_id})
    else:
        # Variant B: Current pricing
        pricing = calculate_current_pricing()
        analytics.track("pricing_variant", {"variant": "B", "user_id": user_id})

    return pricing
```

**Admin Setup**:
```bash
# Set rollout to 50% for A/B test
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_new_pricing_model \
  -H "Authorization: emp_xxxxxxxxxxxxxxxxxxxxx" \
  -d '{"enabled": true, "rollout_percentage": 50}'
```

### Use Case 2: Gradual Rollout (Canary Deployment)

Slowly increase exposure to minimize risk:

```python
async def process_payment(payment_data: dict, user_id: str):
    ff = get_feature_flag_manager()

    # New payment processor (gradual rollout)
    if await ff.is_enabled("feature_new_payment_processor", user_id=user_id):
        return new_payment_processor.process(payment_data)
    else:
        return legacy_payment_processor.process(payment_data)
```

**Rollout Schedule**:
```bash
# Week 1: 10% rollout
curl -X PUT .../feature_new_payment_processor \
  -d '{"enabled": true, "rollout_percentage": 10}'

# Week 2: 50% rollout (if metrics look good)
curl -X PUT .../feature_new_payment_processor \
  -d '{"enabled": true, "rollout_percentage": 50}'

# Week 3: Full rollout
curl -X PUT .../feature_new_payment_processor \
  -d '{"enabled": true, "rollout_percentage": 100}'
```

### Use Case 3: Emergency Kill Switch

Quickly disable problematic features without deploying code:

```python
async def generate_report(report_params: dict):
    ff = get_feature_flag_manager()

    # Resource-intensive feature with kill switch
    if await ff.is_enabled("feature_advanced_reporting"):
        try:
            return generate_advanced_report(report_params)
        except Exception as e:
            logger.error(f"Advanced reporting failed: {e}")
            # Fallback to basic reporting
            return generate_basic_report(report_params)
    else:
        return generate_basic_report(report_params)
```

**Emergency Disable**:
```bash
# Disable feature immediately (no code deploy needed)
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_advanced_reporting \
  -H "Authorization: emp_xxxxxxxxxxxxxxxxxxxxx" \
  -d '{"enabled": false}'
```

### Use Case 4: Beta Feature for Specific Users

Enable features only for beta testers:

```python
async def get_features(user_id: str):
    ff = get_feature_flag_manager()

    features = ["basic_search", "document_upload"]

    # Beta features only for specific users
    if await ff.is_enabled("feature_beta_collaboration", user_id=user_id):
        features.append("real_time_collaboration")

    return {"available_features": features}
```

**Admin Setup** (using user segments):
```bash
# Enable only for beta user segment
curl -X PUT .../feature_beta_collaboration \
  -d '{
    "enabled": true,
    "user_segments": ["beta_testers", "premium_users"]
  }'
```

### Use Case 5: Feature Dependencies

Handle features that depend on other features:

```python
async def get_available_actions(user_id: str):
    ff = get_feature_flag_manager()

    actions = ["view", "edit"]

    # Advanced features require base feature
    if await ff.is_enabled("feature_course_management", user_id=user_id):
        actions.append("create_course")

        # Nested feature (requires parent)
        if await ff.is_enabled("feature_course_assignments", user_id=user_id):
            actions.append("assign_course")

    return {"actions": actions}
```

---

## Best Practices

### 1. Always Use Descriptive Flag Names

```python
# Good: Descriptive, clear purpose
"feature_course_management"
"feature_advanced_search"
"feature_webhook_notifications"

# Bad: Vague, unclear
"new_feature"
"test_flag"
"experimental"
```

### 2. Provide Fallback Behavior

Always handle the case where feature is disabled:

```python
# Good: Has fallback
if await ff.is_enabled("feature_new_algo"):
    result = new_algorithm()
else:
    result = legacy_algorithm()

# Bad: No fallback (breaks if flag is off)
if await ff.is_enabled("feature_new_algo"):
    result = new_algorithm()
# What happens if flag is off?
```

### 3. Use User-Specific Checks for Personalized Features

```python
# Good: User-specific for gradual rollout
await ff.is_enabled("feature_name", user_id=user_id)

# Acceptable: Global check for system-wide features
await ff.is_enabled("feature_maintenance_mode")
```

### 4. Clean Up Old Flags

Remove feature flags once feature is fully rolled out (100% for >1 month):

```python
# Before cleanup
if await ff.is_enabled("feature_old_feature"):
    return new_way()
else:
    return old_way()

# After cleanup (remove flag check, keep new code)
return new_way()
```

### 5. Document Flag Purpose in Code

```python
async def process_document(doc_id: str, user_id: str):
    ff = get_feature_flag_manager()

    # Feature flag: Gradual rollout of new PDF parser
    # Jira: EMP-123
    # Expected rollout: Feb 2025
    # TODO: Remove flag after full rollout
    if await ff.is_enabled("feature_new_pdf_parser", user_id=user_id):
        return parse_with_llama_parse(doc_id)
    else:
        return parse_with_pypdf(doc_id)
```

### 6. Avoid Nested Flag Checks

```python
# Bad: Deeply nested flags (hard to reason about)
if await ff.is_enabled("feature_a"):
    if await ff.is_enabled("feature_b"):
        if await ff.is_enabled("feature_c"):
            return complex_logic()

# Good: Flatten with early returns
if not await ff.is_enabled("feature_a"):
    return basic_logic()

if not await ff.is_enabled("feature_b"):
    return intermediate_logic()

if await ff.is_enabled("feature_c"):
    return complex_logic()

return advanced_logic()
```

### 7. Log Feature Flag Usage

```python
import logging

async def experimental_feature(user_id: str):
    ff = get_feature_flag_manager()
    is_enabled = await ff.is_enabled("feature_experimental", user_id=user_id)

    logger.info(f"Feature flag check: feature_experimental={is_enabled}, user={user_id}")

    if is_enabled:
        return experimental_logic()
    else:
        return stable_logic()
```

### 8. Use Flags for Configuration, Not Business Logic

```python
# Good: Feature toggle
if await ff.is_enabled("feature_new_dashboard"):
    return render_new_dashboard()

# Bad: Business logic via flag (should be in database)
if await ff.is_enabled("user_is_premium"):  # Wrong!
    # This should check user.subscription_tier in database
    return premium_features()
```

---

## Adding New Feature Flags

### Step 1: Create Flag in Database

**Via Admin API**:
```bash
curl -X POST https://jb-empire-api.onrender.com/api/feature-flags \
  -H "Authorization: emp_xxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "flag_name": "feature_my_new_feature",
    "enabled": false,
    "description": "My awesome new feature",
    "rollout_percentage": 0,
    "metadata": {
      "jira_ticket": "EMP-456",
      "team": "backend",
      "expected_rollout_date": "2025-03-01"
    },
    "created_by": "dev@empire.ai"
  }'
```

**Via Supabase SQL** (alternative):
```sql
INSERT INTO feature_flags (flag_name, enabled, description, rollout_percentage, metadata, created_by)
VALUES (
    'feature_my_new_feature',
    FALSE,
    'My awesome new feature',
    0,
    '{"jira_ticket": "EMP-456", "team": "backend"}'::jsonb,
    'dev@empire.ai'
);
```

### Step 2: Use Flag in Code

```python
from app.core.feature_flags import get_feature_flag_manager

@app.post("/api/my-new-endpoint")
async def my_new_endpoint(data: dict, user_id: str):
    ff = get_feature_flag_manager()

    if not await ff.is_enabled("feature_my_new_feature", user_id=user_id):
        raise HTTPException(status_code=403, detail="Feature not enabled")

    # Your new feature logic
    return {"result": "success"}
```

### Step 3: Test Locally

```python
# In tests
async def test_my_new_feature():
    # Enable flag for testing
    ff = get_feature_flag_manager()
    await ff.update_flag("feature_my_new_feature", enabled=True)

    # Test code
    response = await my_new_endpoint({"data": "test"}, user_id="test_user")
    assert response["result"] == "success"
```

### Step 4: Deploy and Gradually Enable

```bash
# Initial deploy: Flag is off (0% rollout)
git push origin main

# Week 1: Enable for 10% of users
curl -X PUT .../feature_my_new_feature -d '{"enabled": true, "rollout_percentage": 10}'

# Week 2: 50% rollout
curl -X PUT .../feature_my_new_feature -d '{"enabled": true, "rollout_percentage": 50}'

# Week 3: Full rollout
curl -X PUT .../feature_my_new_feature -d '{"enabled": true, "rollout_percentage": 100}'
```

### Step 5: Remove Flag (After Successful Rollout)

After feature has been at 100% for >1 month:

```python
# Before
if await ff.is_enabled("feature_my_new_feature", user_id=user_id):
    return new_logic()
else:
    return old_logic()

# After (remove flag, keep new code)
return new_logic()
```

```bash
# Delete flag from database
curl -X DELETE https://jb-empire-api.onrender.com/api/feature-flags/feature_my_new_feature \
  -H "Authorization: emp_xxxxxxxxxxxxxxxxxxxxx"
```

---

## Testing with Feature Flags

### Unit Testing

```python
import pytest
from app.core.feature_flags import get_feature_flag_manager

@pytest.mark.asyncio
async def test_feature_enabled():
    ff = get_feature_flag_manager()

    # Test with feature enabled
    await ff.update_flag("feature_test", enabled=True)
    result = await my_function()
    assert result == expected_with_feature

    # Test with feature disabled
    await ff.update_flag("feature_test", enabled=False)
    result = await my_function()
    assert result == expected_without_feature
```

### Integration Testing

```python
@pytest.mark.asyncio
async def test_api_with_feature_flag():
    # Enable flag for test
    ff = get_feature_flag_manager()
    await ff.update_flag("feature_course_management", enabled=True)

    # Test API endpoint
    response = await client.post("/api/courses", json={"name": "Test Course"})
    assert response.status_code == 201

    # Disable flag
    await ff.update_flag("feature_course_management", enabled=False)

    # Should now return 403
    response = await client.post("/api/courses", json={"name": "Test Course"})
    assert response.status_code == 403
```

### Mocking Feature Flags

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_mocked_flag():
    with patch('app.core.feature_flags.get_feature_flag_manager') as mock_ff:
        mock_instance = AsyncMock()
        mock_instance.is_enabled.return_value = True
        mock_ff.return_value = mock_instance

        # Test code
        result = await my_function()
        assert result == expected_result
```

---

## Troubleshooting

### Issue 1: Flag Check Always Returns False

**Symptoms**:
- Feature is enabled in database (checked via `/api/feature-flags/{name}`)
- `is_enabled()` still returns `False` in code

**Causes**:
1. Cache is stale (60-second TTL)
2. Wrong flag name (typo)
3. User not in rollout percentage

**Solutions**:

```bash
# Check flag status
curl https://jb-empire-api.onrender.com/api/feature-flags/feature_my_feature

# Verify:
# - "enabled": true
# - "rollout_percentage": 100 (or user should be in percentage)

# If cache is stale, wait 60 seconds or invalidate manually
redis-cli -h <redis-host> DEL "feature_flag:feature_my_feature*"
```

```python
# Debug code
ff = get_feature_flag_manager()
flag = await ff.get_flag("feature_my_feature")
print(f"Flag state: {flag.to_dict()}")

is_enabled = await ff.is_enabled("feature_my_feature", user_id="test_user")
print(f"Is enabled for user: {is_enabled}")
```

### Issue 2: Different Users See Different Behavior (Rollout Percentage)

**This is expected behavior** if `rollout_percentage < 100`.

**Explanation**:
```python
# User hash determines if user sees feature
user_hash = abs(hash(user_id)) % 100  # 0-99

# Example with 50% rollout
if user_hash < 50:  # Users with hash 0-49 see feature
    return True
else:  # Users with hash 50-99 do not see feature
    return False
```

**Solution**:
```bash
# Set rollout to 100% for all users
curl -X PUT .../feature_my_feature -d '{"rollout_percentage": 100}'
```

### Issue 3: Flag Changes Not Taking Effect

**Cause**: Redis cache holds old value (60-second TTL)

**Solutions**:

1. **Wait 60 seconds** (cache will expire)

2. **Manual cache invalidation**:
```bash
redis-cli -h <redis-host> -p 6379
> KEYS feature_flag:*
> DEL feature_flag:feature_my_feature:*
```

3. **Disable cache temporarily** (development only):
```bash
# In .env
FEATURE_FLAGS_CACHE_ENABLED=false
```

### Issue 4: Performance Issues with Flag Checks

**Symptoms**: Slow API responses when checking flags

**Causes**:
1. Redis cache not configured
2. Too many sequential flag checks
3. Network latency to Supabase

**Solutions**:

```python
# Bad: Sequential checks (each takes 5-50ms)
if await ff.is_enabled("feature_a"):
    pass
if await ff.is_enabled("feature_b"):
    pass
if await ff.is_enabled("feature_c"):
    pass
# Total: 15-150ms

# Good: Batch checks or cache results
flags_to_check = ["feature_a", "feature_b", "feature_c"]
results = {}
for flag_name in flags_to_check:
    results[flag_name] = await ff.is_enabled(flag_name, user_id=user_id)

# Even better: Minimize flag checks
if await ff.is_enabled("feature_bundle"):  # Single check
    # All three features enabled together
    pass
```

### Issue 5: Flag Not Found in Database

**Error**: `Flag not found: feature_xyz`

**Cause**: Flag hasn't been created yet

**Solution**:
```bash
# Create flag first
curl -X POST https://jb-empire-api.onrender.com/api/feature-flags \
  -H "Authorization: emp_xxxxxxxxxxxxxxxxxxxxx" \
  -d '{
    "flag_name": "feature_xyz",
    "enabled": false,
    "description": "New feature",
    "created_by": "dev@empire.ai"
  }'
```

---

## Architecture Overview

### System Components

```
┌──────────────────────────────────────────────────────────────────┐
│                       Empire v7.3 Application                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Application Code (app/routes/, app/services/)              │ │
│  │  - Checks flags via: await ff.is_enabled(flag, user_id)    │ │
│  └────────────────────────┬───────────────────────────────────┘ │
│                           │                                      │
│  ┌────────────────────────▼───────────────────────────────────┐ │
│  │ FeatureFlagManager (app/core/feature_flags.py)             │ │
│  │  - Singleton pattern                                       │ │
│  │  - Handles caching, rollout logic                          │ │
│  └────────────┬──────────────────────┬────────────────────────┘ │
│               │                      │                          │
└───────────────┼──────────────────────┼──────────────────────────┘
                │                      │
     Cache Hit? │                      │ Cache Miss
                ▼                      ▼
       ┌─────────────────┐    ┌─────────────────────┐
       │  Redis (Upstash)│    │ Supabase PostgreSQL │
       │  L1 Cache       │    │  feature_flags      │
       │  TTL: 60s       │    │  table              │
       │  <5ms           │    │  <50ms              │
       └─────────────────┘    └──────────┬──────────┘
                                         │
                          ┌──────────────▼──────────────┐
                          │ PostgreSQL Functions        │
                          │ - get_feature_flag()        │
                          │ - list_feature_flags()      │
                          │ - log_feature_flag_change() │
                          └─────────────────────────────┘
```

### Database Schema

```sql
-- Main feature flags table
CREATE TABLE feature_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_name VARCHAR(100) UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT FALSE,
    description TEXT,
    rollout_percentage INTEGER DEFAULT 0 CHECK (rollout_percentage >= 0 AND rollout_percentage <= 100),
    user_segments JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_by VARCHAR(255),
    updated_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Audit trail for compliance
CREATE TABLE feature_flag_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_name VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT
);
```

### File Organization

```
Empire/
├── app/
│   ├── core/
│   │   └── feature_flags.py          # FeatureFlagManager singleton
│   ├── routes/
│   │   └── feature_flags.py          # Admin API endpoints
│   └── main.py                        # FastAPI app (initializes manager)
├── supabase/
│   └── migrations/
│       ├── 20251124_v73_create_feature_flags.sql    # Database setup
│       └── 20251124_v73_rollback_feature_flags.sql  # Rollback
├── docs/
│   ├── FEATURE_FLAGS_DEVELOPER_GUIDE.md            # This file
│   ├── FEATURE_FLAG_ADMIN_GUIDE.md                 # Admin operations
│   ├── FEATURE_FLAG_CONFIGURATION_GUIDE.md         # Integration details
│   ├── FEATURE_FLAG_DEPLOYMENT_GUIDE.md            # Deployment procedures
│   └── FEATURE_FLAG_IMPLEMENTATION_SUMMARY.md      # Technical architecture
└── .env.example                      # Environment variables
```

---

## Additional Resources

### Documentation

- **[Feature Flag Implementation Summary](FEATURE_FLAG_IMPLEMENTATION_SUMMARY.md)** - Technical architecture and design decisions
- **[Feature Flag Configuration Guide](FEATURE_FLAG_CONFIGURATION_GUIDE.md)** - Detailed integration patterns for all 9 v7.3 features
- **[Feature Flag Deployment Guide](FEATURE_FLAG_DEPLOYMENT_GUIDE.md)** - Production deployment procedures
- **[Feature Flag Admin Guide](FEATURE_FLAG_ADMIN_GUIDE.md)** - Admin API documentation

### API Documentation

- **Swagger UI**: https://jb-empire-api.onrender.com/docs
- **ReDoc**: https://jb-empire-api.onrender.com/redoc
- **Feature Flags Endpoints**: `/api/feature-flags/*`

### Code References

- **FeatureFlagManager**: `app/core/feature_flags.py:50-500`
- **Admin API Router**: `app/routes/feature_flags.py:1-605`
- **Database Migration**: `supabase/migrations/20251124_v73_create_feature_flags.sql`
- **Main App Integration**: `app/main.py:96-102`

### Examples

```python
# See FEATURE_FLAG_CONFIGURATION_GUIDE.md for:
# - Pattern 1: Simple enable/disable check
# - Pattern 2: User-specific check with rollout
# - Pattern 3: FastAPI dependency for route protection
# - Pattern 4: Conditional logic with context

# See FEATURE_FLAG_ADMIN_GUIDE.md for:
# - Authentication methods (API key vs JWT)
# - Bulk operations (enable/disable multiple flags)
# - Scheduled changes (time-based rollouts)
# - Monitoring and auditing
```

### Support

- **Internal Slack**: #empire-feature-flags
- **Jira Project**: EMP
- **Code Review**: Tag @backend-team
- **Documentation**: This guide + linked resources above

---

## Summary

**Key Takeaways**:

1. ✅ **Always provide fallback behavior** when feature is disabled
2. ✅ **Use user-specific checks** for gradual rollouts
3. ✅ **Test both enabled and disabled states** in unit tests
4. ✅ **Clean up old flags** after full rollout (>1 month at 100%)
5. ✅ **Document flag purpose** in code comments
6. ✅ **Monitor flag usage** via audit logs and statistics
7. ✅ **Use descriptive names** following `feature_*` convention

**Quick Reference**:

```python
from app.core.feature_flags import get_feature_flag_manager

# Simple check
ff = get_feature_flag_manager()
if await ff.is_enabled("feature_name"):
    # New feature code

# User-specific check (respects rollout %)
if await ff.is_enabled("feature_name", user_id=user_id):
    # User sees feature

# Block entire endpoint
if not await ff.is_enabled("feature_name"):
    raise HTTPException(status_code=403, detail="Feature not enabled")
```

**Performance**:
- Cached: <5ms
- Uncached: <50ms
- Cache TTL: 60 seconds

**Next Steps**:
1. Review existing feature flags: `GET /api/feature-flags`
2. Try adding a test flag following the guide above
3. Integrate flags into your feature development
4. Monitor via audit logs: `GET /api/feature-flags/{name}/audit`

For questions or issues, refer to the troubleshooting section or contact the backend team.
