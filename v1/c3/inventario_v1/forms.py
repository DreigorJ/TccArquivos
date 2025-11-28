from django import forms
from .models import Produtos, Movimentacao, PerfilUsuario, Categoria

class ProdutosFormulario(forms.ModelForm):
    class Meta:
        model = Produtos
        fields = ["nome", "descricao", "quantidade", "preco", "categoria"]

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

class CategoriaFormulario(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nome", "descricao"]

# ConfirmForm concreto para usar nas DeleteViews (confirmação simples)
class ConfirmForm(forms.Form):
    """
    Formulário vazio usado apenas para habilitar o FormMixin nas DeleteViews.
    Ter um tipo concreto evita erros de type-checkers ao atribuir form_class.
    """
    pass