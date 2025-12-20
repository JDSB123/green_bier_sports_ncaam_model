# Azure Deployment Status

**Date:** December 19, 2025  
**Status:** ✅ DEPLOYED TO AZURE (Enterprise)

---

## 🎯 Deployment Summary

All NCAAM containers are deployed to the enterprise Azure Container Apps environment.

---

## 📊 Azure Resources Created

### Resource Group
- **Name:** `greenbier-enterprise-rg`
- **Location:** `eastus`
- **Subscription:** Azure Green Bier Capital

### Container Registry
- **Name:** `greenbieracr`
- **URL:** `greenbieracr.azurecr.io`
- **Image:** `ncaam-prediction:v6.0`

### Key Vault
- **Name:** `greenbier-keyvault`
- **Secrets Stored:**
  - `db-password` ✅
  - `redis-password` ✅
  - `odds-api-key` ✅

### Container Apps Environment
- **Name:** `greenbier-ncaam-env`
- **Status:** Running

---

## 🐳 Container Apps Status

| Container | Status | CPU | Memory |
|-----------|--------|-----|--------|
| `ncaam-postgres` | ✅ Running | 1.0 | 2.0Gi |
| `ncaam-redis` | ✅ Running | 0.5 | 1.0Gi |
| `ncaam-prediction` | ✅ Running | 1.0 | 2.0Gi |

---

## 🌐 Access URLs

```bash
az containerapp show \
  --name ncaam-prediction \
  --resource-group greenbier-enterprise-rg \
  --query properties.configuration.ingress.fqdn -o tsv
```

Use the returned FQDN for `https://<fqdn>/health`.

---

## 📋 Next Steps

### 1. Run Database Migrations

```bash
az containerapp exec \
  --name ncaam-postgres \
  --resource-group greenbier-enterprise-rg \
  --command "psql -U ncaam -d ncaam"

\i /migrations/001_initial_schema.sql
```

### 2. Test Health Endpoint

```bash
FQDN=$(az containerapp show \
  --name ncaam-prediction \
  --resource-group greenbier-enterprise-rg \
  --query properties.configuration.ingress.fqdn -o tsv)


```

### 3. Execute Predictions

```bash
az containerapp exec \
  --name ncaam-prediction \
  --resource-group greenbier-enterprise-rg \
  --command "python /app/run_today.py"
```

---

## 🔍 Troubleshooting

### Check Container Logs
```bash
az containerapp logs show --name ncaam-postgres --resource-group greenbier-enterprise-rg --follow
az containerapp logs show --name ncaam-redis --resource-group greenbier-enterprise-rg --follow
az containerapp logs show --name ncaam-prediction --resource-group greenbier-enterprise-rg --follow
```

### Check Container Status
```bash
az containerapp list \
  --resource-group greenbier-enterprise-rg \
  --query "[].{Name:name, Status:properties.runningStatus}" \
  -o table
```

### Update Container Environment Variables
```bash
az containerapp update \
  --name ncaam-prediction \
  --resource-group greenbier-enterprise-rg \
  --set-env-vars "KEY=value"
```

---

## 🔐 Key Vault Access

```bash
az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee $(az ad signed-in-user show --query id -o tsv) \
  --scope "/subscriptions/3a1a4a94-45a5-4f7c-8ada-97978221052c/resourceGroups/greenbier-enterprise-rg/providers/Microsoft.KeyVault/vaults/greenbier-keyvault"
```

---

## 📊 Resource Costs

- Container Apps Environment: ~$73/month
- PostgreSQL Container (1 CPU, 2GB): ~$15/month
- Redis Container (0.5 CPU, 1GB): ~$10/month
- Prediction Service (1 CPU, 2GB): ~$20/month
- Container Registry (Basic): ~$5/month
- Key Vault: ~$0.03/month
- **Total: ~$123/month**

---

## ✅ Deployment Checklist

- [x] Resource Group created
- [x] Container Registry created
- [x] Container image built and pushed
- [x] Key Vault created
- [x] Secrets stored in Key Vault
- [x] Container Apps Environment created
- [x] PostgreSQL container deployed
- [x] Redis container deployed
- [x] Prediction service container deployed
- [x] All containers running
- [ ] Database migrations run
- [ ] Health endpoint tested
- [ ] Predictions tested

---

## 🎯 Quick Commands

### Get Service URL
```bash
az containerapp show \
  --name ncaam-prediction \
  --resource-group greenbier-enterprise-rg \
  --query "properties.configuration.ingress.fqdn" \
  -o tsv
```

### View Logs
```bash
az containerapp logs show \
  --name ncaam-prediction \
  --resource-group greenbier-enterprise-rg \
  --follow
```

### Restart Container
```bash
az containerapp revision restart \
  --name ncaam-prediction \
  --resource-group greenbier-enterprise-rg
```

---

**Last Updated:** December 19, 2025  
**Deployment Status:** ✅ COMPLETE
  -o tsv
