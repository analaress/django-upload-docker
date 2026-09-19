#!/bin/sh
set -eu
host="${POSTGRES_HOST:-db}"
port="${POSTGRES_PORT:-5432}"
tentativas=0
echo "Aguardando PostgreSQL em ${host}:${port}..."
while ! python -c "import socket; socket.create_connection(('${host}', ${port}), 2).close()" 2>/dev/null
do
  tentativas=$((tentativas + 1))
  if [ "$tentativas" -ge 30 ]; then
    echo "PostgreSQL não ficou disponível após 30 tentativas." >&2
    exit 1
  fi
  sleep 2
done
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --access-logfile - --error-logfile -
