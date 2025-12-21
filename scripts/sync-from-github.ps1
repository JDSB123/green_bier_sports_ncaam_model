# ═══════════════════════════════════════════════════════════════════════════════
# Sync from GitHub - Ensure Local Matches Remote
# ═══════════════════════════════════════════════════════════════════════════════
# This script ensures your local repository matches GitHub (single source of truth)
# 
# Usage: .\scripts\sync-from-github.ps1
# ═══════════════════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Syncing Local Repository with GitHub (Single Source of Truth)" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check if we're in a git repository
if (-not (Test-Path .git)) {
    Write-Host "❌ Not in a git repository!" -ForegroundColor Red
    exit 1
}

# Get current branch
$currentBranch = git rev-parse --abbrev-ref HEAD
Write-Host "Current branch: $currentBranch" -ForegroundColor Gray
Write-Host ""

# Check for uncommitted changes
Write-Host "Checking for uncommitted changes..." -ForegroundColor Gray
$status = git status --porcelain
if ($status) {
    Write-Host "⚠️  You have uncommitted changes:" -ForegroundColor Yellow
    Write-Host $status -ForegroundColor Yellow
    Write-Host ""
    $response = Read-Host "Continue anyway? (y/N)"
    if ($response -ne "y" -and $response -ne "Y") {
        Write-Host "Cancelled. Commit or stash your changes first." -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host "✅ Working tree is clean" -ForegroundColor Green
}
Write-Host ""

# Fetch latest from remote
Write-Host "Fetching latest from GitHub..." -ForegroundColor Gray
git fetch origin
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to fetch from GitHub" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Fetched successfully" -ForegroundColor Green
Write-Host ""

# Check if we're on main
if ($currentBranch -eq "main") {
    Write-Host "On main branch. Pulling latest changes..." -ForegroundColor Gray
    git pull origin main
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to pull from GitHub" -ForegroundColor Red
        Write-Host "You may have conflicts. Resolve them manually." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "✅ Main branch is up to date" -ForegroundColor Green
} else {
    Write-Host "On feature branch: $currentBranch" -ForegroundColor Gray
    Write-Host ""
    
    # Check if branch exists on remote
    $remoteBranch = git ls-remote --heads origin $currentBranch
    if ($remoteBranch) {
        Write-Host "Branch exists on remote. Pulling..." -ForegroundColor Gray
        git pull origin $currentBranch
        if ($LASTEXITCODE -ne 0) {
            Write-Host "⚠️  Pull had conflicts or issues" -ForegroundColor Yellow
        } else {
            Write-Host "✅ Feature branch synced" -ForegroundColor Green
        }
    } else {
        Write-Host "Branch doesn't exist on remote yet" -ForegroundColor Gray
    }
    
    # Check if main has updates
    Write-Host ""
    Write-Host "Checking if main has updates..." -ForegroundColor Gray
    git fetch origin main
    $mainAhead = git rev-list --count origin/main..main 2>$null
    $mainBehind = git rev-list --count main..origin/main 2>$null
    
    if ($mainBehind -gt 0) {
        Write-Host "⚠️  Main branch is $mainBehind commits behind origin/main" -ForegroundColor Yellow
        Write-Host "Consider merging main into your feature branch:" -ForegroundColor Yellow
        Write-Host "  git checkout main" -ForegroundColor Cyan
        Write-Host "  git pull origin main" -ForegroundColor Cyan
        Write-Host "  git checkout $currentBranch" -ForegroundColor Cyan
        Write-Host "  git merge main" -ForegroundColor Cyan
    } else {
        Write-Host "✅ Main branch is up to date" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Sync Complete" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Show current status
Write-Host "Current Status:" -ForegroundColor Cyan
git status --short
Write-Host ""

# Show recent commits
Write-Host "Recent commits:" -ForegroundColor Cyan
git log --oneline --graph -5
Write-Host ""

