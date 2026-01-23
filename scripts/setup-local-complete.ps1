# ═══════════════════════════════════════════════════════════════════════════════
# NCAAM SPORTS MODEL - COMPLETE LOCAL SETUP SCRIPT
# ═══════════════════════════════════════════════════════════════════════════════
# This is the ONLY setup script you need. Run once with Administrator privileges.
# It installs PostgreSQL, Redis, Python, and all dependencies.
#
# Usage: .\scripts\setup-local-complete.ps1
# ═══════════════════════════════════════════════════════════════════════════════

#Requires -RunAsAdministrator

Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║        NCAAM Sports Model - Complete Local Setup              ║" -ForegroundColor Cyan
Write-Host "║                    (Admin Privileges Required)                ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

# Color helper
function Write-Success { Write-Host $args[0] -ForegroundColor Green }
function Write-Warn { Write-Host $args[0] -ForegroundColor Yellow }
function Write-Error_ { Write-Host $args[0] -ForegroundColor Red }
function Write-Section { Write-Host "`n$($args[0])" -ForegroundColor Cyan; Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray }

$startTime = Get-Date
$failedSteps = @()

# ─────────────────────────────────────────────────────────────────────────────────
# STEP 1: PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────────
Write-Section "[1] PostgreSQL 15 Installation"

$pgPath = "C:\Program Files\PostgreSQL\15"
$pgExe = "$pgPath\bin\psql.exe"

if (Test-Path $pgExe) {
    Write-Success "✓ PostgreSQL 15 already installed at $pgPath"
} else {
    Write-Warn "Downloading PostgreSQL 15..."
    try {
        $pgInstaller = "$env:TEMP\postgresql-15-installer.exe"
        $pgUrl = "https://get.enterprisedb.com/postgresql/postgresql-15.5-1-windows-x64.exe"

        Invoke-WebRequest -Uri $pgUrl -OutFile $pgInstaller -TimeoutSec 120 -ErrorAction Stop
        Write-Warn "Running PostgreSQL installer (this may take 2-3 minutes)..."

        & $pgInstaller --unattendedmodeui minimal --mode unattended `
                       --superpassword postgres123 --servicepassword postgres123 | Out-Null

        Start-Sleep -Seconds 3

        if (Test-Path $pgExe) {
            Write-Success "✓ PostgreSQL 15 installed successfully"
            Remove-Item $pgInstaller -Force
        } else {
            Write-Error_ "✗ PostgreSQL installation failed"
            $failedSteps += "PostgreSQL"
        }
    } catch {
        Write-Error_ "✗ Failed to install PostgreSQL: $_"
        Write-Warn "Download manually from: https://www.postgresql.org/download/windows/"
        $failedSteps += "PostgreSQL"
    }
}

# Start PostgreSQL service
$pgSvc = Get-Service -Name "postgresql-x64-15" -ErrorAction SilentlyContinue
if ($pgSvc) {
    if ($pgSvc.Status -ne "Running") {
        Write-Warn "Starting PostgreSQL service..."
        Start-Service -Name "postgresql-x64-15" -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    Write-Success "✓ PostgreSQL service running"
} else {
    Write-Error_ "✗ PostgreSQL service not found"
    $failedSteps += "PostgreSQL Service"
}

# ─────────────────────────────────────────────────────────────────────────────────
# STEP 2: Redis
# ─────────────────────────────────────────────────────────────────────────────────
Write-Section "[2] Redis Installation"

$redisPath = "C:\Program Files\Redis"
$redisExe = "$redisPath\redis-server.exe"

if (Test-Path $redisExe) {
    Write-Success "✓ Redis already installed at $redisPath"
} else {
    Write-Warn "Downloading Redis for Windows..."
    try {
        $redisInstaller = "$env:TEMP\redis-installer.msi"
        $redisUrl = "https://github.com/microsoftarchive/redis/releases/download/win-3.2.100/Redis-x64-3.2.100.msi"

        Invoke-WebRequest -Uri $redisUrl -OutFile $redisInstaller -TimeoutSec 120 -ErrorAction Stop
        Write-Warn "Running Redis installer..."

        msiexec /i $redisInstaller /quiet /norestart | Out-Null
        Start-Sleep -Seconds 3

        if (Test-Path $redisExe) {
            Write-Success "✓ Redis installed successfully"
            Remove-Item $redisInstaller -Force
        } else {
            Write-Error_ "✗ Redis installation failed"
            $failedSteps += "Redis"
        }
    } catch {
        Write-Error_ "✗ Failed to install Redis: $_"
        Write-Warn "Alternative: Run Redis in WSL2 or Docker"
        $failedSteps += "Redis"
    }
}

# Start Redis service
$redisSvc = Get-Service -Name "Redis" -ErrorAction SilentlyContinue
if ($redisSvc) {
    if ($redisSvc.Status -ne "Running") {
        Write-Warn "Starting Redis service..."
        Start-Service -Name "Redis" -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    Write-Success "✓ Redis service running"
} else {
    Write-Error_ "✗ Redis service not found (will need manual start)"
    $failedSteps += "Redis Service"
}

# ─────────────────────────────────────────────────────────────────────────────────
# STEP 3: Python Virtual Environment
# ─────────────────────────────────────────────────────────────────────────────────
Write-Section "[3] Python Virtual Environment"

Write-Warn "Cleaning old venv..."
$venvPath = ".\.venv"
if (Test-Path $venvPath) {
    cmd /c "rmdir /s /q $venvPath" 2>$null
    Start-Sleep -Seconds 1
}

Write-Warn "Creating new Python venv..."
try {
    python -m venv .venv -ErrorAction Stop
    Write-Success "✓ Virtual environment created"
} catch {
    Write-Error_ "✗ Failed to create venv: $_"
    $failedSteps += "Python venv"
}

# Upgrade pip
Write-Warn "Upgrading pip..."
try {
    & ".\.venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel --quiet -ErrorAction Stop
    Write-Success "✓ pip upgraded"
} catch {
    Write-Error_ "✗ Failed to upgrade pip: $_"
    $failedSteps += "pip upgrade"
}

# ─────────────────────────────────────────────────────────────────────────────────
# STEP 4: Python Dependencies
# ─────────────────────────────────────────────────────────────────────────────────
Write-Section "[4] Installing Python Dependencies"

Write-Warn "Installing project dependencies..."
try {
    & ".\.venv\Scripts\pip.exe" install -r "services\prediction-service-python\requirements.txt" --quiet -ErrorAction Stop
    Write-Success "✓ Project dependencies installed"
} catch {
    Write-Error_ "✗ Failed to install project dependencies: $_"
    $failedSteps += "Project dependencies"
}

Write-Warn "Installing development dependencies..."
try {
    & ".\.venv\Scripts\pip.exe" install -r "requirements-dev.txt" --quiet -ErrorAction Stop
    Write-Success "✓ Development dependencies installed"
} catch {
    Write-Error_ "✗ Failed to install dev dependencies: $_"
    $failedSteps += "Dev dependencies"
}

# ─────────────────────────────────────────────────────────────────────────────────
# STEP 5: Configuration Files
# ─────────────────────────────────────────────────────────────────────────────────
Write-Section "[5] Creating Configuration Files"

if (-not (Test-Path ".\.env.local")) {
    Write-Warn "Creating .env.local..."
    $envContent = @"
# Local Development Configuration
# Created: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

DATABASE_URL=postgresql://postgres:postgres123@localhost:5432/ncaam_local
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres123
DB_NAME=ncaam_local

REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

ENVIRONMENT=local
DEBUG=true
LOG_LEVEL=DEBUG

API_PORT=8000

ODDS_API_KEY=
TEAMS_WEBHOOK_SECRET=
"@
    Set-Content -Path ".\.env.local" -Value $envContent
    Write-Success "✓ Created .env.local (add your API keys)"
} else {
    Write-Success "✓ .env.local already exists"
}

# ─────────────────────────────────────────────────────────────────────────────────
# STEP 6: Database Setup
# ─────────────────────────────────────────────────────────────────────────────────
Write-Section "[6] Database Initialization"

$pgExe = "C:\Program Files\PostgreSQL\15\bin\psql.exe"
if (Test-Path $pgExe) {
    Write-Warn "Checking PostgreSQL connectivity..."
    try {
        $env:PGPASSWORD = "postgres123"
        & $pgExe -h localhost -U postgres -c "SELECT 1" -q 2>$null
        Write-Success "✓ PostgreSQL connection verified"

        Write-Warn "Creating ncaam_local database..."
        & $pgExe -h localhost -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'ncaam_local'" 2>$null | Select-String "1" | Out-Null
        if (-not $?) {
            & $pgExe -h localhost -U postgres -c "CREATE DATABASE ncaam_local" -q 2>$null
            Write-Success "✓ Database created"
        } else {
            Write-Success "✓ Database already exists"
        }
    } catch {
        Write-Error_ "✗ Database initialization failed: $_"
        $failedSteps += "Database init"
    }
} else {
    Write-Warn "⚠ PostgreSQL not available for database setup"
}

# ─────────────────────────────────────────────────────────────────────────────────
# STEP 7: Verification
# ─────────────────────────────────────────────────────────────────────────────────
Write-Section "[7] Verification"

Write-Warn "Checking Python..."
& ".\.venv\Scripts\python.exe" --version
Write-Success "✓ Python ready"

Write-Warn "Checking pip packages..."
$pkgCount = (& ".\.venv\Scripts\pip.exe" list --quiet | Measure-Object -Line).Lines
Write-Success "✓ $pkgCount packages installed"

# ─────────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────────
Write-Section "Setup Summary"

$duration = (Get-Date) - $startTime
Write-Host "Time elapsed: $($duration.Minutes)m $($duration.Seconds)s"
Write-Host ""

if ($failedSteps.Count -eq 0) {
    Write-Success "✓ ALL STEPS COMPLETED SUCCESSFULLY!"
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Edit .env.local and add ODDS_API_KEY"
    Write-Host "  2. Run: .\.venv\Scripts\Activate.ps1"
    Write-Host "  3. Run: cd services\prediction-service-python; python -m uvicorn app.main:app --reload --port 8000"
    Write-Host "  4. Visit: http://localhost:8000/docs"
    Write-Host ""
    Write-Host "To verify everything: .\scripts\verify-all.ps1"
} else {
    Write-Error_ "⚠ Setup completed with $($failedSteps.Count) issue(s):"
    $failedSteps | ForEach-Object { Write-Error_ "  - $_" }
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Check SETUP.md for manual instructions"
    Write-Host "  2. Run script again with Administrator privileges"
    Write-Host "  3. Check Services.msc for PostgreSQL/Redis status"
}

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Gray
Write-Host "  PostgreSQL: localhost:5432 (user: postgres, pass: postgres123)"
Write-Host "  Redis: localhost:6379"
Write-Host "  Python venv: .\.venv"
Write-Host ""
