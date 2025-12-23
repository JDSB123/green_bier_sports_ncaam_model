$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$secrets = @(
  'ncaam_v33_model_db_password',
  'ncaam_v33_model_redis_password',
  'ncaam_v33_model_odds_api_key'
)
$failed = $false
foreach ($s in $secrets) {
  $p = Join-Path $root $s
  if (!(Test-Path -LiteralPath $p)) { Write-Error "Missing secret file: $s"; $failed = $true; continue }
  $len = (Get-Item -LiteralPath $p).Length
  if ($len -lt 1) { Write-Error "Empty secret file: $s"; $failed = $true }
}
if ($failed) { exit 1 }

# Output non-sensitive confirmation (filenames + SHA256 of contents)
Write-Host "All required secret files exist and are non-empty."
foreach ($s in $secrets) {
  $hash = Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $root $s)
  Write-Host ("{0}: {1}" -f $s, $hash.Hash)
}
