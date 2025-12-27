# Empire v7.3 Rollback Runbook

**Task 7.5**: Comprehensive rollback runbook with step-by-step procedures

**Version**: 1.0
**Last Updated**: 2025-11-25
**Owner**: Jay Bajaj (jbajaj08@gmail.com)

---

## Table of Contents

1. [Overview](#overview)
2. [Decision Matrix](#decision-matrix)
3. [Pre-Rollback Checklist](#pre-rollback-checklist)
4. [Rollback Procedures](#rollback-procedures)
   - [Procedure 1: Service Rollback (Render)](#procedure-1-service-rollback-render)
   - [Procedure 2: Database Migration Rollback](#procedure-2-database-migration-rollback)
   - [Procedure 3: Full System Rollback](#procedure-3-full-system-rollback)
   - [Procedure 4: Configuration Rollback](#procedure-4-configuration-rollback)
5. [Post-Rollback Verification](#post-rollback-verification)
6. [Communication Templates](#communication-templates)
7. [Troubleshooting](#troubleshooting)
8. [Contact Information](#contact-information)

---

## Overview

This runbook provides step-by-step procedures for rolling back Empire v7.3 components during incidents or failed deployments.

### Scope

- **Services**: FastAPI (empire-api), Celery Worker, Chat UI
- **Database**: PostgreSQL (Supabase) migrations
- **Infrastructure**: Render deployments, environment variables

### Out of Scope

- Third-party service rollbacks (Anthropic, Supabase infrastructure)
- Client-side application rollbacks
- Data restoration from backups (see Backup Runbook)

---

## Decision Matrix

### When to Initiate Rollback

| Condition | Severity | Action |
|-----------|----------|--------|
| Service returning 5xx errors > 5% for 5+ min | Critical | Immediate service rollback |
| P95 latency > 60s for 10+ min | Critical | Service rollback |
| Database connection failures | Critical | Check DB first, then service rollback |
| Migration causing data integrity issues | Critical | Database migration rollback |
| New feature causing user-facing bugs | High | Service rollback |
| Performance degradation > 50% | High | Service rollback |
| Security vulnerability discovered | Critical | Immediate service rollback |
| Feature toggle not working | Medium | Configuration rollback |

### Rollback Decision Tree

```
START: Issue Detected
  │
  ├─► Is service completely down?
  │   YES ──► IMMEDIATE SERVICE ROLLBACK
  │   NO ──┬► Is error rate > 5%?
  │        │   YES ──► SERVICE ROLLBACK
  │        │   NO ──┬► Is latency > 3x baseline?
  │                 │   YES ──► SERVICE ROLLBACK
  │                 │   NO ──┬► Is it a database issue?
  │                          │   YES ──► DATABASE ROLLBACK
  │                          │   NO ──┬► Is it a config issue?
  │                                   │   YES ──► CONFIG ROLLBACK
  │                                   │   NO ──► INVESTIGATE FURTHER
```

---

## Pre-Rollback Checklist

### Before ANY Rollback

- [ ] **Identify the issue** - What symptom triggered this?
- [ ] **Notify team** - Post in #empire-incidents Slack
- [ ] **Document start time** - Record incident start time
- [ ] **Check recent changes** - What was deployed in last 24h?
- [ ] **Backup current state** - Screenshot dashboards, save logs

### Required Access

- [ ] Render dashboard access (https://dashboard.render.com)
- [ ] Render API key (`RENDER_API_KEY` env var)
- [ ] Supabase dashboard access
- [ ] Supabase service key (`SUPABASE_SERVICE_KEY` env var)
- [ ] GitHub repository access
- [ ] Slack #empire-incidents channel

### Tools Ready

```bash
# Verify tools are installed
which curl jq psql
export RENDER_API_KEY="rnd_xxxxx"  # Set if not in .env
export SUPABASE_URL="https://xxx.supabase.co"
export SUPABASE_SERVICE_KEY="eyJxxx"
```

---

## Rollback Procedures

---

### Procedure 1: Service Rollback (Render)

**Estimated Time**: 5-15 minutes
**Risk Level**: Low
**Data Loss**: None

#### Step 1.1: Enable Maintenance Mode (Optional)

```bash
# For user-facing services, enable maintenance mode
./scripts/rollback/render_rollback.sh --maintenance empire-api
./scripts/rollback/render_rollback.sh --maintenance empire-chat
```

**Verification**: Check https://jb-empire-api.onrender.com returns maintenance page

#### Step 1.2: Identify Previous Deployment

```bash
# List recent deployments
./scripts/rollback/render_rollback.sh --list empire-api

# Note the deployment ID to rollback to (typically the one before current)
# Example output:
# Deploy: dep-abc123 | Status: live | Created: 2025-11-25T10:00:00Z
# Deploy: dep-xyz789 | Status: build_succeeded | Created: 2025-11-24T15:00:00Z  <-- TARGET
```

#### Step 1.3: Execute Rollback

**Option A: Rollback to Previous (Automatic)**
```bash
./scripts/rollback/render_rollback.sh empire-api
```

**Option B: Rollback to Specific Version**
```bash
./scripts/rollback/render_rollback.sh empire-api dep-xyz789
```

**Expected Output**:
```
[INFO] Rolling back empire-api to deploy: dep-xyz789
[INFO] Target commit: abc123def456
[SUCCESS] Rollback deploy initiated: dep-newid123
[INFO] Monitor at: https://dashboard.render.com/web/srv-xxx/deploys/dep-newid123
```

#### Step 1.4: Monitor Deployment

```bash
# Watch deployment progress (takes 3-5 minutes)
# Open the dashboard URL provided in step 1.3

# Or check via CLI
./scripts/rollback/render_rollback.sh --status
```

**Wait for**: "Deploy Live" status in Render dashboard

#### Step 1.5: Verify Service Health

```bash
# Health check
curl https://jb-empire-api.onrender.com/health

# Expected: {"status": "healthy", ...}

# Additional health checks
curl https://jb-empire-api.onrender.com/api/query/health
curl https://jb-empire-api.onrender.com/api/crewai/health
```

#### Step 1.6: Disable Maintenance Mode

```bash
./scripts/rollback/render_rollback.sh --no-maintenance empire-api
./scripts/rollback/render_rollback.sh --no-maintenance empire-chat
```

#### Step 1.7: Verify Full Functionality

```bash
# Test key endpoints
curl -X POST https://jb-empire-api.onrender.com/api/query/auto \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "max_iterations": 1}'

# Check for 200 response
```

#### Step 1.8: Document Rollback

```markdown
## Service Rollback Record

- **Date**: YYYY-MM-DD HH:MM UTC
- **Service**: empire-api
- **From Deploy**: dep-abc123
- **To Deploy**: dep-xyz789
- **Reason**: [Brief description]
- **Duration**: X minutes
- **Performed By**: [Name]
```

---

### Procedure 2: Database Migration Rollback

**Estimated Time**: 10-30 minutes
**Risk Level**: Medium to High
**Data Loss**: Possible (depends on migration)

⚠️ **WARNING**: Database rollbacks may cause data loss. Export data before proceeding.

#### Step 2.1: Identify Migration to Rollback

```bash
# List available rollback scripts
./scripts/rollback/full_rollback.sh --list-migrations

# Output:
# Available database rollback scripts:
#   - enable_rls_policies
#   - create_audit_logs_table
#   - add_performance_indexes
#   - create_cost_tracking_tables
#   - add_memory_rls_policies
#   - enhance_agent_interactions
```

#### Step 2.2: Export Affected Data (If Applicable)

```bash
# Connect to Supabase via psql
psql "postgresql://postgres:$SUPABASE_SERVICE_KEY@db.$SUPABASE_URL:5432/postgres"

# Export data before rollback
\COPY audit_logs TO '/tmp/audit_logs_backup.csv' CSV HEADER;
\COPY cost_entries TO '/tmp/cost_entries_backup.csv' CSV HEADER;
```

#### Step 2.3: Put Services in Maintenance Mode

```bash
./scripts/rollback/render_rollback.sh --maintenance empire-api
./scripts/rollback/render_rollback.sh --maintenance empire-chat
```

#### Step 2.4: Execute Database Rollback

**Option A: Single Migration Rollback**
```bash
./scripts/rollback/full_rollback.sh --migration enable_rls_policies
```

**Option B: Dry Run First**
```bash
./scripts/rollback/full_rollback.sh --dry-run --migration enable_rls_policies
```

**Expected Output**:
```
[STEP] Rolling back migration: enable_rls_policies
[INFO] Executing rollback SQL...
NOTICE:  Dropped 14 RLS policies
NOTICE:  Disabled RLS on 14 tables
NOTICE:  ✅ RLS successfully disabled on all 14 user-facing tables
[SUCCESS] Migration rollback completed: enable_rls_policies
```

#### Step 2.5: Verify Database State

```bash
# Connect to database
psql "postgresql://postgres:$SUPABASE_SERVICE_KEY@db.$SUPABASE_URL:5432/postgres"

# Verify migration was rolled back
\dt  -- List tables
SELECT * FROM pg_policies WHERE schemaname='public';  -- Check policies
SELECT indexname FROM pg_indexes WHERE schemaname='public';  -- Check indexes
```

#### Step 2.6: Restart Services

```bash
# Services may need restart to pick up DB changes
./scripts/rollback/render_rollback.sh empire-api
./scripts/rollback/render_rollback.sh empire-celery
```

#### Step 2.7: Disable Maintenance Mode

```bash
./scripts/rollback/render_rollback.sh --no-maintenance empire-api
./scripts/rollback/render_rollback.sh --no-maintenance empire-chat
```

#### Step 2.8: Verify Application Functionality

```bash
# Test database-dependent operations
curl https://jb-empire-api.onrender.com/api/query/search/faceted \
  -X POST -H "Content-Type: application/json" \
  -d '{"query": "test", "page": 1, "page_size": 10}'
```

---

### Procedure 3: Full System Rollback

**Estimated Time**: 30-60 minutes
**Risk Level**: High
**Data Loss**: Likely for new data

Use this procedure when both services AND database need rollback.

#### Step 3.1: Confirm Full Rollback is Required

```
⚠️ STOP AND CONFIRM:
- [ ] Service-only rollback is NOT sufficient
- [ ] Database state is inconsistent with service version
- [ ] Team lead has approved full rollback
- [ ] Data export completed (if possible)
```

#### Step 3.2: Execute Full Rollback (Dry Run)

```bash
./scripts/rollback/full_rollback.sh --dry-run --full
```

Review the dry run output to understand what will change.

#### Step 3.3: Execute Full Rollback

```bash
# This will:
# 1. Enable maintenance mode
# 2. Rollback services (Chat UI -> API -> Celery)
# 3. Rollback all database migrations
# 4. Verify health
# 5. Disable maintenance mode

./scripts/rollback/full_rollback.sh --full
```

**Monitor Progress**: The script will output each step. Watch for errors.

#### Step 3.4: Manual Verification

```bash
# Check service health
curl https://jb-empire-api.onrender.com/health
curl https://jb-empire-chat.onrender.com

# Check database state
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM documents;"
```

#### Step 3.5: Smoke Test

```bash
# Run quick smoke test
cd tests/load_testing
./run_load_tests.sh light --run-time=1m
```

---

### Procedure 4: Configuration Rollback

**Estimated Time**: 5-10 minutes
**Risk Level**: Low
**Data Loss**: None

Use for environment variable or feature flag rollbacks.

#### Step 4.1: Identify Configuration Change

```bash
# View current environment variables (via Render dashboard or API)
# Compare with git history for .env.example or configuration files
git log --oneline -10 -- .env.example
```

#### Step 4.2: Revert Environment Variables

**Via Render Dashboard**:
1. Go to https://dashboard.render.com/web/srv-d44o2dq4d50c73elgupg
2. Click "Environment"
3. Edit/revert the changed variable
4. Save changes (triggers redeploy)

**Via API**:
```bash
# Revert specific env var
curl -X PATCH "https://api.render.com/v1/services/srv-d44o2dq4d50c73elgupg/env-vars" \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"envVars": [{"key": "FEATURE_FLAG_X", "value": "false"}]}'
```

#### Step 4.3: Verify Configuration Applied

```bash
# Check health endpoint for config
curl https://jb-empire-api.onrender.com/health | jq .config

# Or check specific endpoint behavior
```

---

## Post-Rollback Verification

### Immediate Checks (Within 5 minutes)

- [ ] Health endpoints return 200
- [ ] Error rate < 1%
- [ ] P95 latency within baseline
- [ ] No 5xx errors in logs

```bash
# Quick verification script
curl -s https://jb-empire-api.onrender.com/health | jq .status
curl -s https://jb-empire-api.onrender.com/api/query/health | jq .status
```

### Extended Checks (Within 30 minutes)

- [ ] Key user flows working (query, document upload)
- [ ] Celery tasks processing
- [ ] Database connections stable
- [ ] No memory/CPU spikes

### Monitoring Check

- [ ] Prometheus metrics showing normal
- [ ] No new alerts firing
- [ ] Grafana dashboards green

---

## Communication Templates

### Incident Start (Slack)

```
🚨 **INCIDENT STARTED** - Empire API

**Status**: Investigating
**Impact**: [High/Medium/Low]
**Symptoms**: [Brief description]
**Start Time**: YYYY-MM-DD HH:MM UTC

We are investigating and will provide updates every 15 minutes.

cc: @on-call
```

### Rollback Initiated (Slack)

```
🔄 **ROLLBACK INITIATED** - Empire API

**Action**: Rolling back to deploy dep-xyz789
**Reason**: [Brief description]
**ETA**: ~10 minutes

Services may be briefly unavailable. Updates to follow.
```

### Rollback Complete (Slack)

```
✅ **ROLLBACK COMPLETE** - Empire API

**Status**: Resolved
**Duration**: X minutes
**Root Cause**: [Brief description]
**Next Steps**: [Investigation, fix, etc.]

Services are back to normal operation.
```

### Post-Incident Email

```
Subject: [RESOLVED] Empire API Incident - YYYY-MM-DD

Team,

An incident occurred affecting Empire API services. Here's a summary:

**Timeline**:
- HH:MM - Issue detected
- HH:MM - Rollback initiated
- HH:MM - Services restored

**Impact**:
- Duration: X minutes
- Users affected: ~Y
- Error rate peaked at: Z%

**Root Cause**:
[Description]

**Resolution**:
Rolled back to previous deployment (dep-xyz789)

**Action Items**:
1. [Item 1]
2. [Item 2]

**Lessons Learned**:
[Key takeaways]

Full incident report: [Link]

Regards,
[Name]
```

---

## Troubleshooting

### Rollback Script Fails

```bash
# Check Render API key
echo $RENDER_API_KEY | head -c 10

# Check API connectivity
curl -H "Authorization: Bearer $RENDER_API_KEY" https://api.render.com/v1/services

# Manual rollback via dashboard
open https://dashboard.render.com/web/srv-d44o2dq4d50c73elgupg/deploys
```

### Service Won't Start After Rollback

```bash
# Check logs
./scripts/rollback/render_rollback.sh --logs empire-api

# Common issues:
# - Missing env vars (check deployment settings)
# - Database schema mismatch (may need DB rollback too)
# - Dependency version conflict (check requirements.txt)
```

### Database Rollback Fails

```bash
# Check connection
psql "$DATABASE_URL" -c "SELECT 1;"

# Check for locks
psql "$DATABASE_URL" -c "SELECT * FROM pg_locks WHERE NOT granted;"

# Force terminate connections if needed (DANGEROUS)
psql "$DATABASE_URL" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'postgres' AND pid <> pg_backend_pid();"
```

### Services Healthy But Users Report Issues

```bash
# Check for stale caches
curl -X POST https://jb-empire-api.onrender.com/api/cache/clear

# Check Celery queue
celery -A app.celery_app inspect active

# Check for stuck tasks
celery -A app.celery_app purge
```

---

## Contact Information

### On-Call Rotation

- **Primary**: Check PagerDuty schedule
- **Secondary**: Check PagerDuty schedule
- **Escalation**: Jay Bajaj (jbajaj08@gmail.com)

### Communication Channels

- **Incidents**: #empire-incidents (Slack)
- **General**: #empire-dev (Slack)
- **Email**: empire-team@company.com

### External Contacts

- **Render Support**: support@render.com
- **Supabase Support**: support@supabase.io
- **Anthropic Status**: status.anthropic.com

---

## Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2025-11-25 | 1.0 | Claude | Initial runbook |

---

## Appendix: Script Locations

```
Empire/
├── scripts/
│   └── rollback/
│       ├── render_rollback.sh      # Service rollback script
│       ├── full_rollback.sh        # Full system rollback
│       └── README.md               # Script documentation
├── migrations/
│   └── rollback/
│       ├── rollback_enable_rls_policies.sql
│       ├── rollback_create_audit_logs_table.sql
│       ├── rollback_add_performance_indexes.sql
│       ├── rollback_create_cost_tracking_tables.sql
│       ├── rollback_add_memory_rls_policies.sql
│       ├── rollback_enhance_agent_interactions.sql
│       └── README.md
└── docs/
    ├── ROLLBACK_RUNBOOK.md         # This document
    └── BASELINE_PERFORMANCE_METRICS.md
```
