# NCAA Basketball v6.3.1 - PRODUCTION FINAL

## Single Point of Entry

```powershell
.\predict.bat
```

That's it. One command. Everything runs inside the container.

## What This Does

1. Syncs fresh ratings from Barttorvik (Go binary)
2. Syncs fresh odds from The Odds API (Rust binary)  
3. Runs predictions using the model (Python)
4. Outputs betting recommendations with edge calculations

## First-Time Setup

1. **Create secrets files** (REQUIRED - NO .env fallbacks):
   ```powershell
   python ensure_secrets.py
   ```
   This creates `db_password.txt` and `redis_password.txt` with secure random values.
   
2. **Create** `secrets/odds_api_key.txt` with your The Odds API key:
   
   **Configuration locations (used by code):**
   - **Docker Compose:** File `secrets/odds_api_key.txt` → mounted at `/run/secrets/odds_api_key`
   - **Azure Container Apps:** Environment variable `THE_ODDS_API_KEY`
   
   **Get your API key from:** https://the-odds-api.com/
   
   **Create the file (replace `YOUR_ACTUAL_KEY` with your real key):**
   ```powershell
   # Windows PowerShell - replace YOUR_ACTUAL_KEY with your real API key
   $apiKey = "YOUR_ACTUAL_KEY"  # Get from https://the-odds-api.com/
   $apiKey | Out-File -FilePath secrets/odds_api_key.txt -NoNewline -Encoding utf8
   ```
   
   **Or use environment variable (Azure only):**
   ```powershell
   # Set environment variable - code reads from THE_ODDS_API_KEY
   $env:THE_ODDS_API_KEY = "YOUR_ACTUAL_KEY"
   ```
   
   Or use the helper script:
   ```powershell
   python ensure_secrets.py
   ```
   (It will prompt for the API key if not found)

3. Build the container: `docker compose build`
4. Run: `.\predict.bat`

**IMPORTANT:** All secrets MUST be in `secrets/` directory. Container will FAIL if secrets are missing - NO fallbacks to .env or localhost.

## Options

```powershell
.\predict.bat                       # Full slate today
.\predict.bat --no-sync             # Skip data sync (use cached)
.\predict.bat --game "Duke" "UNC"   # Specific game
.\predict.bat --date 2025-12-20     # Specific date
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  prediction-service                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ ratings-sync│  │odds-ingestion│  │  predictor.py  │ │
│  │   (Go)      │  │   (Rust)     │  │   (Python)     │ │
│  └──────┬──────┘  └──────┬───────┘  └────────┬───────┘ │
│         │                │                    │         │
│         └────────────────┴────────────────────┘         │
│                          │                              │
└──────────────────────────┼──────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  PostgreSQL  │
                    │   (ncaam)    │
                    └─────────────┘
```

## Model Parameters

- Home Court Advantage (Spread): 3.2 pts (Standard Torvik)
- Home Court Advantage (Total): 0.0 pts (Standard Efficiency Model)
- Minimum Spread Edge: 2.5 pts
- Minimum Total Edge: 3.0 pts

## Data Sources

- **Bart Torvik API:** Team efficiency ratings and Four Factors metrics
  - For complete field reference, see [`docs/BARTTORVIK_FIELDS.md`](docs/BARTTORVIK_FIELDS.md)
- **The Odds API:** Live betting odds for edge calculation

## Container Status

This is the **FINAL** production container. Do not modify unless creating a new version.

## Manual-Only Operation

**ALL operations are user-initiated only. ZERO automation.**

- ✅ No `.github/workflows/` directory exists
- ✅ No GitHub Actions or CI/CD pipelines
- ✅ No cron jobs or scheduled tasks
- ✅ No continuous polling loops
- ✅ No automated triggers
- ✅ All data fetches are manual via `.\predict.bat`
- ✅ Services run once and exit (RUN_ONCE=true always)

**To get fresh picks:**
1. Execute `.\predict.bat` manually when you want fresh data and recommendations
2. System syncs ratings and odds once, runs predictions, and exits
3. You have full control - nothing runs automatically

