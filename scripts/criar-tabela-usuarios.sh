#!/usr/bin/env bash
set -euo pipefail

TABLE="${DYNAMODB_TABLE_USUARIOS:-usuarios}"

if docker compose exec -T localstack awslocal dynamodb describe-table \
  --table-name "$TABLE" >/dev/null 2>&1; then
  echo "Tabela já existe: ${TABLE}"
  exit 0
fi

docker compose exec -T localstack awslocal dynamodb create-table \
  --table-name "$TABLE" \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=email,AttributeType=S \
  --key-schema AttributeName=user_id,KeyType=HASH \
  --global-secondary-indexes \
    "IndexName=email-index,KeySchema=[{AttributeName=email,KeyType=HASH}],Projection={ProjectionType=ALL}" \
  --billing-mode PAY_PER_REQUEST

docker compose exec -T localstack awslocal dynamodb wait table-exists \
  --table-name "$TABLE"

echo "Tabela criada: ${TABLE}"
