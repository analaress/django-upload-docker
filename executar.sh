#!/usr/bin/env bash
# Sobe a Central de Arquivos e espera o provisionamento do LocalStack.
# Execute no terminal do host (onde o Docker funciona):
#
#   ./executar.sh
#
# O script não apaga volumes. Para recomeçar do zero, use
#   docker compose down -v
# antes de executá-lo novamente.

set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERRO: o comando 'docker' não foi encontrado no PATH." >&2
  echo "Abra o terminal do host onde 'docker --version' funciona." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERRO: o plugin 'docker compose' (v2) não foi encontrado." >&2
  echo "Confira com: docker compose version" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERRO: o daemon do Docker não está acessível." >&2
  echo "Verifique se o Docker está rodando e se você tem permissão no socket." >&2
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Criei o arquivo .env a partir de .env.example."
  echo "Edite POSTGRES_PASSWORD em .env e execute este script novamente."
  exit 1
fi

if grep -q '^POSTGRES_PASSWORD=defina-uma-senha-local$' .env; then
  echo "ERRO: POSTGRES_PASSWORD ainda é o valor de exemplo." >&2
  echo "Edite .env e defina uma senha local antes de continuar." >&2
  exit 1
fi

echo "Subindo os containers (o primeiro build pode demorar)..."
docker compose up --build -d

echo "Aguardando o provisionador criar buckets, tabela, Lambda e evento S3..."
for _ in $(seq 1 180); do
  estado="$(docker compose ps -a --format '{{.Service}} {{.State}}' 2>/dev/null \
    | awk '$1 == "provisionador" {print $2; exit}')"

  if [ "$estado" = "exited" ]; then
    container="$(docker compose ps -aq provisionador 2>/dev/null || true)"
    codigo="$(docker inspect -f '{{.State.ExitCode}}' "$container" 2>/dev/null || echo 1)"
    if [ "$codigo" != "0" ]; then
      echo "ERRO: o provisionador terminou com código $codigo." >&2
      echo "Últimas linhas do log:" >&2
      docker compose logs --tail=120 provisionador >&2 || true
      exit 1
    fi
    echo "Provisionamento concluído com sucesso."
    break
  fi

  sleep 2
done

if [ "${estado:-}" != "exited" ]; then
  echo "ERRO: o provisionador não terminou no tempo esperado." >&2
  echo "Confira os logs com: docker compose logs -f provisionador" >&2
  exit 1
fi

# Relê o nginx/default.conf (bind mount) para aplicar o Cache-Control dos
# estáticos sem depender de o container ter sido recriado.
echo "Aplicando a configuração do Nginx..."
docker compose restart nginx >/dev/null

echo
docker compose ps
echo
echo "Aplicação:  http://localhost:8090"
echo "Admin:      http://localhost:8090/admin/"
echo "LocalStack: http://localhost:4566/_localstack/health"
echo
echo "Acompanhe os logs com:"
echo "  docker compose logs -f web nginx localstack"
echo
echo "Roteiro de testes: COMANDOS.md"
