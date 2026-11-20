# COMANDOS — subir, testar e limpar o ambiente

Este guia mostra, na ordem, como executar a **Central de Arquivos** com
Docker Compose e validar as três atividades do enunciado:

1. **S3/LocalStack** — upload, listagem e download de imagens.
2. **DynamoDB/LocalStack** — cadastro e login de usuários.
3. **Lambda/LocalStack** — geração automática de miniaturas após o upload.

O passo a passo assume que o terminal está na raiz do projeto:

```bash
cd "Computação Dupla/django-upload-docker"
```

> **Atenção:** `docker compose down -v` apaga os volumes e, com eles, os dados
> do PostgreSQL, do S3, do DynamoDB e da Lambda. Use apenas quando quiser
> recomeçar do zero. Para parar sem perder dados, use `docker compose down`
> (sem `-v`).

---

## 1. Pré-requisitos

| Item | Versão / observação |
|---|---|
| Docker Engine | 24 ou superior, com o daemon em execução |
| Docker Compose | plugin v2 (`docker compose`, sem hífen) |
| Espaço em disco | ~2 GB para imagens, Lambda e volumes |
| Memória | ~2 GB livres; a primeira invocação da Lambda usa um container extra |
| Portas livres | `8090` (Nginx), `15432` (PostgreSQL) e `4566` (LocalStack) |
| Acesso ao Docker | o usuário precisa poder usar `/var/run/docker.sock` (grupo `docker` no Linux) |

Confira antes de começar:

```bash
docker --version
docker compose version
docker info > /dev/null && echo "Docker daemon OK"
```

Se `docker info` falhar com *permission denied*, no Linux:

```bash
sudo usermod -aG docker "$USER"
# saia da sessão e entre novamente para o grupo valer
```

> **Por que o socket do Docker é necessário?** O LocalStack executa a Lambda
> em containers reais. O Compose monta `/var/run/docker.sock` no serviço
> `localstack` e define `LAMBDA_DOCKER_NETWORK=rede_aplicacao`. Sem isso, a
> função fica em `Pending`/`Failed`.

---

## 2. Preparar o arquivo `.env`

O `.env.example` contém apenas valores fictícios. Crie o `.env` e troque a
senha local do PostgreSQL:

```bash
cp .env.example .env
```

Edite `.env` e ajuste pelo menos:

```dotenv
POSTGRES_PASSWORD=uma-senha-local-forte
```

As credenciais `AWS_ACCESS_KEY_ID=test` e `AWS_SECRET_ACCESS_KEY=test` são
**fictícias e intencionais**: o LocalStack aceita qualquer valor. Não coloque
credenciais reais da AWS nesse arquivo.

Variáveis que costumam ser alteradas:

| Variável | Padrão | Quando mudar |
|---|---|---|
| `PORTA_NGINX` | `8090` | se a porta estiver ocupada |
| `PORTA_LOCALSTACK` | `4566` | se a porta estiver ocupada |
| `POSTGRES_PASSWORD` | — | obrigatória; defina uma senha local |
| `LIMITE_TAMANHO_IMAGEM_MB` | `10` | para testar outro limite |
| `LIMITE_ARQUIVOS_POR_ENVIO` | `5` | para permitir mais/menos arquivos |
| `LARGURA_MAXIMA_MINIATURA` | `300` | para mudar a largura da miniatura |

Se você mudar `PORTA_NGINX`, ajuste também `ORIGENS_CSRF_PERMITIDAS` e use a
nova porta no navegador. Se mudar `PORTA_LOCALSTACK`, o endpoint interno
`AWS_ENDPOINT_URL=http://localstack:4566` **não** muda (ele usa a porta interna
do container).

---

## 3. Subir o ambiente

Se preferir um atalho, execute no terminal do host:

```bash
./executar.sh
```

O script confere Docker/Compose, cria o `.env` se ele não existir, sobe os
containers e espera o `provisionador` terminar com sucesso. Se ele criar o
`.env`, edite `POSTGRES_PASSWORD` e rode novamente. O restante deste guia
continua valendo.

Para fazer manualmente:

```bash
docker compose up --build -d
```

O primeiro build pode demorar porque:

- instala as dependências Python da aplicação;
- baixa a wheel `manylinux` do Pillow para empacotar a Lambda.

Acompanhe a subida:

```bash
docker compose ps
docker compose logs -f provisionador
```

O `provisionador` é um serviço **one-shot**. Ele termina com código `0` quando
cria/atualiza:

- os buckets `central-arquivos-originais` e `central-arquivos-processados`;
- a tabela DynamoDB `usuarios` e o índice `email-index`;
- a função Lambda `processar-imagem` (com Pillow no zip);
- a permissão para o S3 invocar a Lambda;
- o evento `s3:ObjectCreated:*` no bucket de originais;
- a ausência de gatilho no bucket de processados.

Saída esperada no final:

```text
[provisionador] provisionamento concluído com sucesso
[provisionador]   bucket originais:  central-arquivos-originais
[provisionador]   bucket processados:central-arquivos-processados
[provisionador]   tabela DynamoDB:   usuarios (índice email-index)
[provisionador]   função Lambda:     processar-imagem (arn:aws:lambda:...)
```

Confirme que ele terminou bem:

```bash
docker compose ps -a
```

O serviço `provisionador` deve aparecer como `Exited (0)`. O `web` e o `nginx`
só iniciam depois que o provisionamento termina com sucesso.

### Se o provisionador falhar

```bash
docker compose logs provisionador
docker compose logs localstack | tail -n 100
```

Depois de corrigir a causa, recrie apenas ele:

```bash
docker compose rm -sf provisionador
docker compose up -d provisionador
docker compose logs -f provisionador
```

---

## 4. Conferir se tudo está no ar

### 4.1 Containers

```bash
docker compose ps
```

Esperado: `db`, `localstack`, `web` e `nginx` em execução; `provisionador`
como `Exited (0)`.

### 4.2 LocalStack

```bash
curl -s http://localhost:4566/_localstack/health | python3 -m json.tool
```

Procure `"s3": "available"`, `"dynamodb": "available"` e
`"lambda": "available"`.

### 4.3 Aplicação

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8090/login/
```

Esperado: `200`.

```bash
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" http://localhost:8090/
```

Esperado: `302` com redirecionamento para `/login/?next=/` (a área privada
está bloqueada sem sessão).

### 4.4 Endereços

| Serviço | Endereço |
|---|---|
| Aplicação (Nginx) | <http://localhost:8090> |
| Admin do Django | <http://localhost:8090/admin/> |
| LocalStack | <http://localhost:4566> |
| Health do LocalStack | <http://localhost:4566/_localstack/health> |
| PostgreSQL | `localhost:15432` (usuário/banco conforme `.env`) |

O admin do Django usa o usuário interno do Django/PostgreSQL e **não** é o
mesmo login da aplicação. Para criar um superusuário:

```bash
docker compose exec web python manage.py createsuperuser
```

---

## 5. Roteiro de testes

A ordem sugerida é: criar conta → entrar → enviar imagem → conferir S3 →
conferir Lambda → baixar arquivos → testar erros → testar persistência.

### 5.1 Atividade 2 — DynamoDB (cadastro e login)

#### a) Criar uma conta pela interface

1. Abra <http://localhost:8090/cadastro/>.
2. Informe nome, e-mail e uma senha com pelo menos 8 caracteres.
3. Confirme a senha e envie.

A aplicação deve autenticar automaticamente e abrir a área privada.

#### b) Confirmar o item no DynamoDB

```bash
docker compose exec -T localstack awslocal dynamodb scan \
  --table-name usuarios \
  --projection-expression "user_id, tipo, nome, email" \
  --query "Items"
```

Você deve ver:

- um item com `"tipo": "usuario"` e os dados da conta;
- um item de reserva com `"tipo": "reserva_email"` e
  `"user_id": "email#<e-mail>"`.

O item de reserva é o que garante unicidade de e-mail de forma atômica.

#### c) Confirmar que a senha é um hash

Copie o `user_id` do item de usuário e execute:

```bash
docker compose exec -T localstack awslocal dynamodb get-item \
  --table-name usuarios \
  --key '{"user_id":{"S":"COLE_O_USER_ID_AQUI"}}' \
  --projection-expression "senha_hash" \
  --query "Item.senha_hash.S" --output text
```

O resultado deve começar com `pbkdf2_sha256$`. **Não** deve ser a senha
digitada. Não cole esse hash em issues, prints ou documentos.

#### d) Consultar pelo índice de e-mail

```bash
docker compose exec -T localstack awslocal dynamodb query \
  --table-name usuarios \
  --index-name email-index \
  --key-condition-expression "email = :email" \
  --expression-attribute-values '{":email":{"S":"maria@exemplo.com"}}' \
  --query "Items[].user_id.S" --output text
```

Troque `maria@exemplo.com` pelo e-mail cadastrado. Deve retornar **um** `user_id`.

#### e) Testar e-mail duplicado

1. Saia da conta (botão **Sair**).
2. Tente criar outra conta com o **mesmo e-mail** (pode variar maiúsculas/
   minúsculas; o e-mail é normalizado).
3. A tela deve mostrar “Este e-mail já está cadastrado.”

Confirme que continua existindo apenas uma conta com aquele e-mail:

```bash
docker compose exec -T localstack awslocal dynamodb query \
  --table-name usuarios \
  --index-name email-index \
  --key-condition-expression "email = :email" \
  --expression-attribute-values '{":email":{"S":"maria@exemplo.com"}}' \
  --select COUNT \
  --query "Count" --output text
```

Esperado: `1`.

#### f) Testar login correto e incorreto

1. Abra <http://localhost:8090/login/>.
2. Entre com o e-mail e a senha corretos: deve ir para a área privada.
3. Saia e tente novamente com a senha errada: deve aparecer
   “E-mail ou senha inválidos.”
4. Saia e tente com um e-mail inexistente: a mesma mensagem genérica.

#### g) Testar bloqueio e logout

Sem sessão:

```bash
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" http://localhost:8090/
```

Esperado: `302` para `/login/?next=/`.

Depois de entrar pela interface, o mesmo comando com o cookie de sessão
retornaria `200`; o jeito mais simples de conferir é abrir a área privada no
navegador. Ao clicar em **Sair**, a área privada deve voltar a redirecionar
para o login.

#### h) Conferir a sessão no PostgreSQL

```bash
docker compose exec db psql -U aplicacao -d aplicacao \
  -c "select count(*) from django_session;"
```

Deve haver pelo menos uma sessão enquanto você estiver logado. A sessão guarda
apenas o identificador da conta; a senha/hash fica no DynamoDB.

> Se você alterou `POSTGRES_USER`, use o valor do seu `.env` no lugar de
> `aplicacao`.

---

### 5.2 Atividade 1 — S3 (upload, listagem e download)

#### a) Enviar uma imagem pela interface

1. Entre na aplicação.
2. Na área privada, selecione uma imagem JPEG, PNG, GIF ou WEBP.
3. Clique em **Enviar para o S3**.

A mensagem deve indicar quantas imagens foram enviadas. A listagem mostra o
card com o estado **Aguardando** ou **Processando pela Lambda...** até a
miniatura ficar pronta.

#### b) Confirmar o objeto no bucket de originais

```bash
docker compose exec -T localstack awslocal s3 ls \
  s3://central-arquivos-originais/usuarios/ --recursive --human-readable
```

O caminho deve seguir o padrão:

```text
usuarios/<user_id>/<uuid>.<ext>
```

O nome enviado pelo navegador **não** é usado na chave; o UUID evita colisões e
nomes previsíveis.

#### c) Acompanhar a listagem

A imagem deve continuar aparecendo. O card mostra “Processando pela Lambda...”
e é atualizado automaticamente quando a miniatura fica pronta, sem recarregar
a página. Se quiser forçar uma nova consulta, use **Atualizar lista**. Quando
processada, o card exibe os links:

- **Baixar original**;
- **Baixar miniatura**.

#### d) Baixar o original e comparar

Baixe pelo link **Baixar original** e compare o conteúdo com o arquivo que
você enviou:

```bash
sha256sum caminho/do/arquivo_original
sha256sum ~/Downloads/arquivo_baixado
```

Os hashes devem ser iguais. O download é feito por uma view autenticada do
Django, que lê do S3; o Nginx não serve a pasta de mídia.

#### e) Testar arquivo inválido

Crie um arquivo de texto com extensão de imagem:

```bash
printf 'isto nao e uma imagem\n' > arquivo_falso.png
```

Envie `arquivo_falso.png` pela interface. O Pillow tenta abrir o conteúdo e a
aplicação deve recusar com uma mensagem de imagem inválida. O objeto **não**
deve aparecer no bucket:

```bash
docker compose exec -T localstack awslocal s3 ls \
  s3://central-arquivos-originais/usuarios/ --recursive
```

#### f) Testar arquivo acima do limite

O limite padrão é 10 MB por imagem:

```bash
dd if=/dev/zero of=imagem_grande.jpg bs=1M count=11 status=none
ls -lh imagem_grande.jpg
```

Envie `imagem_grande.jpg` pela interface. A aplicação deve recusar por tamanho
antes de enviar ao S3. O Nginx está configurado com `client_max_body_size 55m`
para acomodar até 5 imagens de 10 MB.

#### g) Testar muitos arquivos

Com o limite padrão de 5 imagens por envio, selecione 6 arquivos. O formulário
deve recusar o envio com uma mensagem de limite.

#### h) Testar isolamento entre contas

1. Crie uma segunda conta.
2. Envie uma imagem com a segunda conta.
3. Volte para a primeira conta e confira que a listagem mostra apenas as
   imagens da primeira.
4. Tente acessar uma chave da segunda conta pela URL da primeira, por exemplo:

```text
http://localhost:8090/arquivos/usuarios/<user_id_da_outra_conta>/<uuid>.png/original/
```

O esperado é `404`, porque a view valida o prefixo `usuarios/<user_id>/` contra
o usuário da sessão.

---

### 5.3 Atividade 3 — Lambda (miniatura automática)

#### a) Confirmar a função e o gatilho

```bash
docker compose exec -T localstack awslocal lambda list-functions \
  --query "Functions[].{Nome:FunctionName,Runtime:Runtime,Estado:State}"

docker compose exec -T localstack awslocal lambda get-function-configuration \
  --function-name processar-imagem \
  --query "{Estado:State,UltimaAtualizacao:LastUpdateStatus,Handler:Handler,Timeout:Timeout,Memoria:MemorySize}"
```

Esperado: `State=Active`, `LastUpdateStatus=Successful`,
`Handler=processar_imagem.handler`.

Confira a notificação do bucket de originais:

```bash
docker compose exec -T localstack awslocal s3api \
  get-bucket-notification-configuration \
  --bucket central-arquivos-originais
```

Deve haver uma configuração com:

- `Events: ["s3:ObjectCreated:*"]`;
- filtro de prefixo `usuarios/`;
- ARN da função `processar-imagem`.

Confirme que o bucket de processados **não** tem gatilho:

```bash
docker compose exec -T localstack awslocal s3api \
  get-bucket-notification-configuration \
  --bucket central-arquivos-processados
```

Esperado: `{}` (ou nenhuma configuração de Lambda). Isso evita recursão.

#### b) Enviar uma imagem e acompanhar a Lambda

Envie uma imagem pela interface e acompanhe os logs:

```bash
docker compose logs -f localstack
```

Procure por mensagens como:

```text
Miniatura gerada: usuarios/<id>/<uuid>.png -> usuarios/<id>/<uuid>_thumb.jpg
```

A primeira invocação pode demorar porque o LocalStack baixa a imagem
`public.ecr.aws/lambda/python:3.12` para executar a função. As seguintes são
mais rápidas.

#### c) Confirmar a miniatura no bucket de processados

```bash
docker compose exec -T localstack awslocal s3 ls \
  s3://central-arquivos-processados/usuarios/ --recursive --human-readable
```

O caminho deve ser:

```text
usuarios/<user_id>/<uuid>_thumb.jpg
```

A miniatura é sempre JPEG, mesmo que o original seja PNG/GIF/WEBP.

#### d) Conferir as dimensões

Baixe a miniatura para inspecionar:

```bash
docker compose exec -T localstack awslocal s3 cp \
  s3://central-arquivos-processados/usuarios/<user_id>/<uuid>_thumb.jpg \
  /tmp/thumb.jpg

docker compose cp localstack:/tmp/thumb.jpg ./thumb.jpg
docker compose cp ./thumb.jpg web:/tmp/thumb.jpg

docker compose exec -T web python -c \
  "from PIL import Image; print(Image.open('/tmp/thumb.jpg').size)"
```

Para um original de 800×600, o esperado é `(300, 225)`. A proporção é
preservada e imagens menores que 300 px de largura **não** são ampliadas.

#### e) Confirmar que a aplicação mostra “Processada”

Aguarde alguns segundos na listagem. O card deve trocar “Processando pela
Lambda...” pela miniatura, pela etiqueta **Processada** e pelo link **Baixar
miniatura** automaticamente.

#### f) Teste isolado do gatilho (opcional, sem a interface)

Este teste envia um objeto diretamente ao bucket com um prefixo de teste. Ele
**não** aparece na interface, porque a listagem filtra pelo `user_id` da sessão.
Serve para validar o evento e a Lambda de forma independente.

```bash
# Cria uma imagem 800x600 dentro do container web (que tem Pillow)
docker compose exec -T web python - <<'PY'
from PIL import Image
Image.new("RGB", (800, 600), (25, 45, 120)).save("/tmp/teste_lambda.png")
PY

# Copia para o host e para o container do LocalStack
docker compose cp web:/tmp/teste_lambda.png ./teste_lambda.png
docker compose cp ./teste_lambda.png localstack:/tmp/teste_lambda.png

# Envia ao bucket de originais (dispara o evento ObjectCreated)
docker compose exec -T localstack awslocal s3 cp \
  /tmp/teste_lambda.png \
  s3://central-arquivos-originais/usuarios/teste-lambda/teste_lambda.png
```

Aguarde alguns segundos e confira:

```bash
docker compose exec -T localstack awslocal s3 ls \
  s3://central-arquivos-processados/usuarios/teste-lambda/
```

Deve aparecer `teste_lambda_thumb.jpg`. Se a primeira invocação estiver
baixando a imagem da Lambda, aguarde e repita.

Limpe os objetos de teste:

```bash
docker compose exec -T localstack awslocal s3 rm \
  s3://central-arquivos-originais/usuarios/teste-lambda/teste_lambda.png

docker compose exec -T localstack awslocal s3 rm \
  s3://central-arquivos-processados/usuarios/teste-lambda/teste_lambda_thumb.jpg

rm -f teste_lambda.png thumb.jpg
```

> A Lambda é acionada **somente** pelo evento do S3. A aplicação não chama a
> função manualmente. Se você apagar o original diretamente pelo `awslocal`,
> a miniatura não é apagada automaticamente; remova as duas chaves.

---

## 6. Inspeção manual dos recursos

### 6.1 S3

Listar buckets:

```bash
docker compose exec -T localstack awslocal s3api list-buckets \
  --query "Buckets[].Name"
```

Listar originais:

```bash
docker compose exec -T localstack awslocal s3 ls \
  s3://central-arquivos-originais --recursive --human-readable
```

Listar miniaturas:

```bash
docker compose exec -T localstack awslocal s3 ls \
  s3://central-arquivos-processados --recursive --human-readable
```

Detalhes de um objeto:

```bash
docker compose exec -T localstack awslocal s3api head-object \
  --bucket central-arquivos-originais \
  --key "usuarios/<user_id>/<uuid>.png"
```

### 6.2 DynamoDB

Listar tabelas:

```bash
docker compose exec -T localstack awslocal dynamodb list-tables
```

Descrever a tabela e o índice:

```bash
docker compose exec -T localstack awslocal dynamodb describe-table \
  --table-name usuarios \
  --query "Table.{Chave:KeySchema,Indices:GlobalSecondaryIndexes[].IndexName,Status:TableStatus}"
```

Contar contas (sem imprimir hashes):

```bash
docker compose exec -T localstack awslocal dynamodb scan \
  --table-name usuarios \
  --filter-expression "tipo = :tipo" \
  --expression-attribute-values '{":tipo":{"S":"usuario"}}' \
  --select COUNT \
  --query "Count" --output text
```

### 6.3 Lambda

```bash
docker compose exec -T localstack awslocal lambda get-function \
  --function-name processar-imagem \
  --query "{Nome:Configuration.FunctionName,Arn:Configuration.FunctionArn,Estado:Configuration.State,CodigoBytes:Code.Size}"
```

Ver a permissão criada para o S3:

```bash
docker compose exec -T localstack awslocal lambda get-policy \
  --function-name processar-imagem
```

### 6.4 PostgreSQL

Tabelas:

```bash
docker compose exec db psql -U aplicacao -d aplicacao -c "\dt"
```

Metadados dos envios:

```bash
docker compose exec db psql -U aplicacao -d aplicacao \
  -c "select id, proprietario_id, nome_original, chave_s3, enviado_em from envios_arquivoenviado order by id desc limit 10;"
```

Sessões:

```bash
docker compose exec db psql -U aplicacao -d aplicacao \
  -c "select count(*) from django_session;"
```

### 6.5 Logs

```bash
docker compose logs -f web
docker compose logs -f nginx
docker compose logs -f localstack
docker compose logs -f provisionador
```

Para filtrar a Lambda:

```bash
docker compose logs --since 10m localstack | grep -Ei "miniatura|lambda|error|traceback"
```

---

## 7. Persistência e reinício

### 7.1 Reiniciar sem perder dados

```bash
docker compose restart
```

Ou derrubar e subir novamente mantendo os volumes:

```bash
docker compose down
docker compose up -d
```

O `provisionador` roda de novo de forma **idempotente**: ele reconhece os
buckets, a tabela, o índice e a função existentes, atualiza o código da Lambda
e reaplica a notificação do S3.

A persistência de S3 e DynamoDB é feita pela imagem
`gresau/localstack-persist:3.8.1`, que grava no volume
`localstack_persist_data` (montado em `/persisted-data`). A Lambda e o evento
S3 não são persistidos; o provisionador os recria a cada `up`.

Depois do reinício, confirme:

- a conta continua no DynamoDB;
- as imagens continuam nos dois buckets;
- a sessão pode continuar válida (a sessão fica no PostgreSQL);
- a Lambda continua configurada.

### 7.2 Recomeçar do zero (apaga dados)

Use apenas em ambiente descartável:

```bash
docker compose down -v
docker compose up --build -d
```

Isso remove `postgres_data`, `static_data` e `localstack_persist_data`. O
provisionador recria os recursos AWS simulados; as contas e imagens antigas
**não** voltam.

Se o diretório `.localstack-backup/` existir, remova-o também. Caso contrário,
o provisionador restaura o snapshot antigo no próximo `up`:

```bash
rm -rf .localstack-backup
```

### 7.3 Backup e restauração

O serviço `provisionador` monta `./.localstack-backup` em `/backup`. No
primeiro start com o volume novo, ele restaura o backup automaticamente
**somente se** os buckets e a tabela estiverem vazios. Depois disso, o backup
é ignorado para não sobrescrever dados novos.

O diretório `.localstack-backup/` é ignorado pelo Git. Ele pode conter hashes
de senha (nunca senhas em texto puro) e imagens; não faça commit dele.

Backup manual:

```bash
docker compose run --rm provisionador \
  python backup_localstack.py exportar --dir /backup
```

Restauração manual (faça depois que o provisionador já criou a tabela e os
buckets, por exemplo após um `docker compose up -d`):

```bash
docker compose run --rm provisionador \
  python backup_localstack.py importar --dir /backup --somente-se-vazio
```

Para começar do zero, remova o backup e o volume:

```bash
rm -rf .localstack-backup
docker compose down -v
```

### 7.4 Rebuild após mudança de código

O código é copiado para dentro da imagem no build (não há bind mount da
aplicação). Depois de alterar arquivos em `app/`, `lambda/` ou `infra/`:

```bash
docker compose up -d --build web provisionador
```

Se a mudança for só no handler da Lambda, o `provisionador` precisa rodar de
novo para atualizar o zip:

```bash
docker compose rm -sf provisionador
docker compose up -d --build provisionador
docker compose logs -f provisionador
```

Se a interface continuar com o CSS/JS antigo, confirme que o container `web`
foi realmente recriado (`docker compose ps`) e recarregue a página. O Nginx
serve `/static/` com `Cache-Control: no-cache` justamente para evitar esse
problema; o `web` antigo não tem o arquivo `app.js` novo.

---

## 8. Parar e limpar

Parar mantendo os dados:

```bash
docker compose down
```

Parar e remover também os volumes (apaga tudo):

```bash
docker compose down -v
```

Remover as imagens construídas localmente:

```bash
docker compose down --rmi local
```

O volume antigo `media_data` não é mais usado. Se ele existir de uma versão
anterior, não é montado nem apagado automaticamente. Para removê-lo
manualmente:

```bash
docker volume ls | grep media_data
# confira o nome exato antes de remover
docker volume rm <nome_do_volume_media_data>
```

O volume `localstack_data` da imagem oficial antiga também não é mais usado;
o novo é `localstack_persist_data`. Depois de confirmar que a conta e as
imagens foram restauradas, remova o antigo se quiser liberar espaço:

```bash
docker volume ls | grep localstack_data
# confira o nome exato antes de remover
docker volume rm <nome_do_volume_localstack_data>
```

---

## 9. Solução de problemas

### `POSTGRES_PASSWORD` obrigatória

**Sintoma:** o Compose reclama que `POSTGRES_PASSWORD` não foi definida.

**Causa:** falta o `.env` ou a variável está vazia.

```bash
cp .env.example .env
# edite POSTGRES_PASSWORD
docker compose up -d
```

### `provisionador` sai com código diferente de 0

```bash
docker compose logs provisionador
docker compose logs localstack | tail -n 100
```

Causas comuns:

- LocalStack ainda não estava saudável (o Compose espera o healthcheck, mas
  reinícios manuais podem atropelar);
- falha ao baixar a wheel do Pillow durante o build;
- permissão no socket do Docker.

Recrie o serviço:

```bash
docker compose rm -sf provisionador
docker compose up -d --build provisionador
docker compose logs -f provisionador
```

### Lambda em `Pending` ou `Failed`

Verifique:

```bash
docker compose exec localstack ls -l /var/run/docker.sock
docker compose logs localstack | grep -Ei "docker|lambda|error"
docker compose exec -T localstack awslocal lambda get-function-configuration \
  --function-name processar-imagem \
  --query "{Estado:State,UltimaAtualizacao:LastUpdateStatus,Motivo:StateReason}"
```

Checklist:

- `/var/run/docker.sock` está montado?
- o usuário tem permissão no socket?
- a rede do Compose se chama `rede_aplicacao`?
- `LAMBDA_DOCKER_NETWORK=rede_aplicacao` está no serviço `localstack`?
- a imagem `public.ecr.aws/lambda/python:3.12` consegue ser baixada?

Teste o download da imagem manualmente:

```bash
docker pull public.ecr.aws/lambda/python:3.12
```

### A miniatura nunca aparece (“Processando pela Lambda...”)

1. Confirme que o objeto está no bucket de originais e começa com `usuarios/`.
2. Confira a notificação do bucket (seção 5.3).
3. Confira a permissão S3 → Lambda:

   ```bash
   docker compose exec -T localstack awslocal lambda get-policy \
     --function-name processar-imagem
   ```

4. Veja os logs:

   ```bash
   docker compose logs --since 10m localstack | grep -Ei "miniatura|error|traceback"
   ```

5. Se for a primeira execução, aguarde o download da imagem da Lambda. O card
   é atualizado automaticamente quando a miniatura fica pronta; **Atualizar
   lista** serve como fallback.

### `502 Bad Gateway` no Nginx

O `web` ainda não subiu ou reiniciou:

```bash
docker compose ps
docker compose logs web
```

O `entrypoint.sh` espera o PostgreSQL, roda `migrate`, `collectstatic` e só
então inicia o Gunicorn. Se o banco estiver indisponível, o `web` falha.

### `CSRF verification failed` (403)

Acesse a aplicação por `http://localhost:8090` (não por um IP ou hostname
diferente). Se precisar usar outro endereço, ajuste no `.env`:

```dotenv
HOSTS_PERMITIDOS=localhost,127.0.0.1,meu-host
ORIGENS_CSRF_PERMITIDAS=http://localhost:8090,http://meu-host:8090
```

Depois reinicie o `web`:

```bash
docker compose up -d web
```

### Porta já em uso

**Sintoma:** `bind: address already in use`.

Descubra o processo:

```bash
ss -ltnp | grep -E '8090|15432|4566'
```

Altere no `.env`:

```dotenv
PORTA_NGINX=8091
PORTA_LOCALSTACK=4567
```

Para o PostgreSQL, a porta `15432` está fixa no `docker-compose.yml`; pare o
serviço conflitante ou ajuste o mapeamento no arquivo.

### LocalStack pede token de autenticação

O projeto usa `gresau/localstack-persist:3.8.1`, derivada da
`localstack/localstack:3.8.1`, justamente para evitar a exigência de
`LOCALSTACK_AUTH_TOKEN` das versões mais novas e manter a persistência de S3 e
DynamoDB sem o plano Pro. Não troque a tag sem antes ler a documentação de
licenciamento. Se for usar uma versão nova, configure o token no
`.env`/Compose; o código da aplicação não muda.

### Erro de plataforma em Mac com Apple Silicon

Se o LocalStack 3.8 reclamar de arquitetura, rode com emulação:

```bash
DOCKER_DEFAULT_PLATFORM=linux/amd64 docker compose up --build -d
```

### Dados “sumiram” depois de `down -v`

`down -v` remove os volumes, incluindo `localstack_persist_data`. Use
`docker compose down` (sem `-v`) no dia a dia. O projeto tem um snapshot
manual em `.localstack-backup/`, mas ele **não** é atualizado continuamente;
para um backup atualizado, rode o comando de exportação da seção 7.3 antes de
remover os volumes.

---

## 10. Comandos úteis

```bash
# Status e logs
docker compose ps
docker compose ps -a
docker compose logs -f web nginx
docker compose logs -f localstack

# Checagens do Django
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput

# Shell do Django
docker compose exec web python manage.py shell

# Shell do PostgreSQL
docker compose exec db psql -U aplicacao -d aplicacao

# S3
docker compose exec -T localstack awslocal s3 ls
docker compose exec -T localstack awslocal s3 ls s3://central-arquivos-originais --recursive
docker compose exec -T localstack awslocal s3 ls s3://central-arquivos-processados --recursive

# DynamoDB
docker compose exec -T localstack awslocal dynamodb list-tables
docker compose exec -T localstack awslocal dynamodb scan --table-name usuarios

# Lambda
docker compose exec -T localstack awslocal lambda list-functions
docker compose exec -T localstack awslocal lambda get-function-configuration \
  --function-name processar-imagem

# Reiniciar um serviço
docker compose restart web
docker compose up -d --build web

# Recriar o provisionamento
docker compose rm -sf provisionador
docker compose up -d provisionador
```

---

## 11. Checklist de aceitação

### S3

- [ ] Os buckets `central-arquivos-originais` e `central-arquivos-processados`
      existem.
- [ ] O upload grava o objeto em `usuarios/<user_id>/<uuid>.<ext>`.
- [ ] A listagem lê do S3 e mostra a imagem.
- [ ] O download do original devolve o mesmo conteúdo (hash igual).
- [ ] Arquivo de texto com extensão `.png` é recusado.
- [ ] Arquivo acima de 10 MB é recusado.
- [ ] Uma conta não acessa a chave de outra (404).

### DynamoDB

- [ ] O cadastro cria o item `tipo=usuario` e a reserva `email#<email>`.
- [ ] `senha_hash` começa com `pbkdf2_sha256$` e não é a senha em texto puro.
- [ ] O mesmo e-mail não pode ser cadastrado duas vezes.
- [ ] O login correto entra na área privada.
- [ ] O login com senha errada mostra mensagem genérica.
- [ ] A área privada redireciona para `/login/` sem sessão.
- [ ] O logout encerra a sessão.

### Lambda

- [ ] A função `processar-imagem` está `Active`.
- [ ] O bucket de originais tem evento `s3:ObjectCreated:*` com prefixo
      `usuarios/`.
- [ ] O bucket de processados não tem gatilho.
- [ ] O upload dispara a Lambda automaticamente (sem chamada manual).
- [ ] A miniatura `_thumb.jpg` aparece no bucket de processados.
- [ ] A miniatura tem largura máxima de 300 px e proporção preservada.
- [ ] Imagens menores que 300 px não são ampliadas.
- [ ] A interface mostra **Processada** e permite baixar a miniatura.

### Persistência

- [ ] `docker compose down` + `docker compose up -d` mantém contas e imagens.
- [ ] `docker compose down -v` remove tudo e o provisionador recria os
      recursos no próximo `up`.

---

## 12. Onde cada coisa está no código

| Assunto | Arquivo |
|---|---|
| Clientes boto3 (S3/DynamoDB) | `app/envios/aws/clientes.py` |
| Contas, hash e login no DynamoDB | `app/envios/aws/usuarios.py` |
| Upload/listagem/download no S3 | `app/envios/aws/arquivos.py` |
| Cadastro, login, upload e downloads | `app/envios/views.py` |
| Formulários e limites | `app/envios/forms.py` |
| Validação real da imagem (Pillow) | `app/envios/validacao.py` |
| Sessão e middleware | `app/envios/sessao.py`, `app/envios/middleware.py` |
| Rotas | `app/envios/urls.py` |
| Metadados/auditoria no PostgreSQL | `app/envios/models.py` |
| Handler da Lambda | `lambda/processar_imagem.py` |
| Provisionamento idempotente | `infra/localstack/init_aws.py` |
| Build do zip da Lambda | `infra/localstack/Dockerfile` |
| Orquestração | `docker-compose.yml` |
| Proxy reverso e estáticos | `nginx/default.conf` |
| Diagramas e decisões | `docs/arquitetura.md` |
| Visão geral | `README.md` |
