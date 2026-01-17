# NCAAM Sports Model - Setup & Architecture Guide

## 🎯 One-Step Setup (Choose One Path)

### Path 1: Local Development (Windows 10/11)
**Use this if:** You want full control, prefer local testing, have a powerful machine
```powershell
# Run once with Administrator privileges
.\scripts\setup-local-complete.ps1
```
**What it does:**
- Installs PostgreSQL 15 (localhost:5432)
- Installs Redis (localhost:6379)
- Creates Python 3.12 venv
- Installs all dependencies (Python + Go)
- Runs verification tests
**Time:** ~15 minutes
**Resources:** 2GB RAM minimum, 5GB disk

### Path 2: GitHub Codespaces (Browser)
**Use this if:** You want cloud dev, need fast onboarding, prefer browser IDE
```bash
# Click "Create codespace on main" in GitHub
# Everything pre-configured automatically
```
**What it does:**
- Spins up cloud VM with all tools pre-installed
- PostgreSQL + Redis running in container
- Python 3.12 + Go 1.22 ready
- VS Code in browser
**Time:** ~3 minutes
**Cost:** Free tier included, then ~$0.07-0.18/hour

---

## 📁 Project Structure (Single Source of Truth)

```
green_bier_sports_ncaam_model/
├── .devcontainer/                    # ← Codespaces config (DO NOT TOUCH)
│   └── devcontainer.json
│
├── services/
│   ├── prediction-service-python/    # ← ML models + API (Python)
│   │   ├── main.py
│   │   ├── requirements.txt           # ← Install this with pip
│   │   └── ...
│   │
│   └── ratings-sync-go/              # ← Data ingestion (Go)
│       ├── main.go
│       ├── go.mod
│       ├── go.sum
│       └── ...
│
├── database/
│   ├── migrations/                   # ← PostgreSQL schema
│   └── seeds/
│
├── .env.local                        # ← Local config (DO NOT COMMIT)
├── docker-compose.yml                # ← For Codespaces/production only
│
├── SETUP.md                          # ← THIS FILE - read first!
├── ARCHITECTURE.md                   # ← System design
├── VERIFY.md                         # ← Health check commands
│
└── scripts/
    ├── setup-local-complete.ps1      # ← ONE setup script for Windows
    ├── check-r-setup.ps1             # ← Verify R is installed
    └── verify-all.ps1                # ← Run all checks
```

---

## 🏗️ Architecture at a Glance

```
┌──────────────────────────────────────────────────────────────┐
│                    YOUR TECH STACK                           │
└──────────────────────────────────────────────────────────────┘

🌐 CLIENT LAYER
├─ Web browser (picks display)
└─ Mobile app (future)

📡 API LAYER
├─ FastAPI (Python) - HTTP REST endpoints
│  └─ Handles: /predict, /picks, /history
└─ Health check: localhost:8000/health

⚙️ BUSINESS LOGIC
├─ Python ML Models
│  ├─ XGBoost (spread prediction)
│  ├─ XGBoost (total prediction)
│  └─ Ensemble combinations
└─ Go Ratings Sync (data ingestion)
   └─ Fetches Barttorvik daily ratings

💾 DATA LAYER
├─ PostgreSQL 15 (localhost:5432)
│  ├─ teams table
│  ├─ games table
│  ├─ odds_snapshots table
│  ├─ team_ratings table
│  └─ predictions table
│
└─ Redis (localhost:6379)
   ├─ Prediction cache (TTL: 4 hours)
   ├─ Odds snapshot cache
   └─ Session data

```

---

## ✅ What Gets Installed (No Confusion)

### LOCAL (Windows)
```
✅ PostgreSQL 15         → C:\Program Files\PostgreSQL\15
✅ Redis 3.2 (Windows)   → C:\Program Files\Redis
✅ Python 3.12           → System (already have)
✅ Python venv           → .\.venv\ (created by script)
✅ Go 1.22               → Uses system Go (if installed)
✅ R 4.5.2               → C:\Program Files\R\R-4.5.2 (optional)
```

### CODESPACES (Cloud)
```
✅ Everything automatic (no manual install needed)
✅ PostgreSQL 15         → localhost:5432 (container)
✅ Redis 7               → localhost:6379 (container)
✅ Python 3.12           → Pre-installed
✅ Go 1.22               → Pre-installed
✅ R 4.5.2               → Pre-installed
```

---

## 🚀 Quick Start

### First Time: LOCAL
```powershell
# 1. Start fresh (admin terminal)
.\scripts\setup-local-complete.ps1

# 2. Verify everything works
.\scripts\verify-all.ps1

# 3. Start services (keep running)
.\scripts\start-services.ps1

# 4. In NEW terminal: Activate venv and run app
.\.venv\Scripts\Activate.ps1
python services/prediction-service-python/main.py
```

### First Time: CODESPACES
```bash
# 1. Click "Create codespace on main"
# 2. Wait 2-3 minutes
# 3. Everything ready - start coding!

# Verify
./scripts/verify-all.sh

# Run app
python services/prediction-service-python/main.py
```

---

## 🔍 How to Verify Setup

**Quick check (30 seconds):**
```powershell
# Windows
.\scripts\verify-all.ps1

# Codespaces
./scripts/verify-all.sh
```

**Full health check (2 minutes):**
```powershell
# Check services
ps aux | grep -E "postgres|redis"

# Check connectivity
psql -U postgres -h localhost -c "SELECT 1"
redis-cli ping

# Check Python
python -m pip list | grep fastapi

# Check Go
go version
```

---

## ⚠️ If Something Goes Wrong

### PostgreSQL won't start
```powershell
# Check service
Get-Service -Name "postgresql-x64-15"

# Restart
Restart-Service -Name "postgresql-x64-15"

# Check logs
C:\Program Files\PostgreSQL\15\data\pg_log
```

### Redis won't start
```powershell
# Check service
Get-Service -Name "Redis"

# Restart
Restart-Service -Name "Redis"

# Or run directly
redis-server
```

### Python venv issues
```powershell
# Delete and recreate
Remove-Item -Recurse -Force .\.venv
python -m venv .venv
.\.venv\Scripts\pip install -r services/prediction-service-python/requirements.txt
```

### Can't connect to PostgreSQL
```powershell
# Default credentials (from .env.local)
$env:PGUSER="postgres"
$env:PGPASSWORD="postgres123"
$env:PGHOST="localhost"
$env:PGPORT="5432"

psql -d ncaam_local
```

---

## 📚 Documentation Files

**Read in order:**
1. **SETUP.md** (this file) - Getting started
2. **ARCHITECTURE.md** - How it's organized
3. **VERIFY.md** - Health checks
4. **CONTRIBUTING.md** - How to add features

---

## 🎯 Decision Tree

| Question | Answer | Then |
|----------|--------|------|
| Do you have local PostgreSQL? | No | Run `setup-local-complete.ps1` |
| Do you want cloud dev? | Yes | Click "Codespaces" button |
| Is your venv broken? | Yes | Run `setup-local-complete.ps1` again |
| Can't connect to DB? | Run `verify-all.ps1` first |
| Want to add a feature? | Read CONTRIBUTING.md |

---

## 🔐 Secrets & Configuration

### Local Development (.env.local)
```
DATABASE_URL=postgresql://postgres:postgres123@localhost:5432/ncaam_local
REDIS_URL=redis://localhost:6379/0
ODDS_API_KEY=<your key from OddsAPI.com>
```

⚠️ **NEVER commit .env.local to git**
✅ Already in .gitignore

### Codespaces
```
All configured automatically via .devcontainer/
No manual .env needed
```

---

## 🆘 Support

1. **Script fails?** → Check `.venv\Scripts\` exists
2. **Port 5432 in use?** → Kill `postgres.exe` and restart service
3. **Still broken?** → Delete `.venv` and run setup again
4. **Antivirus blocking?** → Add `.venv` to exclusion list

---

**Last Updated:** January 17, 2026
**Status:** Production-Ready
