# Post NCAA lineup analysis to Teams
$webhookUrl = "https://greenbiercapital.webhook.office.com/webhookb2/6d55cb22-b8b0-43a4-8ec1-f5df8a966856@18ee0910-417d-4a81-a3f5-7945bdbd5a78/IncomingWebhook/c4bfae73ea2c4a1fa43541853c8ae09a/c30a04d7-4015-49cf-9fb9-f4735f413e33/V2PLKEtg95VC-EsDSS00BAojeMMFQwGBk86CIh8y8gu8Q1"
$resourceGroup = "greenbier-enterprise-rg"
$serviceUrl = try {
    $fqdn = az containerapp show --name ncaam-prediction --resource-group $resourceGroup --query "properties.configuration.ingress.fqdn" -o tsv 2>$null
    if ($fqdn) { "https://$fqdn" } else { "" }
} catch {
    ""
}

# Matchups from images (Friday, December 19, 2025)
$matchups = @(
    @{ Time = "04:00 PM CST"; Away = "South Dakota St"; AwayRecord = "7-6"; Home = "Wisc Milwaukee"; HomeRecord = "4-6"; Venue = "@ FISERV FORUM - MILWAUKEE, WI" },
    @{ Time = "05:30 PM CST"; Away = "Seton Hall"; AwayRecord = "10-1"; Home = "Providence"; HomeRecord = "7-5" },
    @{ Time = "06:00 PM CST"; Away = "Mount St Marys"; AwayRecord = "3-8"; Home = "Drexel"; HomeRecord = "4-7" },
    @{ Time = "06:00 PM CST"; Away = "Eastern Michigan"; AwayRecord = "6-5"; Home = "Akron"; HomeRecord = "8-3" },
    @{ Time = "06:30 PM CST"; Away = "Tulsa"; AwayRecord = "10-1"; Home = "Western Kentucky"; HomeRecord = "7-3" },
    @{ Time = "07:00 PM CST"; Away = "Villanova"; AwayRecord = "8-2"; Home = "Wisconsin"; HomeRecord = "7-3"; Venue = "@ FISERV FORUM - MILWAUKEE, WI"; Broadcast = "FOX" },
    @{ Time = "08:00 PM CST"; Away = "Belmont"; AwayRecord = "11-1"; Home = "Cal Irvine"; HomeRecord = "7-4" },
    @{ Time = "08:30 PM CST"; Away = "Abilene Christian"; AwayRecord = "7-4"; Home = "BYU"; HomeRecord = "0-0"; Broadcast = "TNT" },
    @{ Time = "09:00 PM CST"; Away = "Cal Poly SLO"; AwayRecord = "5-7"; Home = "UCLA"; HomeRecord = "8-3" },
    @{ Time = "09:00 PM CST"; Away = "San Diego"; AwayRecord = "4-6"; Home = "UC San Diego"; HomeRecord = "10-1" },
    @{ Time = "09:00 PM CST"; Away = "Florida Atlantic"; AwayRecord = "8-3"; Home = "St Marys CA"; HomeRecord = "9-2" },
    @{ Time = "10:30 PM CST"; Away = "Seattle"; AwayRecord = "9-2"; Home = "Washington"; HomeRecord = "7-3"; Venue = "@ CLIMATE PLEDGE ARENA - SEATTLE, WA"; Broadcast = "ESPN2" }
)

# Check service health
try {
    if ($serviceUrl) {
        $health = Invoke-RestMethod -Uri "$serviceUrl/health" -Method Get -TimeoutSec 5
        $serviceStatus = "$($health.status) | Version: $($health.version)"
    } else {
        $serviceStatus = "Unavailable: prediction service FQDN not resolved"
    }
} catch {
    $serviceStatus = "Unavailable: $($_.Exception.Message)"
}

# Build matchup facts for Teams
$matchupFacts = @()
foreach ($game in $matchups) {
    $awayTeam = "$($game.Away) ($($game.AwayRecord))"
    $homeTeam = "$($game.Home) ($($game.HomeRecord))"
    $venue = if ($game.Venue) { 
        if ($game.Broadcast) { "$($game.Venue) [$($game.Broadcast)]" } else { $game.Venue }
    } else { 
        if ($game.Broadcast) { "[$($game.Broadcast)]" } else { "-" }
    }
    
    $matchupFacts += @{
        "name" = "$($game.Time) - $awayTeam @ $homeTeam"
        "value" = $venue
    }
}

# Create Teams message card
$jsonBody = @{
    "@type" = "MessageCard"
    "@context" = "https://schema.org/extensions"
    "summary" = "NCAA Basketball Lineup - December 19, 2025"
    "themeColor" = "008f58"
    "title" = "NCAA Basketball Prediction Analysis - Friday, December 19, 2025"
    "sections" = @(
        @{
            "activityTitle" = "Today's Lineup - 12 Games"
            "activitySubtitle" = "Azure Service: $serviceStatus"
            "text" = "**Matchups Scheduled**"
            "facts" = $matchupFacts
        },
        @{
            "title" = "Analysis Status"
            "startGroup" = $true
            "text" = "**To generate predictions:**`n• Games need to be in database with correct team name matching`n• Team ratings synced from Barttorvik (365 teams)`n• Odds synced from The Odds API (Pinnacle/Bovada)`n`n**Service URL:** $(if ($serviceUrl) { $serviceUrl } else { 'Resolve via az containerapp show' })"
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
    Write-Host "Lineup analysis posted to Teams successfully"
} catch {
    Write-Host "Error posting to Teams: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response body: $responseBody"
    }
}
