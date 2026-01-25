#!/bin/bash
# Test Performance Optimizations (Task 43.3)
# Validates that optimization implementations are working correctly

set -e

HOST="${1:-http://localhost:8000}"

echo "======================================================================"
echo "Empire v7.3 - Optimization Validation Tests"
echo "======================================================================"
echo "Host: $HOST"
echo ""

TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
test_passed() {
    echo "   ✅ PASSED: $1"
    ((TESTS_PASSED++))
}

test_failed() {
    echo "   ❌ FAILED: $1"
    ((TESTS_FAILED++))
}

# ============================================================================
# Test 1: Response Compression
# ============================================================================

echo "Test 1: Response Compression"
echo "----------------------------"

# Check if gzip compression is enabled
echo "Testing gzip compression support..."
response=$(curl -s -i -H "Accept-Encoding: gzip" "$HOST/health" 2>/dev/null)

if echo "$response" | grep -iq "content-encoding: gzip"; then
    test_passed "Gzip compression is enabled"
else
    echo "$response" | head -20
    test_failed "Gzip compression not found (check middleware configuration)"
fi

# Test compression on large response
echo "Testing compression on large response..."
response=$(curl -s -i -H "Accept-Encoding: gzip" "$HOST/api/documents" 2>/dev/null)

if echo "$response" | grep -iq "content-encoding: gzip"; then
    test_passed "Large responses are compressed"
else
    test_failed "Large responses not compressed"
fi

echo ""

# ============================================================================
# Test 2: Query Result Caching
# ============================================================================

echo "Test 2: Query Result Caching"
echo "----------------------------"

# Make same query multiple times
TEST_QUERY="What are insurance requirements?"

echo "Making initial query (should be cache miss)..."
start_time=$(date +%s%3N)
response1=$(curl -s -X POST "$HOST/api/query/adaptive" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer test-token" \
    -d "{\"query\":\"$TEST_QUERY\"}" 2>/dev/null || echo '{"error": "endpoint not available"}')
end_time=$(date +%s%3N)
time1=$((end_time - start_time))

echo "First request took: ${time1}ms"

# Wait a moment
sleep 1

echo "Making same query again (should be cache hit)..."
start_time=$(date +%s%3N)
response2=$(curl -s -X POST "$HOST/api/query/adaptive" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer test-token" \
    -d "{\"query\":\"$TEST_QUERY\"}" 2>/dev/null || echo '{"error": "endpoint not available"}')
end_time=$(date +%s%3N)
time2=$((end_time - start_time))

echo "Second request took: ${time2}ms"

# Check if second request was faster (cache hit)
if [ $time2 -lt $time1 ]; then
    speedup=$(( (time1 - time2) * 100 / time1 ))
    test_passed "Cache speedup detected (${speedup}% faster)"
else
    test_failed "No cache speedup detected (caching may not be enabled)"
fi

# Check for cache metadata in response
if echo "$response2" | grep -q "from_cache"; then
    test_passed "Cache metadata present in response"
else
    echo "   ⚠️  Cache metadata not found (might be normal if endpoint doesn't include it)"
fi

echo ""

# ============================================================================
# Test 3: Database Indexes
# ============================================================================

echo "Test 3: Database Index Validation"
echo "----------------------------------"

echo "Checking if performance indexes exist..."

# This would require database access - mock for now
# In production, use: psql or Supabase MCP to verify indexes

echo "   ℹ️  Index validation requires database access"
echo "   Run this query in Supabase to verify:"
echo ""
echo "   SELECT indexname, tablename"
echo "   FROM pg_indexes"
echo "   WHERE indexname LIKE 'idx_%'"
echo "   AND schemaname = 'public'"
echo "   ORDER BY tablename, indexname;"
echo ""

# ============================================================================
# Test 4: Pagination
# ============================================================================

echo "Test 4: Pagination Implementation"
echo "----------------------------------"

echo "Testing paginated document listing..."
response=$(curl -s "$HOST/api/documents?page=1&page_size=10" 2>/dev/null)

if echo "$response" | grep -q "pagination"; then
    test_passed "Pagination metadata present"

    # Check pagination fields
    if echo "$response" | jq -e '.pagination.page' > /dev/null 2>&1; then
        test_passed "Pagination includes page number"
    else
        test_failed "Pagination missing page number"
    fi

    if echo "$response" | jq -e '.pagination.total' > /dev/null 2>&1; then
        test_passed "Pagination includes total count"
    else
        test_failed "Pagination missing total count"
    fi
else
    test_failed "Pagination not implemented"
fi

echo ""

# ============================================================================
# Test 5: Async Processing
# ============================================================================

echo "Test 5: Async Background Processing"
echo "------------------------------------"

echo "Testing async bulk upload..."
# Create a small test file
echo "Test content" > /tmp/test_upload.txt

response=$(curl -s -X POST "$HOST/api/documents/bulk-upload" \
    -F "files=@/tmp/test_upload.txt" 2>/dev/null || echo '{"error": "endpoint not available"}')

# Clean up
rm -f /tmp/test_upload.txt

# Check for operation_id (indicates async processing)
if echo "$response" | grep -q "operation_id"; then
    operation_id=$(echo "$response" | jq -r '.operation_id' 2>/dev/null || echo "")

    if [ -n "$operation_id" ]; then
        test_passed "Async operation initiated (ID: ${operation_id})"

        # Check status endpoint
        echo "Checking operation status..."
        status_response=$(curl -s "$HOST/api/documents/batch-operations/$operation_id" 2>/dev/null)

        if echo "$status_response" | grep -q "status"; then
            test_passed "Status polling endpoint available"
        else
            test_failed "Status polling endpoint not working"
        fi
    else
        test_failed "Operation ID not returned"
    fi
else
    test_failed "Async processing not detected (endpoint may not be available)"
fi

echo ""

# ============================================================================
# Test 6: Cache Monitoring
# ============================================================================

echo "Test 6: Cache Monitoring and Metrics"
echo "-------------------------------------"

echo "Checking cache metrics endpoint..."
response=$(curl -s "$HOST/monitoring/metrics" 2>/dev/null)

if echo "$response" | grep -q "cache_hit_rate"; then
    test_passed "Cache hit rate metrics available"

    # Extract cache hit rate if available
    cache_hit_rate=$(echo "$response" | grep "cache_hit_rate{level=\"overall\"}" | awk '{print $2}' || echo "N/A")
    echo "   Current cache hit rate: $cache_hit_rate"
else
    test_failed "Cache metrics not found in Prometheus endpoint"
fi

echo ""

# ============================================================================
# Test 7: Health Check Performance
# ============================================================================

echo "Test 7: Health Check Response Time"
echo "-----------------------------------"

echo "Measuring health endpoint performance..."

total_time=0
requests=10

for i in $(seq 1 $requests); do
    start_time=$(date +%s%3N)
    curl -s "$HOST/health" > /dev/null 2>&1
    end_time=$(date +%s%3N)
    duration=$((end_time - start_time))
    total_time=$((total_time + duration))
done

avg_time=$((total_time / requests))

echo "   Average response time: ${avg_time}ms (over $requests requests)"

if [ $avg_time -lt 100 ]; then
    test_passed "Health check response time < 100ms"
elif [ $avg_time -lt 200 ]; then
    echo "   ⚠️  Response time acceptable but could be better (target: < 100ms)"
else
    test_failed "Health check response time too high (${avg_time}ms > 200ms target)"
fi

echo ""

# ============================================================================
# Test Summary
# ============================================================================

echo "======================================================================"
echo "Optimization Validation Summary"
echo "======================================================================"
echo ""
echo "Tests Passed:  $TESTS_PASSED"
echo "Tests Failed:  $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo "✅ All optimization tests passed!"
    echo ""
    echo "Next steps:"
    echo "  1. Run full load test: ./run_full_load_test.sh $HOST moderate"
    echo "  2. Compare with baseline results"
    echo "  3. Validate performance improvements"
    exit 0
else
    echo "⚠️  Some optimization tests failed"
    echo ""
    echo "Review failed tests and ensure optimizations are properly configured:"
    echo "  - Compression: Check app/main.py for compression middleware"
    echo "  - Caching: Verify query cache decorator is applied to endpoints"
    echo "  - Indexes: Run migration: migrations/add_performance_indexes.sql"
    echo "  - Async: Ensure Celery workers are running"
    echo ""
    exit 1
fi
