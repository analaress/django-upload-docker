import io
import os
import posixpath
from urllib.parse import unquote_plus

import boto3
from PIL import Image, UnidentifiedImageError


def handler(event, context):
    endpoint = os.getenv("AWS_ENDPOINT_URL", "http://localstack:4566")
    region = os.getenv("AWS_REGION", "us-east-1")
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    )
    origem = os.getenv("S3_BUCKET_ORIGINAIS", "central-arquivos-originais")
    destino = os.getenv("S3_BUCKET_PROCESSADOS", "central-arquivos-processados")

    processados = []
    for registro in event.get("Records", []):
        bucket = registro["s3"]["bucket"]["name"]
        chave = unquote_plus(registro["s3"]["object"]["key"])
        objeto = s3.get_object(Bucket=bucket, Key=chave)
        try:
            imagem = Image.open(io.BytesIO(objeto["Body"].read())).convert("RGB")
        except UnidentifiedImageError:
            print(f"Arquivo não-imagem ignorado: s3://{bucket}/{chave}")
            processados.append({"chave": chave, "status": "ignorado"})
            continue
        imagem.thumbnail((300, 300))
        saida = io.BytesIO()
        imagem.save(saida, format="JPEG", quality=85)
        saida.seek(0)
        nome = posixpath.splitext(chave)[0] + "_miniatura.jpg"
        s3.upload_fileobj(saida, destino, nome, ExtraArgs={"ContentType": "image/jpeg"})
        processados.append({"chave": nome, "status": "processado"})

    return {"bucket_origem": origem, "processados": processados}
