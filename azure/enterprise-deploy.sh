#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# GREEN BIER SPORT VENTURES - Enterprise Azure Deployment
# ═══════════════════════════════════════════════════════════════════════════════
#
# This script creates the enterprise Azure infrastructure for Green Bier Sport
# Ventures, with separate environments for each sport/league model.
#
# Architecture:
#   greenbier-enterprise-rg (Resource Group)
#   ├── greenbieracr (Azure Container Registry - shared)
#   ├── greenbier-keyvault (Key Vault - shared secrets)
#   ├── greenbier-ncaam-env (Container Apps Environment - NCAAM)
#   │   ├── ncaam-postgres (PostgreSQL + TimescaleDB)
#   │   ├── ncaam-redis (Redis cache)
#   │   └── ncaam-prediction (Prediction service)
#   ├── greenbier-nfl-env (Future: NFL model)
#   ├── greenbier-nba-env (Future: NBA model)
#   └── greenbier-mlb-env (Future: MLB model)
#
# Usage:
#   ./enterprise-deploy.sh              # Deploy NCAAM model
#   ./enterprise-deploy.sh --sport nfl  # Deploy NFL model (future)
#
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Enterprise-level resources (shared across all sports)
ENTERPRISE_NAME="${ENTERPRISE_NAME:-greenbier}"
RESOURCE_GROUP="${ENTERPRISE_NAME}-enterprise-rg"
LOCATION="${AZURE_LOCATION:-eastus}"
ACR_NAME="${ENTERPRISE_NAME}acr"
KEY_VAULT_NAME="${ENTERPRISE_NAME}-keyvault"

# Sport-specific configuration
SPORT="${1:-ncaam}"
SPORT_UPPER=$(echo "$SPORT" | tr '[:lower:]' '[:upper:]')
CONTAINER_APP_ENV="${ENTERPRISE_NAME}-${SPORT}-env"
POSTGRES_NAME="${SPORT}-postgres"
REDIS_NAME="${SPORT}-redis"
PREDICTION_NAME="${SPORT}-prediction"
IMAGE_TAG="${IMAGE_TAG:-v6.0}"

echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║  GREEN BIER SPORT VENTURES - Enterprise Azure Deployment                      ║"
echo "╠═══════════════════════════════════════════════════════════════════════════════╣"
echo "║  Enterprise:     $ENTERPRISE_NAME"
echo "║  Sport/Model:    $SPORT_UPPER"
echo "║  Location:       $LOCATION"
echo "║  Resource Group: $RESOURCE_GROUP"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# SPORT-SPECIFIC CONFIGURATION (from port_allocator.py)
# ═══════════════════════════════════════════════════════════════════════════════

# Sport port allocation - prevents conflicts across multiple sports
case $SPORT in
    ncaam)
        SPORT_OFFSET=0
        DB_USER="ncaam"
        DB_NAME="ncaam"
        ;;
    nfl)
        SPORT_OFFSET=1
        DB_USER="nfl"
        DB_NAME="nfl"
        ;;
    nba)
        SPORT_OFFSET=2
        DB_USER="nba"
        DB_NAME="nba"
        ;;
    mlb)
        SPORT_OFFSET=3
        DB_USER="mlb"
        DB_NAME="mlb"
        ;;
    nhl)
        SPORT_OFFSET=4
        DB_USER="nhl"
        DB_NAME="nhl"
        ;;
    *)
        # Dynamic allocation for unknown sports
        SPORT_OFFSET=$(($(echo -n "$SPORT" | cksum | cut -d' ' -f1) % 100 + 10))
        DB_USER="$SPORT"
        DB_NAME="$SPORT"
        ;;
esac

echo "  Sport Config:    DB_USER=$DB_USER, DB_NAME=$DB_NAME, offset=$SPORT_OFFSET"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# PRE-FLIGHT CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

# Run Python pre-deploy checks if available
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/pre_deploy_check.py" ]; then
    echo "Running pre-deployment validation..."
    if python3 "$SCRIPT_DIR/pre_deploy_check.py" "$SPORT" --target azure; then
        echo "Pre-deployment checks passed"
    else
        echo "Pre-deployment checks FAILED. Fix errors before continuing."
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    echo ""
fi

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo "Azure CLI not found. Install: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# Login check
echo "Checking Azure login..."
az account show &> /dev/null || {
    echo "Not logged in. Running az login..."
    az login
}

SUBSCRIPTION=$(az account show --query name -o tsv)
echo "Logged in to subscription: $SUBSCRIPTION"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: ENTERPRISE INFRASTRUCTURE (Shared)
# ═══════════════════════════════════════════════════════════════════════════════

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "PHASE 1: Creating Enterprise Infrastructure (Shared Resources)"
echo "═══════════════════════════════════════════════════════════════════════════════"

# Create Resource Group
echo "📦 Creating resource group: $RESOURCE_GROUP"
az group create \
    --name $RESOURCE_GROUP \
    --location $LOCATION \
    --tags "enterprise=$ENTERPRISE_NAME" "managed-by=greenbier-deploy" \
    --output none

# Create Azure Container Registry (shared across all sports)
echo "🐳 Creating Azure Container Registry: $ACR_NAME"
az acr create \
    --resource-group $RESOURCE_GROUP \
    --name $ACR_NAME \
    --sku Standard \
    --admin-enabled true \
    --output none 2>/dev/null || echo "   (ACR already exists)"

# Login to ACR
echo "🔐 Logging into ACR..."
az acr login --name $ACR_NAME

# Create Key Vault (shared secrets across all sports)
echo "🔒 Creating Key Vault: $KEY_VAULT_NAME"
az keyvault create \
    --name $KEY_VAULT_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --enable-soft-delete false \
    --output none 2>/dev/null || echo "   (Key Vault already exists)"

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: SPORT-SPECIFIC SECRETS
# ═══════════════════════════════════════════════════════════════════════════════

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "PHASE 2: Configuring Secrets for $SPORT_UPPER"
echo "═══════════════════════════════════════════════════════════════════════════════"

# Store sport-specific secrets
SECRET_PREFIX="${SPORT}"

if [ -f "secrets/db_password.txt" ]; then
    echo "💾 Storing ${SPORT}-db-password..."
    az keyvault secret set \
        --vault-name $KEY_VAULT_NAME \
        --name "${SECRET_PREFIX}-db-password" \
        --value "$(cat secrets/db_password.txt)" \
        --output none
else
    echo "⚠️  secrets/db_password.txt not found. Generating random password..."
    DB_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
    az keyvault secret set \
        --vault-name $KEY_VAULT_NAME \
        --name "${SECRET_PREFIX}-db-password" \
        --value "$DB_PASSWORD" \
        --output none
    echo "$DB_PASSWORD" > secrets/db_password.txt
    echo "   ✓ Generated and stored in secrets/db_password.txt"
fi

if [ -f "secrets/redis_password.txt" ]; then
    echo "💾 Storing ${SPORT}-redis-password..."
    az keyvault secret set \
        --vault-name $KEY_VAULT_NAME \
        --name "${SECRET_PREFIX}-redis-password" \
        --value "$(cat secrets/redis_password.txt)" \
        --output none
else
    echo "⚠️  secrets/redis_password.txt not found. Generating random password..."
    REDIS_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
    az keyvault secret set \
        --vault-name $KEY_VAULT_NAME \
        --name "${SECRET_PREFIX}-redis-password" \
        --value "$REDIS_PASSWORD" \
        --output none
    echo "$REDIS_PASSWORD" > secrets/redis_password.txt
    echo "   ✓ Generated and stored in secrets/redis_password.txt"
fi

if [ -f "secrets/odds_api_key.txt" ]; then
    echo "💾 Storing ${SPORT}-odds-api-key..."
    az keyvault secret set \
        --vault-name $KEY_VAULT_NAME \
        --name "${SECRET_PREFIX}-odds-api-key" \
        --value "$(cat secrets/odds_api_key.txt)" \
        --output none
else
    echo "❌ secrets/odds_api_key.txt not found. This is REQUIRED."
    echo "   Get your API key from https://the-odds-api.com/"
    exit 1
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: BUILD & PUSH CONTAINER IMAGES
# ═══════════════════════════════════════════════════════════════════════════════

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "PHASE 3: Building Container Images for $SPORT_UPPER"
echo "═══════════════════════════════════════════════════════════════════════════════"

# Build prediction service
echo "🔨 Building prediction service image..."
docker build \
    -f services/prediction-service-python/Dockerfile.hardened \
    -t $ACR_NAME.azurecr.io/${SPORT}-prediction:$IMAGE_TAG \
    .

echo "📤 Pushing to ACR..."
docker push $ACR_NAME.azurecr.io/${SPORT}-prediction:$IMAGE_TAG

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: CONTAINER APPS ENVIRONMENT
# ═══════════════════════════════════════════════════════════════════════════════

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "PHASE 4: Creating Container Apps Environment for $SPORT_UPPER"
echo "═══════════════════════════════════════════════════════════════════════════════"

echo "🌐 Creating Container Apps environment: $CONTAINER_APP_ENV"
az containerapp env create \
    --name $CONTAINER_APP_ENV \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --output none 2>/dev/null || echo "   (Environment already exists)"

# Get secrets for container creation
DB_PASSWORD=$(az keyvault secret show --vault-name $KEY_VAULT_NAME --name "${SECRET_PREFIX}-db-password" --query value -o tsv)
REDIS_PASSWORD=$(az keyvault secret show --vault-name $KEY_VAULT_NAME --name "${SECRET_PREFIX}-redis-password" --query value -o tsv)
ODDS_API_KEY=$(az keyvault secret show --vault-name $KEY_VAULT_NAME --name "${SECRET_PREFIX}-odds-api-key" --query value -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: DEPLOY CONTAINERS
# ═══════════════════════════════════════════════════════════════════════════════

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "PHASE 5: Deploying Containers for $SPORT_UPPER"
echo "═══════════════════════════════════════════════════════════════════════════════"

# PostgreSQL with TimescaleDB
echo "🗄️  Creating PostgreSQL container: $POSTGRES_NAME"
az containerapp create \
    --name $POSTGRES_NAME \
    --resource-group $RESOURCE_GROUP \
    --environment $CONTAINER_APP_ENV \
    --image timescale/timescaledb:latest-pg15 \
    --cpu 1.0 \
    --memory 2.0Gi \
    --min-replicas 1 \
    --max-replicas 1 \
    --env-vars \
        POSTGRES_DB=${SPORT} \
        POSTGRES_USER=${SPORT} \
        POSTGRES_PASSWORD="$DB_PASSWORD" \
    --output none 2>/dev/null || echo "   (Updating existing container)"

# Redis
echo "🔴 Creating Redis container: $REDIS_NAME"
az containerapp create \
    --name $REDIS_NAME \
    --resource-group $RESOURCE_GROUP \
    --environment $CONTAINER_APP_ENV \
    --image redis:7-alpine \
    --cpu 0.5 \
    --memory 0.5Gi \
    --min-replicas 1 \
    --max-replicas 1 \
    --command "/bin/sh" "-c" "redis-server --requirepass $REDIS_PASSWORD" \
    --output none 2>/dev/null || echo "   (Updating existing container)"

# Prediction Service
echo "🎯 Creating prediction service: $PREDICTION_NAME"
az containerapp create \
    --name $PREDICTION_NAME \
    --resource-group $RESOURCE_GROUP \
    --environment $CONTAINER_APP_ENV \
    --image $ACR_NAME.azurecr.io/${SPORT}-prediction:$IMAGE_TAG \
    --cpu 1.0 \
    --memory 2.0Gi \
    --min-replicas 1 \
    --max-replicas 3 \
    --registry-server $ACR_NAME.azurecr.io \
    --registry-username $ACR_NAME \
    --registry-password "$ACR_PASSWORD" \
    --env-vars \
        DATABASE_URL="postgresql://${SPORT}:${DB_PASSWORD}@${POSTGRES_NAME}:5432/${SPORT}" \
        REDIS_URL="redis://:${REDIS_PASSWORD}@${REDIS_NAME}:6379" \
        THE_ODDS_API_KEY="$ODDS_API_KEY" \
        SPORT="$SPORT" \
        MODEL__HOME_COURT_ADVANTAGE_SPREAD=3.0 \
        MODEL__HOME_COURT_ADVANTAGE_TOTAL=4.5 \
        TZ=America/Chicago \
    --ingress external \
    --target-port 8082 \
    --output none 2>/dev/null || echo "   (Updating existing container)"

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6: VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "PHASE 6: Deployment Verification"
echo "═══════════════════════════════════════════════════════════════════════════════"

# Get service URL
SERVICE_URL=$(az containerapp show --name $PREDICTION_NAME --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn -o tsv 2>/dev/null || echo "pending")

echo ""
echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║  ✅ GREEN BIER SPORT VENTURES - Deployment Complete!                          ║"
echo "╠═══════════════════════════════════════════════════════════════════════════════╣"
echo "║  Enterprise Resources (Shared):                                               ║"
echo "║    Resource Group:    $RESOURCE_GROUP"
echo "║    Container Registry: $ACR_NAME.azurecr.io"
echo "║    Key Vault:         $KEY_VAULT_NAME"
echo "║                                                                               ║"
echo "║  $SPORT_UPPER Model Resources:                                                       ║"
echo "║    Environment:       $CONTAINER_APP_ENV"
echo "║    PostgreSQL:        $POSTGRES_NAME"
echo "║    Redis:             $REDIS_NAME"
echo "║    Prediction Service: $PREDICTION_NAME"
echo "║    Service URL:       https://$SERVICE_URL"
echo "╠═══════════════════════════════════════════════════════════════════════════════╣"
echo "║  Next Steps:                                                                  ║"
echo "║  1. Run database migrations                                                   ║"
echo "║  2. Verify team matching accuracy                                            ║"
echo "║  3. Run predictions: az containerapp exec -n $PREDICTION_NAME -g $RESOURCE_GROUP --command 'python /app/run_today.py'"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
