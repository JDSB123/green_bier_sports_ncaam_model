$ErrorActionPreference = "Stop"
function Read-Secret([string]$label) {
  $s = Read-Host "Enter $label" -AsSecureString
  if (!$s) { throw "No input provided for $label" }
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
  try { [Runtime.InteropServices.Marshal]::PtrToStringUni($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}
function Write-SecretFile([string]$path, [string]$value) {
  Set-Content -NoNewline -Encoding UTF8 -LiteralPath $path -Value $value
  # Restrict ACL to current user read-only
  & icacls $path /inheritance:r | Out-Null
  $user = "$env:UserDomain\$env:UserName"
  & icacls $path /grant:r "$user":R | Out-Null
}
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$map = @{
  'ncaam_v33_model_db_password'     = 'Postgres password';
  'ncaam_v33_model_redis_password'  = 'Redis password';
  'ncaam_v33_model_odds_api_key'    = 'Odds API key';
}
foreach ($kvp in $map.GetEnumerator()) {
  $file = Join-Path $root $kvp.Key
  if (Test-Path -LiteralPath $file) {
    $resp = Read-Host "Secret file '$($kvp.Key)' exists. Overwrite? (y/N)"
    if ($resp -ne 'y' -and $resp -ne 'Y') { continue }
  }
  $val = Read-Secret $kvp.Value
  Write-SecretFile -path $file -value $val
}
Write-Host "Secrets written. Run: .\\check-secrets.ps1"
