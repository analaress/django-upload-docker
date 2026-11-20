import uuid
import posixpath
from pathlib import Path

from django.http import FileResponse, Http404
from django.contrib import messages
from django.conf import settings
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from botocore.exceptions import BotoCoreError, ClientError
from .forms import ArquivoEnviadoForm
from .models import ArquivoEnviado
from .aws.s3 import (
    enviar_arquivo as enviar_arquivo_s3,
    excluir_objeto_s3,
    obter_arquivo,
    objeto_existe_s3,
)
from .aws.dynamodb import autenticar_usuario, criar_usuario
from .auth import login_obrigatorio, usuario_atual
from .forms_auth import FormularioCadastro, FormularioLogin


@login_obrigatorio
def pagina_inicial(request):
    arquivos = ArquivoEnviado.objects.filter(
        proprietario_id=request.usuario["user_id"]
    )
    extensoes_imagem = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}
    for arquivo in arquivos:
        extensao = Path(arquivo.nome_original).suffix.lower()
        arquivo.eh_imagem = extensao in extensoes_imagem
        arquivo.eh_pdf = extensao == ".pdf"
        arquivo.extensao_exibicao = extensao.lstrip(".").upper() or "ARQ"
        if arquivo.eh_imagem:
            chave_miniatura = posixpath.splitext(arquivo.chave_s3)[0] + "_miniatura.jpg"
            arquivo.miniatura_disponivel = objeto_existe_s3(
                chave_miniatura,
                bucket=settings.S3_BUCKET_PROCESSADOS,
            )
        else:
            arquivo.miniatura_disponivel = False
    return render(request, "envios/pagina_inicial.html", {"arquivos": arquivos})


@login_obrigatorio
def visualizar_miniatura(request, arquivo_id: int):
    registro = ArquivoEnviado.objects.filter(
        id=arquivo_id,
        proprietario_id=request.usuario["user_id"],
    ).first()
    if not registro or not registro.chave_s3:
        raise Http404
    if Path(registro.nome_original).suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}:
        raise Http404
    chave = posixpath.splitext(registro.chave_s3)[0] + "_miniatura.jpg"
    try:
        objeto = obter_arquivo(chave, bucket=settings.S3_BUCKET_PROCESSADOS)
    except (BotoCoreError, ClientError):
        raise Http404
    return FileResponse(objeto["Body"], content_type="image/jpeg")


@login_obrigatorio
def enviar_arquivo(request):
    if request.method == "POST":
        formulario = ArquivoEnviadoForm(request.POST, request.FILES)
        if formulario.is_valid():
            arquivo = formulario.cleaned_data["arquivo"]
            chave = f"arquivos/{uuid.uuid4()}-{arquivo.name}"
            try:
                enviar_arquivo_s3(
                    chave,
                    arquivo,
                    content_type=arquivo.content_type or "application/octet-stream",
                )
            except (BotoCoreError, ClientError):
                messages.error(request, "Não foi possível enviar o arquivo ao armazenamento.")
                return redirect("pagina_inicial")
            ArquivoEnviado.objects.create(
                nome_original=arquivo.name,
                tamanho_em_bytes=arquivo.size,
                chave_s3=chave,
                proprietario_id=request.usuario["user_id"],
            )
            if Path(arquivo.name).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}:
                messages.success(request, "Imagem enviada com sucesso. O processamento está em andamento.")
            else:
                messages.success(request, "Arquivo enviado com sucesso.")
            return redirect("pagina_inicial")
        for erro in formulario.errors.get("arquivo", []):
            messages.error(request, str(erro))
        if not formulario.errors.get("arquivo"):
            messages.error(request, "Não foi possível enviar o arquivo.")
        return redirect("pagina_inicial")
    else:
        return redirect("pagina_inicial")


@login_obrigatorio
def baixar_arquivo(request, arquivo_id: int):
    registro = ArquivoEnviado.objects.filter(
        id=arquivo_id,
        proprietario_id=request.usuario["user_id"],
    ).first()
    if not registro or not registro.chave_s3:
        messages.error(request, "Arquivo não encontrado.")
        return redirect("pagina_inicial")
    try:
        objeto = obter_arquivo(registro.chave_s3)
    except (BotoCoreError, ClientError):
        messages.error(request, "Não foi possível baixar o arquivo agora.")
        return redirect("pagina_inicial")
    return FileResponse(
        objeto["Body"],
        as_attachment=True,
        filename=registro.nome_original,
        content_type=objeto.get("ContentType", "application/octet-stream"),
    )


@login_obrigatorio
def visualizar_arquivo(request, arquivo_id: int):
    registro = ArquivoEnviado.objects.filter(
        id=arquivo_id,
        proprietario_id=request.usuario["user_id"],
    ).first()
    if not registro or not registro.chave_s3:
        raise Http404
    if Path(registro.nome_original).suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}:
        raise Http404
    try:
        objeto = obter_arquivo(registro.chave_s3)
    except (BotoCoreError, ClientError):
        raise Http404
    return FileResponse(
        objeto["Body"],
        as_attachment=False,
        filename=registro.nome_original,
        content_type=objeto.get("ContentType", "application/octet-stream"),
    )


@login_obrigatorio
@require_POST
def excluir_arquivo(request, arquivo_id: int):
    registro = ArquivoEnviado.objects.filter(
        id=arquivo_id,
        proprietario_id=request.usuario["user_id"],
    ).first()
    if not registro or not registro.chave_s3:
        messages.error(request, "Arquivo não encontrado.")
        return redirect("pagina_inicial")

    try:
        excluir_objeto_s3(registro.chave_s3)
    except (BotoCoreError, ClientError):
        messages.error(request, "Não foi possível remover o arquivo do armazenamento.")
        return redirect("pagina_inicial")
    chave_miniatura = posixpath.splitext(registro.chave_s3)[0] + "_miniatura.jpg"
    try:
        excluir_objeto_s3(chave_miniatura, bucket=settings.S3_BUCKET_PROCESSADOS)
    except Exception:
        pass
    registro.delete()
    messages.success(request, "Arquivo removido com sucesso.")
    return redirect("pagina_inicial")


def cadastro(request):
    formulario = FormularioCadastro(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            usuario = criar_usuario(
                nome=formulario.cleaned_data["nome"],
                email=formulario.cleaned_data["email"],
                senha=formulario.cleaned_data["senha"],
            )
        except ValueError as erro:
            formulario.add_error("email", str(erro))
        else:
            request.session["usuario"] = {
                "user_id": usuario["user_id"],
                "nome": usuario["nome"],
                "email": usuario["email"],
            }
            return redirect("pagina_inicial")
    return render(request, "envios/cadastro.html", {"formulario": formulario})


def login(request):
    formulario = FormularioLogin(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        usuario = autenticar_usuario(
            email=formulario.cleaned_data["email"],
            senha=formulario.cleaned_data["senha"],
        )
        if usuario:
            request.session["usuario"] = {
                "user_id": usuario["user_id"],
                "nome": usuario["nome"],
                "email": usuario["email"],
            }
            return redirect("pagina_inicial")
        formulario.add_error(None, "E-mail ou senha inválidos.")
    return render(request, "envios/login.html", {"formulario": formulario})


def logout(request):
    request.session.flush()
    return redirect("login")
