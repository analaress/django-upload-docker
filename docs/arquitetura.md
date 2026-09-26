# Arquitetura da solução

Este arquivo é a fonte central de todos os diagramas da solução. O `README.md` apresenta os tópicos da defesa técnica e aponta para esta página, evitando manter cópias dos diagramas em locais diferentes.

## 1. Diagrama de Implantação (Deployment Diagram)

Representa onde os componentes são executados, as portas publicadas e internas, a rede Docker, os volumes e os clientes externos.

```mermaid
flowchart LR
    cliente["Cliente / navegador<br/>localhost:8090"]
    dbeaver["DBeaver<br/>localhost:15432"]

    subgraph docker["Docker network: rede_aplicacao"]
        nginx["nginx<br/>container:80"]
        web["web<br/>Django + Gunicorn<br/>container:8000"]
        db["db<br/>PostgreSQL<br/>container:5432"]
        static[("static_data<br/>web: /app/staticfiles<br/>nginx: /var/www/static")]
        media[("media_data<br/>web: /app/media<br/>nginx: /var/www/media")]
        postgres[("postgres_data<br/>db: /var/lib/postgresql/data")]
    end

    cliente -->|"127.0.0.1:8090 → nginx:80"| nginx
    dbeaver -->|"127.0.0.1:15432 → db:5432"| db
    nginx -->|"proxy_pass http://web:8000"| web
    web -->|"POSTGRES_HOST=db<br/>POSTGRES_PORT=5432"| db
    web -->|"grava uploads"| media
    nginx -->|"serve /media/"| media
    nginx -->|"serve /static/"| static
    db -->|"dados persistentes"| postgres
    web -->|"collectstatic"| static
```

Portas externas: `localhost:8090` publica o Nginx e `localhost:15432` publica o PostgreSQL apenas para acesso local. Portas internas: `nginx:80`, `web:8000` e `db:5432`. O agrupamento representa a rede `rede_aplicacao`; os volumes ficam disponíveis enquanto os containers podem ser recriados.

## 2. Diagrama de Componentes

Representa a visão lógica da solução e a responsabilidade de cada componente, sem confundir componentes da aplicação com containers ou máquinas.

```mermaid
flowchart LR
    navegador["Cliente<br/>navegador"]
    dbeaver["Cliente administrativo<br/>DBeaver"]
    proxy["Nginx<br/>proxy reverso"]
    app["Django + Gunicorn<br/>regras e upload"]
    banco["PostgreSQL<br/>metadados"]
    volumes["Docker Volumes<br/>media_data, static_data, postgres_data"]

    navegador -->|"HTTP"| proxy
    dbeaver -->|"localhost:15432 → db:5432"| banco
    proxy -->|"proxy_pass"| app
    app -->|"SQL via Psycopg"| banco
    app -->|"grava uploads e estáticos"| volumes
    proxy -->|"lê mídia e estáticos"| volumes
    banco -->|"dados físicos"| volumes
```

O Diagrama de Implantação responde **onde** cada elemento executa. O Diagrama de Componentes responde **como** as responsabilidades colaboram.

## 3. Dependências e inicialização dos serviços

Mostra a ordem lógica de disponibilidade definida no `docker-compose.yml`. O `web` depende do banco saudável; o Nginx depende do serviço web iniciado.

```mermaid
flowchart LR
    db["db<br/>PostgreSQL"] -->|"healthcheck: pg_isready"| web["web<br/>Django + Gunicorn"]
    web -->|"depends_on: service_started"| nginx["nginx<br/>proxy reverso"]
```

## 4. Diagrama de comunicação entre containers

Mostra as portas internas e os nomes resolvidos pelo DNS da rede Docker.

```mermaid
sequenceDiagram
    actor Cliente
    participant Nginx as nginx:80
    participant Django as web:8000
    participant Banco as db:5432

    Cliente->>Nginx: http://localhost:8090
    Nginx->>Nginx: verifica /static/, /media/ ou outra rota
    Nginx->>Django: proxy_pass http://web:8000
    Django->>Banco: conexão PostgreSQL via db:5432
    Banco-->>Django: dados da aplicação
    Django-->>Nginx: resposta HTTP
    Nginx-->>Cliente: resposta final
```

## 5. Diagrama de sequência do upload

Representa o caminho do arquivo desde o navegador até o volume persistente e o registro de metadados no PostgreSQL.

```mermaid
sequenceDiagram
    actor Cliente
    participant Nginx as nginx:80
    participant Django as web:8000
    participant Form as ArquivoEnviadoForm
    participant Banco as db:5432
    participant Volume as media_data

    Cliente->>Nginx: POST /enviar/ multipart/form-data
    Nginx->>Django: proxy_pass para web:8000
    Django->>Form: request.POST e request.FILES
    Form->>Form: verifica extensão e tamanho
    Form-->>Django: formulário válido
    Django->>Volume: grava em /app/media
    Django->>Banco: grava metadados e caminho
    Banco-->>Django: confirmação da transação
    Django-->>Nginx: redirect para /
    Nginx-->>Cliente: página atualizada
    Cliente->>Nginx: GET /media/arquivo
    Nginx->>Volume: lê /var/www/media
    Volume-->>Nginx: conteúdo do arquivo
    Nginx-->>Cliente: entrega o arquivo
```

## Relação entre os diagramas e a implementação

| Elemento | Implementação |
|---|---|
| Cliente → Nginx | `PORTA_NGINX` (padrão `8090`) → porta `80` |
| Nginx → Django/Gunicorn | `proxy_pass http://web:8000` |
| Django → PostgreSQL | `POSTGRES_HOST=db` e `POSTGRES_PORT=5432` |
| Rede dos serviços | `rede_aplicacao` |
| Banco persistente | `postgres_data:/var/lib/postgresql/data` |
| Upload persistente | `media_data:/app/media` e `media_data:/var/www/media:ro` |
| Arquivos estáticos | `static_data:/app/staticfiles` e `static_data:/var/www/static:ro` |

Os nomes, portas, caminhos e volumes dos diagramas correspondem ao `docker-compose.yml` e ao `nginx/default.conf` atuais.

Consulte o [README principal](../README.md) para a explicação completa, execução, comandos e análise técnica.
