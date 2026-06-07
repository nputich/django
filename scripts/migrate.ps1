$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:APP_ENV = "local"
Set-Location (Join-Path $Root "backend")
& (Join-Path $Root "venv\Scripts\python.exe") manage.py migrate @args
