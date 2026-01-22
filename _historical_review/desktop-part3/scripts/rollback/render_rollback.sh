#!/bin/bash
# ============================================================================
# Render Deployment Rollback Script
# Empire v7.3 - Task 7.2
# ============================================================================
#
# PURPOSE: Rollback Render services to previous deployment versions
#
# USAGE:
#   ./render_rollback.sh <service> [deploy_id]
#   ./render_rollback.sh empire-api             # Rollback to previous deploy
#   ./render_rollback.sh empire-api dep-xxx     # Rollback to specific deploy
#   ./render_rollback.sh --list empire-api      # List recent deploys
#   ./render_rollback.sh --status               # Check all service statuses
#
# REQUIREMENTS:
#   - RENDER_API_KEY environment variable set
#   - jq installed (brew install jq)
#   - curl installed
#
# ============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Render API Configuration
RENDER_API_BASE="https://api.render.com/v1"
RENDER_API_KEY="${RENDER_API_KEY:-}"

# Service IDs (Empire v7.3 Production)
declare -A SERVICE_IDS=(
    ["empire-api"]="srv-d44o2dq4d50c73elgupg"
    ["empire-celery"]="srv-d44oclodl3ps73bg8rmg"
    ["empire-chat"]="srv-d47ptdmr433s739ljolg"
    ["llamaindex"]="srv-d2nl1lre5dus73atm9u0"
    ["crewai"]="srv-d2n0hh3uibrs73buafo0"
    ["n8n"]="srv-d2ii86umcj7s73ce35eg"
)

# Service URLs for health checks
declare -A SERVICE_URLS=(
    ["empire-api"]="https://jb-empire-api.onrender.com/health"
    ["empire-celery"]=""  # Background worker, no health endpoint
    ["empire-chat"]="https://jb-empire-chat.onrender.com"
    ["llamaindex"]="https://jb-llamaindex.onrender.com"
    ["crewai"]="https://jb-crewai.onrender.com"
    ["n8n"]="https://jb-n8n.onrender.com"
)

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
    if [[ -z "$RENDER_API_KEY" ]]; then
        log_error "RENDER_API_KEY environment variable not set"
        log_info "Export it with: export RENDER_API_KEY=rnd_xxxxxxxxx"
        exit 1
    fi

    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not installed"
        log_info "Install with: brew install jq"
        exit 1
    fi

    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        exit 1
    fi
}

render_api() {
    local endpoint="$1"
    local method="${2:-GET}"
    local data="${3:-}"

    if [[ -n "$data" ]]; then
        curl -s -X "$method" \
            -H "Authorization: Bearer $RENDER_API_KEY" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$RENDER_API_BASE$endpoint"
    else
        curl -s -X "$method" \
            -H "Authorization: Bearer $RENDER_API_KEY" \
            "$RENDER_API_BASE$endpoint"
    fi
}

get_service_id() {
    local service_name="$1"
    if [[ -n "${SERVICE_IDS[$service_name]:-}" ]]; then
        echo "${SERVICE_IDS[$service_name]}"
    else
        log_error "Unknown service: $service_name"
        log_info "Available services: ${!SERVICE_IDS[*]}"
        exit 1
    fi
}

# ============================================================================
# Rollback Functions
# ============================================================================

list_deploys() {
    local service_name="$1"
    local service_id=$(get_service_id "$service_name")
    local limit="${2:-10}"

    log_info "Listing last $limit deployments for $service_name..."

    local deploys=$(render_api "/services/$service_id/deploys?limit=$limit")

    echo ""
    echo "Recent deployments for $service_name:"
    echo "======================================="
    echo "$deploys" | jq -r '.[] | "Deploy: \(.deploy.id) | Status: \(.deploy.status) | Created: \(.deploy.createdAt) | Commit: \(.deploy.commit.id[0:7] // "N/A")"'
    echo ""
}

get_current_deploy() {
    local service_name="$1"
    local service_id=$(get_service_id "$service_name")

    local deploys=$(render_api "/services/$service_id/deploys?limit=5")
    local current=$(echo "$deploys" | jq -r '.[0].deploy | select(.status == "live") | .id')

    if [[ -z "$current" || "$current" == "null" ]]; then
        # Get the most recent successful deploy
        current=$(echo "$deploys" | jq -r '.[] | select(.deploy.status == "live") | .deploy.id' | head -1)
    fi

    echo "$current"
}

get_previous_deploy() {
    local service_name="$1"
    local service_id=$(get_service_id "$service_name")

    local deploys=$(render_api "/services/$service_id/deploys?limit=10")

    # Get the second most recent "live" or "build_succeeded" deploy
    local previous=$(echo "$deploys" | jq -r '[.[] | select(.deploy.status == "live" or .deploy.status == "build_succeeded")] | .[1].deploy.id // empty')

    if [[ -z "$previous" ]]; then
        log_error "No previous successful deployment found for rollback"
        exit 1
    fi

    echo "$previous"
}

rollback_to_deploy() {
    local service_name="$1"
    local target_deploy_id="$2"
    local service_id=$(get_service_id "$service_name")

    log_info "Rolling back $service_name to deploy: $target_deploy_id"

    # Get commit SHA from target deploy
    local deploy_info=$(render_api "/services/$service_id/deploys/$target_deploy_id")
    local commit_id=$(echo "$deploy_info" | jq -r '.commit.id // empty')

    if [[ -z "$commit_id" || "$commit_id" == "null" ]]; then
        log_warning "Could not get commit ID from deploy, attempting direct rollback..."
        # Use Render's rollback endpoint if available
        local result=$(render_api "/services/$service_id/rollback/$target_deploy_id" "POST")
        echo "$result"
        return
    fi

    log_info "Target commit: $commit_id"

    # Trigger new deploy with the target commit
    local deploy_data="{\"clearCache\": \"do_not_clear\"}"
    local result=$(render_api "/services/$service_id/deploys" "POST" "$deploy_data")

    local new_deploy_id=$(echo "$result" | jq -r '.id // empty')

    if [[ -n "$new_deploy_id" && "$new_deploy_id" != "null" ]]; then
        log_success "Rollback deploy initiated: $new_deploy_id"
        log_info "Monitor at: https://dashboard.render.com/web/$service_id/deploys/$new_deploy_id"
    else
        log_error "Failed to initiate rollback"
        echo "$result" | jq .
        exit 1
    fi
}

rollback_to_previous() {
    local service_name="$1"

    log_info "Finding previous successful deployment..."

    local current_deploy=$(get_current_deploy "$service_name")
    local previous_deploy=$(get_previous_deploy "$service_name")

    log_info "Current deploy: $current_deploy"
    log_info "Previous deploy: $previous_deploy"

    if [[ "$current_deploy" == "$previous_deploy" ]]; then
        log_warning "Current and previous deploys are the same. No rollback needed."
        exit 0
    fi

    rollback_to_deploy "$service_name" "$previous_deploy"
}

check_health() {
    local service_name="$1"
    local url="${SERVICE_URLS[$service_name]:-}"

    if [[ -z "$url" ]]; then
        log_warning "No health check URL for $service_name (background worker)"
        return 0
    fi

    log_info "Checking health of $service_name at $url..."

    local status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")

    if [[ "$status_code" == "200" ]]; then
        log_success "$service_name is healthy (HTTP $status_code)"
        return 0
    else
        log_error "$service_name health check failed (HTTP $status_code)"
        return 1
    fi
}

show_status() {
    log_info "Checking status of all Empire services..."
    echo ""

    for service_name in "${!SERVICE_IDS[@]}"; do
        local service_id="${SERVICE_IDS[$service_name]}"
        local service_info=$(render_api "/services/$service_id")
        local status=$(echo "$service_info" | jq -r '.suspended // "active"')
        local updated=$(echo "$service_info" | jq -r '.updatedAt // "unknown"')

        if [[ "$status" == "not_suspended" ]]; then
            echo -e "${GREEN}●${NC} $service_name - Active (Updated: $updated)"
        elif [[ "$status" == "suspended" ]]; then
            echo -e "${YELLOW}●${NC} $service_name - Suspended"
        else
            echo -e "${RED}●${NC} $service_name - Unknown status"
        fi
    done

    echo ""
    log_info "Health checks:"
    for service_name in "${!SERVICE_URLS[@]}"; do
        if [[ -n "${SERVICE_URLS[$service_name]}" ]]; then
            check_health "$service_name" || true
        fi
    done
}

enable_maintenance_mode() {
    local service_name="$1"
    local service_id=$(get_service_id "$service_name")

    log_info "Enabling maintenance mode for $service_name..."

    local result=$(render_api "/services/$service_id" "PATCH" '{"serviceDetails": {"maintenanceMode": {"enabled": true}}}')

    if echo "$result" | jq -e '.id' > /dev/null 2>&1; then
        log_success "Maintenance mode enabled for $service_name"
    else
        log_error "Failed to enable maintenance mode"
        echo "$result" | jq .
    fi
}

disable_maintenance_mode() {
    local service_name="$1"
    local service_id=$(get_service_id "$service_name")

    log_info "Disabling maintenance mode for $service_name..."

    local result=$(render_api "/services/$service_id" "PATCH" '{"serviceDetails": {"maintenanceMode": {"enabled": false}}}')

    if echo "$result" | jq -e '.id' > /dev/null 2>&1; then
        log_success "Maintenance mode disabled for $service_name"
    else
        log_error "Failed to disable maintenance mode"
        echo "$result" | jq .
    fi
}

# ============================================================================
# Main Script
# ============================================================================

print_usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  <service>                 Rollback service to previous deploy"
    echo "  <service> <deploy_id>     Rollback service to specific deploy"
    echo "  --list <service>          List recent deployments for service"
    echo "  --status                  Check status of all services"
    echo "  --maintenance <service>   Enable maintenance mode"
    echo "  --no-maintenance <service> Disable maintenance mode"
    echo "  --help                    Show this help message"
    echo ""
    echo "Available services:"
    for svc in "${!SERVICE_IDS[@]}"; do
        echo "  - $svc"
    done
    echo ""
    echo "Examples:"
    echo "  $0 empire-api                    # Rollback API to previous deploy"
    echo "  $0 empire-api dep-abc123         # Rollback API to specific deploy"
    echo "  $0 --list empire-api             # List recent API deploys"
    echo "  $0 --status                      # Check all service statuses"
}

main() {
    check_requirements

    if [[ $# -eq 0 ]]; then
        print_usage
        exit 1
    fi

    case "$1" in
        --help|-h)
            print_usage
            exit 0
            ;;
        --list)
            if [[ $# -lt 2 ]]; then
                log_error "Service name required for --list"
                exit 1
            fi
            list_deploys "$2" "${3:-10}"
            ;;
        --status)
            show_status
            ;;
        --maintenance)
            if [[ $# -lt 2 ]]; then
                log_error "Service name required for --maintenance"
                exit 1
            fi
            enable_maintenance_mode "$2"
            ;;
        --no-maintenance)
            if [[ $# -lt 2 ]]; then
                log_error "Service name required for --no-maintenance"
                exit 1
            fi
            disable_maintenance_mode "$2"
            ;;
        *)
            # Service rollback
            local service_name="$1"

            # Validate service name
            get_service_id "$service_name" > /dev/null

            if [[ $# -ge 2 ]]; then
                # Rollback to specific deploy
                rollback_to_deploy "$service_name" "$2"
            else
                # Rollback to previous deploy
                rollback_to_previous "$service_name"
            fi
            ;;
    esac
}

main "$@"
