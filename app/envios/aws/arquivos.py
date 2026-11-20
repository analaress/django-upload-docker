"""Operações de armazenamento das imagens no Amazon S3 (LocalStack).

Convenção de chaves:

- originais: ``usuarios/<user_id>/<uuid>.<ext>``
- miniaturas: ``usuarios/<user_id>/<uuid>_thumb.jpg``

A aplicação sempre deriva o proprietário a partir da sessão autenticada e
verifica se a chave começa com ``usuarios/<user_id>/`` antes de listar ou
entregar qualquer objeto. O bucket de processados nunca recebe gatilho de
evento, evitando recursão da Lambda.
"""

from __future__ import annotations

import logging
import posixpath
import uuid
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

from .clientes import cliente_s3

logger = logging.getLogger(__name__)


class ErroS3(Exception):
    """Falha genérica de comunicação/operação com o S3."""


class ObjetoNaoEncontrado(ErroS3):
    """O objeto solicitado não existe no bucket."""


def chave_do_usuario(usuario_id: str) -> str:
    return f"usuarios/{usuario_id}/"


def chave_miniatura(chave: str) -> str:
    """Deriva a chave da miniatura a partir da chave do original."""
    base, _extensao = posixpath.splitext(chave)
    return f"{base}_thumb.jpg"


def chave_pertence_ao_usuario(chave: str, usuario_id: str) -> bool:
    if not chave or "\x00" in chave or ".." in chave.split("/"):
        return False
    return chave.startswith(chave_do_usuario(usuario_id))


def montar_chave(usuario_id: str, extensao: str) -> str:
    return f"{chave_do_usuario(usuario_id)}{uuid.uuid4().hex}{extensao}"


def enviar_imagem(
    usuario_id: str,
    conteudo: bytes,
    content_type: str,
    extensao: str,
) -> str:
    """Envia o binário da imagem para o bucket de originais e devolve a chave."""
    chave = montar_chave(usuario_id, extensao)
    try:
        cliente_s3().put_object(
            Bucket=settings.S3_BUCKET_ORIGINAIS,
            Key=chave,
            Body=conteudo,
            ContentType=content_type,
            CacheControl="private, max-age=0",
        )
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Falha ao enviar imagem para o S3")
        raise ErroS3("Não foi possível armazenar a imagem no S3.") from exc
    return chave


def listar_imagens_do_usuario(usuario_id: str) -> list[dict[str, Any]]:
    """Lista diretamente no bucket de originais os objetos do usuário."""
    paginador = cliente_s3().get_paginator("list_objects_v2")
    prefixo = chave_do_usuario(usuario_id)
    imagens: list[dict[str, Any]] = []

    try:
        for pagina in paginador.paginate(
            Bucket=settings.S3_BUCKET_ORIGINAIS, Prefix=prefixo
        ):
            for objeto in pagina.get("Contents", []):
                chave = objeto["Key"]
                if chave.endswith("/"):
                    continue
                imagens.append(
                    {
                        "chave": chave,
                        "tamanho": objeto.get("Size", 0),
                        "modificado_em": objeto.get("LastModified"),
                        "etag": (objeto.get("ETag") or "").strip('"'),
                    }
                )
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Falha ao listar imagens no S3")
        raise ErroS3("Não foi possível listar as imagens no S3.") from exc

    imagens.sort(
        key=lambda item: item["modificado_em"] or 0,
        reverse=True,
    )
    return imagens


def listar_chaves_processadas(usuario_id: str) -> set[str]:
    """Conjunto de chaves já existentes no bucket de processados."""
    paginador = cliente_s3().get_paginator("list_objects_v2")
    prefixo = chave_do_usuario(usuario_id)
    chaves: set[str] = set()

    try:
        for pagina in paginador.paginate(
            Bucket=settings.S3_BUCKET_PROCESSADOS, Prefix=prefixo
        ):
            for objeto in pagina.get("Contents", []):
                chaves.add(objeto["Key"])
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Falha ao listar miniaturas no S3")
        raise ErroS3("Não foi possível consultar as miniaturas no S3.") from exc

    return chaves


def obter_objeto(bucket: str, chave: str) -> dict[str, Any]:
    """Baixa o objeto do S3. Devolve a resposta bruta do boto3."""
    try:
        return cliente_s3().get_object(Bucket=bucket, Key=chave)
    except ClientError as exc:
        codigo = exc.response.get("Error", {}).get("Code", "")
        if codigo in {"NoSuchKey", "404", "NotFound"}:
            raise ObjetoNaoEncontrado("Arquivo não encontrado no S3.") from exc
        logger.exception("Falha ao baixar objeto do S3")
        raise ErroS3("Não foi possível recuperar o arquivo do S3.") from exc
    except BotoCoreError as exc:
        logger.exception("Falha de conexão com o S3")
        raise ErroS3("Não foi possível conectar ao S3.") from exc


def objeto_existe(bucket: str, chave: str) -> bool:
    """Verifica se o objeto existe sem baixar o conteúdo.

    Usado pelo endpoint de status consultado pelo navegador enquanto a Lambda
    gera a miniatura. Um ``404`` significa "ainda não existe", não um erro.
    """
    try:
        cliente_s3().head_object(Bucket=bucket, Key=chave)
        return True
    except ClientError as exc:
        codigo = exc.response.get("Error", {}).get("Code", "")
        if codigo in {"NoSuchKey", "404", "NotFound"}:
            return False
        logger.exception("Falha ao verificar objeto no S3")
        raise ErroS3("Não foi possível verificar o arquivo no S3.") from exc
    except BotoCoreError as exc:
        logger.exception("Falha de conexão com o S3")
        raise ErroS3("Não foi possível conectar ao S3.") from exc


def nome_do_arquivo(chave: str) -> str:
    return posixpath.basename(chave) or "imagem"
