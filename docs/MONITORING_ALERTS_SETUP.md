# Empire v7.3 - Monitoring & Alerts Setup Guide

**Complete guide to setting up production monitoring with email notifications**

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start (5 Minutes)](#quick-start-5-minutes)
4. [Email Configuration](#email-configuration)
5. [Alert Rules Reference](#alert-rules-reference)
6. [Testing Alerts](#testing-alerts)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Configuration](#advanced-configuration)
9. [Maintenance](#maintenance)

---

## Overview

Empire v7.3 includes a comprehensive monitoring stack with automatic email alerts:

### Components

| Service | Purpose | Port | URL |
|---------|---------|------|-----|
| **Prometheus** | Metrics collection & alerting | 9090 | http://localhost:9090 |
| **Grafana** | Visualization dashboards | 3000 | http://localhost:3000 |
| **Alertmanager** | Alert routing & notifications | 9093 | http://localhost:9093 |
| **Node Exporter** | System metrics | 9100 | http://localhost:9100 |

### Alert Categories

- ✅ **API Health** - API downtime, high error rates, slow responses
- ✅ **Cache Performance** - Cache hit rates, Redis availability (Task 43.3)
- ✅ **Database** - Connection errors, slow queries
- ✅ **LangGraph Workflows** - Workflow failures, iteration limits (Task 46)
- ✅ **Security** - Authentication failures, rate limit violations
- ✅ **Celery Tasks** - Worker health, task backlog, failures
- ✅ **System Resources** - Memory usage, CPU usage
- ✅ **External Services** - Claude API errors, Arcade.dev tools
- ✅ **Business Metrics** - Query volume, costs

---

## Prerequisites

### Required

- Docker Desktop installed and running
- Empire v7.3 FastAPI app deployed (https://jb-empire-api.onrender.com)
- Gmail account for receiving alerts (jbajaj08@gmail.com)
- Gmail App Password (see setup below)

### Optional

- Slack webhook URL (for Slack notifications)
- PagerDuty API key (for on-call alerts)

---

## Quick Start (5 Minutes)

### Step 1: Create Gmail App Password (2 minutes)

**Why needed?** Gmail requires App Passwords for third-party applications to send emails.

1. Go to: https://myaccount.google.com/apppasswords
2. Sign in to your Gmail account (jbajaj08@gmail.com)
3. App name: `Empire Monitoring`
4. Click **Generate**
5. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)

### Step 2: Configure Environment (1 minute)

```bash
cd /path/to/Empire

# Add SMTP password to .env file
echo "SMTP_PASSWORD=abcd efgh ijkl mnop" >> .env
```

**Important:** Replace `abcd efgh ijkl mnop` with your actual App Password from Step 1.

### Step 3: Start Monitoring Stack (2 minutes)

```bash
./start-monitoring.sh
```

**Expected output:**
```
✅ Prometheus    → http://localhost:9090
✅ Grafana       → http://localhost:3000 (admin/empiregrafana123)
✅ Alertmanager  → http://localhost:9093
✅ Node Exporter → http://localhost:9100
```

### Step 4: Test Email Alerts (30 seconds)

```bash
./test-alert.sh
```

Check your email (jbajaj08@gmail.com) for a test alert within 5 minutes.

---

## Email Configuration

### Alertmanager Email Settings

Location: `monitoring/alertmanager.yml`

```yaml
global:
  smtp_from: 'empire-alerts@noreply.com'
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_auth_username: 'jbajaj08@gmail.com'
  smtp_auth_password: '${SMTP_PASSWORD}'
  smtp_require_tls: true
```

### Alert Severity Levels

| Severity | Notification Delay | Repeat Interval | Email Subject |
|----------|-------------------|-----------------|---------------|
| **Critical** | 10 seconds | 1 hour | 🚨 [CRITICAL] Empire Alert |
| **Warning** | 2 minutes | 12 hours | ⚠️ [WARNING] Empire Alert |
| **Info** | 5 minutes | 24 hours | ℹ️ [INFO] Empire Daily Digest |

### Email Recipients

**Current:** jbajaj08@gmail.com

**To add more recipients**, edit `monitoring/alertmanager.yml`:

```yaml
receivers:
  - name: 'email-critical'
    email_configs:
      - to: 'jbajaj08@gmail.com,team@example.com,oncall@example.com'
```

---

## Alert Rules Reference

### Critical Alerts

**1. APIDown**
- **Condition:** Empire API unreachable for 2+ minutes
- **Action:** Immediate notification → Check Render service
- **Runbook:** https://jb-empire-api.onrender.com

**2. APIHighErrorRate**
- **Condition:** >5% of requests return 5xx errors
- **Action:** Investigate error logs
- **Runbook:** `docker logs empire-api` or Render logs

**3. CacheServiceDown**
- **Condition:** Redis (Upstash) unreachable
- **Action:** All queries will be uncached (slower performance)
- **Runbook:** Check Upstash status

**4. DatabaseConnectionErrors**
- **Condition:** >0.1 connection errors/second
- **Action:** Check Supabase and Neo4j connections
- **Runbook:** Verify credentials in .env

**5. ClaudeAPIError**
- **Condition:** High error rate from Anthropic API
- **Action:** Check API key and rate limits
- **Runbook:** https://console.anthropic.com

### Warning Alerts

**1. APISlowResponse**
- **Condition:** P95 response time >30 seconds
- **Action:** Monitor performance, consider scaling

**2. LowCacheHitRate** (Task 43.3)
- **Condition:** Cache hit rate <30% for 15+ minutes
- **Action:** Check Redis connection, semantic similarity threshold
- **Target:** >40% hit rate in production

**3. HighLangGraphFailureRate** (Task 46)
- **Condition:** >10% of LangGraph workflows failing
- **Action:** Check Claude API availability, Arcade.dev tools

**4. CeleryTaskQueueBacklog**
- **Condition:** >100 pending tasks for 10+ minutes
- **Action:** Consider scaling Celery workers

**5. HighMemoryUsage**
- **Condition:** Process using >1.5GB RAM
- **Action:** Check for memory leaks, consider upgrading instance

### Info Alerts

**1. NoQueriesProcessed**
- **Condition:** No user queries in the last hour
- **Action:** System may not be receiving traffic

**2. HighAverageCost**
- **Condition:** Average query cost >$0.50 for 2+ hours
- **Action:** Review LLM usage, optimize prompts

---

## Testing Alerts

### Manual Test Alert

```bash
./test-alert.sh
```

### Trigger Specific Alerts

**Test API Down Alert:**
```bash
# Stop the FastAPI service temporarily
docker-compose down empire-api
# Wait 2 minutes → Alert fires
# Restart service
docker-compose up -d empire-api
```

**Test Cache Alert:**
```bash
# Stop Redis temporarily
docker-compose down redis
# Wait 2 minutes → CacheServiceDown alert fires
```

**Test High Error Rate:**
```bash
# Send requests that return 500 errors
for i in {1..100}; do
  curl https://jb-empire-api.onrender.com/api/query/invalid
done
```

### Verify Alert Delivery

1. **Check Prometheus Alerts:**
   - http://localhost:9090/alerts
   - Should show "FIRING" status

2. **Check Alertmanager:**
   - http://localhost:9093/#/alerts
   - Should show active alerts

3. **Check Email:**
   - Inbox: jbajaj08@gmail.com
   - May take up to 5 minutes due to grouping

4. **Check Logs:**
   ```bash
   docker logs empire-alertmanager
   ```

---

## Troubleshooting

### Email Not Received

**Problem:** Test alert sent but no email received

**Solutions:**
1. **Check SMTP Password:**
   ```bash
   grep SMTP_PASSWORD .env
   # Should show: SMTP_PASSWORD=your-app-password
   ```

2. **Verify Gmail App Password:**
   - App Passwords expire if not used for 90 days
   - Regenerate at: https://myaccount.google.com/apppasswords

3. **Check Alertmanager Logs:**
   ```bash
   docker logs empire-alertmanager | grep -i smtp
   ```

4. **Check Spam Folder:**
   - Empire alerts may be marked as spam initially
   - Mark as "Not Spam" to receive future alerts

### Alert Not Firing

**Problem:** Condition met but alert not firing

**Solutions:**
1. **Check Prometheus Targets:**
   - http://localhost:9090/targets
   - Empire API should show "UP" status

2. **Verify Alert Rules:**
   ```bash
   # Validate alert_rules.yml syntax
   docker exec empire-prometheus promtool check rules /etc/prometheus/alert_rules.yml
   ```

3. **Check Metric Collection:**
   - http://localhost:9090/graph
   - Query: `up{job="empire-api-production"}`
   - Should return value: 1

### Alertmanager Not Starting

**Problem:** `docker-compose up` fails for alertmanager

**Solutions:**
1. **Check Configuration Syntax:**
   ```bash
   docker run --rm -v $(pwd)/monitoring:/etc/alertmanager \
     prom/alertmanager:latest \
     amtool check-config /etc/alertmanager/alertmanager.yml
   ```

2. **Verify SMTP_PASSWORD:**
   - Must be set in .env file
   - Cannot contain special characters that break YAML

### Too Many Alerts

**Problem:** Receiving too many email notifications

**Solutions:**
1. **Adjust Repeat Intervals:**
   Edit `monitoring/alertmanager.yml`:
   ```yaml
   route:
     repeat_interval: 24h  # Increase from 4h
   ```

2. **Increase Thresholds:**
   Edit `monitoring/alert_rules.yml`:
   ```yaml
   expr: rate(http_requests_total{status=~"5.."}) > 0.10  # Increase from 0.05
   ```

3. **Add Inhibition Rules:**
   Suppress related alerts when primary alert fires

---

## Advanced Configuration

### Add Slack Notifications

1. **Create Slack Webhook:**
   - https://api.slack.com/messaging/webhooks
   - Example: `https://hooks.slack.com/services/T00/B00/XXX`

2. **Add to Alertmanager Config:**
   Edit `monitoring/alertmanager.yml`:
   ```yaml
   receivers:
     - name: 'slack-critical'
       slack_configs:
         - api_url: 'https://hooks.slack.com/services/T00/B00/XXX'
           channel: '#empire-alerts'
           title: '🚨 {{ .GroupLabels.alertname }}'
           text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
   ```

3. **Update Routing:**
   ```yaml
   routes:
     - receiver: 'slack-critical'
       match:
         severity: critical
       continue: true  # Also send to email
   ```

### Add PagerDuty Integration

1. **Get PagerDuty Service Key:**
   - https://your-org.pagerduty.com/services
   - Create integration key

2. **Add to Alertmanager:**
   ```yaml
   receivers:
     - name: 'pagerduty-oncall'
       pagerduty_configs:
         - service_key: 'YOUR_SERVICE_KEY'
           description: '{{ .GroupLabels.alertname }}'
   ```

### Custom Alert Rules

**Add New Alert:**

Edit `monitoring/alert_rules.yml`:

```yaml
- alert: HighQueryLatency
  expr: histogram_quantile(0.99, rate(query_duration_seconds_bucket[5m])) > 60
  for: 10m
  labels:
    severity: warning
    component: api
  annotations:
    summary: "Query latency is very high"
    description: "P99 query latency: {{ $value }}s (threshold: 60s)"
    runbook: "Check database performance and cache hit rate"
```

**Reload Prometheus Config:**
```bash
curl -X POST http://localhost:9090/-/reload
```

### Grafana Dashboards

**Import Pre-built Dashboard:**
1. Open http://localhost:3000
2. Login: admin / empiregrafana123
3. Import Dashboard → ID: 1860 (Node Exporter Full)
4. Data source: Prometheus

**Create Custom Dashboard:**
1. Dashboards → New Dashboard
2. Add Panel → Query:
   ```promql
   rate(query_requests_total[5m])
   ```
3. Save Dashboard

---

## Maintenance

### Daily Tasks

- ✅ Check http://localhost:9090/alerts for active alerts
- ✅ Review Grafana dashboards for trends

### Weekly Tasks

- ✅ Review alert email volume
- ✅ Verify no false positives
- ✅ Check disk usage: `docker system df`

### Monthly Tasks

- ✅ Review and adjust alert thresholds
- ✅ Update alert rules for new features
- ✅ Rotate Gmail App Password (optional)
- ✅ Clean up old metrics: `docker volume prune`

### Backup Configuration

```bash
# Backup all monitoring configs
tar -czf monitoring-backup-$(date +%Y%m%d).tar.gz \
  monitoring/ \
  docker-compose.monitoring.yml \
  start-monitoring.sh \
  test-alert.sh
```

### Update Monitoring Stack

```bash
# Pull latest images
docker-compose -f docker-compose.monitoring.yml pull

# Restart with new images
docker-compose -f docker-compose.monitoring.yml up -d
```

---

## Metrics Retention

| Service | Default Retention | Storage Location |
|---------|-------------------|------------------|
| Prometheus | 30 days | `prometheus-data` volume |
| Alertmanager | 120 hours | `alertmanager-data` volume |
| Grafana | Unlimited | `grafana-data` volume |

**Extend Retention:**
Edit `docker-compose.monitoring.yml`:
```yaml
command:
  - '--storage.tsdb.retention.time=90d'  # 90 days
```

---

## Support & Resources

### Documentation

- **Prometheus Docs:** https://prometheus.io/docs/
- **Alertmanager Docs:** https://prometheus.io/docs/alerting/latest/alertmanager/
- **Grafana Docs:** https://grafana.com/docs/

### Troubleshooting Logs

```bash
# View all monitoring logs
docker-compose -f docker-compose.monitoring.yml logs -f

# Specific service logs
docker logs empire-prometheus
docker logs empire-alertmanager
docker logs empire-grafana
```

### Health Check Endpoints

- Prometheus: http://localhost:9090/-/healthy
- Alertmanager: http://localhost:9093/-/healthy
- Grafana: http://localhost:3000/api/health

---

## Summary

**You now have:**
- ✅ 24/7 monitoring of Empire v7.3
- ✅ Email alerts to jbajaj08@gmail.com
- ✅ 30+ pre-configured alert rules
- ✅ Grafana dashboards for visualization
- ✅ Automated alert routing and grouping

**Next Steps:**
1. Run `./start-monitoring.sh` to start monitoring
2. Run `./test-alert.sh` to verify email delivery
3. Monitor http://localhost:9090/alerts daily
4. Adjust thresholds based on your traffic patterns

---

**Questions?** Check the troubleshooting section or review the Prometheus/Alertmanager logs.

---

**Last Updated:** 2025-11-17
**Version:** 1.0
**For:** Empire v7.3
