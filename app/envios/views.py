"""Views da Central de Arquivos.

Fluxos principais:

- cadastro/login/logout com contas no DynamoDB;
- upload de imagens para o bucket de originais do S3 (LocalStack);
- listagem consultando o próprio S3 e enriquecendo com metadados do PostgreSQL;
- download do original e da miniatura gerada pela Lambda.
"""

from __future__ import annotations

import logging
import posixpath

from django.conf import settings
from django.contrib import messages
from django.db import DatabaseError
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .aws.arquivos import (
    ErroS3,
    ObjetoNaoEncontrado,
    chave_miniatura,
    chave_pertence_ao_usuario,
    enviar_imagem,
    listar_chaves_processadas,
    listar_imagens_do_usuario,
    nome_do_arquivo,
    objeto_existe,
    obter_objeto,
)
from .aws.usuarios import (
    EmailJaCadastrado,
    ErroDynamoDB,
    autenticar,
    criar_usuario,
)
from .decorators import login_obrigatorio
from .forms import FormularioCadastro, FormularioLogin, FormularioUploadImagens
from .models import ArquivoEnviado
from .sessao import encerrar_sessao, iniciar_sessao
from .validacao import ImagemInvalida, validar_imagem

logger = logging.getLogger(__name__)


def _destino_seguro(request, destino: str | None) -> str:
    if destino and url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return destino
    return reverse("pagina_inicial")


def _registros_do_usuario(usuario_id: str) -> dict[str, ArquivoEnviado]:
    registros = ArquivoEnviado.objects.filter(proprietario_id=usuario_id).exclude(
        chave_s3__isnull=True
    )
    return {registro.chave_s3: registro for registro in registros}


def _nome_original(usuario_id: str, chave: str) -> str:
    registro = (
        ArquivoEnviado.objects.filter(proprietario_id=usuario_id, chave_s3=chave)
        .only("nome_original")
        .first()
    )
    return registro.nome_original if registro else nome_do_arquivo(chave)


def _entregar_arquivo(
    request,
    bucket: str,
    chave: str,
    nome: str,
    *,
    anexo: bool,
    content_type_padrao: str = "application/octet-stream",
):
    try:
        objeto = obter_objeto(bucket, chave)
    except ObjetoNaoEncontrado as exc:
        raise Http404("Arquivo não encontrado.") from exc
    except ErroS3:
        logger.exception("Falha ao recuperar %s/%s", bucket, chave)
        return HttpResponse(
            "O armazenamento de arquivos está indisponível no momento. "
            "Tente novamente em instantes.",
            status=503,
            content_type="text/plain; charset=utf-8",
        )

    resposta = FileResponse(
        objeto["Body"],
        content_type=objeto.get("ContentType") or content_type_padrao,
        as_attachment=anexo,
        filename=nome,
    )
    tamanho = objeto.get("ContentLength")
    if tamanho is not None:
        resposta["Content-Length"] = str(tamanho)
    return resposta


@login_obrigatorio
def pagina_inicial(request):
    itens: list[dict] = []
    try:
        objetos = listar_imagens_do_usuario(request.usuario.id)
        processadas = listar_chaves_processadas(request.usuario.id)
    except ErroS3:
        logger.exception("Falha ao montar a listagem de imagens")
        messages.error(
            request,
            "Não foi possível consultar o armazenamento S3. "
            "Confira se o LocalStack e os buckets estão disponíveis.",
        )
        objetos, processadas = [], set()

    registros = _registros_do_usuario(request.usuario.id)
    for objeto in objetos:
        chave = objeto["chave"]
        registro = registros.get(chave)
        itens.append(
            {
                "chave": chave,
                "nome": registro.nome_original if registro else nome_do_arquivo(chave),
                "tamanho": registro.tamanho_em_bytes if registro else objeto["tamanho"],
                "enviado_em": objeto["modificado_em"]
                or (registro.enviado_em if registro else None),
                "processada": chave_miniatura(chave) in processadas,
            }
        )

    return render(
        request,
        "envios/pagina_inicial.html",
        {
            "itens": itens,
            "formulario_upload": FormularioUploadImagens(),
            "limite_mb": settings.LIMITE_TAMANHO_IMAGEM_MB,
            "limite_arquivos": settings.LIMITE_ARQUIVOS_POR_ENVIO,
            "bucket_originais": settings.S3_BUCKET_ORIGINAIS,
            "bucket_processados": settings.S3_BUCKET_PROCESSADOS,
        },
    )


@login_obrigatorio
def enviar_arquivo(request):
    formulario = FormularioUploadImagens(request.POST or None, request.FILES or None)

    if request.method == "POST" and formulario.is_valid():
        imagens = formulario.cleaned_data["imagens"]
        enviados = 0
        erros: list[str] = []

        for imagem in imagens:
            try:
                _formato, content_type, extensao = validar_imagem(imagem)
                chave = enviar_imagem(
                    usuario_id=request.usuario.id,
                    conteudo=imagem.read(),
                    content_type=content_type,
                    extensao=extensao,
                )
            except ImagemInvalida as exc:
                erros.append(f"{imagem.name}: {exc}")
                continue
            except ErroS3:
                erros.append(f"{imagem.name}: não foi possível enviar ao S3.")
                continue

            enviados += 1
            try:
                ArquivoEnviado.objects.create(
                    proprietario_id=request.usuario.id,
                    proprietario_email=request.usuario.email,
                    chave_s3=chave,
                    nome_original=imagem.name,
                    tamanho_em_bytes=imagem.size,
                    content_type=content_type,
                )
            except DatabaseError:
                # A imagem já está no S3; a listagem usa o S3 como fonte de
                # verdade e continua funcionando sem o metadado local.
                logger.exception("Falha ao registrar metadados no PostgreSQL")

        if enviados:
            if enviados == 1:
                mensagem = (
                    "1 imagem enviada para o S3. A miniatura aparece "
                    "automaticamente assim que a Lambda termina."
                )
            else:
                mensagem = (
                    f"{enviados} imagens enviadas para o S3. As miniaturas "
                    "aparecem automaticamente assim que a Lambda termina."
                )
            messages.success(request, mensagem)
        for erro in erros:
            messages.error(request, erro)
        if not enviados and not erros:
            messages.error(request, "Nenhuma imagem foi enviada.")
        return redirect("pagina_inicial")

    return render(
        request,
        "envios/enviar_arquivo.html",
        {
            "formulario": formulario,
            "limite_mb": settings.LIMITE_TAMANHO_IMAGEM_MB,
            "limite_arquivos": settings.LIMITE_ARQUIVOS_POR_ENVIO,
        },
    )


def cadastro(request):
    if request.usuario is not None:
        return redirect("pagina_inicial")

    formulario = FormularioCadastro(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            usuario = criar_usuario(
                nome=formulario.cleaned_data["nome"],
                email=formulario.cleaned_data["email"],
                senha=formulario.cleaned_data["senha"],
            )
        except EmailJaCadastrado:
            formulario.add_error("email", "Este e-mail já está cadastrado.")
        except ErroDynamoDB:
            logger.exception("Falha ao criar conta")
            formulario.add_error(
                None,
                "Não foi possível criar a conta agora. "
                "Verifique o DynamoDB/LocalStack e tente novamente.",
            )
        else:
            iniciar_sessao(request, usuario)
            messages.success(request, f"Conta criada. Bem-vindo(a), {usuario['nome']}!")
            return redirect("pagina_inicial")

    return render(request, "envios/cadastro.html", {"formulario": formulario})


def login(request):
    if request.usuario is not None:
        return redirect("pagina_inicial")

    formulario = FormularioLogin(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            usuario = autenticar(
                email=formulario.cleaned_data["email"],
                senha=formulario.cleaned_data["senha"],
            )
        except ErroDynamoDB:
            logger.exception("Falha ao autenticar no DynamoDB")
            formulario.add_error(
                None,
                "Não foi possível consultar o DynamoDB agora. "
                "Verifique o LocalStack e tente novamente.",
            )
        else:
            if usuario is None:
                formulario.add_error(None, "E-mail ou senha inválidos.")
            else:
                iniciar_sessao(request, usuario)
                messages.success(request, f"Olá, {usuario['nome']}!")
                return redirect(_destino_seguro(request, request.POST.get("next")))

    return render(
        request,
        "envios/login.html",
        {"formulario": formulario, "next": request.GET.get("next", "")},
    )


@require_POST
def logout(request):
    encerrar_sessao(request)
    messages.info(request, "Sessão encerrada.")
    return redirect("login")


@login_obrigatorio
def baixar_original(request, chave: str):
    if not chave_pertence_ao_usuario(chave, request.usuario.id):
        raise Http404("Arquivo não encontrado.")

    return _entregar_arquivo(
        request,
        settings.S3_BUCKET_ORIGINAIS,
        chave,
        _nome_original(request.usuario.id, chave),
        anexo=True,
    )


@login_obrigatorio
def ver_processado(request, chave: str):
    if not chave_pertence_ao_usuario(chave, request.usuario.id):
        raise Http404("Arquivo não encontrado.")

    return _entregar_arquivo(
        request,
        settings.S3_BUCKET_PROCESSADOS,
        chave_miniatura(chave),
        f"{posixpath.splitext(nome_do_arquivo(chave))[0]}_miniatura.jpg",
        anexo=False,
        content_type_padrao="image/jpeg",
    )


@login_obrigatorio
@require_GET
def status_processado(request, chave: str):
    """Informa ao navegador se a miniatura daquela chave já foi gerada.

    A página faz polling neste endpoint enquanto a Lambda trabalha. Quando o
    objeto aparece no bucket de processados, o JavaScript troca o cartão de
    "Processando" para a miniatura pronta, sem recarregar a página.
    """
    if not chave_pertence_ao_usuario(chave, request.usuario.id):
        raise Http404("Arquivo não encontrado.")

    try:
        processada = objeto_existe(
            settings.S3_BUCKET_PROCESSADOS,
            chave_miniatura(chave),
        )
    except ErroS3:
        logger.exception("Falha ao consultar o status da miniatura")
        return JsonResponse(
            {"processada": False, "erro": "Armazenamento indisponível."},
            status=503,
        )

    if not processada:
        return JsonResponse({"processada": False})

    return JsonResponse(
        {
            "processada": True,
            "url": reverse("ver_processado", kwargs={"chave": chave}),
            "download_url": reverse("baixar_processado", kwargs={"chave": chave}),
        }
    )


@login_obrigatorio
def baixar_processado(request, chave: str):
    if not chave_pertence_ao_usuario(chave, request.usuario.id):
        raise Http404("Arquivo não encontrado.")

    nome = _nome_original(request.usuario.id, chave)
    nome_miniatura = f"{posixpath.splitext(nome)[0]}_miniatura.jpg"
    return _entregar_arquivo(
        request,
        settings.S3_BUCKET_PROCESSADOS,
        chave_miniatura(chave),
        nome_miniatura,
        anexo=True,
        content_type_padrao="image/jpeg",
    )
