# NCAAM Model - Complete Verification Script
# Run this to verify your entire setup is working

Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         NCAAM Sports Model - System Verification              ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

$allGood = $true

# PostgreSQL
Write-Host "`n[PostgreSQL]" -ForegroundColor Cyan
$pgExe = "C:\Program Files\PostgreSQL\15\bin\psql.exe"
if (Test-Path $pgExe) {
    Write-Host "✓ PostgreSQL binary found" -ForegroundColor Green
    $pgSvc = Get-Service -Name "postgresql-x64-15" -ErrorAction SilentlyContinue
    if ($pgSvc -and $pgSvc.Status -eq "Running") {
        Write-Host "✓ PostgreSQL service running" -ForegroundColor Green
        $env:PGPASSWORD = "postgres123"
        try {
            $result = & $pgExe -h localhost -U postgres -tc "SELECT 1" 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✓ PostgreSQL connection OK" -ForegroundColor Green
            } else {
                Write-Host "✗ Cannot connect to PostgreSQL" -ForegroundColor Red
                $allGood = $false
            }
        } catch {
            Write-Host "✗ Error testing PostgreSQL: $_" -ForegroundColor Red
            $allGood = $false
        }
    } else {
        Write-Host "✗ PostgreSQL service not running" -ForegroundColor Red
        Write-Host "  Run: Start-Service -Name 'postgresql-x64-15'" -ForegroundColor Yellow
        $allGood = $false
    }
} else {
    Write-Host "✗ PostgreSQL not installed at $pgExe" -ForegroundColor Red
    $allGood = $false
}

# Redis
Write-Host "`n[Redis]" -ForegroundColor Cyan
$redisExe = "C:\Program Files\Redis\redis-cli.exe"
if (Test-Path $redisExe) {
    Write-Host "✓ Redis binary found" -ForegroundColor Green
    $redisSvc = Get-Service -Name "Redis" -ErrorAction SilentlyContinue
    if ($redisSvc -and $redisSvc.Status -eq "Running") {
        Write-Host "✓ Redis service running" -ForegroundColor Green
        try {
            $result = & $redisExe ping 2>&1
            if ($result -eq "PONG") {
                Write-Host "✓ Redis connection OK" -ForegroundColor Green
            } else {
                Write-Host "✗ Redis not responding correctly" -ForegroundColor Red
                $allGood = $false
            }
        } catch {
            Write-Host "✗ Error testing Redis: $_" -ForegroundColor Red
            $allGood = $false
        }
    } else {
        Write-Host "✗ Redis service not running" -ForegroundColor Red
        Write-Host "  Run: Start-Service -Name 'Redis'" -ForegroundColor Yellow
        $allGood = $false
    }
} else {
    Write-Host "✗ Redis not installed at $redisExe" -ForegroundColor Red
    $allGood = $false
}

# Python
Write-Host "`n[Python & Virtual Environment]" -ForegroundColor Cyan
if (Test-Path ".\.venv\Scripts\python.exe") {
    Write-Host "✓ Virtual environment exists" -ForegroundColor Green
    try {
        $version = & ".\.venv\Scripts\python.exe" --version 2>&1
        Write-Host "✓ $version" -ForegroundColor Green

        $fastapi = & ".\.venv\Scripts\pip.exe" list --quiet 2>&1 | Select-String "fastapi"
        if ($fastapi) {
            Write-Host "✓ FastAPI installed" -ForegroundColor Green
        } else {
            Write-Host "✗ FastAPI not found" -ForegroundColor Red
            $allGood = $false
        }

        $redis = & ".\.venv\Scripts\pip.exe" list --quiet 2>&1 | Select-String "redis"
        if ($redis) {
            Write-Host "✓ Redis Python client installed" -ForegroundColor Green
        } else {
            Write-Host "✗ Redis Python client not found" -ForegroundColor Red
            $allGood = $false
        }

        $psycopg = & ".\.venv\Scripts\pip.exe" list --quiet 2>&1 | Select-String "psycopg"
        if ($psycopg) {
            Write-Host "✓ PostgreSQL driver installed" -ForegroundColor Green
        } else {
            Write-Host "✗ PostgreSQL driver not found" -ForegroundColor Red
            $allGood = $false
        }
    } catch {
        Write-Host "✗ Error checking Python: $_" -ForegroundColor Red
        $allGood = $false
    }
} else {
    Write-Host "✗ Virtual environment not found (.\.venv)" -ForegroundColor Red
    Write-Host "  Run: .\scripts\setup-local-complete.ps1" -ForegroundColor Yellow
    $allGood = $false
}

# Go
Write-Host "`n[Go]" -ForegroundColor Cyan
try {
    $goVersion = go version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ $goVersion" -ForegroundColor Green
        if (Test-Path "services\ratings-sync-go\go.mod") {
            Write-Host "✓ Go module found" -ForegroundColor Green
        } else {
            Write-Host "⚠ Go module not found" -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "⚠ Go not installed (optional for now)" -ForegroundColor Yellow
}

# R
Write-Host "`n[R (Optional)]" -ForegroundColor Cyan
$rPath = "C:\Program Files\R\R-4.5.2\bin\R.exe"
if (Test-Path $rPath) {
    Write-Host "✓ R 4.5.2 installed" -ForegroundColor Green
} else {
    Write-Host "⚠ R not installed (optional)" -ForegroundColor Yellow
}

# Configuration
Write-Host "`n[Configuration]" -ForegroundColor Cyan
if (Test-Path ".\.env.local") {
    Write-Host "✓ .env.local exists" -ForegroundColor Green
    $apiKey = Select-String "^ODDS_API_KEY=" ".\.env.local"
    if ($apiKey -match "ODDS_API_KEY=\s*$") {
        Write-Host "⚠ ODDS_API_KEY not set in .env.local" -ForegroundColor Yellow
    } else {
        Write-Host "✓ ODDS_API_KEY configured" -ForegroundColor Green
    }
} else {
    Write-Host "✗ .env.local not found" -ForegroundColor Red
    $allGood = $false
}

# Summary
Write-Host "`n╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
if ($allGood) {
    Write-Host "║  ✓ ALL SYSTEMS OPERATIONAL                                   ║" -ForegroundColor Green
    Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "Ready to run:" -ForegroundColor Cyan
    Write-Host "  .\.venv\Scripts\Activate.ps1"
    Write-Host "  cd services\prediction-service-python; python -m uvicorn app.main:app --reload --port 8000"
} else {
    Write-Host "║  ⚠ SOME ISSUES DETECTED - SEE ABOVE                         ║" -ForegroundColor Red
    Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Run setup again: .\scripts\setup-local-complete.ps1"
    Write-Host "  2. Check SETUP.md for manual steps"
    Write-Host "  3. Restart Services (Services.msc)"
}

Write-Host ""
