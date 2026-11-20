#!/usr/bin/env bash
set -euo pipefail

BUCKET="${S3_BUCKET_ORIGINAIS:-central-arquivos-originais}"

echo "=== Saúde do LocalStack ==="
curl -fsS http://localhost:4566/_localstack/health
echo

echo "=== Buckets ==="
docker compose exec localstack awslocal s3 ls

echo "=== Objetos em ${BUCKET} ==="
docker compose exec localstack awslocal s3 ls \
  "s3://${BUCKET}" \
  --recursive \
  --human-readable \
  --summarize
