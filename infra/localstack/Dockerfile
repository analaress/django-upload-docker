# Provisionador one-shot: empacota a Lambda com Pillow e cria os recursos
# no LocalStack. A imagem é construída no host e executada uma vez.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends zip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /provisionamento

COPY infra/localstack/requirements-provisionamento.txt .
RUN pip install --no-cache-dir -r requirements-provisionamento.txt

COPY lambda/ /origem-lambda/
COPY infra/localstack/init_aws.py .

# O wheel é baixado para a plataforma x86_64 do runtime Lambda, e não para a
# arquitetura/ambiente do provisionador.
RUN mkdir -p /pacote-lambda \
    && cp /origem-lambda/processar_imagem.py /pacote-lambda/ \
    && pip install --no-cache-dir --upgrade \
        --target /pacote-lambda \
        --platform manylinux2014_x86_64 \
        --only-binary=:all: \
        --implementation cp \
        --python-version 3.12 \
        --abi cp312 \
        "pillow==10.4.0" \
    && cd /pacote-lambda \
    && zip -qr /lambda.zip . \
    && test -s /lambda.zip

CMD ["python", "init_aws.py"]
