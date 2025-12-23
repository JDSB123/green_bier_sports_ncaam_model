# Non-Interactive Docker Secrets Setup for NCAAM v33 Model
# Usage: Set environment variables OR create a .env file before running
# Example: $env:DB_PASSWORD="your_password"; .\setup-docker-secrets-noninteractive.ps1

Write-Host "Setting up Docker secrets (non-interactive mode)" -ForegroundColor Cyan
Write-Host ""

# Function to get value from env or .env file
function Get-SecretValue {
    param($EnvVarName, $DefaultValue = $null, $Required = $false)
    
    $value = [System.Environment]::GetEnvironmentVariable($EnvVarName)
    
    if ([string]::IsNullOrWhiteSpace($value) -and (Test-Path ".env")) {
        $envContent = Get-Content ".env" -ErrorAction SilentlyContinue
        $line = $envContent | Where-Object { $_ -match "^$EnvVarName=" }
        if ($line) {
            $value = ($line -split "=", 2)[1].Trim('"').Trim("''")
        }
    }
    
    if ([string]::IsNullOrWhiteSpace($value)) {
        if ($Required) {
            Write-Host "ERROR: $EnvVarName is required but not set!" -ForegroundColor Red
            exit 1
        }
        $value = $DefaultValue
    }
    
    return $value
}

# Create secrets directory if it doesn't exist
if (!(Test-Path "secrets")) {
    New-Item -ItemType Directory -Path "secrets" | Out-Null
}

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

# Get secret values from environment variables or .env file
$db_password = Get-SecretValue "DB_PASSWORD" -DefaultValue "ncaam_secure_$(Get-Random)" -Required $false
$redis_password = Get-SecretValue "REDIS_PASSWORD" -DefaultValue "redis_secure_$(Get-Random)" -Required $false
$odds_api_key = Get-SecretValue "ODDS_API_KEY" -DefaultValue "test_key" -Required $false
$teams_url = Get-SecretValue "TEAMS_WEBHOOK_URL" -DefaultValue "https://example.com/webhook" -Required $false
$teams_secret = Get-SecretValue "TEAMS_WEBHOOK_SECRET" -DefaultValue "webhook_secret" -Required $false

# Write secrets to files
Set-Content -Path "secrets\db_password.txt" -Value $db_password -NoNewline -Encoding UTF8
Set-Content -Path "secrets\redis_password.txt" -Value $redis_password -NoNewline -Encoding UTF8
Set-Content -Path "secrets\odds_api_key.txt" -Value $odds_api_key -NoNewline -Encoding UTF8
Set-Content -Path "secrets\teams_webhook_url.txt" -Value $teams_url -NoNewline -Encoding UTF8
Set-Content -Path "secrets\teams_webhook_secret.txt" -Value $teams_secret -NoNewline -Encoding UTF8

Write-Host ""
Write-Host "✓ Secrets created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Secret files created:"
Get-ChildItem secrets\*.txt | ForEach-Object { 
    $maskedValue = if ($_.Length -gt 0) { "*".PadRight([Math]::Min($_.Length, 20), "*") } else { "(empty)" }
    Write-Host "  - $($_.Name): $maskedValue" -ForegroundColor Cyan 
}
Write-Host ""
Write-Host "To use custom values, either:" -ForegroundColor Yellow
Write-Host "  1. Set environment variables: `$env:DB_PASSWORD=''yourpass''; .\setup-docker-secrets-noninteractive.ps1" -ForegroundColor Gray
Write-Host "  2. Create a .env file with: DB_PASSWORD=yourpass" -ForegroundColor Gray
