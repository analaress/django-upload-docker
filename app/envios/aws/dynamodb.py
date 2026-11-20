"""Acesso à tabela de usuários no DynamoDB."""

from __future__ import annotations

from uuid import uuid4

import boto3
from botocore.config import Config
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password


def cliente_dynamodb():
    return boto3.resource(
        "dynamodb",
        endpoint_url=settings.AWS_ENDPOINT_URL,
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(retries={"max_attempts": 3, "mode": "standard"}),
    )


def tabela_usuarios():
    return cliente_dynamodb().Table(settings.DYNAMODB_TABLE_USUARIOS)


def criar_usuario(*, nome: str, email: str, senha: str) -> dict:
    """Cria um usuário com senha armazenada somente como hash."""
    if buscar_usuario_por_email(email):
        raise ValueError("Este e-mail já está cadastrado.")
    usuario = {
        "user_id": str(uuid4()),
        "nome": nome,
        "email": email.strip().lower(),
        "senha_hash": make_password(senha),
    }
    tabela_usuarios().put_item(
        Item=usuario,
        ConditionExpression="attribute_not_exists(email)",
    )
    return usuario


def buscar_usuario_por_email(email: str) -> dict | None:
    resposta = tabela_usuarios().query(
        IndexName="email-index",
        KeyConditionExpression="email = :email",
        ExpressionAttributeValues={":email": email.strip().lower()},
        Limit=1,
    )
    itens = resposta.get("Items", [])
    return itens[0] if itens else None


def autenticar_usuario(*, email: str, senha: str) -> dict | None:
    usuario = buscar_usuario_por_email(email)
    if not usuario or not check_password(senha, usuario["senha_hash"]):
        return None
    return usuario
