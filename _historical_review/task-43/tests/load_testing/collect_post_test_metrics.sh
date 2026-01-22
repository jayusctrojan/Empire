#!/bin/bash
# Collect Post-Test Metrics for Empire v7.3
# Task 43.2 - Performance Profiling and Bottleneck Identification

set -e

# Configuration
HOST="${1:-http://localhost:8000}"
OUTPUT_DIR="reports/post_test"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "======================================================================"
echo "Empire v7.3 - Post-Test Metrics Collection"
echo "======================================================================"
echo "Host: $HOST"
echo "Output: $OUTPUT_DIR"
echo "Timestamp: $TIMESTAMP"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "1. Collecting post-test Prometheus metrics..."
curl -s "$HOST/monitoring/metrics" > "$OUTPUT_DIR/prometheus_post_test_${TIMESTAMP}.txt" 2>/dev/null || {
    echo "   ⚠️  Failed to collect Prometheus metrics from $HOST/monitoring/metrics"
    echo "   This is expected if server is not running or metrics endpoint is different"
}
echo "   ✅ Prometheus metrics saved"
echo ""

echo "2. Checking health endpoints after load test..."
for endpoint in "/health" "/api/query/health" "/api/crewai/health" "/api/monitoring/health"; do
    echo "   Testing: $HOST$endpoint"
    response=$(curl -s -w "\n%{http_code}" "$HOST$endpoint" 2>/dev/null || echo "ERROR")

    if [ "$response" != "ERROR" ]; then
        http_code=$(echo "$response" | tail -n 1)
        body=$(echo "$response" | head -n -1)

        if [ "$http_code" = "200" ]; then
            echo "      ✅ Status: $http_code"
            echo "$body" | jq '.' 2>/dev/null || echo "$body"
        else
            echo "      ⚠️  Status: $http_code"
        fi
    else
        echo "      ❌ Connection failed"
    fi
    echo ""
done

echo "3. Collecting post-test system resources..."
{
    echo "=== CPU and Memory After Load Test ==="
    top -l 1 -n 0 | head -20
    echo ""
    echo "=== Disk Usage ==="
    df -h
    echo ""
    echo "=== Network Connections ==="
    netstat -an | grep LISTEN | grep -E ':(8000|6379|7687|5432)' || echo "No relevant ports listening"
} > "$OUTPUT_DIR/system_resources_${TIMESTAMP}.txt"
echo "   ✅ System resources captured"
echo ""

echo "4. Checking database connections after load..."
{
    echo "=== Redis Info (Post-Test) ==="
    redis-cli INFO stats 2>/dev/null || echo "Redis CLI not available or not running"
    echo ""
    echo "=== Redis Memory Stats ==="
    redis-cli INFO memory 2>/dev/null || echo "Redis CLI not available"
    echo ""
    echo "=== Neo4j Status ==="
    docker ps | grep neo4j 2>/dev/null || echo "Neo4j Docker container not found"
    echo ""
    echo "=== Neo4j Connection Stats ==="
    docker exec empire-neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-password}" \
        "CALL dbms.listConnections() YIELD connectionId, connector, username, userAgent RETURN count(*) as active_connections" \
        2>/dev/null || echo "Could not query Neo4j connections"
} > "$OUTPUT_DIR/database_status_${TIMESTAMP}.txt"
echo "   ✅ Database status captured"
echo ""

echo "5. Checking Celery workers after load..."
{
    echo "=== Celery Active Tasks (Post-Test) ==="
    celery -A app.celery_app inspect active 2>/dev/null || echo "Celery not running or not accessible"
    echo ""
    echo "=== Celery Reserved Tasks ==="
    celery -A app.celery_app inspect reserved 2>/dev/null || echo "Celery not running"
    echo ""
    echo "=== Celery Stats ==="
    celery -A app.celery_app inspect stats 2>/dev/null || echo "Celery not running or not accessible"
    echo ""
    echo "=== Celery Worker Memory ==="
    ps aux | grep "celery worker" | grep -v grep || echo "No Celery workers found"
} > "$OUTPUT_DIR/celery_status_${TIMESTAMP}.txt"
echo "   ✅ Celery status captured"
echo ""

echo "6. Collecting Locust test results..."
if [ -f "reports/load_test_light_report.html" ]; then
    cp reports/load_test_light_*.csv "$OUTPUT_DIR/" 2>/dev/null || echo "   ⚠️  CSV files not found"
    cp reports/load_test_light_report.html "$OUTPUT_DIR/load_test_report_${TIMESTAMP}.html" 2>/dev/null || echo "   ⚠️  HTML report not found"
    echo "   ✅ Locust reports copied"
else
    echo "   ⚠️  No Locust reports found (expected if test hasn't been run)"
fi
echo ""

echo "7. Creating post-test summary..."
{
    echo "======================================================================"
    echo "Empire v7.3 - Post-Test Metrics Summary"
    echo "======================================================================"
    echo "Timestamp: $TIMESTAMP"
    echo "Host: $HOST"
    echo ""
    echo "Files created:"
    ls -lh "$OUTPUT_DIR"/*_${TIMESTAMP}.* 2>/dev/null || echo "No files created"
    echo ""
    echo "Next steps:"
    echo "  1. Compare baseline vs post-test metrics"
    echo "  2. Run analysis: python analyze_performance.py"
    echo "  3. Identify bottlenecks from reports"
    echo "  4. Implement optimizations"
    echo ""
} | tee "$OUTPUT_DIR/post_test_summary_${TIMESTAMP}.txt"

echo "======================================================================"
echo "Post-Test Metrics Collection Complete"
echo "======================================================================"
echo ""
echo "Output directory: $OUTPUT_DIR"
echo ""
echo "To compare with baseline:"
echo "  python analyze_performance.py reports/baseline reports/post_test"
echo ""
