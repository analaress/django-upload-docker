FROM python:3.12-slim
WORKDIR /provisionador
RUN apt-get update && apt-get install -y --no-install-recommends zip && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir boto3 pillow
COPY lambda/processar_imagem.py /provisionador/processar_imagem.py
COPY infra/localstack/init_aws.py /provisionador/init_aws.py
RUN mkdir /provisionador/pacote && \
    cp /provisionador/processar_imagem.py /provisionador/pacote/ && \
    pip install --no-cache-dir --target /provisionador/pacote boto3 pillow && \
    cd /provisionador/pacote && zip -qr /provisionador/lambda.zip .
CMD ["python", "/provisionador/init_aws.py"]
