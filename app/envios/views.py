from django.contrib import messages
from django.shortcuts import redirect, render
from .forms import ArquivoEnviadoForm
from .models import ArquivoEnviado


def pagina_inicial(request):
    arquivos = ArquivoEnviado.objects.all()
    return render(request, "envios/pagina_inicial.html", {"arquivos": arquivos})


def enviar_arquivo(request):
    if request.method == "POST":
        formulario = ArquivoEnviadoForm(request.POST, request.FILES)
        if formulario.is_valid():
            formulario.save()
            messages.success(request, "Arquivo enviado com sucesso.")
            return redirect("pagina_inicial")
    else:
        formulario = ArquivoEnviadoForm()
    return render(request, "envios/enviar_arquivo.html", {"formulario": formulario})
