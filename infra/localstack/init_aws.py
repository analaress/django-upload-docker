import json
import os
import time
import urllib.request

import boto3
from botocore.exceptions import ClientError

ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localstack:4566")
REGION = os.getenv("AWS_REGION", "us-east-1")
ACCESS = os.getenv("AWS_ACCESS_KEY_ID", "test")
SECRET = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
ORIGINAIS = os.getenv("S3_BUCKET_ORIGINAIS", "central-arquivos-originais")
PROCESSADOS = os.getenv("S3_BUCKET_PROCESSADOS", "central-arquivos-processados")
FUNCAO = os.getenv("LAMBDA_FUNCAO", "processar-imagem")


def clientes():
    args = dict(
        endpoint_url=ENDPOINT,
        region_name=REGION,
        aws_access_key_id=ACCESS,
        aws_secret_access_key=SECRET,
    )
    return boto3.client("s3", **args), boto3.client("lambda", **args)


def esperar_localstack():
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"{ENDPOINT}/_localstack/health", timeout=3):
                return
        except Exception:
            time.sleep(2)
    raise RuntimeError("LocalStack não ficou disponível")


def garantir_bucket(s3, nome):
    try:
        s3.head_bucket(Bucket=nome)
    except ClientError:
        s3.create_bucket(Bucket=nome)


def garantir_lambda(lambda_client):
    with open("/provisionador/lambda.zip", "rb") as pacote:
        codigo = pacote.read()
    args = dict(
        FunctionName=FUNCAO,
        Runtime="python3.12",
        Role="arn:aws:iam::000000000000:role/lambda-role",
        Handler="processar_imagem.handler",
        Timeout=60,
        MemorySize=512,
        Environment={"Variables": {
            "AWS_ENDPOINT_URL": ENDPOINT,
            "AWS_REGION": REGION,
            "AWS_ACCESS_KEY_ID": ACCESS,
            "AWS_SECRET_ACCESS_KEY": SECRET,
            "S3_BUCKET_ORIGINAIS": ORIGINAIS,
            "S3_BUCKET_PROCESSADOS": PROCESSADOS,
        }},
    )
    try:
        lambda_client.get_function(FunctionName=FUNCAO)
        aguardar_lambda(lambda_client)
        lambda_client.update_function_code(FunctionName=FUNCAO, ZipFile=codigo)
        aguardar_lambda(lambda_client)
        lambda_client.update_function_configuration(**args)
    except ClientError as erro:
        if erro.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        lambda_client.create_function(Code={"ZipFile": codigo}, **args)


def aguardar_lambda(lambda_client):
    for _ in range(60):
        configuracao = lambda_client.get_function(FunctionName=FUNCAO)["Configuration"]
        if configuracao.get("State", "Active") == "Active" and configuracao.get(
            "LastUpdateStatus", "Successful"
        ) == "Successful":
            return configuracao
        time.sleep(2)
    raise RuntimeError("Lambda não ficou ativa no tempo esperado")


def configurar_gatilho(s3, lambda_client):
    funcao = aguardar_lambda(lambda_client)
    arn = funcao["FunctionArn"]
    try:
        lambda_client.add_permission(
            FunctionName=FUNCAO,
            StatementId="s3-invoke-processar-imagem",
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn=f"arn:aws:s3:::{ORIGINAIS}",
        )
    except ClientError as erro:
        if erro.response["Error"]["Code"] != "ResourceConflictException":
            raise
    s3.put_bucket_notification_configuration(
        Bucket=ORIGINAIS,
        NotificationConfiguration={
            "LambdaFunctionConfigurations": [
                {"LambdaFunctionArn": arn, "Events": ["s3:ObjectCreated:*"]}
            ]
        },
    )


def main():
    esperar_localstack()
    s3, lambda_client = clientes()
    garantir_bucket(s3, ORIGINAIS)
    garantir_bucket(s3, PROCESSADOS)
    garantir_lambda(lambda_client)
    configurar_gatilho(s3, lambda_client)
    print(json.dumps({"buckets": [ORIGINAIS, PROCESSADOS], "lambda": FUNCAO}))


if __name__ == "__main__":
    main()
