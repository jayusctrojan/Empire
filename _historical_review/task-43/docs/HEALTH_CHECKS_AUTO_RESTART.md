# Empire v7.3 - Health Checks & Auto-Restart Configuration

**Document Version:** 1.0
**Last Updated:** 2025-01-15
**Owner:** DevOps Team
**Review Frequency:** Monthly

---

## Overview

This document describes the health check and automatic restart configuration for all Empire production services on Render.

---

## Service Health Check Status

### FastAPI Service (jb-empire-api)

**Service Details**:
- **Service ID**: `srv-d44o2dq4d50c73elgupg`
- **URL**: https://jb-empire-api.onrender.com
- **Dashboard**: https://dashboard.render.com/web/srv-d44o2dq4d50c73elgupg
- **Plan**: Starter ($7/month)
- **Region**: Oregon

**Health Check Configuration**:
- **Health Check Path**: `/health` ✅ **CONFIGURED**
- **Health Check Interval**: Every 30 seconds (Render default)
- **Failure Threshold**: 3 consecutive failures (Render default)
- **Auto-Restart**: ✅ **ENABLED** (Render automatic)

**Health Endpoints**:
1. **Basic Health**: `GET /health`
   ```json
   {
     "status": "healthy",
     "timestamp": "2025-01-15T12:00:00Z"
   }
   ```

2. **Detailed Health**: `GET /health/detailed`
   ```json
   {
     "status": "healthy",
     "database": "connected",
     "redis": "connected",
     "version": "7.3.0",
     "uptime_seconds": 3600,
     "timestamp": "2025-01-15T12:00:00Z"
   }
   ```

3. **Readiness Probe**: `GET /health/ready`
   - Returns 200 if service is ready to accept traffic
   - Returns 503 if not ready (startup, dependencies unavailable)

4. **Liveness Probe**: `GET /health/live`
   - Returns 200 if service is alive
   - Returns 503 if service should be restarted

**Test Health Check**:
```bash
# Basic health
curl https://jb-empire-api.onrender.com/health

# Detailed health
curl https://jb-empire-api.onrender.com/health/detailed

# Readiness
curl https://jb-empire-api.onrender.com/health/ready

# Liveness
curl https://jb-empire-api.onrender.com/health/live
```

---

### Celery Worker Service (jb-empire-celery)

**Service Details**:
- **Service ID**: `srv-d44oclodl3ps73bg8rmg`
- **Dashboard**: https://dashboard.render.com/worker/srv-d44oclodl3ps73bg8rmg
- **Plan**: Starter ($7/month)
- **Region**: Oregon

**Health Check Configuration**:
- **Health Check Path**: N/A (background worker)
- **Process Monitoring**: ✅ **ENABLED** (Render automatic)
- **Auto-Restart on Crash**: ✅ **ENABLED** (Render automatic)

**Monitoring**:
- Render monitors the Celery worker process
- Automatic restart if process exits unexpectedly
- Logs available in Render dashboard

**Test Worker Health**:
```bash
# Check worker logs
# Via Render MCP or dashboard

# Test task execution (from FastAPI)
curl -X POST https://jb-empire-api.onrender.com/api/documents/process \
  -H "Content-Type: application/json" \
  -d '{"document_id": "test-123"}'
```

---

### Other Services

#### LlamaIndex Service (jb-llamaindex)

**Service Details**:
- **Service ID**: `srv-d2nl1lre5dus73atm9u0`
- **URL**: https://jb-llamaindex.onrender.com
- **Health Check**: Configured (service-specific)
- **Auto-Restart**: ✅ **ENABLED**

#### CrewAI Service (jb-crewai)

**Service Details**:
- **Service ID**: `srv-d2n0hh3uibrs73buafo0`
- **URL**: https://jb-crewai.onrender.com
- **Health Check**: Configured (service-specific)
- **Auto-Restart**: ✅ **ENABLED**

#### Chat UI Service (jb-empire-chat)

**Service Details**:
- **Service ID**: `srv-d47ptdmr433s739ljolg`
- **URL**: https://jb-empire-chat.onrender.com
- **Health Check**: Configured (Gradio default)
- **Auto-Restart**: ✅ **ENABLED**

---

## Auto-Restart Behavior

### How Render Auto-Restart Works

**Automatic Restart Triggers**:
1. **Health check failures**: 3 consecutive failures on `/health`
2. **Process crashes**: Service exits with non-zero code
3. **OOM (Out of Memory)**: Service exceeds memory limits
4. **Unhandled exceptions**: Python crashes, segfaults, etc.

**Restart Process**:
1. Render detects failure (health check or process exit)
2. Service is marked as "unhealthy"
3. New instance is started
4. Old instance is terminated (graceful shutdown, 30s timeout)
5. Traffic is routed to new instance once healthy

**Restart Limits**:
- **No limit** on restart attempts
- **Exponential backoff** if restarting frequently
- **Notification** on repeated failures (if configured)

**Verification**:
```bash
# Check service status via Render MCP
# Should show "not_suspended" status
```

---

## Health Check Implementation

### FastAPI Health Endpoints (app/routes/health.py)

```python
from fastapi import APIRouter, Response, status
from datetime import datetime
import time

router = APIRouter()

# Global startup time
STARTUP_TIME = time.time()

@router.get("/health")
async def health_check():
    """Basic health check - used by Render"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health/detailed")
async def detailed_health():
    """Detailed health with component checks"""
    # Check database
    db_status = await check_database_connection()

    # Check Redis
    redis_status = await check_redis_connection()

    # Overall status
    overall = "healthy" if (db_status and redis_status) else "degraded"

    return {
        "status": overall,
        "database": "connected" if db_status else "disconnected",
        "redis": "connected" if redis_status else "disconnected",
        "version": "7.3.0",
        "uptime_seconds": int(time.time() - STARTUP_TIME),
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health/ready")
async def readiness_check():
    """Readiness probe - is service ready to accept traffic?"""
    # Check critical dependencies
    db_ready = await check_database_connection()
    redis_ready = await check_redis_connection()

    if not (db_ready and redis_ready):
        return Response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content="Service not ready"
        )

    return {"status": "ready"}

@router.get("/health/live")
async def liveness_check():
    """Liveness probe - is service alive?"""
    # Basic check - if we can respond, we're alive
    return {"status": "alive"}
```

---

## Monitoring Recommendations

### Current Monitoring

**Render Built-in**:
- ✅ Automatic health checks every 30 seconds
- ✅ Automatic restart on failure
- ✅ Logs available in dashboard
- ✅ Email notifications on service down (if configured)

**GitHub Actions**:
- ✅ Daily backup monitoring (creates issue on failure)

### Recommended Additional Monitoring

**1. Uptime Monitoring** (External):
- **Service**: UptimeRobot, Pingdom, or StatusCake
- **Monitor**: https://jb-empire-api.onrender.com/health
- **Interval**: 5 minutes
- **Alert**: Email/SMS on downtime

**2. Application Performance Monitoring (APM)**:
- **Service**: Sentry, New Relic, or Datadog
- **Features**:
  - Error tracking
  - Performance monitoring
  - Request tracing
  - Custom metrics

**3. Log Aggregation**:
- **Service**: Papertrail, Loggly, or Logz.io
- **Features**:
  - Centralized logs from all services
  - Search and filter
  - Alerting on error patterns

**4. Metrics Dashboard**:
- **Service**: Grafana Cloud or Prometheus
- **Metrics**:
  - Request rate
  - Error rate
  - Response time (p50, p95, p99)
  - Database query performance
  - Celery queue length

---

## Testing Auto-Restart

### Test Scenario 1: Health Check Failure

**Simulate Failure**:
```python
# Add to app/routes/health.py for testing only
@router.get("/health/fail")
async def force_failure():
    """Force health check to fail (testing only)"""
    return Response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content="Forced failure for testing"
    )
```

**Test Procedure**:
1. Deploy code with forced failure endpoint
2. Change health check path to `/health/fail` in Render dashboard
3. Wait for 3 consecutive failures (~90 seconds)
4. Verify Render restarts service
5. Restore health check path to `/health`

**Expected Behavior**:
- Service marked as unhealthy after ~90 seconds
- New instance started
- Traffic routed to new instance
- Old instance terminated

### Test Scenario 2: Process Crash

**Simulate Crash**:
```python
# Add to app/routes/health.py for testing only
@router.get("/crash")
async def force_crash():
    """Force process crash (testing only)"""
    import sys
    sys.exit(1)
```

**Test Procedure**:
1. Deploy code with crash endpoint
2. Call crash endpoint: `curl https://jb-empire-api.onrender.com/crash`
3. Verify Render detects crash
4. Verify Render restarts service

**Expected Behavior**:
- Service crashes immediately
- Render detects process exit
- New instance started within seconds
- Service recovers automatically

### Test Scenario 3: OOM (Out of Memory)

**Simulate OOM**:
```python
# Add to app/routes/health.py for testing only
@router.get("/oom")
async def force_oom():
    """Force out-of-memory (testing only)"""
    # Allocate large list until memory exhausted
    data = []
    while True:
        data.append([0] * 10**6)  # Allocate 1M integers
```

**Test Procedure**:
1. Deploy code with OOM endpoint
2. Call OOM endpoint: `curl https://jb-empire-api.onrender.com/oom`
3. Verify Render detects OOM
4. Verify Render restarts service

**Expected Behavior**:
- Service consumes memory rapidly
- Render detects memory limit exceeded
- Service is killed (OOM killer)
- New instance started automatically

**⚠️ WARNING**: Only test these scenarios in non-production environments or during maintenance windows.

---

## Alert Configuration

### Render Notifications

**Email Alerts** (configure in Render dashboard):
1. Go to service settings
2. Navigate to "Notifications" tab
3. Configure:
   - ✅ Deploy failures
   - ✅ Service crashes
   - ✅ Health check failures
   - Email: [your-email@example.com]

### GitHub Issue Alerts

**Automated Issues** (via GitHub Actions):
- ✅ Daily backup failures automatically create issues
- Labels: `backup`, `alert`
- Assigned to: System owner

**Setup Additional Alerts**:
```yaml
# .github/workflows/health-check.yml
name: Periodic Health Check

on:
  schedule:
    - cron: '*/15 * * * *'  # Every 15 minutes

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - name: Check API Health
        run: |
          STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://jb-empire-api.onrender.com/health)
          if [ $STATUS -ne 200 ]; then
            echo "Health check failed with status $STATUS"
            exit 1
          fi

      - name: Create Issue on Failure
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: '🚨 API Health Check Failed',
              body: 'API health check failed. Check service status.',
              labels: ['alert', 'health-check']
            })
```

---

## Troubleshooting Auto-Restart Issues

### Problem: Service Keeps Restarting (Restart Loop)

**Symptoms**:
- Service restarts every few minutes
- Health checks always fail
- Logs show repeating errors

**Common Causes**:
1. **Database connection failure**: Check Supabase credentials
2. **Missing environment variables**: Verify all required vars
3. **Code bug on startup**: Check application logs
4. **Memory limits**: Upgrade to higher plan

**Solution**:
```bash
# Check logs via Render MCP
# Look for errors during startup

# Verify environment variables
# Via Render dashboard → Settings → Environment

# Check database connectivity
psql -h $SUPABASE_DB_HOST -U $SUPABASE_DB_USER -d $SUPABASE_DB_NAME

# If OOM, upgrade plan
# Starter: 512 MB → Standard: 2 GB
```

### Problem: Health Check Fails but Service Works

**Symptoms**:
- Health endpoint returns 503
- But application functionality works
- Render marks service as unhealthy

**Common Causes**:
1. **Dependency check too strict**: Database temporarily slow
2. **Timeout too short**: Health check times out
3. **Wrong health check path**: Typo in configuration

**Solution**:
```python
# Make health check more lenient
@router.get("/health")
async def health_check():
    # Don't check dependencies for basic health
    # Just return 200 if process is alive
    return {"status": "healthy"}

@router.get("/health/detailed")
async def detailed_health():
    # Check dependencies here instead
    # But don't use for Render health check
    ...
```

### Problem: Service Doesn't Auto-Restart After Crash

**Symptoms**:
- Service crashes
- Render doesn't restart it
- Service stays down

**Common Causes**:
1. **Service manually suspended**: Check dashboard
2. **Render platform issue**: Check status.render.com
3. **Account billing issue**: Check account status

**Solution**:
```bash
# Check service status via Render MCP
# "suspended": "not_suspended" means auto-restart is active

# Manually restart via dashboard
# Or via Render MCP: update service with restart flag

# Check Render status
# https://status.render.com/
```

---

## Emergency Procedures

### Force Manual Restart

**Via Render Dashboard**:
1. Go to service dashboard
2. Click "Manual Deploy" dropdown
3. Select "Clear build cache & deploy"
4. Or: "Suspend Service" → "Resume Service"

**Via Render MCP**:
```python
# Not directly supported by MCP
# Use dashboard for manual restarts
```

### Disable Auto-Restart (Emergency)

**When to use**:
- Service is in restart loop
- Need to investigate without interruption
- Testing fix before re-enabling

**Procedure**:
1. Suspend service via dashboard
2. Investigate logs and fix issue
3. Test fix locally
4. Resume service

**⚠️ WARNING**: Only suspend services during approved maintenance windows.

---

## Best Practices

### Health Check Design

**DO**:
- ✅ Return 200 for basic health (process alive)
- ✅ Check critical dependencies in detailed health
- ✅ Use separate endpoints for liveness vs readiness
- ✅ Keep health checks fast (<1 second)
- ✅ Log health check failures

**DON'T**:
- ❌ Check all dependencies in basic health (too strict)
- ❌ Make health checks slow (causes false failures)
- ❌ Return 503 for non-critical issues
- ❌ Use health check for business logic

### Auto-Restart Configuration

**DO**:
- ✅ Configure health check path in Render
- ✅ Set up email notifications
- ✅ Monitor restart frequency
- ✅ Investigate repeated restarts
- ✅ Test auto-restart in staging

**DON'T**:
- ❌ Rely solely on auto-restart (monitor actively)
- ❌ Ignore restart notifications
- ❌ Disable auto-restart unless necessary
- ❌ Forget to re-enable after investigation

---

## Appendix: Service Status Check Script

**Check all services**:

```bash
#!/bin/bash
# check_services.sh

echo "Checking Empire Services..."
echo ""

# FastAPI
echo "FastAPI Service:"
curl -s https://jb-empire-api.onrender.com/health | jq '.'
echo ""

# CrewAI
echo "CrewAI Service:"
curl -s https://jb-crewai.onrender.com/health | jq '.'
echo ""

# LlamaIndex
echo "LlamaIndex Service:"
curl -s https://jb-llamaindex.onrender.com/health | jq '.'
echo ""

# Chat UI
echo "Chat UI:"
curl -s -o /dev/null -w "Status: %{http_code}\n" https://jb-empire-chat.onrender.com
echo ""
```

**Run**:
```bash
chmod +x check_services.sh
./check_services.sh
```

---

## Document Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-15 | DevOps Team | Initial health check documentation |

---

**Next Review Date**: 2025-02-15
