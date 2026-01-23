# GitHub Actions → Azure Deployment Setup

This guide enables **automated CI/CD from GitHub Actions to Azure Container Apps** without needing Azure CLI in Codespaces.

## Required GitHub Secrets

| Secret Name | Required | Description |
|-------------|----------|-------------|
| `AZURE_CREDENTIALS` | ✅ Yes | Service principal JSON for Azure login |
| `GITHUB_TOKEN` | Auto | Automatically provided by GitHub |
| `ACR_REGISTRY` | Optional | ACR login server (for devcontainer builds) |
| `AZURE_CLIENT_ID` | Optional | Service principal client ID (for devcontainer builds) |
| `AZURE_CLIENT_SECRET` | Optional | Service principal secret (for devcontainer builds) |
| `HISTORICAL_DATA_PAT` | Optional | PAT for cross-repo historical data sync |
| `AZURE_STORAGE_CONNECTION_STRING` | Optional | For blob storage operations |

---

## Quick Setup (5 minutes)

### Step 1: Create Azure Service Principal

Run this in **Azure Cloud Shell** (portal.azure.com → Cloud Shell icon):

```bash
# Replace with your subscription ID
SUBSCRIPTION_ID="YOUR_SUBSCRIPTION_ID"
RESOURCE_GROUP="NCAAM-GBSV-MODEL-RG"

az ad sp create-for-rbac \
  --name "ncaam-github-actions" \
  --role contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resource-groups/$RESOURCE_GROUP \
  --sdk-auth
```

This outputs JSON like:

```json
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "subscriptionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  ...
}
```

**Copy the entire JSON output.**

### Step 2: Add GitHub Secret

1. Go to your repo: https://github.com/JDSB123/green_bier_sports_ncaam_model/settings/secrets/actions
2. Click **New repository secret**
3. Name: `AZURE_CREDENTIALS`
4. Value: Paste the entire JSON from Step 1
5. Click **Add secret**

### Step 3: Enable Automatic Deployment

Edit [.github/workflows/build-and-push.yml](../../.github/workflows/build-and-push.yml):

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'services/prediction-service-python/**'
      - 'services/ratings-sync-go/**'
      - 'services/odds-ingestion-rust/**'
      - 'services/web-frontend/**'
      - 'azure/**'
      - 'database/migrations/**'
      - '.github/workflows/build-and-push.yml'
  workflow_dispatch:  # Keep manual trigger available
```

(Uncomment the `push:` block in the workflow file)

---

## Manual Deployment

Even without auto-deploy, you can manually trigger:

1. Go to: https://github.com/JDSB123/green_bier_sports_ncaam_model/actions
2. Select **Build and Push to ACR**
3. Click **Run workflow** → **Run workflow**

---

## What the Workflow Does

1. **Builds** prediction-service and web-frontend Docker images
2. **Pushes** to Azure Container Registry (`ncaamstablegbsvacr.azurecr.io`)
3. **Deploys** to Azure Container Apps (`ncaam-stable-prediction`, `ncaam-stable-web`)
4. **Updates** `docker-compose.yml` with new image tags

---

## Verify Setup

After adding the secret, test with a manual run:

```bash
# From your browser
# 1. Go to Actions tab
# 2. Select "Build and Push to ACR"
# 3. Click "Run workflow"
# 4. Watch the logs
```

Expected output:
- ✅ Images built and pushed
- ✅ Container Apps updated
- ✅ docker-compose.yml committed with new version

---

## Troubleshooting

### "AZURE_CREDENTIALS secret is missing"

The workflow validates secrets at startup. Make sure you:
1. Created the service principal with `--sdk-auth` flag
2. Copied the **entire JSON** output
3. Named the secret exactly `AZURE_CREDENTIALS`

### "az acr login failed"

The service principal needs ACR pull/push permissions. This is included with `contributor` role on the resource group.

### "Container App not found"

The Azure infrastructure must exist first. Run the initial deployment:

```powershell
# PowerShell (Windows/Cloud Shell)
./azure/deploy.ps1 -OddsApiKey "YOUR_API_KEY"
```

---

## Security Notes

- The service principal only has access to `NCAAM-GBSV-MODEL-RG`
- `clientSecret` is stored encrypted in GitHub Secrets
- Consider using OIDC federation for production (no secret rotation needed)

## Next Steps

Once configured:
- Push code → automatic deployment
- No `az` CLI needed in Codespaces
- Focus on development, not deployment mechanics
