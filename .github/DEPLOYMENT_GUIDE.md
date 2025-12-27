# Quick Deployment Guide - Empire v7.3

## Prerequisites

Before deploying, ensure these secrets are configured in GitHub repository settings:

**Settings → Secrets and variables → Actions → New repository secret**

### Required Secrets

```
SUPABASE_URL
SUPABASE_SERVICE_KEY
SUPABASE_DB_HOST
SUPABASE_DB_NAME
SUPABASE_DB_USER
SUPABASE_DB_PASSWORD
SUPABASE_DB_PORT

RENDER_API_KEY
RENDER_SERVICE_ID
RENDER_CELERY_SERVICE_ID

REDIS_URL
ANTHROPIC_API_KEY
```

---

## Deployment Workflows

### 1. Standard Deployment (Push to main)

```bash
# Merge PR to main branch
git checkout main
git pull origin main
git push origin main

# GitHub Actions automatically:
# - Runs tests
# - Lints code
# - Deploys to Render
# - Runs migrations
# - Runs smoke tests
```

### 2. Manual Deployment

```
1. Go to GitHub Actions tab
2. Select "CI/CD Pipeline"
3. Click "Run workflow"
4. Select branch: main
5. Click "Run workflow" button
```

### 3. Emergency Rollback

**Via Render Dashboard:**
```
1. Go to https://dashboard.render.com
2. Select "Empire API" service
3. Click "Rollback" on previous deployment
```

**Via GitHub:**
```bash
# Revert last commit
git revert HEAD
git push origin main
# CI/CD will automatically deploy the reverted version
```

---

## Pre-Deployment Checklist

- [ ] All tests passing locally (`pytest`)
- [ ] Code linted (`flake8 app/`)
- [ ] Migrations tested (`python scripts/run_migrations.py --dry-run`)
- [ ] Environment variables updated (if needed)
- [ ] Documentation updated (if needed)
- [ ] PR approved and reviewed

---

## Post-Deployment Verification

```bash
# 1. Check health endpoint
curl https://jb-empire-api.onrender.com/health

# 2. Check API docs
curl https://jb-empire-api.onrender.com/docs

# 3. Check Render logs
# Go to Render Dashboard → Empire API → Logs

# 4. Run smoke tests locally
pytest tests/ -m smoke --api-url=https://jb-empire-api.onrender.com
```

---

## Monitoring

**GitHub Actions:** https://github.com/YOUR_USERNAME/Empire/actions
**Render Dashboard:** https://dashboard.render.com/web/srv-d44o2dq4d50c73elgupg
**Grafana:** http://localhost:3001 (local monitoring)
**Prometheus:** http://localhost:9090 (local metrics)

---

## Common Issues

### Issue: Tests pass locally but fail in CI

**Solution:**
- Check Python version matches (3.11)
- Verify all secrets are set in GitHub
- Check GitHub Actions logs for specific error

### Issue: Deployment succeeds but health check fails

**Solution:**
- Check Render service logs
- Verify environment variables on Render
- Ensure migrations completed successfully
- Check Redis connectivity

### Issue: Migration fails

**Solution:**
- Check migration SQL syntax
- Verify database permissions
- Test migration locally first
- Check `schema_migrations` table for errors

---

## Support

For issues, create a GitHub issue with:
- Description of problem
- GitHub Actions run link
- Render service logs
- Steps to reproduce

---

**Last Updated**: January 24, 2025
**Pipeline Version**: v1.0 (Task 6)
