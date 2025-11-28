from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import Produtos, Movimentacao, Categoria, PerfilUsuario, TabelaProdutos

User = get_user_model()


class ProdutosFormulario(forms.ModelForm):
    class Meta:
        model = Produtos
        fields = ["nome", "descricao", "categoria", "tabela", "quantidade", "preco"]


class MovimentacaoFormulario(forms.ModelForm):
    class Meta:
        model = Movimentacao
        fields = ["produto", "tipo", "quantidade", "descricao"]

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        quantidade = cleaned.get("quantidade")
        produto = cleaned.get("produto")

        if tipo == Movimentacao.TIPO_SAIDA and produto and quantidade is not None:
            if quantidade > produto.quantidade:
                raise forms.ValidationError("Quantidade para saída maior que estoque disponível.")
        return cleaned


class CategoriaFormulario(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nome", "descricao"]


class TabelaProdutosFormulario(forms.ModelForm):
    class Meta:
        model = TabelaProdutos
        fields = ["nome", "descricao", "owner", "acessos"]


class PerfilUsuarioFormulario(forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        fields = ["papel"]


class RegistroUsuarioForm(UserCreationForm):
    """
    Formulário aberto para auto-registro. Não permite atribuir papel ou tabelas.
    Perfil com papel padrão será criado automaticamente na view.
    """
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")