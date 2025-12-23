Write-Host "Setting up Docker secrets for NCAAM v33 Model" -ForegroundColor Cyan
Write-Host ""

# Remove old directories if they exist
"db_password.txt", "redis_password.txt", "odds_api_key.txt", "teams_webhook_url.txt", "teams_webhook_secret.txt" | ForEach-Object {
    $path = "secrets\$_"
    if (Test-Path $path) {
        if ((Get-Item $path).PSIsContainer) {
            Write-Host "Removing directory: $path" -ForegroundColor Yellow
            Remove-Item $path -Recurse -Force
        }
    }
}

Write-Host ""
Write-Host "Enter secrets (or press Enter to use default for optional):" -ForegroundColor Green
Write-Host ""

# DB Password (required)
$db_password = Read-Host "DB Password (required)"
if ([string]::IsNullOrWhiteSpace($db_password)) { $db_password = "ncaam_secure_$(Get-Random)" }
Set-Content -Path "secrets\db_password.txt" -Value $db_password -NoNewline -Encoding UTF8

# Redis Password (required)
$redis_password = Read-Host "Redis Password (required)"
if ([string]::IsNullOrWhiteSpace($redis_password)) { $redis_password = "redis_secure_$(Get-Random)" }
Set-Content -Path "secrets\redis_password.txt" -Value $redis_password -NoNewline -Encoding UTF8

# Odds API Key (required for odds fetching)
do {
    $odds_api_key = Read-Host "Odds API Key (REQUIRED - get from https://the-odds-api.com)"
    if ([string]::IsNullOrWhiteSpace($odds_api_key)) {
        Write-Host "ERROR: Odds API Key is required!" -ForegroundColor Red
    }
} while ([string]::IsNullOrWhiteSpace($odds_api_key))
Set-Content -Path "secrets\odds_api_key.txt" -Value $odds_api_key -NoNewline -Encoding UTF8

# Teams Webhook (optional)
$teams_url = Read-Host "Teams Webhook URL (optional, press Enter to skip)"
if ([string]::IsNullOrWhiteSpace($teams_url)) { $teams_url = "" }
Set-Content -Path "secrets\teams_webhook_url.txt" -Value $teams_url -NoNewline -Encoding UTF8

# Teams Webhook Secret (optional)
$teams_secret = Read-Host "Teams Webhook Secret (optional, press Enter to skip)"
if ([string]::IsNullOrWhiteSpace($teams_secret)) { $teams_secret = "" }
Set-Content -Path "secrets\teams_webhook_secret.txt" -Value $teams_secret -NoNewline -Encoding UTF8

Write-Host ""
Write-Host "✅ Secrets created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Secret files created:"
Get-ChildItem secrets\*.txt | ForEach-Object { Write-Host "  - $($_.Name)" -ForegroundColor Cyan }
