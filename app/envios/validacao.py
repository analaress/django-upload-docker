"""Validação de imagens pelo conteúdo real (Pillow), não pela extensão."""

from __future__ import annotations

from PIL import Image, UnidentifiedImageError
from django.conf import settings

# Evita imagens gigantes capazes de consumir memória excessiva (bombas de
# descompressão). O limite também é conferido manualmente abaixo.
Image.MAX_IMAGE_PIXELS = 30_000_000

FORMATOS_ACEITOS: dict[str, tuple[str, str]] = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "GIF": (".gif", "image/gif"),
    "WEBP": (".webp", "image/webp"),
}

EXTENSOES_ACEITAS = ", ".join(extensao for extensao, _tipo in FORMATOS_ACEITOS.values())


class ImagemInvalida(Exception):
    """A imagem não passou na validação de tipo/tamanho/conteúdo."""


def validar_imagem(arquivo) -> tuple[str, str, str]:
    """Valida o upload e devolve ``(formato, content_type, extensão)``.

    A extensão e o MIME informados pelo navegador não são confiáveis: o
    formato é identificado pelo Pillow ao abrir o conteúdo binário.
    """
    if arquivo.size == 0:
        raise ImagemInvalida("O arquivo está vazio.")

    limite = settings.LIMITE_TAMANHO_IMAGEM_MB * 1024 * 1024
    if arquivo.size > limite:
        raise ImagemInvalida(
            f"A imagem ultrapassa o limite de {settings.LIMITE_TAMANHO_IMAGEM_MB} MB."
        )

    formato = None
    try:
        with Image.open(arquivo) as imagem:
            formato = imagem.format
            if imagem.width * imagem.height > Image.MAX_IMAGE_PIXELS:
                raise ImagemInvalida("A imagem possui dimensões muito grandes.")
            imagem.verify()
    except ImagemInvalida:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ImagemInvalida("O arquivo não é uma imagem válida.") from exc
    finally:
        arquivo.seek(0)

    if formato not in FORMATOS_ACEITOS:
        raise ImagemInvalida(
            f"Formato não permitido. Envie {EXTENSOES_ACEITAS}."
        )

    extensao, content_type = FORMATOS_ACEITOS[formato]
    return formato, content_type, extensao
