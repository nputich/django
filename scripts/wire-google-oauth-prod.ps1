# Wire Google OAuth (YouTube verifier) secrets into django-backend Cloud Run.
#
# Google Secret Manager (communib):
#   Google_ID / Google_Secret
#
# Mapped into app env (what Django reads):
#   GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET
# plus GOOGLE_OAUTH_REDIRECT_URI
#
# Usage:
#   .\scripts\wire-google-oauth-prod.ps1

$ErrorActionPreference = "Stop"
$Project = "communib"
$Region = "us-central1"
$BackendService = "django-backend"
$ClientSecretName = "Google_ID"
$SecretSecretName = "Google_Secret"
$RedirectUri = "https://django-backend-460809694305.us-central1.run.app/api/youtube/oauth/callback/"
$AllSecrets = @($ClientSecretName, $SecretSecretName)

Write-Host "=== Wire Google OAuth to Cloud Run ===" -ForegroundColor Cyan
Write-Host "Project: $Project  Service: $BackendService" -ForegroundColor Yellow
Write-Host "Secret Manager -> Cloud Run env:" -ForegroundColor Yellow
Write-Host "  $ClientSecretName -> GOOGLE_OAUTH_CLIENT_ID"
Write-Host "  $SecretSecretName -> GOOGLE_OAUTH_CLIENT_SECRET"
Write-Host "  GOOGLE_OAUTH_REDIRECT_URI = $RedirectUri"

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
    --update-secrets="GOOGLE_OAUTH_CLIENT_ID=${ClientSecretName}:latest,GOOGLE_OAUTH_CLIENT_SECRET=${SecretSecretName}:latest" `
    --update-env-vars="GOOGLE_OAUTH_REDIRECT_URI=${RedirectUri}" `
    --quiet 2>&1
$updateCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($updateCode -ne 0) {
    Write-Host ($updateOut | Out-String) -ForegroundColor Red
    exit $updateCode
}
Write-Host ($updateOut | Out-String)

Write-Host "`nDone. Google OAuth wired for YouTube verification." -ForegroundColor Green
Write-Host "Ensure this exact redirect URI is in the OAuth client:"
Write-Host "  $RedirectUri"
Write-Host "Also keep local:"
Write-Host "  http://localhost:8001/api/youtube/oauth/callback/"
