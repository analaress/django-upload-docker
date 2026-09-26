from pathlib import Path
from django import forms
from .models import ArquivoEnviado


class ArquivoEnviadoForm(forms.ModelForm):
    extensoes_permitidas = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".docx", ".pptx"}
    tamanho_maximo = 10 * 1024 * 1024
    class Meta:
        model = ArquivoEnviado
        fields = ["arquivo"]

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        extensao = Path(arquivo.name).suffix.lower()
        if extensao not in self.extensoes_permitidas:
            raise forms.ValidationError(
                "Este tipo de arquivo não é permitido. "
                "Use PDF, PNG, JPG, TXT, DOCX ou PPTX."
            )
        if arquivo.size > self.tamanho_maximo:
            raise forms.ValidationError("O arquivo não pode ultrapassar 10 MB.")
        return arquivo
        
    def save(self, commit=True):
        instancia = super().save(commit=False)
        instancia.nome_original = self.cleaned_data["arquivo"].name
        instancia.tamanho_em_bytes = self.cleaned_data["arquivo"].size
        if commit:
            instancia.save()
        return instancia
