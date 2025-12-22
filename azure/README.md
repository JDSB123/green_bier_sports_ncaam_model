# NCAAM v6.3 - Azure Deployment (Enterprise Primary)

## Overview

Azure Container Apps in **greenbier-enterprise-rg** is the canonical runtime. Local Docker Compose is for development and troubleshooting only.

**Manual-only picks:** Azure hosts the API and data plane; picks run only when you manually invoke `run_today.py` (no cron/polling).

**Manual-only:** Azure runs the API, but **picks are generated only when you manually run** `run_today.py` (no cron/polling).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Azure Resource Group                              │
│                        (greenbier-enterprise-rg)                        │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │ Azure Container │  │ Azure Database  │  │ Azure Cache for Redis  │ │
│  │ Registry (ACR)  │  │ for PostgreSQL  │  │                        │ │
│  │ ncaamprodgbeacr │  │ ncaam-prod-gbe- │  │ ncaam-prod-gbe-redis   │ │
│  │                 │  │ postgres        │  │                        │ │
│  └────────┬────────┘  └────────┬────────┘  └────────────────────────┘ │
│           │                    │                       │               │
│           ▼                    ▼                       ▼               │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                   Container Apps Environment                     │  │
│  │                   (ncaam-prod-env)                              │  │
│  │                                                                  │  │
│  │  ┌────────────────────────────────────────────────────────────┐ │  │
│  │  │            ncaam-prod-prediction                           │ │  │
│  │  │          (single container image)                          │ │  │
│  │  │                                                            │ │  │
│  │  └────────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Azure CLI** - Install from https://aka.ms/installazurecliwindows
2. **Docker Desktop** - Running and logged in
3. **Azure Subscription** - With permissions to create resources in **greenbier-enterprise-rg**
4. **The Odds API Key** - From https://the-odds-api.com

## Quick Start (Enterprise RG)

```powershell
az login
az account set --subscription "<Your Subscription Name>"
cd azure
./deploy.ps1 -Environment prod -EnterpriseMode -OddsApiKey "YOUR_ACTUAL_KEY"
```

What this does:
- Creates/uses resources in **greenbier-enterprise-rg** (eastus)
- Deploys ACR, PostgreSQL Flexible Server, Redis Cache, Log Analytics
- Builds and pushes the prediction image to ACR
- Deploys the Container App
- Seeds secrets (db/redis/passwords, odds key, optional Teams webhook)

## Deployment Options

- **Enterprise (recommended):** `./deploy.ps1 -Environment prod -EnterpriseMode -OddsApiKey "KEY"`
- **Dedicated RG per env:** `./deploy.ps1 -Environment staging -ResourceGroup ncaam-staging-rg -OddsApiKey "KEY" -EnterpriseMode:$false`
- **Skip infra (re-deploy image only):** `./deploy.ps1 -Environment prod -OddsApiKey "KEY" -SkipInfra`
- **Skip build (reuse latest pushed image):** `./deploy.ps1 -Environment prod -OddsApiKey "KEY" -SkipBuild`
- **Override image tag:** `./deploy.ps1 -Environment prod -ImageTag "v6.3.1" -OddsApiKey "KEY"`

## Manual deployment (not typical)

```powershell
az group create --name greenbier-enterprise-rg --location eastus
az deployment group create `
  --resource-group greenbier-enterprise-rg `
  --template-file main.bicep `
  --parameters environment=prod postgresPassword="$(openssl rand -base64 24)" redisPassword="$(openssl rand -base64 24)" oddsApiKey="YOUR_ACTUAL_KEY"
```

Build/push image manually:

```powershell
az acr login --name ncaamprodgbeacr
docker build -t ncaamprodgbeacr.azurecr.io/ncaam-prediction:v6.3.1 -f services/prediction-service-python/Dockerfile.hardened .
docker push ncaamprodgbeacr.azurecr.io/ncaam-prediction:v6.3.1
az containerapp update --name ncaam-prod-prediction --resource-group greenbier-enterprise-rg --image ncaamprodgbeacr.azurecr.io/ncaam-prediction:v6.3.1
```

## Environment Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `DATABASE_URL` | Constructed | PostgreSQL connection string |
| `REDIS_URL` | Constructed | Redis connection string |
| `THE_ODDS_API_KEY` | Secret | Odds API key |
| `TEAMS_WEBHOOK_URL` | Optional secret | Enables `run_today.py --teams` |
| `SPORT` | Config | Sport identifier (ncaam) |
| `TZ` | Config | Timezone (America/Chicago) |

**Note:** Code reads API key from environment variable `THE_ODDS_API_KEY`. The `-OddsApiKey` deployment parameter sets this environment variable.

## Secrets Management

- `db-password` - PostgreSQL password (auto-generated)
- `redis-password` - Redis access key (from Azure)
- `odds-api-key` - The Odds API key (provided by you)
- `acr-password` - ACR pull credential (auto-generated)
- `teams-webhook-url` - (Optional) Teams webhook URL for posting picks

## Scaling

- **Min replicas:** 0 (scale to zero when idle)
- **Max replicas:** 1 (default). Increase if you need concurrent callers.
- **Scale trigger:** HTTP requests (10 concurrent)

Example to change scaling:

```powershell
az containerapp update `
  --name ncaam-prod-prediction `
  --resource-group greenbier-enterprise-rg `
  --min-replicas 1 `
  --max-replicas 3
```

## Monitoring

- Logs: `az containerapp logs show -n ncaam-prod-prediction -g greenbier-enterprise-rg --follow`
- Metrics: `az monitor metrics list --resource /subscriptions/{sub}/resourceGroups/greenbier-enterprise-rg/providers/Microsoft.App/containerApps/ncaam-prod-prediction --metric "Requests"`
- Portal: **Azure Portal > Container Apps > ncaam-prod-prediction**

## Troubleshooting

- Container status: `az containerapp show -n ncaam-prod-prediction -g greenbier-enterprise-rg --query "properties.runningStatus"`
- System logs: `az containerapp logs show -n ncaam-prod-prediction -g greenbier-enterprise-rg --type system`
- PostgreSQL connectivity: `az postgres flexible-server execute -n ncaam-prod-gbe-postgres -g greenbier-enterprise-rg -u ncaam -d ncaam --querytext "SELECT 1"`
- Image tags: `az acr repository show-tags --name ncaamprodgbeacr --repository ncaam-prediction`

## Cleanup (destructive)

```powershell
az group delete --name greenbier-enterprise-rg --yes --no-wait
```

## Notes on local vs Azure

- **Azure is the source of truth.** Use this directory and greenbier-enterprise-rg for production.
- Local Docker Compose is for development or offline modeling only.
- Picks are manual: run inside the container app shell if you need Teams/web output.
