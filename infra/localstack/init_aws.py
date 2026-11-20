#!/usr/bin/env python3
"""Provisiona S3, DynamoDB e Lambda no LocalStack de forma idempotente.

Executado uma vez pelo serviço ``provisionador`` do Docker Compose. Pode ser
reexecutado sem falhar: verifica a existência de cada recurso antes de criar,
atualiza o código da Lambda e reaplica a notificação do bucket.

Ordem:
1. aguardar S3, DynamoDB e Lambda ficarem disponíveis;
2. criar os buckets de originais e processados;
3. criar a tabela ``usuarios`` e o índice ``email-index``;
4. criar/atualizar a função Lambda;
5. permitir que o S3 invoque a Lambda;
6. configurar o evento ``ObjectCreated`` no bucket de originais;
7. garantir que o bucket de processados não tenha gatilho.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localstack:4566")
REGION = os.getenv("AWS_REGION", "us-east-1")
ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "test")
SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "test")

BUCKET_ORIGINAIS = os.getenv("S3_BUCKET_ORIGINAIS", "central-arquivos-originais")
BUCKET_PROCESSADOS = os.getenv("S3_BUCKET_PROCESSADOS", "central-arquivos-processados")
TABELA_USUARIOS = os.getenv("DYNAMODB_TABLE_USUARIOS", "usuarios")
INDICE_EMAIL = os.getenv("DYNAMODB_INDICE_EMAIL", "email-index")
FUNCAO_LAMBDA = os.getenv("LAMBDA_FUNCAO", "processar-imagem")
LARGURA_MINIATURA = os.getenv("LARGURA_MAXIMA_MINIATURA", "300")
CAMINHO_ZIP = os.getenv("LAMBDA_ZIP", "/lambda.zip")
ROLE_LAMBDA = "arn:aws:iam::000000000000:role/lambda-role"
STATEMENT_ID = "s3-invoke-originais"


def log(mensagem: str) -> None:
    print(f"[provisionador] {mensagem}", flush=True)


def configuracao() -> Config:
    return Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        retries={"max_attempts": 5, "mode": "standard"},
        connect_timeout=5,
        read_timeout=60,
    )


def clientes():
    parametros = {
        "endpoint_url": ENDPOINT,
        "region_name": REGION,
        "aws_access_key_id": ACCESS_KEY,
        "aws_secret_access_key": SECRET_KEY,
        "config": configuracao(),
    }
    return (
        boto3.client("s3", **parametros),
        boto3.client("dynamodb", **parametros),
        boto3.client("lambda", **parametros),
    )


def aguardar_localstack(tentativas: int = 60) -> None:
    url = f"{ENDPOINT.rstrip('/')}/_localstack/health"
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(url, timeout=5) as resposta:
                dados = json.load(resposta)
            servicos = dados.get("services", {})
            estados = {nome: servicos.get(nome) for nome in ("s3", "dynamodb", "lambda")}
            prontos = all(
                estado in ("available", "running") for estado in estados.values()
            )
            if prontos:
                log(f"LocalStack pronto: {estados}")
                return
            ultimo_erro = f"serviços ainda não prontos: {estados}"
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            ultimo_erro = exc
        log(f"aguardando LocalStack ({tentativa}/{tentativas})...")
        time.sleep(2)
    raise RuntimeError(f"LocalStack não ficou pronto: {ultimo_erro}")


def garantir_bucket(s3, nome: str) -> None:
    try:
        s3.head_bucket(Bucket=nome)
        log(f"bucket já existe: {nome}")
        return
    except ClientError as exc:
        codigo = exc.response.get("Error", {}).get("Code", "")
        if codigo not in {"404", "NoSuchBucket", "NotFound"}:
            raise
    s3.create_bucket(Bucket=nome)
    log(f"bucket criado: {nome}")


def aguardar_indice_ativo(dynamodb, tentativas: int = 60) -> None:
    """O ``table_exists`` não garante que o GSI já esteja ACTIVE."""
    for _ in range(tentativas):
        descricao = dynamodb.describe_table(TableName=TABELA_USUARIOS)["Table"]
        indices = {
            indice["IndexName"]: indice.get("IndexStatus")
            for indice in descricao.get("GlobalSecondaryIndexes", [])
        }
        if indices.get(INDICE_EMAIL) == "ACTIVE":
            log(f"índice ativo: {INDICE_EMAIL}")
            return
        time.sleep(2)
    raise RuntimeError(f"O índice {INDICE_EMAIL} não ficou ACTIVE no tempo esperado")


def garantir_tabela(dynamodb) -> None:
    try:
        descricao = dynamodb.describe_table(TableName=TABELA_USUARIOS)["Table"]
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise
        dynamodb.create_table(
            TableName=TABELA_USUARIOS,
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "email", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": INDICE_EMAIL,
                    "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        log(f"tabela criada: {TABELA_USUARIOS} (índice {INDICE_EMAIL})")
        dynamodb.get_waiter("table_exists").wait(
            TableName=TABELA_USUARIOS,
            WaiterConfig={"Delay": 2, "MaxAttempts": 60},
        )
        aguardar_indice_ativo(dynamodb)
        return

    indices = {
        indice["IndexName"] for indice in descricao.get("GlobalSecondaryIndexes", [])
    }
    if INDICE_EMAIL in indices:
        log(f"tabela já existe: {TABELA_USUARIOS}")
        aguardar_indice_ativo(dynamodb)
        return

    log(f"adicionando índice {INDICE_EMAIL} à tabela existente")
    dynamodb.update_table(
        TableName=TABELA_USUARIOS,
        AttributeDefinitions=[{"AttributeName": "email", "AttributeType": "S"}],
        GlobalSecondaryIndexUpdates=[
            {
                "Create": {
                    "IndexName": INDICE_EMAIL,
                    "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            }
        ],
    )
    dynamodb.get_waiter("table_exists").wait(
        TableName=TABELA_USUARIOS,
        WaiterConfig={"Delay": 2, "MaxAttempts": 60},
    )
    aguardar_indice_ativo(dynamodb)
    log("índice criado")


def ler_zip_lambda() -> bytes:
    with open(CAMINHO_ZIP, "rb") as arquivo:
        conteudo = arquivo.read()
    if not conteudo:
        raise RuntimeError(f"Pacote Lambda vazio: {CAMINHO_ZIP}")
    log(f"pacote Lambda: {len(conteudo)} bytes")
    return conteudo


def variaveis_lambda() -> dict[str, str]:
    return {
        "S3_BUCKET_ORIGINAIS": BUCKET_ORIGINAIS,
        "S3_BUCKET_PROCESSADOS": BUCKET_PROCESSADOS,
        "LARGURA_MAXIMA_MINIATURA": LARGURA_MINIATURA,
        "AWS_ENDPOINT_URL": "http://localstack:4566",
        "AWS_REGION": REGION,
        "AWS_DEFAULT_REGION": REGION,
        "AWS_ACCESS_KEY_ID": ACCESS_KEY,
        "AWS_SECRET_ACCESS_KEY": SECRET_KEY,
    }


def aguardar_lambda_ativa(lambda_client) -> dict:
    for _ in range(90):
        configuracao_funcao = lambda_client.get_function(
            FunctionName=FUNCAO_LAMBDA
        )["Configuration"]
        estado = configuracao_funcao.get("State", "Active")
        ultima_atualizacao = configuracao_funcao.get("LastUpdateStatus", "Successful")
        if estado == "Active" and ultima_atualizacao in (None, "Successful"):
            return configuracao_funcao
        time.sleep(2)
    raise RuntimeError("A função Lambda não ficou ativa no tempo esperado")


def garantir_lambda(lambda_client) -> dict:
    codigo = ler_zip_lambda()
    try:
        lambda_client.get_function(FunctionName=FUNCAO_LAMBDA)
        existe = True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise
        existe = False

    if not existe:
        lambda_client.create_function(
            FunctionName=FUNCAO_LAMBDA,
            Runtime="python3.12",
            Role=ROLE_LAMBDA,
            Handler="processar_imagem.handler",
            Code={"ZipFile": codigo},
            Timeout=60,
            MemorySize=512,
            Environment={"Variables": variaveis_lambda()},
            Tags={"projeto": "central-de-arquivos"},
        )
        log(f"função Lambda criada: {FUNCAO_LAMBDA}")
    else:
        # Evita atualizar uma função que ainda está em Pending/Creating.
        aguardar_lambda_ativa(lambda_client)
        lambda_client.update_function_code(FunctionName=FUNCAO_LAMBDA, ZipFile=codigo)
        lambda_client.update_function_configuration(
            FunctionName=FUNCAO_LAMBDA,
            Runtime="python3.12",
            Role=ROLE_LAMBDA,
            Handler="processar_imagem.handler",
            Timeout=60,
            MemorySize=512,
            Environment={"Variables": variaveis_lambda()},
        )
        log(f"função Lambda atualizada: {FUNCAO_LAMBDA}")

    return aguardar_lambda_ativa(lambda_client)


def garantir_permissao_s3(lambda_client, arn_funcao: str) -> None:
    try:
        lambda_client.add_permission(
            FunctionName=FUNCAO_LAMBDA,
            StatementId=STATEMENT_ID,
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn=f"arn:aws:s3:::{BUCKET_ORIGINAIS}",
        )
        log("permissão S3 -> Lambda criada")
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ResourceConflictException":
            log("permissão S3 -> Lambda já existe")
            return
        raise


def configurar_eventos(s3, arn_funcao: str) -> None:
    s3.put_bucket_notification_configuration(
        Bucket=BUCKET_ORIGINAIS,
        NotificationConfiguration={
            "LambdaFunctionConfigurations": [
                {
                    "Id": "processar-imagem-criada",
                    "LambdaFunctionArn": arn_funcao,
                    "Events": ["s3:ObjectCreated:*"],
                    "Filter": {
                        "Key": {
                            "FilterRules": [
                                {"Name": "prefix", "Value": "usuarios/"},
                            ]
                        }
                    },
                }
            ]
        },
    )
    log(f"evento ObjectCreated configurado no bucket {BUCKET_ORIGINAIS}")

    # Reforça que o bucket de saída não dispara a Lambda (sem recursão).
    s3.put_bucket_notification_configuration(
        Bucket=BUCKET_PROCESSADOS,
        NotificationConfiguration={},
    )
    log(f"bucket de processados sem gatilho: {BUCKET_PROCESSADOS}")


def main() -> int:
    log(f"endpoint: {ENDPOINT} | região: {REGION}")
    aguardar_localstack()
    s3, dynamodb, lambda_client = clientes()

    garantir_bucket(s3, BUCKET_ORIGINAIS)
    garantir_bucket(s3, BUCKET_PROCESSADOS)
    garantir_tabela(dynamodb)

    configuracao_funcao = garantir_lambda(lambda_client)
    arn_funcao = configuracao_funcao["FunctionArn"]

    garantir_permissao_s3(lambda_client, arn_funcao)
    configurar_eventos(s3, arn_funcao)

    log("provisionamento concluído com sucesso")
    log(f"  bucket originais:  {BUCKET_ORIGINAIS}")
    log(f"  bucket processados:{BUCKET_PROCESSADOS}")
    log(f"  tabela DynamoDB:   {TABELA_USUARIOS} (índice {INDICE_EMAIL})")
    log(f"  função Lambda:     {FUNCAO_LAMBDA} ({arn_funcao})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as erro:  # pragma: no cover - falha visível nos logs
        log(f"ERRO: {erro}")
        raise
