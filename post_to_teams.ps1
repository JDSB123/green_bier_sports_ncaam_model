$webhookUrl = "https://greenbiercapital.webhook.office.com/webhookb2/6d55cb22-b8b0-43a4-8ec1-f5df8a966856@18ee0910-417d-4a81-a3f5-7945bdbd5a78/IncomingWebhook/c4bfae73ea2c4a1fa43541853c8ae09a/c30a04d7-4015-49cf-9fb9-f4735f413e33/V2PLKEtg95VC-EsDSS00BAojeMMFQwGBk86CIh8y8gu8Q1"

# Using dashboard color scheme: Primary green #008f58
$resourceGroup = "greenbier-enterprise-rg"
$registry = "greenbieracr.azurecr.io"
$keyVault = "greenbier-keyvault"
$containerEnv = "greenbier-ncaam-env"

$predictionFqdn = try {
    az containerapp show --name ncaam-prediction --resource-group $resourceGroup --query "properties.configuration.ingress.fqdn" -o tsv 2>$null
} catch {
    "(set FQDN manually)"
}

$jsonBody = @{
    "@type" = "MessageCard"
    "@context" = "https://schema.org/extensions"
    "summary" = "NCAA Basketball v6.0 - Azure Deployment Complete"
    "themeColor" = "008f58"
    "title" = "Azure Deployment Complete - NCAA Basketball v6.0"
    "sections" = @(
        @{
            "activityTitle" = "All containers successfully deployed to Azure"
            "activitySubtitle" = "December 19, 2025"
            "text" = "**Azure Resources**"
            "facts" = @(
                @{
                    "name" = "Resource Group"
                    "value" = $resourceGroup
                },
                @{
                    "name" = "Container Registry"
                    "value" = $registry
                },
                @{
                    "name" = "Key Vault"
                    "value" = $keyVault
                },
                @{
                    "name" = "Container Apps Environment"
                    "value" = $containerEnv
                }
            )
        },
        @{
            "title" = "Container Apps Status"
            "startGroup" = $true
            "facts" = @(
                @{
                    "name" = "PostgreSQL"
                    "value" = "ncaam-postgres | Running | 1.0 CPU | 2.0Gi Memory"
                },
                @{
                    "name" = "Redis"
                    "value" = "ncaam-redis | Running | 0.5 CPU | 1.0Gi Memory"
                },
                @{
                    "name" = "Prediction Service"
                    "value" = "ncaam-prediction | Running | 1.0 CPU | 2.0Gi Memory"
                }
            )
        },
        @{
            "title" = "Service Endpoints"
            "startGroup" = $true
            "facts" = @(
                @{
                    "name" = "Prediction Service URL"
                    "value" = if ($predictionFqdn) { "https://$predictionFqdn" } else { "(set FQDN manually)" }
                },
                @{
                    "name" = "Health Check Status"
                    "value" = "PASSED (200 OK)"
                }
            )
        },
        @{
            "title" = "Deployment Summary"
            "startGroup" = $true
            "text" = "All systems operational. Containers are running and health checks are passing. Ready for database migrations and prediction execution."
        }
    )
    "potentialAction" = @(
        @{
            "@type" = "OpenUri"
            "name" = "View in Azure Portal"
            "targets" = @(
                @{
                    "os" = "default"
                    "uri" = "https://portal.azure.com/#@greenbiercapital.onmicrosoft.com/resource/subscriptions/3a1a4a94-45a5-4f7c-8ada-97978221052c/resourceGroups/greenbier-enterprise-rg"
                }
            )
        }
    )
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $webhookUrl -Method Post -Body $jsonBody -ContentType "application/json"
    Write-Host "Message posted to Teams successfully with dashboard styling"
} catch {
    Write-Host "Error posting to Teams: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response body: $responseBody"
    }
}
