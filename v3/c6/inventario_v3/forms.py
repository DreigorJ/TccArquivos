from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password

from .models import Produto, Movimento, Categoria, TabelaProdutos, AcessoTabela, PerfilUsuario

Usuario = get_user_model()


class TabelaProdutosForm(forms.ModelForm):
    class Meta:
        model = TabelaProdutos
        fields = ("nome", "descricao", "publico")


class AcessoTabelaForm(forms.ModelForm):
    class Meta:
        model = AcessoTabela
        fields = ("usuario", "tabela", "nivel")


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nome", "descricao", "ativo"]


class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ['nome', 'descricao', 'preco', 'categoria', 'tabelas']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tabelas'].widget.attrs.update({'size': 6})


class MovimentoForm(forms.ModelForm):
    class Meta:
        model = Movimento
        fields = ['tipo_movimento', 'quantidade', 'motivo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # labels e placeholders opcionais:
        self.fields['quantidade'].widget.attrs.update({'min': '1'})
        self.fields['tipo_movimento'].label = 'Tipo de movimento'
        self.fields['quantidade'].label = 'Quantidade'
        self.fields['motivo'].label = 'Motivo (opcional)'

    def clean_quantidade(self):
        qnt = self.cleaned_data.get('quantidade')
        if qnt is None or qnt <= 0:
            raise forms.ValidationError("A quantidade deve ser um número inteiro positivo!")
        return qnt


# --- User forms ---
class UserCreateForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ("username", "email")


class UserUpdateForm(forms.ModelForm):
    """
    Form para edição de usuário por staff. Inclui campos opcionais password1/password2.
    Se password1 for preenchido e válido, a senha do usuário será alterada.
    """
    password1 = forms.CharField(
        label="Nova senha",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        required=False,
        help_text="Deixe em branco para manter a senha atual."
    )
    password2 = forms.CharField(
        label="Confirme a nova senha",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        required=False
    )

    class Meta:
        model = Usuario
        fields = ("username", "email", "is_active", "is_staff")

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")

        if p1 or p2:
            if p1 != p2:
                raise forms.ValidationError("As senhas não coincidem.")
            # valida força/complexidade da senha usando validators do Django
            try:
                validate_password(p1, self.instance)
            except forms.ValidationError as ve:
                # adiciona o erro ao campo password1 para exibição no template
                self.add_error("password1", ve)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        new_password = self.cleaned_data.get("password1")
        if new_password:
            user.set_password(new_password)
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        # usar o nome correto do campo no model (funcao, não role)
        fields = ("funcao", "ativo")