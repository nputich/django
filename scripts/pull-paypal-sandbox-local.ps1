# Pull PayPal sandbox credentials from Secret Manager for local Docker.
# Does not print secret values.
#
# Usage:
#   .\scripts\pull-paypal-sandbox-local.ps1
#   docker compose up -d --build communib-backend

$ErrorActionPreference = "Stop"
$Project = "communib"
$Root = Split-Path -Parent $PSScriptRoot
$SecretsDir = Join-Path $Root "secrets"

$Pairs = @(
    @{ Secret = "PAYPAL_SANDBOX_CLIENT_ID"; File = "paypal_sandbox_client_id.txt" },
    @{ Secret = "PAYPAL_SANDBOX_SECRET"; File = "paypal_sandbox_secret.txt" },
    @{ Secret = "PAYPAL_SANDBOX_WEBHOOK_ID"; File = "paypal_sandbox_webhook_id.txt" }
)

Write-Host "Pulling PayPal sandbox secrets from project $Project" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $SecretsDir | Out-Null

foreach ($pair in $Pairs) {
    $OutFile = Join-Path $SecretsDir $pair.File
    Write-Host "  $($pair.Secret) -> secrets\$($pair.File)" -ForegroundColor Yellow
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $value = & gcloud secrets versions access latest --secret=$($pair.Secret) --project=$Project 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($code -ne 0) {
        Write-Host ($value | Out-String) -ForegroundColor Red
        exit $code
    }
    $normalized = (($value | Out-String).Trim())
    [System.IO.File]::WriteAllText($OutFile, $normalized)
    Write-Host "  Wrote $($pair.File) ($($normalized.Length) chars, value not shown)." -ForegroundColor Green
}

Write-Host "`nNext: docker compose up -d --build communib-backend" -ForegroundColor Cyan
Write-Host "Billing page will show a sandbox banner; checkout uses PayPal sandbox."
