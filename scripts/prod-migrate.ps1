# Run production migrations using credentials from GCP Secret Manager.
# Option A (recommended): Cloud SQL Auth Proxy on 127.0.0.1:5433
#   1. gcloud auth application-default login
#   2. In another terminal:
#      .\scripts\bin\cloud-sql-proxy.exe communib:us-central1:postgres --port 5433
#   3. .\scripts\prod-migrate.ps1
#
# Option B: Direct to Cloud SQL public IP (requires SSL + your IP authorized in Cloud SQL)
#   Set in .env.production: DB_SSLMODE=require and correct DB_USER (communib, not postgres)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Project = "communib"

Write-Host "Loading DB credentials from Secret Manager ($Project)..." -ForegroundColor Cyan
$env:DB_USER = (gcloud secrets versions access latest --secret=DB_USER --project=$Project).Trim()
$env:DB_NAME = (gcloud secrets versions access latest --secret=DB_NAME --project=$Project).Trim()
$env:DB_PWD = (gcloud secrets versions access latest --secret=DB_PWD --project=$Project).Trim()

if (-not $env:DB_HOST) {
    # Default to proxy port if not set in .env.production
    $env:DB_HOST = "127.0.0.1"
}
if (-not $env:DB_PORT) {
    $env:DB_PORT = "5433"
}

$env:APP_ENV = "production"
Set-Location (Join-Path $Root "backend")

Write-Host "DB_HOST=$($env:DB_HOST) DB_PORT=$($env:DB_PORT) DB_USER=$($env:DB_USER) DB_NAME=$($env:DB_NAME)" -ForegroundColor Yellow
& (Join-Path $Root "venv\Scripts\python.exe") manage.py migrate @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running seed_resource_types..." -ForegroundColor Cyan
& (Join-Path $Root "venv\Scripts\python.exe") manage.py seed_resource_types @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running seed_directory_data (geo + categories)..." -ForegroundColor Cyan
& (Join-Path $Root "venv\Scripts\python.exe") manage.py seed_directory_data @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
