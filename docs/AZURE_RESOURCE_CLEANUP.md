# Azure Resource Cleanup - COMPLETED

**Date:** December 23, 2025  
**Status:** ✅ CLEANUP COMPLETE

---

## 🎯 Production Standard

All NCAAM resources are now consolidated in a single resource group:

- **Resource Group:** `NCAAM-GBSV-MODEL-RG`
- **Location:** `centralus`
- **Container Registry:** `ncaamstablegbsvacr.azurecr.io`

---

## ✅ Cleanup Completed

The following legacy/duplicate resource groups have been cleaned up:

| Resource Group | Status | Notes |
|----------------|--------|-------|
| `ncaam-prod-rg` | ❌ Deleted | Replaced by NCAAM-GBSV-MODEL-RG |
| `green-bier-ncaam` | ❌ Deleted | Legacy deployment |
| `greenbier-enterprise-rg` | ❌ Deleted | Enterprise mode deprecated |

---

## 📋 Current Production Resources

All resources in `NCAAM-GBSV-MODEL-RG`:

```
NCAAM-GBSV-MODEL-RG/
├── ncaamstablegbsvacr           # Container Registry
├── ncaam-stable-postgres    # PostgreSQL Flexible Server
├── ncaam-stable-redis       # Azure Cache for Redis
├── ncaam-stable-env         # Container Apps Environment
├── ncaam-stable-prediction  # Container App
└── ncaam-stable-logs        # Log Analytics Workspace
```

---

## 🚀 Deployment

Use the standard deployment script:

```powershell
cd azure
.\deploy.ps1 -OddsApiKey "YOUR_KEY"
```

Default values:
- **Resource Group:** `ncaam-stable-rg`
- **Location:** `centralus`
- **Environment:** `prod`

---

## 📝 Naming Convention

Going forward, use this standard:

| Resource Type | Name |
|---------------|------|
| Resource Group | `ncaam-stable-rg` |
| Container Registry | `ncaamstableacr` |
| PostgreSQL | `ncaam-stable-postgres` |
| Redis | `ncaam-stable-redis` |
| Container Apps Env | `ncaam-stable-env` |
| Container App | `ncaam-stable-prediction` |
| Log Analytics | `ncaam-stable-logs` |

---

## ✅ CI/CD Pipeline

GitHub Actions automatically builds and pushes to `ncaamstableacr.azurecr.io`:

- **Trigger:** Push to `main` branch
- **Image:** `ncaamstableacr.azurecr.io/ncaam-prediction:{version}`
- **Latest Version:** See `docker-compose.yml` line 134

---

**Cleanup Completed:** December 23, 2025  
**Maintained By:** Development Team
