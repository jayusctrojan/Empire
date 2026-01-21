#!/bin/bash
#
# Empire v7.3 - Complete Startup Script
# Runs preflight checks and starts all services
#
# Usage:
#   ./start_empire.sh              # Full startup with preflight
#   ./start_empire.sh --skip-preflight  # Skip preflight checks
#   ./start_empire.sh --dev        # Development mode (auto-reload)
#   ./start_empire.sh --no-celery  # Start without Celery workers
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

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/venv"
PID_DIR="${PROJECT_ROOT}/.pids"
LOG_DIR="${PROJECT_ROOT}/logs"

# Default options
SKIP_PREFLIGHT=false
DEV_MODE=false
NO_CELERY=false
START_MONITORING=false
PORT=8000

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-preflight)
            SKIP_PREFLIGHT=true
            shift
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        --no-celery)
            NO_CELERY=true
            shift
            ;;
        --with-monitoring)
            START_MONITORING=true
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Empire v7.3 Startup Script"
            echo ""
            echo "Usage: ./start_empire.sh [options]"
            echo ""
            echo "Options:"
            echo "  --skip-preflight    Skip preflight health checks"
            echo "  --dev               Development mode with auto-reload"
            echo "  --no-celery         Start without Celery workers"
            echo "  --with-monitoring   Start monitoring stack (Prometheus, Grafana)"
            echo "  --port PORT         Set FastAPI port (default: 8000)"
            echo "  -h, --help          Show this help message"
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
    echo -e "${CYAN}║              Empire v7.3 - Starting Up                 ║${NC}"
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

# Create directories
setup_directories() {
    mkdir -p "$PID_DIR"
    mkdir -p "$LOG_DIR"
}

# Activate virtual environment
activate_venv() {
    if [ -d "$VENV_PATH" ]; then
        source "$VENV_PATH/bin/activate"
        print_success "Virtual environment activated"
    else
        print_error "Virtual environment not found at $VENV_PATH"
        print_step "Creating virtual environment..."
        python3 -m venv "$VENV_PATH"
        source "$VENV_PATH/bin/activate"
        pip install -r "$PROJECT_ROOT/requirements.txt"
        print_success "Virtual environment created and dependencies installed"
    fi
}

# Load environment variables
load_env() {
    if [ -f "$PROJECT_ROOT/.env" ]; then
        export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
        print_success "Environment variables loaded"
    else
        print_warning "No .env file found"
    fi
}

# Run preflight checks
run_preflight() {
    print_step "Running preflight checks..."
    echo ""

    cd "$PROJECT_ROOT"

    if python3 "$SCRIPT_DIR/empire_preflight.py"; then
        return 0
    else
        return 1
    fi
}

# Start Docker services (Neo4j, Redis if local)
start_docker_services() {
    print_step "Checking Docker services..."

    # Check if docker-compose file exists
    COMPOSE_FILE="${PROJECT_ROOT}/config/docker/docker-compose.yml"
    if [ ! -f "$COMPOSE_FILE" ]; then
        COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
    fi

    if [ -f "$COMPOSE_FILE" ]; then
        # Check if Neo4j is needed and not running
        if docker ps | grep -q "neo4j"; then
            print_success "Neo4j already running"
        else
            print_step "Starting Neo4j..."
            docker-compose -f "$COMPOSE_FILE" up -d neo4j 2>/dev/null || true
            sleep 5
        fi
    else
        print_warning "No docker-compose.yml found, skipping Docker services"
    fi
}

# Start FastAPI
start_fastapi() {
    print_step "Starting FastAPI..."

    cd "$PROJECT_ROOT"

    if is_running "$PID_DIR/fastapi.pid"; then
        print_warning "FastAPI already running"
        return 0
    fi

    local RELOAD_FLAG=""
    if [ "$DEV_MODE" = true ]; then
        RELOAD_FLAG="--reload"
        print_step "Development mode: auto-reload enabled"
    fi

    # Start uvicorn
    nohup uvicorn app.main:app \
        --host 0.0.0.0 \
        --port "$PORT" \
        $RELOAD_FLAG \
        --log-level info \
        > "$LOG_DIR/fastapi.log" 2>&1 &

    echo $! > "$PID_DIR/fastapi.pid"
    sleep 2

    if is_running "$PID_DIR/fastapi.pid"; then
        print_success "FastAPI started on port $PORT"
    else
        print_error "Failed to start FastAPI"
        cat "$LOG_DIR/fastapi.log" | tail -20
        return 1
    fi
}

# Start Celery worker
start_celery() {
    if [ "$NO_CELERY" = true ]; then
        print_warning "Skipping Celery (--no-celery flag)"
        return 0
    fi

    print_step "Starting Celery worker..."

    cd "$PROJECT_ROOT"

    if is_running "$PID_DIR/celery.pid"; then
        print_warning "Celery already running"
        return 0
    fi

    # Start Celery worker
    nohup celery -A app.celery_app worker \
        --loglevel=info \
        --concurrency=4 \
        > "$LOG_DIR/celery.log" 2>&1 &

    echo $! > "$PID_DIR/celery.pid"
    sleep 3

    if is_running "$PID_DIR/celery.pid"; then
        print_success "Celery worker started"
    else
        print_warning "Celery worker may not have started correctly"
    fi
}

# Start monitoring stack
start_monitoring() {
    if [ "$START_MONITORING" = false ]; then
        return 0
    fi

    print_step "Starting monitoring stack..."

    MONITORING_SCRIPT="${PROJECT_ROOT}/start-monitoring.sh"
    if [ -f "$MONITORING_SCRIPT" ]; then
        bash "$MONITORING_SCRIPT"
        print_success "Monitoring stack started"
    else
        print_warning "Monitoring script not found"
    fi
}

# Wait for FastAPI to be ready
wait_for_health() {
    print_step "Waiting for FastAPI to be ready..."

    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
            print_success "FastAPI is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done

    print_warning "FastAPI may not be fully ready yet"
    return 0
}

# Print summary
print_summary() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}Empire v7.3 Started Successfully${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}FastAPI:${NC}      http://localhost:$PORT"
    echo -e "  ${BOLD}API Docs:${NC}     http://localhost:$PORT/docs"
    echo -e "  ${BOLD}Health:${NC}       http://localhost:$PORT/health"

    if [ "$NO_CELERY" = false ]; then
        echo -e "  ${BOLD}Celery:${NC}       Running (see logs/celery.log)"
    fi

    if [ "$START_MONITORING" = true ]; then
        echo ""
        echo -e "  ${BOLD}Prometheus:${NC}   http://localhost:9090"
        echo -e "  ${BOLD}Grafana:${NC}      http://localhost:3001"
        echo -e "  ${BOLD}Flower:${NC}       http://localhost:5555"
    fi

    echo ""
    echo -e "  ${DIM}Logs: $LOG_DIR${NC}"
    echo -e "  ${DIM}PIDs: $PID_DIR${NC}"
    echo ""
    echo -e "  To stop: ${BOLD}./scripts/startup/stop_empire.sh${NC}"
    echo ""
}

# Main
main() {
    print_banner

    # Setup
    setup_directories
    activate_venv
    load_env

    # Preflight checks
    if [ "$SKIP_PREFLIGHT" = false ]; then
        if ! run_preflight; then
            echo ""
            print_error "Preflight checks failed!"
            echo ""
            echo -e "  Use ${BOLD}--skip-preflight${NC} to skip checks (not recommended)"
            echo ""
            exit 1
        fi
        echo ""
    else
        print_warning "Skipping preflight checks"
    fi

    # Start services
    start_docker_services
    start_fastapi
    start_celery
    start_monitoring

    # Wait for health
    wait_for_health

    # Summary
    print_summary
}

main "$@"
