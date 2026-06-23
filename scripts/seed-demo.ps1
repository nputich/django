$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:APP_ENV = "local"
Set-Location (Join-Path $Root "backend")

$Python = Join-Path $Root "venv\Scripts\python.exe"
& $Python manage.py migrate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python manage.py seed_demo_data @args
