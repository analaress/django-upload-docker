from django.contrib import admin

from .models import ArquivoEnviado


@admin.register(ArquivoEnviado)
class ArquivoEnviadoAdmin(admin.ModelAdmin):
    """Histórico/auditoria dos envios; o conteúdo vive no S3."""

    list_display = (
        "nome_original",
        "proprietario_email",
        "tamanho_em_bytes",
        "content_type",
        "enviado_em",
    )
    list_filter = ("content_type", "enviado_em")
    search_fields = ("nome_original", "proprietario_email", "chave_s3", "proprietario_id")
    readonly_fields = (
        "proprietario_id",
        "proprietario_email",
        "chave_s3",
        "nome_original",
        "tamanho_em_bytes",
        "content_type",
        "enviado_em",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
