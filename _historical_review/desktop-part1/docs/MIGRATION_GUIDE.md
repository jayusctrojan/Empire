# Empire v7.3 Database Migration Guide

This guide covers database schema migrations for Empire v7.3, including how to run migrations, create new migrations, rollback procedures, and best practices.

## Table of Contents
1. [Quick Start](#quick-start)
2. [Migration Overview](#migration-overview)
3. [Running Migrations](#running-migrations)
4. [Creating New Migrations](#creating-new-migrations)
5. [Rollback Procedures](#rollback-procedures)
6. [Migration Best Practices](#migration-best-practices)
7. [Troubleshooting](#troubleshooting)
8. [Version History](#version-history)

---

## Quick Start

### Prerequisites
- Supabase project with PostgreSQL
- Python 3.9+ with `psycopg2` installed
- Environment variables configured (see below)

### Required Environment Variables
```bash
# Add to .env file
SUPABASE_DB_HOST=db.xxxxx.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=<your-password>
SUPABASE_DB_PORT=5432
```

### Run All Pending Migrations
```bash
# Dry run (preview changes)
python scripts/run_migrations.py --dry-run

# Apply migrations
python scripts/run_migrations.py
```

### Using Supabase MCP (Claude Code)
```
"List all migrations in the database"
"Apply the agent_router_cache migration"
"Run the SQL from migrations/create_audit_logs_table.sql"
```

---

## Migration Overview

### Directory Structure
```
Empire/
├── migrations/                    # Root migrations (security, performance)
│   ├── add_memory_rls_policies.sql
│   ├── add_performance_indexes.sql
│   ├── create_audit_logs_table.sql
│   ├── create_cost_tracking_tables.sql
│   └── enable_rls_policies.sql
│
└── supabase/migrations/           # Feature migrations (v7.3)
    ├── 20251112_enhance_agent_interactions.sql
    ├── 20251124_v73_add_research_development_department.sql
    ├── 20251124_v73_add_processing_status_details.sql
    ├── 20251124_v73_add_source_metadata.sql
    ├── 20251124_v73_create_agent_router_cache.sql
    ├── 20251124_v73_create_agent_feedback.sql
    ├── 20251124_v73_create_book_metadata_tables.sql
    ├── 20251124_v73_create_course_structure_tables.sql
    ├── 20251124_v73_create_feature_flags.sql
    └── 20251124_v73_rollback_*.sql  # Corresponding rollback scripts
```

### Migration Naming Convention
```
YYYYMMDD_[version]_[action]_[description].sql
```

Examples:
- `20251124_v73_create_agent_router_cache.sql`
- `20251124_v73_add_source_metadata.sql`
- `20251124_v73_rollback_agent_router_cache.sql`

### Migration Tracking
Migrations are tracked in the `schema_migrations` table:
```sql
CREATE TABLE schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT
);
```

---

## Running Migrations

### Method 1: Python Script (Recommended)
```bash
# From project root
cd /path/to/Empire

# Preview migrations
python scripts/run_migrations.py --dry-run

# Apply all pending migrations
python scripts/run_migrations.py
```

### Method 2: Supabase CLI
```bash
# Push all migrations
supabase db push

# Reset database (DANGER: destroys all data)
supabase db reset
```

### Method 3: Direct SQL Execution
```bash
# Using psql
psql -h db.xxxxx.supabase.co -U postgres -d postgres \
  -f migrations/create_audit_logs_table.sql

# Using Supabase MCP (in Claude Code)
"Execute the SQL from migrations/create_audit_logs_table.sql"
```

### Method 4: Supabase Dashboard
1. Go to Supabase Dashboard → SQL Editor
2. Copy migration SQL content
3. Execute

### Migration Order (v7.3)
**IMPORTANT**: Apply migrations in this exact order:

1. `20251124_v73_add_research_development_department.sql` - Department enum
2. `20251124_v73_add_processing_status_details.sql` - Status tracking
3. `20251124_v73_add_source_metadata.sql` - Source attribution
4. `20251124_v73_create_agent_router_cache.sql` - Router cache
5. `20251124_v73_create_agent_feedback.sql` - Feedback system
6. `20251124_v73_create_book_metadata_tables.sql` - Book support
7. `20251124_v73_create_course_structure_tables.sql` - Course system
8. `20251124_v73_create_feature_flags.sql` - Feature flags

---

## Creating New Migrations

### Step 1: Create Migration File
```bash
# Use timestamp + descriptive name
touch supabase/migrations/$(date +%Y%m%d)_v73_create_new_table.sql
```

### Step 2: Write Migration SQL
```sql
-- Migration: Create new_feature table
-- Version: 7.3
-- Date: 2025-01-25
-- Description: Adds support for new feature X
-- Dependencies: None

-- ============================================
-- UP MIGRATION
-- ============================================

-- Create table
CREATE TABLE IF NOT EXISTS new_feature (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_new_feature_name
    ON new_feature(name);
CREATE INDEX IF NOT EXISTS idx_new_feature_active
    ON new_feature(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_new_feature_metadata
    ON new_feature USING GIN (metadata);

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_new_feature_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_new_feature_updated_at
    BEFORE UPDATE ON new_feature
    FOR EACH ROW
    EXECUTE FUNCTION update_new_feature_updated_at();

-- Enable RLS
ALTER TABLE new_feature ENABLE ROW LEVEL SECURITY;

-- RLS Policy
CREATE POLICY new_feature_user_access ON new_feature
    FOR ALL
    USING (auth.uid() IS NOT NULL);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON new_feature TO authenticated;
GRANT SELECT ON new_feature TO anon;

-- ============================================
-- VERIFICATION QUERIES (run manually)
-- ============================================
-- SELECT * FROM information_schema.tables WHERE table_name = 'new_feature';
-- SELECT * FROM pg_indexes WHERE tablename = 'new_feature';
```

### Step 3: Create Rollback Script
```bash
touch supabase/migrations/$(date +%Y%m%d)_v73_rollback_new_table.sql
```

```sql
-- Rollback: Drop new_feature table
-- Version: 7.3
-- Date: 2025-01-25
-- Description: Reverts create_new_table migration

-- ============================================
-- DOWN MIGRATION
-- ============================================

-- Drop trigger
DROP TRIGGER IF EXISTS trigger_new_feature_updated_at ON new_feature;

-- Drop function
DROP FUNCTION IF EXISTS update_new_feature_updated_at();

-- Drop table (cascades indexes and policies)
DROP TABLE IF EXISTS new_feature CASCADE;

-- ============================================
-- VERIFICATION
-- ============================================
-- SELECT * FROM information_schema.tables WHERE table_name = 'new_feature';
-- Should return 0 rows
```

### Step 4: Test Migration
```sql
-- Run migration
\i supabase/migrations/20250125_v73_create_new_table.sql

-- Verify
SELECT * FROM information_schema.tables WHERE table_name = 'new_feature';

-- Test rollback
\i supabase/migrations/20250125_v73_rollback_new_table.sql

-- Verify rollback
SELECT * FROM information_schema.tables WHERE table_name = 'new_feature';
-- Should return 0 rows

-- Re-apply migration
\i supabase/migrations/20250125_v73_create_new_table.sql
```

---

## Rollback Procedures

### Rollback Single Migration
```bash
# Using psql
psql -h db.xxxxx.supabase.co -U postgres -d postgres \
  -f supabase/migrations/20251124_v73_rollback_agent_router_cache.sql
```

### Rollback All v7.3 Migrations (Reverse Order)
```sql
-- Execute in this order:
\i supabase/migrations/20251124_v73_rollback_feature_flags.sql
\i supabase/migrations/20251124_v73_rollback_course_structure_tables.sql
\i supabase/migrations/20251124_v73_rollback_book_metadata_tables.sql
\i supabase/migrations/20251124_v73_rollback_agent_feedback.sql
\i supabase/migrations/20251124_v73_rollback_agent_router_cache.sql
\i supabase/migrations/20251124_v73_rollback_source_metadata.sql
\i supabase/migrations/20251124_v73_rollback_processing_status_details.sql
\i supabase/migrations/20251124_v73_rollback_research_development_department.sql
```

### Update Migration Tracking After Rollback
```sql
-- Mark migration as rolled back
UPDATE schema_migrations
SET success = FALSE,
    error_message = 'Manually rolled back on ' || NOW()::TEXT
WHERE migration_name = '20251124_v73_create_agent_router_cache.sql';

-- Or delete the record entirely
DELETE FROM schema_migrations
WHERE migration_name = '20251124_v73_create_agent_router_cache.sql';
```

### Emergency Rollback Script
```sql
-- For emergency rollbacks when you need to restore quickly
-- Creates a savepoint before changes

BEGIN;
SAVEPOINT before_migration;

-- Run your migration SQL here
-- ...

-- If something goes wrong:
ROLLBACK TO SAVEPOINT before_migration;

-- If everything is OK:
RELEASE SAVEPOINT before_migration;
COMMIT;
```

---

## Migration Best Practices

### 1. Always Create Rollback Scripts
Every migration should have a corresponding rollback script that completely reverses all changes.

### 2. Use Transactions
Wrap migrations in transactions for atomicity:
```sql
BEGIN;

-- Migration SQL here

COMMIT;
```

### 3. Make Migrations Idempotent
Use `IF NOT EXISTS` and `IF EXISTS` clauses:
```sql
CREATE TABLE IF NOT EXISTS my_table (...);
CREATE INDEX IF NOT EXISTS idx_name ON my_table(...);
DROP TABLE IF EXISTS my_table CASCADE;
```

### 4. Test in Development First
Always test migrations in a development environment before production:
```bash
# Create a branch database
supabase db branch create feature/new-migration

# Test migration
psql -f migration.sql

# Test rollback
psql -f rollback.sql
```

### 5. Backup Before Production Migrations
```bash
# Using pg_dump
pg_dump -h db.xxxxx.supabase.co -U postgres -d postgres \
  --schema-only > schema_backup_$(date +%Y%m%d).sql

# Full backup including data
pg_dump -h db.xxxxx.supabase.co -U postgres -d postgres \
  > full_backup_$(date +%Y%m%d).sql
```

### 6. Document Dependencies
List any dependencies at the top of migration files:
```sql
-- Dependencies:
--   - pgvector extension must be enabled
--   - documents table must exist
--   - Migration 2.1 (department_enum) must be applied first
```

### 7. Use Descriptive Comments
```sql
-- Create table for storing AI agent routing decisions
-- This table enables <100ms routing by caching decisions
-- Related: agent_feedback table for learning loop
CREATE TABLE agent_router_cache (...);
```

### 8. Handle NULL Values Carefully
```sql
-- Add column with default value to avoid NULL issues
ALTER TABLE existing_table
ADD COLUMN new_column VARCHAR(255) DEFAULT 'unknown';

-- Then update existing rows
UPDATE existing_table SET new_column = 'calculated_value' WHERE condition;

-- Finally, add NOT NULL constraint if needed
ALTER TABLE existing_table ALTER COLUMN new_column SET NOT NULL;
```

### 9. Create Indexes Concurrently (Production)
```sql
-- Avoid table locks on large tables
CREATE INDEX CONCURRENTLY idx_large_table_column
ON large_table(column);
```

### 10. Monitor Migration Performance
```sql
-- Check migration execution time
SELECT
    migration_name,
    applied_at,
    EXTRACT(EPOCH FROM (NOW() - applied_at)) as seconds_ago
FROM schema_migrations
ORDER BY applied_at DESC
LIMIT 10;
```

---

## Troubleshooting

### Common Issues

#### 1. Permission Denied
```sql
-- Grant necessary permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO postgres;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres;
```

#### 2. Enum Already Exists
```sql
-- Check existing enum values
SELECT typname, enumlabel
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
WHERE typname = 'workflow_type';

-- Drop and recreate if needed
DROP TYPE IF EXISTS workflow_type CASCADE;
```

#### 3. Foreign Key Violation
```sql
-- Find orphaned references
SELECT * FROM child_table
WHERE parent_id NOT IN (SELECT id FROM parent_table);

-- Delete orphaned records
DELETE FROM child_table
WHERE parent_id NOT IN (SELECT id FROM parent_table);
```

#### 4. Migration Already Applied
```sql
-- Check if migration was already applied
SELECT * FROM schema_migrations
WHERE migration_name = 'your_migration.sql';

-- Remove record to re-run
DELETE FROM schema_migrations
WHERE migration_name = 'your_migration.sql';
```

#### 5. Vector Extension Not Enabled
```sql
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
SELECT * FROM pg_extension WHERE extname = 'vector';
```

#### 6. Table Lock Timeout
```sql
-- Increase lock timeout for large tables
SET lock_timeout = '10s';

-- Or use concurrent operations
CREATE INDEX CONCURRENTLY idx_name ON large_table(column);
```

### Diagnostic Queries

```sql
-- Check table structure
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'your_table'
ORDER BY ordinal_position;

-- Check indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'your_table';

-- Check constraints
SELECT conname, contype, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'your_table'::regclass;

-- Check RLS policies
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
FROM pg_policies
WHERE tablename = 'your_table';

-- Check table size
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## Version History

### v7.3 Migrations (November 2024)

| Migration | Description | Status |
|-----------|-------------|--------|
| `20251112_enhance_agent_interactions` | Agent interaction enhancements | ✅ Applied |
| `20251124_v73_add_research_development_department` | R&D department enum | ✅ Applied |
| `20251124_v73_add_processing_status_details` | Processing status tracking | ✅ Applied |
| `20251124_v73_add_source_metadata` | Source attribution | ✅ Applied |
| `20251124_v73_create_agent_router_cache` | Router cache table | ✅ Applied |
| `20251124_v73_create_agent_feedback` | Feedback collection | ✅ Applied |
| `20251124_v73_create_book_metadata_tables` | Book support (5 tables) | ✅ Applied |
| `20251124_v73_create_course_structure_tables` | Course system (6 tables) | ✅ Applied |
| `20251124_v73_create_feature_flags` | Feature flag system | ✅ Applied |

### Security Migrations

| Migration | Description | Status |
|-----------|-------------|--------|
| `enable_rls_policies` | Row-level security on 14 tables | ✅ Applied |
| `add_memory_rls_policies` | User memory graph RLS | ✅ Applied |
| `create_audit_logs_table` | Comprehensive audit logging | ✅ Applied |
| `add_performance_indexes` | B-tree indexes for lookups | ✅ Applied |

### Cost Tracking Migrations

| Migration | Description | Status |
|-----------|-------------|--------|
| `create_cost_tracking_tables` | Budget configs, alerts, reports | ✅ Applied |

---

## Related Documentation

- [DATABASE_ER_DIAGRAMS.md](./DATABASE_ER_DIAGRAMS.md) - Visual schema documentation
- [API_REFERENCE.md](./API_REFERENCE.md) - API endpoints documentation
- [DEVELOPER_GUIDE.md](./onboarding/DEVELOPER_GUIDE.md) - Developer onboarding
- [MIGRATION_VALIDATION_GUIDE.md](../supabase/migrations/MIGRATION_VALIDATION_GUIDE.md) - Detailed validation steps

---

## Support

For migration issues:
1. Check troubleshooting section above
2. Review error logs in `schema_migrations` table
3. Create GitHub issue with:
   - Migration file name
   - Error message
   - Database logs

---

*Generated for Empire v7.3 - Task 5.4 (Migration Guide Documentation)*
