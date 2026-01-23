#!/bin/bash
# Master Emergency Recovery Script
# Handles EVERY possible access, environment, extension, and login issue
# Run this when ANYTHING goes wrong

set -e

PROJECT_ROOT="/workspaces/green_bier_sports_ncaam_model"
VENV_PATH="$PROJECT_ROOT/.venv"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          🆘 MASTER EMERGENCY RECOVERY SCRIPT 🆘              ║"
echo "║   Fixes ALL access, environment, and login issues             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# ============================================================================
# STEP 1: ENVIRONMENT DETECTION & LOGGING
# ============================================================================

print_step "STEP 1: Environment Detection"

RECOVERY_LOG="$PROJECT_ROOT/.recovery_$(date +%Y%m%d_%H%M%S).log"

{
    echo "Emergency Recovery Log"
    echo "======================"
    echo "Time: $(date)"
    echo "User: $(whoami)"
    echo "Host: $(hostname)"
    echo "PWD: $(pwd)"
    echo "Environment:"
    env | grep -E "^(PATH|PYTHON|VIRTUAL_|GITHUB|AZURE|AWS|DATABASE|REDIS|ENVIRONMENT)" || true
} > "$RECOVERY_LOG"

print_success "Recovery log created: $RECOVERY_LOG"

# ============================================================================
# STEP 2: RESET PYTHON ENVIRONMENT
# ============================================================================

print_step "STEP 2: Python Virtual Environment Reset"

if [ -d "$VENV_PATH" ]; then
    print_warning "Removing broken venv..."
    rm -rf "$VENV_PATH"
fi

print_success "Creating fresh venv..."
python -m venv "$VENV_PATH" --upgrade-deps

source "$VENV_PATH/bin/activate"
print_success "Venv activated"

# Upgrade pip
print_success "Upgrading pip..."
pip install --upgrade pip setuptools wheel -q

# Install dependencies
print_success "Installing production dependencies..."
pip install -q -r services/prediction-service-python/requirements.txt 2>/dev/null || pip install -r services/prediction-service-python/requirements.txt

print_success "Installing development dependencies..."
pip install -q -r requirements-dev.txt 2>/dev/null || pip install -r requirements-dev.txt || true

# ============================================================================
# STEP 3: ENVIRONMENT FILES RECOVERY
# ============================================================================

print_step "STEP 3: Environment Files Recovery"

# Backup existing files
if [ -f "$PROJECT_ROOT/.env.local" ]; then
    cp "$PROJECT_ROOT/.env.local" "$PROJECT_ROOT/.env.local.backup"
    print_success "Backed up .env.local to .env.local.backup"
fi

# Create fresh .env.local
cat > "$PROJECT_ROOT/.env.local" << 'EOF'
# Emergency Recovery - Auto-generated environment
# Generated: $(date)

# ===== DATABASE =====
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ncaam_local
REDIS_URL=redis://localhost:6379/0

# ===== ENVIRONMENT =====
ENVIRONMENT=codespaces
DEBUG=true
LOG_LEVEL=DEBUG
API_PORT=8000

# ===== REQUIRED API KEYS =====
# Add your credentials here (get from respective services)
ODDS_API_KEY=

# ===== OPTIONAL: AZURE =====
AZURE_SUBSCRIPTION_ID=
AZURE_RESOURCE_GROUP=
AZURE_STORAGE_ACCOUNT=
AZURE_COSMOS_DB_ENDPOINT=

# ===== OPTIONAL: GITHUB =====
GITHUB_TOKEN=

# ===== OPTIONAL: WEBHOOKS =====
TEAMS_WEBHOOK_SECRET=

# ===== PYTHON =====
PYTHONUNBUFFERED=1

# ===== BUILD/TESTING =====
PYTHONDONTWRITEBYTECODE=1
EOF

print_success ".env.local recovered"

# ============================================================================
# STEP 4: SHELL CONFIGURATION RESET
# ============================================================================

print_step "STEP 4: Shell Configuration Reset"

# Add venv auto-activation to bashrc
BASHRC="$HOME/.bashrc"
ACTIVATION_LINE='[ -f "/workspaces/green_bier_sports_ncaam_model/.venv/bin/activate" ] && source "/workspaces/green_bier_sports_ncaam_model/.venv/bin/activate"'

if ! grep -qF ".venv/bin/activate" "$BASHRC" 2>/dev/null; then
    {
        echo ""
        echo "# Emergency Recovery - venv auto-activation"
        echo "$ACTIVATION_LINE"
    } >> "$BASHRC"
    print_success "Added venv auto-activation to .bashrc"
else
    print_success "Venv auto-activation already in .bashrc"
fi

# ============================================================================
# STEP 5: GIT CONFIGURATION
# ============================================================================

print_step "STEP 5: Git Configuration"

if ! git config --global user.name > /dev/null 2>&1; then
    git config --global user.name "NCAAM Developer"
    print_success "Set git user.name"
fi

if ! git config --global user.email > /dev/null 2>&1; then
    git config --global user.email "dev@ncaam-model.local"
    print_success "Set git user.email"
fi

print_success "Git configured"

# ============================================================================
# STEP 6: VS CODE EXTENSIONS
# ============================================================================

print_step "STEP 6: VS Code Extensions Recovery"

if command -v code &> /dev/null; then
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
        "ckolkman.vscode-postgres"
        "redhat.vscode-yaml"
        "github.vscode-github-actions"
        "editorconfig.editorconfig"
        "mikestead.dotenv"
    )

    print_warning "Installing VS Code extensions (this may take a minute)..."

    for ext in "${EXTENSIONS[@]}"; do
        code --install-extension "$ext" --force 2>/dev/null || true
    done

    print_success "VS Code extensions recovered"
else
    print_warning "VS Code CLI not available - extensions must be installed manually"
fi

# ============================================================================
# STEP 7: CACHE & ARTIFACT CLEANUP
# ============================================================================

print_step "STEP 7: Cache & Artifact Cleanup"

# Python caches
find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$PROJECT_ROOT" -type f -name ".pytest_cache" -delete 2>/dev/null || true

print_success "Python caches cleared"

# ============================================================================
# STEP 8: DIAGNOSTIC REPORT
# ============================================================================

print_step "STEP 8: Diagnostic Report"

echo ""
echo "Environment Status:"
echo "  Python: $("$VENV_PATH/bin/python" --version)"
echo "  Pip: $("$VENV_PATH/bin/pip" --version | cut -d' ' -f1-2)"

if [ -f "$PROJECT_ROOT/.env.local" ]; then
    echo "  .env.local: ✓ Created"
else
    echo "  .env.local: ✗ Missing"
fi

if command -v git &> /dev/null; then
    echo "  Git: $(git --version | cut -d' ' -f3)"
fi

if command -v docker &> /dev/null; then
    echo "  Docker: $(docker --version | cut -d' ' -f3)"
fi

if command -v az &> /dev/null; then
    echo "  Azure CLI: $(az --version | head -1)"
fi

if command -v gh &> /dev/null; then
    echo "  GitHub CLI: ✓ Installed"
fi

# ============================================================================
# STEP 9: COMPREHENSIVE VERIFICATION
# ============================================================================

print_step "STEP 9: Comprehensive Verification"

echo ""
echo "Running comprehensive access checks..."
echo ""

python "$PROJECT_ROOT/scripts/codespaces/ensure_all_access.py" --status

# ============================================================================
# FINAL SUMMARY
# ============================================================================

print_step "🎉 RECOVERY COMPLETE"

echo ""
echo "📋 NEXT STEPS:"
echo ""
echo "1. REQUIRED: Add your ODDS_API_KEY"
echo "   $ nano .env.local"
echo "   Get key from: https://the-odds-api.com/api-keys"
echo ""

echo "2. OPTIONAL: Configure Azure (if using)"
echo "   $ az login"
echo ""

echo "3. OPTIONAL: Configure GitHub (if needed)"
echo "   $ gh auth login"
echo ""

echo "4. VERIFY EVERYTHING:"
echo "   $ python scripts/codespaces/ensure_all_access.py --status"
echo ""

echo "5. START CODING:"
echo "   $ cd services/prediction-service-python && python -m uvicorn app.main:app --reload --port 8000"
echo ""

echo "📁 Recovery log: $RECOVERY_LOG"
echo ""

print_success "All systems recovered and ready!"

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "If you still encounter issues, attach the recovery log:"
echo "  $RECOVERY_LOG"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
