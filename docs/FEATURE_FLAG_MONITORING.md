# Feature Flag Monitoring - Task 4 Documentation

## Overview

Task 4 added comprehensive monitoring for the Empire v7.3 feature flag system using Prometheus metrics and alert rules.

## Metrics Added

### Feature Flag Performance Metrics

1. **empire_feature_flag_checks_total** (Counter)
   - Labels: `flag_name`, `status` (enabled/disabled)
   - Tracks total number of feature flag checks
   - Use case: Monitor which flags are being checked most frequently

2. **empire_feature_flag_cache_hits_total** (Counter)
   - Labels: `flag_name`
   - Tracks successful cache hits
   - Use case: Measure cache effectiveness per flag

3. **empire_feature_flag_cache_misses_total** (Counter)
   - Labels: `flag_name`
   - Tracks cache misses requiring database lookups
   - Use case: Identify flags with poor cache performance

4. **empire_feature_flag_check_duration_seconds** (Histogram)
   - Labels: `flag_name`, `cache_hit` (true/false)
   - Buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0] seconds
   - Use case: Track performance of flag checks (target: <5ms cached, <50ms uncached)

5. **empire_feature_flag_updates_total** (Counter)
   - Labels: `flag_name`, `operation` (enable/disable/update_rollout)
   - Tracks flag modification operations
   - Use case: Audit flag changes and identify frequently toggled flags

6. **empire_feature_flag_errors_total** (Counter)
   - Labels: `flag_name`, `operation`, `error_type`
   - Tracks errors in flag operations
   - Use case: Monitor system health and catch configuration issues

7. **empire_feature_flags_active** (Gauge)
   - Number of currently enabled feature flags
   - Use case: Track feature rollout progress

8. **empire_feature_flag_rollout_percentage** (Gauge)
   - Labels: `flag_name`
   - Current rollout percentage for gradual rollouts (0-100)
   - Use case: Monitor staged rollout progress

## Alert Rules Added

### 1. FeatureFlagCacheMissRateHigh (Warning)
- **Trigger**: >50% cache miss rate for 10+ minutes
- **Impact**: Increased database load and slower flag checks
- **Runbook**: Check Redis connection and adjust cache TTL

### 2. FeatureFlagCheckErrors (Critical)
- **Trigger**: >0.5 errors/sec for 5+ minutes
- **Impact**: Features may fail to load correctly
- **Runbook**: Check Supabase connectivity and table permissions

### 3. FeatureFlagSlowChecks (Warning)
- **Trigger**: P95 latency >100ms for 10+ minutes
- **Impact**: Degraded application performance
- **Runbook**: Investigate cache hit rate and database query performance

### 4. FeatureFlagUpdateErrors (Warning)
- **Trigger**: >0.1 update errors/sec for 5+ minutes
- **Impact**: Admin operations failing
- **Runbook**: Check authentication and database write permissions

### 5. ExcessiveFeatureFlagUpdates (Info)
- **Trigger**: >5 updates/sec for 15+ minutes
- **Impact**: May indicate testing or misconfiguration
- **Runbook**: Review audit logs to identify source

## Integration Points

### Code Instrumentation
- **File**: `app/core/feature_flags.py`
- **Methods instrumented**:
  - `is_enabled()` - Records checks, cache hits/misses, duration, errors
  - `update_flag()` - Records updates, rollout changes, errors

### Metrics Endpoint
- **URL**: `/api/monitoring/metrics`
- **Format**: Prometheus text format
- **Scrape interval**: 15 seconds (configured in `monitoring/prometheus.yml`)

### Alert Configuration
- **File**: `monitoring/alert_rules.yml`
- **Group**: `feature_flags`
- **Evaluation interval**: 1 minute

## Grafana Dashboard Queries

### Example Queries for Dashboards

**1. Cache Hit Rate**
```promql
(
  rate(empire_feature_flag_cache_hits_total[5m]) /
  (rate(empire_feature_flag_cache_hits_total[5m]) + rate(empire_feature_flag_cache_misses_total[5m]))
) * 100
```

**2. Top 10 Most Checked Flags**
```promql
topk(10, rate(empire_feature_flag_checks_total[1h]))
```

**3. Average Check Latency (Cached)**
```promql
rate(empire_feature_flag_check_duration_seconds_sum{cache_hit="true"}[5m]) /
rate(empire_feature_flag_check_duration_seconds_count{cache_hit="true"}[5m])
```

**4. Average Check Latency (Uncached)**
```promql
rate(empire_feature_flag_check_duration_seconds_sum{cache_hit="false"}[5m]) /
rate(empire_feature_flag_check_duration_seconds_count{cache_hit="false"}[5m])
```

**5. Flag Update Frequency**
```promql
sum by (operation) (rate(empire_feature_flag_updates_total[1h]))
```

**6. Error Rate by Flag**
```promql
sum by (flag_name) (rate(empire_feature_flag_errors_total[5m]))
```

**7. Active Flags**
```promql
empire_feature_flags_active
```

**8. Rollout Progress**
```promql
empire_feature_flag_rollout_percentage
```

## Performance Targets

| Metric | Target | Alert Threshold |
|--------|--------|----------------|
| Cache hit rate | >50% | <50% for 10min |
| Cached check latency | <5ms | P95 >100ms |
| Uncached check latency | <50ms | P95 >100ms |
| Check error rate | <0.1% | >0.5 errors/sec |
| Update error rate | 0% | >0.1 errors/sec |

## Testing Monitoring

### 1. Verify Metrics Are Exported

```bash
# Check Prometheus metrics endpoint
curl https://jb-empire-api.onrender.com/api/monitoring/metrics | grep empire_feature_flag
```

### 2. Trigger Test Alert

```python
# Simulate high error rate
from app.core.feature_flags import get_feature_flag_manager

ff = get_feature_flag_manager()

# Generate errors by checking non-existent flags
for i in range(100):
    await ff.is_enabled(f"nonexistent_flag_{i}")
```

### 3. Check Alert Status

```bash
# View active alerts
curl http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.component=="feature_flags")'
```

## Operational Playbooks

### High Cache Miss Rate
1. Check Redis connection: `redis-cli -h <host> PING`
2. Review cache TTL setting (default: 60s)
3. Consider increasing TTL if flags are stable
4. Check for cache eviction due to memory pressure

### Slow Flag Checks
1. Check cache hit rate first (should be >50%)
2. Query Supabase for slow query logs
3. Verify HNSW index exists on feature_flags table
4. Consider adding database read replicas if needed

### Update Errors
1. Verify admin authentication is working
2. Check Supabase RLS policies for feature_flags table
3. Review database write permissions
4. Check network connectivity to Supabase

### Excessive Updates
1. Review audit logs: `SELECT * FROM audit_logs WHERE event_type = 'feature_flag_update' ORDER BY created_at DESC LIMIT 100`
2. Identify source of updates (automated scripts, manual changes, etc.)
3. If testing: No action needed
4. If misconfiguration: Investigate automated processes

## Related Documentation

- Feature Flag Admin Guide: `docs/FEATURE_FLAG_ADMIN_GUIDE.md`
- Feature Flag Developer Guide: `docs/FEATURE_FLAGS_DEVELOPER_GUIDE.md`
- Monitoring Integration Guide: `monitoring/INTEGRATION_GUIDE.md`
- Alert Rules Configuration: `monitoring/alert_rules.yml`

## Future Enhancements

Potential future monitoring additions:
- Per-user flag check frequency
- A/B test variant distribution metrics
- Flag rollout success rate (correlation with error rates)
- Cost tracking for feature flag infrastructure
- Scheduled change execution metrics (when implemented with Celery)

---

**Last Updated**: January 24, 2025
**Task**: Task 4 - Configure Monitoring for v7.3 Features
**Status**: Complete
