# Build, push, and deploy communib to Google Cloud Run.
# Prereqs: gcloud auth login, gcloud auth configure-docker gcr.io
# Optional migrations: start Cloud SQL proxy, then run prod-migrate.ps1 first.
#
# Usage:
#   .\scripts\deploy-prod.ps1              # full build + push + deploy
#   .\scripts\deploy-prod.ps1 -SkipBuild     # push + deploy existing local images

param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Project = "communib"
$Region = "us-central1"
$BackendImage = "gcr.io/$Project/communib-backend:latest"
$FrontendImage = "gcr.io/$Project/communib-frontend:latest"

Write-Host "=== communib production deploy ===" -ForegroundColor Cyan
Write-Host "Project: $Project  Region: $Region" -ForegroundColor Yellow

$activeAccount = gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>$null
if (-not $activeAccount) {
    Write-Host "Not logged in to gcloud. Run these first:" -ForegroundColor Red
    Write-Host "  gcloud auth login"
    Write-Host "  gcloud auth configure-docker gcr.io"
    exit 1
}
Write-Host "gcloud account: $activeAccount" -ForegroundColor Green

if (-not $SkipBuild) {
    Write-Host "`n[1/4] Building backend image..." -ForegroundColor Cyan
    Set-Location (Join-Path $Root "backend")
    docker buildx build --platform linux/amd64 -t $BackendImage --load .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "`n[2/4] Building frontend image..." -ForegroundColor Cyan
    Set-Location (Join-Path $Root "frontend")
    docker buildx build --no-cache --platform linux/amd64 -t $FrontendImage --load .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "`nSkipping build (using local images tagged latest)." -ForegroundColor Yellow
}

Write-Host "`n[3/4] Pushing images to gcr.io..." -ForegroundColor Cyan
docker push $BackendImage
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker push $FrontendImage
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[4/4] Deploying Cloud Run services..." -ForegroundColor Cyan

$BackendService = "django-backend"
$ServiceAccount = (
    gcloud run services describe $BackendService `
        --region $Region `
        --project $Project `
        --format="value(spec.template.spec.serviceAccountName)" 2>$null
).Trim()
if (-not $ServiceAccount) {
    $ProjectNumber = (gcloud projects describe $Project --format="value(projectNumber)").Trim()
    $ServiceAccount = "$ProjectNumber-compute@developer.gserviceaccount.com"
}
Write-Host "Backend service account: $ServiceAccount" -ForegroundColor Yellow

Write-Host "Ensuring Secret Manager access for OPENAI_API_KEY..." -ForegroundColor Cyan
# gcloud writes success notices to stderr; PowerShell Stop mode treats that as fatal.
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$iamOut = & gcloud secrets add-iam-policy-binding OPENAI_API_KEY `
    --project $Project `
    --member="serviceAccount:$ServiceAccount" `
    --role="roles/secretmanager.secretAccessor" `
    --quiet 2>&1
$iamCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($iamCode -ne 0) {
    Write-Host "Could not bind OPENAI_API_KEY (secret may not exist yet)." -ForegroundColor Yellow
    Write-Host ($iamOut | Out-String)
} else {
    Write-Host "OPENAI_API_KEY accessor binding OK." -ForegroundColor Green
}

Write-Host "Deploying backend..." -ForegroundColor Cyan
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$backendOut = & gcloud run deploy $BackendService `
    --image $BackendImage `
    --region $Region `
    --project $Project `
    --update-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest" `
    --update-env-vars="OPENAI_MODEL=gpt-4o-mini,PAID_AI_MODEL=gpt-4o" `
    --quiet 2>&1
$backendCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($backendCode -ne 0) {
    Write-Host ($backendOut | Out-String) -ForegroundColor Red
    exit $backendCode
}
Write-Host ($backendOut | Out-String)

Write-Host "Deploying frontend..." -ForegroundColor Cyan
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$frontendOut = & gcloud run deploy communib `
    --image $FrontendImage `
    --region $Region `
    --project $Project `
    --quiet 2>&1
$frontendCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($frontendCode -ne 0) {
    Write-Host ($frontendOut | Out-String) -ForegroundColor Red
    exit $frontendCode
}
Write-Host ($frontendOut | Out-String)

Write-Host "`nDone. Test:" -ForegroundColor Green
Write-Host "  https://communib.com"
Write-Host "  https://django-backend-460809694305.us-central1.run.app"
