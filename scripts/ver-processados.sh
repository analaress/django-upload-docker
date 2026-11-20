#!/usr/bin/env bash
set -euo pipefail

BUCKET="${S3_BUCKET_PROCESSADOS:-central-arquivos-processados}"

echo "=== Imagens processadas em ${BUCKET} ==="
docker compose exec -T localstack awslocal s3 ls \
  "s3://${BUCKET}" \
  --recursive \
  --human-readable \
  --summarize
