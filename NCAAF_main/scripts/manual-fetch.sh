#!/bin/bash
# Hardened CLI for manual fetch operations
# Ensures atomicity, validation, logging, and safety for production use

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
INGESTION_DIR="$PROJECT_ROOT/ingestion"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
  echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $*" >&2
}

# Validation
validate_env() {
  log_info "Validating Docker and compose setup..."
  
  if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed or not in PATH"
    return 1
  fi
  
  if ! command -v docker-compose &> /dev/null; then
    log_error "docker-compose is not installed or not in PATH"
    return 1
  fi
  
  if [ ! -f "$PROJECT_ROOT/docker-compose.yml" ]; then
    log_error "docker-compose.yml not found at $PROJECT_ROOT"
    return 1
  fi
  
  log_success "Docker setup validated"
  return 0
}

# Perform health check before manual fetch
pre_flight_check() {
  log_info "Running pre-flight checks..."
  
  # Check if services are running
  log_info "Checking service health..."
  docker-compose -f "$PROJECT_ROOT/docker-compose.yml" exec -T postgres psql -U ncaaf_user -d ncaaf_v5 -c "SELECT 1" > /dev/null 2>&1 || {
    log_error "PostgreSQL is not running or not accessible"
    return 1
  }
  
  log_success "PostgreSQL is healthy"
  
  # Optional: Check Redis
  if docker-compose -f "$PROJECT_ROOT/docker-compose.yml" ps redis 2>/dev/null | grep -q "redis"; then
    docker-compose -f "$PROJECT_ROOT/docker-compose.yml" exec -T redis redis-cli ping > /dev/null 2>&1 || {
      log_warn "Redis is running but not responding"
    }
  fi
  
  log_success "Pre-flight checks passed"
  return 0
}

# Execute manual fetch
run_manual_fetch() {
  log_info "Executing manual fetch for new picks..."
  log_info "This operation will:"
  log_info "  1. Validate all inputs and database state"
  log_info "  2. Atomically fetch and save predictions"
  log_info "  3. Log all operations for audit trail"
  log_info "  4. Gracefully handle errors without data corruption"
  echo ""
  
  # Build the image if needed
  log_info "Building Docker images..."
  docker-compose -f "$PROJECT_ROOT/docker-compose.yml" build --no-cache ingestion || {
    log_error "Failed to build Docker image"
    return 1
  }
  
  # Run manualfetch with compose override
  log_info "Running manualfetch command..."
  docker-compose \
    -f "$PROJECT_ROOT/docker-compose.yml" \
    -f "$PROJECT_ROOT/docker-compose.manualfetch.yml" \
    run --rm ingestion || {
    log_error "Manual fetch operation failed"
    return 1
  }
  
  log_success "Manual fetch completed"
  return 0
}

# Post-execution validation
post_execution_check() {
  log_info "Running post-execution validation..."
  
  # Verify predictions were created
  PRED_COUNT=$(docker-compose -f "$PROJECT_ROOT/docker-compose.yml" exec -T postgres psql -U ncaaf_user -d ncaaf_v5 -t -c "SELECT COUNT(*) FROM predictions WHERE predicted_at > NOW() - INTERVAL '5 minutes'" | xargs)
  
  if [ "$PRED_COUNT" -gt 0 ]; then
    log_success "Created $PRED_COUNT new predictions"
  else
    log_warn "No predictions were created (this may be normal if all games already have predictions)"
  fi
  
  log_success "Post-execution validation passed"
  return 0
}

# Cleanup on error
trap 'log_error "Script interrupted"; exit 1' SIGINT SIGTERM

# Main execution
main() {
  echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}    NCAAF v5.0 - Hardened Manual Fetch for New Picks${NC}"
  echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
  echo ""
  
  validate_env || exit 1
  echo ""
  
  pre_flight_check || exit 1
  echo ""
  
  run_manual_fetch || exit 1
  echo ""
  
  post_execution_check || exit 1
  echo ""
  
  echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
  echo -e "${GREEN}    Manual Fetch Operation Completed Successfully!${NC}"
  echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
}

main "$@"
