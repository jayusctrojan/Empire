#!/bin/bash
#
# Empire v7.3 - Graceful Stop Script
# Gracefully stops all Empire services
#
# Usage:
#   ./stop_empire.sh          # Graceful shutdown
#   ./stop_empire.sh --force  # Force kill all processes
#   ./stop_empire.sh --status # Check status only
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'
DIM='\033[2m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PID_DIR="${PROJECT_ROOT}/.pids"

# Default options
FORCE_KILL=false
STATUS_ONLY=false
DRAIN_TIMEOUT=30

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force|-f)
            FORCE_KILL=true
            shift
            ;;
        --status|-s)
            STATUS_ONLY=true
            shift
            ;;
        --timeout)
            DRAIN_TIMEOUT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Empire v7.3 Stop Script"
            echo ""
            echo "Usage: ./stop_empire.sh [options]"
            echo ""
            echo "Options:"
            echo "  --force, -f    Force kill all processes"
            echo "  --status, -s   Check status only, don't stop"
            echo "  --timeout N    Set drain timeout in seconds (default: 30)"
            echo "  -h, --help     Show this help message"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Print banner
print_banner() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║             Empire v7.3 - Shutting Down                ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Print step
print_step() {
    echo -e "${BLUE}▸${NC} $1"
}

# Print success
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Print warning
print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Print error
print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if a process is running
is_running() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Get PID from file
get_pid() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        cat "$pid_file"
    else
        echo ""
    fi
}

# Show status
show_status() {
    echo -e "${BOLD}Service Status:${NC}"
    echo ""

    # FastAPI
    if is_running "$PID_DIR/fastapi.pid"; then
        local pid=$(get_pid "$PID_DIR/fastapi.pid")
        echo -e "  ${GREEN}●${NC} FastAPI      Running (PID: $pid)"
    else
        echo -e "  ${DIM}○${NC} FastAPI      Not running"
    fi

    # Celery
    if is_running "$PID_DIR/celery.pid"; then
        local pid=$(get_pid "$PID_DIR/celery.pid")
        echo -e "  ${GREEN}●${NC} Celery       Running (PID: $pid)"
    else
        echo -e "  ${DIM}○${NC} Celery       Not running"
    fi

    # Check for any orphaned processes
    local orphaned_uvicorn=$(pgrep -f "uvicorn app.main:app" 2>/dev/null || true)
    local orphaned_celery=$(pgrep -f "celery.*app.celery_app" 2>/dev/null || true)

    if [ -n "$orphaned_uvicorn" ] || [ -n "$orphaned_celery" ]; then
        echo ""
        echo -e "${YELLOW}Orphaned processes detected:${NC}"
        if [ -n "$orphaned_uvicorn" ]; then
            echo -e "  - uvicorn: $orphaned_uvicorn"
        fi
        if [ -n "$orphaned_celery" ]; then
            echo -e "  - celery: $orphaned_celery"
        fi
    fi

    echo ""
}

# Prepare shutdown (notify API)
prepare_shutdown() {
    print_step "Preparing for shutdown..."

    # Try to notify FastAPI about shutdown
    local response=$(curl -s -X POST "http://localhost:8000/api/preflight/shutdown/prepare" 2>/dev/null || echo "")

    if [ -n "$response" ]; then
        print_success "Shutdown prepared - no new requests accepted"
    else
        print_warning "Could not notify API (may already be stopped)"
    fi
}

# Drain in-flight requests
drain_requests() {
    print_step "Draining in-flight requests (timeout: ${DRAIN_TIMEOUT}s)..."

    local start_time=$(date +%s)
    local elapsed=0

    while [ $elapsed -lt $DRAIN_TIMEOUT ]; do
        # Check drain status
        local response=$(curl -s "http://localhost:8000/api/preflight/shutdown/status" 2>/dev/null || echo "")

        if [ -z "$response" ]; then
            # API not responding, assume drained
            break
        fi

        # Check if drained
        local active=$(echo "$response" | grep -o '"active_requests":[0-9]*' | cut -d: -f2 || echo "0")

        if [ "$active" = "0" ]; then
            print_success "All requests drained"
            return 0
        fi

        echo -e "  ${DIM}Active requests: $active (${elapsed}s elapsed)${NC}"
        sleep 2

        elapsed=$(($(date +%s) - start_time))
    done

    if [ $elapsed -ge $DRAIN_TIMEOUT ]; then
        print_warning "Drain timeout reached"
    fi
}

# Stop FastAPI gracefully
stop_fastapi() {
    print_step "Stopping FastAPI..."

    if ! is_running "$PID_DIR/fastapi.pid"; then
        print_warning "FastAPI not running (no PID file)"
        # Check for orphaned processes
        local orphaned=$(pgrep -f "uvicorn app.main:app" 2>/dev/null || true)
        if [ -n "$orphaned" ]; then
            print_warning "Found orphaned uvicorn process: $orphaned"
            if [ "$FORCE_KILL" = true ]; then
                # shellcheck disable=SC2086
                kill -9 $orphaned 2>/dev/null || true
                print_success "Force killed orphaned process(es)"
            fi
        fi
        return 0
    fi

    local pid=$(get_pid "$PID_DIR/fastapi.pid")

    if [ "$FORCE_KILL" = true ]; then
        kill -9 "$pid" 2>/dev/null || true
        rm -f "$PID_DIR/fastapi.pid"
        print_success "FastAPI force killed"
        return 0
    fi

    # Graceful shutdown with SIGTERM
    kill -TERM "$pid" 2>/dev/null || true

    # Wait for process to exit
    local wait_count=0
    while ps -p "$pid" > /dev/null 2>&1; do
        if [ $wait_count -ge 10 ]; then
            print_warning "FastAPI not responding to SIGTERM, sending SIGKILL"
            kill -9 "$pid" 2>/dev/null || true
            break
        fi
        sleep 1
        wait_count=$((wait_count + 1))
    done

    rm -f "$PID_DIR/fastapi.pid"
    print_success "FastAPI stopped"
}

# Stop Celery gracefully
stop_celery() {
    print_step "Stopping Celery worker..."

    if ! is_running "$PID_DIR/celery.pid"; then
        print_warning "Celery not running (no PID file)"
        # Check for orphaned processes
        local orphaned=$(pgrep -f "celery.*app.celery_app" 2>/dev/null || true)
        if [ -n "$orphaned" ]; then
            print_warning "Found orphaned Celery process: $orphaned"
            if [ "$FORCE_KILL" = true ]; then
                kill -9 $orphaned 2>/dev/null || true
                print_success "Force killed orphaned process"
            fi
        fi
        return 0
    fi

    local pid=$(get_pid "$PID_DIR/celery.pid")

    if [ "$FORCE_KILL" = true ]; then
        kill -9 "$pid" 2>/dev/null || true
        rm -f "$PID_DIR/celery.pid"
        print_success "Celery force killed"
        return 0
    fi

    # Graceful shutdown - tell Celery to finish current tasks
    print_step "Waiting for Celery tasks to complete..."

    # Send SIGTERM for graceful shutdown
    kill -TERM "$pid" 2>/dev/null || true

    # Wait for process to exit
    local wait_count=0
    while ps -p "$pid" > /dev/null 2>&1; do
        if [ $wait_count -ge 30 ]; then
            print_warning "Celery not responding, sending SIGKILL"
            kill -9 "$pid" 2>/dev/null || true
            break
        fi
        sleep 1
        wait_count=$((wait_count + 1))
    done

    rm -f "$PID_DIR/celery.pid"
    print_success "Celery stopped"
}

# Stop monitoring stack
stop_monitoring() {
    print_step "Checking monitoring stack..."

    COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.monitoring.yml"
    if [ -f "$COMPOSE_FILE" ]; then
        # Check if any monitoring containers are running
        local running=$(docker-compose -f "$COMPOSE_FILE" ps -q 2>/dev/null || true)
        if [ -n "$running" ]; then
            print_step "Stopping monitoring stack..."
            docker-compose -f "$COMPOSE_FILE" down 2>/dev/null || true
            print_success "Monitoring stack stopped"
        else
            print_warning "Monitoring stack not running"
        fi
    fi
}

# Cleanup
cleanup() {
    print_step "Cleaning up..."

    # Remove stale PID files
    rm -f "$PID_DIR"/*.pid 2>/dev/null || true

    print_success "Cleanup complete"
}

# Print summary
print_summary() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}Empire v7.3 Stopped${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  All services have been stopped."
    echo ""
    echo -e "  To restart: ${BOLD}./scripts/startup/start_empire.sh${NC}"
    echo ""
}

# Main
main() {
    print_banner

    # Status only mode
    if [ "$STATUS_ONLY" = true ]; then
        show_status
        exit 0
    fi

    # Show current status
    show_status

    # Prepare shutdown
    prepare_shutdown

    # Drain requests
    if [ "$FORCE_KILL" = false ]; then
        drain_requests
    fi

    # Stop services in order
    stop_celery
    stop_fastapi
    stop_monitoring

    # Cleanup
    cleanup

    # Summary
    print_summary
}

main "$@"
