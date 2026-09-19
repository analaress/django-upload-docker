from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(name="ArquivoEnviado", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("arquivo", models.FileField(upload_to="arquivos/%Y/%m/%d/")), ("nome_original", models.CharField(max_length=255)), ("tamanho_em_bytes", models.PositiveBigIntegerField()), ("enviado_em", models.DateTimeField(auto_now_add=True))], options={"verbose_name": "arquivo enviado", "verbose_name_plural": "arquivos enviados", "ordering": ["-enviado_em"]})]
