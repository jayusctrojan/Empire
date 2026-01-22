# Database Migration Rollback Scripts

This directory contains rollback scripts for all Empire v7.3 database migrations. Each rollback script can safely revert its corresponding forward migration.

## Quick Reference

| Rollback Script | Original Migration | Task | Risk Level |
|----------------|-------------------|------|------------|
| `rollback_enable_rls_policies.sql` | `enable_rls_policies.sql` | 41.2 | ⚠️ HIGH (security) |
| `rollback_create_audit_logs_table.sql` | `create_audit_logs_table.sql` | 41 | ⚠️ HIGH (compliance) |
| `rollback_add_performance_indexes.sql` | `add_performance_indexes.sql` | 43.3 | 🟡 MEDIUM |
| `rollback_create_cost_tracking_tables.sql` | `create_cost_tracking_tables.sql` | 30 | 🟡 MEDIUM |
| `rollback_add_memory_rls_policies.sql` | `add_memory_rls_policies.sql` | 27 | ⚠️ HIGH (security) |
| `rollback_enhance_agent_interactions.sql` | `enhance_agent_interactions.sql` | 39.1 | 🟢 LOW |

## Usage

### Single Migration Rollback

```bash
# Via psql
psql -d empire -f migrations/rollback/rollback_<migration_name>.sql

# Via Supabase CLI
supabase db reset --debug  # Then selectively re-apply migrations
```

### Via Application

```python
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

with open('migrations/rollback/rollback_<migration_name>.sql', 'r') as f:
    sql = f.read()
    supabase.rpc('exec_sql', {'query': sql}).execute()
```

## Rollback Order (Recommended)

When rolling back multiple migrations, use reverse chronological order:

1. `rollback_enhance_agent_interactions.sql` (most recent)
2. `rollback_add_performance_indexes.sql`
3. `rollback_create_audit_logs_table.sql`
4. `rollback_enable_rls_policies.sql`
5. `rollback_add_memory_rls_policies.sql`
6. `rollback_create_cost_tracking_tables.sql`

## Pre-Rollback Checklist

- [ ] **Backup database** before any rollback
- [ ] **Export data** from tables being dropped
- [ ] **Notify team** of planned maintenance
- [ ] **Test in staging** first
- [ ] **Document reason** for rollback

## Post-Rollback Verification

After each rollback, verify:

```sql
-- Check table exists/not exists
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name = '<table_name>';

-- Check RLS status
SELECT tablename, rowsecurity FROM pg_tables
WHERE schemaname = 'public';

-- Check indexes
SELECT indexname FROM pg_indexes
WHERE schemaname = 'public' AND tablename = '<table_name>';

-- Check policies
SELECT policyname, tablename FROM pg_policies
WHERE schemaname = 'public';
```

## Emergency Rollback Procedures

For production emergencies, see the full runbook at:
`docs/ROLLBACK_RUNBOOK.md`

### Quick Emergency Commands

```bash
# 1. Put service in maintenance mode
curl -X POST https://jb-empire-api.onrender.com/api/admin/maintenance -H "Authorization: Bearer $ADMIN_TOKEN"

# 2. Connect to Supabase
psql $SUPABASE_CONNECTION_STRING

# 3. Run rollback
\i migrations/rollback/rollback_<migration>.sql

# 4. Verify rollback
SELECT * FROM pg_tables WHERE schemaname = 'public';

# 5. Take service out of maintenance
curl -X DELETE https://jb-empire-api.onrender.com/api/admin/maintenance -H "Authorization: Bearer $ADMIN_TOKEN"
```

## v7.3 Migration Rollbacks (Supabase Folder)

Additional v7.3-specific rollback scripts are in `supabase/migrations/`:

- `20251124_v73_rollback_research_development_department.sql`
- `20251124_v73_rollback_processing_status_details.sql`
- `20251124_v73_rollback_source_metadata.sql`
- `20251124_v73_rollback_agent_router_cache.sql`
- `20251124_v73_rollback_agent_feedback.sql`
- `20251124_v73_rollback_book_metadata_tables.sql`
- `20251124_v73_rollback_course_structure_tables.sql`
- `20251124_v73_rollback_feature_flags.sql`

## Security Considerations

⚠️ **WARNING**: Some rollbacks significantly impact security posture:

1. **RLS Rollbacks** (`rollback_enable_rls_policies.sql`, `rollback_add_memory_rls_policies.sql`)
   - Removes database-level data isolation
   - Application becomes sole security layer
   - Monitor for unauthorized data access

2. **Audit Log Rollback** (`rollback_create_audit_logs_table.sql`)
   - Compliance audit trail deleted
   - SOC 2, GDPR, HIPAA implications
   - Consider external logging alternative

## Contact

For rollback assistance:
- **On-call**: Check PagerDuty rotation
- **Slack**: #empire-incidents
- **Email**: jbajaj08@gmail.com
