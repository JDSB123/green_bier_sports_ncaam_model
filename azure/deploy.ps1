# ═══════════════════════════════════════════════════════════════════════════════
# NCAAM v33.6.1 - Azure Deployment Script
# ═══════════════════════════════════════════════════════════════════════════════
# Usage:
#   .\deploy.ps1 -OddsApiKey "YOUR_KEY"              # Full deployment
#   .\deploy.ps1 -QuickDeploy                        # Fast code-only update (RECOMMENDED)
#   .\deploy.ps1 -SkipInfra -ParallelBuild           # Skip infra + parallel builds
#   .\deploy.ps1 -SkipInfra -SkipBuild               # Update container apps only
#
# Performance Flags:
#   -QuickDeploy    Fastest option for code updates (implies -SkipInfra -ParallelBuild)
#   -SkipInfra      Skip Azure resource provisioning (use after initial deploy)
#   -SkipBuild      Skip Docker build/push (only update container app config)
#   -ParallelBuild  Build all 4 Docker images concurrently
#   -NoCache        Force full Docker rebuild (slower, use for dependency changes)
#
# Other Options:
#   -OddsApiKey     The Odds API key (auto-fetched from existing app if omitted)
#   -TeamsWebhookUrl  Microsoft Teams webhook for notifications
#   -ImageTag       Container image tag (default: v33.6.1)
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('dev', 'staging', 'prod', 'stable')]
    [string]$Environment = 'stable',

    [Parameter(Mandatory=$false)]
    [string]$OddsApiKey,

    [Parameter(Mandatory=$false)]
    [string]$BasketballApiKey = '',

    [Parameter(Mandatory=$false)]
    [string]$TeamsWebhookUrl = '',

    [Parameter(Mandatory=$false)]
    [string]$Location = 'centralus',

    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = 'NCAAM-GBSV-MODEL-RG',

    [Parameter(Mandatory=$false)]
    [switch]$SkipInfra,

    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild,

    [Parameter(Mandatory=$false)]
    [switch]$NoCache,

    [Parameter(Mandatory=$false)]
    [switch]$ParallelBuild,

    [Parameter(Mandatory=$false)]
    [switch]$QuickDeploy,

    [Parameter(Mandatory=$false)]
    [string]$ImageTag = 'v33.6.1'
)

# ─────────────────────────────────────────────────────────────────────────────────
# QUICK DEPLOY MODE
# ─────────────────────────────────────────────────────────────────────────────────
# QuickDeploy automatically enables optimizations for fast code-only updates
if ($QuickDeploy) {
    $SkipInfra = $true
    $ParallelBuild = $true
    Write-Host ""
    Write-Host "  [QUICK DEPLOY MODE] Skipping infra, using parallel builds" -ForegroundColor Magenta
}

$ErrorActionPreference = 'Stop'

# ─────────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────────

$baseName = 'ncaam'
$webImageName = 'gbsv-web'
$ratingsImageName = "$baseName-ratings-sync"
$oddsImageName = "$baseName-odds-ingestion"
$resourcePrefix = "$baseName-$Environment"
$acrName = 'ncaamstablegbsvacr'

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  NCAAM v6.3 - Azure Deployment" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Environment:    $Environment" -ForegroundColor Yellow
Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor Yellow
Write-Host "  Location:       $Location" -ForegroundColor Yellow
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
                Write-Host "  [OK] Successfully retrieved Odds API Key from Azure!" -ForegroundColor Green
            } else {
                Write-Warning "  ! Could not retrieve key (secret 'odds-api-key' not found)."
            }
        } else {
            Write-Warning "  ! App '$existingAppName' not found in RG '$ResourceGroup'. Cannot fetch key."
        }
    } catch {
        Write-Warning "  ! Error fetching existing key: $_"
    }
    
    # If still empty, check if we can proceed
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
    Write-Host "  [OK] Azure CLI: $($azVersion.'azure-cli')" -ForegroundColor Gray
} catch {
    Write-Error "Azure CLI not found. Install from https://aka.ms/installazurecliwindows"
}

# Check Docker
try {
    docker version --format '{{.Server.Version}}' | Out-Null
    Write-Host "  [OK] Docker: Running" -ForegroundColor Gray
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
Write-Host "  [OK] Azure Account: $($account.name)" -ForegroundColor Gray

# ─────────────────────────────────────────────────────────────────────────────────
# GENERATE PASSWORDS
# ─────────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "[2/6] Generating secure passwords..." -ForegroundColor Green

# Generate secure passwords
$postgresPassword = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
$redisPassword = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})

Write-Host "  [OK] PostgreSQL password generated (32 chars)" -ForegroundColor Gray
Write-Host "  [OK] Redis password generated (32 chars)" -ForegroundColor Gray

# Optional: Load Basketball API key from repo secret file if not explicitly provided
if ([string]::IsNullOrWhiteSpace($BasketballApiKey)) {
    $basketballSecretPath = Join-Path $PSScriptRoot "..\secrets\basketball_api_key.txt"
    if (Test-Path $basketballSecretPath) {
        $BasketballApiKey = (Get-Content $basketballSecretPath -Raw).Trim()
        Write-Host "  [OK] Basketball API key loaded from secrets file" -ForegroundColor Gray
    }
}

# Optional: Load Teams webhook from repo secret file if not explicitly provided
if ([string]::IsNullOrWhiteSpace($TeamsWebhookUrl)) {
    $teamsSecretPath = Join-Path $PSScriptRoot "..\secrets\teams_webhook_url.txt"
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
        Write-Host "  [OK] Teams webhook configured (will enable run_today.py --teams)" -ForegroundColor Gray
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

    $deploymentOutput = az deployment group create `
        --resource-group $ResourceGroup `
        --template-file "$PSScriptRoot\main.bicep" `
        --parameters `
            environment=$Environment `
            location=$Location `
            baseName=$baseName `
            postgresPassword=$postgresPassword `
            oddsApiKey=$OddsApiKey `
            basketballApiKey=$BasketballApiKey `
            teamsWebhookUrl=$TeamsWebhookUrl `
            imageTag=$ImageTag `
            resourceNameSuffix='-gbsv' `
        --output json | ConvertFrom-Json

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Bicep deployment failed!"
    }

    $acrLoginServer = $deploymentOutput.properties.outputs.acrLoginServer.value
    $postgresHost = $deploymentOutput.properties.outputs.postgresHost.value
    $containerAppUrl = $deploymentOutput.properties.outputs.containerAppUrl.value

    Write-Host "  [OK] ACR: $acrLoginServer" -ForegroundColor Gray
    Write-Host "  [OK] PostgreSQL: $postgresHost" -ForegroundColor Gray
    Write-Host "  [OK] Container App URL: https://$containerAppUrl" -ForegroundColor Gray
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

    Push-Location "$PSScriptRoot\.."

    $images = @(
        @{ Name = "${acrLoginServer}/${baseName}-prediction:${ImageTag}"; Context = "."; Dockerfile = "services/prediction-service-python/Dockerfile" },
        @{ Name = "${acrLoginServer}/${webImageName}:${ImageTag}"; Context = "services/web-frontend"; Dockerfile = "services/web-frontend/Dockerfile" },
        @{ Name = "${acrLoginServer}/${ratingsImageName}:${ImageTag}"; Context = "services/ratings-sync-go"; Dockerfile = "services/ratings-sync-go/Dockerfile" },
        @{ Name = "${acrLoginServer}/${oddsImageName}:${ImageTag}"; Context = "services/odds-ingestion-rust"; Dockerfile = "services/odds-ingestion-rust/Dockerfile" }
    )

    # Determine cache flag
    $cacheFlag = if ($NoCache) { "--no-cache" } else { "" }
    if ($NoCache) {
        Write-Host "  [INFO] Building with --no-cache (full rebuild)" -ForegroundColor Yellow
    } else {
        Write-Host "  [INFO] Building with Docker cache (faster)" -ForegroundColor Gray
    }

    if ($ParallelBuild) {
        # ─────────────────────────────────────────────────────────────────────────
        # PARALLEL BUILD MODE - Build all images concurrently
        # ─────────────────────────────────────────────────────────────────────────
        Write-Host "  [PARALLEL] Starting concurrent builds for $($images.Count) images..." -ForegroundColor Cyan

        $buildJobs = @()
        $repoRoot = (Get-Location).Path

        foreach ($img in $images) {
            $imgName = $img.Name
            $imgContext = $img.Context
            $imgDockerfile = $img.Dockerfile
            $useNoCache = $NoCache

            $job = Start-Job -ScriptBlock {
                param($name, $context, $dockerfile, $noCache, $root)
                Set-Location $root
                $cacheArg = if ($noCache) { "--no-cache" } else { "" }
                if ($cacheArg) {
                    docker build $cacheArg -t $name -f $dockerfile $context 2>&1
                } else {
                    docker build -t $name -f $dockerfile $context 2>&1
                }
                return @{ ExitCode = $LASTEXITCODE; Image = $name }
            } -ArgumentList $imgName, $imgContext, $imgDockerfile, $useNoCache, $repoRoot

            $buildJobs += @{ Job = $job; Image = $imgName }
            Write-Host "    Started: $imgName" -ForegroundColor Gray
        }

        # Wait for all builds to complete
        Write-Host "  [PARALLEL] Waiting for builds to complete..." -ForegroundColor Cyan
        $failedBuilds = @()

        foreach ($buildJob in $buildJobs) {
            $result = Receive-Job -Job $buildJob.Job -Wait
            Remove-Job -Job $buildJob.Job

            # Check if build failed
            if ($result.ExitCode -ne 0) {
                $failedBuilds += $buildJob.Image
                Write-Host "    FAILED: $($buildJob.Image)" -ForegroundColor Red
            } else {
                Write-Host "    OK: $($buildJob.Image)" -ForegroundColor Green
            }
        }

        if ($failedBuilds.Count -gt 0) {
            Pop-Location
            Write-Error "Docker build failed for: $($failedBuilds -join ', ')"
        }

        # Push images (can also be parallelized but ACR handles sequential better)
        Write-Host "  [PARALLEL] Pushing images to ACR..." -ForegroundColor Cyan
        foreach ($img in $images) {
            Write-Host "    Pushing: $($img.Name)" -ForegroundColor Gray
            docker push $($img.Name)
            if ($LASTEXITCODE -ne 0) {
                Pop-Location
                Write-Error "Docker push failed for $($img.Name)!"
            }
        }
    } else {
        # ─────────────────────────────────────────────────────────────────────────
        # SEQUENTIAL BUILD MODE - Build images one at a time
        # ─────────────────────────────────────────────────────────────────────────
        foreach ($img in $images) {
            Write-Host "  Building image: $($img.Name)" -ForegroundColor Gray
            if ($NoCache) {
                docker build --no-cache -t $($img.Name) -f $($img.Dockerfile) $($img.Context)
            } else {
                docker build -t $($img.Name) -f $($img.Dockerfile) $($img.Context)
            }
            if ($LASTEXITCODE -ne 0) {
                Pop-Location
                Write-Error "Docker build failed for $($img.Name)!"
            }

            Write-Host "  Pushing image: $($img.Name)" -ForegroundColor Gray
            docker push $($img.Name)
            if ($LASTEXITCODE -ne 0) {
                Pop-Location
                Write-Error "Docker push failed for $($img.Name)!"
            }
        }
    }

    Pop-Location
    Write-Host "  [OK] Images pushed to ACR" -ForegroundColor Gray

    # Best-effort: update running Container Apps (useful with --SkipInfra)
    try {
        az containerapp update --name "${resourcePrefix}-prediction" --resource-group $ResourceGroup --image "${acrLoginServer}/${baseName}-prediction:${ImageTag}" --output none
    } catch { }

    try {
        az containerapp update --name "${resourcePrefix}-web" --resource-group $ResourceGroup --image "${acrLoginServer}/${webImageName}:${ImageTag}" --output none
    } catch { }

    try {
        az containerapp job update --name "${resourcePrefix}-ratings-sync" --resource-group $ResourceGroup --image "${acrLoginServer}/${ratingsImageName}:${ImageTag}" --output none
    } catch { }

    try {
        az containerapp job update --name "${resourcePrefix}-odds-ingestion" --resource-group $ResourceGroup --image "${acrLoginServer}/${oddsImageName}:${ImageTag}" --output none
    } catch { }
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
Write-Host "  [OK] Migrations will run automatically on container startup" -ForegroundColor Gray

# ─────────────────────────────────────────────────────────────────────────────────
# VERIFY DEPLOYMENT
# ─────────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "[6/6] Verifying deployment..." -ForegroundColor Green

# Get container app URL
$containerAppUrl = az containerapp show `
    --name $containerAppName `
    --resource-group $ResourceGroup `
    --query "properties.configuration.ingress.fqdn" `
    --output tsv

if ($containerAppUrl) {
    # Smart health check loop - exits early when healthy
    $maxAttempts = 12
    $attemptInterval = 10
    $healthy = $false

    Write-Host "  Waiting for container to be ready (polling every ${attemptInterval}s, max ${maxAttempts} attempts)..." -ForegroundColor Gray

    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "https://$containerAppUrl/health" -TimeoutSec 5
            Write-Host "  [OK] Health check passed on attempt $attempt : $($health.status)" -ForegroundColor Green
            $healthy = $true
            break
        } catch {
            if ($attempt -lt $maxAttempts) {
                Write-Host "    Attempt $attempt/$maxAttempts - not ready yet, waiting..." -ForegroundColor Gray
                Start-Sleep -Seconds $attemptInterval
            }
        }
    }

    if (-not $healthy) {
        Write-Host "  ! Health check did not pass after $maxAttempts attempts (container may still be starting)" -ForegroundColor Yellow
        Write-Host "    Check logs: az containerapp logs show -n $containerAppName -g $ResourceGroup --follow" -ForegroundColor Gray
    }
} else {
    Write-Host "  ! Could not retrieve container app URL" -ForegroundColor Yellow
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
