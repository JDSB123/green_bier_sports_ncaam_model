#!/bin/bash
# Checks Azure CLI connectivity and resource access
set -euo pipefail

if ! command -v az &> /dev/null; then
  echo "Azure CLI (az) not installed."
  exit 1
fi

echo "Checking Azure CLI login..."
az account show &> /dev/null && echo "✅ Azure CLI is logged in." || {
  echo "❌ Azure CLI is not logged in. Run 'az login' or configure service principal."; exit 1;
}

RESOURCE_GROUP="NCAAM-GBSV-MODEL-RG"
ACR_NAME="ncaamstablegbsvacr"

# Check resource group
if az group show --name "$RESOURCE_GROUP" &> /dev/null; then
  echo "✅ Resource group $RESOURCE_GROUP exists."
else
  echo "❌ Resource group $RESOURCE_GROUP not found."
  exit 1
fi

# Check ACR access
if az acr show --name "$ACR_NAME" &> /dev/null; then
  echo "✅ Azure Container Registry $ACR_NAME exists."
else
  echo "❌ Azure Container Registry $ACR_NAME not found."
  exit 1
fi

echo "All Azure connectivity checks passed."
