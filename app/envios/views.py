import uuid

from django.http import FileResponse, Http404
from django.contrib import messages
from django.shortcuts import redirect, render
from .forms import ArquivoEnviadoForm
from .models import ArquivoEnviado
from .aws.s3 import enviar_arquivo as enviar_arquivo_s3, obter_arquivo
from .aws.dynamodb import autenticar_usuario, criar_usuario
from .auth import login_obrigatorio, usuario_atual
from .forms_auth import FormularioCadastro, FormularioLogin


@login_obrigatorio
def pagina_inicial(request):
    arquivos = ArquivoEnviado.objects.filter(
        proprietario_id=request.usuario["user_id"]
    )
    return render(request, "envios/pagina_inicial.html", {"arquivos": arquivos})


@login_obrigatorio
def enviar_arquivo(request):
    if request.method == "POST":
        formulario = ArquivoEnviadoForm(request.POST, request.FILES)
        if formulario.is_valid():
            arquivo = formulario.cleaned_data["arquivo"]
            chave = f"arquivos/{uuid.uuid4()}-{arquivo.name}"
            enviar_arquivo_s3(
                chave,
                arquivo,
                content_type=arquivo.content_type or "application/octet-stream",
            )
            ArquivoEnviado.objects.create(
                nome_original=arquivo.name,
                tamanho_em_bytes=arquivo.size,
                chave_s3=chave,
                proprietario_id=request.usuario["user_id"],
            )
            messages.success(request, "Arquivo enviado com sucesso.")
            return redirect("pagina_inicial")
    else:
        formulario = ArquivoEnviadoForm()
    return render(request, "envios/enviar_arquivo.html", {"formulario": formulario})


@login_obrigatorio
def baixar_arquivo(request, arquivo_id: int):
    registro = ArquivoEnviado.objects.filter(
        id=arquivo_id,
        proprietario_id=request.usuario["user_id"],
    ).first()
    if not registro or not registro.chave_s3:
        raise Http404("Arquivo não encontrado.")
    try:
        objeto = obter_arquivo(registro.chave_s3)
    except Exception as exc:
        raise Http404("Arquivo não encontrado.") from exc
    return FileResponse(
        objeto["Body"],
        as_attachment=True,
        filename=registro.nome_original,
        content_type=objeto.get("ContentType", "application/octet-stream"),
    )


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
