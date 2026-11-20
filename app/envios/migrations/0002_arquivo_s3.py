from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("envios", "0001_inicial")]

    operations = [
        migrations.AddField(
            model_name="arquivoenviado",
            name="chave_s3",
            field=models.CharField(blank=True, max_length=512, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="arquivoenviado",
            name="arquivo",
            field=models.FileField(blank=True, null=True, upload_to="arquivos/%Y/%m/%d/"),
        ),
    ]
