# Wire Gmail contact-form SMTP into django-backend Cloud Run.
# Prereq: Secret Manager secret GMAIL_KEY = Gmail App Password
#
# Usage:
#   .\scripts\wire-email-prod.ps1

$ErrorActionPreference = "Stop"
$Project = "communib"
$Region = "us-central1"
$BackendService = "django-backend"
$SecretName = "GMAIL_KEY"

Write-Host "=== Wire Gmail SMTP to Cloud Run ===" -ForegroundColor Cyan
Write-Host "Project: $Project  Service: $BackendService  Secret: $SecretName" -ForegroundColor Yellow

$activeAccount = gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>$null
if (-not $activeAccount) {
    Write-Host "Not logged in to gcloud. Run: gcloud auth login" -ForegroundColor Red
    exit 1
}
Write-Host "gcloud account: $activeAccount" -ForegroundColor Green

Write-Host "Checking secret $SecretName exists..." -ForegroundColor Cyan
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& gcloud secrets describe $SecretName --project $Project --quiet 2>&1 | Out-Null
$descCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($descCode -ne 0) {
    Write-Host "Secret $SecretName not found in project $Project." -ForegroundColor Red
    Write-Host "Create it in Secret Manager with the Gmail App Password, then re-run."
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
$ErrorActionPreference = "Continue"
$iamOut = & gcloud secrets add-iam-policy-binding $SecretName `
    --project $Project `
    --member="serviceAccount:$ServiceAccount" `
    --role="roles/secretmanager.secretAccessor" `
    --quiet 2>&1
$iamCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($iamCode -ne 0) {
    Write-Host ($iamOut | Out-String) -ForegroundColor Red
    exit $iamCode
}
Write-Host "IAM binding OK." -ForegroundColor Green

Write-Host "Updating Cloud Run service (maps GMAIL_KEY → EMAIL_HOST_PASSWORD)..." -ForegroundColor Cyan
$ErrorActionPreference = "Continue"
$updateOut = & gcloud run services update $BackendService `
    --region $Region `
    --project $Project `
    --update-secrets="EMAIL_HOST_PASSWORD=${SecretName}:latest" `
    --update-env-vars="EMAIL_HOST=smtp.gmail.com,EMAIL_PORT=587,EMAIL_USE_TLS=true,EMAIL_HOST_USER=contactcommunib@gmail.com,CONTACT_INBOX_EMAIL=contactcommunib@gmail.com,DEFAULT_FROM_EMAIL=contactcommunib@gmail.com" `
    --quiet 2>&1
$updateCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($updateCode -ne 0) {
    Write-Host ($updateOut | Out-String) -ForegroundColor Red
    exit $updateCode
}
Write-Host ($updateOut | Out-String)

Write-Host "`nDone. Test: https://communib.com/contact" -ForegroundColor Green
Write-Host "Messages should arrive at contactcommunib@gmail.com (check spam)."
