from django import forms


class FormularioCadastro(forms.Form):
    nome = forms.CharField(
        max_length=120,
        label="Nome",
        widget=forms.TextInput(attrs={"class": "campo-input", "placeholder": "Seu nome"}),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(
            attrs={"class": "campo-input", "placeholder": "voce@exemplo.com"}
        ),
    )
    senha = forms.CharField(
        min_length=8,
        label="Senha",
        widget=forms.PasswordInput(
            attrs={"class": "campo-input", "placeholder": "••••••••"}
        ),
    )
    confirmar_senha = forms.CharField(
        min_length=8,
        label="Confirmar senha",
        widget=forms.PasswordInput(
            attrs={"class": "campo-input", "placeholder": "••••••••"}
        ),
    )

    def clean(self):
        dados = super().clean()
        if dados.get("senha") != dados.get("confirmar_senha"):
            raise forms.ValidationError("As senhas precisam ser iguais.")
        return dados


class FormularioLogin(forms.Form):
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(
            attrs={"class": "campo-input", "placeholder": "voce@exemplo.com"}
        ),
    )
    senha = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(
            attrs={"class": "campo-input", "placeholder": "••••••••"}
        ),
    )
