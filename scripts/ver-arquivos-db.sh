#!/usr/bin/env bash
set -euo pipefail

docker compose exec -T db psql \
  -U "${POSTGRES_USER:-aplicacao}" \
  -d "${POSTGRES_DB:-aplicacao}" \
  -c 'SELECT id, nome_original, tamanho_em_bytes, proprietario_id, chave_s3, enviado_em FROM envios_arquivoenviado ORDER BY enviado_em DESC;'
