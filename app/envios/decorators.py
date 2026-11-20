"""Decorador de acesso às páginas privadas."""

from functools import wraps
from urllib.parse import quote

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def login_obrigatorio(view):
    @wraps(view)
    def _view_protegida(request, *args, **kwargs):
        if getattr(request, "usuario", None) is None:
            messages.warning(request, "Faça login para acessar a Central de Arquivos.")
            url = reverse("login")
            destino = request.get_full_path()
            if url_has_allowed_host_and_scheme(
                destino,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                url = f"{url}?next={quote(destino)}"
            return redirect(url)
        return view(request, *args, **kwargs)

    return _view_protegida
