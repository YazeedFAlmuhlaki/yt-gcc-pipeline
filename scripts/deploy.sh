#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

FUNCTIONS=(
  "yt-gcc-ingest"
  "yt-gcc-categories"
  "yt-gcc-daily-merge"
)

for fn in "${FUNCTIONS[@]}"; do
  echo "deploying to $fn"
  aws lambda update-function-code \
    --function-name "$fn" \
    --zip-file fileb://function.zip \
    --no-cli-pager
done

echo "done"