#!/usr/bin/env python3
"""Exporta e importa os dados do LocalStack para um diretório local.

O LocalStack Community não persiste recursos nativamente. O projeto usa a
imagem ``gresau/localstack-persist`` para manter S3 e DynamoDB entre reinícios,
mas este utilitário também serve para:

- preservar as contas e imagens existentes durante a troca de imagem;
- criar um backup manual antes de um ``docker compose down -v``;
- restaurar o backup automaticamente no primeiro provisionamento.

Formato do backup::

    /backup/
      manifest.json
      s3/<bucket>/<chave-do-objeto>
      s3/<bucket>/objetos.json
      dynamodb/<tabela>.json

O arquivo ``objetos.json`` guarda apenas metadados (Content-Type e Metadata).
O conteúdo binário fica no caminho equivalente à chave S3. Os itens do
DynamoDB são gravados no formato de baixo nível aceito por ``put_item``.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localstack:4566")
REGION = os.getenv("AWS_REGION", "us-east-1")
ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "test")
SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
BUCKET_ORIGINAIS = os.getenv("S3_BUCKET_ORIGINAIS", "central-arquivos-originais")
BUCKET_PROCESSADOS = os.getenv("S3_BUCKET_PROCESSADOS", "central-arquivos-processados")
TABELA_USUARIOS = os.getenv("DYNAMODB_TABLE_USUARIOS", "usuarios")
BACKUP_DIR = Path(os.getenv("BACKUP_LOCALSTACK_DIR", "/backup"))


def clientes():
    parametros = {
        "endpoint_url": ENDPOINT,
        "region_name": REGION,
        "aws_access_key_id": ACCESS_KEY,
        "aws_secret_access_key": SECRET_KEY,
    }
    return boto3.client("s3", **parametros), boto3.client("dynamodb", **parametros)


def _bucket_existe(s3, nome: str) -> bool:
    try:
        s3.head_bucket(Bucket=nome)
        return True
    except ClientError:
        return False


def _tem_objetos(s3, nome: str) -> bool:
    if not _bucket_existe(s3, nome):
        return False
    resposta = s3.list_objects_v2(Bucket=nome, MaxKeys=1)
    return bool(resposta.get("Contents"))


def _tabela_tem_itens(dynamodb, nome: str) -> bool:
    try:
        resposta = dynamodb.scan(TableName=nome, Limit=1)
        return bool(resposta.get("Items"))
    except ClientError:
        return False


def _caminho_do_objeto(base: Path, chave: str) -> Path:
    """Evita que uma chave S3 estranha escape do diretório do backup."""
    destino = (base / chave).resolve()
    raiz = base.resolve()
    if raiz != destino and raiz not in destino.parents:
        raise ValueError(f"chave S3 inválida para backup: {chave!r}")
    return destino


def exportar(destino: Path = BACKUP_DIR) -> None:
    s3, dynamodb = clientes()
    destino.mkdir(parents=True, exist_ok=True)

    manifesto = {
        "versao": 1,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "buckets": [BUCKET_ORIGINAIS, BUCKET_PROCESSADOS],
        "tabela": TABELA_USUARIOS,
    }
    (destino / "manifest.json").write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    for bucket in manifesto["buckets"]:
        pasta = destino / "s3" / bucket
        pasta.mkdir(parents=True, exist_ok=True)
        objetos: list[dict] = []
        if _bucket_existe(s3, bucket):
            paginador = s3.get_paginator("list_objects_v2")
            for pagina in paginador.paginate(Bucket=bucket):
                for objeto in pagina.get("Contents", []):
                    chave = objeto["Key"]
                    resposta = s3.get_object(Bucket=bucket, Key=chave)
                    caminho = _caminho_do_objeto(pasta, chave)
                    caminho.parent.mkdir(parents=True, exist_ok=True)
                    caminho.write_bytes(resposta["Body"].read())
                    objetos.append(
                        {
                            "key": chave,
                            "content_type": resposta.get("ContentType"),
                            "metadata": resposta.get("Metadata") or {},
                        }
                    )
        (pasta / "objetos.json").write_text(
            json.dumps(objetos, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[backup] {bucket}: {len(objetos)} objeto(s)")

    pasta_tabela = destino / "dynamodb"
    pasta_tabela.mkdir(parents=True, exist_ok=True)
    itens: list[dict] = []
    try:
        paginador = dynamodb.get_paginator("scan")
        for pagina in paginador.paginate(TableName=TABELA_USUARIOS):
            itens.extend(pagina.get("Items", []))
    except ClientError as erro:
        print(f"[backup] tabela {TABELA_USUARIOS} indisponível: {erro}")
    (pasta_tabela / f"{TABELA_USUARIOS}.json").write_text(
        json.dumps(itens, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[backup] {TABELA_USUARIOS}: {len(itens)} item(ns)")


def importar(origem: Path = BACKUP_DIR, *, somente_se_vazio: bool = False) -> None:
    manifesto_path = origem / "manifest.json"
    if not manifesto_path.exists():
        print(f"[restauração] nenhum backup em {origem}; nada a fazer.")
        return

    manifesto = json.loads(manifesto_path.read_text(encoding="utf-8"))
    s3, dynamodb = clientes()

    for bucket in manifesto.get("buckets", []):
        pasta = origem / "s3" / bucket
        arquivo_objetos = pasta / "objetos.json"
        if not arquivo_objetos.exists():
            continue
        if somente_se_vazio and _tem_objetos(s3, bucket):
            print(f"[restauração] {bucket} já tem objetos; ignorando.")
            continue
        if not _bucket_existe(s3, bucket):
            s3.create_bucket(Bucket=bucket)
        objetos = json.loads(arquivo_objetos.read_text(encoding="utf-8"))
        restaurados = 0
        for objeto in objetos:
            caminho = _caminho_do_objeto(pasta, objeto["key"])
            if not caminho.exists():
                print(f"[restauração] arquivo ausente no backup: {caminho}")
                continue
            extras = {}
            if objeto.get("content_type"):
                extras["ContentType"] = objeto["content_type"]
            if objeto.get("metadata"):
                extras["Metadata"] = objeto["metadata"]
            s3.put_object(
                Bucket=bucket,
                Key=objeto["key"],
                Body=caminho.read_bytes(),
                **extras,
            )
            restaurados += 1
        print(f"[restauração] {bucket}: {restaurados} objeto(s)")

    tabela = manifesto.get("tabela", TABELA_USUARIOS)
    arquivo_tabela = origem / "dynamodb" / f"{tabela}.json"
    if not arquivo_tabela.exists():
        return
    if somente_se_vazio and _tabela_tem_itens(dynamodb, tabela):
        print(f"[restauração] {tabela} já tem itens; ignorando.")
        return

    itens = json.loads(arquivo_tabela.read_text(encoding="utf-8"))
    for item in itens:
        dynamodb.put_item(TableName=tabela, Item=item)
    print(f"[restauração] {tabela}: {len(itens)} item(ns)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modo", choices=("exportar", "importar"))
    parser.add_argument("--dir", type=Path, default=BACKUP_DIR)
    parser.add_argument(
        "--somente-se-vazio",
        action="store_true",
        help="não sobrescreve buckets/tabela que já tenham dados",
    )
    args = parser.parse_args()

    if args.modo == "exportar":
        exportar(args.dir)
    else:
        importar(args.dir, somente_se_vazio=args.somente_se_vazio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
