#!/usr/bin/env bash
set -euo pipefail

REGION=ap-northeast-2
BUCKET=${1:?usage: package-lambdas.sh ARTIFACT_BUCKET [ARTIFACT_PREFIX]}
PREFIX=${2:-emotion-diary}
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
BUILD_DIR=$(mktemp -d)
trap 'rm -rf "$BUILD_DIR"' EXIT

for lambda_name in analyze_emotion recommend_music send_diary; do
  hash=$(openssl dgst -sha256 -r "$ROOT/lambda/$lambda_name/handler.py")
  hash=${hash%% *}
  key="$PREFIX/$lambda_name-$hash.zip"

  (cd "$ROOT/lambda/$lambda_name" && zip -q "$BUILD_DIR/$lambda_name.zip" handler.py)
  aws s3 cp "$BUILD_DIR/$lambda_name.zip" "s3://$BUCKET/$key" --region "$REGION" >&2

  case "$lambda_name" in
    analyze_emotion) printf 'AnalyzeCodeS3Key=%s\n' "$key" ;;
    recommend_music) printf 'RecommendCodeS3Key=%s\n' "$key" ;;
    send_diary) printf 'SendDiaryCodeS3Key=%s\n' "$key" ;;
  esac
done
