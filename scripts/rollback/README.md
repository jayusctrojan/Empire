# Infrastructure Rollback Scripts

This directory contains scripts for rolling back Empire v7.3 infrastructure components including Render services and database migrations.

## Quick Start

```bash
# Check current system status
./full_rollback.sh --status

# Preview a full rollback (dry run)
./full_rollback.sh --dry-run --full

# Rollback services only
./full_rollback.sh --services

# Rollback specific database migration
./full_rollback.sh --migration enable_rls_policies
```

## Scripts

### `render_rollback.sh`

Individual Render service management script.

```bash
# List recent deployments
./render_rollback.sh --list empire-api

# Rollback to previous deployment
./render_rollback.sh empire-api

# Rollback to specific deployment
./render_rollback.sh empire-api dep-abc123def

# Check all service statuses
./render_rollback.sh --status

# Enable/disable maintenance mode
./render_rollback.sh --maintenance empire-api
./render_rollback.sh --no-maintenance empire-api
```

### `full_rollback.sh`

Orchestrated full system rollback script.

```bash
# Full system rollback (services + database)
./full_rollback.sh --full

# Services only rollback
./full_rollback.sh --services

# Database only rollback
./full_rollback.sh --database

# Specific migration rollback
./full_rollback.sh --migration <migration_name>

# List available migrations
./full_rollback.sh --list-migrations

# Dry run mode
./full_rollback.sh --dry-run --full
```

## Environment Variables Required

```bash
# Render API (get from https://dashboard.render.com/u/settings/api-keys)
export RENDER_API_KEY="rnd_xxxxxxxxxxxxxxxxxx"

# Supabase (get from project settings)
export SUPABASE_URL="https://xxxxxxxx.supabase.co"
export SUPABASE_SERVICE_KEY="eyJxxx..."
```

## Available Services

| Service Name | Service ID | Type | URL |
|-------------|------------|------|-----|
| empire-api | srv-d44o2dq4d50c73elgupg | Web Service | https://jb-empire-api.onrender.com |
| empire-celery | srv-d44oclodl3ps73bg8rmg | Background Worker | - |
| empire-chat | srv-d47ptdmr433s739ljolg | Web Service | https://jb-empire-chat.onrender.com |
| llamaindex | srv-d2nl1lre5dus73atm9u0 | Web Service | https://jb-llamaindex.onrender.com |
| crewai | srv-d2n0hh3uibrs73buafo0 | Web Service | https://jb-crewai.onrender.com |
| n8n | srv-d2ii86umcj7s73ce35eg | Web Service | https://jb-n8n.onrender.com |

## Rollback Order

### Services (Reverse deployment order)
1. empire-chat (UI)
2. empire-api (API)
3. empire-celery (Worker)

### Database Migrations (Reverse chronological)
1. enhance_agent_interactions (Task 39.1)
2. add_performance_indexes (Task 43.3)
3. create_audit_logs_table (Task 41)
4. enable_rls_policies (Task 41.2)
5. add_memory_rls_policies (Task 27)
6. create_cost_tracking_tables (Task 30)

## Rollback Scenarios

### Scenario 1: API Issues After Deployment

```bash
# Put API in maintenance mode
./render_rollback.sh --maintenance empire-api

# Rollback API to previous version
./render_rollback.sh empire-api

# Wait for deployment, then verify
./render_rollback.sh --status

# Remove maintenance mode
./render_rollback.sh --no-maintenance empire-api
```

### Scenario 2: Database Migration Causing Issues

```bash
# Rollback specific migration
./full_rollback.sh --migration enable_rls_policies

# Verify database state
psql $DATABASE_URL -c "SELECT * FROM pg_policies WHERE schemaname='public';"
```

### Scenario 3: Complete System Rollback

```bash
# Preview the rollback
./full_rollback.sh --dry-run --full

# Execute full rollback (after confirmation)
./full_rollback.sh --full
```

## Post-Rollback Verification

After any rollback:

1. **Check service health**:
   ```bash
   curl https://jb-empire-api.onrender.com/health
   ```

2. **Check database state**:
   ```bash
   # Via Supabase MCP or psql
   SELECT table_name FROM information_schema.tables WHERE table_schema='public';
   ```

3. **Check logs**:
   ```bash
   # Render logs
   render logs --service empire-api --tail 100

   # Or via dashboard
   open https://dashboard.render.com/web/srv-d44o2dq4d50c73elgupg/logs
   ```

4. **Notify team**:
   - Post in #empire-incidents Slack channel
   - Update incident log

## Logs

All rollback operations are logged to:
```
logs/rollback_YYYYMMDD_HHMMSS.log
```

## Troubleshooting

### "RENDER_API_KEY not set"
```bash
export RENDER_API_KEY=$(cat ~/.render-api-key)
# Or source your .env file
source .env
```

### "Service not found"
Check the service name matches one of the available services:
```bash
./render_rollback.sh --status
```

### "Database connection failed"
Verify Supabase credentials:
```bash
psql "postgresql://postgres:$SUPABASE_SERVICE_KEY@db.$SUPABASE_URL:5432/postgres" -c "SELECT 1;"
```

### "Migration rollback failed"
1. Check the rollback SQL file exists
2. Review the error in the log file
3. Consider manual intervention via Supabase dashboard

## Emergency Contacts

- **On-call**: Check PagerDuty rotation
- **Slack**: #empire-incidents
- **Email**: jbajaj08@gmail.com
