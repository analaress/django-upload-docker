# Django + Nginx + PostgreSQL + Docker Compose

Projeto demonstrativo em português com upload persistente. São aceitos arquivos PDF, PNG, JPG, TXT, DOCX e PPTX, até 10 MB.

Copie `.env.example` para `.env` e execute `docker compose up --build -d`. Acesse `http://localhost:8090`. A porta pode ser alterada em `PORTA_NGINX`.

Serviços: Nginx na porta 80 interna e 8090 externa; Gunicorn na porta interna 8000; PostgreSQL na porta interna 5432 e externa 15432, limitado ao acesso local. No DBeaver use `localhost:15432`.

Limites locais: PostgreSQL usa até 0,50 CPU e 512 MB; Django/Gunicorn até 0,75 CPU e 512 MB; Nginx até 0,25 CPU e 128 MB. Esses limites economizam recursos, mas podem ser aumentados para arquivos grandes ou maior concorrência.

Comandos úteis: `docker compose ps`, `docker compose logs -f web`, `docker compose logs -f nginx`, `docker compose logs -f db` e `docker compose down`.

Os volumes `postgres_data`, `static_data` e `media_data` são preservados por `docker compose down`. Não use `docker compose down -v` se quiser preservar os dados.
