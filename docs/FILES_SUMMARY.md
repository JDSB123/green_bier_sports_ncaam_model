# Files Summary - Recent Changes

**Date:** December 21, 2025  
**Purpose:** Quick reference of files created/modified for enterprise resource organization

---

## 🎯 Essential Files (Required for Functionality)

### Deployment Files (Core)
1. **`azure/deploy.ps1`** ✏️ Modified
   - Added `-EnterpriseMode` flag
   - Supports deploying to `greenbier-enterprise-rg`
   - **Why:** Enables enterprise resource organization

2. **`azure/main.bicep`** ✏️ Modified
   - Added tags to all resources (`Model=ncaam`)
   - **Why:** Organizes resources for filtering in enterprise RG

---

## 📚 Documentation Files (Reference Only)

3. **`docs/ENTERPRISE_RESOURCE_ORGANIZATION.md`** ✨ New
   - Guide for enterprise resource organization
   - **Why:** Documents how to use enterprise mode
   - **Can review later:** ✅ Yes

4. **`docs/AZURE_RESOURCE_CLEANUP.md`** ✨ New
   - Guide for cleaning up duplicate resource groups
   - **Why:** Helps identify which resources to keep/delete
   - **Can review later:** ✅ Yes

5. **`docs/DEVELOPMENT_WORKFLOW.md`** ✨ New
   - Explains local/GitHub/Azure workflow
   - **Why:** Clarifies where development happens
   - **Can review later:** ✅ Yes

6. **`azure/README.md`** ✏️ Modified
   - Added enterprise mode deployment instructions
   - **Why:** Updated deployment docs
   - **Can review later:** ✅ Yes (if you remember the command)

---

## 🛠️ Utility Scripts (Optional)

7. **`scripts/cleanup-duplicate-azure-resources.ps1`** ✨ New
   - Script to clean up duplicate resource groups
   - **Why:** Helps remove `green-bier-ncaam` duplicate RG
   - **Can review later:** ✅ Yes (use when ready to clean up)

---

## 📋 Quick Summary

### What You Actually Need to Know:

**To deploy to enterprise RG:**
```powershell
.\azure\deploy.ps1 -Environment prod -EnterpriseMode -OddsApiKey "YOUR_KEY"
```

**That's it!** The rest is documentation for reference.

### What Changed?

1. **Deployment script** now supports `-EnterpriseMode`
2. **All resources** get tagged with `Model=ncaam`
3. **Documentation** created for future reference

### Files You Can Ignore for Now:

- All `docs/*.md` files (documentation, review when needed)
- `scripts/cleanup-*.ps1` (utility, use when cleaning up)

### Files You Need:

- `azure/deploy.ps1` (to deploy)
- `azure/main.bicep` (infrastructure template)

---

## 🗑️ Want to Clean Up Documentation?

If you want fewer files, we can:
1. **Consolidate** multiple docs into one file
2. **Delete** optional utility scripts (you can recreate if needed)
3. **Keep only** essential deployment files

Just let me know what you'd prefer!

---

**TL;DR:** Only 2 files actually matter for deployment (`deploy.ps1` and `main.bicep`). The rest is documentation you can review later.

