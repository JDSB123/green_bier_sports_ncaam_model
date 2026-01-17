# NCAA Basketball v33.15.0

## 🚀 **NEW USERS: START HERE**

**First time setting up?** Read this first → [START_HERE.md](../START_HERE.md)

**Having issues?** Run environment checker: `.\check-environment.bat`

---

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

## Codespaces quick-start notes

- The Codespaces setup installs only the base Python dependencies for fast startup. Heavy data and ML packages (pandas, numpy, scikit-learn, xgboost, Azure blob clients) are optional and moved to `services/prediction-service-python/requirements-heavy.txt`.
- To install heavy dependencies inside the Codespace (may take a while):

```bash
bash .devcontainer/install-heavy-requirements.sh
```

- A persistent pip cache is mounted at `/home/codespace/.cache/pip` to speed repeated starts.

If you want the full environment baked into the image for instantaneous starts, consider creating a custom devcontainer image or enabling Codespaces prebuilds.

### Publishing the devcontainer image to Azure Container Registry (optional)

If you want the prebuilt devcontainer image available in Azure Container Registry (ACR) so your Azure Container Apps or other infra can reuse the same image, configure the following GitHub repository secrets and the CI workflow will push to ACR automatically when present:

- `AZURE_CLIENT_ID` — Service principal client id
- `AZURE_CLIENT_SECRET` — Service principal client secret
- `AZURE_TENANT_ID` — Azure tenant id (used if you modify the workflow to login via `azure/login`)
- `ACR_REGISTRY` — Your ACR login server (e.g. `myregistry.azurecr.io`)

How it works:

- The GitHub Actions workflow builds the devcontainer image and always pushes to GitHub Container Registry (GHCR).
- If the ACR secrets above are set, the workflow additionally logs into ACR and pushes the same image to `ACR_REGISTRY/green_bier_sports_ncaam_model:latest`.

To create a service principal and grant push access to ACR, run:

```bash
az ad sp create-for-rbac --name "gh-actions-acr-pusher" --role acrpush --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/<RG>/providers/Microsoft.ContainerRegistry/registries/<ACR_NAME>
```

Then add the returned `appId` as `AZURE_CLIENT_ID`, `password` as `AZURE_CLIENT_SECRET`, and your `tenant` as `AZURE_TENANT_ID`. Set `ACR_REGISTRY` to `<ACR_NAME>.azurecr.io`.

### Heavy devcontainer image

The workflow now builds two devcontainer images:

- `ghcr.io/<owner>/green_bier_sports_ncaam_model:latest` — base image with runtime packages.
- `ghcr.io/<owner>/green_bier_sports_ncaam_model:heavy` — image that includes heavy ML/data packages (pandas, numpy, scikit-learn, xgboost).

If ACR secrets are configured, both variants are also mirrored to your ACR as `ACR_REGISTRY/green_bier_sports_ncaam_model:latest` and `ACR_REGISTRY/green_bier_sports_ncaam_model:heavy`.

Use the `:heavy` image in ACA if you want the ML deps preinstalled in production (note larger image size and longer build times).

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

3. **Set Azure historical data access:**
   ```powershell
   # Required for canonical historical data + team aliases
   $env:AZURE_CANONICAL_CONNECTION_STRING = "YOUR_CANONICAL_CONNECTION_STRING"
   ```
4. Build the container: `docker compose build`
5. Run: `.\predict.bat`

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

## Model Parameters (v33.10.0)

**Full Game:**
- Home Court Advantage (Spread): 5.8 pts (backtested from 3,318 games)
- Home Court Advantage (Total): 0.0 pts (zero-sum)
- Minimum Spread Edge: 2.0 pts
- Minimum Total Edge: 3.0 pts (no MAX_EDGE cap; totals are range-gated)

**First Half:**
- Home Court Advantage (Spread): 3.6 pts (backtested from 904 1H games)
- Home Court Advantage (Total): 0.0 pts (zero-sum)
- Minimum Spread Edge: 3.5 pts
- Minimum Total Edge: 2.0 pts (max 3.5)

## Data Sources

**IMPORTANT:** Before working with historical data, read [`docs/SINGLE_SOURCE_OF_TRUTH.md`](docs/SINGLE_SOURCE_OF_TRUTH.md) - this establishes canonical data sources and prevents data inconsistencies.

- **Bart Torvik API:** Team efficiency ratings and Four Factors metrics
  - For complete field reference, see [`docs/BARTTORVIK_FIELDS.md`](docs/BARTTORVIK_FIELDS.md)
- **The Odds API:** Live betting odds for edge calculation
- **Historical Data:** Azure Blob Storage (`metricstrackersgbsv/ncaam-historical-data`)
  - Canonical scores, odds, and ratings for backtesting
  - See [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) for details

## Container Status

This is the **FINAL** production container. Do not modify unless creating a new version.

## Manual-Only Operation

**Picks and deployments are operator-initiated.** Nothing runs on schedules or polling loops.

- ✅ Deployments are run via `azure/deploy.ps1` (manual)
- ✅ No cron jobs or scheduled tasks kick off predictions.
- ✅ No continuous polling loops (RUN_ONCE=true enforced in Go/Rust services).
- ✅ No automated data/backtesting workflows—`.\predict.bat` is still the only way to refresh data and make picks.
- ✅ Services run once and exit; everything is manual-run + manual-review.
- ✅ Backtesting remains manual-only (see `MODEL_BACKTEST_AND_INDEPENDENCE_CONFIRMATION.md`).

**To get fresh picks:**
1. Execute `.\predict.bat` manually when you want fresh data and recommendations
2. System syncs ratings and odds once, runs predictions, and exits
3. You have full control - nothing runs automatically
