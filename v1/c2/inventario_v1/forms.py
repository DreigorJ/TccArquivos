from django import forms
from .models import Produtos, Movimentacao, PerfilUsuario

class ProdutosFormulario(forms.ModelForm):
    class Meta:
        model = Produtos
        fields = ["nome", "descricao", "quantidade", "preco"]

class MovimentacaoFormulario(forms.ModelForm):
    class Meta:
        model = Movimentacao
        fields = ["produto", "tipo", "quantidade", "observacao"]

    def clean_quantidade(self):
        q = self.cleaned_data.get("quantidade")
        if q is None or q <= 0:
            raise forms.ValidationError("Quantidade deve ser maior que zero.")
        return q

class PerfilUsuarioFormulario(forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        fields = ["papel", "observacao"]