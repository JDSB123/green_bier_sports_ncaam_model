# Azure Resource Cleanup Guide

**Date:** December 21, 2025  
**Purpose:** Identify and clean up duplicate/legacy Azure resource groups

---

## 🔍 Current Azure Resource Groups

### Expected Resource Group (Active)
- **Name:** `ncaam-prod-rg`
- **Location:** `centralus`
- **Status:** ✅ Active production deployment
- **Used By:** Current deployment script (`azure/deploy.ps1`)

### Legacy Resource Group (Potential Cleanup)
- **Name:** `green-bier-ncaam`
- **Location:** `eastus`
- **Status:** ❓ Unknown - may be old/legacy deployment
- **Used By:** ❌ Not referenced in current deployment scripts

---

## 📋 What Should Exist

According to `azure/deploy.ps1`, the standard resource group is:
- **Format:** `{baseName}-{environment}-rg`
- **Example:** `ncaam-prod-rg` (for production)
- **Default Location:** `centralus`

---

## 🧹 Cleanup Decision

### Before Deleting `green-bier-ncaam`:

**Check what's in it:**
```powershell
# List all resources in the legacy group
az resource list --resource-group green-bier-ncaam --output table

# Check container apps
az containerapp list --resource-group green-bier-ncaam --output table

# Check databases
az postgres flexible-server list --resource-group green-bier-ncaam --output table

# Check Redis
az redis list --resource-group green-bier-ncaam --output table
```

### If `green-bier-ncaam` is Empty/Unused:

**Delete it:**
```powershell
# WARNING: This will delete ALL resources in the group!
az group delete --name green-bier-ncaam --yes --no-wait
```

### If `green-bier-ncaam` Has Active Resources:

**Option 1: Migrate resources** (if needed)
- Move resources to `ncaam-prod-rg` if they're still needed

**Option 2: Keep both** (if you need different environments)
- Rename to follow naming convention: `ncaam-{env}-rg`
- Use different locations for different purposes

---

## ✅ Standard Resource Group Naming

Going forward, use this naming convention:
- **Production:** `ncaam-prod-rg`
- **Staging:** `ncaam-staging-rg`
- **Development:** `ncaam-dev-rg`

---

## 🎯 Recommendation

1. **Check resources** in `green-bier-ncaam`
2. **If empty/unused:** Delete it
3. **If has resources:** Decide if they're needed
   - If needed: Keep or migrate to `ncaam-prod-rg`
   - If not needed: Delete the resource group

---

**Remember:** Only `ncaam-prod-rg` should be used for production deployments going forward.

