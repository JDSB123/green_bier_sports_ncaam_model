# NCAA Basketball v5.1 - PRODUCTION FINAL

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
   
2. **Manually create** `secrets/odds_api_key.txt` with your API key:
   ```
   4a0b80471d1ebeeb74c358fa0fcc4a27
   ```
   (Replace with your actual API key)

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

- Home Court Advantage (Spread): 3.0 pts
- Home Court Advantage (Total): 4.5 pts
- Minimum Spread Edge: 2.5 pts
- Minimum Total Edge: 3.0 pts

## Container Status

This is the **FINAL** production container. Do not modify unless creating a new version.

