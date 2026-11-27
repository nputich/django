# Bootstrap production DB: migrate + demo seed (superuser, org, surveys, meetings, codes).
# Uses GCP Secret Manager for DB credentials.
#
# Option A — Cloud SQL Auth Proxy (recommended):
#   gcloud auth application-default login
#   .\scripts\bin\cloud-sql-proxy.exe communib:us-central1:postgres --port 5433
#   .\scripts\prod-bootstrap.ps1
#
# Option B — Direct IP with SSL (your IP must be authorized in Cloud SQL):
#   Set DB_HOST=35.225.116.19, DB_PORT=5432, DB_SSLMODE=require in .env.production

param(
    [string]$SuperuserPassword = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Project = "communib"

Write-Host "Loading DB credentials from Secret Manager ($Project)..." -ForegroundColor Cyan
$env:DB_USER = (gcloud secrets versions access latest --secret=DB_USER --project=$Project).Trim()
$env:DB_NAME = (gcloud secrets versions access latest --secret=DB_NAME --project=$Project).Trim()
$env:DB_PWD = (gcloud secrets versions access latest --secret=DB_PWD --project=$Project).Trim()

if (-not $env:DB_HOST) { $env:DB_HOST = "127.0.0.1" }
if (-not $env:DB_PORT) { $env:DB_PORT = "5433" }

if ($SuperuserPassword) {
    $env:DJANGO_SUPERUSER_PASSWORD = $SuperuserPassword
} elseif (-not $env:DJANGO_SUPERUSER_PASSWORD) {
    $env:DJANGO_SUPERUSER_PASSWORD = "CommunibAdmin2026!"
    Write-Host "Using default superuser password (set -SuperuserPassword or DJANGO_SUPERUSER_PASSWORD to override)" -ForegroundColor Yellow
}

$env:APP_ENV = "production"
Set-Location (Join-Path $Root "backend")
$Python = Join-Path $Root "venv\Scripts\python.exe"

Write-Host "Running migrations..." -ForegroundColor Cyan
& $Python manage.py migrate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Seeding demo data..." -ForegroundColor Cyan
& $Python manage.py seed_demo_data
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Production bootstrap complete." -ForegroundColor Green
