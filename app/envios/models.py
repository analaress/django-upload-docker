from django.db import models
class ArquivoEnviado(models.Model):
    arquivo = models.FileField(upload_to="arquivos/%Y/%m/%d/")
    nome_original = models.CharField(max_length=255)
    tamanho_em_bytes = models.PositiveBigIntegerField()
    enviado_em = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-enviado_em"]
        verbose_name = "arquivo enviado"
        verbose_name_plural = "arquivos enviados"
    def __str__(self):
        return self.nome_original
