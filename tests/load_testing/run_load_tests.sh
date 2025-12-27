#!/bin/bash
# ============================================================================
# Empire v7.3 Load Testing Runner
# Task 7.3: Set up Locust for load testing API endpoints
# ============================================================================
#
# PURPOSE: Run load tests with different profiles and collect baseline metrics
#
# USAGE:
#   ./run_load_tests.sh <profile> [host]
#   ./run_load_tests.sh light                           # Local, light profile
#   ./run_load_tests.sh moderate https://jb-empire-api.onrender.com  # Production, moderate
#   ./run_load_tests.sh heavy                           # Local, heavy profile
#   ./run_load_tests.sh all                             # Run all profiles sequentially
#   ./run_load_tests.sh baseline                        # Run baseline collection (all profiles)
#
# REQUIREMENTS:
#   - Python 3.8+
#   - locust installed (pip install locust)
#   - reports/ directory (created automatically)
#
# ============================================================================

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default configuration
DEFAULT_HOST="http://localhost:8000"
REPORTS_DIR="$SCRIPT_DIR/reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Checking requirements..."

    if ! command -v locust &> /dev/null; then
        log_error "locust is not installed"
        log_info "Install with: pip install locust"
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        log_error "python3 is not installed"
        exit 1
    fi

    # Create reports directory if it doesn't exist
    mkdir -p "$REPORTS_DIR"

    log_success "Requirements check passed"
}

check_target_health() {
    local host="$1"
    log_info "Checking target health: $host/health"

    local status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$host/health" 2>/dev/null || echo "000")

    if [[ "$status" == "200" ]]; then
        log_success "Target is healthy"
        return 0
    else
        log_warning "Target health check returned HTTP $status"
        read -p "Continue anyway? (y/n): " confirm
        if [[ "$confirm" != "y" ]]; then
            log_info "Aborting"
            exit 0
        fi
    fi
}

# ============================================================================
# Load Test Functions
# ============================================================================

run_load_test() {
    local profile="$1"
    local host="$2"
    local conf_file="locust_${profile}.conf"

    if [[ ! -f "$conf_file" ]]; then
        log_error "Configuration file not found: $conf_file"
        exit 1
    fi

    log_info "=========================================="
    log_info "Running load test: $profile profile"
    log_info "Host: $host"
    log_info "Config: $conf_file"
    log_info "=========================================="

    # Update HTML and CSV output paths with timestamp
    local html_report="$REPORTS_DIR/load_test_${profile}_${TIMESTAMP}.html"
    local csv_prefix="$REPORTS_DIR/load_test_${profile}_${TIMESTAMP}"

    # Run locust with configuration file
    locust \
        --config "$conf_file" \
        --host "$host" \
        --html "$html_report" \
        --csv "$csv_prefix" \
        2>&1 | tee "$REPORTS_DIR/load_test_${profile}_${TIMESTAMP}.log"

    local exit_code=${PIPESTATUS[0]}

    if [[ $exit_code -eq 0 ]]; then
        log_success "Load test completed: $profile"
        log_info "Reports:"
        log_info "  HTML: $html_report"
        log_info "  CSV: ${csv_prefix}_stats.csv"
        log_info "  Log: $REPORTS_DIR/load_test_${profile}_${TIMESTAMP}.log"
    else
        log_error "Load test failed with exit code: $exit_code"
        return $exit_code
    fi

    echo ""
}

run_all_profiles() {
    local host="$1"

    log_info "Running all load test profiles..."

    local profiles=("light" "moderate" "heavy")

    for profile in "${profiles[@]}"; do
        run_load_test "$profile" "$host"

        # Wait between profiles
        if [[ "$profile" != "${profiles[-1]}" ]]; then
            log_info "Waiting 60 seconds before next profile..."
            sleep 60
        fi
    done

    log_success "All load tests completed"
    generate_summary
}

run_baseline_collection() {
    local host="$1"

    log_info "=========================================="
    log_info "Running baseline collection"
    log_info "This will run all profiles and generate"
    log_info "baseline metrics documentation"
    log_info "=========================================="

    # Run all profiles
    run_all_profiles "$host"

    # Generate baseline report
    generate_baseline_report
}

# ============================================================================
# Report Generation
# ============================================================================

generate_summary() {
    local summary_file="$REPORTS_DIR/load_test_summary_${TIMESTAMP}.md"

    log_info "Generating summary report..."

    cat > "$summary_file" << EOF
# Empire v7.3 Load Test Summary
Date: $(date '+%Y-%m-%d %H:%M:%S')
Timestamp: $TIMESTAMP

## Test Configuration

| Profile | Users | Spawn Rate | Duration |
|---------|-------|------------|----------|
| Light | 10 | 1/s | 5m |
| Moderate | 50 | 5/s | 10m |
| Heavy | 120 | 10/s | 15m |

## Reports Generated

$(ls -la "$REPORTS_DIR"/*_${TIMESTAMP}* 2>/dev/null | awk '{print "- " $NF}')

## Next Steps

1. Review HTML reports for detailed metrics
2. Compare against baseline metrics
3. Identify performance bottlenecks
4. Document any regressions

## Quick View Commands

\`\`\`bash
# View stats CSV
cat $REPORTS_DIR/load_test_light_${TIMESTAMP}_stats.csv | column -t -s,

# Open HTML report (macOS)
open $REPORTS_DIR/load_test_light_${TIMESTAMP}.html
\`\`\`
EOF

    log_success "Summary report: $summary_file"
}

generate_baseline_report() {
    local baseline_file="$REPORTS_DIR/baseline_metrics_${TIMESTAMP}.md"

    log_info "Generating baseline metrics report..."

    cat > "$baseline_file" << EOF
# Empire v7.3 Performance Baseline Metrics
Generated: $(date '+%Y-%m-%d %H:%M:%S')
Timestamp: $TIMESTAMP

## Overview

This document contains baseline performance metrics for Empire v7.3 API endpoints.
These metrics should be used as a reference for performance regression testing.

## Test Environment

- **Target**: ${HOST:-$DEFAULT_HOST}
- **Test Date**: $(date '+%Y-%m-%d')
- **Test Profiles**: Light, Moderate, Heavy

## Baseline Metrics

### Light Load (10 users)
$(extract_metrics "light")

### Moderate Load (50 users)
$(extract_metrics "moderate")

### Heavy Load (120 users)
$(extract_metrics "heavy")

## Success Criteria

Based on these baselines, the following thresholds are recommended:

| Metric | Warning | Critical |
|--------|---------|----------|
| Error Rate | > 1% | > 5% |
| P95 Latency | > 10s | > 30s |
| P99 Latency | > 30s | > 60s |
| Requests/sec | < 50% baseline | < 25% baseline |

## Usage

Compare future load test results against these baselines:

\`\`\`bash
# Run load test
./run_load_tests.sh moderate

# Compare with baseline
diff -y $baseline_file latest_report.md
\`\`\`

## Notes

- These baselines represent production-like conditions
- Seasonal variations may affect actual production performance
- Re-run baselines after major infrastructure changes
EOF

    log_success "Baseline report: $baseline_file"
}

extract_metrics() {
    local profile="$1"
    local stats_file="$REPORTS_DIR/load_test_${profile}_${TIMESTAMP}_stats.csv"

    if [[ -f "$stats_file" ]]; then
        echo ""
        echo "\`\`\`"
        head -20 "$stats_file" | column -t -s,
        echo "\`\`\`"
    else
        echo "(Stats file not found)"
    fi
}

# ============================================================================
# Interactive Mode
# ============================================================================

run_interactive() {
    echo ""
    echo "Empire v7.3 Load Testing"
    echo "========================"
    echo ""
    echo "Select a profile:"
    echo "  1) Light (10 users, 5 min)"
    echo "  2) Moderate (50 users, 10 min)"
    echo "  3) Heavy (120 users, 15 min)"
    echo "  4) Spike (200 users, 5 min)"
    echo "  5) All profiles (sequential)"
    echo "  6) Baseline collection"
    echo "  7) Interactive mode (Locust web UI)"
    echo ""
    read -p "Enter selection [1-7]: " selection

    local profile
    case "$selection" in
        1) profile="light" ;;
        2) profile="moderate" ;;
        3) profile="heavy" ;;
        4) profile="spike" ;;
        5)
            read -p "Enter target host [$DEFAULT_HOST]: " host
            host="${host:-$DEFAULT_HOST}"
            run_all_profiles "$host"
            return
            ;;
        6)
            read -p "Enter target host [$DEFAULT_HOST]: " host
            host="${host:-$DEFAULT_HOST}"
            run_baseline_collection "$host"
            return
            ;;
        7)
            read -p "Enter target host [$DEFAULT_HOST]: " host
            host="${host:-$DEFAULT_HOST}"
            log_info "Starting Locust web UI at http://localhost:8089"
            locust -f locustfile.py --host "$host"
            return
            ;;
        *)
            log_error "Invalid selection"
            exit 1
            ;;
    esac

    read -p "Enter target host [$DEFAULT_HOST]: " host
    host="${host:-$DEFAULT_HOST}"

    check_target_health "$host"
    run_load_test "$profile" "$host"
}

# ============================================================================
# Main
# ============================================================================

print_usage() {
    cat << EOF
Usage: $0 <command> [host]

Commands:
  light             Run light load test (10 users)
  moderate          Run moderate load test (50 users)
  heavy             Run heavy load test (120 users)
  spike             Run spike test (200 users)
  all               Run all profiles sequentially
  baseline          Run baseline collection and documentation
  interactive       Interactive mode (choose profile)
  web               Start Locust web UI for manual testing

Options:
  [host]            Target host (default: $DEFAULT_HOST)

Examples:
  $0 light
  $0 moderate https://jb-empire-api.onrender.com
  $0 all
  $0 baseline
  $0 web

Environment Variables:
  LOCUST_HOST       Override default host

EOF
}

main() {
    check_requirements

    if [[ $# -eq 0 ]]; then
        run_interactive
        exit 0
    fi

    local command="$1"
    local host="${2:-$DEFAULT_HOST}"

    # Check for LOCUST_HOST environment variable
    host="${LOCUST_HOST:-$host}"

    case "$command" in
        light|moderate|heavy|spike)
            check_target_health "$host"
            run_load_test "$command" "$host"
            ;;
        all)
            check_target_health "$host"
            run_all_profiles "$host"
            ;;
        baseline)
            check_target_health "$host"
            run_baseline_collection "$host"
            ;;
        interactive)
            run_interactive
            ;;
        web)
            log_info "Starting Locust web UI at http://localhost:8089"
            locust -f locustfile.py --host "$host"
            ;;
        --help|-h)
            print_usage
            ;;
        *)
            log_error "Unknown command: $command"
            print_usage
            exit 1
            ;;
    esac
}

main "$@"
