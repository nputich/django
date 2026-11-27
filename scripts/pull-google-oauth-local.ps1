# Pull Google OAuth client credentials from Secret Manager for local Docker.
# Does not print secret values.
#
# Secret Manager (communib):
#   Google_ID     -> secrets/google_oauth_client_id.txt
#   Google_Secret -> secrets/google_oauth_client_secret.txt
#
# Usage:
#   .\scripts\pull-google-oauth-local.ps1
#   docker compose up -d --force-recreate communib-backend

$ErrorActionPreference = "Stop"
$Project = "communib"
$Root = Split-Path -Parent $PSScriptRoot
$SecretsDir = Join-Path $Root "secrets"

$Pairs = @(
    @{ Secret = "Google_ID"; File = "google_oauth_client_id.txt" },
    @{ Secret = "Google_Secret"; File = "google_oauth_client_secret.txt" }
)

Write-Host "Pulling Google OAuth secrets from project $Project" -ForegroundColor Cyan
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

Write-Host "`nNext: docker compose up -d --force-recreate communib-backend" -ForegroundColor Cyan
Write-Host "Local redirect URI: http://localhost:8001/api/youtube/oauth/callback/"
