from django.urls import path
from . import views

urlpatterns = [
    path("", views.pagina_inicial, name="pagina_inicial"),
    path("enviar/", views.enviar_arquivo, name="enviar_arquivo"),
    path("baixar/<int:arquivo_id>/", views.baixar_arquivo, name="baixar_arquivo"),
]
