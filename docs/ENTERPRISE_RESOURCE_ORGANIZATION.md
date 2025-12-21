# Enterprise Resource Organization - NCAAM Model

**Date:** December 21, 2025  
**Purpose:** Organize all NCAAM resources within Green Bier Enterprise resource group

---

## 🎯 Organization Strategy

All NCAAM model/app resources are consolidated within the **`greenbier-enterprise-rg`** resource group, organized using:

1. **Naming Convention:** All resources prefixed with `ncaam-{environment}-{resourceType}`
2. **Tags:** Resources tagged with `Model=ncaam` for easy filtering
3. **Location:** Primary deployment in `eastus` (matching enterprise RG location)

---

## 📋 Resource Structure

### Enterprise Resource Group
- **Name:** `greenbier-enterprise-rg`
- **Location:** `eastus`
- **Purpose:** Centralized resource group for all Green Bier models (NCAAM, NCAAF, NBA, etc.)

### NCAAM Resources (Organized by Tags)

All NCAAM resources are tagged with:
```json
{
  "Model": "ncaam",
  "Environment": "prod|dev|staging",
  "ManagedBy": "Bicep",
  "Application": "NCAAM-Prediction-Model"
}
```

### Resource Naming Pattern

```
ncaam-{environment}-{resourceType}
```

**Examples:**
- `ncaam-prod-postgres` - PostgreSQL server
- `ncaam-prod-redis` - Redis cache
- `ncaam-prod-env` - Container Apps Environment
- `ncaam-prod-prediction` - Prediction Container App
- `ncaam-prod-logs` - Log Analytics workspace
- `ncaamprodacr` - Container Registry (no hyphens per Azure requirement)

---

## 🚀 Deployment

### Enterprise Mode Deployment

Use the `-EnterpriseMode` flag to deploy to enterprise resource group:

```powershell
cd azure
.\deploy.ps1 -Environment prod -EnterpriseMode -OddsApiKey "YOUR_KEY"
```

This will:
- Deploy to `greenbier-enterprise-rg` (instead of `ncaam-prod-rg`)
- Use `eastus` location (matching enterprise RG)
- Apply tags to all resources for organization
- Keep resource names with `ncaam-` prefix for filtering

### Standard Mode Deployment

Without `-EnterpriseMode`, uses dedicated resource group:

```powershell
.\deploy.ps1 -Environment prod -OddsApiKey "YOUR_KEY"
# Deploys to: ncaam-prod-rg (centralus)
```

---

## 🔍 Filtering Resources by Model

### List All NCAAM Resources

```powershell
# Filter by tag
az resource list --resource-group greenbier-enterprise-rg `
    --query "[?tags.Model == 'ncaam'].{Name:name, Type:type, Environment:tags.Environment}" `
    --output table

# Filter by name prefix
az resource list --resource-group greenbier-enterprise-rg `
    --query "[?starts_with(name, 'ncaam-')].{Name:name, Type:type}" `
    --output table
```

### List Resources by Environment

```powershell
# Production NCAAM resources
az resource list --resource-group greenbier-enterprise-rg `
    --query "[?tags.Model == 'ncaam' && tags.Environment == 'prod'].{Name:name, Type:type}" `
    --output table
```

---

## 📊 Current Enterprise RG Structure

The `greenbier-enterprise-rg` contains:

### NCAAM Resources (Production)
- PostgreSQL: `ncaam-prod-postgres`
- Redis: `ncaam-prod-redis`
- Container Registry: `ncaamprodacr`
- Container Apps Environment: `ncaam-prod-env`
- Container Apps:
  - `ncaam-prod-prediction`
  - `ncaam-prod-ratings-sync`
  - `ncaam-prod-odds-ingestion`
- Log Analytics: `ncaam-prod-logs`

### Other Models
- NCAAF resources (prefixed with `ncaaf-`)
- NBA resources (prefixed with `nba-`)
- Shared resources (ACR, Key Vault, etc.)

---

## 🔄 Migration from Dedicated RG

### From `ncaam-prod-rg` to `greenbier-enterprise-rg`

**Option 1: Redeploy (Recommended)**
```powershell
# 1. Deploy to enterprise RG
cd azure
.\deploy.ps1 -Environment prod -EnterpriseMode -OddsApiKey "YOUR_KEY"

# 2. Migrate data from old resources (if needed)
# - Export PostgreSQL data
# - Import to new PostgreSQL

# 3. Update application connections to new resources
# 4. Verify everything works
# 5. Delete old ncaam-prod-rg (after verification)
```

**Option 2: Move Resources**
```powershell
# Note: Not all Azure resources support move operations
# PostgreSQL and Redis cannot be moved between regions/resource groups easily
# Recommended: Redeploy instead of moving
```

---

## 🏷️ Tagging Standards

### Required Tags
- **Model:** `ncaam` (identifies the model)
- **Environment:** `prod|dev|staging` (deployment environment)
- **ManagedBy:** `Bicep` (infrastructure tool)
- **Application:** `NCAAM-Prediction-Model` (application name)

### Optional Tags
- **CostCenter:** For cost allocation
- **Owner:** Team/owner information
- **Version:** Application version

### Apply Tags to Existing Resources

```powershell
# Tag existing resources
az resource tag --tags Model=ncaam Environment=prod `
    --ids $(az resource list --resource-group greenbier-enterprise-rg `
        --query "[?starts_with(name, 'ncaam-')].id" --output tsv)
```

---

## ✅ Benefits of Enterprise Organization

1. **Centralized Management:** All models in one resource group
2. **Cost Visibility:** Easy to filter costs by model tag
3. **Resource Sharing:** Shared ACR, Key Vault, etc.
4. **Consistent Naming:** Clear identification of resources
5. **Easy Filtering:** Tag-based organization

---

## 📝 Quick Reference

### Deploy NCAAM to Enterprise RG
```powershell
.\azure\deploy.ps1 -Environment prod -EnterpriseMode -OddsApiKey "KEY"
```

### List NCAAM Resources
```powershell
az resource list --resource-group greenbier-enterprise-rg `
    --query "[?tags.Model == 'ncaam'].name" --output table
```

### Filter by Environment
```powershell
az resource list --resource-group greenbier-enterprise-rg `
    --query "[?tags.Model == 'ncaam' && tags.Environment == 'prod'].name" `
    --output table
```

---

**Last Updated:** December 21, 2025  
**Maintained By:** Development Team

