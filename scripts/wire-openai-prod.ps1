# Wire OPENAI_API_KEY from Secret Manager into the django-backend Cloud Run service.
# Run after creating the OPENAI_API_KEY secret in GCP Secret Manager.
#
# Usage:
#   .\scripts\wire-openai-prod.ps1

$ErrorActionPreference = "Stop"
$Project = "communib"
$Region = "us-central1"
$BackendService = "django-backend"
$SecretName = "OPENAI_API_KEY"

Write-Host "=== Wire OpenAI secret to Cloud Run ===" -ForegroundColor Cyan
Write-Host "Project: $Project  Service: $BackendService  Region: $Region" -ForegroundColor Yellow

$activeAccount = gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>$null
if (-not $activeAccount) {
    Write-Host "Not logged in to gcloud. Run: gcloud auth login" -ForegroundColor Red
    exit 1
}

Write-Host "Checking secret $SecretName exists..." -ForegroundColor Cyan
gcloud secrets describe $SecretName --project $Project --quiet | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Secret $SecretName not found in project $Project." -ForegroundColor Red
    exit 1
}

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
Write-Host "Service account: $ServiceAccount" -ForegroundColor Green

Write-Host "Granting secretAccessor on $SecretName..." -ForegroundColor Cyan
gcloud secrets add-iam-policy-binding $SecretName `
    --project $Project `
    --member="serviceAccount:$ServiceAccount" `
    --role="roles/secretmanager.secretAccessor" `
    --quiet
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Updating Cloud Run service (no image change)..." -ForegroundColor Cyan
gcloud run services update $BackendService `
    --region $Region `
    --project $Project `
    --update-secrets="${SecretName}=${SecretName}:latest" `
    --update-env-vars="OPENAI_MODEL=gpt-4o-mini,PAID_AI_MODEL=gpt-4o" `
    --quiet
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`nDone. Paid AI meetings will use OpenAI when ai_mode=paid." -ForegroundColor Green
Write-Host "Verify: create a meeting with AI mode 'Paid AI Model' and run a session."
