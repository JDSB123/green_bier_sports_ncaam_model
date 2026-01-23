#!/bin/bash
# Universal Access Manager - Handles all credentials, logins, and access issues
# Works across all environments (codespaces, local, CI/CD, production)

set -e

PROJECT_ROOT="/workspaces/green_bier_sports_ncaam_model"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          UNIVERSAL ACCESS & LOGIN MANAGER                     ║"
echo "║   Ensures all credentials and access stays available          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================================================
# SECTION 1: ENVIRONMENT DETECTION
# ============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Environment Detection"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -n "$CODESPACES" ]; then
    ENV_TYPE="codespaces"
    echo -e "${GREEN}✓${NC} Running in GitHub Codespaces"
elif [ -n "$CI" ]; then
    ENV_TYPE="ci-cd"
    echo -e "${GREEN}✓${NC} Running in CI/CD environment"
elif [ -n "$PROD" ]; then
    ENV_TYPE="production"
    echo -e "${GREEN}✓${NC} Running in Production"
else
    ENV_TYPE="local"
    echo -e "${GREEN}✓${NC} Running locally"
fi

# ============================================================================
# SECTION 2: ENV FILE MANAGEMENT
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚙️  Environment Files Management"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Create environment files if they don't exist
create_env_file() {
    local env_file=$1
    local env_type=$2

    if [ ! -f "$env_file" ]; then
        echo "Creating $env_type environment file..."

        case $env_type in
            local)
                cat > "$env_file" << 'EOF'
# Local Development Environment
# Copy from .env.example or update with your values

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ncaam_local
REDIS_URL=redis://localhost:6379/0

ENVIRONMENT=local
DEBUG=true
LOG_LEVEL=DEBUG
API_PORT=8000

# API Keys (get from respective services)
ODDS_API_KEY=

# Optional
GITHUB_TOKEN=
TEAMS_WEBHOOK_SECRET=
AZURE_SUBSCRIPTION_ID=

PYTHONUNBUFFERED=1
EOF
                ;;
            staging)
                cat > "$env_file" << 'EOF'
# Staging Environment
# Use with caution - connects to staging resources

DATABASE_URL=
REDIS_URL=

ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO
API_PORT=8000

# API Keys for staging
ODDS_API_KEY=
GITHUB_TOKEN=
AZURE_SUBSCRIPTION_ID=

PYTHONUNBUFFERED=1
EOF
                ;;
            production)
                cat > "$env_file" << 'EOF'
# Production Environment
# CRITICAL: Use environment variables or secrets manager
# DO NOT hardcode sensitive values here

ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
API_PORT=8000

# Production values should come from:
# - Azure Key Vault
# - GitHub Secrets
# - Environment variables
# - Managed identity

PYTHONUNBUFFERED=1
EOF
                ;;
        esac

        echo -e "${GREEN}✓${NC} Created $env_file"
    else
        echo -e "${GREEN}✓${NC} $env_file already exists"
    fi
}

create_env_file "$PROJECT_ROOT/.env.local" "local"
create_env_file "$PROJECT_ROOT/.env.staging" "staging"
create_env_file "$PROJECT_ROOT/.env.production" "production"

# ============================================================================
# SECTION 3: GIT CONFIGURATION
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 Git Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check and configure Git
if git config --global user.name > /dev/null 2>&1; then
    GIT_USER=$(git config --global user.name)
    echo -e "${GREEN}✓${NC} Git user: $GIT_USER"
else
    if [ "$ENV_TYPE" != "ci-cd" ] && [ "$ENV_TYPE" != "production" ]; then
        echo -e "${YELLOW}⚠${NC} Git user not configured"
        echo "  Run: git config --global user.name 'Your Name'"
    fi
fi

if git config --global user.email > /dev/null 2>&1; then
    GIT_EMAIL=$(git config --global user.email)
    echo -e "${GREEN}✓${NC} Git email: $GIT_EMAIL"
else
    if [ "$ENV_TYPE" != "ci-cd" ] && [ "$ENV_TYPE" != "production" ]; then
        echo -e "${YELLOW}⚠${NC} Git email not configured"
        echo "  Run: git config --global user.email 'your.email@example.com'"
    fi
fi

# ============================================================================
# SECTION 4: SSH KEYS
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔑 SSH Keys Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SSH_DIR="$HOME/.ssh"

if [ -d "$SSH_DIR" ]; then
    SSH_KEYS=$(find "$SSH_DIR" -maxdepth 1 -name "id_*" -o -name "*.pem" 2>/dev/null | wc -l)
    if [ "$SSH_KEYS" -gt 0 ]; then
        echo -e "${GREEN}✓${NC} SSH keys found ($SSH_KEYS files)"
    else
        echo -e "${YELLOW}⚠${NC} No SSH keys found"
        if [ "$ENV_TYPE" = "codespaces" ]; then
            echo "  SSH keys are auto-mounted in Codespaces"
        fi
    fi
else
    echo -e "${YELLOW}⚠${NC} SSH directory not found"
fi

# ============================================================================
# SECTION 5: VSCODE EXTENSIONS AUTO-INSTALL
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧩 VS Code Extensions"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if code command is available
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
        "github.copilot"
        "github.copilot-chat"
    )

    echo "Checking VS Code extensions..."
    INSTALLED=0
    MISSING=0

    for ext in "${EXTENSIONS[@]}"; do
        if code --list-extensions 2>/dev/null | grep -q "^${ext}$"; then
            INSTALLED=$((INSTALLED + 1))
        else
            echo -e "  Installing $ext..."
            code --install-extension "$ext" --force 2>/dev/null || true
            MISSING=$((MISSING + 1))
        fi
    done

    echo -e "${GREEN}✓${NC} VS Code extensions: $INSTALLED installed, $MISSING fixed"
else
    echo -e "${YELLOW}⚠${NC} VS Code CLI not available (expected in remote environments)"
    echo "  Extensions are pre-configured in devcontainer.json"
fi

# ============================================================================
# SECTION 6: CLOUD PROVIDER ACCESS CHECKS
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "☁️  Cloud Provider Access"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Azure CLI
if command -v az &> /dev/null; then
    if az account show > /dev/null 2>&1; then
        AZURE_USER=$(az account show --query "user.name" -o tsv 2>/dev/null)
        echo -e "${GREEN}✓${NC} Azure CLI logged in as: $AZURE_USER"
    else
        echo -e "${YELLOW}⚠${NC} Azure CLI not logged in"
        echo "  Run: az login"
    fi
else
    echo -e "${YELLOW}⚠${NC} Azure CLI not installed"
fi

# Check GitHub CLI
if command -v gh &> /dev/null; then
    if gh auth status > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} GitHub CLI logged in"
    else
        echo -e "${YELLOW}⚠${NC} GitHub CLI not logged in"
        echo "  Run: gh auth login"
    fi
else
    echo -e "${YELLOW}⚠${NC} GitHub CLI not installed"
fi

# ============================================================================
# SECTION 7: SECRETS VALIDATION
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔒 Secrets & API Keys Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CRITICAL_VARS=(
    "ODDS_API_KEY"
    "DATABASE_URL"
)

for var in "${CRITICAL_VARS[@]}"; do
    if [ -n "${!var}" ]; then
        if [ "$var" = "ODDS_API_KEY" ]; then
            echo -e "${GREEN}✓${NC} $var is set"
        else
            echo -e "${GREEN}✓${NC} $var is set"
        fi
    else
        # Check in env file
        if grep -q "^${var}=" "$PROJECT_ROOT/.env.local" 2>/dev/null; then
            ENV_VAL=$(grep "^${var}=" "$PROJECT_ROOT/.env.local" | cut -d= -f2)
            if [ -n "$ENV_VAL" ]; then
                echo -e "${GREEN}✓${NC} $var found in .env.local"
            else
                echo -e "${RED}✗${NC} $var is empty in .env.local (REQUIRED)"
            fi
        else
            echo -e "${RED}✗${NC} $var not found (REQUIRED)"
        fi
    fi
done

# ============================================================================
# SECTION 8: FINAL STATUS & RECOMMENDATIONS
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Quick Actions"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "1️⃣  Add your ODDS_API_KEY to .env.local"
echo "    Get from: https://the-odds-api.com/api-keys"
echo ""

if [ "$ENV_TYPE" = "codespaces" ]; then
    echo "2️⃣  For Azure access, run:"
    echo "    az login"
    echo ""
fi

if [ "$ENV_TYPE" = "codespaces" ] || [ "$ENV_TYPE" = "local" ]; then
    echo "3️⃣  For GitHub access, run:"
    echo "    gh auth login"
    echo ""
fi

echo "4️⃣  Verify all access:"
echo "    python scripts/codespaces/ensure_all_access.py --status"
echo ""

echo -e "${GREEN}✓ Access manager complete!${NC}"
echo ""
