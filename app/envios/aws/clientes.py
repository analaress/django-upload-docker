"""Fábrica de clientes boto3 apontando para o LocalStack.

Os clientes são criados uma única vez por processo (Gunicorn) e reutilizam
a mesma configuração de endpoint, região e credenciais fictícias. Dentro da
rede Docker, o endpoint correto é ``http://localstack:4566``; nunca use
``localhost`` dentro de um container.
"""

from functools import lru_cache

import boto3
from botocore.config import Config
from django.conf import settings


def _configuracao() -> Config:
    return Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        retries={"max_attempts": 3, "mode": "standard"},
        connect_timeout=5,
        read_timeout=30,
    )


def _parametros_comuns() -> dict:
    return {
        "endpoint_url": settings.AWS_ENDPOINT_URL,
        "region_name": settings.AWS_REGION,
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        "config": _configuracao(),
    }


@lru_cache(maxsize=1)
def cliente_s3():
    """Cliente S3 configurado para o LocalStack (path-style)."""
    return boto3.client("s3", **_parametros_comuns())


@lru_cache(maxsize=1)
def cliente_dynamodb():
    """Cliente DynamoDB de baixo nível.

    Usamos o cliente (e não o ``boto3.resource``) porque o recurso registra
    um desserializador de documentos que também transforma os itens de
    ``TransactWriteItems``, duplicando a serialização (``{"M": {"S": ...}}``).
    """
    return boto3.client("dynamodb", **_parametros_comuns())
