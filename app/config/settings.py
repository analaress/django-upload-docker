import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("SECRET_KEY", "chave-insegura-apenas-para-desenvolvimento")
DEBUG = os.getenv("DEBUG", "0") == "1"


def ler_lista_ambiente(nome, padrao):
    configuracao = os.getenv(nome, padrao)
    return [valor.strip() for valor in configuracao.split(",") if valor.strip()]


ALLOWED_HOSTS = ler_lista_ambiente(
    "HOSTS_PERMITIDOS",
    "localhost,127.0.0.1",
)
CSRF_TRUSTED_ORIGINS = ler_lista_ambiente(
    "ORIGENS_CSRF_PERMITIDAS",
    "http://localhost:8090,http://127.0.0.1:8090",
)
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "envios",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "envios.middleware.UsuarioDynamoDBMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "aplicacao"),
        "USER": os.getenv("POSTGRES_USER", "aplicacao"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "senha-desenvolvimento"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Sessões
# ---------------------------------------------------------------------------
# A identidade/credencial é verificada no DynamoDB. A sessão em si continua
# sendo a sessão padrão do Django, persistida na tabela django_session do
# PostgreSQL.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 8 * 60 * 60
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
DATA_UPLOAD_MAX_NUMBER_FILES = 20

# ---------------------------------------------------------------------------
# AWS / LocalStack
# ---------------------------------------------------------------------------
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "http://localstack:4566")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "test")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
S3_BUCKET_ORIGINAIS = os.getenv("S3_BUCKET_ORIGINAIS", "central-arquivos-originais")
S3_BUCKET_PROCESSADOS = os.getenv("S3_BUCKET_PROCESSADOS", "central-arquivos-processados")
DYNAMODB_TABLE_USUARIOS = os.getenv("DYNAMODB_TABLE_USUARIOS", "usuarios")
DYNAMODB_INDICE_EMAIL = os.getenv("DYNAMODB_INDICE_EMAIL", "email-index")

# ---------------------------------------------------------------------------
# Limites de upload
# ---------------------------------------------------------------------------
LIMITE_TAMANHO_IMAGEM_MB = int(os.getenv("LIMITE_TAMANHO_IMAGEM_MB", "10"))
LIMITE_ARQUIVOS_POR_ENVIO = int(os.getenv("LIMITE_ARQUIVOS_POR_ENVIO", "5"))

# ---------------------------------------------------------------------------
# Logs (stdout, capturados por `docker compose logs`)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "padrao": {
            "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "padrao",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
}
