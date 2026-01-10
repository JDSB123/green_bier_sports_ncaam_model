# Naming Standards - NCAAM Model

**Date:** December 23, 2025  
**Purpose:** Standardize all resource naming across local, GitHub, and Azure

---

## 🎯 Standard Naming Convention

### Base Name
- **Standard:** `ncaam` (lowercase, no underscores)
- **Use for:** All resource prefixes, environment variables, database names

### Format Pattern
```
{baseName}-stable{resourceSuffix}-{resourceType}
```

**Default suffix:** `-gbsv` (set by `resourceNameSuffix` in `azure/deploy.ps1`)
**Suffix applies to:** ACR, PostgreSQL, Redis, and Key Vault (app/env/logs remain `ncaam-stable-*`)

**Examples:**
- Resource Group: `NCAAM-GBSV-MODEL-RG`
- Container Registry: `ncaamstablegbsvacr` (no hyphens - Azure requirement)
- PostgreSQL: `ncaam-stable-gbsv-postgres`
- Redis: `ncaam-stable-gbsv-redis`
- Key Vault: `ncaam-stablegbsvkv`
- Container App: `ncaam-stable-prediction`
- Web App: `ncaam-stable-web`
- Container Environment: `ncaam-stable-env`

---

## 📁 Local Repository

### Docker Compose Project Name
- **Default:** `ncaam_v33_model`
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

### Repository Name
- **Current:** `green_bier_sports_ncaam_model`
- **Standard:** Keep as-is (descriptive)

---

## ☁️ Azure Resources

### Production Resource Group
- **Name:** `NCAAM-GBSV-MODEL-RG`
- **Location:** `centralus`

### Container Registry (ACR)
- **Name:** `ncaamstablegbsvacr` (no hyphens - Azure requirement)
- **Login Server:** `ncaamstablegbsvacr.azurecr.io`

### PostgreSQL
- **Server:** `ncaam-stable-gbsv-postgres`
- **Database Name:** `ncaam`
- **Admin User:** `ncaam`

### Redis Cache
- **Name:** `ncaam-stable-gbsv-redis`

### Key Vault
- **Name:** `ncaam-stablegbsvkv`

### Container Apps Environment
- **Name:** `ncaam-stable-env`

### Container App
- **Name:** `ncaam-stable-prediction`

### Web App
- **Name:** `ncaam-stable-web`

### Log Analytics
- **Name:** `ncaam-stable-logs`

### Storage Account (v34.1.0)
- **Name:** `ncaamstablegbsvsa` (no hyphens - Azure requirement)
- **Container:** `picks-history`
- **Purpose:** Pick history blob storage snapshots
- **Note:** Created internally in `NCAAM-GBSV-MODEL-RG` by default. Can be overridden with external storage via `-StorageConnectionString` parameter.

### Container Image
- **Image:** `ncaamstablegbsvacr.azurecr.io/ncaam-prediction:{tag}`
- **Example:** `ncaamstablegbsvacr.azurecr.io/ncaam-prediction:v<VERSION>` (e.g., `v34.1.0`)

---

## 🔧 Configuration Files

### Azure Bicep (`azure/main.bicep`)
- **baseName parameter:** `'ncaam'` (default)
- **environment parameter:** `'stable'` (default)

### Azure Deploy Script (`azure/deploy.ps1`)
- **$baseName:** `'ncaam'`
- **$ResourceGroup:** `'NCAAM-GBSV-MODEL-RG'` (default)
- **$acrName:** `'ncaamstablegbsvacr'`

### Docker Compose (`docker-compose.yml`)
- **COMPOSE_PROJECT_NAME:** `ncaam_v33_model` (default)
- **SPORT:** `ncaam` (default)
- **DB_NAME:** `ncaam` (default, uses SPORT)
- **DB_USER:** `ncaam` (default, uses SPORT)
- **Image:** `ncaamstablegbsvacr.azurecr.io/ncaam-prediction:{version}`

### CI/CD (Optional)
This repository does not include a GitHub Actions workflow; deployments are performed via `azure/deploy.ps1`.

---

## ✅ Validation Checklist

### Before Deployment
- [ ] App resources follow `ncaam-stable-{resourceType}`; data resources use `ncaam-stable-gbsv-{resourceType}`
- [ ] ACR name is `ncaamstablegbsvacr` (no hyphens)
- [ ] Database name is `ncaam` (lowercase)
- [ ] Database user is `ncaam` (lowercase)
- [ ] SPORT environment variable is `ncaam` (lowercase)
- [ ] Container image repository is `ncaam-prediction`

### After Deployment
- [ ] Verify all resources created in `NCAAM-GBSV-MODEL-RG`
- [ ] Check container app can connect to database
- [ ] Confirm Redis connection works
- [ ] Verify storage account created (if using internal storage, v34.1.0+)
- [ ] Test container app health endpoint
- [ ] Verify resource tags are applied (CostCenter, Owner, Project, Version)

---

## 🚫 Anti-Patterns (Don't Use)

- ❌ `NCAAM` (uppercase)
- ❌ `ncaam_model` (underscore in Azure)
- ❌ `ncaamModel` (camelCase)
- ❌ `ncaam-prod-rg` (deprecated)
- ❌ `greenbier-enterprise-rg` (deprecated)
- ❌ `green-bier-ncaam` (deprecated)

---

## 📝 Production Deployment Example

```powershell
# Resource Group
NCAAM-GBSV-MODEL-RG

# Resources
ncaamstablegbsvacr (ACR)
ncaam-stable-gbsv-postgres (PostgreSQL)
ncaam-stable-gbsv-redis (Redis)
ncaamstablegbsvsa (Storage Account - v34.1.0)
ncaam-stablegbsvkv (Key Vault)
ncaam-stable-env (Container Apps Environment)
ncaam-stable-prediction (Container App)
ncaam-stable-web (Web App)
ncaam-stable-logs (Log Analytics)

# Container Image
ncaamstablegbsvacr.azurecr.io/ncaam-prediction:v<VERSION>
```

---

**Last Updated:** December 23, 2025  
**Maintained By:** Development Team
