# NCAA Basketball Model

This repository contains the NCAAM prediction service (FastAPI) plus supporting scripts and documentation.

## Start Here

- Setup overview: [SETUP.md](SETUP.md)
- Quick start: [QUICK_START.md](QUICK_START.md)
- Codespaces canonical doc: [docs/setup/CODESPACES.md](docs/setup/CODESPACES.md)
- Secrets / API keys: [docs/setup/API_KEY_SETUP.md](docs/setup/API_KEY_SETUP.md)
- Legacy root scripts archived: [archive/README.md](archive/README.md)

## Run The API (Local or Codespaces)

```bash
cd services/prediction-service-python
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

VS Code tasks are available in `.vscode/tasks.json` (start/stop/restart, pytest, ruff).

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

## Secrets

- Odds API key: `ODDS_API_KEY` (preferred) or `THE_ODDS_API_KEY` (legacy name, still accepted)
- Docker Compose/Azure secrets are supported via env vars and secret files.

See [docs/setup/API_KEY_SETUP.md](docs/setup/API_KEY_SETUP.md).

## Generate Picks (CLI)

```bash
# Paper-mode picks from canonical data
python generate_tonight_picks.py

# Live mode pulls games/odds from The Odds API
python generate_tonight_picks.py --live
```

See [QUICK_START_TONIGHT.md](QUICK_START_TONIGHT.md) for common workflows.

## Architecture

- FastAPI service: `services/prediction-service-python/app/main.py` (run via uvicorn)
- Data sources: Azure Blob canonical data + The Odds API (optional live mode)
- Storage/cache: PostgreSQL + Redis (used in container/dev modes)

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
- ✅ No automated schedules: runs are operator-initiated.
- ✅ Services run once and exit; everything is manual-run + manual-review.
- ✅ Backtesting remains manual-only (see `MODEL_BACKTEST_AND_INDEPENDENCE_CONFIRMATION.md`).

**To get fresh picks:**
1. Run `python generate_tonight_picks.py` (or `--live`)
2. Review outputs under `testing/results/predictions/`
