# Central de Arquivos — Guia de execução

Guia rápido para executar e validar o projeto localmente.

## 1. Arquitetura

```text
Navegador -> Nginx :8090 -> Django
                              |
             +----------------+----------------+
             |                |                |
         PostgreSQL       DynamoDB       S3 original
         metadados        usuários       arquivos
                                                |
                                      ObjectCreated -> Lambda
                                                |
                                      S3 processados
                                      miniaturas JPEG
```

- **Django:** telas, autenticação e regras de acesso.
- **PostgreSQL:** metadados dos arquivos.
- **DynamoDB:** usuários e hashes das senhas.
- **S3:** arquivos originais e miniaturas.
- **Lambda:** processa imagens após o upload.
- **Nginx:** acesso da aplicação em `http://localhost:8090`.
- **LocalStack:** simula AWS localmente.

## 2. Subir o projeto

Execute no WSL, na raiz do projeto:

```bash
docker compose up -d --build
docker compose ps
```

Acesse:

```text
http://localhost:8090
```

Para acompanhar o Django:

```bash
docker compose logs -f web
```

O arquivo `.env` é local e não deve ser commitado. O `DEBUG` deve permanecer em `0` depois dos testes.

## 3. Atividades implementadas

### Atividade 1 — S3

- Upload de imagens e outros arquivos permitidos.
- Listagem por usuário.
- Download do arquivo original.
- Exclusão do original e da miniatura.

Verificar S3:

```bash
bash scripts/ver-s3.sh
bash scripts/ver-processados.sh
bash scripts/ver-arquivos-db.sh
```

### Atividade 2 — DynamoDB

- Cadastro de usuários.
- Senhas armazenadas como hash.
- Login consultando o DynamoDB.
- Arquivos isolados por usuário.

Verificar DynamoDB:

```bash
bash scripts/ver-dynamodb.sh
bash scripts/ver-usuarios.sh
```

### Atividade 3 — Lambda

Ao receber uma imagem no bucket original, a Lambda:

1. abre a imagem;
2. redimensiona para até `300x300`;
3. salva uma miniatura JPEG no bucket processado.

PDF, TXT, DOCX e PPTX continuam armazenados e disponíveis para download, mas não são processados pela Lambda.

O processamento é assíncrono e normalmente leva alguns segundos no LocalStack. A miniatura aparece somente depois que estiver disponível no bucket processado.

## 4. Teste manual

1. Crie uma conta.
2. Faça login e logout.
3. Envie uma imagem.
4. Atualize a página após alguns segundos e abra a miniatura.
5. Baixe e visualize o arquivo original.
6. Envie um PDF ou TXT e confirme que ele aparece com o badge do tipo.
7. Crie outro usuário e confirme que ele não vê os arquivos anteriores.
8. Teste a exclusão.

## 5. Persistência

Os dados ficam nos volumes Docker. Para reiniciar sem apagar dados:

```bash
docker compose down
docker compose up -d
```

Não use `docker compose down -v`, pois ele remove os volumes e os dados locais.

## 6. Diagnóstico rápido

```bash
docker compose ps
docker compose logs --tail=100 web
docker compose logs --tail=100 localstack
docker compose exec web python manage.py check
docker compose exec web python -m compileall -q /app
```

Se a miniatura não aparecer:

```bash
bash scripts/ver-processados.sh
docker compose logs --tail=100 localstack
```

O projeto está configurado para desenvolvimento e avaliação local. Não há deploy em produção nem uso de credenciais AWS reais.
