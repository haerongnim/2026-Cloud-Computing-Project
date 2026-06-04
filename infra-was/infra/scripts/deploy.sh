#!/usr/bin/env bash
set -euo pipefail

REGION=ap-northeast-2
STACK_NAME=${STACK_NAME:-emotion-diary}
ARTIFACT_BUCKET=${ARTIFACT_BUCKET:?set ARTIFACT_BUCKET}
ARTIFACT_PREFIX=${ARTIFACT_PREFIX:-emotion-diary}
SPOTIFY_SECRET_ARN=${SPOTIFY_SECRET_ARN:?set SPOTIFY_SECRET_ARN}
SES_FROM_EMAIL=${SES_FROM_EMAIL:?set SES_FROM_EMAIL}
ALLOWED_ORIGIN=${ALLOWED_ORIGIN:-'*'}
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)

"$ROOT/infra-was/infra/scripts/bootstrap-artifacts.sh" "$ARTIFACT_BUCKET"
while IFS='=' read -r name value; do
  case "$name" in
    AnalyzeCodeS3Key) AnalyzeCodeS3Key=$value ;;
    RecommendCodeS3Key) RecommendCodeS3Key=$value ;;
    SendDiaryCodeS3Key) SendDiaryCodeS3Key=$value ;;
  esac
done < <("$ROOT/infra-was/infra/scripts/package-lambdas.sh" "$ARTIFACT_BUCKET" "$ARTIFACT_PREFIX")

aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --template-file "$ROOT/infra-was/infra/template.yaml" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    ArtifactBucket="$ARTIFACT_BUCKET" \
    ArtifactPrefix="$ARTIFACT_PREFIX" \
    AnalyzeCodeS3Key="$AnalyzeCodeS3Key" \
    RecommendCodeS3Key="$RecommendCodeS3Key" \
    SendDiaryCodeS3Key="$SendDiaryCodeS3Key" \
    SpotifySecretArn="$SPOTIFY_SECRET_ARN" \
    SesFromEmail="$SES_FROM_EMAIL" \
    AllowedOrigin="$ALLOWED_ORIGIN"

aws cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table
