# NCAAM v6.3 - Azure Deployment (Manual-Only)

## Overview

This directory contains everything needed to deploy the NCAAM prediction model to Azure Container Apps.

**Manual-only:** Azure runs the API, but **picks are generated only when you manually run** `run_today.py` (no cron/polling).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Azure Resource Group                              │
│                        (ncaam-prod-rg)                                  │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │ Azure Container │  │ Azure Database  │  │ Azure Cache for Redis  │ │
│  │ Registry (ACR)  │  │ for PostgreSQL  │  │                        │ │
│  │                 │  │                 │  │                        │ │
│  │ ncaamprodacr    │  │ Flexible Server │  │ ncaam-prod-redis       │ │
│  └────────┬────────┘  │ ncaam-prod-pg   │  └────────────────────────┘ │
│           │           └────────┬────────┘              │               │
│           │                    │                       │               │
│           ▼                    ▼                       ▼               │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                   Container Apps Environment                     │  │
│  │                   (ncaam-prod-env)                              │  │
│  │                                                                  │  │
│  │  ┌────────────────────────────────────────────────────────────┐ │  │
│  │  │            ncaam-prod-prediction                           │ │  │
│  │  │                                                            │ │  │
│  │  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐  │ │  │
│  │  │  │ ratings-sync │ │ odds-ingest  │ │ prediction-svc   │  │ │  │
│  │  │  │ (Go binary)  │ │ (Rust binary)│ │ (Python + API)   │  │ │  │
│  │  │  └──────────────┘ └──────────────┘ └──────────────────┘  │ │  │
│  │  │                                                            │ │  │
│  │  └────────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Azure CLI** - Install from https://aka.ms/installazurecliwindows
2. **Docker Desktop** - Running and logged in
3. **Azure Subscription** - With permissions to create resources
4. **The Odds API Key** - From https://the-odds-api.com

## Quick Start

### 1. Login to Azure

```powershell
az login
az account set --subscription "Your Subscription Name"
```

### 2. Deploy Everything

```powershell
cd azure
# Replace YOUR_ACTUAL_KEY with your real API key from https://the-odds-api.com/
# The code will read from environment variable THE_ODDS_API_KEY
.\deploy.ps1 -Environment prod -OddsApiKey "YOUR_ACTUAL_KEY"
```

This will:
- Create Azure Resource Group
- Deploy Azure Container Registry
- Deploy Azure Database for PostgreSQL
- Deploy Azure Cache for Redis
- Deploy Container Apps Environment
- Build and push Docker image
- Deploy the prediction service
- Run database migrations

### 3. Verify Deployment

```powershell
# Check health
curl https://ncaam-prod-prediction.azurecontainerapps.io/health

# View logs
az containerapp logs show -n ncaam-prod-prediction -g ncaam-prod-rg --follow
```

## Deployment Options

### Full Deployment (Default - Dedicated Resource Group)

```powershell
# Replace YOUR_ACTUAL_KEY with your real API key (sets env var THE_ODDS_API_KEY)
.\deploy.ps1 -Environment prod -OddsApiKey "YOUR_ACTUAL_KEY"
# Deploys to: ncaam-prod-rg (centralus)
```

### Enterprise Mode Deployment (greenbier-enterprise-rg)

```powershell
# Deploy to enterprise resource group with NCAAM model organization
.\deploy.ps1 -Environment prod -EnterpriseMode -OddsApiKey "YOUR_ACTUAL_KEY"
# Deploys to: greenbier-enterprise-rg (eastus)
# Resources tagged with Model=ncaam for organization
```

### Skip Infrastructure (Image Update Only)

```powershell
.\deploy.ps1 -Environment prod -OddsApiKey "your-key" -SkipInfra
```

### Skip Docker Build (Redeploy Existing Image)

```powershell
.\deploy.ps1 -Environment prod -OddsApiKey "your-key" -SkipBuild
```

### Custom Location

```powershell
.\deploy.ps1 -Environment prod -OddsApiKey "your-key" -Location "eastus"
```

### Custom Image Tag

```powershell
.\deploy.ps1 -Environment prod -OddsApiKey "your-key" -ImageTag "v6.3.0"
```

## Manual Deployment Steps

If you prefer to deploy manually:

### 1. Create Resource Group

```powershell
az group create --name ncaam-prod-rg --location centralus
```

### 2. Deploy Bicep Template

```powershell
az deployment group create `
    --resource-group ncaam-prod-rg `
    --template-file main.bicep `
    --parameters `
        environment=prod `
        postgresPassword="$(openssl rand -base64 24)" `
        redisPassword="$(openssl rand -base64 24)" `
        oddsApiKey="YOUR_ACTUAL_KEY"  # Replace with real key - sets env var THE_ODDS_API_KEY
```

### 3. Build and Push Image

```powershell
# Login to ACR
az acr login --name ncaamprodacr

# Build
docker build -t ncaamprodacr.azurecr.io/ncaam-prediction:v6.3.0 `
    -f services/prediction-service-python/Dockerfile.hardened .

# Push
docker push ncaamprodacr.azurecr.io/ncaam-prediction:v6.3.0
```

### 4. Update Container App

```powershell
az containerapp update `
    --name ncaam-prod-prediction `
    --resource-group ncaam-prod-rg `
    --image ncaamprodacr.azurecr.io/ncaam-prediction:v6.3.0
```

## Files

| File | Purpose |
|------|---------|
| `main.bicep` | Azure infrastructure as code |
| `deploy.ps1` | One-click deployment script |
| `parameters.prod.json` | Production environment parameters |
| `README.md` | This documentation |

## Azure Resources Created

| Resource | SKU | Monthly Cost (Est.) |
|----------|-----|---------------------|
| Container Registry | Basic | ~$5 |
| PostgreSQL Flexible | B1ms | ~$15 |
| Redis Cache | Basic C0 | ~$16 |
| Container Apps | Consumption | ~$0-10 (pay per use) |
| Log Analytics | Per GB | ~$2-5 |

**Total Estimated Cost: ~$40-50/month**

## Environment Variables

The container receives these environment variables:

| Variable | Source | Description |
|----------|--------|-------------|
| `DATABASE_URL` | Constructed | PostgreSQL connection string |
| `REDIS_URL` | Constructed | Redis connection string |
| `THE_ODDS_API_KEY` | **Environment Variable** | Odds API key (set via `-OddsApiKey` parameter) |
| `TEAMS_WEBHOOK_URL` | Optional | Microsoft Teams Incoming Webhook URL (only needed for `run_today.py --teams`) |
| `SPORT` | Config | Sport identifier (ncaam) |
| `TZ` | Config | Timezone (America/Chicago) |

**Note:** Code reads API key from environment variable `THE_ODDS_API_KEY`. The `-OddsApiKey` deployment parameter sets this environment variable.

## Secrets Management

Secrets are managed through Azure Container Apps secrets:

- `db-password` - PostgreSQL password (auto-generated)
- `redis-password` - Redis access key (from Azure)
- `odds-api-key` - The Odds API key (provided by you)
- `acr-password` - ACR pull credential (auto-generated)
- `teams-webhook-url` - (Optional) Teams webhook URL for posting picks

## Manual picks run (optional)

Azure does **not** auto-run daily picks. When you want picks, run them manually inside the container app:

1. Open a shell:

```powershell
az containerapp exec -n ncaam-prod-prediction -g greenbier-enterprise-rg --command sh
```

2. Inside the shell, run:

```bash
python /app/run_today.py --teams
```

### CSV output note

- **Local Docker**: CSV can be saved directly into your Teams channel "Shared Documents" by setting
  `PICKS_OUTPUT_HOST_DIR` to your OneDrive-synced channel folder (recommended).
- **Azure**: `run_today.py --teams` will still write a CSV to `/app/output`, but that filesystem is
  not your Teams SharePoint drive. Uploading to channel documents from Azure would require a separate
  Microsoft Graph/SharePoint integration.

## Scaling

Default configuration:
- **Min replicas:** 0 (scale to zero when idle)
- **Max replicas:** 1
- **Scale trigger:** HTTP requests (10 concurrent)

To modify scaling:

```powershell
az containerapp update `
    --name ncaam-prod-prediction `
    --resource-group ncaam-prod-rg `
    --min-replicas 1 `
    --max-replicas 3
```

## Monitoring

### View Logs

```powershell
az containerapp logs show -n ncaam-prod-prediction -g ncaam-prod-rg --follow
```

### View Metrics

```powershell
az monitor metrics list `
    --resource /subscriptions/{sub}/resourceGroups/ncaam-prod-rg/providers/Microsoft.App/containerApps/ncaam-prod-prediction `
    --metric "Requests"
```

### Azure Portal

Navigate to: **Azure Portal > Container Apps > ncaam-prod-prediction > Monitoring**

## Troubleshooting

### Container Won't Start

```powershell
# Check container app status
az containerapp show -n ncaam-prod-prediction -g ncaam-prod-rg --query "properties.runningStatus"

# View system logs
az containerapp logs show -n ncaam-prod-prediction -g ncaam-prod-rg --type system
```

### Database Connection Issues

```powershell
# Test PostgreSQL connectivity
az postgres flexible-server execute `
    -n ncaam-prod-postgres `
    -g ncaam-prod-rg `
    -u ncaam `
    -p "password" `
    -d ncaam `
    --querytext "SELECT 1"
```

### Image Pull Failures

```powershell
# Verify ACR credentials
az acr credential show --name ncaamprodacr

# Verify image exists
az acr repository show-tags --name ncaamprodacr --repository ncaam-prediction
```

## Cleanup

To delete all Azure resources:

```powershell
az group delete --name ncaam-prod-rg --yes --no-wait
```

**Warning:** This deletes ALL resources including the database. Data will be lost.

## Differences from Docker Compose

| Feature | Docker Compose | Azure Container Apps |
|---------|----------------|---------------------|
| Secrets | `/run/secrets/*` files | Environment variables |
| Database | TimescaleDB | Azure PostgreSQL |
| Redis | Container | Azure Cache for Redis |
| Networking | Docker networks | Azure VNet (optional) |
| Scaling | Manual | Automatic |
| SSL | Manual | Automatic |

## Next Steps

1. Set up custom domain (optional)
2. Configure alerts for monitoring
3. Set up CI/CD pipeline with GitHub Actions
4. Configure backup retention for PostgreSQL
