#!/bin/bash
set -e

echo "🚀 Starting NCAA Prediction Service Container..."

# Start Ratings Sync (Go) in background
# It has its own internal cron scheduler (daily 6 AM)
echo "   - Starting ratings-sync (daemon)..."
/app/bin/ratings-sync > /proc/1/fd/1 2>&1 &

# Start Odds Ingestion (Rust) in background
# It has its own internal loop (every 30s)
echo "   - Starting odds-ingestion (daemon)..."
/app/bin/odds-ingestion > /proc/1/fd/1 2>&1 &

# Start Python API in foreground
echo "   - Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8082 --workers 2
