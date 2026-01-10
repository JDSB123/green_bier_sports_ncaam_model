# Azure Infrastructure Diagram - v34.1.0

**Resource Group:** `NCAAM-GBSV-MODEL-RG`  
**Location:** `centralus`  
**Environment:** `stable`

---

## 🏗️ Infrastructure Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     NCAAM-GBSV-MODEL-RG (Resource Group)                     │
│                               centralus                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                    Container Registry (ACR)                         │    │
│  │  Name: ncaamstablegbsvacr                                          │    │
│  │  SKU: Basic                                                        │    │
│  │  Cost: ~$5/month                                                   │    │
│  │  Purpose: Docker image storage                                     │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│                              │ (image pull)                                  │
│                              ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │              Container Apps Environment                            │    │
│  │              Name: ncaam-stable-env                                │    │
│  │                                                                    │    │
│  │  ┌────────────────────────┐    ┌────────────────────────┐        │    │
│  │  │  Prediction Service    │    │  Web Frontend          │        │    │
│  │  │  ncaam-stable-         │    │  ncaam-stable-web      │        │    │
│  │  │  prediction            │    │                        │        │    │
│  │  │                        │    │  CPU: 0.25 / 2Gi max   │        │    │
│  │  │  CPU: 1.0 / 2Gi        │    │  Port: 8080            │        │    │
│  │  │  Port: 8082            │    │                        │        │    │
│  │  │  Min: 1, Max: 1        │    │  Min: 1, Max: 2        │        │    │
│  │  └────────┬───────────────┘    └────────────────────────┘        │    │
│  │           │                                                       │    │
│  └───────────┼───────────────────────────────────────────────────────┘    │
│              │                                                              │
│              │ (database queries)                                          │
│              ▼                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │          PostgreSQL Flexible Server                                │    │
│  │          Name: ncaam-stable-gbsv-postgres                          │    │
│  │          SKU: Standard_B1ms (Burstable)                            │    │
│  │          Database: ncaam                                           │    │
│  │          Version: 15                                               │    │
│  │          Storage: 32 GB                                            │    │
│  │          Cost: ~$15/month                                          │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │              Azure Cache for Redis                                 │    │
│  │              Name: ncaam-stable-gbsv-redis                         │    │
│  │              SKU: Basic C0                                         │    │
│  │              TLS: 1.2 minimum                                      │    │
│  │              Cost: ~$16/month                                      │    │
│  │              Purpose: Cache layer                                  │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │              Storage Account (NEW v34.1.0)                         │    │
│  │              Name: ncaamstablegbsvsa                               │    │
│  │              SKU: Standard LRS                                     │    │
│  │              Container: picks-history                              │    │
│  │              Cost: ~$0.02/GB/month                                 │    │
│  │              Purpose: Pick history blob snapshots                  │    │
│  │              Access: Private (no public access)                    │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │              Azure Key Vault                                       │    │
│  │              Name: ncaam-stablegbsvkv                              │    │
│  │              SKU: Standard                                         │    │
│  │              RBAC: Enabled                                         │    │
│  │              Soft Delete: 90 days                                  │    │
│  │              Cost: ~$1/month                                       │    │
│  │              Secrets:                                              │    │
│  │                - postgres-password                                 │    │
│  │                - odds-api-key                                      │    │
│  │                - redis-password                                    │    │
│  │                - acr-password                                      │    │
│  │                - storage-connection-string                         │    │
│  │                - database-url                                      │    │
│  │                - redis-url                                         │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │              Log Analytics Workspace                               │    │
│  │              Name: ncaam-stable-logs                               │    │
│  │              SKU: PerGB2018                                        │    │
│  │              Retention: 30 days                                    │    │
│  │              Cost: ~$2-5/month                                     │    │
│  │              Purpose: Centralized logging                          │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │              Monitoring & Alerts                                   │    │
│  │              Action Group: ncaam-stable-alerts                     │    │
│  │              Alerts:                                               │    │
│  │                - API Health Check Failures                         │    │
│  │                - Database Connection Issues                        │    │
│  │                - High CPU Usage                                    │    │
│  │                - High Memory Usage                                 │    │
│  │                - 5xx Errors (Log Query)                            │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Resource Summary

### Compute Resources

| Resource | Name | Configuration | Cost |
|----------|------|---------------|------|
| Container Registry | `ncaamstablegbsvacr` | Basic SKU | ~$5/month |
| Container App (Prediction) | `ncaam-stable-prediction` | 1 CPU, 2Gi RAM | Pay-per-use |
| Container App (Web) | `ncaam-stable-web` | 0.25 CPU, 0.5Gi RAM | Pay-per-use |
| Container Apps Environment | `ncaam-stable-env` | Consumption plan | Included |

### Data Resources

| Resource | Name | Configuration | Cost |
|----------|------|---------------|------|
| PostgreSQL Flexible | `ncaam-stable-gbsv-postgres` | B1ms, 32GB | ~$15/month |
| Redis Cache | `ncaam-stable-gbsv-redis` | Basic C0 | ~$16/month |
| Storage Account | `ncaamstablegbsvsa` | Standard LRS | ~$0.02/GB/month |

### Security & Operations

| Resource | Name | Configuration | Cost |
|----------|------|---------------|------|
| Key Vault | `ncaam-stablegbsvkv` | Standard, RBAC | ~$1/month |
| Log Analytics | `ncaam-stable-logs` | PerGB2018, 30d retention | ~$2-5/month |
| Action Group | `ncaam-stable-alerts` | Email/Webhook notifications | Free |
| Metric Alerts | `ncaam-stable-*-alert` | 4 alerts configured | Free |

**Total Estimated Monthly Cost: ~$41-53/month**

---

## 🔄 Data Flow

### Prediction Generation Flow

```
1. External Request
   └─> ncaam-stable-prediction (Container App)
       ├─> PostgreSQL (read game/team data)
       ├─> Redis (cache odds/results)
       └─> Generate Predictions
           └─> PostgreSQL (store picks)
               └─> Storage Account (snapshot picks-history container)
```

### Web Frontend Flow

```
2. User Browser
   └─> ncaam-stable-web (Container App)
       └─> Static Content / API Proxy
           └─> ncaam-stable-prediction (for API calls)
```

### Logging & Monitoring Flow

```
3. All Services
   └─> Log Analytics Workspace
       └─> Metric Alerts
           └─> Action Group
               └─> Email/Webhook Notifications
```

---

## 🏷️ Resource Tags (All Resources)

All resources are tagged with:

```bicep
{
  Model: "ncaam"
  Environment: "stable"
  ManagedBy: "Bicep"
  Application: "NCAAM-Prediction-Model"
  CostCenter: "GBSV-Sports"
  Owner: "green-bier-ventures"
  Project: "NCAAM-Prediction"
  Version: "v34.1.0"
}
```

---

## 🔐 Secrets Management

### Key Vault Secrets

All secrets are stored in `ncaam-stablegbsvkv`:

- **postgres-password** - PostgreSQL admin password
- **odds-api-key** - The Odds API key
- **basketball-api-key** - Basketball API key (optional)
- **action-network-username** - Action Network username (optional)
- **action-network-password** - Action Network password (optional)
- **redis-password** - Redis access key (auto-generated)
- **acr-password** - ACR pull credentials (auto-generated)
- **storage-connection-string** - Storage account connection string (auto-generated)
- **database-url** - Full PostgreSQL connection string
- **redis-url** - Full Redis connection string

### Container App Secrets

Container Apps reference secrets via `secretRef`:
- Secrets are injected as environment variables at runtime
- Never exposed in container logs or environment inspection

---

## 🌐 Network Architecture

### Public Endpoints

- **Prediction API:** `https://ncaam-stable-prediction.{region}.azurecontainerapps.io`
- **Web Frontend:** `https://ncaam-stable-web.{region}.azurecontainerapps.io`

### Private Connectivity

- **PostgreSQL:** Private endpoint (firewall allows Azure services: 0.0.0.0/0)
- **Redis:** Private endpoint with TLS 1.2 minimum
- **Storage Account:** Private access only (no public blob access)
- **Key Vault:** Public network access enabled (RBAC protected)

---

## 📈 Scaling Configuration

### Container Apps Scaling

**Prediction Service:**
- Min Replicas: 1
- Max Replicas: 1 (fixed - single instance)
- Scale Rule: HTTP-based (10 concurrent requests)

**Web Frontend:**
- Min Replicas: 1
- Max Replicas: 2 (auto-scale)
- Scale Rule: HTTP-based (50 concurrent requests)

### Database Scaling

**PostgreSQL:**
- Fixed: B1ms (1 vCore, 2GB RAM)
- Manual scaling required for higher tiers

**Redis:**
- Fixed: Basic C0 (250MB)
- Manual scaling required for higher tiers

---

## 🔄 Changes from Previous Version (v33.15.0)

### ✅ Added (v34.1.0)

1. **Storage Account** (`ncaamstablegbsvsa`)
   - NEW: Internal storage account in NCAAM-GBSV-MODEL-RG
   - Automatic `picks-history` container creation
   - Replaces external dependency on `metricstrackersgbsv`

2. **Enhanced Tags**
   - Added: `CostCenter`, `Owner`, `Project`, `Version`
   - Better cost allocation and resource management

### 🔄 Modified (v34.1.0)

1. **Deployment Script** (`deploy.ps1`)
   - Default behavior: Creates internal storage account
   - Backward compatible: External storage via parameter override

2. **Storage Connection**
   - Auto-generated from internal storage account
   - Falls back to external if `-StorageConnectionString` provided

### ❌ Removed

- External storage dependency (now optional/override only)

---

## 🚀 Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Deployment Process                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Run: .\azure\deploy.ps1 -OddsApiKey "KEY"              │
│     │                                                       │
│     ├─> Create Resource Group (if new)                     │
│     ├─> Deploy Bicep Template                              │
│     │   ├─> Create all resources                           │
│     │   ├─> Create storage account (NEW)                   │
│     │   ├─> Create picks-history container (NEW)           │
│     │   └─> Apply enhanced tags (NEW)                      │
│     │                                                       │
│     ├─> Build Docker Images                                │
│     │   └─> Push to ACR                                    │
│     │                                                       │
│     ├─> Update Container Apps                              │
│     │   └─> Reference new storage account (NEW)            │
│     │                                                       │
│     └─> Verify Health                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 Resource Dependencies

```
Storage Account
  └─> Key Vault (stores connection string)
      └─> Container App (uses connection string)

PostgreSQL
  └─> Key Vault (stores password)
      └─> Container App (uses DATABASE_URL)

Redis
  └─> Key Vault (stores password)
      └─> Container App (uses REDIS_URL)

ACR
  └─> Key Vault (stores pull credentials)
      └─> Container Apps (pull images)

Log Analytics
  └─> Container Apps Environment (sends logs)
      └─> Metric Alerts (queries logs)
          └─> Action Group (sends notifications)
```

---

## 💰 Cost Breakdown

| Category | Resource | Estimated Monthly Cost |
|----------|----------|------------------------|
| Compute | Container Apps (Consumption) | ~$0-10 |
| Data | PostgreSQL (B1ms) | ~$15 |
| Data | Redis (Basic C0) | ~$16 |
| Data | Storage Account (LRS) | ~$0-2 |
| Registry | ACR (Basic) | ~$5 |
| Security | Key Vault (Standard) | ~$1 |
| Monitoring | Log Analytics (PerGB) | ~$2-5 |
| Monitoring | Alerts & Action Groups | $0 (Free) |
| **TOTAL** | | **~$41-53/month** |

**Note:** Storage cost depends on blob data volume (typically < 1GB = < $0.02/month)

---

## 📍 Resource Locations

All resources deployed to: **`centralus`** (Central US)

- Single region deployment
- No geo-redundancy (cost optimization)
- All resources in same region for low latency

---

## 🔐 Security Posture

- ✅ RBAC enabled on Key Vault
- ✅ TLS 1.2 minimum for Redis
- ✅ HTTPS only for Storage Account
- ✅ Private blob access (no public access)
- ✅ Secrets in Key Vault (not in code/config)
- ✅ Container Apps use managed identity (recommended future enhancement)

---

**Last Updated:** January 27, 2025  
**Infrastructure Version:** v34.1.0  
**Diagram Version:** 1.0
