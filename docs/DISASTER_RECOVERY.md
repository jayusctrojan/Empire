# Empire v7.3 - Disaster Recovery Plan

**Document Version:** 1.0
**Last Updated:** 2025-01-15
**Owner:** Engineering Team
**Review Frequency:** Quarterly

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Recovery Objectives](#recovery-objectives)
3. [Disaster Scenarios](#disaster-scenarios)
4. [Recovery Procedures](#recovery-procedures)
5. [Critical Contacts](#critical-contacts)
6. [Testing & Drills](#testing--drills)
7. [Post-Recovery Checklist](#post-recovery-checklist)

---

## Executive Summary

This document outlines the disaster recovery (DR) procedures for Empire v7.3, a production AI file processing system. The plan covers:

- **System Components**: FastAPI (Render), Celery Workers (Render), Supabase PostgreSQL, Neo4j (Mac Studio), Redis (Upstash)
- **Primary Risks**: Service outages, data corruption, regional failures, credential compromise
- **Recovery Strategy**: Automated backups, health monitoring, documented restoration procedures

**Key Principle**: All critical data is backed up daily to Backblaze B2 with 30-day retention.

---

## Recovery Objectives

### RTO (Recovery Time Objective)

| Component | Target RTO | Notes |
|-----------|-----------|-------|
| FastAPI Services (Render) | < 15 minutes | Auto-restart on failure |
| Celery Workers (Render) | < 15 minutes | Auto-restart on failure |
| Supabase Database | < 2 hours | Manual restore from B2 backup |
| Neo4j Database | < 4 hours | Manual rebuild + restore |
| Redis Cache | < 5 minutes | Upstash auto-recovery |

### RPO (Recovery Point Objective)

| Data Type | Target RPO | Backup Frequency |
|-----------|-----------|------------------|
| Supabase PostgreSQL | 24 hours | Daily at 2:00 AM UTC |
| Neo4j Graph Data | 24 hours | Manual export recommended |
| Uploaded Documents (B2) | 0 (real-time) | Direct storage to B2 |
| Application Code | 0 (git) | GitHub main branch |

---

## Disaster Scenarios

### Scenario 1: Render Service Outage (FastAPI/Celery)

**Symptoms:**
- `/health` endpoint returns 503 or times out
- Users report API unavailable
- Render dashboard shows service crashed

**Automatic Recovery:**
- Render automatically restarts services on failure
- Health check: `/health/ready` triggers restart if failing

**Manual Recovery (if auto-restart fails):**
1. Check Render logs: `https://dashboard.render.com/web/srv-d44o2dq4d50c73elgupg`
2. Verify environment variables are correct
3. Check for OOM (out of memory) issues - upgrade plan if needed
4. Manual restart via Render dashboard or Render MCP
5. Verify recovery with `curl https://jb-empire-api.onrender.com/health`

**Prevention:**
- Monitor Render service health daily
- Set up alerting for failed health checks
- Review logs for recurring errors

---

### Scenario 2: Supabase Database Corruption/Loss

**Symptoms:**
- Database queries failing with connection errors
- Data inconsistencies detected
- Supabase dashboard shows database unavailable

**Recovery Procedure:**

1. **Assess Damage**
   ```bash
   # Check Supabase status
   curl https://[project-id].supabase.co/rest/v1/
   ```

2. **List Available Backups**
   ```bash
   cd /path/to/Empire
   python scripts/restore_supabase.py --list
   ```

3. **Restore from Latest Backup**
   ```bash
   # WARNING: This will overwrite current data
   python scripts/restore_supabase.py --latest --drop-existing
   ```

4. **Verify Restoration**
   ```bash
   # Check table counts
   # Connect via Supabase dashboard or psql
   psql -h [host] -U postgres -d postgres -c "\dt"
   ```

5. **Restart Services**
   - Restart FastAPI and Celery services on Render
   - Verify health checks pass

**Recovery Time:** ~2 hours (download + restore + verify)

---

### Scenario 3: Complete Regional Failure (Render Oregon)

**Symptoms:**
- All Render services unreachable
- Render status page shows regional outage

**Recovery Procedure:**

1. **Create New Render Services in Different Region**
   ```bash
   # Use Render MCP or dashboard to deploy to Virginia/Frankfurt
   ```

2. **Update DNS/Environment Variables**
   - Point to new service URLs
   - Update frontend environment variables

3. **Restore Database**
   - Follow Scenario 2 recovery procedure
   - Point new services to restored database

4. **Verify Full System**
   - Test all critical endpoints
   - Verify document upload/retrieval
   - Check CrewAI and LlamaIndex integration

**Recovery Time:** ~4-6 hours

---

### Scenario 4: Credentials Compromise

**Symptoms:**
- Unauthorized access detected
- Suspicious API activity
- Security alert from monitoring

**Immediate Actions:**

1. **Revoke Compromised Credentials**
   - Rotate Supabase API keys (Project Settings → API)
   - Rotate B2 application keys
   - Rotate any exposed API keys (Anthropic, OpenAI, etc.)

2. **Audit Access Logs**
   ```bash
   # Check audit logs
   curl https://jb-empire-api.onrender.com/api/audit/events/recent
   ```

3. **Force User Re-authentication**
   - Delete all active sessions from `admin_sessions` table
   - Invalidate all API keys

4. **Update All Services**
   - Update environment variables on Render
   - Restart all services to use new credentials

5. **Investigate & Report**
   - Review audit logs for extent of compromise
   - Document incident timeline
   - Implement additional security measures

**Recovery Time:** ~2-4 hours

---

### Scenario 5: Data Corruption (Partial)

**Symptoms:**
- Specific tables/documents corrupted
- Queries return unexpected results
- Vector search failures

**Recovery Procedure:**

1. **Identify Corrupted Data**
   ```sql
   -- Check for null embeddings
   SELECT COUNT(*) FROM documents_v2 WHERE embedding IS NULL;

   -- Check for orphaned records
   SELECT COUNT(*) FROM tabular_document_rows
   WHERE document_id NOT IN (SELECT id FROM documents_v2);
   ```

2. **Restore Specific Tables** (if possible)
   ```bash
   # Extract specific table from backup
   python scripts/restore_supabase.py --latest

   # Then manually extract and restore specific tables
   # using psql or Supabase SQL editor
   ```

3. **Rebuild Affected Indexes**
   ```sql
   -- Rebuild vector indexes
   REINDEX INDEX documents_embedding_idx;
   ```

4. **Verify Data Integrity**
   - Run data validation queries
   - Test affected functionality
   - Check query performance

**Recovery Time:** ~1-3 hours (depends on extent)

---

## Recovery Procedures

### Quick Reference: Service Restarts

**Restart FastAPI Service:**
```bash
# Via Render Dashboard
https://dashboard.render.com/web/srv-d44o2dq4d50c73elgupg

# Or via Render MCP (if available)
# Use Render MCP to restart service
```

**Restart Celery Worker:**
```bash
# Via Render Dashboard
https://dashboard.render.com/worker/srv-d44oclodl3ps73bg8rmg
```

**Clear Redis Cache (if needed):**
```bash
# Connect to Upstash Redis
redis-cli -h enhanced-manatee-37521.upstash.io -p 6379 --tls \
  -a [password] FLUSHDB
```

### Database Backup Verification

**Test Backup Integrity:**
```bash
# Download and verify latest backup
python scripts/restore_supabase.py --latest --dry-run

# Check backup file size and timestamp
# Should be > 10MB for production database
```

**Manual Backup (Emergency):**
```bash
# Create immediate backup
python scripts/backup_supabase.py

# Verify upload to B2
# Check Backblaze B2 dashboard
```

---

## Critical Contacts

### Internal Team

| Role | Name | Contact | Availability |
|------|------|---------|--------------|
| System Owner | [Name] | [Email/Phone] | 24/7 |
| Database Admin | [Name] | [Email/Phone] | Business Hours |
| DevOps Lead | [Name] | [Email/Phone] | On-Call Rotation |

### External Services

| Service | Support Contact | SLA |
|---------|----------------|-----|
| Render | support@render.com | Standard Plan |
| Supabase | support@supabase.com | Pro Plan |
| Backblaze B2 | support@backblaze.com | Business Hours |
| Upstash Redis | support@upstash.com | Email Support |

### Escalation Path

1. **On-Call Engineer** (respond within 15 min)
2. **System Owner** (if unavailable after 30 min)
3. **External Support** (if critical, engage vendor support)

---

## Testing & Drills

### Quarterly DR Drills

**Objective:** Validate recovery procedures and team readiness

**Schedule:**
- Q1: Service restart drill
- Q2: Database restore drill
- Q3: Full regional failover drill
- Q4: Credentials rotation drill

**Drill Procedure:**

1. **Pre-Drill Planning**
   - Schedule during low-traffic period
   - Notify team members
   - Prepare test environment

2. **Execute Drill**
   - Follow specific scenario procedure
   - Time each step
   - Document any issues

3. **Post-Drill Review**
   - Measure actual RTO vs. target
   - Identify process improvements
   - Update documentation
   - Train team on changes

### Test Backup Restoration (Monthly)

```bash
# Restore to test database (not production)
export SUPABASE_DB_NAME=test_restore_db
python scripts/restore_supabase.py --latest --drop-existing

# Verify data integrity
# Run test queries
# Document any issues
```

---

## Post-Recovery Checklist

After executing any recovery procedure:

- [ ] **Verify System Health**
  - [ ] All services return 200 on `/health`
  - [ ] Database queries succeed
  - [ ] Background tasks processing
  - [ ] File uploads working

- [ ] **Check Data Integrity**
  - [ ] Run data validation queries
  - [ ] Verify recent documents accessible
  - [ ] Test vector search functionality
  - [ ] Confirm user sessions intact

- [ ] **Monitor for 24 Hours**
  - [ ] Watch error rates
  - [ ] Check performance metrics
  - [ ] Review audit logs for anomalies
  - [ ] Verify backup scheduled correctly

- [ ] **Document Incident**
  - [ ] Record timeline of events
  - [ ] Note root cause (if identified)
  - [ ] List actions taken
  - [ ] Identify preventive measures

- [ ] **Communicate Status**
  - [ ] Notify team of resolution
  - [ ] Update status page (if applicable)
  - [ ] Send post-mortem report
  - [ ] Schedule lessons-learned meeting

- [ ] **Implement Improvements**
  - [ ] Update DR procedures if needed
  - [ ] Add monitoring for identified gaps
  - [ ] Schedule follow-up tasks
  - [ ] Update this document

---

## Appendix A: Service URLs & Dashboards

### Production Services

| Service | URL | Dashboard |
|---------|-----|-----------|
| Empire API | https://jb-empire-api.onrender.com | https://dashboard.render.com/web/srv-d44o2dq4d50c73elgupg |
| Empire Chat UI | https://jb-empire-chat.onrender.com | https://dashboard.render.com/web/srv-d47ptdmr433s739ljolg |
| Celery Worker | N/A (background) | https://dashboard.render.com/worker/srv-d44oclodl3ps73bg8rmg |
| LlamaIndex | https://jb-llamaindex.onrender.com | https://dashboard.render.com/web/srv-d2nl1lre5dus73atm9u0 |
| CrewAI | https://jb-crewai.onrender.com | https://dashboard.render.com/web/srv-d2n0hh3uibrs73buafo0 |
| Supabase | [Project URL] | https://app.supabase.com |
| Backblaze B2 | N/A | https://secure.backblaze.com |
| Upstash Redis | N/A | https://console.upstash.com |

### Health Check Endpoints

- **API Health**: `GET https://jb-empire-api.onrender.com/health`
- **Detailed Health**: `GET https://jb-empire-api.onrender.com/health/detailed`
- **Readiness Probe**: `GET https://jb-empire-api.onrender.com/health/ready`
- **Liveness Probe**: `GET https://jb-empire-api.onrender.com/health/live`

---

## Appendix B: Environment Variables Checklist

Critical environment variables that must be restored:

**Render Services:**
- [ ] SUPABASE_URL
- [ ] SUPABASE_SERVICE_KEY
- [ ] ANTHROPIC_API_KEY
- [ ] B2_APPLICATION_KEY_ID
- [ ] B2_APPLICATION_KEY
- [ ] REDIS_URL (Upstash)
- [ ] NEO4J_URI
- [ ] NEO4J_PASSWORD

**GitHub Secrets (for backups):**
- [ ] SUPABASE_DB_HOST
- [ ] SUPABASE_DB_PASSWORD
- [ ] B2_APPLICATION_KEY_ID
- [ ] B2_APPLICATION_KEY

---

## Document Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-15 | Claude | Initial disaster recovery plan |

---

**Next Review Date:** 2025-04-15
