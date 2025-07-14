from django import forms
from .models import Produto, Categoria, Estoque, Metrica

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column

class CustomUserCreationForm(UserCreationForm):
    """Formulário para registro de novos usuários, incluindo nome completo e email."""
    nome = forms.CharField(max_length=150, label="Nome completo")
    email = forms.EmailField(max_length=254, label="Email", help_text="Obrigatório. Informe um email válido.")

    class Meta:
        model = User
        fields = ("username", "nome", "email", "password1", "password2")
        labels = {"username": "Login"}

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["nome"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class EstoqueForm(forms.ModelForm):
    """Formulário para cadastro/edição de estoques."""
    usuarios = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Usuários com acesso"
    )

    class Meta:
        model = Estoque
        fields = ['nome', 'usuarios']

    def __init__(self, *args, **kwargs):
        usuario_atual = kwargs.pop('usuario_atual', None)
        super().__init__(*args, **kwargs)
        if usuario_atual:
            self.fields['usuarios'].queryset = User.objects.exclude(pk=usuario_atual.pk)
        else:
            self.fields['usuarios'].queryset = User.objects.all()

class ProdutoForm(forms.ModelForm):
    """
    Formulário para cadastro/edição de produtos.
    Inclui campos para controle de cota mínima e checagem periódica.
    """
    precisa_alerta_cota = forms.BooleanField(
        required=False,
        label="Precisa alerta de cota mínima?",
        help_text="Se marcado, ativará o campo de cota mínima."
    )
    cota_minima = forms.IntegerField(
        required=False,
        min_value=1,
        initial=1,
        label="Cota Mínima",
        help_text="Quantidade mínima desejada. Se vazio, será 1."
    )
    checar_periodicamente = forms.BooleanField(
        required=False,
        label="Checar periodicamente?",
        help_text="Ativa a verificação automática da cota mínima."
    )
    intervalo_valor = forms.IntegerField(
        required=False,
        min_value=1,
        initial=30,
        label="Intervalo",
        help_text="A cada quantos dias/meses deseja a verificação? Ex: 30."
    )
    intervalo_tipo = forms.ChoiceField(
        choices=Produto.INTERVALO_CHOICES,
        required=False,
        initial='dias',
        label="Tipo de Intervalo"
    )

    class Meta:
        model = Produto
        fields = [
            'nome', 'categoria', 'marca', 'data_validade', 'preco', 'metrica', 'unidades',
            'precisa_alerta_cota', 'cota_minima', 'checar_periodicamente', 'intervalo_valor', 'intervalo_tipo'
        ]
        widgets = {
            'data_validade': forms.DateInput(attrs={'type': 'date'}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'preco': forms.NumberInput(attrs={'class': 'form-control'}),
            'metrica': forms.Select(attrs={'class': 'form-control'}),
            'unidades': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        estoque = kwargs.pop('estoque', None)
        super().__init__(*args, **kwargs)
        if estoque:
            self.fields['categoria'].queryset = Categoria.objects.filter(estoque=estoque)
        else:
            self.fields['categoria'].queryset = Categoria.objects.none()
        self.fields['unidades'].min_value = 0
        self.fields['unidades'].help_text = "Quantidade inicial do produto no estoque."
        self.fields['metrica'].queryset = Metrica.objects.all().order_by('-fixa', 'nome')
        self.helper = FormHelper()
        self.helper.template_pack = "bootstrap5"
        self.helper.layout = Layout(
            'nome',
            'categoria',
            'marca',
            'data_validade',
            'preco',
            Row(
                Column('unidades', css_class='col-md-6'),
                Column('metrica', css_class='col-md-6'),
                css_class='row'
            ),
            'precisa_alerta_cota',
            'cota_minima',
            'checar_periodicamente',
            Row(
                Column('intervalo_valor', css_class='col-md-6'),
                Column('intervalo_tipo', css_class='col-md-6'),
                css_class='row'
            ),
        )

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nome']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da categoria'}),
        }

class MetricaForm(forms.ModelForm):
    class Meta:
        model = Metrica
        fields = ['nome', 'codigo', 'fixa']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da métrica'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código da métrica'}),
            'fixa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }