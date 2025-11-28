from django.contrib import admin
from .models import Produtos, Movimentacao

@admin.register(Produtos)
class ProdutosAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'quantidade', 'preco', 'criado_em')
    search_fields = ('nome',)
    readonly_fields = ('criado_em', 'atualizado_em')

@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'produto', 'tipo', 'quantidade', 'usuario', 'criado_em', 'quantidade_antes', 'quantidade_depois')
    list_filter = ('tipo', 'criado_em', 'produto')
    search_fields = ('produto__nome', 'descricao')
    readonly_fields = ('quantidade_antes', 'quantidade_depois', 'criado_em')