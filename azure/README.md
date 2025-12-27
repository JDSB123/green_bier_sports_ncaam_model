# NCAAM v33.6.1 - Azure Deployment (Manual-Only)

## Overview

This directory contains everything needed to deploy the NCAAM prediction model to Azure Container Apps.

**Manual-only:** Azure runs the API, but **picks are generated only when you manually run** `run_today.py` (no cron/polling).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Azure Resource Group                              │
│                        (ncaam-stable-rg)                                │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │ Azure Container │  │ Azure Database  │  │ Azure Cache for Redis  │ │
│  │ Registry (ACR)  │  │ for PostgreSQL  │  │                        │ │
│  │                 │  │                 │  │                        │ │
│  │ ncaamstableacr  │  │ Flexible Server │  │ ncaam-stable-redis     │ │
│  └────────┬────────┘  │ ncaam-stable-pg │  └────────────────────────┘ │
│           │           └────────┬────────┘              │               │
│           │                    │                       │               │
│           ▼                    ▼                       ▼               │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                   Container Apps Environment                     │  │
│  │                   (ncaam-stable-env)                            │  │
│  │                                                                  │  │
│  │  ┌────────────────────────────────────────────────────────────┐ │  │
│  │  │            ncaam-stable-prediction                         │ │  │
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
.\deploy.ps1 -OddsApiKey "YOUR_ACTUAL_KEY"
```

This will:
- Create Azure Resource Group (`ncaam-stable-rg`)
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
curl https://ncaam-stable-prediction.azurecontainerapps.io/health

# View logs
az containerapp logs show -n ncaam-stable-prediction -g ncaam-stable-rg --follow
```

## Deployment Options

### Full Deployment (Default)

```powershell
.\deploy.ps1 -OddsApiKey "YOUR_ACTUAL_KEY"
# Deploys to: ncaam-stable-rg (centralus)
```

### Skip Infrastructure (Image Update Only)

```powershell
.\deploy.ps1 -OddsApiKey "your-key" -SkipInfra
```

### Skip Docker Build (Redeploy Existing Image)

```powershell
.\deploy.ps1 -OddsApiKey "your-key" -SkipBuild
```

### Custom Location

```powershell
.\deploy.ps1 -OddsApiKey "your-key" -Location "eastus"
```

### Custom Image Tag

```powershell
.\deploy.ps1 -OddsApiKey "your-key" -ImageTag "v33.6.1"
```

## Manual Deployment Steps

If you prefer to deploy manually:

### 1. Create Resource Group

```powershell
az group create --name ncaam-stable-rg --location centralus
```

### 2. Deploy Bicep Template

```powershell
az deployment group create `
    --resource-group ncaam-stable-rg `
    --template-file main.bicep `
    --parameters `
        environment=stable `
        postgresPassword="$(openssl rand -base64 24)" `
        redisPassword="$(openssl rand -base64 24)" `
        oddsApiKey="YOUR_ACTUAL_KEY"
```

### 3. Build and Push Image

```powershell
# Login to ACR
az acr login --name ncaamstableacr

# Build
docker build -t ncaamstableacr.azurecr.io/ncaam-prediction:v33.6.1 `
    -f services/prediction-service-python/Dockerfile .

# Push
docker push ncaamstableacr.azurecr.io/ncaam-prediction:v33.6.1
```

### 4. Update Container App

```powershell
az containerapp update `
    --name ncaam-stable-prediction `
    --resource-group ncaam-stable-rg `
    --image ncaamstableacr.azurecr.io/ncaam-prediction:v33.6.1
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
| `THE_ODDS_API_KEY` | Secret | Odds API key |
| `TEAMS_WEBHOOK_URL` | Optional | Microsoft Teams Incoming Webhook URL |
| `SPORT` | Config | Sport identifier (ncaam) |
| `TZ` | Config | Timezone (America/Chicago) |

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
az containerapp exec -n ncaam-stable-prediction -g ncaam-stable-rg --command sh
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
    --name ncaam-stable-prediction `
    --resource-group ncaam-stable-rg `
    --min-replicas 1 `
    --max-replicas 3
```

## Monitoring

### View Logs

```powershell
az containerapp logs show -n ncaam-stable-prediction -g ncaam-stable-rg --follow
```

### View Metrics

```powershell
az monitor metrics list `
    --resource /subscriptions/{sub}/resourceGroups/ncaam-stable-rg/providers/Microsoft.App/containerApps/ncaam-stable-prediction `
    --metric "Requests"
```

### Azure Portal

Navigate to: **Azure Portal > Container Apps > ncaam-stable-prediction > Monitoring**

## Troubleshooting

### Container Won't Start

```powershell
# Check container app status
az containerapp show -n ncaam-stable-prediction -g ncaam-stable-rg --query "properties.runningStatus"

# View system logs
az containerapp logs show -n ncaam-stable-prediction -g ncaam-stable-rg --type system
```

### Database Connection Issues

```powershell
# Test PostgreSQL connectivity
az postgres flexible-server execute `
    -n ncaam-stable-postgres `
    -g ncaam-stable-rg `
    -u ncaam `
    -p "password" `
    -d ncaam `
    --querytext "SELECT 1"
```

### Image Pull Failures

```powershell
# Verify ACR credentials
az acr credential show --name ncaamstableacr

# Verify image exists
az acr repository show-tags --name ncaamstableacr --repository ncaam-prediction
```

## Cleanup

To delete all Azure resources:

```powershell
az group delete --name ncaam-stable-rg --yes --no-wait
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

## CI/CD Pipeline

GitHub Actions automatically builds and pushes images on merge to `main`:

- **Workflow:** `.github/workflows/build-and-push.yml`
- **ACR:** `ncaamstableacr.azurecr.io`
- **Image:** `ncaam-prediction:{version}`

## Next Steps

1. Set up custom domain (optional)
2. Configure alerts for monitoring
3. Configure backup retention for PostgreSQL

## Custom domain (www.greenbiersportventures.com)

This repo can host a simple website via Azure Container Apps (`ncaam-stable-web`). To bind your domain:

1) Deploy infra (and the web app) first:

- `cd azure`
- `./deploy.ps1 -OddsApiKey "YOUR_KEY"`

2) Create DNS records at your registrar:

- **CNAME**: `www` → the web app FQDN (shown in Azure Portal or via `az containerapp show`)
- **TXT**: `asuid.www` → token returned by the hostname add step

3) Run the binding script:

- `./bind-domain.ps1 -Hostname www.greenbiersportventures.com`

It will print the required DNS records (first run) and then bind a managed TLS certificate once DNS is verified.
