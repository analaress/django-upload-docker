from functools import wraps

from django.shortcuts import redirect


def usuario_atual(request):
    return request.session.get("usuario")


def login_obrigatorio(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not usuario_atual(request):
            return redirect("login")
        request.usuario = usuario_atual(request)
        return view(request, *args, **kwargs)

    return wrapper
