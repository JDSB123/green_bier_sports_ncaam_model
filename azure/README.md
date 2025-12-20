# Azure Deployment Files

This directory contains Azure-specific deployment scripts and configurations for the enterprise NCAAM stack.

## Files

- `enterprise-deploy.sh` - Enterprise Azure Container Apps deployment (greenbier-enterprise-rg)
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

### Deployment (Enterprise)
```bash
chmod +x azure/enterprise-deploy.sh
./azure/enterprise-deploy.sh            # NCAAM (default)
# ./azure/enterprise-deploy.sh --sport nfl  # Future sports
```

Enterprise defaults:
- Resource group: `greenbier-enterprise-rg`
- Registry: `greenbieracr`
- Key Vault: `greenbier-keyvault`
- Container Apps env: `greenbier-ncaam-env`
- Services: `ncaam-postgres`, `ncaam-redis`, `ncaam-prediction`
- Image tag: `v6.0`

## Post-Deployment

1. **Run Database Migrations:**
   ```bash
   az containerapp exec \
     --name ncaam-postgres \
     --resource-group greenbier-enterprise-rg \
     --command "psql -U ncaam -d ncaam"

   # Run migrations inside psql
   \i /migrations/001_initial_schema.sql
   ```

2. **Test Prediction Service:**
   ```bash
   URL=$(az containerapp show \
     --name ncaam-prediction \
     --resource-group greenbier-enterprise-rg \
     --query properties.configuration.ingress.fqdn -o tsv)

   curl https://$URL/health
   ```

3. **Run Predictions:**
   ```bash
   az containerapp exec \
     --name ncaam-prediction \
     --resource-group greenbier-enterprise-rg \
     --command "python /app/run_today.py"
   ```

## Cleanup

To remove all Azure resources:
```bash
az group delete --name greenbier-enterprise-rg --yes --no-wait
```

## Troubleshooting

### Container won't start
- Check logs: `az containerapp logs show --name ncaam-prediction --resource-group greenbier-enterprise-rg`
- Verify secrets in Key Vault
- Check container registry authentication (greenbieracr)

### Database connection issues
- Verify PostgreSQL container is running
- Check connection string format
- Ensure network connectivity between containers

### Image pull errors
- Verify ACR login: `az acr login --name greenbieracr`
- Check image exists: `az acr repository list --name greenbieracr`
- Verify registry credentials in container app

## Support

See `../docs/AZURE_MIGRATION.md` for the detailed enterprise guide.
