# Migrate production DB, then build/push/deploy backend + frontend to Cloud Run.
# Prereqs (run once if auth expired):
#   gcloud auth login
#   gcloud auth application-default login
#   gcloud auth configure-docker gcr.io
#
# Usage:
#   .\scripts\deploy-all-prod.ps1
#   .\scripts\deploy-all-prod.ps1 -SkipBuild

param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ProxyExe = Join-Path $Root "scripts\bin\cloud-sql-proxy.exe"
$Instance = "communib:us-central1:postgres"
$ProxyPort = 5433

Write-Host "=== communib: migrate + deploy ===" -ForegroundColor Cyan

$activeAccount = gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>$null
if (-not $activeAccount) {
    Write-Host "gcloud is not authenticated. Run:" -ForegroundColor Red
    Write-Host "  gcloud auth login"
    Write-Host "  gcloud auth application-default login"
    exit 1
}
Write-Host "gcloud account: $activeAccount" -ForegroundColor Green

$proxyJob = $null
if (-not (Get-NetTCPConnection -LocalPort $ProxyPort -State Listen -ErrorAction SilentlyContinue)) {
    if (-not (Test-Path $ProxyExe)) {
        Write-Host "Cloud SQL proxy not found at $ProxyExe" -ForegroundColor Red
        exit 1
    }
    Write-Host "Starting Cloud SQL Auth Proxy on port $ProxyPort..." -ForegroundColor Cyan
    $proxyJob = Start-Job -ScriptBlock {
        param($exe, $instance, $port)
        & $exe $instance --port $port
    } -ArgumentList $ProxyExe, $Instance, $ProxyPort
    Start-Sleep -Seconds 4
    if (-not (Get-NetTCPConnection -LocalPort $ProxyPort -State Listen -ErrorAction SilentlyContinue)) {
        Receive-Job $proxyJob -ErrorAction SilentlyContinue | Write-Host
        Write-Host "Cloud SQL proxy failed to start. Run application-default login:" -ForegroundColor Red
        Write-Host "  gcloud auth application-default login"
        if ($proxyJob) { Stop-Job $proxyJob; Remove-Job $proxyJob }
        exit 1
    }
}

try {
    Write-Host "`n[1/2] Production migrations..." -ForegroundColor Cyan
    & (Join-Path $Root "scripts\prod-migrate.ps1")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "`n[2/2] Production deploy..." -ForegroundColor Cyan
    if ($SkipBuild) {
        & (Join-Path $Root "scripts\deploy-prod.ps1") -SkipBuild
    } else {
        & (Join-Path $Root "scripts\deploy-prod.ps1")
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "`nAll done: migrations applied and Cloud Run updated." -ForegroundColor Green
}
finally {
    if ($proxyJob) {
        Stop-Job $proxyJob -ErrorAction SilentlyContinue
        Remove-Job $proxyJob -ErrorAction SilentlyContinue
    }
}
