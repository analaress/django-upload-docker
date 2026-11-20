"""Repositório de contas de usuário no DynamoDB (LocalStack).

A tabela ``usuarios`` possui:

- chave primária ``user_id`` (string, UUID);
- índice secundário global ``email-index`` (partição por ``email``);
- um item de reserva por e-mail, cuja chave é ``email#<email normalizado>``.

O item de reserva não possui o atributo ``email`` e, por isso, não aparece no
índice global. Ele existe para garantir unicidade de e-mail de forma atômica:
a gravação do usuário e a reserva do e-mail acontecem na mesma transação
(``TransactWriteItems``), com ``attribute_not_exists`` nas duas condições.
Assim, duas requisições simultâneas com o mesmo e-mail não criam contas
duplicadas.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password

from .clientes import cliente_dynamodb

logger = logging.getLogger(__name__)

PREFIXO_RESERVA_EMAIL = "email#"
TIPO_USUARIO = "usuario"
TIPO_RESERVA = "reserva_email"

_serializador = TypeSerializer()
_desserializador = TypeDeserializer()


class ErroDynamoDB(Exception):
    """Falha genérica de comunicação/operação com o DynamoDB."""


class EmailJaCadastrado(ErroDynamoDB):
    """O e-mail informado já pertence a outra conta."""


def normalizar_email(email: str) -> str:
    return (email or "").strip().lower()


def _serializar(item: dict[str, Any]) -> dict[str, Any]:
    return {chave: _serializador.serialize(valor) for chave, valor in item.items()}


def _desserializar(item: dict[str, Any]) -> dict[str, Any]:
    return {chave: _desserializador.deserialize(valor) for chave, valor in item.items()}


def _e_item_de_usuario(item: dict[str, Any] | None) -> bool:
    return bool(item) and item.get("tipo") == TIPO_USUARIO


def sanitizar(item: dict[str, Any]) -> dict[str, Any]:
    """Remove o hash da senha antes de devolver o usuário para a aplicação."""
    return {
        "user_id": item["user_id"],
        "nome": item.get("nome", ""),
        "email": item.get("email", ""),
        "data_cadastro": item.get("data_cadastro", ""),
    }


def criar_usuario(nome: str, email: str, senha: str) -> dict[str, Any]:
    """Cria a conta no DynamoDB com senha em hash e e-mail único."""
    email = normalizar_email(email)
    usuario_id = str(uuid.uuid4())
    agora = datetime.now(timezone.utc).isoformat()

    item_usuario = {
        "user_id": usuario_id,
        "tipo": TIPO_USUARIO,
        "nome": nome.strip(),
        "email": email,
        "senha_hash": make_password(senha),
        "data_cadastro": agora,
    }
    item_reserva = {
        "user_id": f"{PREFIXO_RESERVA_EMAIL}{email}",
        "tipo": TIPO_RESERVA,
        "email_normalizado": email,
        "criado_em": agora,
    }

    try:
        cliente_dynamodb().transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": settings.DYNAMODB_TABLE_USUARIOS,
                        "Item": _serializar(item_usuario),
                        "ConditionExpression": "attribute_not_exists(user_id)",
                    }
                },
                {
                    "Put": {
                        "TableName": settings.DYNAMODB_TABLE_USUARIOS,
                        "Item": _serializar(item_reserva),
                        "ConditionExpression": "attribute_not_exists(user_id)",
                    }
                },
            ]
        )
    except ClientError as exc:
        codigo = exc.response.get("Error", {}).get("Code", "")
        if codigo == "TransactionCanceledException":
            motivos = exc.response.get("CancellationReasons", [])
            if any(motivo.get("Code") == "ConditionalCheckFailed" for motivo in motivos):
                raise EmailJaCadastrado("Este e-mail já está cadastrado.") from exc
        logger.exception("Falha ao gravar usuário no DynamoDB")
        raise ErroDynamoDB("Não foi possível gravar a conta no DynamoDB.") from exc
    except BotoCoreError as exc:
        logger.exception("Falha de conexão com o DynamoDB")
        raise ErroDynamoDB("Não foi possível conectar ao DynamoDB.") from exc

    return sanitizar(item_usuario)


def buscar_usuario_por_email(email: str) -> dict[str, Any] | None:
    """Consulta o índice ``email-index`` e devolve o item completo do usuário."""
    email = normalizar_email(email)
    try:
        resposta = cliente_dynamodb().query(
            TableName=settings.DYNAMODB_TABLE_USUARIOS,
            IndexName=settings.DYNAMODB_INDICE_EMAIL,
            KeyConditionExpression="email = :email",
            ExpressionAttributeValues={":email": {"S": email}},
        )
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Falha ao consultar usuário por e-mail no DynamoDB")
        raise ErroDynamoDB("Não foi possível consultar a conta no DynamoDB.") from exc

    for item_bruto in resposta.get("Items", []):
        item = _desserializar(item_bruto)
        if _e_item_de_usuario(item):
            return item
    return None


def buscar_usuario_por_id(usuario_id: str) -> dict[str, Any] | None:
    """Recupera a conta pela chave primária (usada a cada requisição)."""
    try:
        resposta = cliente_dynamodb().get_item(
            TableName=settings.DYNAMODB_TABLE_USUARIOS,
            Key={"user_id": {"S": usuario_id}},
        )
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Falha ao consultar usuário por id no DynamoDB")
        raise ErroDynamoDB("Não foi possível consultar a conta no DynamoDB.") from exc

    item_bruto = resposta.get("Item")
    if not item_bruto:
        return None
    item = _desserializar(item_bruto)
    return item if _e_item_de_usuario(item) else None


def autenticar(email: str, senha: str) -> dict[str, Any] | None:
    """Valida e-mail/senha consultando o DynamoDB e o hash armazenado."""
    item = buscar_usuario_por_email(email)
    if item is None:
        return None

    senha_hash = item.get("senha_hash", "")
    if not senha_hash or not check_password(senha, senha_hash):
        return None

    return sanitizar(item)
