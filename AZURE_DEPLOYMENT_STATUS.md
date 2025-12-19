# Azure Deployment Status

**Date:** December 19, 2025  
**Status:** ✅ DEPLOYED TO AZURE

---

## 🎯 Deployment Summary

**All containers successfully deployed to Azure Container Apps!**

---

## 📊 Azure Resources Created

### Resource Group
- **Name:** `ncaam-v5-rg`
- **Location:** `eastus`
- **Subscription:** Azure Green Bier Capital

### Container Registry
- **Name:** `ncaamv5registry`
- **URL:** `ncaamv5registry.azurecr.io`
- **Image:** `ncaam-prediction:v5.1` (pushed successfully)

### Key Vault
- **Name:** `ncaam-v5-secrets`
- **Secrets Stored:**
  - `db-password` ✅
  - `redis-password` ✅
  - `odds-api-key` ✅

### Container Apps Environment
- **Name:** `ncaam-v5-env`
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

### Prediction Service
- **URL:** `https://ncaam-prediction.ashycliff-f98889a8.eastus.azurecontainerapps.io`
- **Health Endpoint:** `https://ncaam-prediction.ashycliff-f98889a8.eastus.azurecontainerapps.io/health`
- **Port:** 8082 (internal)

---

## 📋 Next Steps

### 1. Run Database Migrations

**Option A: Via Azure Portal**
- Navigate to Container Apps → `ncaam-postgres`
- Use Console/Exec to run migrations

**Option B: Via Azure CLI**
```bash
# Connect to PostgreSQL container
az containerapp exec \
  --name ncaam-postgres \
  --resource-group ncaam-v5-rg \
  --command "psql -U ncaam -d ncaam"

# Then run migrations manually
```

**Option C: Copy migrations and run**
```bash
# Copy migration files to container
# Then execute via exec
```

### 2. Test Health Endpoint

```bash
curl https://ncaam-prediction.ashycliff-f98889a8.eastus.azurecontainerapps.io/health
```

### 3. Execute Predictions

```bash
# Execute run_today.py in container
az containerapp exec \
  --name ncaam-prediction \
  --resource-group ncaam-v5-rg \
  --command "python /app/run_today.py"
```

---

## 🔍 Troubleshooting

### Check Container Logs
```bash
# PostgreSQL logs
az containerapp logs show \
  --name ncaam-postgres \
  --resource-group ncaam-v5-rg \
  --follow

# Redis logs
az containerapp logs show \
  --name ncaam-redis \
  --resource-group ncaam-v5-rg \
  --follow

# Prediction service logs
az containerapp logs show \
  --name ncaam-prediction \
  --resource-group ncaam-v5-rg \
  --follow
```

### Check Container Status
```bash
az containerapp list \
  --resource-group ncaam-v5-rg \
  --query "[].{Name:name, Status:properties.runningStatus}" \
  -o table
```

### Update Container Environment Variables
```bash
az containerapp update \
  --name ncaam-prediction \
  --resource-group ncaam-v5-rg \
  --set-env-vars "KEY=value"
```

---

## 🔐 Key Vault Access

**Note:** Key Vault uses RBAC authorization. If you need to access secrets:

```bash
# Grant yourself permissions (if needed)
az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee $(az ad signed-in-user show --query id -o tsv) \
  --scope "/subscriptions/3a1a4a94-45a5-4f7c-8ada-97978221052c/resourceGroups/ncaam-v5-rg/providers/Microsoft.KeyVault/vaults/ncaam-v5-secrets"
```

---

## 📊 Resource Costs

**Estimated Monthly Cost:**
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
  --resource-group ncaam-v5-rg \
  --query "properties.configuration.ingress.fqdn" \
  -o tsv
```

### View Logs
```bash
az containerapp logs show \
  --name ncaam-prediction \
  --resource-group ncaam-v5-rg \
  --follow
```

### Restart Container
```bash
az containerapp revision restart \
  --name ncaam-prediction \
  --resource-group ncaam-v5-rg
```

---

**Last Updated:** December 19, 2025  
**Deployment Status:** ✅ COMPLETE
