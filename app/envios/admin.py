from django.contrib import admin
from .models import ArquivoEnviado
@admin.register(ArquivoEnviado)
class ArquivoEnviadoAdmin(admin.ModelAdmin):
    list_display = ("nome_original", "tamanho_em_bytes", "enviado_em")
