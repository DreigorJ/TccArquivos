from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.apps import apps

from .models import Produto, Movimento, Categoria

Usuario = get_user_model()


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nome", "descricao", "ativo"]


class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ["nome", "descricao", "preco", "categoria"]


class MovimentoForm(forms.ModelForm):
    class Meta:
        model = Movimento
        fields = ["produto", "tipo_movimento", "quantidade", "motivo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "quantidade" in self.fields:
            self.fields["quantidade"].widget.attrs.update({"min": "1"})
            self.fields["quantidade"].label = "Quantidade"
        if "tipo_movimento" in self.fields:
            self.fields["tipo_movimento"].label = "Tipo de movimento"
        if "motivo" in self.fields:
            self.fields["motivo"].label = "Motivo (opcional)"

    def clean_quantidade(self):
        qnt = self.cleaned_data.get("quantidade")
        try:
            if qnt is None or int(qnt) <= 0:
                raise forms.ValidationError("A quantidade deve ser um número inteiro positivo!")
        except (TypeError, ValueError):
            raise forms.ValidationError("A quantidade deve ser um número inteiro positivo!")
        return int(qnt)


class UserCreateForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ("username", "email")


class UserUpdateForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = ("username", "email", "is_active", "is_staff")


# Optional models: load with apps.get_model and provide safe fallbacks if absent.
try:
    PerfilUsuario = apps.get_model("inventario_v3", "PerfilUsuario")
except LookupError:
    PerfilUsuario = None

if PerfilUsuario is not None:
    class UserProfileForm(forms.ModelForm):
        class Meta:
            model = PerfilUsuario
            fields = ("funcao", "ativo")
else:
    class UserProfileForm(forms.Form):
        funcao = forms.CharField(required=False)
        ativo = forms.BooleanField(required=False)


try:
    AcessoProdutos = apps.get_model("inventario_v3", "AcessoProdutos")
except LookupError:
    AcessoProdutos = None

if AcessoProdutos is not None:
    class ProductAccessForm(forms.ModelForm):
        class Meta:
            model = AcessoProdutos
            fields = ("usuario", "produto", "nivel")
else:
    class ProductAccessForm(forms.Form):
        usuario = forms.CharField(required=False)
        produto = forms.CharField(required=False)
        nivel = forms.CharField(required=False)