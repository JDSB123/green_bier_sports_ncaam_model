# ═══════════════════════════════════════════════════════════════════════════════
# Setup Branch Protection for Main Branch
# ═══════════════════════════════════════════════════════════════════════════════
# This script sets up branch protection rules for the main branch using GitHub CLI
# 
# Prerequisites:
#   1. GitHub CLI (gh) installed: https://cli.github.com/
#   2. Authenticated: gh auth login
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [string]$Repository = "JDSB123/green_bier_sports_ncaam_model",
    [string]$Branch = "main"
)

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Setting Up Branch Protection for: $Branch" -ForegroundColor Cyan
Write-Host "  Repository: $Repository" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check if gh CLI is installed
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "❌ GitHub CLI (gh) is not installed." -ForegroundColor Red
    Write-Host ""
    Write-Host "Install from: https://cli.github.com/" -ForegroundColor Yellow
    Write-Host "Then run: gh auth login" -ForegroundColor Yellow
    exit 1
}

# Check if authenticated
$authStatus = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Not authenticated with GitHub CLI." -ForegroundColor Red
    Write-Host ""
    Write-Host "Run: gh auth login" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ GitHub CLI is installed and authenticated" -ForegroundColor Green
Write-Host ""

# Check current protection status
Write-Host "Checking current branch protection status..." -ForegroundColor Gray
$currentProtection = gh api "repos/$Repository/branches/$Branch/protection" 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "⚠️  Branch protection already exists!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Current protection rules:" -ForegroundColor Cyan
    $currentProtection | ConvertFrom-Json | ConvertTo-Json -Depth 10
    Write-Host ""
    $overwrite = Read-Host "Do you want to update it? (y/N)"
    if ($overwrite -ne "y" -and $overwrite -ne "Y") {
        Write-Host "Skipping..." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host ""
Write-Host "Setting up branch protection rules..." -ForegroundColor Cyan

# Create protection configuration
$protectionConfig = @{
    required_status_checks = $null
    enforce_admins = $true
    required_pull_request_reviews = @{
        required_approving_review_count = 1
        dismiss_stale_reviews = $true
        require_code_owner_reviews = $false
    }
    restrictions = $null
    required_linear_history = $false
    allow_force_pushes = $false
    allow_deletions = $false
    block_creations = $false
    required_conversation_resolution = $true
    lock_branch = $false
    allow_fork_syncing = $false
} | ConvertTo-Json -Depth 10

Write-Host ""
Write-Host "Protection rules to apply:" -ForegroundColor Cyan
Write-Host "  ✅ Require pull request reviews before merging" -ForegroundColor Green
Write-Host "  ✅ Require 1 approval" -ForegroundColor Green
Write-Host "  ✅ Dismiss stale reviews when new commits are pushed" -ForegroundColor Green
Write-Host "  ✅ Require conversation resolution before merging" -ForegroundColor Green
Write-Host "  ✅ Include administrators" -ForegroundColor Green
Write-Host "  ✅ Do not allow force pushes" -ForegroundColor Green
Write-Host "  ✅ Do not allow deletions" -ForegroundColor Green
Write-Host ""

$confirm = Read-Host "Apply these rules? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit 0
}

# Apply protection
Write-Host ""
Write-Host "Applying branch protection rules..." -ForegroundColor Gray

$protectionConfig | gh api "repos/$Repository/branches/$Branch/protection" --method PUT --input -
$result = $LASTEXITCODE

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Branch protection rules applied successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Verifying protection..." -ForegroundColor Gray
    $verification = gh api "repos/$Repository/branches/$Branch/protection" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Protection verified!" -ForegroundColor Green
    }
} else {
    Write-Host ""
    Write-Host "❌ Failed to apply branch protection rules" -ForegroundColor Red
    Write-Host "Error: $result" -ForegroundColor Red
    Write-Host ""
    Write-Host "You may need to set this up manually:" -ForegroundColor Yellow
    Write-Host "  https://github.com/$Repository/settings/branches" -ForegroundColor Cyan
    exit 1
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Branch Protection Setup Complete!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "The main branch is now protected. All changes must go through PRs." -ForegroundColor Green
Write-Host ""

