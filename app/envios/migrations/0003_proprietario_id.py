from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("envios", "0002_arquivo_s3")]

    operations = [
        migrations.AddField(
            model_name="arquivoenviado",
            name="proprietario_id",
            field=models.CharField(blank=True, db_index=True, max_length=36, null=True),
        ),
    ]
