# ═══════════════════════════════════════════════════════════════════════════════
# Configure NCAAM Container Apps to use Existing Azure PostgreSQL Database
# ═══════════════════════════════════════════════════════════════════════════════
# Usage:
#   .\configure-existing-db.ps1 -DbHost "ncaam-stable-gbsv-postgres.postgres.database.azure.com" `
#                                -DbUser "ncaam" `
#                                -DbPassword "<password>" `
#                                -DbName "ncaam"
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [Parameter(Mandatory=$true)]
    [string]$DbHost,

    [Parameter(Mandatory=$true)]
    [string]$DbUser,

    [Parameter(Mandatory=$true)]
    [string]$DbPassword,

    [Parameter(Mandatory=$false)]
    [string]$DbName = "ncaam",

    [Parameter(Mandatory=$false)]
    [string]$DbPort = "5432",

    [Parameter(Mandatory=$false)]
    [ValidateSet('dev', 'staging', 'prod', 'stable')]
    [string]$Environment = 'stable',

    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = 'NCAAM-GBSV-MODEL-RG'
)

$ErrorActionPreference = 'Stop'

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Configure Container Apps to use Existing PostgreSQL Database" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Database Host: $DbHost" -ForegroundColor Yellow
Write-Host "  Database User: $DbUser" -ForegroundColor Yellow
Write-Host "  Database Name: $DbName" -ForegroundColor Yellow
Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor Yellow
Write-Host "  Environment: $Environment" -ForegroundColor Yellow
Write-Host ""

# Build DATABASE_URL with SSL mode
$databaseUrl = "postgresql://${DbUser}:${DbPassword}@${DbHost}:${DbPort}/${DbName}?sslmode=require"

# Container App names
$resourcePrefix = "ncaam-$Environment"
$containerApps = @(
    "$resourcePrefix-prediction",
    "$resourcePrefix-ratings-sync",
    "$resourcePrefix-odds-ingestion"
)

Write-Host "[1/3] Setting database password secret..." -ForegroundColor Green

# Set the database password as a secret in each container app
foreach ($appName in $containerApps) {
    Write-Host "  Updating secret in: $appName" -ForegroundColor Gray
    
    try {
        # Check if secret already exists
        $existingSecret = az containerapp secret list `
            --name $appName `
            --resource-group $ResourceGroup `
            --query "[?name=='db-password'].name" `
            --output tsv 2>$null

        if ($existingSecret) {
            # Remove existing secret
            az containerapp secret remove `
                --name $appName `
                --resource-group $ResourceGroup `
                --secret-names "db-password" `
                --output none 2>$null
        }

        # Add new secret
        az containerapp secret set `
            --name $appName `
            --resource-group $ResourceGroup `
            --secrets "db-password=$DbPassword" `
            --output none

        Write-Host "    [OK] Secret updated" -ForegroundColor Green
    } catch {
        Write-Warning "    ! Failed to update secret in $appName`: $_"
    }
}

Write-Host ""
Write-Host "[2/3] Updating environment variables..." -ForegroundColor Green

# Update environment variables for each container app
# Note: --set-env-vars merges/updates existing vars, so we only need to set the DB-related ones
foreach ($appName in $containerApps) {
    Write-Host "  Updating: $appName" -ForegroundColor Gray

    try {
        # Update database-related environment variables
        # The --set-env-vars flag will merge these with existing env vars
        az containerapp update `
            --name $appName `
            --resource-group $ResourceGroup `
            --set-env-vars "DB_HOST=$DbHost" "DB_USER=$DbUser" "DB_NAME=$DbName" "DB_PORT=$DbPort" "DATABASE_URL=$databaseUrl" `
            --output none

        if ($LASTEXITCODE -eq 0) {
            Write-Host "    [OK] Environment variables updated" -ForegroundColor Green
        } else {
            Write-Error "    Failed to update environment variables (exit code: $LASTEXITCODE)"
        }
    } catch {
        Write-Error "    Failed to update $appName`: $_"
    }
}

Write-Host ""
Write-Host "[3/3] Verifying configuration..." -ForegroundColor Green

# Verify the configuration
foreach ($appName in $containerApps) {
    Write-Host "  Verifying: $appName" -ForegroundColor Gray
    
    try {
        $dbHost = az containerapp show `
            --name $appName `
            --resource-group $ResourceGroup `
            --query "properties.template.containers[0].env[?name=='DB_HOST'].value" `
            --output tsv
        
        if ($dbHost -eq $DbHost) {
            Write-Host "    [OK] DB_HOST correctly set to: $dbHost" -ForegroundColor Green
        } else {
            Write-Warning "    ! DB_HOST mismatch. Expected: $DbHost, Got: $dbHost"
        }
    } catch {
        Write-Warning "    ! Could not verify $appName`: $_"
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Configuration Complete" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  The container apps will restart automatically with the new database configuration." -ForegroundColor White
Write-Host ""
Write-Host "  To verify the connection, check logs:" -ForegroundColor Yellow
Write-Host "    az containerapp logs show -n $resourcePrefix-prediction -g $ResourceGroup --follow" -ForegroundColor Gray
Write-Host ""
Write-Host "  To check health:" -ForegroundColor Yellow
Write-Host "    curl https://$(az containerapp show -n $resourcePrefix-prediction -g $ResourceGroup --query 'properties.configuration.ingress.fqdn' -o tsv)/health" -ForegroundColor Gray
Write-Host ""

