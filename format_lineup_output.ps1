# Format NCAA lineup analysis output
$serviceUrl = "https://ncaam-prediction.ashycliff-f98889a8.eastus.azurecontainerapps.io"

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

Write-Host ""
Write-Host "=========================================================================================================="
Write-Host "  NCAA BASKETBALL PREDICTION ANALYSIS - FRIDAY, DECEMBER 19, 2025"
Write-Host "=========================================================================================================="
Write-Host ""

# Check service health
Write-Host "Checking Azure prediction service..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$serviceUrl/health" -Method Get -TimeoutSec 5
    Write-Host "Service Status: $($health.status) | Version: $($health.version)" -ForegroundColor Green
} catch {
    Write-Host "Service unavailable: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=========================================================================================================="
Write-Host "  TODAY'S LINEUP - MATCHUPS"
Write-Host "=========================================================================================================="
Write-Host ""

$table = @()
foreach ($game in $matchups) {
    $awayTeam = "$($game.Away) ($($game.AwayRecord))"
    $homeTeam = "$($game.Home) ($($game.HomeRecord))"
    $venue = if ($game.Venue) { 
        if ($game.Broadcast) { "$($game.Venue) [$($game.Broadcast)]" } else { $game.Venue }
    } else { 
        if ($game.Broadcast) { "[$($game.Broadcast)]" } else { "-" }
    }
    
    $table += [PSCustomObject]@{
        "Time (CST)" = $game.Time
        "Away Team" = $awayTeam
        "Home Team" = $homeTeam
        "Venue/Broadcast" = $venue
    }
}

$table | Format-Table -AutoSize

Write-Host ""
Write-Host "=========================================================================================================="
Write-Host "  ANALYSIS STATUS"
Write-Host "=========================================================================================================="
Write-Host ""
Write-Host "To generate predictions, the system requires:" -ForegroundColor Yellow
Write-Host "  1. Games added to database with correct team name matching"
Write-Host "  2. Team ratings synced from Barttorvik (365 teams)"
Write-Host "  3. Odds synced from The Odds API (Pinnacle/Bovada)"
Write-Host ""
Write-Host "Once data is synced, predictions will be generated automatically." -ForegroundColor Green
Write-Host ""
Write-Host "Service URL: $serviceUrl" -ForegroundColor Cyan
Write-Host ""

