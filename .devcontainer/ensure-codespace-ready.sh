#!/bin/bash
# Comprehensive Codespace Readiness Script
# Ensures ALL dependencies, apps, extensions, and secrets are ready
# Run this script on codespace startup to prevent missing dependencies and API errors

set -e

VENV_PATH="/workspaces/green_bier_sports_ncaam_model/.venv"
PROJECT_ROOT="/workspaces/green_bier_sports_ncaam_model"
ENV_FILE="$PROJECT_ROOT/.env.local"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  NCAAM Codespace Readiness Check                          ║"
echo "║  Ensuring all dependencies are installed                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ===== SECTION 1: VENV VERIFICATION & CREATION =====
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 SECTION 1: Python Virtual Environment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "$VENV_PATH/bin/activate" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment found"

    if "$VENV_PATH/bin/python" --version > /dev/null 2>&1; then
        PYTHON_VERSION=$("$VENV_PATH/bin/python" --version)
        echo -e "${GREEN}✓${NC} Python venv is healthy ($PYTHON_VERSION)"
    else
        echo -e "${YELLOW}⚠${NC} Venv Python broken, recreating..."
        rm -rf "$VENV_PATH"
        python -m venv "$VENV_PATH"
        source "$VENV_PATH/bin/activate"
    fi
else
    echo -e "${YELLOW}⚠${NC} Virtual environment not found, creating..."
    python -m venv "$VENV_PATH"
    source "$VENV_PATH/bin/activate"
fi

source "$VENV_PATH/bin/activate"

# ===== SECTION 2: PYTHON DEPENDENCIES =====
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🐍 SECTION 2: Python Dependencies"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "  Upgrading pip, setuptools, and wheel..."
pip install --quiet --upgrade pip setuptools wheel 2>/dev/null || pip install --upgrade pip setuptools wheel

echo "  Installing production dependencies..."
pip install -q -r services/prediction-service-python/requirements.txt 2>/dev/null || \
    pip install -r services/prediction-service-python/requirements.txt

echo "  Installing development dependencies..."
pip install -q -r requirements-dev.txt 2>/dev/null || \
    pip install -r requirements-dev.txt || true

echo -e "${GREEN}✓${NC} All Python dependencies installed"

# ===== SECTION 3: GO DEPENDENCIES =====
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🐹 SECTION 3: Go Dependencies"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -d "services/ratings-sync-go" ]; then
    cd services/ratings-sync-go
    if [ -f "go.mod" ]; then
        echo "  Downloading Go modules..."
        go mod download
        echo -e "${GREEN}✓${NC} Go dependencies downloaded"
    else
        echo -e "${YELLOW}⚠${NC} go.mod not found in services/ratings-sync-go"
    fi
    cd ../..
else
    echo -e "${YELLOW}⚠${NC} Go service directory not found"
fi

# ===== SECTION 4: DATABASE SERVICES =====
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💾 SECTION 4: Database Services (PostgreSQL & Redis)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check PostgreSQL
if command -v pg_isready &> /dev/null; then
    echo "  Checking PostgreSQL..."
    if pg_isready -h localhost -U postgres > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} PostgreSQL is running"

        # Ensure database exists
        PGPASSWORD=postgres psql -h localhost -U postgres -tc \
            "SELECT 1 FROM pg_database WHERE datname = 'ncaam_local'" | grep -q 1 || {
            echo "  Creating ncaam_local database..."
            PGPASSWORD=postgres psql -h localhost -U postgres -c "CREATE DATABASE ncaam_local" 2>/dev/null
            echo -e "${GREEN}✓${NC} Database created"
        }
    else
        echo -e "${YELLOW}⚠${NC} PostgreSQL not running (expected if using external DB)"
    fi
else
    echo -e "${YELLOW}⚠${NC} PostgreSQL tools not available (expected if using external DB)"
fi

# ===== SECTION 5: ENVIRONMENT CONFIGURATION =====
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚙️  SECTION 5: Environment Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ ! -f "$ENV_FILE" ]; then
    echo "  Creating .env.local..."
    cat > "$ENV_FILE" << 'EOF'
# Codespaces Auto-Configuration
# Generated by ensure-codespace-ready.sh

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ncaam_local
REDIS_URL=redis://localhost:6379/0

# Environment
ENVIRONMENT=codespaces
DEBUG=true
LOG_LEVEL=DEBUG

# API Server
API_PORT=8000

# API Keys (must be provided - get from https://the-odds-api.com/)
ODDS_API_KEY=

# Optional Webhooks
TEAMS_WEBHOOK_SECRET=

# Azure (optional)
AZURE_SUBSCRIPTION_ID=
AZURE_RESOURCE_GROUP=
AZURE_COSMOS_DB_ENDPOINT=

# Other
PYTHONUNBUFFERED=1
EOF
    echo -e "${GREEN}✓${NC} .env.local created"
else
    echo -e "${GREEN}✓${NC} .env.local already exists"

    # Verify critical env vars
    if ! grep -q "ODDS_API_KEY" "$ENV_FILE"; then
        echo "  Adding missing ODDS_API_KEY to .env.local..."
        echo "ODDS_API_KEY=" >> "$ENV_FILE"
    fi
fi

# ===== SECTION 6: BASH AUTO-ACTIVATION =====
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 SECTION 6: Shell Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

BASHRC="$HOME/.bashrc"
touch "$BASHRC"

if ! grep -qF ".venv/bin/activate" "$BASHRC" 2>/dev/null; then
    echo "  Enabling venv auto-activation..."
    {
        echo ""
        echo "# Auto-activate NCAAM Model venv"
        echo '[ -f "/workspaces/green_bier_sports_ncaam_model/.venv/bin/activate" ] && source "/workspaces/green_bier_sports_ncaam_model/.venv/bin/activate"'
    } >> "$BASHRC"
    echo -e "${GREEN}✓${NC} Venv auto-activation enabled"
else
    echo -e "${GREEN}✓${NC} Venv auto-activation already configured"
fi

# ===== SECTION 7: VS CODE EXTENSIONS =====
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧩 SECTION 7: VS Code Extensions (Pre-configured)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

EXTENSIONS=(
    "charliermarsh.ruff"
    "ms-python.python"
    "ms-python.vscode-pylance"
    "ms-azuretools.vscode-docker"
    "ms-azuretools.vscode-bicep"
    "ms-vscode.azure-account"
    "ms-vscode.azurecli"
    "ms-azuretools.vscode-cosmosdb"
    "golang.go"
    "rust-lang.rust-analyzer"
    "ms-vscode.makefile-tools"
    "ckolkman.vscode-postgres"
    "redhat.vscode-yaml"
    "github.vscode-github-actions"
    "editorconfig.editorconfig"
    "mikestead.dotenv"
)

if command -v code &> /dev/null; then
    echo "  Installing VS Code extensions..."
    for ext in "${EXTENSIONS[@]}"; do
        if code --list-extensions | grep -q "^${ext}$"; then
            echo "    ✓ $ext"
        else
            echo "    Installing $ext..."
            code --install-extension "$ext" --force 2>/dev/null || true
        fi
    done
    echo -e "${GREEN}✓${NC} All VS Code extensions configured"
else
    echo -e "${YELLOW}⚠${NC} VS Code CLI not available (extensions configured in devcontainer.json)"
fi

# ===== SECTION 8: CRITICAL FILES CHECK =====
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 SECTION 8: Critical Files Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CRITICAL_FILES=(
    "services/prediction-service-python/app/main.py"
    "services/prediction-service-python/requirements.txt"
    "pyproject.toml"
    "requirements-dev.txt"
    "README.md"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$PROJECT_ROOT/$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file (MISSING)"
    fi
done

# ===== SECTION 9: QUICK DIAGNOSTICS =====
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 SECTION 9: System Information"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "  Python: $("$VENV_PATH/bin/python" --version)"
echo "  Pip: $("$VENV_PATH/bin/pip" --version)"
if command -v go &> /dev/null; then
    echo "  Go: $(go version | awk '{print $3}')"
fi
echo "  Node: $(node --version 2>/dev/null || echo 'not installed')"
echo "  Docker: $(docker --version 2>/dev/null || echo 'not available')"
echo "  Git: $(git --version | awk '{print $3}')"

# ===== FINAL SUMMARY =====
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo -e "║${GREEN}  ✓ Codespace Ready!${NC}                              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📝 TODO BEFORE RUNNING:"
echo "  1. Add your ODDS_API_KEY to .env.local"
echo "    Get it from: https://the-odds-api.com/api-keys"
echo ""
echo "🚀 QUICK START:"
echo "  • API Server: cd services/prediction-service-python && python -m uvicorn app.main:app --reload --port 8000"
echo "  • API Docs:   http://localhost:8000/docs"
echo "  • Tests:      pytest testing/ -v"
echo "  • Lint:       ruff check ."
echo "  • Format:     ruff format ."
echo ""
echo "💡 This script can be re-run anytime to ensure everything is ready:"
echo "  bash .devcontainer/ensure-codespace-ready.sh"
echo ""
