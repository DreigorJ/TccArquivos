from django import forms
from .models import Produtos

class ProdutosFormulario(forms.ModelForm):
    class Meta:
        model = Produtos
        fields = ["nome", "descricao", "quantidade", "preco"]