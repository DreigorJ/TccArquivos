from django import forms
from .models import Produtos, Movimentacao

class ProdutosFormulario(forms.ModelForm):
    class Meta:
        model = Produtos
        fields = ["nome", "descricao", "quantidade", "preco"]

class MovimentacaoFormulario(forms.ModelForm):
    class Meta:
        model = Movimentacao
        fields = ["produto", "tipo", "quantidade", "descricao"]

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo')
        quantidade = cleaned.get('quantidade')
        produto = cleaned.get('produto')

        if tipo == Movimentacao.TIPO_SAIDA and produto and quantidade is not None:
            if quantidade > produto.quantidade:
                raise forms.ValidationError("Quantidade para saída maior que estoque disponível.")
        return cleaned