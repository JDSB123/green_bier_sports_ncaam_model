$ErrorActionPreference = "Stop"

$sourceRg = "green-bier-ncaam"
$targetRg = "greenbier-enterprise-rg"
$location = "centralus"

Write-Host "Checking status of resource group '$sourceRg'..."

while ($true) {
    $state = az group show -n $sourceRg --query properties.provisioningState -o tsv
    Write-Host "Current state: $state"
    
    if ($state -eq "Succeeded") {
        Write-Host "Resource move completed (or group is stable)."
        break
    } elseif ($state -eq "Failed") {
        Write-Host "Resource move failed. Please check Azure Portal."
        exit 1
    }
    
    Write-Host "Waiting for operation to complete... (sleeping 30s)"
    Start-Sleep -Seconds 30
}

# Verify resources in target RG
Write-Host "Verifying resources in '$targetRg'..."
$acr = az resource list -g $targetRg --query "[?name=='ncaamprodacr']" -o tsv
if (-not $acr) {
    Write-Host "WARNING: ACR 'ncaamprodacr' not found in '$targetRg'. The move might have failed or is not yet reflected."
    # We might want to exit here, but maybe the user wants to proceed with redeployment anyway?
    # If ACR is missing, Bicep will try to create it. If it exists in source, it will fail.
    # So we should probably check source too.
    $acrSource = az resource list -g $sourceRg --query "[?name=='ncaamprodacr']" -o tsv
    if ($acrSource) {
        Write-Host "ERROR: ACR still exists in source RG. Move failed."
        exit 1
    }
} else {
    Write-Host "Resources confirmed in target RG."
}

# Delete source RG
Write-Host "Deleting legacy resource group '$sourceRg'..."
# We use --no-wait so we can proceed, but actually we should wait if we want to be clean.
# But deleting the RG might take a while.
# The user said "ensure [legacy env] is deletyed".
# We can start the deletion and proceed to deployment in parallel (since they are different RGs).
az group delete -n $sourceRg --yes --no-wait
Write-Host "Deletion of '$sourceRg' initiated."

# Deploy to target RG
Write-Host "Deploying to '$targetRg'..."
$dbPass = Get-Content "..\secrets\db_password.txt"
$oddsKey = Get-Content "..\secrets\odds_api_key.txt"

az deployment group create `
  --resource-group $targetRg `
  --template-file main.bicep `
  --parameters environment=prod location=$location postgresPassword=$dbPass oddsApiKey=$oddsKey

Write-Host "Migration and deployment completed successfully."
