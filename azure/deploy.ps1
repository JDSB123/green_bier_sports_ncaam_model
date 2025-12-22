# ═══════════════════════════════════════════════════════════════════════════════
# NCAAM v6.3 - Azure Deployment Script
# ═══════════════════════════════════════════════════════════════════════════════
# Usage:
#   .\deploy.ps1 -Environment prod -OddsApiKey "YOUR_ACTUAL_KEY"
#   .\deploy.ps1 -Environment dev -OddsApiKey "YOUR_ACTUAL_KEY" -SkipInfra
#   Note: -OddsApiKey parameter sets environment variable THE_ODDS_API_KEY in the container
#   Optional: -TeamsWebhookUrl sets TEAMS_WEBHOOK_URL secret/env var for run_today.py --teams
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('dev', 'staging', 'prod', 'stable')]
    [string]$Environment = 'prod',

    [Parameter(Mandatory=$false)]
    [string]$OddsApiKey,

    [Parameter(Mandatory=$false)]
    [string]$TeamsWebhookUrl = '',

    [Parameter(Mandatory=$false)]
    [string]$Location = 'centralus',

    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = 'ncaam-stable-rg',

    [Parameter(Mandatory=$false)]
    [switch]$SkipInfra,

    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild,

    [Parameter(Mandatory=$false)]
    [string]$ImageTag = 'v6.3.21',

    [Parameter(Mandatory=$false)]
    [switch]$EnterpriseMode = $true
)

$ErrorActionPreference = 'Stop'

# ─────────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────────

$baseName = 'ncaam'
$resourcePrefix = "$baseName-$Environment"

# Enterprise mode: Use greenbier-enterprise-rg with ncaam- prefixed resources
if ($EnterpriseMode) {
    if ([string]::IsNullOrEmpty($ResourceGroup)) {
        $ResourceGroup = 'greenbier-enterprise-rg'
        # Ensure location matches enterprise RG (default to eastus)
        if ($Location -eq 'centralus') {
            $Location = 'eastus'
        }
    }
    # In enterprise mode, prefix all resource names with 'ncaam-' to organize within RG
    # Resource names stay the same, just organized in enterprise RG
    
    # HARDCODED: Enforce the 'gbe' naming convention for existing Enterprise resources
    # This prevents duplicate resource creation (e.g. ncaamprodacr vs ncaamprodgbeacr)
    if ($Environment -eq 'prod') {
        $acrName = 'ncaamprodgbeacr'
        # Bicep parameters will need to match this convention via overrides or updates
    } else {
        $acrName = ($resourcePrefix -replace '-', '') + 'gbeacr'
    }
} else {
    # Standard mode: Use dedicated resource group per environment
    if ([string]::IsNullOrEmpty($ResourceGroup)) {
        $ResourceGroup = "$resourcePrefix-rg"
    }
    $acrName = ($resourcePrefix -replace '-', '') + 'acr'
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  NCAAM v6.3 - Azure Deployment" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Environment:    $Environment" -ForegroundColor Yellow
Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor Yellow
Write-Host "  Location:       $Location" -ForegroundColor Yellow
Write-Host "  Enterprise Mode: $EnterpriseMode" -ForegroundColor Yellow
Write-Host "  ACR Name:       $acrName" -ForegroundColor Yellow
Write-Host "  Image Tag:      $ImageTag" -ForegroundColor Yellow
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────────
# AUTO-FETCH SECRETS (IF MISSING)
# ─────────────────────────────────────────────────────────────────────────────────

if ([string]::IsNullOrEmpty($OddsApiKey)) {
    Write-Host "[0/6] Odds API Key not provided. Attempting to fetch from existing container app..." -ForegroundColor Cyan
    
    # Try to find the existing container app name
    $existingAppName = "$resourcePrefix-prediction"
    
    try {
        # Check if app exists
        $appExists = az containerapp show --name $existingAppName --resource-group $ResourceGroup --query "id" -o tsv 2>$null
        
        if ($appExists) {
            Write-Host "  Found existing app: $existingAppName" -ForegroundColor Gray
            $fetchedKey = az containerapp secret list --name $existingAppName --resource-group $ResourceGroup --show-values --query "[?name=='odds-api-key'].value" -o tsv 2>$null
            
            if ($fetchedKey) {
                $OddsApiKey = $fetchedKey
                Write-Host "  ✓ Successfully retrieved Odds API Key from Azure!" -ForegroundColor Green
            } else {
                Write-Warning "  ! Could not retrieve key (secret 'odds-api-key' not found)."
            }
        } else {
            Write-Warning "  ! App '$existingAppName' not found in RG '$ResourceGroup'. Cannot fetch key."
        }
    } catch {
        Write-Warning "  ! Error fetching existing key: $_"
    }
    
    # If still empty, check if we can proceed (e.g. maybe SkipInfra doesn't need it?)
    # But Bicep usually needs it. If we can't find it, we must fail.
    if ([string]::IsNullOrEmpty($OddsApiKey)) {
        if (-not $SkipInfra) {
            Write-Error "OddsApiKey is required for infrastructure deployment and could not be found automatically. Please provide it via -OddsApiKey."
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────────
# PREREQUISITES CHECK
# ─────────────────────────────────────────────────────────────────────────────────

Write-Host "[1/6] Checking prerequisites..." -ForegroundColor Green

# Check Azure CLI
try {
    $azVersion = az version --output json | ConvertFrom-Json
    Write-Host "  ✓ Azure CLI: $($azVersion.'azure-cli')" -ForegroundColor Gray
} catch {
    Write-Error "Azure CLI not found. Install from https://aka.ms/installazurecliwindows"
}

# Check Docker
try {
    docker version --format '{{.Server.Version}}' | Out-Null
    Write-Host "  ✓ Docker: Running" -ForegroundColor Gray
} catch {
    Write-Error "Docker not running. Start Docker Desktop."
}

# Check logged in to Azure
$account = az account show --output json 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "  ! Not logged in to Azure. Running 'az login'..." -ForegroundColor Yellow
    az login
    $account = az account show --output json | ConvertFrom-Json
}
Write-Host "  ✓ Azure Account: $($account.name)" -ForegroundColor Gray

# ─────────────────────────────────────────────────────────────────────────────────
# GENERATE PASSWORDS
# ─────────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "[2/6] Generating secure passwords..." -ForegroundColor Green

# Generate secure passwords
$postgresPassword = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
$redisPassword = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})

Write-Host "  ✓ PostgreSQL password generated (32 chars)" -ForegroundColor Gray
Write-Host "  ✓ Redis password generated (32 chars)" -ForegroundColor Gray

# Optional: Load Teams webhook from repo secret file if not explicitly provided
if ([string]::IsNullOrWhiteSpace($TeamsWebhookUrl)) {
    $teamsSecretPath = Join-Path $PSScriptRoot "..\\secrets\\teams_webhook_url.txt"
    if (Test-Path $teamsSecretPath) {
        $TeamsWebhookUrl = (Get-Content $teamsSecretPath -Raw).Trim()
    }
}

# Sanity check / ignore placeholder Teams webhook
if ($TeamsWebhookUrl) {
    $tw = $TeamsWebhookUrl.ToLowerInvariant()
    if ($tw.Contains("change_me") -or $tw.StartsWith("your_") -or ($tw -notlike "*webhook.office.com*") -or ($TeamsWebhookUrl.Length -lt 60)) {
        Write-Host "  [INFO] Teams webhook not configured (placeholder). Skipping Teams webhook env var." -ForegroundColor Gray
        $TeamsWebhookUrl = ''
    } else {
        Write-Host "  ✓ Teams webhook configured (will enable run_today.py --teams)" -ForegroundColor Gray
    }
}

# ─────────────────────────────────────────────────────────────────────────────────
# DEPLOY INFRASTRUCTURE
# ─────────────────────────────────────────────────────────────────────────────────

if (-not $SkipInfra) {
    Write-Host ""
    Write-Host "[3/6] Deploying Azure infrastructure..." -ForegroundColor Green

    # Create resource group
    Write-Host "  Creating resource group: $ResourceGroup" -ForegroundColor Gray
    az group create --name $ResourceGroup --location $Location --output none

    # Deploy Bicep template
    Write-Host "  Deploying Bicep template (this may take 10-15 minutes)..." -ForegroundColor Gray

    # Calculate resource names for 'gbe' convention in Enterprise mode
    $resourceNameSuffix = ''
    if ($EnterpriseMode) {
        $resourceNameSuffix = '-gbe'
    }

    $deploymentOutput = az deployment group create `
        --resource-group $ResourceGroup `
        --template-file "$PSScriptRoot\main.bicep" `
        --parameters `
            environment=$Environment `
            location=$Location `
            baseName=$baseName `
            postgresPassword=$postgresPassword `
            redisPassword=$redisPassword `
            oddsApiKey=$OddsApiKey `
            teamsWebhookUrl=$TeamsWebhookUrl `
            imageTag=$ImageTag `
            resourceNameSuffix=$resourceNameSuffix `
        --output json | ConvertFrom-Json

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Bicep deployment failed!"
    }

    $acrLoginServer = $deploymentOutput.properties.outputs.acrLoginServer.value
    $postgresHost = $deploymentOutput.properties.outputs.postgresHost.value
    $containerAppUrl = $deploymentOutput.properties.outputs.containerAppUrl.value

    Write-Host "  ✓ ACR: $acrLoginServer" -ForegroundColor Gray
    Write-Host "  ✓ PostgreSQL: $postgresHost" -ForegroundColor Gray
    Write-Host "  ✓ Container App URL: https://$containerAppUrl" -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "[3/6] Skipping infrastructure deployment (--SkipInfra)" -ForegroundColor Yellow

    # Get existing ACR login server
    $acrLoginServer = az acr show --name $acrName --query loginServer --output tsv
    Write-Host "  Using existing ACR: $acrLoginServer" -ForegroundColor Gray
}

# ─────────────────────────────────────────────────────────────────────────────────
# BUILD AND PUSH DOCKER IMAGE
# ─────────────────────────────────────────────────────────────────────────────────

if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "[4/6] Building and pushing Docker image..." -ForegroundColor Green

    # Login to ACR
    Write-Host "  Logging in to ACR..." -ForegroundColor Gray
    az acr login --name $acrName

    # Build image
    $imageName = "$acrLoginServer/$baseName-prediction:$ImageTag"
    Write-Host "  Building image: $imageName" -ForegroundColor Gray

    Push-Location "$PSScriptRoot\.."
    docker build -t $imageName -f services/prediction-service-python/Dockerfile.hardened .

    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        Write-Error "Docker build failed!"
    }

    # Push image
    Write-Host "  Pushing image to ACR..." -ForegroundColor Gray
    docker push $imageName

    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        Write-Error "Docker push failed!"
    }

    Pop-Location
    Write-Host "  ✓ Image pushed: $imageName" -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "[4/6] Skipping Docker build (--SkipBuild)" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────────────────────────────────────────
# RUN DATABASE MIGRATIONS
# ─────────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "[5/6] Running database migrations..." -ForegroundColor Green

# Get container app name
$containerAppName = "$resourcePrefix-prediction"

# Execute migrations inside container
Write-Host "  Running migrations via container exec..." -ForegroundColor Gray

# Note: Container Apps doesn't support direct exec like Kubernetes
# Migrations are run on container startup via run_migrations.py
Write-Host "  ✓ Migrations will run automatically on container startup" -ForegroundColor Gray

# ─────────────────────────────────────────────────────────────────────────────────
# VERIFY DEPLOYMENT
# ─────────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "[6/6] Verifying deployment..." -ForegroundColor Green

# Wait for container to be ready
Write-Host "  Waiting for container to be ready (60s)..." -ForegroundColor Gray
Start-Sleep -Seconds 60

# Get container app URL
$containerAppUrl = az containerapp show `
    --name $containerAppName `
    --resource-group $ResourceGroup `
    --query "properties.configuration.ingress.fqdn" `
    --output tsv

if ($containerAppUrl) {
    Write-Host "  Testing health endpoint..." -ForegroundColor Gray
    try {
        $health = Invoke-RestMethod -Uri "https://$containerAppUrl/health" -TimeoutSec 30
        Write-Host "  ✓ Health check passed: $($health.status)" -ForegroundColor Green
    } catch {
        Write-Host "  ! Health check failed (container may still be starting)" -ForegroundColor Yellow
    }
}

# ─────────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DEPLOYMENT COMPLETE" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Resource Group:  $ResourceGroup" -ForegroundColor White
Write-Host "  Container App:   https://$containerAppUrl" -ForegroundColor White
Write-Host "  Health Endpoint: https://$containerAppUrl/health" -ForegroundColor White
Write-Host ""
Write-Host "  To run predictions:" -ForegroundColor Yellow
Write-Host "    curl https://$containerAppUrl/predict" -ForegroundColor Gray
Write-Host ""
Write-Host "  To view logs:" -ForegroundColor Yellow
Write-Host "    az containerapp logs show -n $containerAppName -g $ResourceGroup --follow" -ForegroundColor Gray
Write-Host ""

# Save deployment info
$deploymentInfo = @{
    Environment = $Environment
    ResourceGroup = $ResourceGroup
    ContainerAppUrl = "https://$containerAppUrl"
    AcrLoginServer = $acrLoginServer
    ImageTag = $ImageTag
    DeployedAt = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
}
$deploymentInfo | ConvertTo-Json | Out-File "$PSScriptRoot\deployment-info.json"
Write-Host "  Deployment info saved to: azure\deployment-info.json" -ForegroundColor Gray
Write-Host ""
