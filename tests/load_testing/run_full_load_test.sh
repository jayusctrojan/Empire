#!/bin/bash
# Complete Load Testing Workflow for Empire v7.3
# Task 43.2 - Performance Profiling and Bottleneck Identification
#
# This script orchestrates the full load testing workflow:
# 1. Collect baseline metrics
# 2. Run Locust load test
# 3. Collect post-test metrics
# 4. Analyze and compare results
# 5. Generate recommendations

set -e

# Configuration
HOST="${1:-http://localhost:8000}"
TEST_PROFILE="${2:-light}"  # light, moderate, heavy, production
RUN_ANALYSIS="${3:-yes}"

echo "======================================================================"
echo "Empire v7.3 - Complete Load Testing Workflow"
echo "======================================================================"
echo "Host: $HOST"
echo "Test Profile: $TEST_PROFILE"
echo "Auto-Analyze: $RUN_ANALYSIS"
echo ""

# Validate test profile
case "$TEST_PROFILE" in
    light|moderate|heavy|production)
        echo "✅ Valid test profile: $TEST_PROFILE"
        ;;
    *)
        echo "❌ Invalid test profile: $TEST_PROFILE"
        echo "   Valid options: light, moderate, heavy, production"
        exit 1
        ;;
esac
echo ""

# Check if FastAPI is running (skip for production)
if [ "$TEST_PROFILE" != "production" ]; then
    echo "Checking if FastAPI is running at $HOST..."
    response=$(curl -s -o /dev/null -w "%{http_code}" "$HOST/health" 2>/dev/null || echo "000")

    if [ "$response" = "200" ]; then
        echo "   ✅ FastAPI is running"
    else
        echo "   ❌ FastAPI is not running at $HOST (got HTTP $response)"
        echo ""
        echo "Please start FastAPI before running load tests:"
        echo "  uvicorn app.main:app --reload --port 8000"
        echo ""
        exit 1
    fi
fi
echo ""

# Step 1: Collect Baseline Metrics
echo "======================================================================"
echo "Step 1: Collecting Baseline Metrics"
echo "======================================================================"
./collect_baseline_metrics.sh "$HOST"
echo ""

# Wait for system to stabilize
echo "Waiting 10 seconds for system to stabilize..."
sleep 10
echo ""

# Step 2: Run Load Test
echo "======================================================================"
echo "Step 2: Running Load Test (Profile: $TEST_PROFILE)"
echo "======================================================================"

CONFIG_FILE="locust_${TEST_PROFILE}.conf"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $CONFIG_FILE"
    exit 1
fi

echo "Using configuration: $CONFIG_FILE"
echo ""

# Override host if provided
if [ "$TEST_PROFILE" != "production" ]; then
    echo "Starting Locust load test..."
    locust -f locustfile.py \
        --config="$CONFIG_FILE" \
        --host="$HOST" \
        --headless \
        --html="reports/load_test_${TEST_PROFILE}_report_$(date +%Y%m%d_%H%M%S).html" \
        --csv="reports/load_test_${TEST_PROFILE}_$(date +%Y%m%d_%H%M%S)"
else
    echo "Starting Locust load test against production..."
    locust -f locustfile.py \
        --config="$CONFIG_FILE" \
        --headless \
        --html="reports/load_test_production_report_$(date +%Y%m%d_%H%M%S).html" \
        --csv="reports/load_test_production_$(date +%Y%m%d_%H%M%S)"
fi

echo ""
echo "✅ Load test completed"
echo ""

# Wait for system to settle
echo "Waiting 15 seconds for system to settle..."
sleep 15
echo ""

# Step 3: Collect Post-Test Metrics
echo "======================================================================"
echo "Step 3: Collecting Post-Test Metrics"
echo "======================================================================"
./collect_post_test_metrics.sh "$HOST"
echo ""

# Step 4: Analyze Results
if [ "$RUN_ANALYSIS" = "yes" ]; then
    echo "======================================================================"
    echo "Step 4: Analyzing Performance Results"
    echo "======================================================================"

    if command -v python3 &> /dev/null; then
        python3 analyze_performance.py reports/baseline reports/post_test
    else
        echo "⚠️  Python 3 not found, skipping automated analysis"
        echo "   You can manually run: python3 analyze_performance.py reports/baseline reports/post_test"
    fi
else
    echo "======================================================================"
    echo "Step 4: Skipping Analysis (RUN_ANALYSIS=no)"
    echo "======================================================================"
    echo ""
    echo "To analyze results manually, run:"
    echo "  python3 analyze_performance.py reports/baseline reports/post_test"
fi

echo ""
echo "======================================================================"
echo "Load Testing Workflow Complete!"
echo "======================================================================"
echo ""
echo "Results available in:"
echo "  - Baseline metrics: reports/baseline/"
echo "  - Post-test metrics: reports/post_test/"
echo "  - Locust reports: reports/load_test_${TEST_PROFILE}_*.html"
echo "  - Performance analysis: reports/performance_analysis_*.json"
echo ""
echo "Next steps:"
echo "  1. Review the performance analysis report"
echo "  2. Check Locust HTML report for detailed statistics"
echo "  3. Implement recommended optimizations"
echo "  4. Re-run tests to validate improvements"
echo ""
echo "To run analysis again:"
echo "  python3 analyze_performance.py reports/baseline reports/post_test"
echo ""
echo "To view Locust report:"
echo "  open reports/load_test_${TEST_PROFILE}_report_*.html"
echo ""
