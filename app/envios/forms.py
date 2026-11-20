"""Formulários de cadastro, login e upload de imagens."""

from __future__ import annotations

from django import forms
from django.conf import settings

from .aws.usuarios import normalizar_email


class FormularioCadastro(forms.Form):
    nome = forms.CharField(
        label="Nome",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Seu nome"}),
    )
    email = forms.EmailField(
        label="E-mail",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "voce@exemplo.com"}),
    )
    senha = forms.CharField(
        label="Senha",
        min_length=8,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Mínimo de 8 caracteres.",
    )
    confirmar_senha = forms.CharField(
        label="Confirme a senha",
        min_length=8,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_nome(self):
        nome = self.cleaned_data["nome"].strip()
        if not nome:
            raise forms.ValidationError("Informe seu nome.")
        return nome

    def clean_email(self):
        return normalizar_email(self.cleaned_data["email"])

    def clean(self):
        dados = super().clean()
        senha = dados.get("senha")
        confirmacao = dados.get("confirmar_senha")
        if senha and confirmacao and senha != confirmacao:
            self.add_error("confirmar_senha", "As senhas não conferem.")
        return dados


class FormularioLogin(forms.Form):
    email = forms.EmailField(
        label="E-mail",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "voce@exemplo.com"}),
    )
    senha = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def clean_email(self):
        return normalizar_email(self.cleaned_data["email"])


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Campo de arquivo que aceita uma lista de uploads."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        limpar_um = super().clean
        if data in (None, "", [], (), {}):
            # Deixa o FileField aplicar a validação de obrigatoriedade.
            limpar_um(data, initial)
            return []
        if isinstance(data, (list, tuple)):
            return [limpar_um(item, initial) for item in data]
        return [limpar_um(data, initial)]


class FormularioUploadImagens(forms.Form):
    imagens = MultipleFileField(
        label="Imagens",
        widget=MultipleFileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/gif,image/webp",
                "class": "entrada-arquivo",
            }
        ),
    )

    def clean_imagens(self):
        imagens = self.cleaned_data["imagens"]
        if len(imagens) > settings.LIMITE_ARQUIVOS_POR_ENVIO:
            raise forms.ValidationError(
                f"Envie no máximo {settings.LIMITE_ARQUIVOS_POR_ENVIO} imagens por vez."
            )
        return imagens
