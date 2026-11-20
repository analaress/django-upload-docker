# Apresentação — Central de Arquivos

## 1. Resumo do projeto

A Central de Arquivos é uma aplicação web feita principalmente em Python com Django. Ela permite criar contas, autenticar usuários, enviar imagens, listar e baixar arquivos. O armazenamento de imagens usa a API do Amazon S3, as contas ficam no DynamoDB e uma função Lambda processa cada imagem enviada, gerando uma miniatura.

O projeto roda localmente com Docker Compose e LocalStack. O LocalStack simula os serviços da AWS, então esta implementação demonstra a integração com S3, DynamoDB e Lambda sem usar a infraestrutura real da AWS.

Uma forma curta de apresentar o objetivo é:

> O navegador envia uma imagem para o Django. O Django valida o arquivo e o salva no S3. O evento de criação do objeto aciona uma Lambda, que gera uma miniatura e a grava em outro bucket. O cadastro e a autenticação dos usuários consultam o DynamoDB.

## 2. Linguagens e tecnologias

É útil separar **linguagens de programação** de **frameworks e serviços**. Por exemplo, Python é uma linguagem; Django é o framework web usado com Python.

| Linguagem ou tecnologia | Papel no projeto | Onde consultar |
|---|---|---|
| **Python** | Linguagem principal do backend Django, do provisionador AWS local e da função Lambda. Implementa rotas, validação, integração com AWS e processamento de imagens. | `app/`, `infra/localstack/init_aws.py`, `lambda/processar_imagem.py` |
| **HTML** | Define a estrutura das páginas, formulários, lista de imagens e links de download, renderizados pelo Django. | `app/envios/templates/envios/` |
| **CSS** | Define a apresentação visual e o comportamento responsivo da interface. | `app/envios/static/envios/estilos.css` |
| **JavaScript** | Atualiza os nomes dos arquivos selecionados, permite arrastar e soltar imagens e consulta periodicamente o status da miniatura para atualizar a página sem recarregá-la. | `app/envios/static/envios/app.js` |
| **SQL** | O Django usa o ORM e migrations para trabalhar com PostgreSQL. O banco guarda sessões, registros administrativos e metadados dos uploads; não é a fonte principal das contas nem do conteúdo das imagens. | `app/config/settings.py`, `app/envios/models.py`, `app/envios/migrations/` |
| **Shell (sh)** | Automatiza a inicialização do container web: espera o PostgreSQL, aplica migrations, coleta arquivos estáticos e inicia o Gunicorn. | `entrypoint.sh`, `executar.sh` |
| **YAML** | Descreve os serviços, variáveis, volumes, dependências e rede usados pelo Docker Compose. Não é uma linguagem da aplicação web. | `docker-compose.yml` |

Outras tecnologias importantes:

- **Django:** framework Python que recebe requisições HTTP, valida formulários, chama a lógica de negócio, controla sessões e renderiza templates.
- **Boto3:** SDK Python usado pelo backend e pelo provisionador para chamar as APIs compatíveis da AWS no LocalStack.
- **Pillow:** biblioteca Python que identifica imagens no upload e redimensiona as imagens na Lambda.
- **PostgreSQL:** banco relacional usado para sessões do Django e dados auxiliares.
- **Amazon S3, DynamoDB e Lambda:** serviços simulados pelo LocalStack neste projeto.
- **Docker e Docker Compose:** isolam e conectam os serviços necessários para executar a aplicação.
- **Nginx e Gunicorn:** Nginx recebe as requisições do navegador e as encaminha ao Gunicorn, que executa a aplicação Django.

## 3. Como as partes se comunicam

### Caminho geral de uma requisição

1. O navegador solicita uma página ou envia um formulário para o endereço publicado pelo Nginx.
2. O Nginx serve os arquivos estáticos em `/static/` e encaminha as demais requisições ao serviço `web`.
3. O Gunicorn executa o Django. As rotas principais são incluídas em `app/config/urls.py` e declaradas em `app/envios/urls.py`.
4. A view correspondente executa a ação: renderiza uma página, valida um formulário ou chama uma integração AWS.
5. O backend usa Boto3 para acessar o LocalStack em `http://localstack:4566`. As chamadas dos containers usam o nome do serviço `localstack`, não `localhost`.
6. O Django devolve HTML, JSON, um redirecionamento ou o conteúdo de um arquivo ao navegador.

O fluxo de rede do Compose pode ser resumido assim:

```text
Navegador -> Nginx -> Gunicorn/Django -> Boto3 -> LocalStack
                                      -> PostgreSQL
```

Os containers se encontram na rede interna `rede_aplicacao`, configurada em `docker-compose.yml`.

### Cadastro e autenticação

1. O navegador envia o formulário de cadastro ou login para as rotas `/cadastro/` ou `/login/`.
2. As views em `app/envios/views.py` validam os formulários definidos em `app/envios/forms.py`.
3. Para criar uma conta, `criar_usuario` em `app/envios/aws/usuarios.py` gera um hash para a senha e grava os dados no DynamoDB. A operação também reserva o e-mail numa transação para impedir cadastros duplicados.
4. No login, `autenticar` consulta o índice `email-index` do DynamoDB e compara a senha informada com o hash armazenado.
5. Após o login, o Django cria uma sessão. A sessão fica no PostgreSQL e contém o identificador do usuário, não a senha.
6. O middleware `app/envios/middleware.py` consulta o DynamoDB pelo identificador da sessão e disponibiliza o usuário para as views.

Assim, **o DynamoDB é a fonte dos dados da conta e da verificação de credenciais**. O PostgreSQL participa da sessão web, mas não substitui o DynamoDB na autenticação.

### Upload, listagem e download de imagens

1. Um usuário autenticado envia uma ou mais imagens pelo formulário da página inicial.
2. A view `enviar_arquivo` em `app/envios/views.py` valida cada arquivo usando `validar_imagem`, de `app/envios/validacao.py`.
3. A validação verifica o conteúdo real da imagem com Pillow, não confia apenas no nome ou na extensão. São aceitos JPEG, PNG, GIF e WEBP.
4. `enviar_imagem`, em `app/envios/aws/arquivos.py`, chama `put_object` e grava a imagem no bucket de originais.
5. A página inicial chama `listar_imagens_do_usuario`, que lista os objetos do S3 usando o prefixo do usuário. O PostgreSQL pode complementar a exibição com o nome original e outros metadados.
6. Para baixar, uma view autenticada chama `obter_objeto` no S3 e transmite a resposta ao navegador. A autorização confere que a chave pertence ao usuário da sessão.

O conteúdo binário fica no S3. O PostgreSQL guarda apenas informações auxiliares; ele não armazena a imagem.

### Processamento automático com Lambda

1. O serviço `provisionador` executa `infra/localstack/init_aws.py` quando os serviços do LocalStack estão disponíveis.
2. O provisionador cria ou atualiza os buckets, a tabela DynamoDB, a função Lambda e a permissão para o S3 invocá-la.
3. Também configura uma notificação `s3:ObjectCreated:*` no bucket de originais, filtrada pelo prefixo `usuarios/`.
4. Quando uma imagem é enviada, o S3/LocalStack publica o evento e invoca automaticamente `handler` em `lambda/processar_imagem.py`. O Django **não** chama a Lambda diretamente.
5. A Lambda lê o objeto original, corrige a orientação EXIF quando aplicável, redimensiona a imagem para no máximo 300 pixels de largura e grava o JPEG no bucket de processados.
6. O bucket de processados não tem notificação para a Lambda. Isso evita um ciclo em que o resultado gerado acionaria a própria função novamente.
7. Enquanto a miniatura não existe, o JavaScript em `app/envios/static/envios/app.js` consulta o endpoint de status. Quando o backend encontra a miniatura no S3, o navegador atualiza o cartão e mostra os links de visualização e download.

## 4. Mapa dos arquivos principais

| Arquivo ou diretório | Responsabilidade |
|---|---|
| `app/config/urls.py` | Inclui as rotas da aplicação e do admin do Django. |
| `app/envios/urls.py` | Mapeia URLs para views de cadastro, login, upload, listagem e download. |
| `app/envios/views.py` | Coordena os fluxos web e chama as operações de S3 e DynamoDB. |
| `app/envios/forms.py` | Define e valida os campos de cadastro, login e upload múltiplo. |
| `app/envios/validacao.py` | Valida formato, tamanho e conteúdo real das imagens. |
| `app/envios/aws/clientes.py` | Cria os clientes Boto3 de S3 e DynamoDB apontados para o LocalStack. |
| `app/envios/aws/arquivos.py` | Implementa upload, listagem, consulta e leitura de objetos do S3. |
| `app/envios/aws/usuarios.py` | Implementa criação, busca e autenticação de contas no DynamoDB. |
| `app/envios/middleware.py` | Recupera do DynamoDB a conta identificada pela sessão. |
| `app/envios/sessao.py` | Cria e encerra sessões Django associadas a um usuário. |
| `app/envios/models.py` | Define metadados auxiliares dos uploads guardados no PostgreSQL. |
| `app/envios/templates/envios/` | Contém as páginas HTML renderizadas pelo Django. |
| `app/envios/static/envios/` | Contém CSS e JavaScript da interface. |
| `infra/localstack/init_aws.py` | Provisiona buckets, tabela, função Lambda, permissões e notificação S3. |
| `infra/localstack/Dockerfile` | Instala dependências e empacota o código da Lambda para o runtime Python. |
| `lambda/processar_imagem.py` | Processa a imagem recebida no evento S3 e grava a miniatura. |
| `docker-compose.yml` | Define os containers, a rede, as dependências e os volumes. |
| `entrypoint.sh` | Prepara o Django e inicia o servidor Gunicorn no container web. |
| `nginx/default.conf` | Encaminha requisições ao Django e serve os arquivos estáticos. |
| `COMANDOS.md` | Explica como iniciar o ambiente e executar verificações manuais das atividades. |

## 5. Perguntas que podem surgir

### Onde acontece a comunicação com o S3?

As operações estão em `app/envios/aws/arquivos.py`. O cliente é criado em `app/envios/aws/clientes.py`, que usa o endpoint do LocalStack definido pelas configurações. As views em `app/envios/views.py` chamam essas operações para upload, listagem e download.

### Qual rota recebe o upload?

`/enviar/`, mapeada para a view `enviar_arquivo` em `app/envios/urls.py`. Ela exige uma sessão autenticada e recebe os arquivos como formulário `multipart/form-data`.

### Onde os arquivos ficam armazenados?

Os binários originais ficam no bucket S3 configurado como `S3_BUCKET_ORIGINAIS`; as miniaturas ficam em `S3_BUCKET_PROCESSADOS`. O PostgreSQL guarda metadados auxiliares, não os binários.

### Como a aplicação mostra os arquivos de cada usuário?

As chaves S3 são criadas com o prefixo `usuarios/<id-do-usuario>/`. A listagem consulta esse prefixo, e as rotas de arquivo conferem se a chave pertence ao usuário autenticado antes de entregar o conteúdo.

### Onde ocorre o cadastro e a autenticação no DynamoDB?

No módulo `app/envios/aws/usuarios.py`: `criar_usuario` grava a conta e `autenticar` busca a conta e verifica a senha. As views de cadastro e login chamam essas funções.

### A senha fica armazenada em texto puro?

Não. O Django gera um hash com `make_password`, que é gravado como `senha_hash`. No login, `check_password` compara a senha informada com o hash.

### Por que existe PostgreSQL se a atividade pede DynamoDB?

O PostgreSQL tem funções auxiliares: armazena as sessões do Django e os metadados dos uploads. As contas e a autenticação da aplicação usam DynamoDB, e os arquivos usam S3.

### O Django chama a Lambda diretamente?

Não. O provisionador configura a notificação do bucket S3. Depois, o próprio evento de criação do objeto aciona a Lambda. Isso demonstra o fluxo orientado a eventos pedido na atividade.

### O que a Lambda faz com a imagem?

Lê o original no S3, corrige orientação EXIF quando necessário, converte para JPEG e limita a largura a 300 pixels sem ampliar imagens menores. O resultado vai para o bucket de processados.

### Como o navegador sabe que o processamento terminou?

O JavaScript consulta periodicamente uma rota de status do Django. Essa rota verifica se a miniatura já existe no bucket de processados; quando existe, o navegador atualiza a interface.

### Por que usar dois buckets?

Um guarda os originais e o outro as miniaturas processadas. Além de separar entrada e saída, o bucket de saída não aciona a Lambda, evitando processamento recursivo.

### O projeto usa AWS real?

Não no fluxo local documentado. Usa LocalStack para simular serviços compatíveis com as APIs AWS. O objetivo é desenvolver e demonstrar a integração localmente; isso não significa que a aplicação já esteja configurada para produção na AWS.

### Quais formatos e limites são aceitos?

JPEG, PNG, GIF e WEBP. O limite padrão é 10 MB por imagem e cinco imagens por envio, configuráveis por variáveis de ambiente. A interface e a validação do backend aplicam esses critérios.

### O sistema aceita qualquer tipo de arquivo?

Não. Apesar de ser uma central de arquivos, a implementação atual é focada em imagens, em especial por causa do processamento da Lambda. Documentos como PDF, DOCX e PPTX não são aceitos pelo validador atual.

### Onde ficam os endereços de conexão?

As variáveis de ambiente do Django e do provisionador são definidas no `docker-compose.yml`. Dentro da rede Docker, a aplicação acessa `http://localstack:4566`; o navegador acessa a aplicação pelo endereço publicado pelo Nginx, normalmente `http://localhost:8090`.

### Como os serviços são iniciados?

O Docker Compose inicia PostgreSQL e LocalStack. Depois que o LocalStack está saudável, o serviço `provisionador` cria os recursos AWS simulados. O serviço web aguarda PostgreSQL, aplica migrations e inicia Gunicorn; o Nginx encaminha o tráfego para ele.

## . Pontos importantes e limites

- O projeto foi reaproveitado e mantém tecnologias auxiliares como PostgreSQL, Nginx e Docker. Elas não substituem os serviços centrais do enunciado: S3 e DynamoDB são usados via LocalStack, e a Lambda é acionada por evento do S3.
- O LocalStack é uma simulação local, não uma conta AWS real. Credenciais fictícias como `test` são destinadas a esse ambiente.
- O upload é focado em imagens; o validador aceita JPEG, PNG, GIF e WEBP, não documentos genéricos.
- A listagem usa o S3 como fonte dos objetos. Se o registro de metadados no PostgreSQL falhar após um upload, o objeto ainda pode aparecer, embora alguns detalhes apresentados possam usar valores derivados da chave.
- A análise deste documento descreve o que está implementado no código. Para afirmar que o ambiente está funcionando, é necessário6xecutar o roteiro de `COMANDOS.md` e observar o provisionador, os buckets e a invocação da Lambda.