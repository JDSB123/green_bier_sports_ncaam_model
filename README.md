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

1. Copy `.env.example` to `.env`
2. Add your secrets to `secrets/`:
   - `db_password.txt`
   - `odds_api_key.txt`
   - `redis_password.txt`
3. Build the container: `docker compose build`
4. Run: `.\predict.bat`

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
