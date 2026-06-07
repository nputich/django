$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:APP_ENV = "production"
Set-Location (Join-Path $Root "backend")
Write-Host "Using APP_ENV=production (.env.production)" -ForegroundColor Yellow
& (Join-Path $Root "venv\Scripts\python.exe") manage.py @args
