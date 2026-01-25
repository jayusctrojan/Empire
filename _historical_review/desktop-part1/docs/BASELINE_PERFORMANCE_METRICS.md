# Empire v7.3 Baseline Performance Metrics

**Task 7.4**: Document baseline performance metrics for all endpoints

**Last Updated**: 2025-11-25

## Overview

This document defines baseline performance metrics and thresholds for all Empire v7.3 API endpoints. These baselines are used for:

- Performance regression testing
- Alerting thresholds in monitoring
- Capacity planning
- SLA definitions

## Test Environment

### Local Development
- **Host**: http://localhost:8000
- **Database**: Local PostgreSQL (Supabase)
- **Redis**: Local or Upstash
- **Neo4j**: Local Docker container

### Production (Render)
- **Host**: https://jb-empire-api.onrender.com
- **Plan**: Starter ($7/month)
- **Database**: Supabase (shared tier)
- **Redis**: Upstash (free tier)

---

## Performance Tiers

### Tier 1: Health & Monitoring (Low Latency)
**Target**: < 100ms P95

| Endpoint | P50 | P95 | P99 | Max | RPS |
|----------|-----|-----|-----|-----|-----|
| `GET /health` | 10ms | 50ms | 100ms | 500ms | 100+ |
| `GET /api/query/health` | 15ms | 75ms | 150ms | 750ms | 100+ |
| `GET /api/crewai/health` | 15ms | 75ms | 150ms | 750ms | 100+ |
| `GET /monitoring/metrics` | 20ms | 100ms | 200ms | 1s | 50+ |

### Tier 2: Light Operations (Medium Latency)
**Target**: < 500ms P95

| Endpoint | P50 | P95 | P99 | Max | RPS |
|----------|-----|-----|-----|-----|-----|
| `GET /api/documents/batch-operations/{id}` | 50ms | 200ms | 500ms | 2s | 50+ |
| `GET /api/query/status/{task_id}` | 50ms | 200ms | 500ms | 2s | 50+ |
| `GET /api/crewai/executions/{id}` | 75ms | 250ms | 600ms | 2s | 40+ |
| `GET /api/crewai/crews` | 100ms | 300ms | 700ms | 3s | 30+ |
| `GET /api/crewai/stats` | 100ms | 350ms | 800ms | 3s | 30+ |

### Tier 3: Standard Operations (Higher Latency)
**Target**: < 2000ms P95

| Endpoint | P50 | P95 | P99 | Max | RPS |
|----------|-----|-----|-----|-----|-----|
| `POST /api/query/search/faceted` | 300ms | 1s | 2s | 5s | 20+ |
| `POST /api/documents/bulk-upload` | 500ms | 1.5s | 3s | 10s | 10+ |
| `POST /api/documents/versions/create` | 400ms | 1.2s | 2.5s | 8s | 15+ |
| `GET /api/documents/batch-operations` | 200ms | 800ms | 1.5s | 5s | 20+ |

### Tier 4: AI-Intensive Operations (High Latency)
**Target**: < 10s P95 (sync), async preferred

| Endpoint | P50 | P95 | P99 | Max | RPS |
|----------|-----|-----|-----|-----|-----|
| `POST /api/query/auto` | 2s | 8s | 15s | 30s | 5+ |
| `POST /api/query/adaptive` | 3s | 10s | 20s | 45s | 5+ |
| `POST /api/query/adaptive/async` | 200ms | 500ms | 1s | 3s | 20+ |
| `POST /api/query/auto/async` | 150ms | 400ms | 800ms | 2s | 20+ |
| `POST /api/query/batch` | 300ms | 800ms | 1.5s | 5s | 10+ |
| `POST /api/crewai/execute` | 500ms | 1.5s | 3s | 10s | 5+ |

---

## Baseline Thresholds

### Success Criteria (All profiles)

```yaml
success_criteria:
  error_rate:
    warning: 1%
    critical: 5%

  health_endpoints:
    p95_latency:
      warning: 200ms
      critical: 500ms

  standard_endpoints:
    p95_latency:
      warning: 2s
      critical: 5s

  ai_endpoints:
    p95_latency:
      warning: 15s
      critical: 30s

  throughput:
    minimum_rps: 30
    warning_rps: 20
    critical_rps: 10
```

### Alert Rules

Based on these baselines, configure the following alerts:

```yaml
# Prometheus/Grafana Alert Rules

# Critical: Service Down
- alert: APIDown
  expr: up{job="empire-api"} == 0
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Empire API is down"

# Warning: High Error Rate
- alert: HighErrorRate
  expr: rate(empire_requests_total{status=~"5.."}[5m]) / rate(empire_requests_total[5m]) > 0.01
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Error rate > 1%"

# Critical: Very High Error Rate
- alert: VeryHighErrorRate
  expr: rate(empire_requests_total{status=~"5.."}[5m]) / rate(empire_requests_total[5m]) > 0.05
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Error rate > 5%"

# Warning: Slow Health Check
- alert: SlowHealthCheck
  expr: histogram_quantile(0.95, rate(empire_request_duration_seconds_bucket{endpoint="/health"}[5m])) > 0.2
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Health check P95 > 200ms"

# Warning: Slow Standard Endpoints
- alert: SlowStandardEndpoints
  expr: histogram_quantile(0.95, rate(empire_request_duration_seconds_bucket{endpoint!~"/health|/api/query/adaptive.*"}[5m])) > 2
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Standard endpoint P95 > 2s"

# Warning: Slow AI Endpoints
- alert: SlowAIEndpoints
  expr: histogram_quantile(0.95, rate(empire_request_duration_seconds_bucket{endpoint=~"/api/query/adaptive.*"}[5m])) > 15
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "AI endpoint P95 > 15s"

# Critical: Very Slow AI Endpoints
- alert: VerySlowAIEndpoints
  expr: histogram_quantile(0.95, rate(empire_request_duration_seconds_bucket{endpoint=~"/api/query/adaptive.*"}[5m])) > 30
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "AI endpoint P95 > 30s"

# Warning: Low Throughput
- alert: LowThroughput
  expr: rate(empire_requests_total[5m]) < 20
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Request rate < 20 RPS"
```

---

## Load Test Profiles

### Light Profile (Baseline Collection)
```
Users: 10
Spawn Rate: 1/second
Duration: 5 minutes
Purpose: Establish baseline metrics
```

### Moderate Profile (Expected Production)
```
Users: 50
Spawn Rate: 5/second
Duration: 10 minutes
Purpose: Simulate normal production load
```

### Heavy Profile (2x Expected)
```
Users: 120
Spawn Rate: 10/second
Duration: 15 minutes
Purpose: Stress testing, capacity planning
```

### Spike Profile (Sudden Load)
```
Users: 200
Spawn Rate: 50/second
Duration: 5 minutes
Purpose: Test autoscaling, identify race conditions
```

---

## Performance Budget

### Per-Request Budget (Sync Queries)

```
Total Budget: 10 seconds

- API Gateway / Load Balancer:     100ms (1%)
- Authentication / Rate Limiting:  50ms (0.5%)
- Request Parsing / Validation:    50ms (0.5%)
- Database Query (Supabase):       500ms (5%)
- Vector Search:                   1000ms (10%)
- LLM API Call (Claude):           6000ms (60%)
- Response Synthesis:              500ms (5%)
- Response Serialization:          100ms (1%)
- Network Latency:                 200ms (2%)
- Buffer:                          1500ms (15%)
```

### Per-Request Budget (Async Submission)

```
Total Budget: 1 second

- API Gateway / Load Balancer:     100ms (10%)
- Authentication / Rate Limiting:  50ms (5%)
- Request Parsing / Validation:    50ms (5%)
- Task Queuing (Celery/Redis):     200ms (20%)
- Response Serialization:          50ms (5%)
- Network Latency:                 100ms (10%)
- Buffer:                          450ms (45%)
```

---

## Endpoint-Specific SLAs

### Mission-Critical Endpoints

| Endpoint | Availability | P99 Latency | Error Budget |
|----------|-------------|-------------|--------------|
| `GET /health` | 99.99% | 500ms | 0.01% |
| `GET /api/query/health` | 99.9% | 1s | 0.1% |
| `GET /monitoring/metrics` | 99.9% | 1s | 0.1% |

### Business-Critical Endpoints

| Endpoint | Availability | P99 Latency | Error Budget |
|----------|-------------|-------------|--------------|
| `POST /api/query/auto` | 99.5% | 30s | 0.5% |
| `POST /api/query/adaptive` | 99.5% | 45s | 0.5% |
| `POST /api/query/search/faceted` | 99.5% | 5s | 0.5% |

### Standard Endpoints

| Endpoint | Availability | P99 Latency | Error Budget |
|----------|-------------|-------------|--------------|
| `POST /api/documents/*` | 99% | 10s | 1% |
| `POST /api/crewai/*` | 99% | 10s | 1% |
| `GET /api/*/status/*` | 99.5% | 2s | 0.5% |

---

## Capacity Planning

### Current Limits (Starter Plan)

| Resource | Limit | Warning | Critical |
|----------|-------|---------|----------|
| CPU | 0.5 vCPU | 70% | 90% |
| Memory | 512 MB | 70% | 90% |
| Concurrent Connections | 100 | 70 | 90 |
| Database Pool | 10 | 7 | 9 |
| Redis Connections | 50 | 35 | 45 |

### Scaling Triggers

**Scale Up When:**
- CPU > 80% for 5+ minutes
- Memory > 85% for 5+ minutes
- P95 latency > 2x baseline for 10+ minutes
- Error rate > 2% for 5+ minutes

**Scale Down When:**
- CPU < 30% for 30+ minutes
- Memory < 50% for 30+ minutes
- P95 latency < baseline for 30+ minutes

---

## Regression Testing

### Weekly Baseline Check

Run this command weekly to verify baselines:

```bash
cd tests/load_testing
./run_load_tests.sh light https://jb-empire-api.onrender.com

# Compare with baseline
python scripts/compare_baselines.py \
    --baseline docs/BASELINE_PERFORMANCE_METRICS.md \
    --current reports/load_test_light_latest.csv
```

### Pre-Deployment Check

Before each deployment:

```bash
# 1. Run light load test on staging
./run_load_tests.sh light https://staging.empire-api.onrender.com

# 2. Check for regressions
python scripts/check_regressions.py --threshold 20%

# 3. If passing, deploy to production
# 4. Run smoke test
./run_load_tests.sh light --run-time=1m
```

### Post-Incident Review

After any performance incident:

1. Collect metrics during incident
2. Compare against baselines
3. Identify root cause
4. Update baselines if infrastructure changed
5. Document in incident report

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-25 | 1.0 | Initial baseline document |

---

## References

- [Load Testing README](../tests/load_testing/README.md)
- [Monitoring Integration Guide](../monitoring/INTEGRATION_GUIDE.md)
- [Alert Rules](../monitoring/alert_rules.yml)
- [Prometheus Configuration](../monitoring/prometheus.yml)
