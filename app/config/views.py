from django.shortcuts import render


def erro_404(request, exception):
    return render(request, "envios/erro.html", {"codigo": 404, "mensagem": "Página ou arquivo não encontrado."}, status=404)


def erro_500(request):
    return render(request, "envios/erro.html", {"codigo": 500, "mensagem": "Ocorreu um erro interno. Tente novamente."}, status=500)
