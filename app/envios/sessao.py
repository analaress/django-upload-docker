"""Sessão autenticada baseada em um usuário do DynamoDB.

O Django continua usando o armazenamento padrão de sessões (tabela
``django_session`` no PostgreSQL). O que fica na sessão é apenas o
identificador da conta; nome, e-mail e hash nunca são copiados para o cookie.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CHAVE_USUARIO_ID = "usuario_id"
CHAVE_USUARIO_EMAIL = "usuario_email"
DURACAO_SESSAO_SEGUNDOS = 8 * 60 * 60


@dataclass(frozen=True)
class UsuarioSessao:
    """Objeto leve exposto aos templates e às views."""

    id: str
    nome: str
    email: str
    data_cadastro: str = ""

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_username(self) -> str:
        return self.email


def iniciar_sessao(request, usuario: dict[str, Any]) -> None:
    """Cria uma nova sessão autenticada (rotaciona o identificador)."""
    request.session.cycle_key()
    request.session[CHAVE_USUARIO_ID] = usuario["user_id"]
    request.session[CHAVE_USUARIO_EMAIL] = usuario["email"]
    request.session.set_expiry(DURACAO_SESSAO_SEGUNDOS)


def encerrar_sessao(request) -> None:
    request.session.flush()
