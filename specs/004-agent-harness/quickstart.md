# Quickstart: Research Projects Feature

**Feature**: Research Projects (Agent Harness)
**Date**: 2025-01-10

## Prerequisites

Before implementing, ensure you have:

- [ ] Supabase project with pgvector enabled
- [ ] Anthropic API key (for Claude Sonnet 4)
- [ ] Celery + Redis worker infrastructure
- [ ] Backblaze B2 bucket for report storage
- [ ] Email service (SendGrid) configured

## Step 1: Database Setup

Run the migrations in order:

```bash
# From project root
supabase db push migrations/001_create_research_jobs.sql
supabase db push migrations/002_create_plan_tasks.sql
supabase db push migrations/003_create_research_artifacts.sql
supabase db push migrations/004_create_shared_reports.sql
supabase db push migrations/005_enable_rls_policies.sql
```

## Step 2: Environment Variables

Add to `.env`:

```bash
# Research Projects
RESEARCH_QUEUE_CONCURRENCY=2
RESEARCH_MAX_TASKS_PER_JOB=20
RESEARCH_TASK_TIMEOUT_SECONDS=300

# Email notifications
NOTIFICATION_EMAIL_FROM=research@empire.app
SENDGRID_API_KEY=<from .env>
```

## Step 3: Celery Configuration

Update `app/celery_config.py`:

```python
CELERY_TASK_ROUTES = {
    # ... existing routes
    'app.tasks.research_tasks.initialize_research_job': {'queue': 'research'},
    'app.tasks.research_tasks.execute_research_tasks': {'queue': 'research'},
    'app.tasks.research_tasks.generate_research_report': {'queue': 'research'},
}
```

## Step 4: Register Routes

Add to `app/main.py`:

```python
from app.routes import research_projects

app.include_router(research_projects.router)
```

## Step 5: Test the API

### Create a Project

```bash
curl -X POST https://jb-empire-api.onrender.com/api/research-projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the key terms in our vendor contracts?",
    "research_type": "general",
    "notify_email": "user@example.com"
  }'
```

### Check Status

```bash
curl https://jb-empire-api.onrender.com/api/research-projects/123/status \
  -H "Authorization: Bearer $TOKEN"
```

### Get Report

```bash
curl https://jb-empire-api.onrender.com/api/research-projects/123/report \
  -H "Authorization: Bearer $TOKEN"
```

## Step 6: Monitor with WebSocket

```javascript
const ws = new WebSocket(
  'wss://jb-empire-api.onrender.com/api/research-projects/ws/123',
  ['authorization', `Bearer ${token}`]
);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(`${msg.type}: ${JSON.stringify(msg.data)}`);
};
```

## Development Workflow

### Local Testing

```bash
# Terminal 1: Start FastAPI
uvicorn app.main:app --reload --port 8000

# Terminal 2: Start Celery worker
celery -A app.celery worker -Q research -l INFO

# Terminal 3: Start Redis (if not using Upstash)
redis-server
```

### Running Tests

```bash
# Unit tests
pytest tests/unit/test_initializer.py -v

# Integration tests (requires running services)
pytest tests/integration/test_research_workflow.py -v

# Performance tests
pytest tests/e2e/test_performance_sla.py -v
```

## Key Files

| File | Purpose |
|------|---------|
| `app/models/research_project.py` | Pydantic models |
| `app/services/research_initializer.py` | Task planning service |
| `app/services/task_harness.py` | Task execution service |
| `app/services/concurrent_executor.py` | Parallel execution engine |
| `app/routes/research_projects.py` | API endpoints |
| `app/tasks/research_tasks.py` | Celery tasks |

## Debugging Tips

### Check Task Status

```python
from app.services.task_harness import TaskHarnessService

harness = TaskHarnessService.get_instance()
stats = await harness.db.get_job_task_stats(job_id=123)
print(f"Completed: {stats['completed']}/{stats['total']}")
```

### View Execution Metrics

```python
from app.services.performance_monitor import PerformanceMonitor

monitor = PerformanceMonitor(db_service)
metrics = await monitor.collect_metrics(job_id=123)
print(metrics.to_json())
```

### Check Celery Queue

```bash
celery -A app.celery inspect active
celery -A app.celery inspect reserved
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Tasks not executing | Check Celery worker is running with `-Q research` |
| Slow performance | Verify Redis connection, check parallelism metrics |
| Report not generated | Check B2 credentials and bucket permissions |
| WebSocket disconnects | Check JWT expiry, implement reconnection logic |

## Next Steps

After setup:

1. Run `/speckit.tasks` to generate implementation tasks
2. Implement Phase 1 (Core Infrastructure) first
3. Test with simple queries before complex ones
4. Monitor performance metrics to validate SLAs
