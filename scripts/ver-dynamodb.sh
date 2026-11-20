#!/usr/bin/env bash
set -euo pipefail

TABLE="${DYNAMODB_TABLE_USUARIOS:-usuarios}"

echo "=== Tabelas DynamoDB ==="
docker compose exec -T localstack awslocal dynamodb list-tables

echo
echo "=== Estrutura da tabela ${TABLE} ==="
docker compose exec -T localstack awslocal dynamodb describe-table \
  --table-name "$TABLE"
