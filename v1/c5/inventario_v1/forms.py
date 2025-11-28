from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from .models import Produtos, Movimentacao, PerfilUsuario, Categoria

User = get_user_model()


# helper to check if model has a field (compat com versões sem TabelaProdutos)
def _model_has_field(model, field_name):
    try:
        model._meta.get_field(field_name)
        return True
    except Exception:
        return False


class ProdutosFormulario(forms.ModelForm):
    class Meta:
        model = Produtos
        base_fields = ["nome", "descricao", "quantidade", "preco", "categoria"]
        if _model_has_field(Produtos, "tabelas"):
            base_fields.append("tabelas")
        fields = base_fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tornar quantidade opcional no formulário para permitir POSTs sem campo quantidade
        if "quantidade" in self.fields:
            self.fields["quantidade"].required = False
            # se não enviado, inicializamos com 0 para criação
            if self.instance and getattr(self.instance, "pk", None) is None:
                self.fields["quantidade"].initial = 0

    def clean(self):
        cleaned = super().clean()
        # se categoria vier como string vazia do POST, convertemos para None
        if "categoria" in cleaned and cleaned.get("categoria") == "":
            cleaned["categoria"] = None
        # garantir quantidade default 0 caso não informado
        if "quantidade" in cleaned and (cleaned.get("quantidade") is None or cleaned.get("quantidade") == ""):
            cleaned["quantidade"] = 0
        return cleaned


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
    nova_senha = forms.CharField(
        label="Nova senha",
        widget=forms.PasswordInput,
        required=False,
        help_text="Deixe em branco para não alterar a senha.",
    )
    confirmar_senha = forms.CharField(
        label="Confirmar senha",
        widget=forms.PasswordInput,
        required=False,
    )

    class Meta:
        model = PerfilUsuario
        base = ["papel", "observacao"]
        if _model_has_field(PerfilUsuario, "tabelas_permitidas"):
            base.append("tabelas_permitidas")
        fields = base
        widgets = {
            "tabelas_permitidas": forms.CheckboxSelectMultiple,
        }

    def clean(self):
        cleaned = super().clean()
        s = cleaned.get("nova_senha", "")
        c = cleaned.get("confirmar_senha", "")
        if s or c:
            if s != c:
                raise ValidationError("As senhas não coincidem.")
            if len(s) < 6:
                raise ValidationError("A senha deve ter ao menos 6 caracteres.")
        return cleaned


class CategoriaFormulario(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nome", "descricao"]


# formulário para TabelaProdutos (se o modelo existir)
try:
    from .models import TabelaProdutos  # type: ignore
except Exception:
    TabelaProdutos = None  # type: ignore

if TabelaProdutos is not None:
    class TabelaFormulario(forms.ModelForm):
        class Meta:
            model = TabelaProdutos
            fields = ["nome", "descricao"]


# ConfirmForm concreto para usar nas DeleteViews (confirmação simples)
class ConfirmForm(forms.Form):
    pass


# -------------------------
# Formulário de registro
# -------------------------
class RegistroFormulario(forms.ModelForm):
    """
    Formulário simples para permitir criação de usuário antes de logar.
    Campos: username, email (opcional), password1, password2
    """
    password1 = forms.CharField(label="Senha", widget=forms.PasswordInput, min_length=6)
    password2 = forms.CharField(label="Confirmar senha", widget=forms.PasswordInput, min_length=6)

    class Meta:
        model = User
        fields = ("username", "email")

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if not p1 or not p2 or p1 != p2:
            raise ValidationError("As senhas não coincidem.")
        if len(p1) < 6:
            raise ValidationError("A senha deve ter ao menos 6 caracteres.")
        return p2

    def save(self, commit=True, papel_default=None):
        user = super().save(commit=False)
        password = self.cleaned_data["password1"]
        user.set_password(password)
        if commit:
            user.save()
            # garantir criação do perfil (papel_default opcional)
            try:
                perfil_defaults = {"papel": papel_default} if papel_default else {}
                PerfilUsuario.objects.get_or_create(usuario=user, defaults=perfil_defaults)
            except Exception:
                # se PerfilUsuario não existir ou falhar, não quebrar o registro do user
                pass
        return user