# Files Summary - NCAAM Model

**Date:** December 23, 2025  
**Purpose:** Quick reference of key files in the repository

---

## 🎯 Essential Files (Required for Functionality)

### Deployment Files (Core)
1. **`azure/deploy.ps1`** - One-click Azure deployment script
   - Deploys to `NCAAM-GBSV-MODEL-RG`
   - **Usage:** `.\deploy.ps1 -OddsApiKey "YOUR_KEY"`

2. **`azure/main.bicep`** - Azure infrastructure as code
   - Defines all Azure resources
   - Tags resources for organization

3. **`docker-compose.yml`** - Local development/deployment
   - Pulls from `ncaamstableacr.azurecr.io`
   - **Usage:** `docker compose up -d`

4. **`.github/workflows/build-and-push.yml`** - CI/CD pipeline
   - Builds and pushes images on merge to main
   - Updates docker-compose.yml with new version

---

## 📚 Documentation Files (Reference Only)

| File | Purpose |
|------|---------|
| `docs/AZURE_RESOURCE_CLEANUP.md` | Cleanup status and production standards |
| `docs/NAMING_STANDARDS.md` | Resource naming conventions |
| `docs/CONFIGURATION.md` | Port and environment configuration |
| `azure/README.md` | Azure deployment guide |
| `README.md` | Project overview |

---

## 🔧 Service Code

### Prediction Service (Python)
- `services/prediction-service-python/` - Core prediction engine
   - `app/prediction_engine_v33.py` - Orchestrator/adapter (v33.6)
   - `app/predictors/` - Modular models (FG/H1 Spread & Total)
  - `app/main.py` - FastAPI endpoints
  - `run_today.py` - Daily picks orchestrator

### Ratings Sync (Go)
- `services/ratings-sync-go/` - Barttorvik ratings fetcher
  - `main.go` - Ratings sync logic

### Odds Ingestion (Rust)
- `services/odds-ingestion-rust/` - The Odds API integration
  - `src/main.rs` - Odds ingestion logic

---

## 📋 Quick Reference

### Deploy to Azure
```powershell
cd azure
.\deploy.ps1 -OddsApiKey "YOUR_KEY"
```

### Run Locally
```bash
docker compose up -d
```

### Generate Daily Picks
```bash
docker compose exec prediction-service python /app/run_today.py --teams
```

---

## 🗂️ Project Structure

```
/workspace/
├── azure/                      # Azure deployment files
│   ├── deploy.ps1             # Deployment script
│   ├── main.bicep             # Infrastructure template
│   └── parameters.prod.json   # Production parameters
├── services/
│   ├── prediction-service-python/  # Python prediction engine
│   ├── ratings-sync-go/            # Go ratings fetcher
│   └── odds-ingestion-rust/        # Rust odds ingestion
├── database/
│   └── migrations/            # SQL migrations
├── docs/                      # Documentation
├── testing/                   # Test scripts
├── docker-compose.yml         # Container orchestration
└── README.md                  # Project overview
```

---

**TL;DR:** 
- Deploy with `azure/deploy.ps1`
- Run locally with `docker compose up -d`
- Generate picks with `run_today.py`

---

**Last Updated:** December 23, 2025
