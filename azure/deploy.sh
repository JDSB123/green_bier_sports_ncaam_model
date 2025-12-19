#!/bin/bash
# Azure Deployment Script for NCAA Basketball v5.1
# This script automates the deployment to Azure Container Apps

set -e

# Configuration
RESOURCE_GROUP="ncaam-v5-rg"
LOCATION="eastus"
ACR_NAME="ncaamv5registry"
KEY_VAULT_NAME="ncaam-v5-secrets"
CONTAINER_APP_ENV="ncaam-v5-env"
POSTGRES_NAME="ncaam-postgres"
REDIS_NAME="ncaam-redis"
PREDICTION_NAME="ncaam-prediction"
IMAGE_TAG="v5.1"

echo "🚀 Starting Azure Deployment for NCAA Basketball v5.1"
echo "=================================================="

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# Login check
echo "📋 Checking Azure login..."
az account show &> /dev/null || {
    echo "⚠️  Not logged in. Running az login..."
    az login
}

# Create Resource Group
echo "📦 Creating resource group: $RESOURCE_GROUP"
az group create \
    --name $RESOURCE_GROUP \
    --location $LOCATION \
    --output none

# Create Azure Container Registry
echo "🐳 Creating Azure Container Registry: $ACR_NAME"
az acr create \
    --resource-group $RESOURCE_GROUP \
    --name $ACR_NAME \
    --sku Basic \
    --admin-enabled true \
    --output none

# Login to ACR
echo "🔐 Logging into ACR..."
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)
az acr login --name $ACR_NAME

# Build and push image
echo "🔨 Building and pushing container image..."
docker build \
    -f services/prediction-service-python/Dockerfile.hardened \
    -t $ACR_NAME.azurecr.io/ncaam-prediction:$IMAGE_TAG \
    .

docker push $ACR_NAME.azurecr.io/ncaam-prediction:$IMAGE_TAG

# Create Key Vault
echo "🔒 Creating Azure Key Vault: $KEY_VAULT_NAME"
az keyvault create \
    --name $KEY_VAULT_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --output none

# Store secrets (prompt user if files don't exist)
if [ -f "secrets/db_password.txt" ]; then
    echo "💾 Storing database password..."
    az keyvault secret set \
        --vault-name $KEY_VAULT_NAME \
        --name db-password \
        --value "$(cat secrets/db_password.txt)" \
        --output none
else
    echo "⚠️  secrets/db_password.txt not found. Please create it or set manually in Key Vault."
fi

if [ -f "secrets/redis_password.txt" ]; then
    echo "💾 Storing Redis password..."
    az keyvault secret set \
        --vault-name $KEY_VAULT_NAME \
        --name redis-password \
        --value "$(cat secrets/redis_password.txt)" \
        --output none
else
    echo "⚠️  secrets/redis_password.txt not found. Please create it or set manually in Key Vault."
fi

if [ -f "secrets/odds_api_key.txt" ]; then
    echo "💾 Storing Odds API key..."
    az keyvault secret set \
        --vault-name $KEY_VAULT_NAME \
        --name odds-api-key \
        --value "$(cat secrets/odds_api_key.txt)" \
        --output none
else
    echo "⚠️  secrets/odds_api_key.txt not found. Please create it or set manually in Key Vault."
fi

# Create Container Apps Environment
echo "🌐 Creating Container Apps environment: $CONTAINER_APP_ENV"
az containerapp env create \
    --name $CONTAINER_APP_ENV \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --output none

# Create PostgreSQL Container App
echo "🗄️  Creating PostgreSQL container..."
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
        POSTGRES_DB=ncaam \
        POSTGRES_USER=ncaam \
        POSTGRES_PASSWORD="$(az keyvault secret show --vault-name $KEY_VAULT_NAME --name db-password --query value -o tsv)" \
    --output none

# Create Redis Container App
echo "🔴 Creating Redis container..."
az containerapp create \
    --name $REDIS_NAME \
    --resource-group $RESOURCE_GROUP \
    --environment $CONTAINER_APP_ENV \
    --image redis:7-alpine \
    --cpu 0.5 \
    --memory 0.5Gi \
    --min-replicas 1 \
    --max-replicas 1 \
    --env-vars \
        REDIS_PASSWORD="$(az keyvault secret show --vault-name $KEY_VAULT_NAME --name redis-password --query value -o tsv)" \
    --output none

# Create Prediction Service Container App
echo "🎯 Creating prediction service container..."
az containerapp create \
    --name $PREDICTION_NAME \
    --resource-group $RESOURCE_GROUP \
    --environment $CONTAINER_APP_ENV \
    --image $ACR_NAME.azurecr.io/ncaam-prediction:$IMAGE_TAG \
    --cpu 1.0 \
    --memory 1.0Gi \
    --min-replicas 1 \
    --max-replicas 1 \
    --registry-server $ACR_NAME.azurecr.io \
    --registry-username $ACR_NAME \
    --registry-password "$ACR_PASSWORD" \
    --env-vars \
        DATABASE_URL="postgresql://ncaam:$(az keyvault secret show --vault-name $KEY_VAULT_NAME --name db-password --query value -o tsv)@$POSTGRES_NAME:5432/ncaam" \
        REDIS_URL="redis://:$(az keyvault secret show --vault-name $KEY_VAULT_NAME --name redis-password --query value -o tsv)@$REDIS_NAME:6379" \
        THE_ODDS_API_KEY="$(az keyvault secret show --vault-name $KEY_VAULT_NAME --name odds-api-key --query value -o tsv)" \
        MODEL__HOME_COURT_ADVANTAGE_SPREAD=3.0 \
        MODEL__HOME_COURT_ADVANTAGE_TOTAL=4.5 \
    --ingress external \
    --target-port 8082 \
    --output none

echo ""
echo "✅ Deployment complete!"
echo "=================================================="
echo "Resource Group: $RESOURCE_GROUP"
echo "Container Apps Environment: $CONTAINER_APP_ENV"
echo "Key Vault: $KEY_VAULT_NAME"
echo ""
echo "Next steps:"
echo "1. Run database migrations:"
echo "   az containerapp exec --name $POSTGRES_NAME --resource-group $RESOURCE_GROUP --command 'psql -U ncaam -d ncaam -f /migrations/001_initial_schema.sql'"
echo ""
echo "2. Get prediction service URL:"
echo "   az containerapp show --name $PREDICTION_NAME --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn -o tsv"
