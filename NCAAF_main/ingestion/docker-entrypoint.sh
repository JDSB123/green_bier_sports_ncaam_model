#!/bin/sh
set -e

# Docker entrypoint for NCAAF v5.0 ingestion worker
# Supports multiple commands: worker, webhook, manualfetch, health-check
# Ensures graceful shutdown and health monitoring

LOG_LEVEL=${LOG_LEVEL:-info}
APP_ENV=${APP_ENV:-production}

# Setup logging
log_info() {
  echo "[$(date -u +'%Y-%m-%d %H:%M:%S UTC')] INFO: $*"
}

log_error() {
  echo "[$(date -u +'%Y-%m-%d %H:%M:%S UTC')] ERROR: $*" >&2
}

log_warn() {
  echo "[$(date -u +'%Y-%m-%d %H:%M:%S UTC')] WARN: $*"
}

# Health check function
health_check() {
  log_info "Running health check..."
  
  # Check database connectivity
  if ! nc -z "$DATABASE_HOST" "$DATABASE_PORT" 2>/dev/null; then
    log_error "Database is unreachable at $DATABASE_HOST:$DATABASE_PORT"
    return 1
  fi
  
  # Check Redis connectivity (if enabled)
  if [ "$REDIS_HOST" != "" ]; then
    if ! nc -z "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null; then
      log_warn "Redis is unreachable at $REDIS_HOST:$REDIS_PORT (non-critical)"
    fi
  fi
  
  log_info "Health check passed"
  return 0
}

# Validate environment
validate_env() {
  log_info "Validating environment..."
  
  if [ -z "$DATABASE_HOST" ] || [ -z "$DATABASE_USER" ] || [ -z "$DATABASE_PASSWORD" ]; then
    log_error "Missing required database environment variables"
    return 1
  fi
  
  log_info "Environment validation passed"
  return 0
}

# Run database migrations
run_migrations() {
  log_info "Checking database migrations..."
  
  # This is a placeholder - migrations typically run via migrate CLI or during initial sync
  if command -v migrate > /dev/null 2>&1; then
    log_info "Running pending migrations..."
    migrate -path /app/migrations -database "$DATABASE_URL" up || log_warn "No pending migrations"
  else
    log_warn "migrate CLI not found - skipping migration check"
  fi
}

# Cleanup function for graceful shutdown
cleanup() {
  log_info "Received shutdown signal, cleaning up..."
  exit 0
}

trap cleanup SIGTERM SIGINT

# Main command logic
COMMAND=${1:-worker}

case "$COMMAND" in
  worker)
    log_info "Starting NCAAF v5.0 Data Ingestion Worker..."
    validate_env || exit 1
    health_check || exit 1
    run_migrations || true
    exec /app/bin/worker
    ;;
  
  webhook)
    log_info "Starting NCAAF v5.0 Webhook Server..."
    validate_env || exit 1
    health_check || exit 1
    exec /app/bin/webhook
    ;;
  
  manualfetch)
    log_info "Starting Manual Fetch for New Picks..."
    validate_env || exit 1
    health_check || exit 1
    exec /app/bin/manualfetch
    ;;
  
  health-check)
    log_info "Running health check..."
    validate_env || exit 1
    health_check || exit 1
    log_info "All checks passed"
    exit 0
    ;;
  
  sh)
    log_info "Starting shell session..."
    exec /bin/sh "$@"
    ;;
  
  *)
    log_error "Unknown command: $COMMAND"
    echo "Available commands: worker, webhook, manualfetch, health-check, sh"
    exit 1
    ;;
esac
