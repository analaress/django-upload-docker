from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("envios", "0001_inicial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="arquivoenviado",
            name="arquivo",
        ),
        migrations.AddField(
            model_name="arquivoenviado",
            name="proprietario_id",
            field=models.CharField(
                db_index=True,
                default="legado",
                help_text="user_id da conta no DynamoDB",
                max_length=64,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="arquivoenviado",
            name="proprietario_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="arquivoenviado",
            name="chave_s3",
            field=models.CharField(
                blank=True,
                help_text="Chave do objeto no bucket de originais",
                max_length=512,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="arquivoenviado",
            name="content_type",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
