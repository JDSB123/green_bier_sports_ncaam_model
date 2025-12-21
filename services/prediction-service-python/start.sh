#!/bin/bash
set -e

echo "🚀 Starting NCAA Prediction Service Container..."

# MANUAL-ONLY: No daemons or automated polling
# Ratings and odds sync are triggered manually via run_today.py when user wants fresh picks
# This script only starts the API server for manual predictions

echo "   - Starting API server (manual mode - no automation)..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8082 --workers 2
