# ═══════════════════════════════════════════════════════════════════════════════
# NCAAM - Azure Deployment Script (version sourced from VERSION file)
# ═══════════════════════════════════════════════════════════════════════════════
# Usage:
#   .\deploy.ps1 -OddsApiKey "YOUR_KEY"              # Full deployment
#   .\deploy.ps1 -QuickDeploy                        # Fast code-only update (RECOMMENDED)
#   .\deploy.ps1 -SkipInfra -ParallelBuild           # Skip infra + parallel builds
#   .\deploy.ps1 -SkipInfra -SkipBuild               # Update container apps only
#   .\deploy.ps1 -ForceMigrations                    # Fix schema mismatches
#
# Performance Flags:
#   -QuickDeploy    Fastest option for code updates (implies -SkipInfra -ParallelBuild)
#   -SkipInfra      Skip Azure resource provisioning (use after initial deploy)
#   -SkipBuild      Skip Docker build/push (only update container app config)
#   -ParallelBuild  Build all 4 Docker images concurrently
#   -NoCache        Force full Docker rebuild (slower, use for dependency changes)
#
# Schema Management:
#   -ForceMigrations  Force apply missing database migrations (fixes schema issues)
#   -SkipHealthCheck  Skip schema validation during deployment
#
# Other Options:
#   -OddsApiKey       The Odds API key (auto-fetched from existing app if omitted)
#   -ImageTag         Container image tag (defaults to v<VERSION_FILE>)
#   -PruneAcrImages   Remove old image tags from ACR after successful deploy
#   -KeepAcrTags      How many tags to keep per repo (default: 1)
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
    [string]$ActionNetworkUsername = '',

    [Parameter(Mandatory=$false)]
    [SecureString]$ActionNetworkPasswordSecure,

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

    # Migration controls
    [Parameter(Mandatory=$false)]
    [switch]$ForceMigrations,

    [Parameter(Mandatory=$false)]
    [switch]$SkipHealthCheck,

    # Cleanup / retention controls (ACR/ACA)
    [Parameter(Mandatory=$false)]
    [switch]$PruneAcrImages,

    [Parameter(Mandatory=$false)]
    [ValidateRange(1, 25)]
    [int]$KeepAcrTags = 1,

    [Parameter(Mandatory=$false)]
    [string]$ImageTag,

    # Azure Storage connection string for pick history (external account: metricstrackersgbsv)
    [Parameter(Mandatory=$false)]
    [string]$StorageConnectionString,

    # Azure Storage connection string for canonical historical data (metricstrackersgbsv)
    [Parameter(Mandatory=$false)]
    [string]$CanonicalStorageConnectionString
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

# Default to keeping ACR clean: historical retention should live in Postgres (ROI/picks),
# not in old container image tags. Allow override via `-PruneAcrImages:$false`.
if (-not $PSBoundParameters.ContainsKey('PruneAcrImages')) {
    $PruneAcrImages = $true
}

$ErrorActionPreference = 'Stop'
$deploymentHealthy = $false

# Resolve version tag if not provided
if (-not $ImageTag -or [string]::IsNullOrWhiteSpace($ImageTag)) {
    # Join-Path supports only two positional args (Path, ChildPath). Use a single child path.
    $versionFile = Join-Path $PSScriptRoot "..\VERSION"
    if (Test-Path $versionFile) {
        $rawVersion = (Get-Content -Path $versionFile -TotalCount 1).Trim()
        if (-not [string]::IsNullOrWhiteSpace($rawVersion)) {
            if ($rawVersion.StartsWith('v')) {
                $ImageTag = $rawVersion
            } else {
                $ImageTag = "v$rawVersion"
            }
        }
    }

    if (-not $ImageTag) {
        $ImageTag = 'v0.0.0'
    }
}

# ─────────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────────

$baseName = 'ncaam'
$webImageName = 'gbsv-web'
# REMOVED (v33.11.0): Standalone ratings-sync and odds-ingestion images
# These binaries are now built INTO the prediction-service via multi-stage Docker build.
# The prediction service embeds Go (ratings-sync) and Rust (odds-ingestion) binaries.
$resourcePrefix = "$baseName-$Environment"
# Keep naming consistent with `azure/main.bicep`:
# acrName = replace('${resourcePrefix}${replace(resourceNameSuffix, '-', '')}acr', '-', '')
$acrName = ("{0}gbsvacr" -f $resourcePrefix).Replace("-", "")

function Invoke-AcrTagCleanup {
    param(
        [Parameter(Mandatory=$true)][string]$RegistryName,
        [Parameter(Mandatory=$true)][string[]]$Repositories,
        [Parameter(Mandatory=$true)][string]$KeepTag,
        [Parameter(Mandatory=$true)][int]$KeepCount
    )

    Write-Host ""
    Write-Host "[CLEANUP] ACR tag cleanup (keep $KeepCount tag(s) incl. $KeepTag)..." -ForegroundColor Cyan

    foreach ($repo in $Repositories) {
        Write-Host "  Repo: $repo" -ForegroundColor Gray

        # Get tags newest-first
        $raw = az acr repository show-tags --name $RegistryName --repository $repo --orderby time_desc -o tsv 2>$null
        $tags = @()
        if ($raw) {
            $tags = ($raw -split "`r?`n") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
        }

        if (-not $tags -or $tags.Count -eq 0) {
            Write-Host "    (no tags found)" -ForegroundColor DarkGray
            continue
        }

        if (-not ($tags -contains $KeepTag)) {
            Write-Host "    [SKIP] KeepTag '$KeepTag' not present; refusing to delete." -ForegroundColor Yellow
            continue
        }

        # Always keep the deployment tag, plus N-1 most recent others.
        $keep = New-Object 'System.Collections.Generic.HashSet[string]'
        [void]$keep.Add($KeepTag)
        foreach ($t in $tags) {
            if ($keep.Count -ge $KeepCount) { break }
            if ($t -ne $KeepTag) { [void]$keep.Add($t) }
        }

        $toDelete = @()
        foreach ($t in $tags) {
            if (-not $keep.Contains($t)) { $toDelete += $t }
        }

        if (-not $toDelete -or $toDelete.Count -eq 0) {
            Write-Host "    OK (nothing to delete)" -ForegroundColor Green
            continue
        }

        foreach ($t in $toDelete) {
            Write-Host "    Untagging: ${repo}:$t" -ForegroundColor DarkGray
            try {
                # Use `untag` (tag-only) to avoid deleting the underlying manifest that may be shared
                # with the deployment tag (e.g., if `latest` points at the same digest as `vX.Y.Z`).
                az acr repository untag --name $RegistryName --image "${repo}:$t" --output none | Out-Null
            } catch {
                Write-Warning "    Failed to untag ${repo}:$t : $_"
            }
        }
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  NCAAM $ImageTag - Azure Deployment" -ForegroundColor Cyan
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

# Storage account handling (v34.1.0)
# If StorageConnectionString is not provided, Bicep will create an internal storage account
# If provided, uses external storage account (for migration/override scenarios)
if ([string]::IsNullOrEmpty($StorageConnectionString)) {
    Write-Host "  [INFO] Storage connection string not provided - will create internal storage account in NCAAM-GBSV-MODEL-RG" -ForegroundColor Cyan
    Write-Host "  [INFO] To use external storage instead, pass -StorageConnectionString parameter" -ForegroundColor Gray
} else {
    Write-Host "  [INFO] Using provided storage connection string (external storage account)" -ForegroundColor Cyan
}

if ([string]::IsNullOrEmpty($CanonicalStorageConnectionString)) {
    Write-Host "  [INFO] Canonical storage connection string not provided - will reuse storage connection string if available" -ForegroundColor Gray
} else {
    Write-Host "  [INFO] Using provided canonical storage connection string" -ForegroundColor Cyan
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

# Generate secure password for PostgreSQL (Redis password is auto-generated by Azure)
$postgresPassword = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})

Write-Host "  [OK] PostgreSQL password generated (32 chars)" -ForegroundColor Gray
Write-Host "  [OK] Redis password will be auto-generated by Azure" -ForegroundColor Gray

# Optional: Load Basketball API key from repo secret file if not explicitly provided
if ([string]::IsNullOrWhiteSpace($BasketballApiKey)) {
    $basketballSecretPath = Join-Path $PSScriptRoot "..\secrets\basketball_api_key.txt"
    if (Test-Path $basketballSecretPath) {
        $rawBasketballKey = Get-Content $basketballSecretPath -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($rawBasketballKey)) {
            $BasketballApiKey = $rawBasketballKey.Trim()
            Write-Host "  [OK] Basketball API key loaded from secrets file" -ForegroundColor Gray
        }
    }
}

# DEPRECATED: Incoming webhook (API → Teams) removed
# Teams integration now uses outgoing webhook (Teams → API) via /teams-webhook endpoint
# No longer loading or configuring TEAMS_WEBHOOK_URL

# Optional: Load Action Network credentials from repo secret files
# Convert SecureString to plain text for Bicep deployment (Bicep handles secure params)
$ActionNetworkPassword = ''
if ($ActionNetworkPasswordSecure) {
    $ActionNetworkPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($ActionNetworkPasswordSecure)
    )
}

if ([string]::IsNullOrWhiteSpace($ActionNetworkUsername)) {
    $anUserPath = Join-Path $PSScriptRoot "..\secrets\action_network_username.txt"
    if (Test-Path $anUserPath -PathType Leaf) {
        $rawAnUser = Get-Content $anUserPath -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($rawAnUser)) {
            $ActionNetworkUsername = $rawAnUser.Trim()
        }
    }
}

if ([string]::IsNullOrWhiteSpace($ActionNetworkPassword)) {
    $anPassPath = Join-Path $PSScriptRoot "..\secrets\action_network_password.txt"
    if (Test-Path $anPassPath -PathType Leaf) {
        $rawAnPass = Get-Content $anPassPath -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($rawAnPass)) {
            $ActionNetworkPassword = $rawAnPass.Trim()
        }
    }
}

if ($ActionNetworkUsername -and $ActionNetworkPassword) {
    Write-Host "  [OK] Action Network credentials loaded (premium betting splits enabled)" -ForegroundColor Gray
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
            actionNetworkUsername=$ActionNetworkUsername `
            actionNetworkPassword=$ActionNetworkPassword `
            imageTag=$ImageTag `
            resourceNameSuffix='-gbsv' `
            storageConnectionString=$StorageConnectionString `
            canonicalStorageConnectionString=$CanonicalStorageConnectionString `
        --output json | ConvertFrom-Json

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Bicep deployment failed!"
    }

    $acrLoginServer = $deploymentOutput.properties.outputs.acrLoginServer.value
    $postgresHost = $deploymentOutput.properties.outputs.postgresHost.value
    $containerAppUrl = $deploymentOutput.properties.outputs.containerAppUrl.value
    $storageAccountName = $deploymentOutput.properties.outputs.storageAccountName.value
    $usingInternalStorage = $deploymentOutput.properties.outputs.usingInternalStorage.value

    Write-Host "  [OK] ACR: $acrLoginServer" -ForegroundColor Gray
    Write-Host "  [OK] PostgreSQL: $postgresHost" -ForegroundColor Gray
    Write-Host "  [OK] Container App URL: https://$containerAppUrl" -ForegroundColor Gray
    if ($usingInternalStorage) {
        Write-Host "  [OK] Storage Account: $storageAccountName (internal, created in NCAAM-GBSV-MODEL-RG)" -ForegroundColor Gray
    } else {
        Write-Host "  [OK] Storage Account: $storageAccountName (external, connection string provided)" -ForegroundColor Gray
    }
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

    # Build metadata for version-control traceability (baked into images)
    $gitSha = "unknown"
    try {
        $gitSha = (git rev-parse HEAD).Trim()
    } catch { }
    $buildDate = (Get-Date).ToUniversalTime().ToString("o")

    # v33.11.0: Reduced to 2 images (prediction + web)
    # Go (ratings-sync) and Rust (odds-ingestion) binaries are built INTO prediction-service
    # via multi-stage Docker build - no separate images needed.
    $images = @(
        @{ Name = "${acrLoginServer}/${baseName}-prediction:${ImageTag}"; Context = "."; Dockerfile = "services/prediction-service-python/Dockerfile" },
        @{ Name = "${acrLoginServer}/${webImageName}:${ImageTag}"; Context = "services/web-frontend"; Dockerfile = "services/web-frontend/Dockerfile" }
    )

    # Determine cache behavior
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
                param($name, $context, $dockerfile, $noCache, $root, $gitSha, $buildDate)
                Set-Location $root
                # IMPORTANT: capture build output so the job returns a single object.
                # If we let `docker build` write to the pipeline, Receive-Job returns
                # many strings + the final object, and `$result.ExitCode` becomes
                # an array containing `$null`, which incorrectly marks builds failed.
                if ($noCache) {
                    $output = & docker build --no-cache --build-arg "GIT_SHA=$gitSha" --build-arg "BUILD_DATE=$buildDate" -t $name -f $dockerfile $context 2>&1
                } else {
                    $output = & docker build --build-arg "GIT_SHA=$gitSha" --build-arg "BUILD_DATE=$buildDate" -t $name -f $dockerfile $context 2>&1
                }

                $exit = $LASTEXITCODE
                return [pscustomobject]@{
                    ExitCode = $exit
                    Image    = $name
                    Output   = $output
                }
            } -ArgumentList $imgName, $imgContext, $imgDockerfile, $useNoCache, $repoRoot, $gitSha, $buildDate

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
                if ($result.Output) {
                    Write-Host "    ---- docker build output (tail) ----" -ForegroundColor DarkGray
                    $tail = $result.Output | Select-Object -Last 120
                    Write-Host ($tail -join "`n") -ForegroundColor DarkGray
                    Write-Host "    ------------------------------------" -ForegroundColor DarkGray
                }
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
                docker build --no-cache --build-arg "GIT_SHA=$gitSha" --build-arg "BUILD_DATE=$buildDate" -t $($img.Name) -f $($img.Dockerfile) $($img.Context)
            } else {
                docker build --build-arg "GIT_SHA=$gitSha" --build-arg "BUILD_DATE=$buildDate" -t $($img.Name) -f $($img.Dockerfile) $($img.Context)
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

    # REMOVED (v33.11.0): Standalone ratings-sync and odds-ingestion jobs
    # These are now embedded in the prediction-service container
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

if ($ForceMigrations) {
    Write-Host "  [FORCE] Forcing application of missing migrations..." -ForegroundColor Yellow

    # Force apply migrations by restarting with FORCE_MISSING_MIGRATIONS env var
    Write-Host "  Setting FORCE_MISSING_MIGRATIONS=true on container..." -ForegroundColor Gray

    # Update container environment to force migrations
    az containerapp update `
        --name $containerAppName `
        --resource-group $ResourceGroup `
        --set-env-vars FORCE_MISSING_MIGRATIONS=true `
        --output none
    Write-Host "  Restart not required; env update triggers a new revision" -ForegroundColor Gray

    # Wait for migration to complete
    Write-Host "  Waiting for migrations to complete..." -ForegroundColor Gray
    Start-Sleep -Seconds 30

    # Remove the force flag after migration
    az containerapp update `
        --name $containerAppName `
        --resource-group $ResourceGroup `
        --remove-env-vars FORCE_MISSING_MIGRATIONS `
        --output none

    Write-Host "  [OK] Forced migrations applied" -ForegroundColor Green
} else {
    Write-Host "  Running migrations via container startup..." -ForegroundColor Gray
    Write-Host "  [OK] Migrations will run automatically on container startup" -ForegroundColor Gray
}

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
            $status = $health.status

            # Check for schema issues
            if ($status -eq "degraded" -and $health.database -and $health.database.missing_migrations) {
                Write-Host "    Attempt $attempt/$maxAttempts - schema issues detected: $($health.database.missing_migrations -join ', ')" -ForegroundColor Yellow
                if (-not $SkipHealthCheck) {
                    Write-Host "    [WARN] Schema validation failed. Use -ForceMigrations to fix." -ForegroundColor Yellow
                }
            } elseif ($status -eq "ok") {
                Write-Host "  [OK] Health check passed on attempt $attempt : $status" -ForegroundColor Green
                $healthy = $true
                break
            } else {
                Write-Host "    Attempt $attempt/$maxAttempts - status: $status, waiting..." -ForegroundColor Gray
            }
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
    } else {
        $deploymentHealthy = $true
    }
} else {
    Write-Host "  ! Could not retrieve container app URL" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────────────────────────────────────────
# OPTIONAL: ACR CLEANUP (KEEP ONLY RECENT TAGS)
# ─────────────────────────────────────────────────────────────────────────────────

if ($PruneAcrImages) {
    if (-not $deploymentHealthy) {
        Write-Host ""
        Write-Host "[CLEANUP] Skipping ACR cleanup because deployment health is not confirmed." -ForegroundColor Yellow
    } else {
        # v33.11.0: Only 2 repos now (prediction + web)
        $repos = @("${baseName}-prediction", $webImageName)
        Invoke-AcrTagCleanup -RegistryName $acrName -Repositories $repos -KeepTag $ImageTag -KeepCount $KeepAcrTags
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
