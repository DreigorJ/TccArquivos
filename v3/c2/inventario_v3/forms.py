from django import forms
from .models import Produto, Movimento

class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ['nome', 'descricao', 'preco', 'categoria']

class MovimentoForm(forms.ModelForm):
    class Meta:
        model = Movimento
        fields = ['tipo_movimento', 'quantidade', 'motivo']

    def __init__(self, *args, **kwargs):
        super(MovimentoForm, self).__init__(*args, **kwargs)
        # labels e placeholders opcionais:
        if 'quantidade' in self.fields:
            self.fields['quantidade'].widget.attrs.update({'min': '1'})
            self.fields['quantidade'].label = 'Quantidade'
        if 'tipo_movimento' in self.fields:
            self.fields['tipo_movimento'].label = 'Tipo de movimento'
        if 'motivo' in self.fields:
            self.fields['motivo'].label = 'Motivo (opcional)'

    def clean_quantidade(self):
        qnt = self.cleaned_data.get('quantidade')
        if qnt is None or qnt <= 0:
            raise forms.ValidationError("A quantidade deve ser um número inteiro positivo!")
        return qnt