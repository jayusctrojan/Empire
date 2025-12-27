# Empire v7.3 - Feature Flag Deployment Guide

**Task**: 3.4 - Update Environment Configuration
**Date**: 2025-01-24
**Status**: ✅ Complete

---

## Overview

This guide provides step-by-step instructions for deploying the feature flag system to all environments (development, staging, production). The feature flag system uses existing infrastructure (Supabase + Redis) with zero additional cost.

---

## Prerequisites

Before deploying, ensure you have:

✅ **Supabase Access**:
- Project URL and Service Key configured in environment
- Admin access to run migrations via Supabase Dashboard or CLI

✅ **Redis Access**:
- Redis URL configured (Upstash or local Redis)
- Redis accessible from application servers

✅ **Render Access** (for production):
- Access to Empire FastAPI service on Render
- Permissions to update environment variables

---

## Environment Variables

### Required Variables (Already Configured)

The feature flag system uses **existing** environment variables:

```bash
# Supabase (already configured)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=<your-service-key>

# Redis (already configured)
REDIS_URL=rediss://default:<token>@enhanced-manatee-37521.upstash.io:6379
```

### Optional Feature Flag Variables (NEW)

Add these to `.env` or Render environment variables for customization:

```bash
# Enable Redis caching for feature flags (default: true)
FEATURE_FLAGS_CACHE_ENABLED=true

# Cache TTL in seconds (default: 60)
FEATURE_FLAGS_CACHE_TTL=60
```

**Default Values**:
- If not set, `FEATURE_FLAGS_CACHE_ENABLED` defaults to `true`
- If not set, `FEATURE_FLAGS_CACHE_TTL` defaults to `60` seconds

---

## Deployment Checklist

### Step 1: Local Development Setup

#### 1.1 Update .env File

```bash
# Copy .env.example to .env if not already done
cp .env.example .env

# Edit .env and verify/add feature flag settings
# (Optional - defaults are fine for most cases)
FEATURE_FLAGS_CACHE_ENABLED=true
FEATURE_FLAGS_CACHE_TTL=60
```

#### 1.2 Run Database Migration

**Option A: Via Supabase MCP (Recommended)**

```bash
# Using Claude Code with Supabase MCP
mcp__supabase__apply_migration \
  --name "create_feature_flags" \
  --query "$(cat supabase/migrations/20251124_v73_create_feature_flags.sql)"
```

**Option B: Via Supabase Dashboard**

1. Go to https://supabase.com/dashboard/project/{your-project}/sql
2. Copy contents of `supabase/migrations/20251124_v73_create_feature_flags.sql`
3. Paste and execute
4. Verify success in logs

**Option C: Via Supabase CLI**

```bash
# If using Supabase CLI locally
supabase db push
```

#### 1.3 Verify Migration

```bash
# Check tables exist
psql $SUPABASE_URL -c "SELECT tablename FROM pg_tables WHERE tablename IN ('feature_flags', 'feature_flag_audit');"

# Or via Supabase MCP
mcp__supabase__list_tables
```

Expected output:
- `feature_flags` table exists
- `feature_flag_audit` table exists
- 9 feature flags pre-seeded (all disabled)

#### 1.4 Start Application

```bash
cd Empire
uvicorn app.main:app --reload --port 8000
```

Check startup logs for:
```
🚩 Feature flag manager initialized (Database + Redis cache)
```

#### 1.5 Test Feature Flags API

```bash
# List all flags
curl http://localhost:8000/api/feature-flags

# Enable a test flag
curl -X PUT http://localhost:8000/api/feature-flags/feature_course_management \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 100, "updated_by": "local_dev"}'

# Verify it's enabled
curl -X POST http://localhost:8000/api/feature-flags/feature_course_management/check \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user"}'

# Expected: {"flag_name": "feature_course_management", "enabled": true, ...}
```

---

### Step 2: Staging Environment Setup

#### 2.1 Deploy Code to Staging

```bash
# Push to staging branch (triggers Render deploy)
git checkout staging
git merge main
git push origin staging
```

#### 2.2 Run Migration on Staging Database

**Via Supabase Dashboard** (if using separate staging project):

1. Switch to staging Supabase project
2. Run `20251124_v73_create_feature_flags.sql` migration
3. Verify 9 flags created

**Via Production Database** (if staging shares production Supabase):

Migration already applied - skip this step.

#### 2.3 Update Render Environment Variables (Staging)

1. Go to Render Dashboard: https://dashboard.render.com
2. Navigate to staging service
3. Go to **Environment** tab
4. Add/update variables (optional, defaults are fine):
   ```
   FEATURE_FLAGS_CACHE_ENABLED=true
   FEATURE_FLAGS_CACHE_TTL=60
   ```
5. Click **Save Changes** (triggers redeploy)

#### 2.4 Verify Staging Deployment

```bash
# Check health
curl https://{staging-url}/health

# List flags
curl https://{staging-url}/api/feature-flags

# Should see 9 flags, all disabled
```

#### 2.5 Enable Features for Testing

```bash
# Enable all features in staging for comprehensive testing
curl -X PUT https://{staging-url}/api/feature-flags/feature_course_management \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 100, "updated_by": "staging_setup"}'

# Repeat for other flags as needed
```

---

### Step 3: Production Deployment

#### 3.1 Run Migration on Production Database

**IMPORTANT**: Schedule during low-traffic window if possible

**Via Supabase Dashboard**:

1. Go to https://supabase.com/dashboard/project/{production-project}/sql
2. Copy contents of `supabase/migrations/20251124_v73_create_feature_flags.sql`
3. Review migration one more time
4. Execute migration
5. Verify success: Check for `feature_flags` and `feature_flag_audit` tables

**Rollback Plan**: If migration fails, run:
```sql
-- Execute 20251124_v73_rollback_feature_flags.sql
-- This will cleanly remove all feature flag infrastructure
```

#### 3.2 Deploy Code to Production

```bash
# Merge to main branch
git checkout main
git merge feature/task-3-feature-flags
git push origin main
```

**Render Auto-Deploy**:
- Render will automatically detect the push and deploy
- Monitor deployment at https://dashboard.render.com

**Manual Deploy** (if auto-deploy disabled):
1. Go to Render Dashboard
2. Navigate to Empire FastAPI service
3. Click **Manual Deploy** → **Deploy latest commit**

#### 3.3 Update Render Environment Variables (Production)

1. Go to https://dashboard.render.com
2. Select **jb-empire-api** service
3. Go to **Environment** tab
4. **Optional**: Add custom cache settings (defaults work well):
   ```
   FEATURE_FLAGS_CACHE_ENABLED=true
   FEATURE_FLAGS_CACHE_TTL=60
   ```
5. Save (if you added variables - triggers redeploy)

**NOTE**: No new required environment variables. System uses existing `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `REDIS_URL`.

#### 3.4 Verify Production Deployment

```bash
# Check health
curl https://jb-empire-api.onrender.com/health

# Should see: {"status": "healthy", "version": "7.3.0", ...}

# Check detailed health with dependencies
curl https://jb-empire-api.onrender.com/health/detailed

# Verify feature flag manager initialized
# Look for: "feature_flags": "initialized" or similar in logs

# List all flags
curl https://jb-empire-api.onrender.com/api/feature-flags

# Should return 9 flags, all with "enabled": false
```

#### 3.5 Monitor Logs

**Render Logs**:
```bash
# View live logs
render logs -s jb-empire-api -f

# Or via Render Dashboard → Logs tab
```

Look for:
```
🚩 Feature flag manager initialized (Database + Redis cache)
```

If you see errors, check:
- Supabase connection (table exists?)
- Redis connection (accessible?)
- Migration ran successfully?

---

## Feature Flag Rollout Strategy (Production)

### Option 1: Safe Rollout (Recommended)

Enable features gradually to monitor impact:

```bash
# Week 1: Enable low-risk database-only features
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_processing_status_details \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 100, "updated_by": "production_admin"}'

curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_source_metadata \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 100, "updated_by": "production_admin"}'

# Week 2: Enable cache and feedback features
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_agent_router_cache \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 100, "updated_by": "production_admin"}'

curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_agent_feedback \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 100, "updated_by": "production_admin"}'

# Week 3+: Gradual rollout of user-facing features
# Start with 10% rollout
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_course_management \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 10, "updated_by": "production_admin"}'

# Monitor metrics for 48 hours, then increase to 50%
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_course_management \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 50, "updated_by": "production_admin"}'

# Monitor metrics for 48 hours, then full rollout
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_course_management \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 100, "updated_by": "production_admin"}'
```

### Option 2: All-at-Once (After Thorough Staging Testing)

```bash
# Enable all features immediately (only if confident from staging tests)
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_processing_status_details \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 100, "updated_by": "production_admin"}' &

curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_source_metadata \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 100, "updated_by": "production_admin"}' &

# ... repeat for all 9 flags
```

---

## Monitoring After Deployment

### Application Metrics

Monitor these via Grafana (http://localhost:3001) or Prometheus:

```promql
# Feature flag check rate
rate(feature_flag_checks_total[5m])

# Cache hit rate
redis_cache_hits_total{key_type="feature_flag"}
/
(redis_cache_hits_total{key_type="feature_flag"} + redis_cache_misses_total{key_type="feature_flag"})

# API latency (should remain <5ms for flag checks)
histogram_quantile(0.95, rate(empire_request_duration_seconds_bucket{endpoint="/api/feature-flags"}[5m]))
```

### Database Queries

```sql
-- Check flag states
SELECT flag_name, enabled, rollout_percentage, updated_at
FROM feature_flags
ORDER BY flag_name;

-- Check audit trail (recent changes)
SELECT flag_name, action, changed_by, changed_at
FROM feature_flag_audit
ORDER BY changed_at DESC
LIMIT 20;

-- Check flag statistics
SELECT * FROM feature_flag_statistics;
```

### Redis Cache

```bash
# Check cached flags
redis-cli KEYS "feature_flag:*"

# Check TTL on a cached flag
redis-cli TTL "feature_flag:feature_course_management"

# Clear cache if needed (flags will be re-fetched from database)
redis-cli DEL "feature_flag:*"
```

---

## Troubleshooting

### Issue: "Feature flag manager initialization failed"

**Symptoms**: Error in startup logs

**Causes & Solutions**:

1. **Supabase connection issue**:
   ```bash
   # Verify Supabase credentials
   echo $SUPABASE_URL
   echo $SUPABASE_SERVICE_KEY

   # Test connection
   curl https://xxxxx.supabase.co/rest/v1/feature_flags \
     -H "apikey: $SUPABASE_SERVICE_KEY" \
     -H "Authorization: Bearer $SUPABASE_SERVICE_KEY"
   ```

2. **Migration not run**:
   ```sql
   -- Check if tables exist
   SELECT tablename FROM pg_tables WHERE tablename = 'feature_flags';

   -- If not, run migration
   ```

3. **Redis connection issue**:
   ```bash
   # Test Redis connection
   redis-cli -u $REDIS_URL ping

   # Should return: PONG
   ```

### Issue: Flags not taking effect

**Cause**: Cache not cleared after update

**Solution**:
```bash
# Clear Redis cache
redis-cli -u $REDIS_URL DEL "feature_flag:*"

# Or restart application (cache will repopulate)
```

### Issue: Slow flag checks (>50ms)

**Cause**: Redis cache not working

**Solution**:
```bash
# Verify FEATURE_FLAGS_CACHE_ENABLED is true
echo $FEATURE_FLAGS_CACHE_ENABLED

# Check Redis connection
redis-cli -u $REDIS_URL PING

# Monitor cache hits/misses
redis-cli -u $REDIS_URL MONITOR
```

---

## Rollback Procedures

### Rollback Flag State

**Disable a problematic feature**:
```bash
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_course_management \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "updated_by": "emergency_rollback"}'
```

**Disable all flags**:
```sql
UPDATE feature_flags SET enabled = FALSE;
```

### Rollback Code Deployment

**Via Render Dashboard**:
1. Go to Render Dashboard → jb-empire-api
2. Go to **Events** tab
3. Find previous successful deployment
4. Click **Rollback to this version**

**Via Git**:
```bash
# Revert the merge commit
git revert <commit-hash>
git push origin main

# Render will auto-deploy the revert
```

### Rollback Database Migration

**If migration causes issues**:
```sql
-- Run rollback migration
-- Execute: supabase/migrations/20251124_v73_rollback_feature_flags.sql
```

**WARNING**: Rollback will delete all feature flag data and audit logs.

---

## CI/CD Integration (Future)

### GitHub Actions Workflow (Example)

```yaml
name: Deploy with Feature Flags

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Feature Flag Migration
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: |
          # Apply migration via Supabase API or CLI
          echo "Migration check - ensure feature_flags table exists"

      - name: Deploy to Render
        env:
          RENDER_API_KEY: ${{ secrets.RENDER_API_KEY }}
        run: |
          # Trigger Render deployment
          curl -X POST https://api.render.com/v1/services/{service-id}/deploys \
            -H "Authorization: Bearer $RENDER_API_KEY"

      - name: Verify Deployment
        run: |
          # Wait for deployment
          sleep 60

          # Check health
          curl https://jb-empire-api.onrender.com/health

          # Verify feature flags API
          curl https://jb-empire-api.onrender.com/api/feature-flags
```

---

## Summary

✅ **Zero new required environment variables** - uses existing Supabase + Redis
✅ **Optional configuration** - cache TTL and enable/disable caching
✅ **Simple deployment** - run migration, deploy code, verify
✅ **Safe rollout** - gradual percentage-based rollouts supported
✅ **Easy rollback** - disable flags without code changes
✅ **Monitoring** - Grafana, Prometheus, database queries
✅ **Production-ready** - tested with zero-cost infrastructure

---

## Next Steps

After deployment:

1. **Task 3.5**: Create admin interface for easier flag management
2. **Task 3.6**: Complete developer documentation
3. **Feature Implementation**: Integrate flag checks into actual feature code
4. **Monitoring**: Set up Grafana dashboards for flag metrics

---

## Quick Reference

### Enable a flag in production
```bash
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/{flag_name} \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 100, "updated_by": "admin"}'
```

### Disable a flag (emergency)
```bash
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/{flag_name} \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "updated_by": "emergency"}'
```

### Check flag status
```bash
curl https://jb-empire-api.onrender.com/api/feature-flags/{flag_name}
```

### View audit trail
```bash
curl https://jb-empire-api.onrender.com/api/feature-flags/{flag_name}/audit
```

---

**Document Version**: 1.0
**Last Updated**: 2025-01-24
**Task**: 3.4 - Update Environment Configuration
