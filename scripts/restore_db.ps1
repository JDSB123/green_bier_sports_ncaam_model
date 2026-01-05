param(
  [Parameter(Mandatory = $true)]
  [string]$Path,
  [string]$DbName = $env:DB_NAME,
  [string]$DbUser = $env:DB_USER
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Path)) {
  throw "Backup file not found: $Path"
}

if ([string]::IsNullOrWhiteSpace($DbName)) { $DbName = "ncaam" }
if ([string]::IsNullOrWhiteSpace($DbUser)) { $DbUser = "ncaam" }

Write-Host "Restoring $Path into DB '$DbName' (this will execute SQL)..."

Get-Content -LiteralPath $Path -Raw `
  | docker compose exec -T postgres sh -c "export PGPASSWORD=\$(cat /run/secrets/db_password); psql -U $DbUser -d $DbName -v ON_ERROR_STOP=1"

Write-Host "OK"

