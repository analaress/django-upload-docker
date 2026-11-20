#!/usr/bin/env bash
set -euo pipefail

TABLE="${DYNAMODB_TABLE_USUARIOS:-usuarios}"

echo "=== Usuários cadastrados em ${TABLE} ==="
docker compose exec -T localstack awslocal dynamodb scan \
  --table-name "$TABLE" \
  --projection-expression "user_id, #nome, email" \
  --expression-attribute-names '{"#nome":"nome"}' \
  --output table
