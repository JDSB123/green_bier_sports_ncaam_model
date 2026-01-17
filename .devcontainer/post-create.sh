#!/bin/bash
# Post-create script for Codespaces
set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  NCAAM Model - Codespaces Setup                           ║"
echo "╚════════════════════════════════════════════════════════════╝"

echo ""
echo "[1] Installing Python dependencies..."
pip install --upgrade pip setuptools wheel -q

# Install all requirements (the image is Debian-based, so xgboost wheels work)
pip install -r services/prediction-service-python/requirements.txt -q || \
  pip install -r services/prediction-service-python/requirements.txt

# Install dev requirements
pip install -r requirements-dev.txt -q || true

echo "  ✓ Python dependencies installed"

echo "[2] Installing Go dependencies..."
cd services/ratings-sync-go
go mod download
cd ../..

echo "[3] Initializing PostgreSQL..."
# PostgreSQL should already be running from the feature
until pg_isready -h localhost -U postgres > /dev/null 2>&1; do
  echo "  Waiting for PostgreSQL..."
  sleep 2
done
echo "  ✓ PostgreSQL ready"

echo "[4] Creating databases..."
PGPASSWORD=postgres psql -h localhost -U postgres -tc \
  "SELECT 1 FROM pg_database WHERE datname = 'ncaam_local'" | grep -q 1 || \
  PGPASSWORD=postgres psql -h localhost -U postgres -c "CREATE DATABASE ncaam_local"

echo "[5] Creating .env.local..."
cat > .env.local << 'EOF'
# Codespaces Auto-Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ncaam_local
REDIS_URL=redis://localhost:6379/0
ENVIRONMENT=codespaces
DEBUG=true
LOG_LEVEL=DEBUG
API_PORT=8000
ODDS_API_KEY=
TEAMS_WEBHOOK_SECRET=
EOF

echo ""
echo "✓ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Add ODDS_API_KEY to .env.local"
echo "  2. Run: python services/prediction-service-python/main.py"
echo "  3. Visit: http://localhost:8000/docs (API docs)"
echo ""
echo "Optional: to install heavier data/ML dependencies (pandas/numpy/xgboost/etc), run:"
echo "  bash .devcontainer/install-heavy-requirements.sh"
echo ""
