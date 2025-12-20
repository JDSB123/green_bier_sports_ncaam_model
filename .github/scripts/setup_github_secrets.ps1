# Setup GitHub Secrets for NCAAM CI/CD
# Prerequisites: Install GitHub CLI (gh)
# Usage: .\setup_github_secrets.ps1

param(
    [string]$Owner = "JDSB123",
    [string]$Repo = "green_bier_sports_ncaam_model",
    [string]$AcrName = "greenbieracr",
    [string]$AcrUsername = "",
    [string]$AcrPassword = "",
    [string]$AzureCredentials = "",
    [string]$OddsApiKey = "",
    [string]$DbPassword = "",
    [string]$RedisPassword = ""
)

# Color output
$ErrorActionPreference = "Stop"
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Error { Write-Host $args -ForegroundColor Red }
function Write-Info { Write-Host $args -ForegroundColor Cyan }

Write-Info "Setting up GitHub Secrets for $Owner/$Repo..."

# Verify gh CLI is installed
try {
    gh --version | Out-Null
} catch {
    Write-Error "GitHub CLI (gh) not found. Install from https://cli.github.com/"
    exit 1
}

# Check if authenticated
try {
    gh auth status | Out-Null
} catch {
    Write-Info "Authenticating with GitHub..."
    gh auth login
}

# Function to set secret
function Set-GithubSecret {
    param(
        [string]$SecretName,
        [string]$SecretValue
    )
    
    if ([string]::IsNullOrWhiteSpace($SecretValue)) {
        Write-Error "Secret value for $SecretName is empty. Skipping..."
        return $false
    }
    
    try {
        $SecretValue | gh secret set $SecretName --repo "$Owner/$Repo"
        Write-Success "✓ Set secret: $SecretName"
        return $true
    } catch {
        Write-Error "✗ Failed to set $SecretName : $_"
        return $false
    }
}

# Set secrets
Write-Info "`nSetting GitHub Secrets..."

Set-GithubSecret "AZURE_ACR_NAME" $AcrName
Set-GithubSecret "AZURE_ACR_USERNAME" $AcrUsername
Set-GithubSecret "AZURE_ACR_PASSWORD" $AcrPassword
Set-GithubSecret "AZURE_CREDENTIALS" $AzureCredentials
Set-GithubSecret "ODDS_API_KEY" $OddsApiKey
Set-GithubSecret "DB_PASSWORD" $DbPassword
Set-GithubSecret "REDIS_PASSWORD" $RedisPassword

Write-Success "`nGitHub Secrets setup complete!"
Write-Info "Verify secrets at: https://github.com/$Owner/$Repo/settings/secrets/actions"
