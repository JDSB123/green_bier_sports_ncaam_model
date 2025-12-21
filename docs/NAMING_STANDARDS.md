# Naming Standards - NCAAM Model

**Date:** December 20, 2025  
**Purpose:** Standardize all resource naming across local, GitHub, and Azure

---

## 🎯 Standard Naming Convention

### Base Name
- **Standard:** `ncaam` (lowercase, no underscores)
- **Use for:** All resource prefixes, environment variables, database names

### Format Pattern
```
{baseName}-{environment}-{resourceType}
```

**Examples:**
- Resource Group: `ncaam-prod-rg`
- Container Registry: `ncaamprodacr` (no hyphens - Azure requirement)
- PostgreSQL: `ncaam-prod-postgres`
- Redis: `ncaam-prod-redis`
- Container App: `ncaam-prod-prediction`
- Container Environment: `ncaam-prod-env`

---

## 📁 Local Repository

### Docker Compose Project Name
- **Default:** `ncaam_v6_model`
- **Environment Variable:** `COMPOSE_PROJECT_NAME`
- **Format:** `{baseName}_v{version}_model`

**Container Names:**
- `{COMPOSE_PROJECT_NAME}_postgres`
- `{COMPOSE_PROJECT_NAME}_redis`
- `{COMPOSE_PROJECT_NAME}_prediction`
- `{COMPOSE_PROJECT_NAME}_ratings_sync`
- `{COMPOSE_PROJECT_NAME}_odds_full_once`
- `{COMPOSE_PROJECT_NAME}_odds_h1_once`

**Network Names:**
- `{COMPOSE_PROJECT_NAME}_backend`
- `{COMPOSE_PROJECT_NAME}_data`

**Volume Names:**
- `{COMPOSE_PROJECT_NAME}_postgres_data`

### Environment Variables
- **SPORT:** `ncaam` (lowercase)
- **DB_NAME:** `ncaam` (defaults to SPORT value)
- **DB_USER:** `ncaam` (defaults to SPORT value)

---

## 🌐 GitHub

### Branch Naming
- **Main branch:** `main`
- **Feature branches:** `feature/{description}` (no ncaam prefix needed)
- **Fix branches:** `fix/{description}`
- **Hotfix branches:** `hotfix/{description}`

**Deprecated/Removed:**
- ❌ `ncaam-codex-review` (merged, deleted)
- ❌ `ncaam_model_dev` (review before deletion)
- ❌ `ncaam_model_testing` (review before deletion)
- ❌ `temp-test` (deleted)

### Repository Name
- **Current:** `green_bier_sports_ncaam_model`
- **Standard:** Keep as-is (descriptive)

---

## ☁️ Azure Resources

### Resource Group
- **Format:** `{baseName}-{environment}-rg`
- **Examples:**
  - Production: `ncaam-prod-rg`
  - Development: `ncaam-dev-rg`
  - Staging: `ncaam-staging-rg`

### Container Registry (ACR)
- **Format:** `{baseName}{environment}acr` (no hyphens)
- **Examples:**
  - Production: `ncaamprodacr`
  - Development: `ncaamdevacr`

### PostgreSQL
- **Format:** `{baseName}-{environment}-postgres`
- **Database Name:** `ncaam`
- **Admin User:** `ncaam`
- **Examples:**
  - Production: `ncaam-prod-postgres`
  - Development: `ncaam-dev-postgres`

### Redis Cache
- **Format:** `{baseName}-{environment}-redis`
- **Examples:**
  - Production: `ncaam-prod-redis`
  - Development: `ncaam-dev-redis`

### Container Apps Environment
- **Format:** `{baseName}-{environment}-env`
- **Examples:**
  - Production: `ncaam-prod-env`
  - Development: `ncaam-dev-env`

### Container App
- **Format:** `{baseName}-{environment}-prediction`
- **Examples:**
  - Production: `ncaam-prod-prediction`
  - Development: `ncaam-dev-prediction`

### Log Analytics
- **Format:** `{baseName}-{environment}-logs`
- **Examples:**
  - Production: `ncaam-prod-logs`
  - Development: `ncaam-dev-logs`

### Container Image
- **Format:** `{acrName}.azurecr.io/ncaam-prediction:{tag}`
- **Examples:**
  - Production: `ncaamprodacr.azurecr.io/ncaam-prediction:v6.2.0`
  - Development: `ncaamdevacr.azurecr.io/ncaam-prediction:v6.2.0`

---

## 🔧 Configuration Files

### Azure Bicep (`azure/main.bicep`)
- **baseName parameter:** `'ncaam'` (default)
- **environment parameter:** `'prod'`, `'dev'`, `'staging'`

### Azure Deploy Script (`azure/deploy.ps1`)
- **$baseName:** `'ncaam'`
- **$resourcePrefix:** `"{baseName}-{environment}"`
- **$acrName:** `"{resourcePrefix}acr"` (hyphens removed)

### Docker Compose (`docker-compose.yml`)
- **COMPOSE_PROJECT_NAME:** `ncaam_v6_model` (default)
- **SPORT:** `ncaam` (default)
- **DB_NAME:** `ncaam` (default, uses SPORT)
- **DB_USER:** `ncaam` (default, uses SPORT)

---

## ✅ Validation Checklist

### Before Deployment
- [ ] All resource names follow `{baseName}-{environment}-{resourceType}` pattern
- [ ] ACR names have no hyphens (Azure requirement)
- [ ] Database name is `ncaam` (lowercase)
- [ ] Database user is `ncaam` (lowercase)
- [ ] SPORT environment variable is `ncaam` (lowercase)
- [ ] No underscores in Azure resource names (use hyphens)
- [ ] Container image repository is `ncaam-prediction`

### After Deployment
- [ ] Verify all resources created with correct names
- [ ] Check resource group contains all expected resources
- [ ] Verify container app can connect to database
- [ ] Confirm Redis connection works
- [ ] Test container app health endpoint

---

## 🚫 Anti-Patterns (Don't Use)

- ❌ `NCAAM` (uppercase)
- ❌ `ncaam_model` (underscore in Azure)
- ❌ `ncaamModel` (camelCase)
- ❌ `ncaam-prod-rg-prod` (redundant)
- ❌ `ncaamprod` (missing environment)
- ❌ `ncaam_prod_rg` (underscores instead of hyphens)

---

## 📝 Examples

### Full Production Deployment
```powershell
# Resource Group
ncaam-prod-rg

# Resources
ncaamprodacr (ACR)
ncaam-prod-postgres (PostgreSQL)
ncaam-prod-redis (Redis)
ncaam-prod-env (Container Apps Environment)
ncaam-prod-prediction (Container App)
ncaam-prod-logs (Log Analytics)

# Container Image
ncaamprodacr.azurecr.io/ncaam-prediction:v6.2.0
```

### Full Development Deployment
```powershell
# Resource Group
ncaam-dev-rg

# Resources
ncaamdevacr (ACR)
ncaam-dev-postgres (PostgreSQL)
ncaam-dev-redis (Redis)
ncaam-dev-env (Container Apps Environment)
ncaam-dev-prediction (Container App)
ncaam-dev-logs (Log Analytics)

# Container Image
ncaamdevacr.azurecr.io/ncaam-prediction:v6.2.0
```

---

## 🔄 Migration Guide

If you have existing resources with non-standard names:

1. **Document current names** in a migration plan
2. **Create new resources** with standard names
3. **Migrate data** from old to new resources
4. **Update configuration** to use new names
5. **Delete old resources** after verification
6. **Update documentation** with new names

---

**Last Updated:** December 20, 2025  
**Maintained By:** Development Team

