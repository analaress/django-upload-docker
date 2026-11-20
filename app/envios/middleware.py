"""Carrega o usuário autenticado a partir do DynamoDB em cada requisição."""

from __future__ import annotations

import logging

from .aws.usuarios import ErroDynamoDB, buscar_usuario_por_id
from .sessao import CHAVE_USUARIO_ID, UsuarioSessao

logger = logging.getLogger(__name__)


class UsuarioDynamoDBMiddleware:
    """Mantém ``request.usuario`` sincronizado com a conta no DynamoDB.

    A sessão guarda somente o ``user_id``. Se a conta for removida do
    DynamoDB, a sessão é descartada. Em caso de indisponibilidade do serviço,
    a sessão é preservada para que o usuário não seja deslogado por uma falha
    temporária; a view mostra uma mensagem de erro.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.usuario = None
        request.falha_dynamodb = False

        usuario_id = request.session.get(CHAVE_USUARIO_ID)
        if usuario_id:
            try:
                item = buscar_usuario_por_id(usuario_id)
            except ErroDynamoDB:
                logger.exception("Não foi possível carregar o usuário da sessão")
                request.falha_dynamodb = True
            else:
                if item is None:
                    request.session.flush()
                else:
                    request.usuario = UsuarioSessao(
                        id=item["user_id"],
                        nome=item.get("nome", ""),
                        email=item.get("email", ""),
                        data_cadastro=item.get("data_cadastro", ""),
                    )

        return self.get_response(request)
