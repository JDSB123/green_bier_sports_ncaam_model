# Historical Data Sync Setup (Azure-only)

This document explains how to keep Azure Blob Storage in sync. Local cache and
git repo storage are not used.

## Architecture

```
testing/scripts/            ingestion scripts (Azure-only)
scripts/export_team_registry.py  alias export to Azure
            |
            v
Azure Blob Storage (metricstrackersgbsv / ncaam-historical-data)
scores/  odds/  ratings/  backtest_datasets/
```

## Required Secrets

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `AZURE_CREDENTIALS` | Azure Service Principal JSON | Azure Portal / az CLI |
| `AZURE_CANONICAL_CONNECTION_STRING` | Canonical data connection string | Azure Portal -> Storage Account -> Access Keys |

## Manual Sync Commands

```bash
# Scores + Barttorvik ratings
python testing/scripts/fetch_historical_data.py --seasons 2024-2026 --format both

# First-half scores
python testing/scripts/fetch_h1_data.py

# Historical odds
python testing/scripts/fetch_historical_odds.py --start 2023-11-01 --end 2024-04-15

# Export team aliases to Azure
python scripts/export_team_registry.py --write-aliases
```

## Verification

After sync, verify data in Azure:

```bash
az storage blob list \
  --container-name ncaam-historical-data \
  --account-name metricstrackersgbsv \
  --auth-mode login \
  --output table
```

Or view in Azure Portal:
- Storage Account: `metricstrackersgbsv`
- Container: `ncaam-historical-data`
