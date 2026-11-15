#!/usr/bin/env bash
# Build the React app, write config.json from the stack outputs, sync to S3, invalidate CloudFront.
# Usage: DEVICE_KEY=<the DeviceApiKey you deployed with> ./scripts/deploy_frontend.sh
set -euo pipefail

STACK="${STACK:-coldchain-guard}"
REGION="${AWS_REGION:-us-east-1}"
: "${DEVICE_KEY:?Set DEVICE_KEY to the DeviceApiKey you passed to sam deploy}"

out() {
  aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

API_URL="$(out ApiUrl)"
BUCKET="$(out FrontendBucket)"
DIST_ID="$(out DistributionId)"
SITE_URL="$(out CloudFrontUrl)"

cd "$(dirname "$0")/../frontend"
npm ci --no-audit --no-fund
npm run build

cat > dist/config.json <<EOF
{
  "apiUrl": "${API_URL}",
  "deviceKey": "${DEVICE_KEY}",
  "siteUrl": ""
}
EOF

# Hashed assets cache forever; index.html and config.json must always be fresh.
aws s3 sync dist/ "s3://${BUCKET}" --delete --region "$REGION" \
  --exclude index.html --exclude config.json \
  --cache-control "public,max-age=31536000,immutable"
aws s3 cp dist/index.html "s3://${BUCKET}/index.html" --region "$REGION" --cache-control "no-cache"
aws s3 cp dist/config.json "s3://${BUCKET}/config.json" --region "$REGION" --cache-control "no-cache"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" >/dev/null

echo "Deployed. Open ${SITE_URL}"
