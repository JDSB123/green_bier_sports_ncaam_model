# ═══════════════════════════════════════════════════════════════════════════════
# Cleanup Duplicate Azure Resources
# ═══════════════════════════════════════════════════════════════════════════════
# This script helps clean up the duplicate 'green-bier-ncaam' resource group
# 
# WARNING: This will DELETE all resources in the 'green-bier-ncaam' resource group!
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [Parameter(Mandatory=$false)]
    [switch]$DryRun = $false
)

$ErrorActionPreference = 'Stop'

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Azure Resource Cleanup - Remove Duplicate Resources" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$legacyResourceGroup = "green-bier-ncaam"
$activeResourceGroup = "ncaam-prod-rg"

# Check if logged in
$account = az account show --output json 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "❌ Not logged in to Azure. Running 'az login'..." -ForegroundColor Red
    az login
    $account = az account show --output json | ConvertFrom-Json
}
Write-Host "✅ Azure Account: $($account.name)" -ForegroundColor Green
Write-Host ""

# Check if legacy resource group exists
$rgExists = az group exists --name $legacyResourceGroup --output json | ConvertFrom-Json
if ($rgExists -eq $false) {
    Write-Host "✅ Resource group '$legacyResourceGroup' does not exist. Nothing to clean up." -ForegroundColor Green
    exit 0
}

# List resources in legacy group
Write-Host "📋 Resources in '$legacyResourceGroup':" -ForegroundColor Yellow
$resources = az resource list --resource-group $legacyResourceGroup --output json | ConvertFrom-Json

if ($resources.Count -eq 0) {
    Write-Host "✅ Resource group is empty. Safe to delete." -ForegroundColor Green
} else {
    Write-Host ""
    foreach ($resource in $resources) {
        Write-Host "   • $($resource.name) ($($resource.type))" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "⚠️  WARNING: These resources will be DELETED!" -ForegroundColor Red
}

# Check if active resource group exists
$activeExists = az group exists --name $activeResourceGroup --output json | ConvertFrom-Json
if ($activeExists -eq $false) {
    Write-Host ""
    Write-Host "⚠️  WARNING: Active resource group '$activeResourceGroup' does not exist!" -ForegroundColor Red
    Write-Host "   Are you sure you want to delete '$legacyResourceGroup'?" -ForegroundColor Yellow
    $confirm = Read-Host "Type 'yes' to continue"
    if ($confirm -ne "yes") {
        Write-Host "❌ Cancelled." -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host ""
    Write-Host "✅ Active resource group '$activeResourceGroup' exists." -ForegroundColor Green
}

# Dry run mode
if ($DryRun) {
    Write-Host ""
    Write-Host "🔍 DRY RUN MODE - No changes will be made" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Would delete resource group: $legacyResourceGroup" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To actually delete, run without -DryRun flag:" -ForegroundColor Cyan
    Write-Host "  .\scripts\cleanup-duplicate-azure-resources.ps1" -ForegroundColor White
    exit 0
}

# Confirm deletion
Write-Host ""
Write-Host "⚠️  FINAL CONFIRMATION" -ForegroundColor Red
Write-Host "   This will PERMANENTLY DELETE all resources in '$legacyResourceGroup'" -ForegroundColor Red
Write-Host ""
$confirm = Read-Host "Type the resource group name to confirm deletion"

if ($confirm -ne $legacyResourceGroup) {
    Write-Host "❌ Confirmation failed. Resource group name does not match." -ForegroundColor Red
    Write-Host "   Expected: $legacyResourceGroup" -ForegroundColor Yellow
    Write-Host "   Got:      $confirm" -ForegroundColor Yellow
    exit 1
}

# Delete resource group
Write-Host ""
Write-Host "🗑️  Deleting resource group '$legacyResourceGroup'..." -ForegroundColor Yellow
az group delete --name $legacyResourceGroup --yes --no-wait

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Resource group deletion initiated!" -ForegroundColor Green
    Write-Host "   (Deletion happens asynchronously and may take a few minutes)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "📋 To check deletion status:" -ForegroundColor Cyan
    Write-Host "   az group show --name $legacyResourceGroup" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "❌ Failed to delete resource group!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Cleanup Complete" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

