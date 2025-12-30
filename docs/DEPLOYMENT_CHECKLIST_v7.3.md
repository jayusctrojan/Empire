# Empire v7.3 Deployment Checklist

**Version:** 7.3.0
**Date:** December 30, 2024

---

## Pre-Deployment Checklist

### 1. Code Review & Testing
- [x] All 132 tests passing
- [x] 19 tests properly skipped (live server/Redis requirements)
- [x] Code committed to git (hash: 5500a8e)
- [x] No security vulnerabilities in dependencies

### 2. Database Migrations Ready

#### Supabase Migrations (Applied via Supabase Dashboard)
| Migration | Status | Rollback Available |
|-----------|--------|-------------------|
| 20251124_v73_add_research_development_department | Ready | Yes |
| 20251124_v73_add_processing_status_details | Ready | Yes |
| 20251124_v73_add_source_metadata | Ready | Yes |
| 20251124_v73_create_agent_router_cache | Ready | Yes |
| 20251124_v73_create_agent_feedback | Ready | Yes |
| 20251124_v73_create_book_metadata_tables | Ready | Yes |
| 20251124_v73_create_course_structure_tables | Ready | Yes |
| 20251124_v73_create_feature_flags | Ready | Yes |
| 20251201_v73_create_embeddings_cache | Ready | Yes |
| 20251201_v73_create_hybrid_search | Ready | Yes |
| 20251112_enhance_agent_interactions | Ready | Yes |

#### Local Migrations (Apply Manually if Needed)
| Migration | Purpose |
|-----------|---------|
| create_memory_graph_tables.sql | User memory graph storage |
| create_rbac_tables.sql | Role-based access control |
| create_crewai_generated_assets.sql | CrewAI asset tracking |
| enable_rls_policies.sql | Row-level security |
| create_audit_logs_table.sql | Audit logging |
| add_performance_indexes.sql | Query optimization |
| create_cost_tracking_tables.sql | API cost tracking |
| add_memory_rls_policies.sql | Memory table RLS |

### 3. Environment Variables

#### Required Variables (Verify on Render)
```bash
# Core API Keys
ANTHROPIC_API_KEY=<set>
SUPABASE_URL=<set>
SUPABASE_SERVICE_KEY=<set>

# New in v7.3
ARCADE_API_KEY=<set>
ARCADE_ENABLED=true
LANGGRAPH_DEFAULT_MODEL=claude-3-5-haiku-20241022

# Redis (Upstash)
REDIS_URL=rediss://<token>@<host>:6379
CELERY_BROKER_URL=rediss://<token>@<host>:6379/0
CELERY_RESULT_BACKEND=rediss://<token>@<host>:6379/1

# Monitoring
PROMETHEUS_ENABLED=true
```

### 4. Render Services Status

| Service | Service ID | Auto-Deploy | Health Check |
|---------|------------|-------------|--------------|
| jb-empire-api | srv-d44o2dq4d50c73elgupg | Yes (main) | /health |
| jb-empire-celery | srv-d44oclodl3ps73bg8rmg | Yes (main) | N/A |
| jb-empire-chat | srv-d47ptdmr433s739ljolg | Yes (main) | N/A |
| jb-llamaindex | srv-d2nl1lre5dus73atm9u0 | Yes | N/A |
| jb-crewai | srv-d2n0hh3uibrs73buafo0 | Yes | N/A |

---

## Deployment Steps

### Step 1: Pre-Deployment Verification
```bash
# Run tests locally
cd Empire
source venv/bin/activate
python -m pytest tests/ -v --tb=short

# Verify git status
git status
git log -1 --oneline
```

### Step 2: Apply Database Migrations (if not auto-applied)
1. Go to Supabase Dashboard > SQL Editor
2. Run migrations in order from `supabase/migrations/` directory
3. Verify each migration succeeds before proceeding

### Step 3: Deploy to Render
```bash
# Push to main branch (auto-deploys to Render)
git push origin main

# Or manually trigger deploy via Render Dashboard
```

### Step 4: Monitor Deployment
1. Watch Render logs for deployment progress
2. Check for any build or startup errors
3. Verify health endpoints respond

### Step 5: Post-Deployment Verification
```bash
# Health checks
curl https://jb-empire-api.onrender.com/health
curl https://jb-empire-api.onrender.com/api/query/health
curl https://jb-empire-api.onrender.com/api/summarizer/health
curl https://jb-empire-api.onrender.com/api/classifier/health

# Test a query
curl -X POST https://jb-empire-api.onrender.com/api/query/auto \
  -H "Content-Type: application/json" \
  -d '{"query": "test query"}'
```

---

## Rollback Plan

### Immediate Rollback (Render)
1. Go to Render Dashboard
2. Select the service (jb-empire-api)
3. Click "Manual Deploy" > Select previous commit
4. Wait for deployment to complete

### Database Rollback
Each migration has a corresponding rollback script in:
- `supabase/migrations/*_rollback_*.sql`
- `migrations/rollback/rollback_*.sql`

Run rollback scripts in reverse order of application.

### Emergency Contacts
- Lead Developer: Jay Bajaj (jbajaj08@gmail.com)

---

## Monitoring Post-Deployment

### Services to Monitor
- **Prometheus**: http://localhost:9090 (or Render Prometheus if deployed)
- **Grafana**: http://localhost:3001
- **Alertmanager**: http://localhost:9093

### Key Metrics to Watch
- API response times (p95 < 500ms)
- Error rate (< 1%)
- WebSocket connection count
- Celery task queue depth
- Redis memory usage

### Alert Thresholds
| Metric | Warning | Critical |
|--------|---------|----------|
| Error Rate | > 1/sec | > 5/sec |
| Response Time (p95) | > 30s | > 60s |
| CPU Usage | > 80% | > 95% |
| Memory Usage | > 80% | > 95% |
| Queue Backlog | > 100 | > 500 |

---

## Feature Flags

### New Features (v7.3)
All features are enabled by default. To disable:

```python
# In app/config/feature_flags.py or via admin endpoint
FEATURE_FLAGS = {
    "ai_summarizer": True,
    "department_classifier": True,
    "document_analysis": True,
    "multi_agent_orchestration": True,
    "websocket_status": True,
    "intelligent_routing": True,
}
```

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | Jay Bajaj | 2024-12-30 | _________ |
| QA | _________ | _________ | _________ |
| Ops | _________ | _________ | _________ |

---

**Checklist Version:** 1.0
**Last Updated:** December 30, 2024
