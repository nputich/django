# Pull GMAIL_KEY from Secret Manager into secrets/gmail_key.txt for local Docker SMTP.
# Does not print the secret value.
#
# Usage:
#   .\scripts\pull-gmail-key-local.ps1

$ErrorActionPreference = "Stop"
$Project = "communib"
$SecretName = "GMAIL_KEY"
$Root = Split-Path -Parent $PSScriptRoot
$OutFile = Join-Path $Root "secrets\gmail_key.txt"

Write-Host "Pulling $SecretName from project $Project → secrets/gmail_key.txt" -ForegroundColor Cyan

New-Item -ItemType Directory -Force -Path (Split-Path $OutFile) | Out-Null

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$value = & gcloud secrets versions access latest --secret=$SecretName --project=$Project 2>&1
$code = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($code -ne 0) {
    Write-Host ($value | Out-String) -ForegroundColor Red
    exit $code
}

# Normalize: App Passwords are often shown with spaces; Gmail accepts either.
$normalized = (($value | Out-String).Trim() -replace "\s+", "")
[System.IO.File]::WriteAllText($OutFile, $normalized)

Write-Host "Wrote secrets/gmail_key.txt ($($normalized.Length) chars, value not shown)." -ForegroundColor Green
Write-Host "Next: docker compose up -d --build communib-backend"
Write-Host "Then open http://localhost:10001/contact"
