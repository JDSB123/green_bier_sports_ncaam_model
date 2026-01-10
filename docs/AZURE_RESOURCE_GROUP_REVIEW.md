# Azure Resource Group Organization Review

**Date:** 2025-01-27  
**Resource Group:** `NCAAM-GBSV-MODEL-RG`  
**Location:** `centralus`

---

## 📊 Current State Assessment

### ✅ **Strengths**

1. **Consistent Naming Convention**
   - Pattern: `${baseName}-${environment}` (e.g., `ncaam-stable-*`)
   - Resource suffix for enterprise: `-gbsv`
   - Clear and predictable resource names

2. **Infrastructure as Code**
   - All resources defined in `main.bicep`
   - Version controlled and reproducible
   - Single deployment script (`deploy.ps1`)

3. **Tagging Strategy**
   - Common tags applied: `Model`, `Environment`, `ManagedBy`, `Application`
   - Helps with resource organization and cost tracking

4. **Cleanup Completed**
   - Legacy resource groups removed (`ncaam-prod-rg`, `green-bier-ncaam`, etc.)
   - Single source of truth established

### ⚠️ **Areas for Improvement**

#### 1. **Cross-Resource Group Dependency**

**Current Issue:**
- External storage account dependency: `metricstrackersgbsv` in `dashboard-gbsv-main-rg`
- Pick history blob storage lives outside the NCAAM resource group

**Impact:**
- Creates coupling between resource groups
- Potential permission/access issues
- Harder to track costs and manage lifecycle
- Deployment dependencies on external resources

**Recommendation:**
- **Option A (Recommended):** Move storage account to `NCAAM-GBSV-MODEL-RG`
  - Better resource ownership and lifecycle management
  - All NCAAM-related resources in one place
  - Easier cost tracking

- **Option B:** Keep external but document dependency clearly
  - Add explicit documentation of cross-RG dependencies
  - Ensure RBAC permissions are properly documented
  - Consider using Azure Blueprints or Management Groups for governance

#### 2. **Resource Group Organization**

**Current Structure:**
```
NCAAM-GBSV-MODEL-RG/
├── ncaamstablegbsvacr           # Container Registry
├── ncaam-stable-gbsv-postgres    # PostgreSQL (Data)
├── ncaam-stable-gbsv-redis       # Redis Cache (Data)
├── ncaam-stable-env              # Container Apps Environment
├── ncaam-stable-prediction       # Container App (Compute)
├── ncaam-stable-web              # Container App (Compute)
├── ncaam-stablegbsvkv            # Key Vault (Security)
├── ncaam-stable-logs             # Log Analytics (Monitoring)
└── [Action Groups & Alerts]      # Monitoring
```

**Current Approach:** Single resource group with all resources

**Pros:**
- Simple management
- Easy deployment
- All resources together

**Cons:**
- No separation by lifecycle (data vs compute)
- Harder to apply different RBAC policies
- All resources have same deletion scope

**Recommendations (Future Consideration):**

If you plan to scale or add multiple environments:

**Option 1: Separate by Environment** (if adding dev/staging)
```
NCAAM-GBSV-DEV-RG/
NCAAM-GBSV-STAGING-RG/
NCAAM-GBSV-PROD-RG/
```

**Option 2: Separate by Resource Type** (only if needed)
```
NCAAM-GBSV-DATA-RG/         # PostgreSQL, Redis, Storage
NCAAM-GBSV-COMPUTE-RG/      # Container Apps, ACR
NCAAM-GBSV-SHARED-RG/       # Key Vault, Log Analytics
```

**Verdict:** Current single-RG approach is **appropriate for current scale**. Only reorganize if you add multiple environments or need different RBAC scopes.

#### 3. **Enhanced Tagging**

**Current Tags:**
```bicep
var commonTags = {
  Model: baseName
  Environment: environment
  ManagedBy: 'Bicep'
  Application: 'NCAAM-Prediction-Model'
}
```

**Recommended Additional Tags:**
```bicep
var commonTags = {
  Model: baseName
  Environment: environment
  ManagedBy: 'Bicep'
  Application: 'NCAAM-Prediction-Model'
  CostCenter: 'GBSV-Sports'           // Cost allocation
  Owner: 'green-bier-ventures'        // Contact/ownership
  Project: 'NCAAM-Prediction'         // Project identification
  CreatedDate: deployment().properties.timestamp // Deployment tracking
  Version: 'v33.15.0'                 // Infrastructure version
}
```

**Benefits:**
- Better cost allocation and reporting
- Easier resource ownership identification
- Version tracking for infrastructure changes

#### 4. **Resource Naming Consistency**

**Current Naming Patterns:**
- ✅ Consistent: `ncaam-stable-*` for most resources
- ⚠️ Inconsistent: `ncaamstablegbsvacr` (ACR - no hyphens, Azure requirement)
- ⚠️ Inconsistent: `ncaam-stablegbsvkv` (Key Vault - no hyphen between stable and gbsv)

**Recommendation:** Document the naming exceptions (like ACR's no-hyphen requirement) more clearly in `NAMING_STANDARDS.md`.

---

## 📋 Resource Inventory

### Current Resources in `NCAAM-GBSV-MODEL-RG`

| Resource Type | Name | Purpose | Cost Impact |
|--------------|------|---------|-------------|
| Container Registry | `ncaamstablegbsvacr` | Docker image storage | ~$5/month |
| PostgreSQL Flexible | `ncaam-stable-gbsv-postgres` | Primary database | ~$15/month |
| Redis Cache (Basic) | `ncaam-stable-gbsv-redis` | Cache layer | ~$16/month |
| Storage Account | `ncaamstablegbsvsa` | Pick history blob storage | ~$0.02/GB/month (v34.1.0) |
| Key Vault | `ncaam-stablegbsvkv` | Secrets management | ~$1/month |
| Container Apps Env | `ncaam-stable-env` | Container hosting | Included |
| Container App (Prediction) | `ncaam-stable-prediction` | Main API service | Pay-per-use |
| Container App (Web) | `ncaam-stable-web` | Web frontend | Pay-per-use |
| Log Analytics | `ncaam-stable-logs` | Log aggregation | ~$2-5/month |
| Action Group | `ncaam-stable-alerts` | Alert notifications | Free |
| Metric Alerts (4) | `ncaam-stable-*-alert` | Monitoring | Free |

**Total Estimated Cost:** ~$41-51/month (Storage cost depends on blob data volume, typically minimal)

### External Resources (Dependencies) - OPTIONAL

| Resource Type | Name | Resource Group | Purpose | Status |
|--------------|------|----------------|---------|--------|
| Storage Account | `metricstrackersgbsv` | `dashboard-gbsv-main-rg` | Pick history blob storage (legacy) | Optional override via `-StorageConnectionString` parameter |

**Note (v34.1.0):** Storage account is now created internally in `NCAAM-GBSV-MODEL-RG` by default. External storage can still be used by providing the `-StorageConnectionString` parameter during deployment.

---

## 🎯 Recommendations Summary

### **Priority 1: Address Cross-RG Dependency** ✅ COMPLETED

**Action:** ✅ Moved storage account to `NCAAM-GBSV-MODEL-RG` (v34.1.0)

**Implementation:**
1. ✅ Created storage account resource in `main.bicep` (`ncaamstablegbsvsa`)
2. ✅ Created `picks-history` container automatically
3. ✅ Updated `deploy.ps1` to use internal storage by default
4. ✅ Maintained backward compatibility: external storage can still be used via `-StorageConnectionString` parameter
5. ⏳ Migration of existing blob data (manual step if needed)

**Migration Notes:**
- New deployments will automatically create internal storage account
- Existing deployments can migrate by:
  - Deploying new infrastructure (creates internal storage)
  - Copying data from `metricstrackersgbsv/picks-history` to `ncaamstablegbsvsa/picks-history`
  - Decommissioning old storage account (optional, after verification)

### **Priority 2: Enhance Tagging** ✅ COMPLETED

**Action:** ✅ Added cost allocation and ownership tags (v34.1.0)

**Implementation:**
- ✅ Updated `main.bicep` to include: `CostCenter`, `Owner`, `Project`, `Version` tags
- ⏳ Deploy updated infrastructure (next deployment will apply tags)
- ⏳ Verify tags in Azure Portal (after deployment)

### **Priority 3: Documentation**

**Action:** Document resource organization decisions

**Updates Needed:**
- Clear explanation of single-RG vs multi-RG decision
- Document external dependencies
- Update architecture diagrams

---

## ✅ Overall Assessment

**Current Organization: 7.5/10**

**Verdict:** Your Azure Resource Group is **well-organized for current scale**. The single resource group approach is appropriate and keeps things simple. The main improvement opportunity is addressing the cross-resource group dependency for storage.

**Recommendation:** Keep current structure, but:
1. Consider consolidating storage account into NCAAM RG
2. Add enhanced tags for better cost tracking
3. Document architectural decisions

**Future Considerations:**
- If adding dev/staging environments → separate resource groups per environment
- If resource count grows significantly → consider separation by resource type
- If RBAC requirements differ → separate by security boundary

---

## 📝 Action Items

- [x] **Decide:** Keep storage external or move to NCAAM RG → **RESOLVED: Internal storage account created in NCAAM-GBSV-MODEL-RG (v34.1.0)**
- [x] **Enhance:** Add cost allocation tags to `main.bicep` → **COMPLETED: Added CostCenter, Owner, Project, Version tags**
- [x] **Document:** Update architecture docs with resource organization rationale → **COMPLETED: Updated NAMING_STANDARDS.md and README.md**
- [ ] **Review:** Quarterly review of resource organization as project scales

---

## 🏗️ Architectural Decisions

### Single Resource Group Approach

**Decision:** Use a single resource group (`NCAAM-GBSV-MODEL-RG`) for all NCAAM resources.

**Rationale:**
- **Simplicity:** Single resource group is easier to manage and deploy
- **Current Scale:** Appropriate for current project size (10 resources)
- **Cost Tracking:** All resources in one RG makes cost allocation straightforward
- **Lifecycle Management:** All resources share the same lifecycle (stable environment)

**When to Reconsider:**
- If adding dev/staging environments → Separate RGs per environment
- If resource count grows significantly (>30-50 resources) → Consider separation by resource type
- If RBAC requirements differ significantly → Separate by security boundary
- If different teams own different resources → Separate for team autonomy

### Internal vs External Storage (v34.1.0)

**Decision:** Create storage account internally in `NCAAM-GBSV-MODEL-RG` by default, with option to use external storage via parameter override.

**Rationale:**
- **Resource Ownership:** All NCAAM resources should live together for better lifecycle management
- **Cost Tracking:** Easier to track costs when all resources are in one RG
- **Deployment Simplicity:** No cross-RG dependencies for default deployments
- **Backward Compatibility:** External storage option maintained for migration/override scenarios

**Migration Strategy:**
- New deployments: Automatically create internal storage
- Existing deployments: Can migrate data manually, or continue using external storage via parameter
- External storage override: Use `-StorageConnectionString` parameter to specify external account

### Enhanced Tagging Strategy (v34.1.0)

**Decision:** Apply comprehensive tags to all resources: `Model`, `Environment`, `ManagedBy`, `Application`, `CostCenter`, `Owner`, `Project`, `Version`.

**Rationale:**
- **Cost Allocation:** `CostCenter` enables better cost reporting and chargeback
- **Resource Ownership:** `Owner` identifies who is responsible for resources
- **Project Tracking:** `Project` helps organize resources by initiative
- **Version Tracking:** `Version` tracks infrastructure-as-code version for change management

---

## 🔍 Quick Reference

**Resource Group Name:** `NCAAM-GBSV-MODEL-RG`  
**Location:** `centralus`  
**Environment:** `stable`  
**Deployment Script:** `azure/deploy.ps1`  
**Infrastructure Code:** `azure/main.bicep` (v34.1.0)  
**Last Cleanup:** December 23, 2025 (per `AZURE_RESOURCE_CLEANUP.md`)  
**Last Review:** January 27, 2025 - Enhanced with storage consolidation and improved tagging
