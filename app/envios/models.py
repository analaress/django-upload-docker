"""Metadados internos das imagens armazenadas no S3.

O conteúdo binário nunca é gravado neste modelo: ele fica nos buckets do
LocalStack. O PostgreSQL guarda apenas o histórico/auditoria dos envios e a
referência à chave S3, que é a fonte de verdade da listagem.
"""

from django.db import models


class ArquivoEnviado(models.Model):
    proprietario_id = models.CharField(
        max_length=64,
        db_index=True,
        help_text="user_id da conta no DynamoDB",
    )
    proprietario_email = models.EmailField(blank=True, default="")
    chave_s3 = models.CharField(
        max_length=512,
        unique=True,
        null=True,
        blank=True,
        help_text="Chave do objeto no bucket de originais",
    )
    nome_original = models.CharField(max_length=255)
    tamanho_em_bytes = models.PositiveBigIntegerField()
    content_type = models.CharField(max_length=100, blank=True, default="")
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enviado_em"]
        verbose_name = "arquivo enviado"
        verbose_name_plural = "arquivos enviados"

    def __str__(self):
        return self.nome_original
