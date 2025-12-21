# ═══════════════════════════════════════════════════════════════════════════════
# Organize NCAAM Resources in Enterprise Resource Group
# ═══════════════════════════════════════════════════════════════════════════════
# This script ensures all NCAAM resources in greenbier-enterprise-rg are:
# 1. Properly tagged with Model=ncaam
# 2. Named consistently with ncaam- prefix
# 3. Organized for easy filtering
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [Parameter(Mandatory=$false)]
    [switch]$DryRun = $false
)

$ErrorActionPreference = 'Stop'

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Organize NCAAM Resources in Enterprise Resource Group" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$resourceGroup = "greenbier-enterprise-rg"

# Check if resource group exists
$rgExists = az group exists --name $resourceGroup --output json | ConvertFrom-Json
if ($rgExists -eq $false) {
    Write-Host "❌ Resource group '$resourceGroup' does not exist!" -ForegroundColor Red
    exit 1
}

Write-Host "📋 Finding all NCAAM-related resources in $resourceGroup..." -ForegroundColor Yellow
Write-Host ""

# Find all resources that might be NCAAM-related
$allResources = az resource list --resource-group $resourceGroup --output json | ConvertFrom-Json
$ncaamResources = @()

foreach ($resource in $allResources) {
    $name = $resource.name
    $lowerName = $name.ToLower()
    
    # Check if resource is NCAAM-related
    if ($lowerName -like "*ncaam*" -or 
        ($resource.tags -and $resource.tags.Model -eq "ncaam")) {
        $ncaamResources += $resource
    }
}

Write-Host "Found $($ncaamResources.Count) NCAAM-related resources:" -ForegroundColor Cyan
Write-Host ""

$resourcesToTag = @()
foreach ($resource in $ncaamResources) {
    $tags = $resource.tags
    
    # Check if already properly tagged
    $needsTagging = $false
    if (-not $tags) {
        $needsTagging = $true
    } elseif (-not $tags.Model -or $tags.Model -ne "ncaam") {
        $needsTagging = $true
    }
    
    $status = if ($needsTagging) { "⚠️  Needs tagging" } else { "✅ Tagged" }
    Write-Host "   $status - $($resource.name) ($($resource.type))" -ForegroundColor $(if ($needsTagging) { "Yellow" } else { "Green" })
    
    if ($needsTagging) {
        $resourcesToTag += $resource
    }
}

Write-Host ""

if ($resourcesToTag.Count -eq 0) {
    Write-Host "✅ All NCAAM resources are already properly tagged!" -ForegroundColor Green
    exit 0
}

if ($DryRun) {
    Write-Host "🔍 DRY RUN MODE - No changes will be made" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Would tag $($resourcesToTag.Count) resources with:" -ForegroundColor Yellow
    Write-Host "   Model=ncaam" -ForegroundColor Gray
    Write-Host "   Environment=prod" -ForegroundColor Gray
    Write-Host "   ManagedBy=Bicep" -ForegroundColor Gray
    Write-Host "   Application=NCAAM-Prediction-Model" -ForegroundColor Gray
    Write-Host ""
    Write-Host "To apply tags, run without -DryRun:" -ForegroundColor Cyan
    Write-Host "  .\scripts\organize-ncaam-resources.ps1" -ForegroundColor White
    exit 0
}

# Tag resources
Write-Host "🏷️  Tagging $($resourcesToTag.Count) resources..." -ForegroundColor Yellow
Write-Host ""

$successCount = 0
$failCount = 0

foreach ($resource in $resourcesToTag) {
    try {
        # Determine environment from resource name
        $environment = "prod"
        if ($resource.name -like "*dev*" -or $resource.name -like "*Dev*") {
            $environment = "dev"
        } elseif ($resource.name -like "*stag*" -or $resource.name -like "*Stag*") {
            $environment = "staging"
        }
        
        Write-Host "   Tagging: $($resource.name) (Environment: $environment)" -ForegroundColor Gray
        
        az resource tag `
            --tags Model=ncaam Environment=$environment ManagedBy=Bicep Application=NCAAM-Prediction-Model `
            --ids $resource.id `
            --output none
        
        if ($LASTEXITCODE -eq 0) {
            $successCount++
        } else {
            $failCount++
            Write-Host "      ⚠️  Failed to tag" -ForegroundColor Yellow
        }
    } catch {
        $failCount++
        Write-Host "      ❌ Error: $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Organization Complete" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "✅ Successfully tagged: $successCount resources" -ForegroundColor Green
if ($failCount -gt 0) {
    Write-Host "⚠️  Failed to tag: $failCount resources" -ForegroundColor Yellow
}
Write-Host ""

# Show summary
Write-Host "📊 NCAAM Resources in Enterprise RG:" -ForegroundColor Cyan
az resource list --resource-group $resourceGroup `
    --query "[?tags.Model == 'ncaam'].{Name:name, Type:type, Environment:tags.Environment}" `
    --output table

Write-Host ""
Write-Host "💡 To filter NCAAM resources in Azure Portal:" -ForegroundColor Yellow
Write-Host "   Use filter: tags.Model = 'ncaam'" -ForegroundColor Gray
Write-Host ""

