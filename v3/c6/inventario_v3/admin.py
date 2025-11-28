from django.contrib import admin
from .models import Produto, Movimento, Categoria, PerfilUsuario, TabelaProdutos, AcessoTabela


@admin.register(TabelaProdutos)
class TabelaProdutosAdmin(admin.ModelAdmin):
    list_display = ("nome", "publico", "criado_em", "criado_por")
    search_fields = ("nome",)


@admin.register(AcessoTabela)
class AcessoTabelaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tabela", "nivel", "criado_em")
    search_fields = ("usuario__username", "tabela__nome", "nivel")
    list_filter = ("nivel",)


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'quantidade', 'preco', 'categoria')
    search_fields = ('nome',)
    list_filter = ('categoria',)


@admin.register(Movimento)
class MovimentoAdmin(admin.ModelAdmin):
    list_display = ('produto', 'quantidade', 'motivo', 'criado_em', 'usuario')
    list_filter = ('criado_em',)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "criado_em")
    search_fields = ("nome",)
    list_filter = ("ativo",)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("usuario", "funcao", "ativo", "criado_em")
    search_fields = ("funcao", "usuario__username")
    list_filter = ("funcao", "ativo")