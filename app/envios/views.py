import uuid

from django.http import FileResponse, Http404
from django.contrib import messages
from django.shortcuts import redirect, render
from .forms import ArquivoEnviadoForm
from .models import ArquivoEnviado
from .aws.s3 import enviar_arquivo as enviar_arquivo_s3, obter_arquivo


def pagina_inicial(request):
    arquivos = ArquivoEnviado.objects.all()
    return render(request, "envios/pagina_inicial.html", {"arquivos": arquivos})


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
            )
            messages.success(request, "Arquivo enviado com sucesso.")
            return redirect("pagina_inicial")
    else:
        formulario = ArquivoEnviadoForm()
    return render(request, "envios/enviar_arquivo.html", {"formulario": formulario})


def baixar_arquivo(request, arquivo_id: int):
    registro = ArquivoEnviado.objects.filter(id=arquivo_id).first()
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
