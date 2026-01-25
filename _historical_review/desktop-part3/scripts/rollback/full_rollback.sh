#!/bin/bash
# ============================================================================
# Full System Rollback Script
# Empire v7.3 - Task 7.2
# ============================================================================
#
# PURPOSE: Orchestrate complete system rollback including:
#   1. Put services in maintenance mode
#   2. Rollback Render deployments
#   3. Rollback database migrations
#   4. Verify system health
#   5. Remove maintenance mode
#
# USAGE:
#   ./full_rollback.sh --dry-run                    # Preview actions
#   ./full_rollback.sh --services                   # Rollback services only
#   ./full_rollback.sh --database                   # Rollback database only
#   ./full_rollback.sh --full                       # Full system rollback
#   ./full_rollback.sh --migration <migration>      # Specific migration rollback
#
# REQUIREMENTS:
#   - RENDER_API_KEY environment variable
#   - SUPABASE_URL environment variable
#   - SUPABASE_SERVICE_KEY environment variable
#   - psql installed (for database rollbacks)
#   - jq installed
#
# ============================================================================

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Configuration
DRY_RUN=false
ROLLBACK_SERVICES=false
ROLLBACK_DATABASE=false
SPECIFIC_MIGRATION=""
LOG_FILE="$PROJECT_ROOT/logs/rollback_$(date +%Y%m%d_%H%M%S).log"

# ============================================================================
# Logging Functions
# ============================================================================

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Console output
    case "$level" in
        INFO)    echo -e "${BLUE}[INFO]${NC} $message" ;;
        SUCCESS) echo -e "${GREEN}[SUCCESS]${NC} $message" ;;
        WARNING) echo -e "${YELLOW}[WARNING]${NC} $message" ;;
        ERROR)   echo -e "${RED}[ERROR]${NC} $message" ;;
        STEP)    echo -e "${MAGENTA}[STEP]${NC} $message" ;;
    esac

    # File output
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

# ============================================================================
# Pre-Rollback Checks
# ============================================================================

check_environment() {
    log INFO "Checking environment..."

    local missing=()

    [[ -z "${RENDER_API_KEY:-}" ]] && missing+=("RENDER_API_KEY")
    [[ -z "${SUPABASE_URL:-}" ]] && missing+=("SUPABASE_URL")
    [[ -z "${SUPABASE_SERVICE_KEY:-}" ]] && missing+=("SUPABASE_SERVICE_KEY")

    if [[ ${#missing[@]} -gt 0 ]]; then
        log ERROR "Missing environment variables: ${missing[*]}"
        log INFO "Please set these in your .env file and source it"
        exit 1
    fi

    # Check required tools
    for tool in curl jq psql; do
        if ! command -v $tool &> /dev/null; then
            log ERROR "$tool is required but not installed"
            exit 1
        fi
    done

    log SUCCESS "Environment check passed"
}

confirm_action() {
    local message="$1"

    if [[ "$DRY_RUN" == "true" ]]; then
        log INFO "[DRY RUN] Would: $message"
        return 0
    fi

    echo -e "${YELLOW}⚠️  $message${NC}"
    read -p "Are you sure you want to proceed? (yes/no): " confirm

    if [[ "$confirm" != "yes" ]]; then
        log INFO "Operation cancelled by user"
        exit 0
    fi
}

# ============================================================================
# Service Rollback Functions
# ============================================================================

enable_all_maintenance_mode() {
    log STEP "Enabling maintenance mode on all services..."

    local services=("empire-api" "empire-chat")

    for service in "${services[@]}"; do
        if [[ "$DRY_RUN" == "true" ]]; then
            log INFO "[DRY RUN] Would enable maintenance mode on $service"
        else
            "$SCRIPT_DIR/render_rollback.sh" --maintenance "$service" || true
        fi
    done
}

disable_all_maintenance_mode() {
    log STEP "Disabling maintenance mode on all services..."

    local services=("empire-api" "empire-chat")

    for service in "${services[@]}"; do
        if [[ "$DRY_RUN" == "true" ]]; then
            log INFO "[DRY RUN] Would disable maintenance mode on $service"
        else
            "$SCRIPT_DIR/render_rollback.sh" --no-maintenance "$service" || true
        fi
    done
}

rollback_services() {
    log STEP "Rolling back Render services..."

    # Rollback order: Chat UI -> API -> Celery Worker
    # (Reverse of deployment order)
    local services=("empire-chat" "empire-api" "empire-celery")

    for service in "${services[@]}"; do
        if [[ "$DRY_RUN" == "true" ]]; then
            log INFO "[DRY RUN] Would rollback $service to previous deployment"
        else
            log INFO "Rolling back $service..."
            "$SCRIPT_DIR/render_rollback.sh" "$service" || {
                log ERROR "Failed to rollback $service"
                return 1
            }
            # Wait between service rollbacks
            log INFO "Waiting 30 seconds for $service to stabilize..."
            sleep 30
        fi
    done

    log SUCCESS "Service rollbacks initiated"
}

verify_services() {
    log STEP "Verifying service health..."

    local max_attempts=10
    local wait_time=30

    for attempt in $(seq 1 $max_attempts); do
        log INFO "Health check attempt $attempt/$max_attempts..."

        local all_healthy=true

        # Check each service
        for url in "https://jb-empire-api.onrender.com/health" \
                   "https://jb-empire-chat.onrender.com"; do
            local status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")
            if [[ "$status" != "200" ]]; then
                all_healthy=false
                log WARNING "$url returned HTTP $status"
            fi
        done

        if [[ "$all_healthy" == "true" ]]; then
            log SUCCESS "All services are healthy"
            return 0
        fi

        if [[ $attempt -lt $max_attempts ]]; then
            log INFO "Waiting $wait_time seconds before retry..."
            sleep $wait_time
        fi
    done

    log ERROR "Services did not become healthy within expected time"
    return 1
}

# ============================================================================
# Database Rollback Functions
# ============================================================================

get_database_connection() {
    # Extract connection details from SUPABASE_URL
    # Format: postgresql://postgres:password@host:port/postgres
    echo "postgresql://postgres.${SUPABASE_URL#https://}:${SUPABASE_SERVICE_KEY}@${SUPABASE_URL#https://}:5432/postgres"
}

list_available_rollbacks() {
    log INFO "Available database rollback scripts:"
    echo ""

    if [[ -d "$PROJECT_ROOT/migrations/rollback" ]]; then
        ls -1 "$PROJECT_ROOT/migrations/rollback/"*.sql 2>/dev/null | while read -r file; do
            local filename=$(basename "$file" .sql)
            echo "  - ${filename#rollback_}"
        done
    fi

    echo ""
}

rollback_migration() {
    local migration_name="$1"
    local rollback_file="$PROJECT_ROOT/migrations/rollback/rollback_${migration_name}.sql"

    if [[ ! -f "$rollback_file" ]]; then
        log ERROR "Rollback file not found: $rollback_file"
        list_available_rollbacks
        return 1
    fi

    log STEP "Rolling back migration: $migration_name"

    if [[ "$DRY_RUN" == "true" ]]; then
        log INFO "[DRY RUN] Would execute: $rollback_file"
        return 0
    fi

    # Execute rollback via Supabase
    log INFO "Executing rollback SQL..."

    # Use psql to execute the rollback
    PGPASSWORD="$SUPABASE_SERVICE_KEY" psql \
        -h "db.${SUPABASE_URL#https://}" \
        -U postgres \
        -d postgres \
        -f "$rollback_file" \
        2>&1 | tee -a "$LOG_FILE"

    local exit_code=${PIPESTATUS[0]}

    if [[ $exit_code -eq 0 ]]; then
        log SUCCESS "Migration rollback completed: $migration_name"
    else
        log ERROR "Migration rollback failed: $migration_name (exit code: $exit_code)"
        return 1
    fi
}

rollback_all_database() {
    log STEP "Rolling back all database migrations..."

    confirm_action "This will rollback ALL database migrations. Data may be lost!"

    # Rollback in reverse order (most recent first)
    local migrations=(
        "enhance_agent_interactions"
        "add_performance_indexes"
        "create_audit_logs_table"
        "enable_rls_policies"
        "add_memory_rls_policies"
        "create_cost_tracking_tables"
    )

    for migration in "${migrations[@]}"; do
        rollback_migration "$migration" || {
            log ERROR "Stopping rollback due to failure in: $migration"
            return 1
        }
    done

    log SUCCESS "All database migrations rolled back"
}

# ============================================================================
# Full Rollback Orchestration
# ============================================================================

full_rollback() {
    log STEP "=== FULL SYSTEM ROLLBACK ==="
    log INFO "Log file: $LOG_FILE"

    confirm_action "This will perform a FULL SYSTEM ROLLBACK. This is a destructive operation!"

    # Step 1: Enable maintenance mode
    enable_all_maintenance_mode

    # Step 2: Rollback services
    rollback_services || {
        log ERROR "Service rollback failed. Disabling maintenance mode..."
        disable_all_maintenance_mode
        return 1
    }

    # Step 3: Rollback database
    rollback_all_database || {
        log ERROR "Database rollback failed. Services may be in inconsistent state!"
        log WARNING "Manual intervention required"
        return 1
    }

    # Step 4: Verify system health
    verify_services || {
        log WARNING "Health verification failed. Keeping maintenance mode enabled."
        return 1
    }

    # Step 5: Disable maintenance mode
    disable_all_maintenance_mode

    log SUCCESS "=== FULL SYSTEM ROLLBACK COMPLETED ==="
    log INFO "Please verify system functionality manually"
}

# ============================================================================
# Main Script
# ============================================================================

print_usage() {
    cat << EOF
Usage: $0 [options]

Options:
  --dry-run                Preview rollback actions without executing
  --services               Rollback Render services only
  --database               Rollback all database migrations
  --migration <name>       Rollback specific migration
  --full                   Full system rollback (services + database)
  --list-migrations        List available rollback scripts
  --status                 Check current system status
  --help                   Show this help message

Examples:
  $0 --dry-run --full              # Preview full rollback
  $0 --services                    # Rollback services only
  $0 --migration enable_rls_policies  # Rollback specific migration
  $0 --full                        # Execute full rollback

Environment Variables Required:
  RENDER_API_KEY          Render API key
  SUPABASE_URL            Supabase project URL
  SUPABASE_SERVICE_KEY    Supabase service role key

EOF
}

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                print_usage
                exit 0
                ;;
            --dry-run)
                DRY_RUN=true
                log INFO "Dry run mode enabled - no changes will be made"
                shift
                ;;
            --services)
                ROLLBACK_SERVICES=true
                shift
                ;;
            --database)
                ROLLBACK_DATABASE=true
                shift
                ;;
            --migration)
                SPECIFIC_MIGRATION="$2"
                shift 2
                ;;
            --full)
                ROLLBACK_SERVICES=true
                ROLLBACK_DATABASE=true
                shift
                ;;
            --list-migrations)
                list_available_rollbacks
                exit 0
                ;;
            --status)
                check_environment
                "$SCRIPT_DIR/render_rollback.sh" --status
                exit 0
                ;;
            *)
                log ERROR "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done

    # Check if any action specified
    if [[ "$ROLLBACK_SERVICES" == "false" && "$ROLLBACK_DATABASE" == "false" && -z "$SPECIFIC_MIGRATION" ]]; then
        print_usage
        exit 1
    fi

    # Check environment
    check_environment

    # Execute rollback
    if [[ "$ROLLBACK_SERVICES" == "true" && "$ROLLBACK_DATABASE" == "true" ]]; then
        full_rollback
    elif [[ "$ROLLBACK_SERVICES" == "true" ]]; then
        confirm_action "This will rollback all Render services"
        enable_all_maintenance_mode
        rollback_services
        verify_services
        disable_all_maintenance_mode
    elif [[ "$ROLLBACK_DATABASE" == "true" ]]; then
        rollback_all_database
    elif [[ -n "$SPECIFIC_MIGRATION" ]]; then
        rollback_migration "$SPECIFIC_MIGRATION"
    fi

    log SUCCESS "Rollback operation completed"
    log INFO "Full log available at: $LOG_FILE"
}

main "$@"
