"""Função AWS Lambda que gera miniaturas das imagens enviadas ao S3.

Gatilho: evento ``s3:ObjectCreated:*`` do bucket de originais, com prefixo
``usuarios/``. A saída vai para outro bucket (``central-arquivos-processados``),
que não possui gatilho, evitando invocação recursiva.

Regra de processamento: largura máxima de 300 px, proporção preservada,
saída em JPEG. Imagens menores que 300 px não são ampliadas.
"""

from __future__ import annotations

import json
import logging
import os
import posixpath
from io import BytesIO
from urllib.parse import unquote_plus

import boto3
from botocore.config import Config
from PIL import Image, ImageOps

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", "http://localstack:4566")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "test")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "test")
BUCKET_ORIGINAIS = os.environ.get("S3_BUCKET_ORIGINAIS", "central-arquivos-originais")
BUCKET_PROCESSADOS = os.environ.get("S3_BUCKET_PROCESSADOS", "central-arquivos-processados")
LARGURA_MAXIMA = int(os.environ.get("LARGURA_MAXIMA_MINIATURA", "300"))

S3 = boto3.client(
    "s3",
    endpoint_url=AWS_ENDPOINT_URL,
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        retries={"max_attempts": 3, "mode": "standard"},
    ),
)


def chave_miniatura(chave: str) -> str:
    """Mesma regra usada pelo Django: ``<base>_thumb.jpg``."""
    base, _extensao = posixpath.splitext(chave)
    return f"{base}_thumb.jpg"


def _converter_para_rgb(imagem: Image.Image) -> Image.Image:
    if imagem.mode in ("RGBA", "LA") or (
        imagem.mode == "P" and "transparency" in imagem.info
    ):
        fundo = Image.new("RGB", imagem.size, (255, 255, 255))
        com_alfa = imagem.convert("RGBA")
        fundo.paste(com_alfa, mask=com_alfa.getchannel("A"))
        return fundo
    return imagem.convert("RGB")


def gerar_miniatura(dados: bytes) -> tuple[bytes, tuple[int, int], tuple[int, int]]:
    """Recebe o binário original e devolve ``(jpeg, dimensões_originais, dimensões_finais)``."""
    with Image.open(BytesIO(dados)) as imagem_original:
        imagem_original.load()
        dimensoes_originais = imagem_original.size

        # Corrige a orientação de fotos com metadados EXIF antes de redimensionar.
        imagem = ImageOps.exif_transpose(imagem_original)
        imagem = _converter_para_rgb(imagem)

        if imagem.width > LARGURA_MAXIMA:
            nova_altura = max(1, round(imagem.height * LARGURA_MAXIMA / imagem.width))
            imagem = imagem.resize(
                (LARGURA_MAXIMA, nova_altura),
                Image.Resampling.LANCZOS,
            )

        dimensoes_finais = imagem.size
        buffer = BytesIO()
        imagem.save(
            buffer,
            format="JPEG",
            quality=85,
            optimize=True,
            progressive=True,
        )
        return buffer.getvalue(), dimensoes_originais, dimensoes_finais


def handler(event, context):
    """Processa cada registro S3 recebido automaticamente pelo LocalStack."""
    logger.info("Evento recebido: %s", json.dumps(event, ensure_ascii=True))
    resultados = []

    for registro in event.get("Records", []):
        chave = ""
        try:
            bucket = registro["s3"]["bucket"]["name"]
            chave = unquote_plus(registro["s3"]["object"]["key"])

            if bucket != BUCKET_ORIGINAIS:
                logger.info("Ignorando bucket não monitorado: %s", bucket)
                continue
            if not chave.startswith("usuarios/"):
                logger.info("Ignorando objeto fora do prefixo usuarios/: %s", chave)
                continue

            resposta = S3.get_object(Bucket=bucket, Key=chave)
            dados = resposta["Body"].read()

            miniatura, dimensoes_originais, dimensoes_finais = gerar_miniatura(dados)
            destino = chave_miniatura(chave)

            S3.put_object(
                Bucket=BUCKET_PROCESSADOS,
                Key=destino,
                Body=miniatura,
                ContentType="image/jpeg",
                CacheControl="private, max-age=0",
                Metadata={"chave-original": chave},
            )

            logger.info(
                "Miniatura gerada: %s -> %s (%sx%s -> %sx%s, %s bytes)",
                chave,
                destino,
                dimensoes_originais[0],
                dimensoes_originais[1],
                dimensoes_finais[0],
                dimensoes_finais[1],
                len(miniatura),
            )
            resultados.append(
                {
                    "original": chave,
                    "miniatura": destino,
                    "dimensoes_originais": dimensoes_originais,
                    "dimensoes_miniatura": dimensoes_finais,
                }
            )
        except Exception as erro:
            # Uma imagem inválida não deve impedir o processamento das demais.
            logger.exception("Falha ao processar registro S3")
            resultados.append({"erro": str(erro), "chave": chave})

    return {"processados": resultados}
