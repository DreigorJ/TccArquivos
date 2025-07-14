from django.contrib import admin
from .models import Estoque, Categoria, Produto, Movimentacao

@admin.register(Estoque)
class EstoqueAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    filter_horizontal = ('usuarios',)

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'estoque')

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'marca', 'data_validade', 'categoria', 'preco', 'unidades', 'metrica', 'estoque')
    list_filter = ('estoque', 'categoria', 'metrica')

@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ('produto', 'tipo', 'quantidade', 'data')
    list_filter = ('tipo', 'produto')