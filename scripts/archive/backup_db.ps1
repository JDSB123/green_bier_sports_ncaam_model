param(
  [string]$OutDir = "backups",
  [string]$DbName = $env:DB_NAME,
  [string]$DbUser = $env:DB_USER
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($DbName)) { $DbName = "ncaam" }
if ([string]::IsNullOrWhiteSpace($DbUser)) { $DbUser = "ncaam" }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $OutDir "$DbName`_$ts.sql"

Write-Host "Backing up DB '$DbName' to $outFile"

# Uses the db_password Docker secret inside the Postgres container.
docker compose exec -T postgres sh -c "export PGPASSWORD=\$(cat /run/secrets/db_password); pg_dump -U $DbUser -d $DbName --no-owner --no-privileges" `
  | Out-File -FilePath $outFile -Encoding utf8

Write-Host "OK"
