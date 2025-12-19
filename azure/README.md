# Azure Deployment Files

This directory contains Azure-specific deployment scripts and configurations.

## Files

- `deploy.sh` - Automated deployment script for Azure Container Apps
- `README.md` - This file

## Quick Start

### Prerequisites

1. **Azure CLI** installed and configured
   ```bash
   az login
   az account set --subscription "Your Subscription Name"
   ```

2. **Docker** installed and running

3. **Secrets files** in `../secrets/` directory:
   - `db_password.txt`
   - `redis_password.txt`
   - `odds_api_key.txt`

### Deployment

**Option 1: Automated Script (Linux/Mac/WSL)**
```bash
chmod +x azure/deploy.sh
./azure/deploy.sh
```

**Option 2: Manual Steps**
Follow the guide in `../docs/AZURE_MIGRATION.md`

## Configuration

Edit `deploy.sh` to customize:
- Resource group name
- Location/region
- Container names
- Resource sizes

## Post-Deployment

1. **Run Database Migrations:**
   ```bash
   # Connect to PostgreSQL container
   az containerapp exec \
     --name ncaam-postgres \
     --resource-group ncaam-v5-rg \
     --command "psql -U ncaam -d ncaam"
   
   # Run migrations
   \i /migrations/001_initial_schema.sql
   ```

2. **Test Prediction Service:**
   ```bash
   # Get service URL
   URL=$(az containerapp show \
     --name ncaam-prediction \
     --resource-group ncaam-v5-rg \
     --query properties.configuration.ingress.fqdn -o tsv)
   
   # Test health endpoint
   curl https://$URL/health
   ```

3. **Run Predictions:**
   ```bash
   # Execute run_today.py in container
   az containerapp exec \
     --name ncaam-prediction \
     --resource-group ncaam-v5-rg \
     --command "python /app/run_today.py"
   ```

## Cleanup

To remove all Azure resources:
```bash
az group delete --name ncaam-v5-rg --yes --no-wait
```

## Troubleshooting

### Container won't start
- Check logs: `az containerapp logs show --name ncaam-prediction --resource-group ncaam-v5-rg`
- Verify secrets in Key Vault
- Check container registry authentication

### Database connection issues
- Verify PostgreSQL container is running
- Check connection string format
- Ensure network connectivity between containers

### Image pull errors
- Verify ACR login: `az acr login --name ncaamv5registry`
- Check image exists: `az acr repository list --name ncaamv5registry`
- Verify registry credentials in container app

## Support

See `../docs/AZURE_MIGRATION.md` for detailed migration guide.
