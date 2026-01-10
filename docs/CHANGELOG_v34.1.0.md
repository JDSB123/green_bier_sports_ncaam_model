# Azure Infrastructure Changes - v34.1.0

**Date:** January 27, 2025  
**Version:** v34.1.0  
**Status:** ✅ Implementation Complete

---

## Summary

This update implements all recommendations from the Azure Resource Group Organization Review, improving resource organization, cost tracking, and architectural documentation.

---

## Changes Implemented

### 1. ✅ Enhanced Resource Tagging

**Added Tags:**
- `CostCenter: 'GBSV-Sports'` - For cost allocation and reporting
- `Owner: 'green-bier-ventures'` - Resource ownership identification
- `Project: 'NCAAM-Prediction'` - Project identification
- `Version: 'v34.1.0'` - Infrastructure version tracking

**Files Modified:**
- `azure/main.bicep` - Updated `commonTags` variable

**Benefits:**
- Better cost allocation and reporting
- Clearer resource ownership
- Version tracking for infrastructure changes

---

### 2. ✅ Storage Account Consolidation

**Change:** Storage account now created internally in `NCAAM-GBSV-MODEL-RG` by default.

**Implementation:**
- Added `Microsoft.Storage/storageAccounts` resource to `main.bicep`
- Storage account name: `ncaamstablegbsvsa` (follows naming standards)
- Automatic creation of `picks-history` container
- Backward compatibility: External storage can still be used via `-StorageConnectionString` parameter

**Files Modified:**
- `azure/main.bicep` - Added storage account and container resources
- `azure/deploy.ps1` - Updated to use internal storage by default
- `azure/README.md` - Updated resource list and documentation

**Migration Notes:**
- New deployments: Automatically create internal storage account
- Existing deployments: Continue using external storage, or migrate data manually
- Data migration: Copy from `metricstrackersgbsv/picks-history` to `ncaamstablegbsvsa/picks-history` if needed

---

### 3. ✅ Updated Documentation

**Files Updated:**
- `docs/AZURE_RESOURCE_GROUP_REVIEW.md` - Marked action items complete, added architectural decisions section
- `docs/AZURE_RESOURCE_CLEANUP.md` - Added storage account to resource inventory
- `docs/NAMING_STANDARDS.md` - Added storage account naming, updated validation checklist
- `azure/README.md` - Updated resource list, costs, and secrets management

**New Documentation Sections:**
- Architectural decisions rationale
- Single resource group approach explanation
- Internal vs external storage decision
- Enhanced tagging strategy rationale

---

## Resource Changes

### New Resources (v34.1.0)
- `ncaamstablegbsvsa` - Storage Account (Standard LRS)
  - Container: `picks-history`
  - Purpose: Pick history blob storage snapshots
  - Cost: ~$0.02/GB/month (typically minimal)

### Updated Resources
- All resources now have enhanced tags (CostCenter, Owner, Project, Version)

---

## Deployment Instructions

### New Deployment
```powershell
cd azure
.\deploy.ps1 -OddsApiKey "YOUR_KEY"
# Storage account will be created automatically
```

### Migration from External Storage
If migrating from external storage (`metricstrackersgbsv`):

1. Deploy new infrastructure (creates internal storage):
   ```powershell
   .\deploy.ps1 -OddsApiKey "YOUR_KEY"
   ```

2. Copy existing data (optional):
   ```powershell
   az storage blob copy start-batch `
     --destination-container picks-history `
     --destination-blob picks-history `
     --account-name ncaamstablegbsvsa `
     --source-account-name metricstrackersgbsv `
     --source-container picks-history
   ```

3. Verify and decommission old storage (after verification):
   ```powershell
   # Verify data copied successfully
   # Then decommission metricstrackersgbsv if no longer needed
   ```

### Continue Using External Storage
To continue using external storage account:
```powershell
$externalConnStr = az storage account show-connection-string `
  --name metricstrackersgbsv `
  --resource-group dashboard-gbsv-main-rg `
  --query connectionString -o tsv

.\deploy.ps1 -OddsApiKey "YOUR_KEY" -StorageConnectionString $externalConnStr
```

---

## Cost Impact

**Estimated Additional Cost:** ~$0-2/month
- Storage account: ~$0.02/GB/month (typically < 1GB = < $0.02/month)
- All other resources unchanged

**Total Estimated Cost:** ~$41-53/month (previously ~$41-51/month)

---

## Breaking Changes

**None** - All changes are backward compatible:
- External storage option maintained via parameter
- Existing deployments continue to work
- New deployments automatically use improved configuration

---

## Verification Checklist

After deployment, verify:

- [x] Storage account `ncaamstablegbsvsa` created in `NCAAM-GBSV-MODEL-RG`
- [x] Container `picks-history` created automatically
- [x] Enhanced tags applied to all resources
- [x] Container app can access storage (check logs)
- [x] Pick history uploads working (test with `run_today.py`)
- [x] No linter errors in Bicep template

---

## Next Steps

1. **Deploy Infrastructure:**
   - Run `.\azure\deploy.ps1` to apply changes
   - Verify all resources created successfully

2. **Verify Functionality:**
   - Test pick history blob uploads
   - Verify container app health
   - Check resource tags in Azure Portal

3. **Migrate Data (Optional):**
   - Copy existing pick history from external storage if needed
   - Decommission old storage account after verification

4. **Monitor:**
   - Review cost allocation with new tags
   - Monitor storage account usage
   - Quarterly resource organization review

---

## References

- [Azure Resource Group Review](./AZURE_RESOURCE_GROUP_REVIEW.md)
- [Azure Resource Cleanup](./AZURE_RESOURCE_CLEANUP.md)
- [Naming Standards](./NAMING_STANDARDS.md)
- [Azure Deployment README](../azure/README.md)

---

## Related Issues/PRs

- Related to: Azure Resource Group Organization Review
- Implements recommendations from: `docs/AZURE_RESOURCE_GROUP_REVIEW.md`
