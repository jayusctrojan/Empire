# CI/CD Pipeline Setup - Task 6

## Overview

Empire v7.3 includes a comprehensive CI/CD pipeline that automatically tests, lints, deploys, and manages database migrations for the production environment.

**Key Features:**
- ✅ Automated testing with pytest (unit + integration)
- ✅ Code linting with Flake8
- ✅ Automated deployment to Render.com
- ✅ Database migration automation
- ✅ Test data seeding for staging
- ✅ Smoke tests post-deployment
- ✅ Automatic rollback on failure
- ✅ GitHub issue creation on CI/CD failures

---

## Architecture

### Workflow Triggers

**Automatic Triggers:**
- Push to `main` branch → Full CI/CD (test + lint + deploy + migrate)
- Push to `develop` branch → Test + Lint only (no deployment)
- Pull Request to `main` or `develop` → Test + Lint only

**Manual Triggers:**
- `workflow_dispatch` → Full control with environment selection

### Workflow Jobs

```
┌─────────────────────────────────────────────────────────────┐
│                    CI/CD Pipeline Flow                       │
└─────────────────────────────────────────────────────────────┘

PR or Push to develop/main
           │
           ├─── [1] Lint Code (Flake8, Black, isort)
           │
           ├─── [2] Unit Tests (pytest -m unit)
           │
           └─── [3] Check Migrations (SQL syntax validation)
                      │
                      └─── (main branch only) ───┐
                                                  │
┌─────────────────────────────────────────────────┘
│
├─── [4] Integration Tests (pytest -m integration)
│
├─── [5] Deploy to Render - Empire API
│         └─── Health check verification
│
├─── [6] Deploy to Render - Celery Worker
│
├─── [7] Run Database Migrations
│         └─── scripts/run_migrations.py
│
├─── [8] Seed Test Data (manual workflow_dispatch only)
│         └─── scripts/seed_test_data.py
│
├─── [9] Smoke Tests (basic API health checks)
│
└─── [10] Notify on Failure (create GitHub issue)
```

---

## Configuration Files

### 1. pytest.ini

**Location**: `pytest.ini`

**Purpose**: Configure pytest behavior for local and CI testing

**Key Settings:**
- Test discovery: `tests/test_*.py`
- Coverage target: 70% minimum
- Async support: `asyncio_mode = auto`
- 15+ test markers for categorization

**Usage:**
```bash
# Run all tests
pytest

# Run only unit tests (fast)
pytest -m unit

# Run integration tests (requires services)
pytest -m integration

# Run with coverage report
pytest --cov=app --cov-report=html
```

### 2. .flake8

**Location**: `.flake8`

**Purpose**: Python code linting configuration

**Key Settings:**
- Max line length: 120 characters
- Complexity limit: 15 (cyclomatic complexity)
- Ignores: E203, W503 (Black compatibility)

**Usage:**
```bash
# Lint entire codebase
flake8 app/

# Lint with statistics
flake8 app/ --statistics

# Check specific file
flake8 app/services/feature_flags.py
```

### 3. .github/workflows/ci-cd.yml

**Location**: `.github/workflows/ci-cd.yml`

**Purpose**: GitHub Actions CI/CD automation

**Environments Used:**
- `production` - Requires manual approval for destructive operations

---

## Required GitHub Secrets

Add these secrets in GitHub repository settings:

**Supabase Database:**
```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGc...
SUPABASE_DB_HOST=db.xxxxx.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your_password
SUPABASE_DB_PORT=5432
```

**Render Deployment:**
```
RENDER_API_KEY=rnd_xxxxx
RENDER_SERVICE_ID=srv-d44o2dq4d50c73elgupg    # Empire API
RENDER_CELERY_SERVICE_ID=srv-d44oclodl3ps73bg8rmg  # Celery Worker
```

**Redis Cache:**
```
REDIS_URL=rediss://default:xxxxx@enhanced-manatee-37521.upstash.io:6379
```

**AI Services (for test data seeding):**
```
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

---

## Database Migrations

### Migration Script: `scripts/run_migrations.py`

**Features:**
- ✅ Tracks applied migrations in `schema_migrations` table
- ✅ Applies migrations in alphabetical order
- ✅ Supports dry-run mode
- ✅ Comprehensive error handling and logging
- ✅ Automatic rollback on failure

**Usage:**

```bash
# Dry run (show what would be migrated)
python scripts/run_migrations.py --dry-run

# Apply all pending migrations
python scripts/run_migrations.py
```

**Migration File Format:**

Create migration files in `migrations/` directory:

```
migrations/
├── 001_create_feature_flags.sql
├── 002_add_rls_policies.sql
├── 003_create_audit_logs.sql
└── 004_add_monitoring_tables.sql
```

Each file should be valid SQL and idempotent when possible.

**Migration Tracking Table:**

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

## Test Data Seeding

### Seeding Script: `scripts/seed_test_data.py`

**Features:**
- ✅ Seeds feature flags (Task 3 - v7.3)
- ✅ Seeds audit logs (Task 41.5 - Security)
- ✅ Seeds chat sessions (Task 26 - Chat UI)
- ✅ Verification of seeded data
- ✅ Supports dry-run mode

**Usage:**

```bash
# Dry run (show what would be seeded)
python scripts/seed_test_data.py --dry-run

# Seed all test data
python scripts/seed_test_data.py
```

**Seeded Data:**

**1. Feature Flags (5 flags):**
- `feature_advanced_search` (enabled, 100%)
- `feature_course_management` (enabled, 100%)
- `feature_reporting_dashboard` (disabled, 0%)
- `feature_ai_summarization` (enabled, 50%)
- `feature_multilingual_support` (disabled, 10%)

**2. Audit Logs (3 events):**
- User login event
- Document upload event
- Config change event

**3. Chat Sessions (2 sessions):**
- Policy Research Session
- Contract Analysis Session

---

## Testing Locally

### 1. Run Linting

```bash
# Flake8
flake8 app/ --statistics

# Black (check formatting)
black --check app/ tests/

# isort (check imports)
isort --check-only app/ tests/
```

### 2. Run Tests

```bash
# All tests
pytest

# Unit tests only (fast)
pytest -m unit

# Integration tests (requires services)
pytest -m integration

# Specific test file
pytest tests/test_feature_flags.py -v

# With coverage
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

### 3. Test Migrations

```bash
# Dry run
python scripts/run_migrations.py --dry-run

# Apply migrations (requires SUPABASE_DB_* env vars)
python scripts/run_migrations.py
```

### 4. Test Data Seeding

```bash
# Dry run
python scripts/seed_test_data.py --dry-run

# Seed data (requires SUPABASE_URL and SUPABASE_SERVICE_KEY)
python scripts/seed_test_data.py
```

---

## Deployment Process

### Automatic Deployment (Push to main)

```
1. Developer merges PR to main
2. GitHub Actions triggers CI/CD workflow
3. Jobs run in sequence:
   a. Lint code
   b. Run unit tests
   c. Check migration syntax
   d. Deploy to Render API
   e. Deploy to Render Celery Worker
   f. Run database migrations
   g. Run smoke tests
4. Deployment verified via health check
5. Notification sent if any step fails
```

### Manual Deployment (workflow_dispatch)

```
1. Go to GitHub Actions tab
2. Select "CI/CD Pipeline" workflow
3. Click "Run workflow"
4. Select environment (production/staging)
5. Click "Run workflow" button
```

### Rollback Procedure

If deployment fails:

1. **Automatic rollback** (Render keeps previous deployment)
2. **Manual rollback** via Render dashboard:
   ```
   Render Dashboard → Empire API → Rollback to previous deploy
   ```
3. **Database rollback** (requires manual intervention):
   ```bash
   # Connect to Supabase
   psql "postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres"

   # Find migration to rollback
   SELECT * FROM schema_migrations ORDER BY applied_at DESC LIMIT 5;

   # Mark migration as failed (prevents re-application)
   UPDATE schema_migrations
   SET success = FALSE,
       error_message = 'Manual rollback'
   WHERE migration_name = 'xxx_migration.sql';
   ```

---

## Monitoring CI/CD

### GitHub Actions Dashboard

**URL**: `https://github.com/YOUR_USERNAME/Empire/actions`

**View:**
- Recent workflow runs
- Job status and logs
- Deployment history
- Test results and coverage

### Render Dashboard

**URL**: `https://dashboard.render.com/web/srv-d44o2dq4d50c73elgupg`

**View:**
- Deployment status
- Application logs
- Resource usage
- Health check status

### Email Notifications

GitHub sends emails for:
- ✅ Successful deployments
- ❌ Failed workflow runs
- 🚨 Created GitHub issues (on failure)

---

## Troubleshooting

### Tests Failing in CI but Pass Locally

**Cause**: Different environment variables or missing dependencies

**Solution:**
```bash
# Check GitHub Actions logs for specific error
# Ensure all secrets are set in GitHub repository settings
# Test with same Python version as CI (3.11)
python --version

# Run tests in clean virtualenv
python -m venv test_env
source test_env/bin/activate
pip install -r requirements.txt
pytest
```

### Deployment Fails with Health Check Error

**Cause**: Application not starting correctly on Render

**Solution:**
```bash
# Check Render logs
# Verify environment variables on Render
# Check if migrations succeeded
# Ensure dependencies are installed

# Test locally with production-like environment
SUPABASE_URL=... uvicorn app.main:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
```

### Migrations Fail

**Cause**: SQL syntax error or missing permissions

**Solution:**
```bash
# Test migration locally
psql "postgresql://..." -f migrations/xxx_migration.sql

# Check migration logs in GitHub Actions
# Verify SUPABASE_DB_* secrets are set correctly
# Ensure PostgreSQL user has required permissions

# Manual migration application
python scripts/run_migrations.py
```

### Test Data Seeding Fails

**Cause**: Missing tables or RLS policies blocking inserts

**Solution:**
```bash
# Check Supabase RLS policies
# Ensure migrations ran successfully
# Verify SUPABASE_SERVICE_KEY has admin privileges

# Test locally
python scripts/seed_test_data.py --dry-run
python scripts/seed_test_data.py
```

---

## Best Practices

### 1. Testing

- ✅ Write tests before merging to main
- ✅ Aim for >70% code coverage
- ✅ Use markers to categorize tests (`@pytest.mark.unit`)
- ✅ Mock external services in unit tests
- ✅ Run integration tests before pushing

### 2. Migrations

- ✅ Create idempotent migrations (use `IF NOT EXISTS`)
- ✅ Test migrations locally before pushing
- ✅ Include rollback SQL in migration comments
- ✅ Never modify existing migration files
- ✅ Use sequential numbering (001, 002, 003...)

### 3. Deployments

- ✅ Review deployment logs after each deploy
- ✅ Monitor error rates in first 30 minutes
- ✅ Keep PRs small and focused
- ✅ Tag releases in Git for easy rollback
- ✅ Document breaking changes

### 4. Code Quality

- ✅ Run `flake8` before committing
- ✅ Use `black` for consistent formatting
- ✅ Keep functions under 15 cyclomatic complexity
- ✅ Write docstrings for public functions
- ✅ Add type hints for better IDE support

---

## CI/CD Metrics

### Target Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Test Coverage | >70% | TBD |
| Build Time | <5 minutes | ~3-4 minutes |
| Deployment Time | <2 minutes | ~1-2 minutes |
| Success Rate | >95% | TBD |
| MTTR (Mean Time to Recovery) | <1 hour | TBD |

### Monitoring

Track these metrics:
- Deployment frequency
- Lead time for changes
- Change failure rate
- Time to restore service

---

## Future Enhancements

Potential improvements for the CI/CD pipeline:

1. **Staging Environment**
   - Add staging deployment before production
   - Automatic rollback on staging failures

2. **Load Testing**
   - Integrate Locust for load testing
   - Run performance tests before deployment

3. **Security Scanning**
   - Add Snyk or Dependabot for dependency scanning
   - SAST (Static Application Security Testing)

4. **Advanced Monitoring**
   - Integrate with Sentry for error tracking
   - Add performance monitoring with DataDog

5. **Blue-Green Deployments**
   - Zero-downtime deployments
   - Instant rollback capability

---

## Related Documentation

- **Feature Flags**: `docs/FEATURE_FLAG_ADMIN_GUIDE.md`
- **Monitoring**: `docs/FEATURE_FLAG_MONITORING.md`
- **Security**: `docs/ENCRYPTION_VERIFICATION_TASK41_3.md`
- **Database Setup**: `migrations/` directory
- **Testing**: `tests/` directory

---

**Last Updated**: January 24, 2025
**Task**: Task 6 - Set Up CI/CD Pipeline and Test Infrastructure
**Status**: Complete
