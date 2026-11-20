from django.urls import path

from . import views

urlpatterns = [
    path("", views.pagina_inicial, name="pagina_inicial"),
    path("enviar/", views.enviar_arquivo, name="enviar_arquivo"),
    path("cadastro/", views.cadastro, name="cadastro"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    # Rotas mais específicas primeiro: ``<path:chave>`` é guloso e poderia
    # capturar ``.../miniatura`` como parte da chave.
    path(
        "arquivos/<path:chave>/original/",
        views.baixar_original,
        name="baixar_original",
    ),
    path(
        "arquivos/<path:chave>/miniatura/baixar/",
        views.baixar_processado,
        name="baixar_processado",
    ),
    path(
        "arquivos/<path:chave>/status/",
        views.status_processado,
        name="status_processado",
    ),
    path(
        "arquivos/<path:chave>/miniatura/",
        views.ver_processado,
        name="ver_processado",
    ),
]
