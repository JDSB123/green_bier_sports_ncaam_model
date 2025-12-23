# Setup Microsoft Graph API App Registration for NCAAM
param(
    [string]$AppName = "NCAAM-Graph-Uploader"
)

$ErrorActionPreference = "Stop"

Write-Host "Creating App Registration: $AppName..."
$app = az ad app create --display-name $AppName --output json | ConvertFrom-Json
$appId = $app.appId
$objectId = $app.id

Write-Host "  App ID: $appId"

# Create Client Secret
Write-Host "Creating Client Secret..."
$secret = az ad app credential reset --id $appId --append --display-name "NCAAM-Secret" --output json | ConvertFrom-Json
$clientSecret = $secret.password

# Get Tenant ID
$account = az account show --output json | ConvertFrom-Json
$tenantId = $account.tenantId

# Grant Files.ReadWrite.All (Application Permission)
# API Permission ID for Microsoft Graph is 00000003-0000-0000-c000-000000000000
# Role ID for Files.ReadWrite.All is 01d488ea-095b-4dd7-8dc4-e83bd47b926c
Write-Host "Granting Files.ReadWrite.All permission..."
az ad app permission add --id $appId --api 00000003-0000-0000-c000-000000000000 --api-permissions 01d488ea-095b-4dd7-8dc4-e83bd47b926c=Role

Write-Host ""
Write-Host "⚠️  IMPORTANT: YOU MUST GRANT ADMIN CONSENT FOR THIS PERMISSION IN THE AZURE PORTAL" -ForegroundColor Yellow
Write-Host "   Go to: Entra ID > App Registrations > $AppName > API Permissions > Grant admin consent"
Write-Host ""

Write-Host "=== CONFIGURATION VALUES ===" -ForegroundColor Green
Write-Host "GRAPH_CLIENT_ID: $appId"
Write-Host "GRAPH_CLIENT_SECRET: $clientSecret"
Write-Host "GRAPH_TENANT_ID: $tenantId"
Write-Host ""
Write-Host "Run these commands to set secrets in your container app:"
Write-Host "az containerapp secret set -n ncaam-stable-prediction -g ncaam-stable-rg --secrets graph-client-id=$appId graph-client-secret=$clientSecret graph-tenant-id=$tenantId"
Write-Host "az containerapp update -n ncaam-stable-prediction -g ncaam-stable-rg --set-env-vars GRAPH_CLIENT_ID=secretref:graph-client-id GRAPH_CLIENT_SECRET=secretref:graph-client-secret GRAPH_TENANT_ID=secretref:graph-tenant-id"

