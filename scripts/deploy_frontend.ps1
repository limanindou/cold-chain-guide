# Build the React app, write config.json from the stack outputs, sync to S3, invalidate CloudFront.
# Usage (PowerShell):  $env:DEVICE_KEY = "<the DeviceApiKey you deployed with>"; .\scripts\deploy_frontend.ps1
param(
  [string]$Stack = "coldchain-guard",
  [string]$Region = "us-east-1"
)
# "Continue": Windows PowerShell 5.1 turns harmless npm/aws warnings on stderr into errors under "Stop".
# Failures are detected through $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
function Assert-Ok([string]$What) { if ($LASTEXITCODE -ne 0) { throw "$What failed (exit $LASTEXITCODE)" } }
if (-not $env:DEVICE_KEY) { throw "Set `$env:DEVICE_KEY to the DeviceApiKey you passed to sam deploy" }

function Get-Output([string]$Key) {
  aws cloudformation describe-stacks --stack-name $Stack --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='$Key'].OutputValue" --output text
}

$ApiUrl = Get-Output "ApiUrl"
$Bucket = Get-Output "FrontendBucket"
$DistId = Get-Output "DistributionId"
$SiteUrl = Get-Output "CloudFrontUrl"

Push-Location (Join-Path $PSScriptRoot "..\frontend")
try {
  npm ci --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
  npm run build
  if ($LASTEXITCODE -ne 0) { throw "build failed" }

  $config = @{ apiUrl = $ApiUrl; deviceKey = $env:DEVICE_KEY; siteUrl = "" } | ConvertTo-Json
  [System.IO.File]::WriteAllText((Join-Path (Get-Location) "dist\config.json"), $config)

  aws s3 sync dist/ "s3://$Bucket" --delete --region $Region --exclude index.html --exclude config.json --cache-control "public,max-age=31536000,immutable"
  Assert-Ok "s3 sync"
  aws s3 cp dist/index.html "s3://$Bucket/index.html" --region $Region --cache-control "no-cache"
  Assert-Ok "upload index.html"
  aws s3 cp dist/config.json "s3://$Bucket/config.json" --region $Region --cache-control "no-cache"
  Assert-Ok "upload config.json"
  aws cloudfront create-invalidation --distribution-id $DistId --paths "/*" | Out-Null
  Assert-Ok "CloudFront invalidation"
  Write-Host "Deployed. Open $SiteUrl"
} finally {
  Pop-Location
}
