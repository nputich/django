# Wire PayPal subscription checkout secrets into django-backend Cloud Run.
#
# Google Secret Manager (communib):
#   PAYPAL_LIVE_CLIENT_ID / PAYPAL_LIVE_SECRET / PAYPAL_LIVE_WEBHOOK_ID
#   PAYPAL_SANDBOX_CLIENT_ID / PAYPAL_SANDBOX_SECRET / PAYPAL_SANDBOX_WEBHOOK_ID
#
# Mapped into app env (what Django reads):
#   PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET / PAYPAL_WEBHOOK_ID
# plus PAYPAL_MODE, PAYPAL_SUBSCRIPTIONS_ENABLED, FRONTEND_BASE_URL
#
# You only need to create the secrets in Secret Manager.
# This script does the Cloud Run "mapping" for you.
#
# Usage:
#   .\scripts\wire-paypal-prod.ps1              # live (default)
#   .\scripts\wire-paypal-prod.ps1 -Mode sandbox
#   .\scripts\wire-paypal-prod.ps1 -Mode live

param(
    [ValidateSet("live", "sandbox")]
    [string]$Mode = "live"
)

$ErrorActionPreference = "Stop"
$Project = "communib"
$Region = "us-central1"
$BackendService = "django-backend"
$FrontendBaseUrl = "https://communib.com"

if ($Mode -eq "live") {
    $ClientSecretName = "PAYPAL_LIVE_CLIENT_ID"
    $SecretSecretName = "PAYPAL_LIVE_SECRET"
    $WebhookSecretName = "PAYPAL_LIVE_WEBHOOK_ID"
} else {
    $ClientSecretName = "PAYPAL_SANDBOX_CLIENT_ID"
    $SecretSecretName = "PAYPAL_SANDBOX_SECRET"
    $WebhookSecretName = "PAYPAL_SANDBOX_WEBHOOK_ID"
}

$AllSecrets = @($ClientSecretName, $SecretSecretName, $WebhookSecretName)

Write-Host "=== Wire PayPal ($Mode) to Cloud Run ===" -ForegroundColor Cyan
Write-Host "Project: $Project  Service: $BackendService" -ForegroundColor Yellow
Write-Host "Secret Manager -> Cloud Run env:" -ForegroundColor Yellow
Write-Host "  $ClientSecretName -> PAYPAL_CLIENT_ID"
Write-Host "  $SecretSecretName -> PAYPAL_CLIENT_SECRET"
Write-Host "  $WebhookSecretName -> PAYPAL_WEBHOOK_ID"

$activeAccount = gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>$null
if (-not $activeAccount) {
    Write-Host "Not logged in to gcloud. Run: gcloud auth login" -ForegroundColor Red
    exit 1
}
Write-Host "gcloud account: $activeAccount" -ForegroundColor Green

foreach ($SecretName in $AllSecrets) {
    Write-Host "Checking secret $SecretName..." -ForegroundColor Cyan
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & gcloud secrets describe $SecretName --project $Project --quiet 2>&1 | Out-Null
    $descCode = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($descCode -ne 0) {
        Write-Host "Secret $SecretName not found in project $Project." -ForegroundColor Red
        Write-Host "Create it in Secret Manager, then re-run this script."
        exit 1
    }
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

foreach ($SecretName in $AllSecrets) {
    Write-Host "Granting secretAccessor on $SecretName..." -ForegroundColor Cyan
    $prevEap = $ErrorActionPreference
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
    Write-Host "IAM OK: $SecretName" -ForegroundColor Green
}

Write-Host "Updating Cloud Run service..." -ForegroundColor Cyan
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$updateOut = & gcloud run services update $BackendService `
    --region $Region `
    --project $Project `
    --update-secrets="PAYPAL_CLIENT_ID=${ClientSecretName}:latest,PAYPAL_CLIENT_SECRET=${SecretSecretName}:latest,PAYPAL_WEBHOOK_ID=${WebhookSecretName}:latest" `
    --update-env-vars="PAYPAL_MODE=${Mode},PAYPAL_SUBSCRIPTIONS_ENABLED=true,FRONTEND_BASE_URL=${FrontendBaseUrl}" `
    --quiet 2>&1
$updateCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($updateCode -ne 0) {
    Write-Host ($updateOut | Out-String) -ForegroundColor Red
    exit $updateCode
}
Write-Host ($updateOut | Out-String)

Write-Host "`nDone. PayPal checkout mode: $Mode" -ForegroundColor Green
Write-Host "Cloud Run now has PAYPAL_WEBHOOK_ID from $WebhookSecretName"
Write-Host "Test: https://communib.com -> org Billing and Service -> Choose a paid plan."
Write-Host "Note: webhook handler must still be implemented before activation works."
Write-Host "Plan IDs must match PayPal dashboard ($Mode) - see api/billing_plans.py"
