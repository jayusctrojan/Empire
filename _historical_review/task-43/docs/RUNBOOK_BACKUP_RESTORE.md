# Empire v7.3 - Backup & Restore Runbook

**Document Version:** 1.0
**Last Updated:** 2025-01-15
**Owner:** Operations Team
**Review Frequency:** Monthly

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Prerequisites](#prerequisites)
3. [Automated Backups](#automated-backups)
4. [Manual Backup Procedures](#manual-backup-procedures)
5. [Restore Procedures](#restore-procedures)
6. [Verification Steps](#verification-steps)
7. [Troubleshooting](#troubleshooting)
8. [Emergency Scenarios](#emergency-scenarios)

---

## Quick Reference

### One-Line Commands

```bash
# List available backups
python scripts/restore_supabase.py --list

# Create immediate backup
python scripts/backup_supabase.py

# Restore latest backup (READ-ONLY - dry run first)
python scripts/restore_supabase.py --latest --dry-run

# Restore latest backup (DESTRUCTIVE - drops database!)
python scripts/restore_supabase.py --latest --drop-existing

# Test backup without uploading
python scripts/backup_supabase.py --dry-run
```

### Key Facts

- **Backup Frequency**: Daily at 2:00 AM UTC (automated via GitHub Actions)
- **Backup Location**: Backblaze B2 bucket `empire-backups` → `supabase/` folder
- **Retention Policy**: 30 days (older backups auto-deleted)
- **Backup Format**: PostgreSQL dump (`.sql.gz` compressed)
- **Average Backup Size**: ~50-200 MB (compressed)
- **Average Backup Time**: 5-10 minutes
- **Average Restore Time**: 30-90 minutes (depends on database size)
- **RPO (Recovery Point Objective)**: 24 hours (daily backups)
- **RTO (Recovery Time Objective)**: 2 hours (manual restore)

---

## Prerequisites

### Required Software

**On your local machine:**
```bash
# Python 3.11+
python3 --version

# PostgreSQL client (for pg_dump and psql)
psql --version

# Python dependencies
pip install b2sdk psycopg2-binary
```

**On macOS:**
```bash
brew install postgresql
pip3 install b2sdk psycopg2-binary
```

**On Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y postgresql-client python3-pip
pip3 install b2sdk psycopg2-binary
```

### Required Credentials

All credentials must be in your `.env` file:

```bash
# Supabase Database
SUPABASE_DB_HOST=db.xxxxx.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=<your-password>
SUPABASE_DB_PORT=5432

# Backblaze B2
B2_APPLICATION_KEY_ID=<your-key-id>
B2_APPLICATION_KEY=<your-application-key>
B2_BUCKET_NAME=empire-backups

# Optional: Backup retention
BACKUP_RETENTION_DAYS=30
```

**Security Note**: NEVER commit the `.env` file to git. Keep it local only.

### Access Verification

Before starting, verify you can access:

1. **Supabase Database**:
   ```bash
   psql -h $SUPABASE_DB_HOST -U $SUPABASE_DB_USER -d $SUPABASE_DB_NAME -c "SELECT version();"
   # Enter password when prompted
   ```

2. **Backblaze B2**:
   ```bash
   python scripts/restore_supabase.py --list
   # Should show available backups
   ```

---

## Automated Backups

### How Automated Backups Work

**GitHub Actions Workflow** (`.github/workflows/daily-backup.yml`):
- **Schedule**: Daily at 2:00 AM UTC
- **Trigger**: Automatic (cron) + Manual (workflow_dispatch)
- **Steps**:
  1. Checkout code
  2. Install Python 3.11 and dependencies
  3. Run `scripts/backup_supabase.py`
  4. Upload logs to GitHub Artifacts
  5. Create GitHub issue on failure

**Backup Process** (`scripts/backup_supabase.py`):
1. Create PostgreSQL dump with `pg_dump`
2. Compress with gzip (level 9)
3. Upload to Backblaze B2
4. Delete backups older than 30 days
5. Clean up local files

### Monitoring Automated Backups

**Check Latest Backup Status:**

1. **GitHub Actions**:
   ```
   https://github.com/[owner]/[repo]/actions/workflows/daily-backup.yml
   ```
   - Green checkmark = successful
   - Red X = failed (check issue tracker)

2. **Backup Logs** (GitHub Artifacts):
   - Go to latest workflow run
   - Download `backup-log-XXXXXX` artifact
   - Review `backup.log` for details

3. **Backblaze B2 Dashboard**:
   ```
   https://secure.backblaze.com/b2_buckets.htm
   ```
   - Navigate to `empire-backups` bucket
   - Check `supabase/` folder for latest `.sql.gz` file
   - Verify timestamp is within 24 hours

**Verify Backup Integrity:**

```bash
# List backups and check timestamps
python scripts/restore_supabase.py --list

# Expected output:
# Available backups:
# ─────────────────────────────────────────────────────────
# 1. supabase/supabase_backup_20250115_020015.sql.gz
#    Size: 123.45 MB
#    Date: 2025-01-15 02:00:15
#
# 2. supabase/supabase_backup_20250114_020012.sql.gz
#    Size: 121.32 MB
#    Date: 2025-01-14 02:00:12
```

### Manual Trigger of Automated Backup

**Via GitHub Actions UI:**
1. Go to Actions → Daily Database Backup
2. Click "Run workflow"
3. Select branch (usually `main`)
4. Choose "Dry run" = `false` (default)
5. Click "Run workflow"

**Via GitHub CLI:**
```bash
gh workflow run daily-backup.yml
```

---

## Manual Backup Procedures

### When to Run Manual Backups

**Required before**:
- Major database migrations
- Schema changes
- Large data imports
- Production deployments
- Testing restore procedures

**NOT required for**:
- Normal development (daily backups are sufficient)
- Small data updates
- Read-only operations

### Full Manual Backup (Production)

**Step 1: Navigate to Project Directory**

```bash
cd /path/to/Empire
```

**Step 2: Verify Environment Variables**

```bash
# Check .env file exists
ls -la .env

# Verify key variables are set (DO NOT print values)
env | grep -E "SUPABASE_DB_HOST|B2_APPLICATION_KEY_ID" > /dev/null && echo "✓ Variables set"
```

**Step 3: Create Backup**

```bash
# Full production backup
python scripts/backup_supabase.py

# Expected output:
# ============================================================
# Starting Supabase backup process
# Database: db.xxxxx.supabase.co/postgres
# Dry run: False
# ============================================================
# Creating database dump: backups/temp/supabase_backup_20250115_143022.sql
# Dump created successfully: 234.56 MB
# Compressing dump: backups/temp/supabase_backup_20250115_143022.sql.gz
# Compression complete: 87.23 MB (62.8% reduction)
# Backup MD5 checksum: a1b2c3d4e5f6...
# Removed uncompressed dump
# Uploading to B2: supabase_backup_20250115_143022.sql.gz
# Upload successful: supabase/supabase_backup_20250115_143022.sql.gz
# Cleaning up backups older than 30 days
# Deleted 0 old backup(s)
# Removed local backup: backups/temp/supabase_backup_20250115_143022.sql.gz
# ============================================================
# Backup completed successfully
# ============================================================
```

**Step 4: Verify Backup**

```bash
# List backups to confirm upload
python scripts/restore_supabase.py --list

# Check logs
cat logs/backup.log | tail -20
```

**Step 5: Document Backup**

Record in your incident log:
- Backup timestamp
- Reason for manual backup
- Backup file name
- MD5 checksum (from logs)

### Test Backup (Dry Run)

**Use dry run to test without uploading:**

```bash
# Test backup process
python scripts/backup_supabase.py --dry-run

# Expected output:
# ============================================================
# Starting Supabase backup process
# Database: db.xxxxx.supabase.co/postgres
# Dry run: True
# ============================================================
# DRY RUN: Would create dump
# DRY RUN: Would compress dump
# DRY RUN: Would upload to B2
# DRY RUN: Would cleanup old backups
# DRY RUN: Would cleanup local file
# ============================================================
# Backup completed successfully
# ============================================================
```

**Benefits of dry run**:
- Verify credentials are correct
- Test script functionality
- No B2 storage costs
- No network bandwidth usage

---

## Restore Procedures

### ⚠️ CRITICAL WARNINGS

**Before ANY restore operation, understand:**

1. **Data Loss Risk**: Restore operations can PERMANENTLY DELETE current data
2. **Downtime Required**: Production services MUST be stopped during restore
3. **Time Commitment**: Restores can take 30-90 minutes
4. **Irreversible**: Once started with `--drop-existing`, there is NO undo
5. **Backup First**: ALWAYS create a fresh backup before restoring (unless database is corrupted)

**Required Approvals:**
- **Test/Dev Restore**: Team lead approval
- **Production Restore**: CTO + System Owner approval + incident ticket

### Pre-Restore Checklist

Before starting ANY restore:

- [ ] **Create Fresh Backup** (unless database is corrupted):
  ```bash
  python scripts/backup_supabase.py
  ```

- [ ] **Stop All Services** (prevents data conflicts):
  - Stop FastAPI service (Render dashboard)
  - Stop Celery workers (Render dashboard)
  - Notify users of maintenance window

- [ ] **Verify Backup File Exists**:
  ```bash
  python scripts/restore_supabase.py --list
  ```

- [ ] **Get Approval** (for production):
  - Incident ticket number: _________
  - Approved by: _________
  - Timestamp: _________

- [ ] **Review Restore Plan** with team

- [ ] **Test Restore** on non-production database first (if possible)

### Restore Procedure 1: View Available Backups

**Step 1: List All Backups**

```bash
python scripts/restore_supabase.py --list
```

**Expected Output:**
```
Available backups:
────────────────────────────────────────────────────────────────────────────────
1. supabase/supabase_backup_20250115_020015.sql.gz
   Size: 123.45 MB
   Date: 2025-01-15 02:00:15

2. supabase/supabase_backup_20250114_020012.sql.gz
   Size: 121.32 MB
   Date: 2025-01-14 02:00:12

3. supabase/supabase_backup_20250113_020009.sql.gz
   Size: 119.87 MB
   Date: 2025-01-13 02:00:09
```

**Step 2: Choose Backup**

Identify the backup you want to restore:
- Latest backup: Use `--latest` flag
- Specific backup: Use `--file supabase/supabase_backup_YYYYMMDD_HHMMSS.sql.gz`

### Restore Procedure 2: Dry Run (ALWAYS DO THIS FIRST)

**Purpose**: Test restore without modifying database

**Step 1: Run Dry Run**

```bash
# Test restore of latest backup
python scripts/restore_supabase.py --latest --dry-run

# Or test specific backup
python scripts/restore_supabase.py \
  --file supabase/supabase_backup_20250115_020015.sql.gz \
  --dry-run
```

**Expected Output:**
```
============================================================
Starting Supabase restore process
Database: db.xxxxx.supabase.co/postgres
Dry run: True
============================================================
Listing available backups from B2
Found 30 backup(s)
Using latest backup: supabase/supabase_backup_20250115_020015.sql.gz
Downloading backup: supabase/supabase_backup_20250115_020015.sql.gz
DRY RUN: Would download backup
Download complete: 0.00 MB
Decompressing backup: backups/restore/supabase_backup_20250115_020015.sql
DRY RUN: Would decompress backup
Decompression complete: 0.00 MB
Restoring database from: backups/restore/supabase_backup_20250115_020015.sql
DRY RUN: Would restore database
DRY RUN: Would cleanup local files
============================================================
Restore completed successfully
============================================================
```

**Step 2: Verify No Errors**

- Check for any error messages in output
- Review `logs/restore.log`
- Confirm dry run completed successfully

### Restore Procedure 3: Full Restore (DESTRUCTIVE)

**⚠️ WARNING: This WILL DELETE all current data!**

**Step 1: Stop All Services**

```bash
# Via Render Dashboard:
# 1. Go to https://dashboard.render.com/web/srv-d44o2dq4d50c73elgupg
# 2. Click "Manual Deploy" dropdown → "Suspend Service"
# 3. Go to https://dashboard.render.com/worker/srv-d44oclodl3ps73bg8rmg
# 4. Click "Manual Deploy" dropdown → "Suspend Service"
```

**Step 2: Create Final Backup** (unless database is corrupted)

```bash
python scripts/backup_supabase.py
```

**Step 3: Run Restore**

```bash
# Restore latest backup
python scripts/restore_supabase.py --latest --drop-existing

# Or restore specific backup
python scripts/restore_supabase.py \
  --file supabase/supabase_backup_20250115_020015.sql.gz \
  --drop-existing
```

**Expected Output:**
```
============================================================
Starting Supabase restore process
Database: db.xxxxx.supabase.co/postgres
Dry run: False
============================================================
Using latest backup: supabase/supabase_backup_20250115_020015.sql.gz
Downloading backup: supabase/supabase_backup_20250115_020015.sql.gz
Download complete: 123.45 MB
Decompressing backup: backups/restore/supabase_backup_20250115_020015.sql
Decompression complete: 456.78 MB
Restoring database from: backups/restore/supabase_backup_20250115_020015.sql

⚠️  Dropping existing database - THIS WILL DELETE ALL DATA!
Sleeping 5 seconds... Press Ctrl+C to cancel

Database dropped and recreated
Restore completed successfully
Removed local file: backups/restore/supabase_backup_20250115_020015.sql.gz
Removed local file: backups/restore/supabase_backup_20250115_020015.sql
============================================================
Restore completed successfully
============================================================
```

**Step 4: Verify Restore** (see Verification Steps section below)

**Step 5: Restart Services**

```bash
# Via Render Dashboard:
# 1. Go to https://dashboard.render.com/web/srv-d44o2dq4d50c73elgupg
# 2. Click "Resume Service"
# 3. Go to https://dashboard.render.com/worker/srv-d44oclodl3ps73bg8rmg
# 4. Click "Resume Service"
```

**Step 6: Monitor for 24 Hours** (see Post-Recovery Checklist in DISASTER_RECOVERY.md)

### Restore Procedure 4: Partial Restore (Advanced)

**When to use**: Restore specific tables without dropping entire database

**Step 1: Download and Decompress Backup**

```bash
# Download latest backup
python scripts/restore_supabase.py --latest --dry-run
# Note the backup file name, then:

# Download manually
python -c "
from scripts.restore_supabase import SupabaseRestore
restore = SupabaseRestore(dry_run=False)
restore.download_backup('supabase/supabase_backup_20250115_020015.sql.gz')
restore.decompress_backup('backups/restore/supabase_backup_20250115_020015.sql.gz')
"
```

**Step 2: Extract Specific Table**

```bash
# Extract specific table from SQL dump
grep -A 10000 "CREATE TABLE documents_v2" \
  backups/restore/supabase_backup_20250115_020015.sql > documents_only.sql

# Or use pg_restore with --table flag (if dump is in custom format)
pg_restore --table=documents_v2 \
  -h $SUPABASE_DB_HOST \
  -U $SUPABASE_DB_USER \
  -d $SUPABASE_DB_NAME \
  backups/restore/supabase_backup_20250115_020015.sql
```

**Step 3: Apply to Database**

```bash
# Restore specific table
psql -h $SUPABASE_DB_HOST \
  -U $SUPABASE_DB_USER \
  -d $SUPABASE_DB_NAME \
  -f documents_only.sql
```

**Note**: Partial restores require SQL expertise. Consult DBA if needed.

---

## Verification Steps

### After Backup Verification

**1. Verify Backup File Exists**

```bash
python scripts/restore_supabase.py --list
# Check latest backup is present and timestamp is correct
```

**2. Check Backup Size**

```bash
# Backup should be > 10 MB (for production database)
# Compressed size typically 30-40% of original
```

**3. Verify MD5 Checksum**

```bash
# Check backup.log for MD5 hash
grep "MD5 checksum" logs/backup.log | tail -1
```

**4. Test Restore (Dry Run)**

```bash
python scripts/restore_supabase.py --latest --dry-run
# Should complete without errors
```

### After Restore Verification

**1. Verify Database Connection**

```bash
psql -h $SUPABASE_DB_HOST -U $SUPABASE_DB_USER -d $SUPABASE_DB_NAME -c "SELECT version();"
# Should return PostgreSQL version
```

**2. Check Table Counts**

```bash
psql -h $SUPABASE_DB_HOST -U $SUPABASE_DB_USER -d $SUPABASE_DB_NAME -c "
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
  n_live_tup AS row_count
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 20;
"
```

**Expected Output:**
```
 schemaname |       tablename        |  size   | row_count
------------+------------------------+---------+-----------
 public     | documents_v2           | 234 MB  | 12345
 public     | tabular_document_rows  | 123 MB  | 98765
 public     | knowledge_entities     | 89 MB   | 45678
 ...
```

**3. Verify Recent Data**

```bash
# Check most recent document
psql -h $SUPABASE_DB_HOST -U $SUPABASE_DB_USER -d $SUPABASE_DB_NAME -c "
SELECT id, title, created_at
FROM documents_v2
ORDER BY created_at DESC
LIMIT 5;
"
```

**4. Test Application Functionality**

```bash
# Check API health
curl https://jb-empire-api.onrender.com/health

# Expected response:
# {"status": "healthy", "database": "connected", "timestamp": "..."}
```

**5. Test Query Functionality**

```bash
# Test vector search (via API or psql)
curl -X POST https://jb-empire-api.onrender.com/api/query/simple \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "limit": 5}'

# Should return search results
```

**6. Check User Sessions**

```bash
# Verify user sessions are intact
psql -h $SUPABASE_DB_HOST -U $SUPABASE_DB_USER -d $SUPABASE_DB_NAME -c "
SELECT COUNT(*) AS active_sessions
FROM admin_sessions
WHERE expires_at > NOW();
"
```

**7. Review Audit Logs**

```bash
# Check audit log for restore event
psql -h $SUPABASE_DB_HOST -U $SUPABASE_DB_USER -d $SUPABASE_DB_NAME -c "
SELECT event_type, created_at, metadata
FROM audit_logs
WHERE event_type = 'database_restore'
ORDER BY created_at DESC
LIMIT 1;
"
```

---

## Troubleshooting

### Problem: Backup Script Fails with "Missing Environment Variables"

**Error Message:**
```
ValueError: Missing required environment variables: SUPABASE_DB_HOST, B2_APPLICATION_KEY_ID
```

**Solution:**
1. Verify `.env` file exists in project root
2. Check `.env` contains required variables:
   ```bash
   grep -E "SUPABASE_DB_HOST|B2_APPLICATION_KEY_ID" .env
   ```
3. Load environment variables:
   ```bash
   export $(cat .env | xargs)
   ```
4. Retry backup/restore

### Problem: "pg_dump: command not found"

**Error Message:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'pg_dump'
```

**Solution:**
```bash
# macOS
brew install postgresql

# Ubuntu/Debian
sudo apt-get install postgresql-client

# Verify installation
pg_dump --version
```

### Problem: "Permission denied" when connecting to Supabase

**Error Message:**
```
psql: error: connection to server at "db.xxxxx.supabase.co" failed: FATAL: password authentication failed
```

**Solution:**
1. Verify password in `.env` file
2. Check Supabase dashboard for correct credentials
3. Test connection manually:
   ```bash
   psql -h $SUPABASE_DB_HOST -U $SUPABASE_DB_USER -d $SUPABASE_DB_NAME
   ```
4. Update `.env` with correct password
5. Retry backup/restore

### Problem: "Backup file is empty or missing"

**Error Message:**
```
Dump file is empty or missing
```

**Causes:**
- Disk space full
- Permission issues
- pg_dump timeout

**Solution:**
1. Check disk space:
   ```bash
   df -h
   ```
2. Check permissions on `backups/` directory:
   ```bash
   ls -la backups/
   chmod 755 backups/temp/
   ```
3. Increase pg_dump timeout (edit `scripts/backup_supabase.py`):
   ```python
   timeout=7200  # 2 hours instead of 1
   ```
4. Retry backup

### Problem: "B2 upload failed"

**Error Message:**
```
Failed to upload to B2: [error details]
```

**Common Causes:**
- Invalid B2 credentials
- Network connectivity issues
- B2 bucket doesn't exist
- Insufficient B2 storage

**Solution:**
1. Verify B2 credentials:
   ```bash
   # Check .env file
   grep B2_ .env
   ```
2. Test B2 connection:
   ```bash
   python scripts/restore_supabase.py --list
   # Should list existing backups
   ```
3. Check B2 dashboard:
   - Login to https://secure.backblaze.com
   - Verify `empire-backups` bucket exists
   - Check storage limits
4. Retry upload

### Problem: Restore Times Out After 2 Hours

**Error Message:**
```
subprocess.TimeoutExpired: Restore timed out after 2 hours
```

**Solution:**
1. Check database size:
   ```bash
   psql -h $SUPABASE_DB_HOST -U $SUPABASE_DB_USER -d $SUPABASE_DB_NAME -c "
   SELECT pg_size_pretty(pg_database_size('postgres'));
   "
   ```
2. If database is very large (> 10 GB), increase timeout in `scripts/restore_supabase.py`:
   ```python
   timeout=14400  # 4 hours instead of 2
   ```
3. Consider partial restore of specific tables instead

### Problem: "Backup exists but download fails"

**Error Message:**
```
Failed to download backup: [error details]
```

**Solution:**
1. Check network connectivity
2. Verify B2 credentials are still valid
3. Try downloading directly from B2 dashboard
4. Check B2 service status: https://www.backblaze.com/status.html

### Problem: Restore Completes but Data is Missing

**Symptoms:**
- Restore completes successfully
- Some tables are empty or missing rows
- Application throws errors about missing data

**Solution:**
1. Check restore logs for warnings:
   ```bash
   cat logs/restore.log | grep -i "error\|warning"
   ```
2. Verify backup file integrity:
   ```bash
   # Download and decompress manually
   python -c "from scripts.restore_supabase import SupabaseRestore; r = SupabaseRestore(); r.download_backup('...');"

   # Check SQL file
   head -100 backups/restore/*.sql
   tail -100 backups/restore/*.sql
   ```
3. Restore from an earlier backup
4. Contact Supabase support if corruption is suspected

---

## Emergency Scenarios

### Scenario 1: Database Corruption Detected

**Symptoms:**
- Query errors
- Null values where data should exist
- Foreign key constraint violations

**Immediate Actions:**
1. **DO NOT create a backup** (will backup corrupted data)
2. Stop all services immediately
3. Identify latest known-good backup:
   ```bash
   python scripts/restore_supabase.py --list
   ```
4. Restore from backup BEFORE corruption occurred
5. Investigate root cause (check audit logs, application logs)

### Scenario 2: Accidental Data Deletion

**Symptoms:**
- User reports missing data
- Recent DELETE operations in audit logs

**Immediate Actions:**
1. Create immediate backup (captures current state):
   ```bash
   python scripts/backup_supabase.py
   ```
2. Identify backup from BEFORE deletion:
   ```bash
   python scripts/restore_supabase.py --list
   # Choose backup with timestamp before deletion
   ```
3. If full restore is too disruptive, consider partial restore:
   - Download backup
   - Extract specific table/rows
   - Restore only missing data
4. Update audit logs to record recovery

### Scenario 3: Complete Database Loss

**Symptoms:**
- Supabase project deleted
- Database completely unavailable
- All data gone

**Recovery Steps:**
1. Create new Supabase project
2. Update `.env` with new connection details
3. Restore from latest backup:
   ```bash
   python scripts/restore_supabase.py --latest --drop-existing
   ```
4. Update all services with new Supabase URL:
   - Render environment variables
   - Local `.env` files
   - Application configs
5. Restart all services
6. Verify data integrity

### Scenario 4: Backup System Failure

**Symptoms:**
- Daily backups haven't run in 3+ days
- GitHub Actions workflow failing
- No recent backups in B2

**Immediate Actions:**
1. Create manual backup immediately:
   ```bash
   python scripts/backup_supabase.py
   ```
2. Investigate GitHub Actions failure:
   - Check workflow logs
   - Verify secrets are configured
   - Check B2 credentials
3. Test backup script locally
4. Fix root cause (expired credentials, workflow config, etc.)
5. Resume automated backups
6. Monitor for 72 hours

### Scenario 5: Disaster Recovery Drill

**Purpose**: Verify restore procedures work

**Steps:**
1. Schedule maintenance window (low-traffic period)
2. Notify team members
3. Create fresh backup:
   ```bash
   python scripts/backup_supabase.py
   ```
4. Perform full restore to TEST database:
   ```bash
   # Update .env to point to test database
   export SUPABASE_DB_NAME=test_restore_db

   # Restore
   python scripts/restore_supabase.py --latest --drop-existing
   ```
5. Verify restored data
6. Document time taken, issues encountered
7. Update procedures based on findings

---

## Appendix A: Backup File Naming Convention

**Format**: `supabase_backup_YYYYMMDD_HHMMSS.sql.gz`

**Examples**:
- `supabase_backup_20250115_020015.sql.gz` = January 15, 2025 at 02:00:15 UTC
- `supabase_backup_20250114_153022.sql.gz` = January 14, 2025 at 15:30:22 UTC

**Components**:
- `supabase_backup_` = Prefix (consistent)
- `YYYYMMDD` = Date (20250115 = January 15, 2025)
- `HHMMSS` = Time in UTC (020015 = 2:00:15 AM UTC)
- `.sql.gz` = Compressed SQL dump

**Sorting**: Files sort chronologically by name (newest first when sorted descending)

---

## Appendix B: Backup Metadata

**Each backup includes metadata stored in B2**:
- `backup_date`: ISO timestamp of backup creation
- `database`: Database name (e.g., "postgres")
- `md5`: MD5 checksum of compressed file

**Access metadata**:
```python
from b2sdk.v2 import B2Api, InMemoryAccountInfo

info = InMemoryAccountInfo()
b2_api = B2Api(info)
b2_api.authorize_account("production", key_id, app_key)
bucket = b2_api.get_bucket_by_name("empire-backups")

for file_version, _ in bucket.ls(folder_to_list="supabase/"):
    print(f"File: {file_version.file_name}")
    print(f"Metadata: {file_version.file_info}")
```

---

## Appendix C: Retention Policy Details

**Automatic Cleanup** (runs after each backup):
- Calculates cutoff date: `current_date - 30 days`
- Lists all backups in B2 `supabase/` folder
- Deletes backups older than cutoff
- Logs number of deleted backups

**Manual Cleanup** (if needed):
```python
from scripts.backup_supabase import SupabaseBackup

backup = SupabaseBackup(dry_run=False)
backup.cleanup_old_backups()
```

**Override Retention** (temporary):
```bash
# Keep backups for 60 days instead of 30
export BACKUP_RETENTION_DAYS=60
python scripts/backup_supabase.py
```

---

## Appendix D: Backup Storage Costs

**Backblaze B2 Pricing** (as of 2025):
- **Storage**: $0.005/GB/month ($5 per TB/month)
- **Download**: $0.01/GB (first 3x storage is free)
- **Upload**: Free
- **API calls**: Free (10,000/day included)

**Estimated Costs for Empire**:
- Average backup size: 150 MB (compressed)
- Backups stored: 30 days
- Total storage: 150 MB × 30 = 4.5 GB
- **Monthly cost**: 4.5 GB × $0.005 = **$0.02/month** ($0.25/year)

**Cost Optimization**:
- Compression reduces costs by 60-70%
- 30-day retention balances cost vs. recovery options
- Free downloads (3x storage = 13.5 GB/month free)

---

## Appendix E: Contact Information

**For Backup/Restore Issues**:
- **System Owner**: [Name] - [Email/Phone]
- **Database Admin**: [Name] - [Email/Phone]
- **DevOps Lead**: [Name] - [Email/Phone]

**External Support**:
- **Supabase Support**: support@supabase.com (Pro plan)
- **Backblaze B2 Support**: support@backblaze.com
- **GitHub Actions Support**: GitHub Community Forums

**Escalation Path**:
1. On-call engineer (respond within 15 min)
2. System owner (if unavailable after 30 min)
3. External vendor support (for critical issues)

---

## Document Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-15 | Operations Team | Initial operational runbook |

---

**Next Review Date**: 2025-02-15
