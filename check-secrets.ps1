$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$secretsDir = Join-Path $root "secrets"
# Docker Compose secrets (single source of truth)
# NOTE: These are intentionally gitignored and must exist locally for `.\predict.bat`.
$secrets = @(
  'db_password.txt',
  'redis_password.txt',
  'odds_api_key.txt',
  'teams_webhook_url.txt',
  'teams_webhook_secret.txt'
)
$failed = $false
foreach ($s in $secrets) {
  $p = Join-Path $secretsDir $s
  if (!(Test-Path -LiteralPath $p)) { Write-Error "Missing secret file: secrets\$s"; $failed = $true; continue }
  $len = (Get-Item -LiteralPath $p).Length
  # Odds API key is required for predictions; Teams files may be empty if not using --teams.
  if ($s -eq 'odds_api_key.txt' -and $len -lt 10) { Write-Error "Empty/invalid secret file: secrets\$s"; $failed = $true }
}
if ($failed) { exit 1 }

# Output non-sensitive confirmation (filenames + SHA256 of contents)
Write-Host "All required secret files exist and are non-empty."
foreach ($s in $secrets) {
  $hash = Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $secretsDir $s)
  Write-Host ("secrets/{0}: {1}" -f $s, $hash.Hash)
}
