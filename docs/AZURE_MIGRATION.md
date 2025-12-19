# Azure Migration Guide - NCAA Basketball v5.1

**Date:** December 19, 2025  
**Target:** Azure Container Instances / Azure Container Apps

---

## 🎯 Migration Overview

This guide covers migrating the self-contained NCAA prediction system to Azure cloud infrastructure.

### Architecture Options

1. **Azure Container Instances (ACI)** - Simple, serverless containers
2. **Azure Container Apps** - Managed Kubernetes-like experience
3. **Azure Container Instances + Azure Database for PostgreSQL** - Full managed stack

**Recommended:** Azure Container Apps (best balance of features and simplicity)

---

## 📋 Prerequisites

### Azure Resources Required

- [ ] Azure Subscription
- [ ] Azure Container Registry (ACR)
- [ ] Azure Key Vault (for secrets)
- [ ] Azure Database for PostgreSQL (or use existing PostgreSQL)
- [ ] Azure Container Apps environment (or ACI resource group)

### Tools Required

- [ ] Azure CLI (`az`)
- [ ] Docker Desktop (for building images)
- [ ] Git (for cloning repository)

---

## 🔐 Secrets Management - Azure Key Vault

### Current Setup (Local)
```
secrets/
├── db_password.txt
├── redis_password.txt
└── odds_api_key.txt
```

### Azure Setup (Key Vault)

**Create Key Vault:**
```bash
az keyvault create \
  --name ncaam-v5-secrets \
  --resource-group ncaam-v5-rg \
  --location eastus
```

**Store Secrets:**
```bash
# Database password
az keyvault secret set \
  --vault-name ncaam-v5-secrets \
  --name db-password \
  --value "$(cat secrets/db_password.txt)"

# Redis password
az keyvault secret set \
  --vault-name ncaam-v5-secrets \
  --name redis-password \
  --value "$(cat secrets/redis_password.txt)"

# Odds API key
az keyvault secret set \
  --vault-name ncaam-v5-secrets \
  --name odds-api-key \
  --value "$(cat secrets/odds_api_key.txt)"
```

**Access from Containers:**
- Use Azure Key Vault CSI driver (Container Apps)
- Or mount secrets as environment variables
- Or use Managed Identity for Key Vault access

---

## 🐳 Container Registry Setup

### Build and Push Images

**1. Login to ACR:**
```bash
az acr login --name ncaamv5registry
```

**2. Build and Push:**
```bash
# Build prediction service (includes Go/Rust binaries)
docker build \
  -f services/prediction-service-python/Dockerfile.hardened \
  -t ncaamv5registry.azurecr.io/ncaam-prediction:v5.1 \
  .

# Push to ACR
docker push ncaamv5registry.azurecr.io/ncaam-prediction:v5.1
```

**3. Tag and Push Base Images (if needed):**
```bash
# PostgreSQL (use Azure Database for PostgreSQL instead)
# Redis (use Azure Cache for Redis instead)
```

---

## 🗄️ Database Options

### Option 1: Azure Database for PostgreSQL (Recommended)

**Create Database:**
```bash
az postgres flexible-server create \
  --resource-group ncaam-v5-rg \
  --name ncaam-db \
  --location eastus \
  --admin-user ncaam \
  --admin-password "$(az keyvault secret show --vault-name ncaam-v5-secrets --name db-password --query value -o tsv)" \
  --sku-name Standard_B2s \
  --tier Burstable \
  --version 15 \
  --storage-size 32
```

**Enable TimescaleDB Extension:**
```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

**Run Migrations:**
```bash
# Connect and run migrations
psql -h ncaam-db.postgres.database.azure.com -U ncaam -d postgres -f database/migrations/001_initial_schema.sql
# ... (run all migrations in order)
```

### Option 2: Azure Container Instances (PostgreSQL)

Use the existing `docker-compose.yml` PostgreSQL container in ACI.

---

## 🔴 Redis Options

### Option 1: Azure Cache for Redis (Recommended)

**Create Redis Cache:**
```bash
az redis create \
  --resource-group ncaam-v5-rg \
  --name ncaam-redis \
  --location eastus \
  --sku Basic \
  --vm-size c0
```

**Get Connection String:**
```bash
az redis list-keys \
  --resource-group ncaam-v5-rg \
  --name ncaam-redis
```

### Option 2: Azure Container Instances (Redis)

Use the existing `docker-compose.yml` Redis container in ACI.

---

## 🚀 Deployment Options

### Option A: Azure Container Apps (Recommended)

**1. Create Container Apps Environment:**
```bash
az containerapp env create \
  --name ncaam-v5-env \
  --resource-group ncaam-v5-rg \
  --location eastus
```

**2. Create PostgreSQL Container App:**
```bash
az containerapp create \
  --name ncaam-postgres \
  --resource-group ncaam-v5-rg \
  --environment ncaam-v5-env \
  --image timescale/timescaledb:latest-pg15 \
  --cpu 1.0 \
  --memory 2.0Gi \
  --min-replicas 1 \
  --max-replicas 1 \
  --env-vars \
    POSTGRES_DB=ncaam \
    POSTGRES_USER=ncaam \
    POSTGRES_PASSWORD=secretref:db-password
```

**3. Create Redis Container App:**
```bash
az containerapp create \
  --name ncaam-redis \
  --resource-group ncaam-v5-rg \
  --environment ncaam-v5-env \
  --image redis:7-alpine \
  --cpu 0.5 \
  --memory 0.5Gi \
  --min-replicas 1 \
  --max-replicas 1 \
  --env-vars \
    REDIS_PASSWORD=secretref:redis-password
```

**4. Create Prediction Service Container App:**
```bash
az containerapp create \
  --name ncaam-prediction \
  --resource-group ncaam-v5-rg \
  --environment ncaam-v5-env \
  --image ncaamv5registry.azurecr.io/ncaam-prediction:v5.1 \
  --cpu 1.0 \
  --memory 1.0Gi \
  --min-replicas 1 \
  --max-replicas 1 \
  --registry-server ncaamv5registry.azurecr.io \
  --env-vars \
    DATABASE_URL=postgresql://ncaam:secretref:db-password@ncaam-postgres:5432/ncaam \
    REDIS_URL=redis://:secretref:redis-password@ncaam-redis:6379 \
    THE_ODDS_API_KEY=secretref:odds-api-key \
    MODEL__HOME_COURT_ADVANTAGE_SPREAD=3.0 \
    MODEL__HOME_COURT_ADVANTAGE_TOTAL=4.5 \
  --ingress external \
  --target-port 8082
```

### Option B: Azure Container Instances

**1. Create Resource Group:**
```bash
az group create --name ncaam-v5-rg --location eastus
```

**2. Deploy with docker-compose (Azure Container Instances):**
```bash
# Use az container create for each service
# Or use Azure Container Instances with docker-compose (limited support)
```

**3. Manual Container Creation:**
```bash
# PostgreSQL
az container create \
  --resource-group ncaam-v5-rg \
  --name ncaam-postgres \
  --image timescale/timescaledb:latest-pg15 \
  --cpu 2 \
  --memory 2 \
  --environment-variables \
    POSTGRES_DB=ncaam \
    POSTGRES_USER=ncaam \
    POSTGRES_PASSWORD="$DB_PASSWORD" \
  --ports 5432

# Redis
az container create \
  --resource-group ncaam-v5-rg \
  --name ncaam-redis \
  --image redis:7-alpine \
  --cpu 0.5 \
  --memory 0.5 \
  --command-line "redis-server --requirepass $REDIS_PASSWORD"

# Prediction Service
az container create \
  --resource-group ncaam-v5-rg \
  --name ncaam-prediction \
  --image ncaamv5registry.azurecr.io/ncaam-prediction:v5.1 \
  --cpu 1 \
  --memory 1 \
  --environment-variables \
    DATABASE_URL="postgresql://ncaam:$DB_PASSWORD@ncaam-postgres:5432/ncaam" \
    REDIS_URL="redis://:$REDIS_PASSWORD@ncaam-redis:6379" \
    THE_ODDS_API_KEY="$ODDS_API_KEY" \
  --registry-login-server ncaamv5registry.azurecr.io \
  --registry-username ncaamv5registry \
  --registry-password "$ACR_PASSWORD" \
  --ports 8082
```

---

## 🔧 Code Modifications for Azure

### Update Secret Reading (Optional)

**Current (Docker Secrets):**
```python
DB_PASSWORD = _read_secret_file("/run/secrets/db_password", "db_password")
```

**Azure (Environment Variables):**
```python
# Fallback to env vars if Docker secrets not available
DB_PASSWORD = os.getenv("DB_PASSWORD") or _read_secret_file("/run/secrets/db_password", "db_password")
```

**Or use Azure Key Vault SDK:**
```python
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://ncaam-v5-secrets.vault.azure.net/", credential=credential)
DB_PASSWORD = client.get_secret("db-password").value
```

### Update Connection Strings

**PostgreSQL:**
```python
# Local: postgresql://ncaam:password@postgres:5432/ncaam
# Azure: postgresql://ncaam:password@ncaam-db.postgres.database.azure.com:5432/ncaam
```

**Redis:**
```python
# Local: redis://:password@redis:6379
# Azure: redis://:password@ncaam-redis.redis.cache.windows.net:6380
```

---

## 📊 Networking

### Container Apps Networking

- Containers in same environment can communicate via service names
- External ingress available for prediction service API
- Private endpoints for database/Redis (recommended)

### Container Instances Networking

- Use Azure Virtual Network for container communication
- Or use public IPs with firewall rules
- Consider Azure Application Gateway for load balancing

---

## 🔒 Security Best Practices

1. **Use Managed Identity** for Key Vault access (no secrets in code)
2. **Private Endpoints** for database and Redis
3. **Network Security Groups** to restrict access
4. **Azure Firewall** for outbound traffic control
5. **Azure Monitor** for logging and alerting
6. **Azure Security Center** for threat detection

---

## 📈 Monitoring & Logging

### Azure Monitor

**Enable Container Insights:**
```bash
az monitor log-analytics workspace create \
  --resource-group ncaam-v5-rg \
  --workspace-name ncaam-logs
```

**Configure Logging:**
- Application Insights for application logs
- Container Insights for container metrics
- Key Vault logging for secret access

### Custom Metrics

- Prediction execution time
- API request counts
- Database query performance
- Odds sync success rate

---

## 💰 Cost Estimation

### Azure Container Apps (Monthly)

- **Environment:** ~$0.10/hour = ~$73/month
- **PostgreSQL Container:** ~$15/month (Basic tier)
- **Redis Container:** ~$10/month (Basic tier)
- **Prediction Service:** ~$20/month (1 CPU, 1GB RAM)
- **Total:** ~$118/month

### Azure Database for PostgreSQL + Azure Cache for Redis

- **PostgreSQL Flexible Server (B2s):** ~$30/month
- **Azure Cache for Redis (Basic C0):** ~$15/month
- **Container Apps Environment:** ~$73/month
- **Prediction Service:** ~$20/month
- **Total:** ~$138/month

---

## 🚀 Deployment Checklist

- [ ] Create Azure Resource Group
- [ ] Create Azure Container Registry
- [ ] Create Azure Key Vault and store secrets
- [ ] Build and push container images to ACR
- [ ] Create Azure Database for PostgreSQL (or use container)
- [ ] Create Azure Cache for Redis (or use container)
- [ ] Run database migrations
- [ ] Create Container Apps environment
- [ ] Deploy PostgreSQL container (if not using managed DB)
- [ ] Deploy Redis container (if not using managed cache)
- [ ] Deploy prediction service container
- [ ] Configure networking and security
- [ ] Set up monitoring and logging
- [ ] Test end-to-end prediction flow
- [ ] Configure backup and disaster recovery

---

## 📚 Additional Resources

- [Azure Container Apps Documentation](https://docs.microsoft.com/azure/container-apps/)
- [Azure Container Instances Documentation](https://docs.microsoft.com/azure/container-instances/)
- [Azure Key Vault Documentation](https://docs.microsoft.com/azure/key-vault/)
- [Azure Database for PostgreSQL Documentation](https://docs.microsoft.com/azure/postgresql/)

---

## 🏁 Next Steps

1. **Review this guide** and choose deployment option
2. **Set up Azure resources** following the checklist
3. **Test deployment** in a development environment
4. **Migrate data** from local database (if applicable)
5. **Update DNS/endpoints** for production access
6. **Monitor and optimize** based on usage patterns

---

**Last Updated:** December 19, 2025  
**Version:** v5.1 FINAL
