# Empire v7.3 - Load Testing Suite

Task 43.1: Design and Execute Load Testing Scenarios

## Overview

Comprehensive load testing infrastructure for Empire v7.3 using Locust. Tests cover:

- **Document Processing**: Bulk uploads, versioning, batch operations
- **Query Processing**: Adaptive queries, auto-routing, faceted search, async tasks
- **CrewAI Workflows**: Crew execution, agent management, status polling
- **Health & Monitoring**: Health checks, Prometheus metrics

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Create reports directory
mkdir -p reports
```

### Run Tests

#### Interactive Web UI (Recommended for manual testing)

```bash
# Start Locust web UI
locust -f locustfile.py --host=http://localhost:8000

# Open browser to http://localhost:8089
# Configure users and spawn rate via UI
```

#### Headless Mode (Recommended for CI/CD)

```bash
# Light load (10 users, 5 minutes)
locust -f locustfile.py --config=locust_light.conf

# Moderate load (50 users, 10 minutes)
locust -f locustfile.py --config=locust_moderate.conf

# Heavy load - 2x expected (120 users, 15 minutes)
locust -f locustfile.py --config=locust_heavy.conf

# Production stress test (USE WITH CAUTION!)
locust -f locustfile.py --config=locust_production.conf
```

#### Custom Configuration

```bash
# Custom users and duration
locust -f locustfile.py --host=http://localhost:8000 --users=30 --spawn-rate=3 --run-time=10m --headless

# Test specific tags only
locust -f locustfile.py --host=http://localhost:8000 --tags query,document --headless

# Exclude resource-intensive operations
locust -f locustfile.py --host=http://localhost:8000 --exclude-tags resource-intensive --headless
```

## Performance Profiling Workflow (Task 43.2)

For comprehensive performance profiling, bottleneck identification, and optimization:

### Complete Profiling Workflow

```bash
# Run full profiling workflow (collects baseline, runs test, analyzes results)
./run_full_load_test.sh http://localhost:8000 moderate

# Production profiling
./run_full_load_test.sh https://jb-empire-api.onrender.com production
```

The complete workflow includes:
1. **Baseline metrics collection** - System state before load test
2. **Load test execution** - Locust test with configured profile
3. **Post-test metrics collection** - System state after load test
4. **Performance analysis** - Automated bottleneck identification
5. **Recommendations** - Prioritized optimization suggestions

### Manual Step-by-Step Profiling

```bash
# Step 1: Collect baseline metrics
./collect_baseline_metrics.sh http://localhost:8000

# Step 2: Run load test
locust -f locustfile.py --config=locust_moderate.conf

# Step 3: Collect post-test metrics
./collect_post_test_metrics.sh http://localhost:8000

# Step 4: Analyze performance
python3 analyze_performance.py reports/baseline reports/post_test
```

### Profiling Outputs

- **Baseline metrics**: `reports/baseline/`
- **Post-test metrics**: `reports/post_test/`
- **Locust reports**: `reports/load_test_*_report.html`
- **Performance analysis**: `reports/performance_analysis_*.json`

See **[PROFILING.md](PROFILING.md)** for complete profiling guide, bottleneck identification, and optimization strategies.

---

## Test Scenarios

### User Types (Weight Distribution)

1. **QueryProcessingUser** (50%) - Most common
   - Adaptive queries
   - Auto-routed queries
   - Faceted search
   - Async task submission
   - Status polling

2. **DocumentProcessingUser** (30%)
   - Bulk document upload
   - Batch operation status polling
   - Document versioning

3. **RealisticWorkflowUser** (20%)
   - Sequential workflow combining multiple operations
   - Simulates real user behavior patterns

4. **MonitoringUser** (10%)
   - Health checks
   - Prometheus metrics collection

5. **CrewAIWorkflowUser** (10%)
   - Crew execution
   - Execution status polling
   - Agent pool statistics

### Task Weights

Within each user type, tasks have different weights representing frequency:

**QueryProcessingUser Tasks:**
- `adaptive_query_sync` (4) - Most resource-intensive
- `check_query_task_status` (4) - Frequent polling
- `auto_routed_query_sync` (3)
- `faceted_search` (3)
- `adaptive_query_async` (2)
- `batch_query_processing` (1)

**DocumentProcessingUser Tasks:**
- `check_batch_operation_status` (5) - Very frequent polling
- `bulk_upload_documents` (3)
- `create_document_version` (2)
- `list_batch_operations` (1)

**CrewAIWorkflowUser Tasks:**
- `check_execution_status` (3) - Frequent polling
- `execute_crew_workflow` (2) - Resource-intensive
- `get_agent_pool_stats` (1)
- `list_crews` (1)

## Load Profiles

### Light Load (`locust_light.conf`)
- **Users**: 10
- **Spawn Rate**: 1/second
- **Duration**: 5 minutes
- **Purpose**: Baseline performance, smoke testing
- **Use Case**: Daily CI/CD checks

### Moderate Load (`locust_moderate.conf`)
- **Users**: 50
- **Spawn Rate**: 5/second
- **Duration**: 10 minutes
- **Purpose**: Expected production load
- **Use Case**: Pre-deployment validation

### Heavy Load (`locust_heavy.conf`)
- **Users**: 120
- **Spawn Rate**: 10/second
- **Duration**: 15 minutes
- **Purpose**: 2x expected load (stress test)
- **Use Case**: Identify breaking points, capacity planning

### Production Load (`locust_production.conf`)
- **Host**: https://jb-empire-api.onrender.com
- **Users**: 100
- **Spawn Rate**: 10/second
- **Duration**: 5 minutes (shorter to minimize cost)
- **Purpose**: Production stress test
- **Caution**: Excludes `resource-intensive` tags to minimize API costs

## Metrics Collection

### Built-in Locust Metrics

Locust automatically collects:
- **Response Times**: Min, max, average, median, 95th/99th percentiles
- **Request Rates**: Requests per second (RPS)
- **Failure Rates**: Failed requests vs total
- **Response Size**: Bytes sent/received

### Custom Metrics

The load test suite emits:
- **Request success/failure by endpoint**
- **Task execution counts by type**
- **User distribution across types**

### Prometheus Integration

Empire's `/monitoring/metrics` endpoint exposes:
- `empire_requests_total{method, endpoint, status}` - Total requests
- `empire_request_duration_seconds{method, endpoint}` - Request latency histogram
- `empire_celery_tasks_total{task_name, status}` - Celery task counts
- `empire_celery_task_duration_seconds{task_name}` - Celery task duration

### View Real-time Metrics

```bash
# During load test, check Prometheus metrics
curl http://localhost:8000/monitoring/metrics | grep empire

# Or use Grafana dashboard (if monitoring stack is running)
# http://localhost:3000
```

## Reports

After each test run, reports are generated in `reports/`:

### HTML Report (`*_report.html`)
- Interactive dashboard with charts
- Request statistics by endpoint
- Response time distribution
- Failure analysis

### CSV Reports (`*_stats.csv`, `*_stats_history.csv`, `*_failures.csv`)
- `*_stats.csv`: Final statistics per endpoint
- `*_stats_history.csv`: Time-series data for charting
- `*_failures.csv`: Detailed failure logs

### Log Files (`*.log`)
- Detailed execution logs
- Errors and exceptions
- Request/response debugging

## Analyzing Results

### Key Performance Indicators (KPIs)

#### Success Criteria (Moderate Load):
- ✅ **95th percentile response time** < 2000ms for sync queries
- ✅ **95th percentile response time** < 500ms for health checks
- ✅ **Failure rate** < 1%
- ✅ **Throughput** > 50 requests/second
- ✅ **All health checks** passing

#### Warning Signs:
- ⚠️ 95th percentile > 3000ms
- ⚠️ Failure rate > 2%
- ⚠️ Throughput < 40 requests/second
- ⚠️ Increasing response times over test duration

#### Critical Issues:
- 🚨 95th percentile > 5000ms
- 🚨 Failure rate > 5%
- 🚨 Throughput < 30 requests/second
- 🚨 Service crashes or timeouts

### Common Bottlenecks

1. **Database Connection Pool Exhaustion**
   - Symptom: Timeouts on database queries
   - Solution: Increase pool size in `app/core/connections.py`

2. **Celery Worker Saturation**
   - Symptom: Increasing task queue depth, delayed async responses
   - Solution: Scale Celery workers, increase concurrency

3. **Redis Connection Limits**
   - Symptom: Cache failures, rate limiting errors
   - Solution: Increase Redis max connections

4. **External API Rate Limits**
   - Symptom: 429 errors from Anthropic/Perplexity
   - Solution: Implement request throttling, use fallback models

5. **Neo4j Query Performance**
   - Symptom: Slow graph queries
   - Solution: Add indexes, optimize Cypher queries

### Performance Profiling

Use Locust results combined with:

```bash
# Check Celery queue depth
celery -A app.celery_app inspect active

# Monitor Redis connections
redis-cli INFO clients

# Check Neo4j query performance
# Access Neo4j browser: http://localhost:7474
# Run: CALL dbms.listQueries()

# Monitor Supabase performance
# Use Supabase dashboard or Render MCP
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Load Testing

on:
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  load-test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r tests/load_testing/requirements.txt

      - name: Start services
        run: |
          docker-compose up -d
          sleep 30  # Wait for services to be ready

      - name: Run light load test
        run: |
          cd tests/load_testing
          locust -f locustfile.py --config=locust_light.conf

      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: load-test-reports
          path: tests/load_testing/reports/

      - name: Check performance thresholds
        run: |
          # Parse CSV and fail if thresholds exceeded
          python scripts/check_performance_thresholds.py
```

## Best Practices

### Before Running Load Tests

1. ✅ **Ensure all services are running**:
   ```bash
   # Check health endpoints
   curl http://localhost:8000/health
   curl http://localhost:8000/api/query/health
   curl http://localhost:8000/api/crewai/health
   ```

2. ✅ **Clear caches and queues**:
   ```bash
   # Redis
   redis-cli FLUSHALL

   # Celery
   celery -A app.celery_app purge
   ```

3. ✅ **Set baseline metrics**:
   ```bash
   # Capture pre-test metrics
   curl http://localhost:8000/monitoring/metrics > reports/baseline_metrics.txt
   ```

4. ✅ **Prepare test data**:
   - Create test crews and agents for CrewAI tests
   - Upload test documents for query tests
   - Set up test users if authentication is enabled

### During Load Tests

1. 📊 **Monitor system resources**:
   ```bash
   # CPU, memory, disk I/O
   htop

   # Network I/O
   iftop

   # Docker containers
   docker stats
   ```

2. 📊 **Watch application logs**:
   ```bash
   # FastAPI logs
   docker logs -f empire-api

   # Celery logs
   docker logs -f empire-celery-worker
   ```

3. 📊 **Monitor external services**:
   - Render dashboard (for production tests)
   - Supabase dashboard (database queries)
   - Upstash Redis dashboard (cache performance)

### After Load Tests

1. 📈 **Review reports**:
   - Open HTML report in browser
   - Analyze CSV data for trends
   - Check log files for errors

2. 📈 **Compare against baseline**:
   ```bash
   # Compare metrics before/after
   curl http://localhost:8000/monitoring/metrics > reports/post_test_metrics.txt
   diff reports/baseline_metrics.txt reports/post_test_metrics.txt
   ```

3. 📈 **Document findings**:
   - Bottlenecks identified
   - Performance improvements needed
   - Infrastructure scaling recommendations

## Troubleshooting

### "Connection refused" errors

```bash
# Check if FastAPI is running
curl http://localhost:8000/health

# Start FastAPI
uvicorn app.main:app --reload --port 8000
```

### "Task X not found" errors (CrewAI tests)

```python
# Create test crews before running tests
# See: tests/setup_test_data.py
```

### Rate limit errors (429)

```bash
# Reduce spawn rate or users
locust -f locustfile.py --host=http://localhost:8000 --users=10 --spawn-rate=1
```

### Memory issues during tests

```bash
# Reduce test duration and users
locust -f locustfile.py --host=http://localhost:8000 --users=20 --run-time=2m
```

## Tags Reference

Use tags to run specific test categories:

### Available Tags

- `document` - Document processing operations
- `bulk` - Bulk operations
- `versioning` - Document versioning
- `query` - Query processing operations
- `adaptive` - Adaptive queries (LangGraph)
- `auto-routed` - Auto-routed queries
- `search` - Search operations
- `faceted` - Faceted search
- `async` - Async task operations
- `polling` - Status polling operations
- `crewai` - CrewAI workflow operations
- `execution` - Crew execution
- `health` - Health check operations
- `monitoring` - Monitoring and metrics
- `metrics` - Prometheus metrics
- `high-priority` - Critical business operations
- `resource-intensive` - Very resource-intensive operations

### Examples

```bash
# Test only query operations
locust -f locustfile.py --host=http://localhost:8000 --tags query --headless

# Test only health and monitoring
locust -f locustfile.py --host=http://localhost:8000 --tags health,monitoring --headless

# Exclude resource-intensive operations
locust -f locustfile.py --host=http://localhost:8000 --exclude-tags resource-intensive --headless

# Test high-priority operations only
locust -f locustfile.py --host=http://localhost:8000 --tags high-priority --headless
```

## Next Steps

After completing load tests:

1. **Task 43.2**: Profile System Performance and Identify Bottlenecks
   - Analyze load test results
   - Use profiling tools (cProfile, py-spy)
   - Monitor Celery worker queues
   - Check database slow queries

2. **Task 43.3**: Optimize and Re-Test
   - Implement identified optimizations
   - Re-run load tests
   - Compare before/after metrics
   - Iterate until performance targets met

## Additional Resources

- [Locust Documentation](https://docs.locust.io/)
- [Empire Monitoring Stack](../../monitoring/INTEGRATION_GUIDE.md)
- [Prometheus Metrics](https://prometheus.io/docs/concepts/metric_types/)
- [Task 43 Requirements](../../.taskmaster/tasks/task-43.md)

---

**Created**: 2025-01-15
**Task**: 43.1 - Load Testing Infrastructure
**Version**: 1.0
