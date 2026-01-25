# Performance Profiling Guide - Empire v7.3
**Task 43.2** - Performance Profiling and Bottleneck Identification

Complete guide for profiling Empire v7.3, identifying bottlenecks, and implementing optimizations.

---

## Overview

This guide covers:
- Running comprehensive performance tests
- Collecting baseline and post-test metrics
- Analyzing results to identify bottlenecks
- Implementing targeted optimizations
- Validating improvements

---

## Quick Start

### Run Complete Profiling Workflow

```bash
# Local testing (light profile)
./run_full_load_test.sh http://localhost:8000 light

# Local testing (moderate profile - expected production load)
./run_full_load_test.sh http://localhost:8000 moderate

# Local testing (heavy profile - 2x stress test)
./run_full_load_test.sh http://localhost:8000 heavy

# Production testing (against Render deployment)
./run_full_load_test.sh https://jb-empire-api.onrender.com production
```

The complete workflow script:
1. Collects baseline metrics
2. Runs Locust load test
3. Collects post-test metrics
4. Analyzes performance
5. Generates recommendations

---

## Step-by-Step Profiling

### Step 1: Collect Baseline Metrics

**Before running any load tests**, capture baseline system metrics:

```bash
# Local
./collect_baseline_metrics.sh http://localhost:8000

# Production
./collect_baseline_metrics.sh https://jb-empire-api.onrender.com
```

**Metrics Collected**:
- Prometheus metrics (HTTP requests, latency, resource usage)
- Health check status for all endpoints
- System resources (CPU, memory, disk)
- Database connection stats (Redis, Neo4j)
- Celery worker status and queue depth

**Output**: `reports/baseline/`

---

### Step 2: Run Load Tests

**Choose the appropriate test profile:**

#### Light Load (CI/CD Smoke Test)
```bash
locust -f locustfile.py --config=locust_light.conf --host=http://localhost:8000
```

**Profile**:
- 10 concurrent users
- 5 minute duration
- Spawn rate: 1 user/second
- Purpose: Quick validation

**Expected Results**:
- P95 response time < 2000ms
- Error rate < 1%
- CPU usage < 50%

---

#### Moderate Load (Expected Production)
```bash
locust -f locustfile.py --config=locust_moderate.conf --host=http://localhost:8000
```

**Profile**:
- 50 concurrent users
- 10 minute duration
- Spawn rate: 5 users/second
- Purpose: Realistic production simulation

**Expected Results**:
- P95 response time < 2000ms
- Error rate < 0.5%
- CPU usage < 70%
- Memory usage < 75%

---

#### Heavy Load (2x Stress Test)
```bash
locust -f locustfile.py --config=locust_heavy.conf --host=http://localhost:8000
```

**Profile**:
- 120 concurrent users (2x expected load)
- 15 minute duration
- Spawn rate: 10 users/second
- Purpose: Identify breaking points

**Expected Results**:
- P95 response time < 5000ms
- Error rate < 2%
- System remains stable (no crashes)
- Graceful degradation

---

#### Production Load (Render Deployment)
```bash
locust -f locustfile.py --config=locust_production.conf
```

**Profile**:
- 100 concurrent users
- 10 minute duration
- Excludes resource-intensive operations (to avoid LLM API costs)
- Tests against https://jb-empire-api.onrender.com

**Expected Results**:
- P95 response time < 3000ms (higher due to cold starts)
- Error rate < 1%
- No service disruptions

---

### Step 3: Collect Post-Test Metrics

**After completing load tests**, capture post-test metrics:

```bash
# Local
./collect_post_test_metrics.sh http://localhost:8000

# Production
./collect_post_test_metrics.sh https://jb-empire-api.onrender.com
```

**Metrics Collected**:
- Same as baseline (for comparison)
- Locust CSV results (response times, error rates)
- Locust HTML report (visual analysis)

**Output**: `reports/post_test/`

---

### Step 4: Analyze Performance

**Run the performance analysis script:**

```bash
python3 analyze_performance.py reports/baseline reports/post_test
```

**Analysis Includes**:
- Prometheus metric comparisons (baseline vs post-test)
- Locust endpoint statistics (P50, P95, P99 response times)
- System resource usage (CPU, memory)
- Database performance (cache hit rates, connection counts)
- Celery worker performance (task queue depth)
- Bottleneck identification
- Optimization recommendations

**Output**: `reports/performance_analysis_TIMESTAMP.json`

---

## Understanding Results

### Locust HTML Report

**Open the report:**
```bash
open reports/load_test_PROFILE_report_TIMESTAMP.html
```

**Key Sections**:

1. **Statistics Table**
   - Request counts per endpoint
   - Response times (P50, P95, P99)
   - Failure rates
   - Requests per second

2. **Charts**
   - Total Requests per Second (RPS)
   - Response Times (over time)
   - Number of Users (ramp-up curve)

3. **Failures**
   - Error messages and counts
   - Identifies problematic endpoints

---

### Performance Analysis JSON

**Example structure:**

```json
{
  "analysis_timestamp": "2025-01-15T10:30:00",
  "bottlenecks": [
    {
      "category": "response_time",
      "endpoint": "/api/query/adaptive",
      "severity": "high",
      "message": "P95 response time: 5200ms",
      "p95_ms": 5200,
      "p99_ms": 8100
    },
    {
      "category": "error_rate",
      "endpoint": "/api/documents/bulk-upload",
      "severity": "medium",
      "message": "Failure rate: 2.3%",
      "failure_rate": 2.3
    }
  ],
  "recommendations": [
    {
      "priority": "high",
      "category": "response_time",
      "title": "Optimize slow endpoints",
      "actions": [
        "Add caching to slow endpoints (Redis)",
        "Optimize database queries (add indexes)",
        "Consider async processing for heavy operations"
      ]
    }
  ]
}
```

---

## Common Bottlenecks

### 1. Slow Response Times (P95 > 2000ms)

**Symptoms**:
- High P95/P99 response times
- User complaints about slowness
- Timeouts under load

**Investigation**:
```bash
# Check endpoint breakdown in Locust report
open reports/load_test_moderate_report.html

# Look for slow queries in logs
grep "duration" app.log | sort -k3 -nr | head -20

# Profile specific endpoint
python -m cProfile -s cumtime app/routes/query.py
```

**Common Causes**:
- Database queries without indexes
- N+1 query problems
- Unoptimized LLM API calls (no caching)
- Heavy synchronous processing
- Vector similarity search on large datasets

**Solutions**:
- Add database indexes on frequently queried columns
- Implement semantic caching for query results
- Use async processing for heavy operations (Celery)
- Add response caching (Redis)
- Optimize vector search (use HNSW indexes)

---

### 2. High Error Rates (> 1%)

**Symptoms**:
- 500 Internal Server Errors
- 429 Rate Limit Errors
- Connection timeouts
- Database connection errors

**Investigation**:
```bash
# Check error logs
grep "ERROR" app.log | tail -100

# Check database connection pool
redis-cli INFO stats

# Check Celery worker status
celery -A app.celery_app inspect stats
```

**Common Causes**:
- Database connection pool exhaustion
- Rate limiting triggered
- Unhandled exceptions
- LLM API rate limits
- Memory leaks causing crashes

**Solutions**:
- Increase database connection pool size
- Implement retry logic with exponential backoff
- Add comprehensive error handling
- Use LLM API fallback models
- Fix memory leaks (profile with memory_profiler)

---

### 3. High CPU Usage (> 80%)

**Symptoms**:
- Slow response times under load
- High CPU usage in system metrics
- Process throttling

**Investigation**:
```bash
# Monitor CPU during load test
top -pid $(pgrep -f "uvicorn") -stats cpu,mem -l 5

# Profile CPU-intensive code
python -m cProfile -o profile.stats app/main.py
python -m pstats profile.stats
```

**Common Causes**:
- Inefficient embedding generation
- Heavy LangGraph iterations
- Unoptimized graph traversals (Neo4j)
- JSON serialization of large responses
- Regex processing on large documents

**Solutions**:
- Cache embedding generation results
- Limit LangGraph max_iterations (3-5)
- Optimize Cypher queries
- Stream large responses
- Use compiled regex patterns

---

### 4. High Memory Usage (> 80%)

**Symptoms**:
- Out of memory errors
- Swap usage increasing
- Process killed by OS

**Investigation**:
```bash
# Monitor memory during test
top -pid $(pgrep -f "uvicorn") -stats mem -l 5

# Profile memory usage
python -m memory_profiler app/main.py
```

**Common Causes**:
- Loading entire documents into memory
- Unbounded caching
- Embedding vectors accumulating
- Large graph query results
- Memory leaks in long-running workers

**Solutions**:
- Stream document processing
- Set cache size limits (LRU eviction)
- Use database for vector storage (not in-memory)
- Paginate graph query results
- Restart Celery workers periodically

---

### 5. Low Cache Hit Rate (< 70%)

**Symptoms**:
- High database query counts
- Slow repeated queries
- High Redis memory usage with low hits

**Investigation**:
```bash
# Check Redis stats
redis-cli INFO stats

# Monitor cache hit rate
redis-cli MONITOR | grep GET
```

**Common Causes**:
- Cache TTL too short
- Cache keys not reused effectively
- Cache eviction too aggressive
- Query variations not normalized

**Solutions**:
- Increase cache TTL for stable data
- Normalize queries before caching
- Use semantic caching (similarity-based)
- Increase Redis memory allocation

---

### 6. Celery Task Queue Buildup

**Symptoms**:
- Tasks not processing
- Increasing queue depth
- Timeouts waiting for tasks

**Investigation**:
```bash
# Check active tasks
celery -A app.celery_app inspect active

# Check reserved tasks
celery -A app.celery_app inspect reserved

# Check worker status
celery -A app.celery_app inspect stats
```

**Common Causes**:
- Not enough workers
- Workers stuck on long tasks
- Task priority not configured
- Worker memory leaks

**Solutions**:
- Scale workers horizontally
- Set task time limits
- Implement task prioritization
- Restart workers periodically
- Use dedicated queues for long tasks

---

## Optimization Workflow

### 1. Identify Bottleneck

Run profiling workflow and review analysis:
```bash
./run_full_load_test.sh http://localhost:8000 moderate
cat reports/performance_analysis_*.json | jq '.bottlenecks'
```

### 2. Implement Fix

**Example: Add Caching to Slow Endpoint**

```python
# Before (slow)
@router.post("/api/query/adaptive")
async def adaptive_query(request: QueryRequest):
    result = await run_langgraph_workflow(request.query)
    return result

# After (cached)
from app.services.cache_service import cache_service

@router.post("/api/query/adaptive")
async def adaptive_query(request: QueryRequest):
    cache_key = f"adaptive:{hash(request.query)}"

    # Try cache first
    cached = await cache_service.get(cache_key)
    if cached:
        return cached

    # Run workflow
    result = await run_langgraph_workflow(request.query)

    # Cache result (5 minutes)
    await cache_service.set(cache_key, result, ttl=300)

    return result
```

### 3. Re-Run Tests

```bash
# Run same test again
./run_full_load_test.sh http://localhost:8000 moderate

# Compare results
python3 analyze_performance.py reports/baseline reports/post_test
```

### 4. Validate Improvement

**Check analysis results:**
- Response time reduced?
- Error rate decreased?
- CPU/memory usage lower?
- Cache hit rate improved?

### 5. Iterate

Repeat for each bottleneck until performance targets met.

---

## Performance Targets

### Response Time Targets (95th Percentile)

| Endpoint Type | Target P95 | Max Acceptable |
|---------------|------------|----------------|
| Health checks | < 100ms | 200ms |
| Status polling | < 200ms | 500ms |
| Simple reads | < 500ms | 1000ms |
| Faceted search | < 1000ms | 2000ms |
| Adaptive query (sync) | < 2000ms | 5000ms |
| Auto-routed query | < 1500ms | 3000ms |
| Async operations (202) | < 300ms | 500ms |

### Throughput Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Overall RPS | > 100 | Total requests per second |
| Query processing | > 50 | Query endpoints only |
| Document processing | > 20 | Upload/processing endpoints |
| Health checks | > 200 | Monitoring traffic |

### Error Rate Targets

| Category | Target | Max Acceptable |
|----------|--------|----------------|
| Overall | < 0.5% | 1% |
| Critical endpoints | < 0.1% | 0.5% |
| LLM API calls | < 1% | 2% |

### Resource Usage Targets

| Resource | Normal | Max Under Load |
|----------|--------|----------------|
| CPU | < 50% | 70% |
| Memory | < 60% | 80% |
| Disk I/O | < 50% | 70% |
| Network | < 40% | 60% |

---

## Monitoring During Load Tests

### Real-Time Monitoring

**Terminal 1: Locust**
```bash
locust -f locustfile.py --config=locust_moderate.conf --host=http://localhost:8000
```

**Terminal 2: Resource Monitoring**
```bash
# CPU and memory
watch -n 2 'top -l 1 | head -20'

# Network connections
watch -n 2 'netstat -an | grep LISTEN | grep 8000'
```

**Terminal 3: Application Logs**
```bash
tail -f app.log | grep -E '(ERROR|WARN|duration)'
```

**Terminal 4: Redis Monitoring**
```bash
watch -n 2 'redis-cli INFO stats | grep -E "(hits|misses|connections)"'
```

---

## Troubleshooting

### Load Test Fails to Start

**Error**: `ModuleNotFoundError: No module named 'locust'`

**Fix**:
```bash
pip install -r requirements.txt
```

---

### Server Crashes During Test

**Symptoms**:
- Connection refused errors
- Load test aborts
- No response from server

**Investigation**:
```bash
# Check if process is running
ps aux | grep uvicorn

# Check logs for crash
tail -100 app.log | grep -E '(ERROR|CRITICAL)'

# Check system resources
top -l 1
```

**Fix**:
- Reduce concurrent users
- Increase server resources
- Fix memory leaks
- Add error handling

---

### Metrics Collection Fails

**Error**: `Failed to collect Prometheus metrics`

**Fix**:
```bash
# Verify metrics endpoint
curl http://localhost:8000/monitoring/metrics

# Check if Prometheus is enabled
grep PROMETHEUS .env
```

---

### Analysis Script Errors

**Error**: `FileNotFoundError: reports/baseline not found`

**Fix**:
```bash
# Ensure baseline was collected first
./collect_baseline_metrics.sh http://localhost:8000

# Verify files exist
ls reports/baseline/
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Performance Tests

on:
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight
  workflow_dispatch:

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd tests/load_testing
          pip install -r requirements.txt

      - name: Start FastAPI
        run: |
          uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          sleep 10

      - name: Run light load test
        run: |
          cd tests/load_testing
          ./run_full_load_test.sh http://localhost:8000 light

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: load-test-results
          path: tests/load_testing/reports/

      - name: Check performance targets
        run: |
          python3 tests/load_testing/check_performance_targets.py
```

---

## Best Practices

### 1. Baseline Before Every Test
Always collect baseline metrics before running load tests for accurate comparisons.

### 2. Run Multiple Iterations
Run tests 3-5 times and average results to account for variance.

### 3. Test Against Production Data
Use production-like data volumes for realistic results.

### 4. Isolate Variables
Change one thing at a time when testing optimizations.

### 5. Monitor During Tests
Watch real-time metrics to catch issues early.

### 6. Document Results
Save all reports and analysis for future reference.

### 7. Schedule Regular Tests
Run weekly or monthly to catch performance regressions.

### 8. Test Production Safely
Use `exclude-tags resource-intensive` for production to avoid costs.

---

## Next Steps

1. **Run Initial Profiling**
   ```bash
   ./run_full_load_test.sh http://localhost:8000 moderate
   ```

2. **Review Analysis**
   ```bash
   cat reports/performance_analysis_*.json | jq '.bottlenecks, .recommendations'
   ```

3. **Implement Top 3 Optimizations**
   - Focus on high-severity bottlenecks first
   - Prioritize quick wins (caching, indexing)

4. **Re-Test and Validate**
   ```bash
   ./run_full_load_test.sh http://localhost:8000 moderate
   ```

5. **Deploy to Production**
   - Test staging environment first
   - Run production load test with safe profile
   - Monitor for 24-48 hours

---

**Created**: 2025-01-15
**Task**: 43.2 - Performance Profiling and Bottleneck Identification
**Version**: 1.0
