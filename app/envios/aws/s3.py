"""Cliente S3 usado pela aplicação.

O mesmo código funciona com LocalStack e com a AWS real; apenas o endpoint
é configurado por variável de ambiente.
"""

from __future__ import annotations

from typing import BinaryIO

import boto3
from botocore.config import Config
from django.conf import settings


def cliente_s3():
    """Retorna um cliente S3 configurado para o ambiente atual."""
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_ENDPOINT_URL,
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def listar_buckets() -> list[str]:
    """Retorna os nomes dos buckets visíveis para a aplicação."""
    resposta = cliente_s3().list_buckets()
    return [bucket["Name"] for bucket in resposta.get("Buckets", [])]


def enviar_arquivo(chave: str, arquivo: BinaryIO, *, content_type: str) -> None:
    """Envia um arquivo para o bucket de originais."""
    cliente_s3().upload_fileobj(
        arquivo,
        settings.S3_BUCKET_ORIGINAIS,
        chave,
        ExtraArgs={"ContentType": content_type},
    )


def obter_arquivo(chave: str):
    """Obtém um objeto do bucket de originais."""
    return cliente_s3().get_object(
        Bucket=settings.S3_BUCKET_ORIGINAIS,
        Key=chave,
    )
