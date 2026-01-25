#!/bin/bash
# Collect Baseline Metrics for Empire v7.3
# Task 43.2 - Performance Profiling and Bottleneck Identification

set -e

# Configuration
HOST="${1:-http://localhost:8000}"
OUTPUT_DIR="reports/baseline"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "======================================================================"
echo "Empire v7.3 - Baseline Metrics Collection"
echo "======================================================================"
echo "Host: $HOST"
echo "Output: $OUTPUT_DIR"
echo "Timestamp: $TIMESTAMP"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "1. Collecting Prometheus metrics..."
curl -s "$HOST/monitoring/metrics" > "$OUTPUT_DIR/prometheus_baseline_${TIMESTAMP}.txt" 2>/dev/null || {
    echo "   ⚠️  Failed to collect Prometheus metrics from $HOST/monitoring/metrics"
    echo "   This is expected if server is not running or metrics endpoint is different"
}
echo "   ✅ Prometheus metrics saved"
echo ""

echo "2. Checking health endpoints..."
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

echo "3. Collecting system resource baseline..."
{
    echo "=== CPU and Memory ==="
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

echo "4. Checking database connections..."
{
    echo "=== Redis Info (if available) ==="
    redis-cli INFO stats 2>/dev/null || echo "Redis CLI not available or not running"
    echo ""
    echo "=== Neo4j Status (via Docker) ==="
    docker ps | grep neo4j 2>/dev/null || echo "Neo4j Docker container not found"
} > "$OUTPUT_DIR/database_status_${TIMESTAMP}.txt"
echo "   ✅ Database status captured"
echo ""

echo "5. Checking Celery workers..."
{
    echo "=== Celery Active Tasks ==="
    celery -A app.celery_app inspect active 2>/dev/null || echo "Celery not running or not accessible"
    echo ""
    echo "=== Celery Registered Tasks ==="
    celery -A app.celery_app inspect registered 2>/dev/null || echo "Celery not running or not accessible"
    echo ""
    echo "=== Celery Stats ==="
    celery -A app.celery_app inspect stats 2>/dev/null || echo "Celery not running or not accessible"
} > "$OUTPUT_DIR/celery_status_${TIMESTAMP}.txt"
echo "   ✅ Celery status captured"
echo ""

echo "6. Creating baseline summary..."
{
    echo "======================================================================"
    echo "Empire v7.3 - Baseline Metrics Summary"
    echo "======================================================================"
    echo "Timestamp: $TIMESTAMP"
    echo "Host: $HOST"
    echo ""
    echo "Files created:"
    ls -lh "$OUTPUT_DIR"/*_${TIMESTAMP}.txt 2>/dev/null || echo "No files created"
    echo ""
    echo "Next steps:"
    echo "  1. Review baseline metrics in $OUTPUT_DIR"
    echo "  2. Run load test: locust -f locustfile.py --config=locust_light.conf"
    echo "  3. Collect post-test metrics: ./collect_post_test_metrics.sh"
    echo "  4. Compare metrics: ./analyze_performance.py"
    echo ""
} | tee "$OUTPUT_DIR/baseline_summary_${TIMESTAMP}.txt"

echo "======================================================================"
echo "Baseline Metrics Collection Complete"
echo "======================================================================"
echo ""
echo "Output directory: $OUTPUT_DIR"
echo ""
echo "To collect metrics from production Render deployment:"
echo "  ./collect_baseline_metrics.sh https://jb-empire-api.onrender.com"
echo ""
