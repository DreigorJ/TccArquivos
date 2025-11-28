from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Produtos, Movimentacao, Categoria, PerfilUsuario, TabelaProdutos

User = get_user_model()


@admin.register(Produtos)
class ProdutosAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "tabela", "categoria", "quantidade", "preco", "criado_em")
    search_fields = ("nome", "categoria__nome", "tabela__nome")
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ("id", "produto", "tipo", "quantidade", "usuario", "criado_em", "quantidade_antes", "quantidade_depois")
    list_filter = ("tipo", "criado_em", "produto")
    search_fields = ("produto__nome", "descricao")
    readonly_fields = ("quantidade_antes", "quantidade_depois", "criado_em")


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "descricao")
    search_fields = ("nome",)


@admin.register(TabelaProdutos)
class TabelaProdutosAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "owner", "criado_em")
    search_fields = ("nome", "owner__username")
    filter_horizontal = ("acessos",)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "papel", "criado_em")
    search_fields = ("usuario__username", "papel")