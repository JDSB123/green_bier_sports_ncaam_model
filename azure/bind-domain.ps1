<#
Bind a custom domain (e.g. www.greenbiersportventures.com) to the web Container App with a managed certificate.

IMPORTANT: You must add DNS records first at your registrar.

Typical steps:
1) Create/Update CNAME:
   www -> <webAppFqdn>
2) Create TXT for domain verification (Azure returns the value):
   asuid.www -> <verificationToken>
3) Then run this script again with -SkipDnsInstructions to proceed to binding.

This script is intentionally best-effort and safe to re-run.
#>

param(
  [Parameter(Mandatory=$false)]
  [string]$ResourceGroup = 'NCAAM-GBSV-MODEL-RG',

  [Parameter(Mandatory=$false)]
  [string]$WebAppName = 'ncaam-stable-web',

  [Parameter(Mandatory=$true)]
  [string]$Hostname,

  [Parameter(Mandatory=$false)]
  [switch]$SkipDnsInstructions
)

$ErrorActionPreference = 'Stop'

Write-Host "Binding hostname '$Hostname' to Container App '$WebAppName' in RG '$ResourceGroup'" -ForegroundColor Cyan

# 1) Add hostname (this returns a verification token if not verified)
$add = az containerapp hostname add --resource-group $ResourceGroup --name $WebAppName --hostname $Hostname -o json | ConvertFrom-Json

# Some CLI versions return 'validationToken' or nested fields. Handle both.
$token = $null
if ($add.validationToken) { $token = $add.validationToken }
elseif ($add.properties -and $add.properties.validationToken) { $token = $add.properties.validationToken }

if (-not $SkipDnsInstructions -and $token) {
  $fqdn = az containerapp show --resource-group $ResourceGroup --name $WebAppName --query "properties.configuration.ingress.fqdn" -o tsv

  Write-Host "\nDNS REQUIRED (do this at your domain registrar):" -ForegroundColor Yellow
  Write-Host "- CNAME:  www  ->  $fqdn" -ForegroundColor Yellow
  Write-Host "- TXT:    asuid.www  ->  $token" -ForegroundColor Yellow
  Write-Host "\nAfter DNS propagates, re-run with -SkipDnsInstructions to bind TLS." -ForegroundColor Yellow
  exit 0
}

# 2) Bind with managed certificate
Write-Host "Requesting managed certificate + binding..." -ForegroundColor Cyan
az containerapp hostname bind --resource-group $ResourceGroup --name $WebAppName --hostname $Hostname --environment-only false --output none

Write-Host "[OK] Bound: https://$Hostname" -ForegroundColor Green
