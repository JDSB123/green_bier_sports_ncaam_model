# Historical Data Sync Setup

This document explains how to keep the two repos and Azure Blob Storage in sync.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    green_bier_sports_ncaam_model                │
│                         (main branch)                           │
│                                                                 │
│  ├── testing/scripts/           ← Ingestion scripts            │
│  │   ├── fetch_historical_odds.py                              │
│  │   ├── fetch_historical_data.py                              │
│  │   └── ...                                                    │
│  │                                                              │
│  ├── scripts/                                                   │
│  │   └── sync_raw_data_to_azure.py  ← Azure Blob sync          │
│  │                                                              │
│  └── ncaam_historical_data_local/   ← Nested repo (gitignored) │
│      └── [ncaam-historical-data repo]                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ GitHub Actions
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ncaam-historical-data                        │
│                       (master branch)                           │
│                                                                 │
│  ├── odds/canonical/          ← Normalized odds (TRACKED)      │
│  ├── odds/raw/archive/        ← Raw API data (GITIGNORED)      │
│  ├── scores/                  ← ESPN scores (TRACKED)          │
│  ├── ratings/                 ← Barttorvik (TRACKED)           │
│  └── backtest_datasets/       ← Training data (TRACKED)        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ GitHub Actions
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Azure Blob Storage                           │
│            metricstrackersgbsv / ncaam-historical-raw           │
│                                                                 │
│  ├── odds/raw/archive/        ← Raw API data backup            │
│  ├── odds/canonical/          ← Canonical odds backup          │
│  ├── scores/                  ← Scores backup                  │
│  ├── ratings/                 ← Ratings backup                 │
│  └── backtest_datasets/       ← Training data backup           │
└─────────────────────────────────────────────────────────────────┘
```

## Workflows

### 1. Main Repo: `sync-historical-data.yml`

**Triggers:**
- Weekly on Sunday at 6 AM UTC
- Manual dispatch

**What it does:**
1. Checks if historical data submodule has uncommitted changes
2. Pushes changes to ncaam-historical-data repo
3. Syncs raw data to Azure Blob Storage

### 2. Historical Data Repo: `sync-to-azure.yml`

**Triggers:**
- On push to master (when odds/scores/ratings change)
- Manual dispatch

**What it does:**
- Uploads canonical data to Azure Blob Storage

## Required Secrets

### For `green_bier_sports_ncaam_model` repo:

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `AZURE_CREDENTIALS` | Azure Service Principal JSON | See below |
| `AZURE_STORAGE_CONNECTION_STRING` | Storage account connection string | Azure Portal → Storage Account → Access Keys |
| `HISTORICAL_DATA_PAT` | GitHub PAT with repo access to ncaam-historical-data | GitHub Settings → Developer Settings → PATs |

### For `ncaam-historical-data` repo:

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `AZURE_CREDENTIALS` | Azure Service Principal JSON | See below |

## Creating Azure Service Principal

```bash
# Create service principal with Storage Blob Data Contributor role
az ad sp create-for-rbac \
  --name "github-actions-ncaam" \
  --role "Storage Blob Data Contributor" \
  --scopes /subscriptions/{subscription-id}/resourceGroups/dashboard-gbsv-main-rg/providers/Microsoft.Storage/storageAccounts/metricstrackersgbsv \
  --sdk-auth
```

Copy the JSON output and add it as `AZURE_CREDENTIALS` secret in both repos.

## Creating GitHub PAT

1. Go to GitHub → Settings → Developer Settings → Personal Access Tokens → Fine-grained tokens
2. Create a new token with:
   - Repository access: `JDSB123/ncaam-historical-data`
   - Permissions: Contents (Read and Write)
3. Copy the token and add as `HISTORICAL_DATA_PAT` secret in the main repo

## Manual Sync Commands

### From your local machine:

```bash
# Navigate to main repo
cd c:\Users\JB\green-bier-ventures\NCAAM_main

# Sync raw data to Azure Blob
python scripts/sync_raw_data_to_azure.py

# Push historical data repo changes
cd ncaam_historical_data_local
git add -A
git commit -m "chore: manual sync"
git push origin master
```

### Via GitHub Actions:

1. Go to the main repo → Actions
2. Select "Sync Historical Data"
3. Click "Run workflow"
4. Choose options and run

## Verification

After sync, verify data in Azure:

```bash
# List blobs in the container
az storage blob list \
  --container-name ncaam-historical-raw \
  --account-name metricstrackersgbsv \
  --auth-mode login \
  --output table
```

Or view in Azure Portal:
- Storage Account: `metricstrackersgbsv`
- Container: `ncaam-historical-raw`
